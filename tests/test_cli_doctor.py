from __future__ import annotations
import subprocess, sys

def test_cli_doctor_exits_zero() -> None:
    out = subprocess.run([sys.executable, "-m", "src.relml.cli", "doctor"], capture_output=True, text=True)
    assert out.returncode == 0
    assert "environment ok" in out.stdout.lower()
