"""
Spec: Phase 1 - Data ingestion & coverage inventory

How to run locally:
    pytest -q tests/specs/test_phase01_csv_ingest_spec.py

Notes:
- This spec encodes acceptance for the Phase 1 thin slice.
- Remaining tests stay xfail until the Backend slice lands.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_import_csv_command_exists_and_runs_help() -> None:
    cmd = [sys.executable, "-m", "src.relml.cli", "import-csv", "--help"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert out.returncode == 0
    stdout = out.stdout.lower()
    assert "import-csv" in stdout
    assert "--root" in stdout


@pytest.mark.xfail(strict=False, reason="Coverage report not implemented yet")
def test_coverage_report_artifacts_layout() -> None:
    reports = ROOT / "data" / "reports"
    assert reports.exists()


@pytest.mark.xfail(strict=False, reason="Idempotence not implemented yet")
def test_rerun_is_noop_exit_code_zero() -> None:
    cmd = [sys.executable, "-m", "src.relml.cli", "import-csv", "--root", "data/raw"]
    out1 = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out2 = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert out1.returncode == 0
    assert out2.returncode == 0
