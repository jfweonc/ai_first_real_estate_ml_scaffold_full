from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from .stage_images import STAGE_IMAGES_FILE
from .stage_listings import STAGE_LISTINGS_FILE

logger = structlog.get_logger(__name__)

DATA_ROOT = Path(os.environ.get("RELML_DATA_ROOT", "data"))
SAMPLES_DIR = DATA_ROOT / "samples"
LISTINGS_SAMPLE_FILE = SAMPLES_DIR / "stage_listings_sample.csv"
IMAGES_SAMPLE_FILE = SAMPLES_DIR / "stage_images_sample.json"


@dataclass(slots=True)
class StageSamplesResult:
    listings_total: int
    images_total: int
    listings_sample_count: int
    images_sample_count: int
    listings_sample_file: str | None
    images_sample_file: str | None
    dry_run: bool


def _read_stage_listings(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        logger.warning("stage_samples.missing_listings", path=str(path))
        empty_header: list[str] = []
        empty_rows: list[dict[str, str]] = []
        return empty_header, empty_rows
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
        header = list(reader.fieldnames or [])
        return header, rows


def _read_stage_images(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.warning("stage_samples.missing_images", path=str(path))
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        logger.warning("stage_samples.invalid_images_json", path=str(path), error=str(exc))
        return {}


def build_stage_samples(*, sample_size: int = 20, dry_run: bool = False) -> StageSamplesResult:
    sample_size = max(sample_size, 0)
    listings_header, listings_rows = _read_stage_listings(STAGE_LISTINGS_FILE)
    listings_total = len(listings_rows)
    listings_sample = listings_rows[:sample_size]

    images_payload = _read_stage_images(STAGE_IMAGES_FILE)
    listings_obj = images_payload.get("listings", [])
    image_listings = list(listings_obj) if isinstance(listings_obj, list) else []
    images_total_obj = images_payload.get("images_total", len(image_listings))
    images_total = int(images_total_obj) if isinstance(images_total_obj, (int, float)) else len(image_listings)
    images_sample_listings = image_listings[:sample_size]

    listings_sample_path = LISTINGS_SAMPLE_FILE if listings_sample and not dry_run else None
    images_sample_path = IMAGES_SAMPLE_FILE if images_sample_listings and not dry_run else None

    if not dry_run:
        if listings_sample:
            SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            with LISTINGS_SAMPLE_FILE.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=listings_header or list(listings_sample[0].keys()))
                writer.writeheader()
                for row in listings_sample:
                    writer.writerow(row)
        if images_sample_listings:
            SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            payload = dict(images_payload)
            payload["generated_at"] = images_payload.get("generated_at", datetime.now(timezone.utc).isoformat())
            payload["listings"] = images_sample_listings
            IMAGES_SAMPLE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info(
        "stage_samples.summary",
        listings_total=listings_total,
        images_total=images_total,
        listings_sample_count=len(listings_sample) if not dry_run else 0,
        images_sample_count=len(images_sample_listings) if not dry_run else 0,
        dry_run=dry_run,
    )

    return StageSamplesResult(
        listings_total=listings_total,
        images_total=images_total,
        listings_sample_count=len(listings_sample) if not dry_run else 0,
        images_sample_count=len(images_sample_listings) if not dry_run else 0,
        listings_sample_file=listings_sample_path.as_posix() if listings_sample_path else None,
        images_sample_file=images_sample_path.as_posix() if images_sample_path else None,
        dry_run=dry_run,
    )
