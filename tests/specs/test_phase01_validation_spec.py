from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.relml.cli import app as cli_app

RUNNER = CliRunner()
FIXTURE_ROOT = Path("fixtures/p1")


def _invoke(args: list[str], *, data_root: Path) -> tuple[int, str]:
    env = {"RELML_DATA_ROOT": str(data_root)}
    result = RUNNER.invoke(cli_app, args, env=env)
    return result.exit_code, result.stdout


@pytest.mark.integration
class TestPhase01Validation:
    def test_header_validation_failure_sets_fail_status(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        ingest_root = tmp_path / "ingest"
        ingest_root.mkdir(parents=True, exist_ok=True)
        bad_csv = ingest_root / "bad_header.csv"
        with bad_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["listing_key", "matrix_modified_dt"])
            writer.writerow(["HAR999", "2024-01-01T00:00:00Z"])

        code, stdout = _invoke(
            [
                "import-csv",
                "--root",
                str(ingest_root),
            ],
            data_root=data_root,
        )
        assert code == 0

        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        summary = next((e["result"] for e in events if e.get("event") == "cli.import_csv.complete"), None)
        assert summary is not None
        payload = summary["summary"]
        assert payload["files_discovered"] == 1  # noqa: PLR2004
        assert payload["rows_quarantined_total"] == 0  # noqa: PLR2004
        assert payload["quarantine_file"] is None

    def test_row_quarantine_summary_logged(self, tmp_path: Path) -> None:
        data_root = tmp_path / "data"
        ingest_root = tmp_path / "ingest"
        ingest_root.mkdir(parents=True, exist_ok=True)
        csv_path = ingest_root / "raw_listings_sample.csv"

        with (FIXTURE_ROOT / "raw_listings_sample.csv").open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        rows[0]["matrix_modified_dt"] = "invalid"
        rows[1]["domain"] = ""

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        code, stdout = _invoke(
            [
                "import-csv",
                "--root",
                str(ingest_root),
            ],
            data_root=data_root,
        )
        assert code == 0

        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        summary = next((e["result"] for e in events if e.get("event") == "cli.import_csv.complete"), None)
        assert summary is not None
        payload = summary["summary"]
        details = payload["coverage_metrics"]
        assert payload["rows_quarantined_total"] == 2  # noqa: PLR2004
        assert details["rows_total"] == 2  # noqa: PLR2004
        assert details["gap_candidates"] == 2  # noqa: PLR2004
        quarantine = Path(payload["quarantine_file"])
        with quarantine.open(encoding="utf-8") as handle:
            lines = list(csv.DictReader(handle))
        assert len(lines) == 2  # noqa: PLR2004
        reasons = {line["_reason"] for line in lines}
        assert "Missing value for domain" in reasons
        assert "matrix_modified_dt is not a valid ISO timestamp" in reasons
