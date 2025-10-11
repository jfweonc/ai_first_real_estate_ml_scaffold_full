from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True, check=False)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_apply_rejects_non_allowlisted(tmp_path: Path) -> None:
    patch = tmp_path / "bad.diff"
    _write(
        patch,
        """*** Begin Patch
*** Add File: NOT_ALLOWED.txt
+Hello
*** End Patch
""",
    )
    out = _run([sys.executable, "-m", "orchestrator.cli", "apply", str(patch)])
    assert out.returncode != 0
    assert "allowlist" in (out.stderr or "").lower()


def test_apply_blocks_path_traversal(tmp_path: Path) -> None:
    patch = tmp_path / "traverse.diff"
    _write(
        patch,
        """*** Begin Patch
*** Add File: ../evil.txt
+Nope
*** End Patch
""",
    )
    out = _run([sys.executable, "-m", "orchestrator.cli", "apply", str(patch)])
    assert out.returncode != 0
    err = (out.stderr or "").lower()
    assert "unsafe path" in err or "allowlist" in err


def test_apply_accepts_minimal_allowed(tmp_path: Path) -> None:
    tasks_path = ROOT / ".vscode" / "tasks.json"
    original = tasks_path.read_text(encoding="utf-8") if tasks_path.exists() else ""
    payload = '{\n  "version": "2.0.0",\n  "tasks": []\n}\n'
    payload_for_patch = payload.replace("\n", "\n+")
    body = f"""*** Begin Patch
*** Add File: .vscode/tasks.json
+{payload_for_patch}
*** End Patch
"""
    patch = tmp_path / "ok.diff"
    _write(patch, body)
    try:
        out = _run([sys.executable, "-m", "orchestrator.cli", "apply", str(patch)])
        assert out.returncode == 0, out.stderr
        assert '"version": "2.0.0"' in tasks_path.read_text(encoding="utf-8")
    finally:
        tasks_path.write_text(original, encoding="utf-8")
