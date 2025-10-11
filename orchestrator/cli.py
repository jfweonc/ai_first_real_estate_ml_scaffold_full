from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

from .diff_utils import PatchError, apply_patch_file, read_manifest_targets
from .make_request import build_request_body, gather_git_diff, gather_last_test_output, maybe_copy_to_clipboard

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_DIR = REPO_ROOT / ".ai"
BUS_DIR = AI_DIR / "bus"
PLAN_DIR = AI_DIR / "plan"
STATUS_FILE = AI_DIR / "status.md"
LAST_APPLIED = AI_DIR / "last_applied.json"
LAST_TEST_OUTPUT = AI_DIR / "last_test_output.txt"
PHASE_MANIFEST = REPO_ROOT / "phases" / "phase_current_manifest.yaml"


def _ensure_dirs() -> None:
    for path in (AI_DIR, BUS_DIR, PLAN_DIR):
        path.mkdir(parents=True, exist_ok=True)


def cmd_emit(_: argparse.Namespace) -> int:
    _ensure_dirs()
    notice: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase_manifest": str(PHASE_MANIFEST),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "targets": sorted(read_manifest_targets(PHASE_MANIFEST)),
        "diff": gather_git_diff(limit=20000),
    }
    (BUS_DIR / "notice.json").write_text(json.dumps(notice, indent=2), encoding="utf-8")
    print(str(BUS_DIR / "notice.json"))
    return 0


def cmd_plan_request(_: argparse.Namespace) -> int:
    _ensure_dirs()
    skeleton = {
        "phase": "current",
        "targets": [],
        "acceptance": [],
        "constraints": {"py": "3.11", "style": "ruff"},
    }
    (PLAN_DIR / "phase_plan.json").write_text(json.dumps(skeleton, indent=2), encoding="utf-8")
    print(str(PLAN_DIR / "phase_plan.json"))
    return 0


def cmd_make_request(_: argparse.Namespace) -> int:
    _ensure_dirs()
    diff = gather_git_diff(limit=20000)
    test_out = gather_last_test_output(limit=10000)
    body = build_request_body(diff_text=diff, test_output=test_out)
    req_path = BUS_DIR / "request_for_gpt5.txt"
    req_path.write_text(body, encoding="utf-8")
    print(str(req_path))
    maybe_copy_to_clipboard(body)
    return 0


