from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterator

import pytest

from src.relml.etl.gap_detector import GapDetector, detect_gaps, detect_missing_images_by_zip, parse_config_thresholds

SAMPLES_DIR = Path("samples")


@pytest.fixture(scope="module")
def listings_sample(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    target = tmp_path_factory.mktemp("gap_detector") / "har_listings_sample.csv"
    sample = (Path(__file__).resolve().parents[1] / "samples" / "har_listings_sample.csv").read_text(encoding="utf-8")
    target.write_text(sample, encoding="utf-8")
    yield target


@pytest.fixture(scope="module")
def images_sample(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    target = tmp_path_factory.mktemp("gap_detector_images") / "listings_images_sample.csv"
    sample = (Path(__file__).resolve().parents[1] / "samples" / "listings_images_sample.csv").read_text(
        encoding="utf-8"
    )
    target.write_text(sample, encoding="utf-8")
    yield target


def test_detect_gaps_presence_only_counts(listings_sample: Path) -> None:
    detector = GapDetector(listings_csv=listings_sample)
    start = date(2025, 10, 5)
    end = date(2025, 10, 8)
    gaps = detect_gaps(detector, start, end, expected_min=None, images_required=False)

    assert gaps[0]["date"] == "2025-10-05"
    assert gaps[0]["status"] == "COMPLETE"
    assert gaps[0]["listings_count"] == 2  # noqa: PLR2004

    assert gaps[1]["date"] == "2025-10-06"
    assert gaps[1]["status"] == "COMPLETE"
    assert gaps[1]["listings_count"] == 3  # noqa: PLR2004

    assert gaps[2]["date"] == "2025-10-07"
    assert gaps[2]["status"] == "COMPLETE"
    assert gaps[3]["date"] == "2025-10-08"
    assert gaps[3]["status"] == "COMPLETE"


def test_detect_gaps_with_thresholds_and_images(listings_sample: Path, images_sample: Path) -> None:
    detector = GapDetector(
        listings_csv=listings_sample,
        images_csv=images_sample,
    )
    thresholds = parse_config_thresholds({"listings_per_day": 3, "images_ratio": 0.5})
    start = date(2025, 10, 5)
    end = date(2025, 10, 7)
    gaps = detect_gaps(detector, start, end, expected_min=thresholds, images_required=True)
    day_to_status = {row["date"]: row for row in gaps}

    assert day_to_status["2025-10-05"]["status"] == "PARTIAL"  # 2 listings < threshold 3
    assert day_to_status["2025-10-06"]["status"] == "PARTIAL"  # 3 listings but images ratio < 0.5
    assert day_to_status["2025-10-07"]["status"] == "COMPLETE"


def test_detect_missing_images_by_zip(listings_sample: Path, images_sample: Path) -> None:
    detector = GapDetector(
        listings_csv=listings_sample,
        images_csv=images_sample,
    )
    start = date(2025, 10, 5)
    end = date(2025, 10, 7)
    missing = detect_missing_images_by_zip(detector, start, end, zip_filters={"77002", "73301"})

    assert missing["77002"]["dates"]["2025-10-05"] == ["HAR101"]
    assert missing["77002"]["dates"]["2025-10-06"] == ["HAR200"]
    assert set(missing["73301"]["dates"]["2025-10-07"]) == {"HAR104", "HAR202"}
