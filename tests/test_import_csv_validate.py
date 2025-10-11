from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

import psycopg
import pytest

from src.relml.etl.import_csv import REQUIRED_COLUMNS, import_csv

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "p1"


def _fetch_ledger_rows(url: str) -> list[tuple[str, str, str, int, int, int]]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT file_hash, raw_source, status, rows_total, rows_clean, rows_quarantined FROM etl_ledger")
        return list(cur.fetchall())


def _write_rows(path: Path, rows: list[dict[str, str]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.mark.integration
def test_import_csv_quarantines_invalid_rows(
    monkeypatch: pytest.MonkeyPatch, postgres_url: str, tmp_path: Path
) -> None:
    data_root = tmp_path / "data_root"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    import_root = tmp_path / "ingest"
    import_root.mkdir(parents=True, exist_ok=True)
    csv_path = import_root / "raw_listings_sample.csv"

    with (FIXTURE_ROOT / "raw_listings_sample.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or list(REQUIRED_COLUMNS)
        rows = list(reader)

    rows[0]["matrix_modified_dt"] = "invalid"
    rows[1]["domain"] = ""
    _write_rows(csv_path, rows, fieldnames)

    result = import_csv(import_root, dry_run=False)

    assert result.processed_files == 1  # noqa: PLR2004
    assert result.parsed_row_count == 2  # noqa: PLR2004
    assert result.rows_quarantined_total == 2  # noqa: PLR2004
    assert result.quarantine_file is not None

    with Path(result.quarantine_file).open(encoding="utf-8") as handle:
        quarantine_rows = list(csv.DictReader(handle))
    assert len(quarantine_rows) == 2  # noqa: PLR2004
    reasons = {row["_reason"] for row in quarantine_rows}
    assert "Missing value for domain" in reasons
    assert "matrix_modified_dt is not a valid ISO timestamp" in reasons

    ledger_rows = _fetch_ledger_rows(postgres_url)
    assert len(ledger_rows) == 1  # noqa: PLR2004
    (_, raw_source, status, rows_total, rows_clean, rows_quarantined) = ledger_rows[0]
    assert status == "ingested"
    assert rows_total == 2  # noqa: PLR2004
    assert rows_clean == 0  # noqa: PLR2004
    assert rows_quarantined == 2  # noqa: PLR2004
    assert raw_source.endswith("raw_listings_sample.csv")


@pytest.mark.integration
def test_import_csv_rejects_bad_header(monkeypatch: pytest.MonkeyPatch, postgres_url: str, tmp_path: Path) -> None:
    data_root = tmp_path / "data_root"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    import_root = tmp_path / "ingest"
    import_root.mkdir(parents=True, exist_ok=True)
    bad_csv = import_root / "broken.csv"
    _write_rows(
        bad_csv,
        [
            {"listing_key": "HAR999", "matrix_modified_dt": "2024-01-01T00:00:00Z"},
        ],
        ["listing_key", "matrix_modified_dt"],
    )

    result = import_csv(import_root, dry_run=False)

    assert result.processed_files == 0  # noqa: PLR2004
    assert result.skipped_files == 1  # noqa: PLR2004
    assert result.rows_quarantined_total == 0  # noqa: PLR2004
    assert result.ledgers and result.ledgers[0]["status"] == "failed"

    ledger_rows = _fetch_ledger_rows(postgres_url)
    assert ledger_rows == []


@pytest.mark.integration
def test_import_csv_writes_quarantine_csv_with_expected_columns(
    monkeypatch: pytest.MonkeyPatch, postgres_url: str, tmp_path: Path
) -> None:
    data_root = tmp_path / "data_root"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    import_root = tmp_path / "ingest"
    import_root.mkdir(parents=True, exist_ok=True)
    csv_path = import_root / "raw_listings_sample.csv"

    with (FIXTURE_ROOT / "raw_listings_sample.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or list(REQUIRED_COLUMNS)
        rows = list(reader)

    broken_rows = [
        {**rows[0], "matrix_modified_dt": "invalid"},
        {**rows[1], "domain": ""},
        {**rows[0], "matrix_modified_dt": "invalid"},
    ]
    _write_rows(csv_path, broken_rows, fieldnames)

    result = import_csv(import_root, dry_run=False)

    assert result.quarantine_file is not None
    quarantine_path = Path(result.quarantine_file)
    assert quarantine_path.exists()

    with quarantine_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [*REQUIRED_COLUMNS, "_source_file", "_reason"]
        quarantine_rows = list(reader)

    assert len(quarantine_rows) == 2  # noqa: PLR2004
    reasons = {row["_reason"] for row in quarantine_rows}
    assert "matrix_modified_dt is not a valid ISO timestamp" in reasons
    assert "Missing value for domain" in reasons
