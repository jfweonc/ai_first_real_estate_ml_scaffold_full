from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys, datetime
from typing import Optional, List
import yaml, requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUS = ROOT / "bus"
POLICY = ROOT / "policy" / "orchestrator.yaml"

def now_id() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def load_yaml(p: pathlib.Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def save_text(p: pathlib.Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def run_runner(role: str, goal: Optional[str]=None, files: Optional[List[str]]=None,
               for_rfc: Optional[str]=None, for_proposal: Optional[str]=None, decide_rfc: Optional[str]=None) -> str:
    cmd = [sys.executable, str(ROOT / "tools" / "agent_runner.py"), "--role", role]
    if goal:
        cmd += ["--goal", goal]
    if files:
        cmd += ["--files", *files]
    if for_rfc:
        cmd += ["--for-rfc", for_rfc]
    if for_proposal:
        cmd += ["--for-proposal", for_proposal]
    if decide_rfc:
        cmd += ["--decide", decide_rfc]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"agent_runner failed: {out.stderr}")
    return out.stdout

def post_openai(model: str, prompt_text: str, max_output_tokens: int = 4000) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    url = "https://api.openai.com/v1/responses"
    payload = {
        "model": model,
        "input": [
            {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
        ],
        "max_output_tokens": max_output_tokens
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    r.raise_for_status()
    return r.json()

def pick_next_story(backlog: dict) -> Optional[dict]:
    must = [s for s in backlog.get("stories", []) if s.get("status")=="ready" and s.get("priority")=="Must"]
    if must:
        return must[0]
    ready = [s for s in backlog.get("stories", []) if s.get("status")=="ready"]
    return ready[0] if ready else None

def orchestrate_slice(story_id: str) -> None:
    pol = load_yaml(POLICY)
    backlog = load_yaml(ROOT / "docs" / "backlog.yaml")
    story = next((s for s in backlog.get("stories", []) if s.get("id")==story_id), None)
    if not story:
        raise SystemExit(f"Story {story_id} not found in docs/backlog.yaml")
    lane = story.get("lane","build")
    lane_roles = pol["lanes"].get(lane, ["test","backend","test"])

    prompt_files = pol["prompt_files"]["common"]
    acceptance = "\n".join(f"- {a}" for a in story.get("acceptance", []))

    # TEST -> failing tests
    if lane_roles and lane_roles[0] == "test":
        goal = f"Write failing tests for story {story_id}: {story.get('title')}"
        prompt = run_runner("test", goal=goal, files=prompt_files)
        prompt += f"\n\n### ACCEPTANCE TO ENCODE IN TESTS\n{acceptance}\n"
        res = post_openai(pol["role_to_model"]["test"], prompt)
        save_text(BUS / "proposals" / f"TEST-{story_id}-{now_id()}.json", json.dumps(res, indent=2))

    # BACKEND -> implement
    if len(lane_roles) > 1 and lane_roles[1] == "backend":
        goal = f"Implement code to satisfy tests for story {story_id}: {story.get('title')}"
        prompt = run_runner("backend", goal=goal, files=prompt_files)
        res = post_openai(pol["role_to_model"]["backend"], prompt)
        save_text(BUS / "proposals" / f"BACKEND-{story_id}-{now_id()}.json", json.dumps(res, indent=2))

    # TEST -> verify
    if len(lane_roles) > 2 and lane_roles[2] == "test":
        goal = f"Verify tests pass for story {story_id} and extend negative tests if gaps exist"
        prompt = run_runner("test", goal=goal, files=prompt_files)
        res = post_openai(pol["role_to_model"]["test"], prompt)
        save_text(BUS / "critiques" / f"TEST-VERIFY-{story_id}-{now_id()}.json", json.dumps(res, indent=2))

def main() -> None:
    ap = argparse.ArgumentParser(description="Policy-driven orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-backlog", help="Validate backlog is present")
    sub.add_parser("next", help="Pick the next ready story and orchestrate")
    p3 = sub.add_parser("run", help="Run a specific story id")
    p3.add_argument("--id", required=True)
    args = ap.parse_args()

    if args.cmd == "init-backlog":
        print("Backlog present at docs/backlog.yaml")
        return
    if args.cmd == "next":
        backlog = load_yaml(ROOT / "docs" / "backlog.yaml")
        story = pick_next_story(backlog)
        if not story:
            print("No ready stories found.")
            return
        orchestrate_slice(story["id"])
        return
    if args.cmd == "run":
        orchestrate_slice(args.id)
        return

if __name__ == "__main__":
    main()
