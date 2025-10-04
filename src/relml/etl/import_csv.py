from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ImportCsvResult:
    """Summary information returned by the import-csv pipeline."""

    root: Path
    discovered_files: int
    processed_files: int
    skipped_files: int

    @property
    def message(self) -> str:
        return (
            f"Scanned {self.discovered_files} CSV files under {self.root}. "
            f"Processed={self.processed_files} skipped={self.skipped_files}."
        )


def _iter_csv_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.csv"):
        if path.is_file():
            yield path


def import_csv(root: Path | str, dry_run: bool = False) -> ImportCsvResult:
    """Execute the initial CSV ingest slice."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        logger.warning("import_csv.missing_root", root=str(root_path))
        return ImportCsvResult(root=root_path, discovered_files=0, processed_files=0, skipped_files=0)

    csvs = list(_iter_csv_files(root_path))
    discovered = len(csvs)
    processed = 0 if dry_run else discovered
    skipped = discovered - processed

    logger.info(
        "import_csv.summary",
        root=str(root_path),
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
        dry_run=dry_run,
    )
    return ImportCsvResult(
        root=root_path,
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
    )
