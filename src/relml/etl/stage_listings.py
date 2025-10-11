from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)

DATA_ROOT = Path(os.environ.get("RELML_DATA_ROOT", "data"))
STAGE_DIR = DATA_ROOT / "stage"
STAGE_LISTINGS_FILE = STAGE_DIR / "listings.csv"

CANONICAL_COLUMNS = [
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

COLUMN_ALIASES = {
    "listing_key": {"listingkey", "mlsnumber", "mlsid", "mls", "mls#"},
    "domain": {"domain", "dataset", "dataarea"},
    "matrix_modified_dt": {
        "matrixmodifieddt",
        "matrixmodifieddate",
        "matrixmodifiedtimestamp",
        "modifieddt",
        "lastupdated",
    },
    "address": {"address", "streetaddress", "propertyaddress"},
    "city": {"city", "town"},
    "state": {"state", "province", "region"},
    "zip": {"zip", "zipcode", "postalcode", "zip5"},
    "list_price": {"list_price", "listprice", "price", "listpricecurrent"},
    "sqft": {"sqft", "squarefeet", "totallivingsf", "livingsize"},
    "beds": {"beds", "bedrooms", "numberbedrooms"},
    "baths": {"baths", "bathrooms", "numberbathrooms", "fullbaths"},
    "property_type": {"propertytype", "proptype", "type"},
}

ALIAS_LOOKUP: dict[str, str] = {}
for canonical, aliases in COLUMN_ALIASES.items():
    normalized = {canonical}
    normalized |= aliases
    for alias in normalized:
        ALIAS_LOOKUP[alias] = canonical


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


def _parse_timestamp(raw: str) -> datetime:
    candidate = raw.strip()
    if not candidate:
        return datetime.min.replace(tzinfo=timezone.utc)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        logger.warning("stage_listings.invalid_timestamp", value=raw)
        return datetime.min.replace(tzinfo=timezone.utc)


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _domain_from_path(path: Path) -> str | None:
    parts = [part.lower() for part in path.parts]
    for part in parts:
        if "rental" in part or "lease" in part:
            return "RENTAL"
        if "sale" in part or "sales" in part:
            return "SALE"
    return None


@dataclass(slots=True)
class StageListingsResult:
    root: Path
    discovered_files: int
    staged_rows: int
    deduplicated_rows: int
    stage_file: str | None
    dry_run: bool


def _append_columns(existing: list[str], header: Iterable[str]) -> None:
    for column in header:
        if column not in existing:
            existing.append(column)


def stage_listings(root: Path | str, *, dry_run: bool = False) -> StageListingsResult:  # noqa: PLR0912, PLR0915
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        logger.warning("stage_listings.missing_root", root=str(root_path))
        return StageListingsResult(
            root=root_path,
            discovered_files=0,
            staged_rows=0,
            deduplicated_rows=0,
            stage_file=None,
            dry_run=dry_run,
        )

    csv_files = list(_iter_csv_files(root_path))
    discovered = len(csv_files)
    if not csv_files:
        return StageListingsResult(
            root=root_path,
            discovered_files=0,
            staged_rows=0,
            deduplicated_rows=0,
            stage_file=None,
            dry_run=dry_run,
        )

    staged_records: dict[tuple[str, str], dict[str, str]] = {}
    record_meta: dict[tuple[str, str], tuple[str, str, datetime]] = {}
    all_columns: list[str] = list(CANONICAL_COLUMNS)
    deduplicated = 0

    for path in csv_files:
        file_hash = _hash_file(path)
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            normalized_headers = {_normalize(name) for name in fieldnames}

            missing_required = []
            for canonical in ("listing_key", "matrix_modified_dt"):
                aliases = COLUMN_ALIASES.get(canonical, {canonical})
                if not any(alias in normalized_headers for alias in aliases):
                    missing_required.append(canonical)
            if missing_required:
                logger.warning(
                    "stage_listings.missing_columns",
                    file=str(path),
                    columns=missing_required,
                )

            for row in reader:
                sanitized_row = {key: (value or "") for key, value in row.items()}
                alias_map = {_normalize(key): key for key in sanitized_row}
                canonical_row: dict[str, str] = {column: "" for column in CANONICAL_COLUMNS}
                extras: dict[str, str] = {}

                for normalized, original in alias_map.items():
                    canonical_key: str | None = ALIAS_LOOKUP.get(normalized)
                    value = sanitized_row.get(original, "").strip()
                    if canonical_key is None:
                        if original not in extras:
                            extras[original] = value
                    else:
                        canonical_row[canonical_key] = value

                listing_key = canonical_row["listing_key"].strip()
                domain = canonical_row["domain"].strip().upper()
                if not domain:
                    derived = _domain_from_path(path)
                    if derived is not None:
                        domain = derived
                        canonical_row["domain"] = derived

                if not listing_key or not domain:
                    logger.warning(
                        "stage_listings.missing_identity",
                        file=str(path),
                        listing_key=listing_key,
                        domain=domain,
                    )
                    deduplicated += 1
                    continue

                canonical_row["listing_key"] = listing_key
                canonical_row["domain"] = domain
                resolved_row = dict(canonical_row)
                resolved_row.update(extras)
                _append_columns(all_columns, resolved_row.keys())

                ts = _parse_timestamp(canonical_row.get("matrix_modified_dt", ""))
                key = (listing_key, domain)
                existing = record_meta.get(key)
                if existing:
                    deduplicated += 1
                    if ts > existing[2]:
                        staged_records[key] = resolved_row
                        record_meta[key] = (str(path), file_hash, ts)
                else:
                    staged_records[key] = resolved_row
                    record_meta[key] = (str(path), file_hash, ts)

    staged_count = len(staged_records)
    stage_file = None

    if not dry_run and staged_count:
        STAGE_DIR.mkdir(parents=True, exist_ok=True)
        staged_at = datetime.now(timezone.utc).isoformat()
        fieldnames = [*all_columns, "_source_file", "_source_hash", "_staged_at"]
        with STAGE_LISTINGS_FILE.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for key in sorted(staged_records):
                base_row = staged_records[key]
                payload = {column: base_row.get(column, "") for column in all_columns}
                source_file, source_hash, _ = record_meta[key]
                payload["_source_file"] = source_file
                payload["_source_hash"] = source_hash
                payload["_staged_at"] = staged_at
                writer.writerow(payload)
        stage_file = STAGE_LISTINGS_FILE.as_posix()

    logger.info(
        "stage_listings.summary",
        root=str(root_path),
        discovered_files=discovered,
        staged_rows=staged_count,
        deduplicated_rows=deduplicated,
        dry_run=dry_run,
    )

    return StageListingsResult(
        root=root_path,
        discovered_files=discovered,
        staged_rows=staged_count if not dry_run else 0,
        deduplicated_rows=deduplicated if not dry_run else 0,
        stage_file=stage_file,
        dry_run=dry_run,
    )
