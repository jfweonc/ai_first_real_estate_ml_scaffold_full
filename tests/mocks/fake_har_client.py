from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class FakeHarRun:
    date: date
    listings: int
    images_batches: dict[str, int] = field(default_factory=dict)
    marked_partial: bool = False


@dataclass
class FakeHarClient:
    runs: list[FakeHarRun] = field(default_factory=list)

    def fetch_listings(self, day: date, count: int) -> None:
        self._current(day).listings = count

    def fetch_images(self, day: date, zip_code: str, count: int) -> None:
        self._current(day).images_batches[zip_code] = count

    def mark_partial(self, day: date) -> None:
        self._current(day).marked_partial = True

    def _current(self, day: date) -> FakeHarRun:
        for run in self.runs:
            if run.date == day:
                return run
        run = FakeHarRun(date=day, listings=0)
        self.runs.append(run)
        return run
