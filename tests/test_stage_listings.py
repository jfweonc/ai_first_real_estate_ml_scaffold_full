from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from src.relml.etl.stage_listings import StageListingsResult, stage_listings


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@pytest.mark.integration
def test_stage_listings_dedupes_and_writes_stage_csv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    fieldnames = [
        "listing_key",
        "domain",
        "matrix_modified_dt",
        "address",
        "city",
        "state",
        "zip",
        "list_price",
        "sqft",
        "beds",
        "baths",
        "property_type",
    ]
    duplicate_rows = [
        {
            "listing_key": "HAR123",
            "domain": "TEST",
            "matrix_modified_dt": "2024-12-01T12:00:00Z",
            "address": "6015 Nowlands Run Ln",
            "city": "Sugar Land",
            "state": "TX",
            "zip": "77479",
            "list_price": "485000",
            "sqft": "2850",
            "beds": "4",
            "baths": "3",
            "property_type": "Single-Family",
        },
        {
            "listing_key": "HAR123",
            "domain": "TEST",
            "matrix_modified_dt": "2024-12-03T08:15:00Z",
            "address": "6015 Nowlands Run Ln",
            "city": "Sugar Land",
            "state": "TX",
            "zip": "77479",
            "list_price": "490000",
            "sqft": "2850",
            "beds": "4",
            "baths": "3",
            "property_type": "Single-Family",
        },
        {
            "listing_key": "HAR124",
            "domain": "TEST",
            "matrix_modified_dt": "2024-12-02T13:30:00Z",
            "address": "1234 Sample Ct",
            "city": "Houston",
            "state": "TX",
            "zip": "77002",
            "list_price": "325000",
            "sqft": "1650",
            "beds": "3",
            "baths": "2",
            "property_type": "Townhouse",
        },
    ]
    csv_path = ingest_root / "raw_listings.csv"
    _write_csv(csv_path, fieldnames, duplicate_rows)

    result = stage_listings(ingest_root, dry_run=False)

    assert isinstance(result, StageListingsResult)
    assert result.discovered_files == 1  # noqa: PLR2004
    assert result.staged_rows == 2  # noqa: PLR2004
    assert result.deduplicated_rows == 1  # noqa: PLR2004
    assert result.stage_file is not None

    stage_path = Path(result.stage_file)
    assert stage_path.exists()

    with stage_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            *fieldnames,
            "_source_file",
            "_source_hash",
            "_staged_at",
        ]
        staged_rows = list(reader)

    assert len(staged_rows) == 2  # noqa: PLR2004

    # Most recent HAR123 row should be retained with updated price.
    har123 = next(row for row in staged_rows if row["listing_key"] == "HAR123")
    assert har123["list_price"] == "490000"
    assert har123["_source_file"].endswith("raw_listings.csv")
    assert len(har123["_source_hash"]) == 64  # noqa: PLR2004
    datetime.fromisoformat(har123["_staged_at"])  # raises on invalid format


def test_stage_listings_dry_run_skips_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    fieldnames = [
        "listing_key",
        "domain",
        "matrix_modified_dt",
        "address",
        "city",
        "state",
        "zip",
        "list_price",
        "sqft",
        "beds",
        "baths",
        "property_type",
    ]
    csv_path = ingest_root / "raw_listings.csv"
    _write_csv(
        csv_path,
        fieldnames,
        [
            {
                "listing_key": "HAR200",
                "domain": "TEST",
                "matrix_modified_dt": "2024-10-01T12:00:00Z",
                "address": "1 Dry Run Ln",
                "city": "Austin",
                "state": "TX",
                "zip": "78701",
                "list_price": "250000",
                "sqft": "1400",
                "beds": "3",
                "baths": "2",
                "property_type": "Condo",
            }
        ],
    )

    result = stage_listings(ingest_root, dry_run=True)

    assert result.stage_file is None
    assert result.staged_rows == 0  # noqa: PLR2004
    assert result.deduplicated_rows == 0  # noqa: PLR2004
    stage_dir = data_root / "stage"
    assert not stage_dir.exists()


def test_stage_listings_skips_rows_missing_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    fieldnames = [
        "listing_key",
        "domain",
        "matrix_modified_dt",
        "address",
    ]
    rows = [
        {
            "listing_key": "HAR500",
            "domain": "TEST",
            "matrix_modified_dt": "2024-10-10T10:00:00Z",
            "address": "500 Valid Ln",
        },
        {
            "listing_key": "",
            "domain": "TEST",
            "matrix_modified_dt": "2024-10-10T11:00:00Z",
            "address": "Unknown",
        },
    ]
    _write_csv(ingest_root / "mixed.csv", fieldnames, rows)

    result = stage_listings(ingest_root, dry_run=False)

    assert result.staged_rows == 1  # noqa: PLR2004
    assert result.deduplicated_rows == 1  # noqa: PLR2004
    stage_path = Path(result.stage_file or "")
    with stage_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        staged_rows = list(reader)
    assert len(staged_rows) == 1  # noqa: PLR2004
    assert staged_rows[0]["listing_key"] == "HAR500"


def test_stage_listings_handles_invalid_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    fieldnames = [
        "listing_key",
        "domain",
        "matrix_modified_dt",
    ]
    rows = [
        {
            "listing_key": "HAR600",
            "domain": "TEST",
            "matrix_modified_dt": "not-a-timestamp",
        }
    ]
    _write_csv(ingest_root / "invalid_ts.csv", fieldnames, rows)

    result = stage_listings(ingest_root, dry_run=False)

    assert result.staged_rows == 1  # noqa: PLR2004
    stage_path = Path(result.stage_file or "")
    with stage_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        staged_rows = list(reader)
    assert staged_rows[0]["matrix_modified_dt"] == "not-a-timestamp"
