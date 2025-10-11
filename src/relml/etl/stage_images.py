from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import structlog

logger = structlog.get_logger(__name__)

DATA_ROOT = Path(os.environ.get("RELML_DATA_ROOT", "data"))
STAGE_DIR = DATA_ROOT / "stage"
STAGE_IMAGES_FILE = STAGE_DIR / "images_summary.json"


def _iter_manifest_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.jsonl")):
        if path.is_file():
            yield path


def _status_from_count(count: int) -> str:
    if count <= 0:
        return "none"
    if count == 1:
        return "partial"
    return "complete"


@dataclass(slots=True)
class StageImagesResult:
    root: Path
    discovered_files: int
    staged_rows: int
    images_total: int
    stage_file: str | None
    dry_run: bool


def stage_images(root: Path | str, *, dry_run: bool = False) -> StageImagesResult:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        logger.warning("stage_images.missing_root", root=str(root_path))
        return StageImagesResult(
            root=root_path,
            discovered_files=0,
            staged_rows=0,
            images_total=0,
            stage_file=None,
            dry_run=dry_run,
        )

    manifest_files = list(_iter_manifest_files(root_path))
    discovered = len(manifest_files)
    if not manifest_files:
        return StageImagesResult(
            root=root_path,
            discovered_files=0,
            staged_rows=0,
            images_total=0,
            stage_file=None,
            dry_run=dry_run,
        )

    listings: dict[tuple[str, str], ListingImages] = {}
    images_total = 0

    for path in manifest_files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            "stage_images.invalid_json",
                            file=str(path),
                            error=str(exc),
                        )
                        continue
                    listing_key = (record.get("listing_key") or "").strip()
                    domain = (record.get("domain") or "").strip()
                    if not listing_key or not domain:
                        logger.warning(
                            "stage_images.missing_identity",
                            file=str(path),
                            listing_key=listing_key,
                            domain=domain,
                        )
                        continue
                    key = (listing_key, domain)
                    entry = listings.setdefault(
                        key,
                        ListingImages(
                            listing_key=listing_key,
                            domain=domain,
                            filenames=[],
                            hashes=[],
                            sources=set(),
                        ),
                    )
                    entry.filenames.append(str(record.get("filename", "")))
                    entry.hashes.append(str(record.get("sha1", "")))
                    entry.sources.add(str(path))
                    images_total += 1
        except FileNotFoundError:
            logger.warning("stage_images.missing_file", file=str(path))

    staged_rows = len(listings)
    stage_file = None

    if not dry_run and staged_rows:
        STAGE_DIR.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "generated_at": generated_at,
            "images_total": images_total,
            "listings": [],
        }
        for entry in sorted(listings.values(), key=lambda item: (item.domain, item.listing_key)):
            count = entry.count
            payload["listings"].append(
                {
                    "listing_key": entry.listing_key,
                    "domain": entry.domain,
                    "images_count": count,
                    "status": _status_from_count(count),
                    "filenames": entry.filenames,
                    "sha1": entry.hashes,
                    "sources": sorted(entry.sources),
                }
            )
        STAGE_IMAGES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        stage_file = STAGE_IMAGES_FILE.as_posix()

    logger.info(
        "stage_images.summary",
        root=str(root_path),
        discovered_files=discovered,
        staged_rows=staged_rows,
        images_total=images_total,
        dry_run=dry_run,
    )

    return StageImagesResult(
        root=root_path,
        discovered_files=discovered,
        staged_rows=staged_rows if not dry_run else 0,
        images_total=images_total if not dry_run else 0,
        stage_file=stage_file,
        dry_run=dry_run,
    )


@dataclass(slots=True)
class ListingImages:
    listing_key: str
    domain: str
    filenames: list[str]
    hashes: list[str]
    sources: set[str]

    @property
    def count(self) -> int:
        return len(self.filenames)
