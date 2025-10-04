from __future__ import annotations

import argparse
import datetime
import pathlib
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]

HEADER = (
    "\n### HOW TO USE\n"
    "Copy everything below into your AI chat as a single message.\n"
    "Return ONLY the requested format (JSON or unified diffs).\n"
)


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def load_files(paths: list[str]) -> str:
    blocks = []
    for s in paths:
        p = (ROOT / s).resolve()
        if p.is_dir():
            continue
        if not p.exists():
            blocks.append(f"\n<!-- MISSING: {s} -->\n")
            continue
        content = read(p)
        blocks.append(f"\n===== FILE: {s} =====\n{content}\n")
    return "\n".join(blocks)


ROLE_FILES = {
    "manager": ".agents/manager.md",
    "pm": ".agents/pm.md",
    "architect": ".agents/architect.md",
    "backend": ".agents/backend.md",
    "frontend": ".agents/frontend.md",
    "test": ".agents/test.md",
    "data_ml": ".agents/data_ml.md",
    "security": ".agents/security.md",
    "sre": ".agents/sre.md",
}

DEF_CONTEXT = [
    ".agents/guardrails.md",
    "context/phase_plan.md",
    "context/file_map.md",
]

SCHEMA_HINT = "Contracts you must respect live under contracts/*. Do not change them without producing an ADR."


def prompt_for_role(role: str, goal: str | None, files: list[str]) -> str:
    role_md = read(ROOT / ROLE_FILES[role])
    guard = load_files(DEF_CONTEXT)
    ctx = load_files(files)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    pre = textwrap.dedent(
        f"""
        ## Context
        - Timestamp: {now}
        - Role: {role}
        - Goal: {goal or ''}
        - Engine hint: use GPT-5 for manager/pm/architect/security/sre/data_ml; Codex for backend/test/frontend.
        - {SCHEMA_HINT}
        """
    )
    return "\n".join(
        [
            HEADER,
            "\n### ROLE DESCRIPTION\n" + role_md,
            pre,
            "\n### CONTRACT FILES\n" + guard,
            "\n### PROJECT FILES\n" + ctx,
        ]
    )


def emit_rfc(goal: str, files: list[str]) -> None:
    rfc_id = f"RFC-{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H%M%S')}"
    prompt = prompt_for_role("manager", goal, files)
    print(prompt)
    print(f"\n# Save the returned JSON to bus/rfc/{rfc_id}.json\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=list(ROLE_FILES.keys()))
    ap.add_argument("--goal", default=None)
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--engine", default="gpt5", help="hint only; not used programmatically")
    ap.add_argument("--emit", choices=["rfc"], default=None)
    ap.add_argument("--for-rfc", dest="for_rfc", help="prepare proposal prompt for RFC id")
    ap.add_argument("--for-proposal", dest="for_proposal", help="prepare critique prompt for proposal id")
    ap.add_argument("--decide", dest="decide_rfc", help="prepare decision prompt for RFC id")
    args = ap.parse_args()

    files = args.files or []

    if args.emit == "rfc" and args.role == "manager":
        return emit_rfc(args.goal or "", files or ["context/phase_plan.md"])  # prints the prompt

    if args.for_rfc and args.role in {"architect", "backend", "pm", "security", "sre", "data_ml"}:
        rfc_path = ROOT / f"bus/rfc/{args.for_rfc}.json"
        files = files + [str(rfc_path.relative_to(ROOT))] if rfc_path.exists() else files
        print(prompt_for_role(args.role, f"Propose for {args.for_rfc}", files))
        return

    if args.for_proposal and args.role in {"test", "security", "sre", "pm", "architect"}:
        prop_path = ROOT / f"bus/proposals/{args.for_proposal}.json"
        files = files + [str(prop_path.relative_to(ROOT))] if prop_path.exists() else files
        print(prompt_for_role(args.role, f"Critique {args.for_proposal}", files))
        return

    if args.decide_rfc and args.role == "manager":
        rfc_path = ROOT / f"bus/rfc/{args.decide_rfc}.json"
        props = list((ROOT / "bus/proposals").glob(f"*{args.decide_rfc}*.json"))
        files2 = files.copy()
        if rfc_path.exists():
            files2.append(str(rfc_path.relative_to(ROOT)))
        files2 += [str(p.relative_to(ROOT)) for p in props]
        print(prompt_for_role("manager", f"Decide {args.decide_rfc}", files2))
        return

    print(prompt_for_role(args.role, args.goal, files))


if __name__ == "__main__":
    main()
