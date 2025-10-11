from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import psycopg
import structlog
from psycopg.types.json import Json

logger = structlog.get_logger(__name__)

LEDGER_LOG_EVENT = "import_csv.ledger"
LEDGER_SKIP_EVENT = "import_csv.ledger_skip"
LEDGER_SUMMARY_EVENT = "import_csv.ledger_summary"
LEDGER_DISABLED_EVENT = "import_csv.ledger_disabled"
VALIDATION_EVENT = "import_csv.validation"
VALIDATION_FAILED_EVENT = "import_csv.validation_failed"
_import_version = "1.0.0"

REQUIRED_COLUMNS: Sequence[str] = (
    "listing_key",
    "domain",
    "matrix_modified_dt",
    "address",
    "city",
    "state",
    "zip",
    "list_price",
)
DATA_ROOT = Path(os.environ.get("RELML_DATA_ROOT", "data"))
REPORTS_DIR = DATA_ROOT / "reports"
QUARANTINE_FILE = REPORTS_DIR / "quarantine_rows.csv"
CLEAN_EXPORT_FILE = REPORTS_DIR / "clean_listings.csv"
COVERAGE_FILE = REPORTS_DIR / "coverage_summary.md"
SELECTED_LISTINGS_FILE = REPORTS_DIR / "selected_listings.csv"


@dataclass(slots=True)
class ImportCsvResult:
    """Summary information returned by the import-csv pipeline."""

    root: Path
    files: list[str]
    discovered_files: int
    processed_files: int
    skipped_files: int
    parsed_row_count: int
    rows_clean_total: int
    rows_quarantined_total: int
    quarantine_file: str | None
    clean_rows_file: str | None
    coverage_report_file: str | None
    selected_listings_file: str | None
    coverage_metrics: dict[str, Any]
    images_summary: dict[str, Any] | None
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
                "parsed_row_count": self.parsed_row_count,
                "rows_clean_total": self.rows_clean_total,
                "rows_quarantined_total": self.rows_quarantined_total,
                "quarantine_file": self.quarantine_file,
                "clean_rows_file": self.clean_rows_file,
                "coverage_report_file": self.coverage_report_file,
                "selected_listings_file": self.selected_listings_file,
                "coverage_metrics": self.coverage_metrics,
                "images_summary": self.images_summary,
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


def _connect() -> psycopg.Connection | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.warning(
            LEDGER_DISABLED_EVENT,
            reason="missing_database_url",
        )
        return None
    return psycopg.connect(url)


def _existing_ledger(cur: psycopg.Cursor[Any], file_hash: str) -> dict[str, Any] | None:
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