def cmd_call_gpt5(_: argparse.Namespace) -> int:
    _ensure_dirs()
    req_path = BUS_DIR / "request_for_gpt5.txt"
    if not req_path.exists():
        print("No request file found. Run `python -m orchestrator.cli make-request` first.", file=sys.stderr)
        return 2
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set. Please copy/paste the request manually.", file=sys.stderr)
        return 2
    try:
        requests_module = cast(Any, importlib.import_module("requests"))
    except ModuleNotFoundError:
        print("`requests` is not installed. Install it or use the copy/paste flow.", file=sys.stderr)
        return 2
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-5",
        "messages": [
            {"role": "system", "content": "You are a planning assistant. Return JSON only."},
            {"role": "user", "content": req_path.read_text(encoding="utf-8")},
        ],
        "temperature": 0.2,
    }
    try:
        resp = requests_module.post(url, headers=headers, json=payload, timeout=120)
        if not resp.ok:
            print(f"GPT-5 API error {resp.status_code}: {resp.text}", file=sys.stderr)
            return 2
        data = resp.json()
        (PLAN_DIR / "gpt5_response.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(str(PLAN_DIR / "gpt5_response.json"))
        return 0
    except Exception as exc:
        print(f"GPT-5 call failed: {exc}", file=sys.stderr)
        return 2


def cmd_apply(ns: argparse.Namespace) -> int:
    _ensure_dirs()
    patch_path = Path(ns.patch).expanduser().resolve()
    try:
        changed = apply_patch_file(
            patch_file=patch_path,
            repo_root=REPO_ROOT,
            manifest_path=PHASE_MANIFEST,
        )
        LAST_APPLIED.write_text(
            json.dumps({"changed": changed, "at": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )
        print("\n".join(changed))
        return 0
    except PatchError as exc:
        print(f"apply failed: {exc}", file=sys.stderr)
        return 2


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    if cmd and cmd[0] == "python":
        cmd = [sys.executable, *cmd[1:]]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _quick_syntax_scan(paths: list[Path]) -> str:
    checked = 0
    ok = 0
    errors: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for src in base.rglob("*.py"):
            checked += 1
            try:
                compile(src.read_text(encoding="utf-8"), str(src), "exec")
                ok += 1
            except Exception as exc:  # pragma: no cover - summarized
                errors.append(f"{src}: {exc}")
    summary = f"Quick syntax scan: {ok}/{checked} OK"
    if errors:
        summary += f" | Errors: {len(errors)}"
    return summary


def cmd_test(_: argparse.Namespace) -> int:
    _ensure_dirs()
    accept: list[str] = []
    try:
        lines = PHASE_MANIFEST.read_text(encoding="utf-8").splitlines()
        in_accept = False
        for raw in lines:
            line = raw.rstrip()
            if not in_accept and line.strip().startswith("acceptance:"):
                in_accept = True
                continue
            if in_accept:
                stripped = line.strip()
                if stripped.startswith("- "):
                    accept.append(stripped[2:].strip())
                elif stripped and not stripped.startswith("#"):
                    break
    except Exception:
        accept = []
    output = ""
    rc = 0
    if accept:
        results: list[str] = []
        for item in accept:
            parts = item.split()
            proc = _run_subprocess(parts)
            results.append("$ " + " ".join(parts) + "\n" + proc.stdout + proc.stderr)
            if proc.returncode != 0:
                rc = proc.returncode
        output = "\n\n".join(results)
    else:
        output = _quick_syntax_scan([REPO_ROOT / "orchestrator", REPO_ROOT / "src"])
        rc = 0
    LAST_TEST_OUTPUT.write_text(output, encoding="utf-8")
    print(output)
    return rc


def cmd_status(_: argparse.Namespace) -> int:
    _ensure_dirs()
    changed: list[str] = []
    if LAST_APPLIED.exists():
        try:
            data = json.loads(LAST_APPLIED.read_text(encoding="utf-8"))
            changed = data.get("changed", [])
        except Exception:
            changed = []
    test_summary = gather_last_test_output(limit=2000)
    md = [
        f"# Status @ {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Changed Files",
    ]
    if changed:
        md.extend(f"- {path}" for path in changed)
    else:
        md.append("- (none)")
    md.extend(
        [
            "",
            "## Quick Test Summary",
            "```",
            test_summary.strip() or "(no recent test summary)",
            "```",
            "",
            "## Next Suggested Commands",
            "- `python -m orchestrator.cli make-request`",
            "- `python -m orchestrator.cli call-gpt5`  (optional)",
            "- `python -m orchestrator.cli apply patches/0001.diff`",
            "- `python -m orchestrator.cli test`",
        ]
    )
    STATUS_FILE.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(str(STATUS_FILE))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator", description="Local orchestrator CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit", help="Capture current diff, env pins, manifest ref").set_defaults(func=cmd_emit)
    sub.add_parser("plan-request", help="Write empty plan skeleton").set_defaults(func=cmd_plan_request)
    sub.add_parser("make-request", help="Create paste-ready planning request").set_defaults(func=cmd_make_request)
    sub.add_parser("call-gpt5", help="Optional GPT-5 API call").set_defaults(func=cmd_call_gpt5)
    p_apply = sub.add_parser("apply", help="Guarded apply of unified diffs")
    p_apply.add_argument("patch", help="Path to patch file")
    p_apply.set_defaults(func=cmd_apply)
    sub.add_parser("test", help="Run focused acceptance tests or quick scan").set_defaults(func=cmd_test)
    sub.add_parser("status", help="Write status and next steps").set_defaults(func=cmd_status)
    ns = parser.parse_args(argv)
    handler = cast(Callable[[argparse.Namespace], int], ns.func)
    return handler(ns)


if __name__ == "__main__":
    raise SystemExit(main())
