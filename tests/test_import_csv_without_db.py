from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.relml.etl.import_csv import import_csv

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "p1"


def _prepare_sample_csv(destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    source = FIXTURE_ROOT / "raw_listings_sample.csv"
    target = destination_dir / "raw_listings_sample.csv"
    shutil.copyfile(source, target)
    return target


def test_import_csv_records_ledger_disabled_when_database_url_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    data_root = tmp_path / "data_root"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))
    _prepare_sample_csv(ingest_root)

    result = import_csv(ingest_root, dry_run=False)

    assert result.processed_files == 1
    assert result.quarantine_file is None
    assert result.ledgers
    statuses = {entry["status"] for entry in result.ledgers}
    assert statuses == {"ledger_disabled"}
