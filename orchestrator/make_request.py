from __future__ import annotations

import platform
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def gather_git_diff(limit: int = 20000) -> str:
    try:
        proc = subprocess.run(["git", "diff"], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False)
        out = proc.stdout or ""
        if len(out) > limit:
            out = out[:limit] + "\n...[truncated]..."
        return out
    except Exception:
        return "(git diff unavailable)"


def gather_last_test_output(limit: int = 10000) -> str:
    path = REPO_ROOT / ".ai" / "last_test_output.txt"
    if not path.exists():
        return "(no prior quick test results)"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        text = text[:limit] + "\n...[truncated]..."
    return text


def build_request_body(*, diff_text: str, test_output: str) -> str:
    template = (
        "Please produce a Context Digest and a step-by-step execution plan (no code yet) for Steps 1-3.\n\n"
        "Context pins:\n"
        "- brief: project_brief@v1\n"
        "- schema: mls_schema@v3\n"
        "- guardrails: guardrails@v2\n"
        "- python: 3.11, style: ruff\n\n"
        "Phase manifest: phases/phase_current_manifest.yaml\n\n"
        "Current diff (truncated):\n{DIFF}\n\n"
        "Latest quick test result (truncated):\n{TEST}\n\n"
        "Return:\n"
        "1) Context Digest (files + versions you read; key assumptions)\n"
        "2) Plan with `targets` (file list) and `acceptance` (pytest node IDs) for Steps 3b-6 next cycle\n"
        "3) Risks/edge cases + rollback notes\n"
        "(No patches yet.)\n"
    )
    return template.format(DIFF=diff_text.strip(), TEST=test_output.strip())


def maybe_copy_to_clipboard(text: str) -> None:
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.run(["clip"], input=text, text=True, capture_output=True, check=False)
        elif system == "Darwin":
            subprocess.run(["pbcopy"], input=text, text=True, capture_output=True, check=False)
    except Exception:
        pass
