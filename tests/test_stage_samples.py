from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.relml.etl.stage_images import stage_images
from src.relml.etl.stage_listings import stage_listings
from src.relml.etl.stage_samples import StageSamplesResult, build_stage_samples


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.mark.integration
def test_build_stage_samples_creates_sample_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    rows = [
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
        {
            "listing_key": "HAR125",
            "domain": "TEST",
            "matrix_modified_dt": "2024-12-03T09:45:00Z",
            "address": "555 Sample Rd",
            "city": "Austin",
            "state": "TX",
            "zip": "73301",
            "list_price": "405000",
            "sqft": "1750",
            "beds": "3",
            "baths": "2.5",
            "property_type": "Single-Family",
        },
    ]
    _write_csv(ingest_root / "listings.csv", fieldnames, rows)

    manifest_rows = [
        {
            "listing_key": "HAR123",
            "domain": "TEST",
            "filename": "HAR123_1.jpg",
            "sha1": "a" * 40,
        },
        {
            "listing_key": "HAR123",
            "domain": "TEST",
            "filename": "HAR123_2.jpg",
            "sha1": "b" * 40,
        },
        {
            "listing_key": "HAR124",
            "domain": "TEST",
            "filename": "HAR124_1.jpg",
            "sha1": "c" * 40,
        },
    ]
    _write_manifest(ingest_root / "images.jsonl", manifest_rows)

    stage_listings(ingest_root, dry_run=False)
    stage_images(ingest_root, dry_run=False)

    result = build_stage_samples(sample_size=2, dry_run=False)

    assert isinstance(result, StageSamplesResult)
    assert result.listings_total == 3  # noqa: PLR2004
    assert result.images_total == 3  # noqa: PLR2004
    assert result.listings_sample_count == 2  # noqa: PLR2004
    assert result.images_sample_count == 2  # noqa: PLR2004
    assert result.listings_sample_file is not None
    assert result.images_sample_file is not None

    listings_sample = Path(result.listings_sample_file)
    assert listings_sample.exists()
    with listings_sample.open(encoding="utf-8") as handle:
        data = list(csv.DictReader(handle))
    assert len(data) == 2  # noqa: PLR2004
    assert data[0]["listing_key"] == "HAR123"
    assert data[0]["_source_file"].endswith("listings.csv")

    images_sample = Path(result.images_sample_file)
    sample_payload = json.loads(images_sample.read_text(encoding="utf-8"))
    assert sample_payload["images_total"] == 3  # noqa: PLR2004
    assert len(sample_payload["listings"]) == 2  # noqa: PLR2004
    statuses = {entry["status"] for entry in sample_payload["listings"]}
    assert statuses == {"complete", "partial"}


def test_build_stage_samples_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))

    _write_csv(
        ingest_root / "listings.csv",
        ["listing_key", "domain"],
        [
            {"listing_key": "HAR200", "domain": "TEST"},
        ],
    )
    _write_manifest(
        ingest_root / "images.jsonl",
        [
            {"listing_key": "HAR200", "domain": "TEST", "filename": "HAR200_1.jpg", "sha1": "d" * 40},
        ],
    )

    stage_listings(ingest_root, dry_run=False)
    stage_images(ingest_root, dry_run=False)

    result = build_stage_samples(sample_size=1, dry_run=True)

    assert result.listings_sample_file is None
    assert result.images_sample_file is None
    samples_dir = data_root / "samples"
    assert not samples_dir.exists()
