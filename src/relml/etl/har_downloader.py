from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

import structlog

from .gap_detector import GapDetector, Thresholds, detect_gaps, detect_missing_images_by_zip, parse_config_thresholds

logger = structlog.get_logger(__name__)

CENTRAL_TZ = timezone(timedelta(hours=-5))


def yesterday(local_today: date | None = None) -> date:
    today = local_today or datetime.now(CENTRAL_TZ).date()
    return today - timedelta(days=1)


def parse_since(value: str) -> date:
    if value.endswith("d"):
        days = int(value[:-1])
        return yesterday() - timedelta(days=days)
    return datetime.fromisoformat(value).date()


@dataclass(slots=True)
class HarDownloadConfig:
    limits: dict[str, int]
    expected_min: Thresholds | None = None
    images_enabled: bool = True
    zip_filters: list[str] | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> HarDownloadConfig:
        limits_raw = raw.get("limits")
        limits: dict[str, int] = {}
        if isinstance(limits_raw, Mapping):
            limits = {str(key): int(value) for key, value in limits_raw.items() if isinstance(value, (int, float))}
        expected_raw = raw.get("expected_min")
        thresholds = parse_config_thresholds(expected_raw) if isinstance(expected_raw, Mapping) else None
        images_cfg = raw.get("images")
        images_enabled = True
        zip_filters: list[str] | None = None
        if isinstance(images_cfg, Mapping):
            enabled_raw = images_cfg.get("enabled")
            images_enabled = bool(enabled_raw) if enabled_raw is not None else True
            filters_raw = images_cfg.get("zip_filters")
            if isinstance(filters_raw, list):
                zip_filters = [str(item).upper() for item in filters_raw]
            elif isinstance(filters_raw, str) and filters_raw.lower() != "all":
                zip_filters = [filters_raw.upper()]
        return cls(
            limits=limits,
            expected_min=thresholds,
            images_enabled=images_enabled,
            zip_filters=zip_filters,
        )


@dataclass(slots=True)
class HarDownloadRequest:
    since: date | None
    until: date | None
    today: bool = False
    images: bool = True
    dry_run: bool = False


@dataclass(slots=True)
class DownloadPlan:
    listing_windows: list[tuple[date, date]]
    image_batches: dict[date, dict[str, list[list[str]]]]


class StatusUpdater:
    def mark_day(self, *, day: date, status: str, files_count: int | None = None, notes: str | None = None) -> None:
        raise NotImplementedError

    def mark_listing_images(self, *, listing_key: str, domain: str, status: str, notes: str | None = None) -> None:
        raise NotImplementedError


class HarDownloader:
    def __init__(
        self,
        *,
        config: HarDownloadConfig,
        gap_detector: GapDetector,
        status_updater: StatusUpdater,
        har_client: object | None,
        dry_run: bool,
    ) -> None:
        self.config = config
        self.detector = gap_detector
        self.status_updater = status_updater
        self.har_client = har_client
        self.dry_run = dry_run

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def plan(self, request: HarDownloadRequest) -> DownloadPlan:
        since, until = self._resolve_range(request)
        limits = self.config.limits
        listing_windows = self._partition_date_range(since, until, limits.get("max_listings_per_run", 5000))
        image_batches: dict[date, dict[str, list[list[str]]]] = {}
        if request.images and self.config.images_enabled:
            image_batches = self._plan_images(since, until)
        return DownloadPlan(listing_windows=listing_windows, image_batches=image_batches)

    def execute(self, request: HarDownloadRequest, *, current_date: date | None = None) -> dict[str, object]:
        if request.today:
            day = current_date or datetime.now(CENTRAL_TZ).date()
            self.status_updater.mark_day(
                day=day,
                status="PARTIAL",
                notes="Marked partial via --today",
            )
            return {"dry_run": True, "message": "Marked today as partial"}

        plan = self.plan(request)
        summary = self._serialize_plan(plan, dry_run=self.dry_run or request.dry_run)
        if summary["dry_run"]:
            logger.info("har_downloader.plan", plan=json.dumps(summary))
            return summary

        logger.warning("har_downloader.execute_not_implemented", message="Downloader execution not yet implemented")
        return summary

    def _resolve_range(self, request: HarDownloadRequest) -> tuple[date, date]:
        if request.since and request.until:
            return request.since, request.until
        if request.since and not request.until:
            return request.since, yesterday()
        if not request.since and request.until:
            return request.until - timedelta(days=14), request.until
        return yesterday() - timedelta(days=14), yesterday()

    def _partition_date_range(
        self,
        start: date,
        end: date,
        max_listings: int,
    ) -> list[tuple[date, date]]:
        gaps = detect_gaps(self.detector, start, end, expected_min=None, images_required=False)
        day_to_count: dict[date, int] = {}
        for row in gaps:
            day_raw = row.get("date")
            listings_count_raw = row.get("listings_count", 0)
            if not isinstance(day_raw, str):
                continue
            try:
                day_key = date.fromisoformat(day_raw)
            except ValueError:
                continue
            if isinstance(listings_count_raw, (int, float)):
                listings_count = int(listings_count_raw)
            elif isinstance(listings_count_raw, str):
                try:
                    listings_count = int(listings_count_raw)
                except ValueError:
                    listings_count = 0
            else:
                listings_count = 0
            day_to_count[day_key] = listings_count
        windows: list[tuple[date, date]] = []
        window_start = start
        total = 0
        cursor = start
        while cursor <= end:
            count = day_to_count.get(cursor, 0)
            if total + count > max_listings and window_start <= cursor - timedelta(days=1):
                windows.append((window_start, cursor - timedelta(days=1)))
                window_start = cursor
                total = 0
            total += count
            cursor += timedelta(days=1)
        windows.append((window_start, end))
        return windows

    def _plan_images(self, start: date, end: date) -> dict[date, dict[str, list[list[str]]]]:
        batches = detect_missing_images_by_zip(
            self.detector,
            start,
            end,
            zip_filters=self.config.zip_filters or "all",
        )
        day_lookup: dict[date, dict[str, list[list[str]]]] = {}
        max_batch = int(self.config.limits.get("max_images_listings_batch", 100))
        for zip_code, payload in batches.items():
            dates = payload.get("dates")
            if not isinstance(dates, dict):
                continue
            for day_str, listings in dates.items():
                if not isinstance(day_str, str) or not isinstance(listings, list):
                    continue
                day = date.fromisoformat(day_str)
                day_lookup.setdefault(day, {})
                batched: list[list[str]] = []
                current: list[str] = []
                for listing in listings:
                    current.append(str(listing))
                    if len(current) >= max_batch:
                        batched.append(current)
                        current = []
                if current:
                    batched.append(current)
                day_lookup[day][zip_code] = batched
        return day_lookup

    def _serialize_plan(self, plan: DownloadPlan, *, dry_run: bool) -> dict[str, object]:
        image_batches = {day.isoformat(): payload for day, payload in plan.image_batches.items()}
        listing_windows = [(start.isoformat(), end.isoformat()) for start, end in plan.listing_windows]
        return {
            "dry_run": dry_run,
            "listing_windows": listing_windows,
            "image_batches": image_batches,
        }
