from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, cast

import pytest

from src.relml.etl.acq_status import ImageStatusRow
from src.relml.etl.gap_detector import GapDetector
from src.relml.etl.har_downloader import HarDownloadConfig, HarDownloader, HarDownloadRequest, StatusUpdater


@dataclass
class StubDay:
    status: str
    last_attempt_ts: datetime
    files_count: int | None
    notes: str | None


@dataclass
class StubStatusUpdater(StatusUpdater):
    daily: dict[date, StubDay] = field(default_factory=dict)
    images: dict[tuple[str, str], ImageStatusRow] = field(default_factory=dict)

    def mark_day(self, *, day: date, status: str, files_count: int | None = None, notes: str | None = None) -> None:
        self.daily[day] = StubDay(
            status=status,
            last_attempt_ts=HarDownloader.now(),
            files_count=files_count,
            notes=notes,
        )

    def mark_listing_images(self, *, listing_key: str, domain: str, status: str, notes: str | None = None) -> None:
        key = (listing_key, domain)
        self.images[key] = ImageStatusRow(listing_key, domain, status, HarDownloader.now(), notes)


@pytest.fixture(scope="module")
def sample_gap_detector(tmp_path_factory: pytest.TempPathFactory) -> Iterator[GapDetector]:
    fixtures_root = Path(__file__).resolve().parents[1] / "samples"
    listings_tmp = tmp_path_factory.mktemp("downloads") / "har_listings_sample.csv"
    images_tmp = tmp_path_factory.mktemp("downloads_images") / "listings_images_sample.csv"
    listings_tmp.write_text((fixtures_root / "har_listings_sample.csv").read_text(encoding="utf-8"), encoding="utf-8")
    images_tmp.write_text((fixtures_root / "listings_images_sample.csv").read_text(encoding="utf-8"), encoding="utf-8")
    yield GapDetector(listings_csv=listings_tmp, images_csv=images_tmp)


def make_config(**kwargs: Any) -> HarDownloadConfig:
    defaults: dict[str, Any] = {"limits": {"max_listings_per_run": 5000, "max_images_listings_batch": 100}}
    defaults.update(kwargs)
    return HarDownloadConfig.from_dict(defaults)


def test_planner_computes_date_windows_under_listing_limit(sample_gap_detector: GapDetector) -> None:
    config = make_config(limits={"max_listings_per_run": 3, "max_images_listings_batch": 100})
    downloader = HarDownloader(
        config=config,
        gap_detector=sample_gap_detector,
        status_updater=StubStatusUpdater(),
        har_client=None,
        dry_run=True,
    )
    request = HarDownloadRequest(since=date(2025, 10, 5), until=date(2025, 10, 8), images=True)
    plan = downloader.plan(request)

    assert plan.listing_windows == [
        (date(2025, 10, 5), date(2025, 10, 5)),
        (date(2025, 10, 6), date(2025, 10, 6)),
        (date(2025, 10, 7), date(2025, 10, 7)),
        (date(2025, 10, 8), date(2025, 10, 8)),
    ]
    assert plan.image_batches[date(2025, 10, 5)] == {"77002": [["HAR101"]]}
    assert plan.image_batches[date(2025, 10, 6)] == {"77002": [["HAR200"]], "77479": [["HAR102"]]}
    assert plan.image_batches[date(2025, 10, 7)] == {"73301": [["HAR104", "HAR202"]]}
    assert plan.image_batches[date(2025, 10, 8)] == {"73301": [["HAR204"]]}


def test_today_flag_marks_partial_and_skips_download(sample_gap_detector: GapDetector) -> None:
    updater = StubStatusUpdater()
    config = make_config()
    downloader = HarDownloader(
        config=config,
        gap_detector=sample_gap_detector,
        status_updater=updater,
        har_client=None,
        dry_run=True,
    )
    today = date(2025, 10, 10)
    request = HarDownloadRequest(today=True, since=None, until=None)
    downloader.execute(request, current_date=today)

    assert updater.daily[today].status == "PARTIAL"
    assert updater.daily[today].notes == "Marked partial via --today"


def test_dry_run_returns_summary_without_fetching(sample_gap_detector: GapDetector) -> None:
    updater = StubStatusUpdater()
    config = make_config(limits={"max_listings_per_run": 5000, "max_images_listings_batch": 2})
    downloader = HarDownloader(
        config=config,
        gap_detector=sample_gap_detector,
        status_updater=updater,
        har_client=None,
        dry_run=True,
    )
    request = HarDownloadRequest(since=date(2025, 10, 5), until=date(2025, 10, 7), images=True)
    summary = downloader.execute(request)

    assert bool(summary.get("dry_run")) is True
    listing_windows = cast(list[tuple[str, str]], summary["listing_windows"])
    assert listing_windows[0] == ("2025-10-05", "2025-10-07")
    batches = cast(dict[str, dict[str, list[list[str]]]], summary["image_batches"])
    assert "2025-10-05" in batches
