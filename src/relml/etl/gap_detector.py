from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import structlog

logger = structlog.get_logger(__name__)


def _parse_iso(value: str) -> datetime:
    candidate = value.strip()
    if not candidate:
        raise ValueError("empty timestamp")
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _date_range(start: date, end: date) -> Iterable[date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


@dataclass(slots=True)
class Thresholds:
    listings_per_day: int | None = None
    images_ratio: float | None = None


@dataclass(slots=True)
class ZipGap:
    listings: set[str]
    dates: dict[str, list[str]]

    def to_payload(self) -> dict[str, Any]:
        return {
            "listings": sorted(self.listings),
            "dates": self.dates,
        }


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def parse_config_thresholds(raw: Mapping[str, object]) -> Thresholds:
    listings = _as_int(raw.get("listings_per_day"))
    images = _as_float(raw.get("images_ratio"))
    return Thresholds(listings_per_day=listings, images_ratio=images)


@dataclass
class GapDetector:
    listings_csv: Path
    images_csv: Path | None = None

    def listings_by_date(self) -> dict[date, list[dict[str, str]]]:
        bucket: dict[date, list[dict[str, str]]] = {}
        with self.listings_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if "\ufefflisting_key" in row:
                    row["listing_key"] = row.pop("\ufefflisting_key")
                try:
                    dt = _parse_iso(row.get("matrix_modified_dt", ""))
                except ValueError:
                    logger.warning("gap_detector.invalid_timestamp", row=row)
                    continue
                bucket.setdefault(dt.date(), []).append(row)
        return bucket

    def images_by_listing(self) -> dict[tuple[str, str], dict[str, str]]:
        if not self.images_csv or not self.images_csv.exists():
            return {}
        result: dict[tuple[str, str], dict[str, str]] = {}
        with self.images_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if "\ufefflisting_key" in row:
                    row["listing_key"] = row.pop("\ufefflisting_key")
                listing = (row.get("listing_key", "").strip(), row.get("domain", "").strip().upper())
                if not listing[0] or not listing[1]:
                    continue
                row["domain"] = listing[1]
                row["status"] = (row.get("status") or "").lower()
                result[listing] = row
        return result


def detect_gaps(
    detector: GapDetector,
    start: date,
    end: date,
    *,
    expected_min: Thresholds | None,
    images_required: bool,
) -> list[dict[str, object]]:
    listings = detector.listings_by_date()
    image_lookup = detector.images_by_listing() if images_required else {}
    rows: list[dict[str, object]] = []

    for day in _date_range(start, end):
        entries = listings.get(day, [])
        listings_count = len(entries)
        images_count = 0
        if images_required and entries:
            for row in entries:
                key = (row.get("listing_key", "").strip(), row.get("domain", "").strip().upper())
                record = image_lookup.get(key)
                if record and record.get("status", "").lower() in {"complete", "partial"}:
                    images_count += 1

        status = "MISSING"
        if listings_count > 0:
            status = "COMPLETE"
            if expected_min and expected_min.listings_per_day and listings_count < expected_min.listings_per_day:
                status = "PARTIAL"
            if images_required:
                ratio = (images_count / listings_count) if listings_count else 0.0
                ratio_threshold = (
                    expected_min.images_ratio if expected_min and expected_min.images_ratio is not None else None
                )
                below_ratio_threshold = ratio_threshold is not None and ratio < ratio_threshold
                if below_ratio_threshold or (ratio_threshold is None and images_count == 0):
                    status = "PARTIAL"

        rows.append(
            {
                "date": day.isoformat(),
                "status": status,
                "listings_count": listings_count,
                "images_count": images_count if images_required else None,
            }
        )

    return rows


def detect_missing_images_by_zip(
    detector: GapDetector,
    start: date,
    end: date,
    *,
    zip_filters: Iterable[str] | str = "all",
) -> dict[str, dict[str, Any]]:
    if isinstance(zip_filters, str):
        zips = None if zip_filters.lower() == "all" else {zip_filters.upper()}
    else:
        zips = {z.upper() for z in zip_filters} if zip_filters else None
    listings = detector.listings_by_date()
    images = detector.images_by_listing()
    result: dict[str, ZipGap] = {}
    for day in _date_range(start, end):
        for row in listings.get(day, []):
            listing_key = (row.get("listing_key") or "").strip()
            if not listing_key:
                continue
            zip_code = (row.get("zip") or "").strip()
            if not zip_code:
                continue
            if zips is not None and zip_code.upper() not in zips:
                continue
            domain = (row.get("domain") or "").strip().upper()
            if not domain:
                continue
            key = (listing_key, domain)
            image_record = images.get(key)
            status = (image_record or {}).get("status", "").lower()
            has_images = status in {"complete", "partial"}
            if not has_images:
                payload = result.setdefault(zip_code, ZipGap(set(), {}))
                payload.listings.add(listing_key)
                payload.dates.setdefault(day.isoformat(), []).append(listing_key)
    return {zip_code: payload.to_payload() for zip_code, payload in result.items()}
