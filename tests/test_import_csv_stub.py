from __future__ import annotations

import pathlib

from src.relml import etl


def test_import_csv_stub_counts_csv_files(tmp_path: pathlib.Path) -> None:
    csv_dir = tmp_path / "incoming"
    csv_dir.mkdir()
    (csv_dir / "a.csv").write_text("col\nval\n", encoding="utf-8")
    (csv_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    result = etl.import_csv(csv_dir, dry_run=True)

    assert result.discovered_files == 1
    assert result.processed_files == 0
    assert result.skipped_files == 1
    assert "Scanned" in result.message


def test_import_csv_stub_handles_missing_root(tmp_path: pathlib.Path) -> None:
    missing_root = tmp_path / "missing"
    result = etl.import_csv(missing_root, dry_run=True)
    assert result.discovered_files == 0
    assert result.processed_files == 0
    assert result.root == missing_root.resolve()