def _insert_ledger(  # noqa: PLR0913
    cur: psycopg.Cursor[Any],
    *,
    file_hash: str,
    source: str,
    status: str,
    rows_total: int,
    rows_clean: int,
    rows_quarantined: int,
    errors: list[str],
) -> dict[str, Any]:
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
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, timezone('utc', now()))
        RETURNING discovered_at, ingested_at
        """,
        (file_hash, source, status, rows_total, rows_clean, rows_quarantined, Json(errors)),
    )
    discovered_at, ingested_at = cur.fetchone()
    return {
        "file_hash": file_hash,
        "raw_source": source,
        "discovered_at": discovered_at.isoformat() if discovered_at else None,
        "ingested_at": ingested_at.isoformat() if ingested_at else None,
        "status": status,
        "rows_total": rows_total,
        "rows_clean": rows_clean,
        "rows_quarantined": rows_quarantined,
        "errors": errors,
    }


def _parse_timestamp(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


def _validate_row(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    for column in REQUIRED_COLUMNS:
        if not row.get(column):
            reasons.append(f"Missing value for {column}")
    timestamp = row.get("matrix_modified_dt", "")
    if timestamp and not _parse_timestamp(timestamp):
        reasons.append("matrix_modified_dt is not a valid ISO timestamp")
    return reasons


def _dedupe_quarantine(
    records: list[tuple[Path, dict[str, str], list[str]]],
) -> list[tuple[Path, dict[str, str], list[str]]]:
    seen: set[tuple[str, ...]] = set()
    unique: list[tuple[Path, dict[str, str], list[str]]] = []
    for source, row, reasons in records:
        key = (
            source.as_posix(),
            *(row.get(column, "").strip() for column in REQUIRED_COLUMNS),
            "|".join(sorted(reasons)),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append((source, row, reasons))
    return unique


def _write_quarantine_report(records: list[tuple[Path, dict[str, str], list[str]]]) -> str | None:
    if not records:
        if QUARANTINE_FILE.exists():
            QUARANTINE_FILE.unlink()
        return None
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    unique_records = _dedupe_quarantine(records)
    with QUARANTINE_FILE.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [*REQUIRED_COLUMNS, "_source_file", "_reason"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for source, row, reasons in unique_records:
            payload = {column: row.get(column, "") for column in REQUIRED_COLUMNS}
            payload["_source_file"] = source.as_posix()
            payload["_reason"] = "; ".join(sorted(reasons))
            writer.writerow(payload)
    return QUARANTINE_FILE.as_posix()


def _write_clean_export(columns: list[str], rows: list[dict[str, str]]) -> str | None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with CLEAN_EXPORT_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return CLEAN_EXPORT_FILE.as_posix()


def _write_selected_listings(rows: list[dict[str, str]]) -> str | None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["listing_key", "domain", "reason", "source_file"]
    with SELECTED_LISTINGS_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return SELECTED_LISTINGS_FILE.as_posix()


def _write_coverage_report(
    metrics: dict[str, Any],
    domain_stats: dict[str, dict[str, int]],
) -> str | None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Coverage Summary",
        "",
        f"- Rows total: {metrics['rows_total']}",
        f"- Rows clean: {metrics['rows_clean']}",
        f"- Rows quarantined: {metrics['rows_quarantined']}",
        f"- Coverage %: {metrics['coverage_pct']:.2f}",
        f"- Gap candidates: {metrics['gap_candidates']}",
        "",
        "## Domain Coverage",
        "| Domain | Total | Clean | Quarantined | Coverage % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for domain, stats in sorted(domain_stats.items()):
        total = stats["total"]
        clean = stats["clean"]
        quarantined = stats["quarantined"]
        coverage = (clean / total * 100.0) if total else 0.0
        lines.append(f"| {domain or 'unknown'} | {total} | {clean} | {quarantined} | {coverage:.2f} |")
    lines.append("")
    COVERAGE_FILE.write_text("\n".join(lines), encoding="utf-8")
    return COVERAGE_FILE.as_posix()


def _summarize_images_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    listings: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            record = json.loads(line)
            key = (record.get("listing_key", ""), record.get("domain", ""))
            listings.setdefault(key, []).append(record)
    summary: list[dict[str, Any]] = []
    status_counts = {"none": 0, "partial": 0, "complete": 0}
    for (listing_key, domain), records in sorted(listings.items()):
        count = len(records)
        if count <= 0:
            status = "none"
        elif count == 1:
            status = "partial"
        else:
            status = "complete"
        status_counts[status] += 1
        summary.append(
            {
                "listing_key": listing_key,
                "domain": domain,
                "images_count": count,
                "images_download_status": status,
                "filenames": [record.get("filename", "") for record in records],
                "sha1_digests": [record.get("sha1", "") for record in records],
            }
        )
    return {
        "manifest_path": path.as_posix(),
        "total_records": sum(len(records) for records in listings.values()),
        "download_status_counts": status_counts,
        "listings": summary,
    }


def import_csv(  # noqa: PLR0912, PLR0915
    root: Path | str,
    *,
    dry_run: bool = False,
    images_manifest: Path | None = None,
) -> ImportCsvResult:
    """Execute the Phase 1 ingest slice."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        logger.warning("import_csv.missing_root", root=str(root_path))
        return ImportCsvResult(
            root=root_path,
            files=[],
            discovered_files=0,
            processed_files=0,
            skipped_files=0,
            parsed_row_count=0,
            rows_clean_total=0,
            rows_quarantined_total=0,
            quarantine_file=None,
            clean_rows_file=None,
            coverage_report_file=None,
            selected_listings_file=None,
            coverage_metrics={
                "rows_total": 0,
                "rows_clean": 0,
                "rows_quarantined": 0,
                "coverage_pct": 0.0,
                "gap_candidates": 0,
                "domains": {},
            },
            images_summary=None,
            ledgers=[],
            dry_run=dry_run,
        )

    csv_paths = list(_iter_csv_files(root_path))
    discovered = len(csv_paths)
    if not csv_paths:
        logger.info(
            LEDGER_SUMMARY_EVENT,
            discovered_files=0,
            processed_files=0,
            skipped_files=0,
            parsed_row_count=0,
            rows_clean_total=0,
            rows_quarantined_total=0,
            dry_run=dry_run,
        )
        return ImportCsvResult(
            root=root_path,
            files=[],
            discovered_files=0,
            processed_files=0,
            skipped_files=0,
            parsed_row_count=0,
            rows_clean_total=0,
            rows_quarantined_total=0,
            quarantine_file=None,
            clean_rows_file=None,
            coverage_report_file=None,
            selected_listings_file=None,
            coverage_metrics={
                "rows_total": 0,
                "rows_clean": 0,
                "rows_quarantined": 0,
                "coverage_pct": 0.0,
                "gap_candidates": 0,
                "domains": {},
            },
            images_summary=None,
            ledgers=[],
            dry_run=dry_run,
        )

    ledgers: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    parsed_total = 0
    clean_total = 0
    quarantined_total = 0
    quarantine_records: list[tuple[Path, dict[str, str], list[str]]] = []
    clean_rows: list[dict[str, str]] = []
    all_columns: list[str] = list(REQUIRED_COLUMNS)
    domain_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "clean": 0, "quarantined": 0})
    gap_candidates: list[dict[str, str]] = []

    connection = _connect() if not dry_run else None
    cursor = connection.cursor() if connection else None

    try:
        for path in csv_paths:
            file_hash = _hash_file(path)
            if cursor:
                existing = _existing_ledger(cursor, file_hash)
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

            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                header = reader.fieldnames or []
                missing = [column for column in REQUIRED_COLUMNS if column not in header]
                if missing:
                    skipped += 1
                    failure = {
                        "file_hash": file_hash,
                        "raw_source": str(path),
                        "status": "failed",
                        "rows_total": 0,
                        "rows_clean": 0,
                        "rows_quarantined": 0,
                        "errors": [f"Missing columns: {', '.join(missing)}"],
                    }
                    ledgers.append(failure)
                    logger.error(
                        VALIDATION_FAILED_EVENT,
                        file=str(path),
                        missing_columns=missing,
                    )
                    continue

                for column in header:
                    if column not in all_columns:
                        all_columns.append(column)

                parsed_count = 0
                valid_rows: list[dict[str, str]] = []
                invalid_rows: list[tuple[dict[str, str], list[str]]] = []

                for row in reader:
                    parsed_count += 1
                    reasons = _validate_row(row)
                    domain = row.get("domain", "").strip()
                    stats = domain_stats[domain]
                    stats["total"] += 1
                    if reasons:
                        stats["quarantined"] += 1
                        invalid_rows.append((row, reasons))
                        gap_candidates.append(
                            {
                                "listing_key": row.get("listing_key", ""),
                                "domain": domain,
                                "reason": "; ".join(sorted(reasons)) or "validation_failed",
                                "source_file": str(path),
                            }
                        )
                        continue
                    stats["clean"] += 1
                    valid_rows.append(row)

            errors = [reason for _, reasons in invalid_rows for reason in reasons]

            parsed_total += parsed_count
            clean_total += len(valid_rows)
            quarantined_total += len(invalid_rows)
            clean_rows.extend(valid_rows)
            for row, reasons in invalid_rows:
                quarantine_records.append((path, row, reasons))

            logger.info(
                VALIDATION_EVENT,
                file=str(path),
                parsed_rows=parsed_count,
                valid_rows=len(valid_rows),
                quarantined=len(invalid_rows),
            )

            if cursor:
                ledger_entry = _insert_ledger(
                    cursor,
                    file_hash=file_hash,
                    source=str(path),
                    status="ingested",
                    rows_total=parsed_count,
                    rows_clean=len(valid_rows),
                    rows_quarantined=len(invalid_rows),
                    errors=errors,
                )
                ledgers.append(ledger_entry)
            else:
                ledgers.append(
                    {
                        "file_hash": file_hash,
                        "raw_source": str(path),
                        "status": "dry_run" if dry_run else "ledger_disabled",
                        "rows_total": parsed_count,
                        "rows_clean": len(valid_rows),
                        "rows_quarantined": len(invalid_rows),
                        "errors": errors,
                    }
                )

            processed += 1

        if connection:
            connection.commit()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    coverage_pct = (clean_total / parsed_total * 100.0) if parsed_total else 0.0
    coverage_metrics = {
        "rows_total": parsed_total,
        "rows_clean": clean_total,
        "rows_quarantined": quarantined_total,
        "coverage_pct": coverage_pct,
        "gap_candidates": len(gap_candidates),
        "domains": domain_stats,
    }

    quarantine_file = None
    clean_export_file = None
    coverage_report_file = None
    selected_listings_file = None

    if not dry_run:
        quarantine_file = _write_quarantine_report(quarantine_records)
        clean_export_file = _write_clean_export(all_columns, clean_rows)
        selected_listings_file = _write_selected_listings(gap_candidates)
        coverage_report_file = _write_coverage_report(coverage_metrics, domain_stats)

    images_summary = None
    if images_manifest is not None:
        try:
            images_summary = _summarize_images_manifest(images_manifest)
        except FileNotFoundError:
            logger.warning(
                "import_csv.images_manifest_missing",
                images_manifest=str(images_manifest),
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "import_csv.images_manifest_error",
                images_manifest=str(images_manifest),
                error=str(exc),
            )

    logger.info(
        LEDGER_SUMMARY_EVENT,
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
        parsed_row_count=parsed_total,
        rows_clean_total=clean_total,
        rows_quarantined_total=quarantined_total,
        dry_run=dry_run,
    )

    return ImportCsvResult(
        root=root_path,
        files=[str(path) for path in csv_paths],
        discovered_files=discovered,
        processed_files=processed,
        skipped_files=skipped,
        parsed_row_count=parsed_total,
        rows_clean_total=clean_total,
        rows_quarantined_total=quarantined_total,
        quarantine_file=quarantine_file,
        clean_rows_file=clean_export_file,
        coverage_report_file=coverage_report_file,
        selected_listings_file=selected_listings_file,
        coverage_metrics=coverage_metrics,
        images_summary=images_summary,
        ledgers=ledgers,
        dry_run=dry_run,
    )
