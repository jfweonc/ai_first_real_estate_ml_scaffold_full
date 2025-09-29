"""
Spec: Phase 0.5 — CSV ingest & coverage inventory

How to run locally:
    pytest -q tests/specs/test_phase05_csv_ingest_spec.py

Notes:
- This spec encodes acceptance for the Phase 0.5 thin slice.
- Tests are marked xfail until Backend implements the CLI.
"""
from __future__ import annotations
import pathlib, subprocess, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

@pytest.mark.xfail(strict=True, reason="CLI not implemented yet (relml import-csv)")
def test_import_csv_command_exists_and_runs_help() -> None:
    cmd = [sys.executable, "-m", "src.relml.cli", "import-csv", "--help"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0
    assert "import-csv" in out.stdout.lower()

@pytest.mark.xfail(strict=True, reason="Coverage report not implemented yet")
def test_coverage_report_artifacts_layout() -> None:
    reports = ROOT / "data" / "reports"
    assert reports.exists()

@pytest.mark.xfail(strict=True, reason="Idempotence not implemented yet")
def test_rerun_is_noop_exit_code_zero() -> None:
    cmd = [sys.executable, "-m", "src.relml.cli", "import-csv", "--root", "data/raw"]
    out1 = subprocess.run(cmd, capture_output=True, text=True)
    out2 = subprocess.run(cmd, capture_output=True, text=True)
    assert out1.returncode == 0
    assert out2.returncode == 0
