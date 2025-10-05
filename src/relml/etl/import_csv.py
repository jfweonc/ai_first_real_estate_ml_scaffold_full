from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import psycopg
import structlog

logger = structlog.get_logger(__name__)

LEDGER_LOG_EVENT = "import_csv.ledger"
LEDGER_SKIP_EVENT = "import_csv.ledger_skip"
LEDGER_SUMMARY_EVENT = "import_csv.ledger_summary"
_import_version = "0.1.0"


@dataclass(slots=True)
class ImportCsvResult:
    """Summary information returned by the import-csv pipeline."""

    root: Path
    files: list[str]
    discovered_files: int
    processed_files: int
    skipped_files: int
    ledgers: list[dict[str, Any]]
    dry_run: bool

    @property
    def message(self) -> str:
        return (
            f"Scanned {self.discovered_files} CSV files under {self.root}. "
            f"Processed={self.processed_files} skipped={self.skipped_files}."
        )

    def to_event(self) -> dict[str, Any]:
        return {
            "event": "dry_run_summary" if self.dry_run else "ingest_summary",
            "module": "import_csv",
            "version": _import_version,
            "summary": {
                "files_discovered": self.discovered_files,
                "files": self.files,
                "ledgers": self.ledgers,
            },
        }


def _iter_csv_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.csv")):
        if path.is_file():
            yield path


def _hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)  # skip header
        return sum(1 for _ in reader)


def _connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; cannot write ETL ledger.")
    return psycopg.connect(url)


def _existing_ledger(cur: psycopg.Cursor, file_hash: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT file_hash, raw_source, discovered_at, ingested_at, status,
               rows_total, rows_clean, rows_quarantined, errors
        FROM etl_ledger
        WHERE file_hash = %s
        """,
        (file_hash,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "file_hash": row[0],
        "raw_source": row[1],
        "discovered_at": row[2].isoformat() if row[2] else None,
        "ingested_at": row[3].isoformat() if row[3] else None,
        "status": row[4],
        "rows_total": row[5],
        "rows_clean": row[6],
        "rows_quarantined": row[7],
        "errors": row[8] if row[8] is not None else [],
    }


def _insert_ledger(cur: psycopg.Cursor, *, file_hash: str, source: str, rows_total: int) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO etl_ledger (
            file_hash,
            raw_source,
            status,
            rows_total,
            rows_clean,
            rows_quarantined,
            errors,
            ingested_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, timezone('utc', now()))
        RETURNING discovered_at, ingested_at
        """,
        (file_hash, source, "ingested", rows_total, rows_total, 0, []),
    )
    discovered_at, ingested_at = cur.fetchone()
    return {
        "file_hash": file_hash,
        "raw_source": source,
        "discovered_at": discovered_at.isoformat() if discovered_at else None,
        "ingested_at": ingested_at.isoformat() if ingested_at else None,
        "status": "ingested",
        "rows_total": rows_total,
        "rows_clean": rows_total,
        "rows_quarantined": 0,
        "errors": [],
    }


def import_csv(root: Path | str, dry_run: bool = False) -> ImportCsvResult:
    """Execute the initial CSV ingest slice."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        logger.warning("import_csv.missing_root", root=str(root_path))
        return ImportCsvResult(
            root=root_path,
            files=[],
            discovered_files=0,
            processed_files=0,
            skipped_files=0,
            ledgers=[],
            dry_run=dry_run,
        )

    csv_paths = list(_iter_csv_files(root_path))
    discovered = len(csv_paths)
    ledgers: list[dict[str, Any]] = []
    processed = 0
    skipped = 0

    if dry_run or not csv_paths:
        logger.info(
            LEDGER_SUMMARY_EVENT,
            discovered_files=discovered,
            processed_files=processed,
            skipped_files=discovered if dry_run else 0,
            dry_run=dry_run,
        )
        return ImportCsvResult(
            root=root_path,
            files=[str(path) for path in csv_paths],
            discovered_files=discovered,
            processed_files=processed,
            skipped_files=discovered if dry_run else 0,
            ledgers=[],
            dry_run=dry_run,
        )

    with _connect() as conn:
        with conn.cursor() as cur:
            for path in csv_paths:
                file_hash = _hash_file(path)
                existing = _existing_ledger(cur, file_hash)
                if existing:
                    skipped += 1
                    ledgers.append(existing)
                    logger.info(
                        LEDGER_SKIP_EVENT,
                        file=str(path),
                        file_hash=file_hash,
                        status=existing["status"],
                    )
                    continue

                rows_total = _count_rows(path)
                ledger_entry = _insert_ledger(
                    cur,
                    file_hash=file_hash,
                    source=str(path),
                    rows_total=rows_total,
                )
                ledgers.append(ledger_entry)
                processed += 1
                logger.info(
                    LEDGER_LOG_EVENT,
                    file=str(path),
                    file_hash=file_hash,
                    rows_total=rows_total,
                )
        conn.commit()

    logger.info(
        LEDGER_SUMMARY_EVENT,
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
        dry_run=dry_run,
    )

    return ImportCsvResult(
        root=root_path,
        files=[str(path) for path in csv_paths],
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
        ledgers=ledgers,
        dry_run=dry_run,
    )
