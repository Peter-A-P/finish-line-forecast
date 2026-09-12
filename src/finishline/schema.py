"""The three things this project reads and the one it writes.

A `Race` is one edition of one event: the Cape to Cabot of 2025, not "Cape to Cabot". A
`Result` is one runner's line on that race's page. A `Runner` is what entity resolution
turns a pile of results into, and the thing a prediction is made for.

⚠️ **A result carries a `course_id` through its race, and the two are not the same.**
Course effects are estimated per edition (PLAN.md 5.3) because the weather differs every
year, but the elevation profile is a property of the course, so the physics prior is
shared across editions and the estimate is not. Merging them would make every year's
prediction inherit the last year's weather.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Distances a road result can be run over, in metres. The mile and its multiples are
# exact by definition of the international yard, which is why they are written out.
MILE_M = 1609.344
HALF_MARATHON_M = 21097.494
MARATHON_M = 42194.988


@dataclass(frozen=True, slots=True)
class Race:
    """One edition of one event."""

    race_id: str
    name: str
    date: date
    distance_m: float
    course_id: str
    url: str

    @property
    def year(self) -> int:
        return self.date.year


@dataclass(frozen=True, slots=True)
class Result:
    """One runner's line on one race's results page, as the page printed it.

    Nothing here is inferred. `sex`, `age_band` and `hometown` are None when the page did
    not print them, because a guess would propagate into the group prior that carries
    every runner with no history.
    """

    race_id: str
    place: int | None
    bib: int | None
    name: str
    club: str | None
    sex: str | None
    sex_place: int | None
    age_band: str | None
    category_place: int | None
    hometown: str | None
    gun_seconds: float | None
    chip_seconds: float | None

    @property
    def seconds(self) -> float | None:
        """The time to model on: chip where the race recorded one, else gun.

        Only the Tely 10 prints both. Its gun and chip times differ by up to several
        minutes in a field of four thousand, and the chip time is the one the runner
        actually ran, so it wins wherever it exists. The backtest reports which basis
        each result used, because a model fitted on chip times and scored against gun
        times would flatter itself by the width of the start corral.
        """
        return self.chip_seconds if self.chip_seconds is not None else self.gun_seconds

    @property
    def finished(self) -> bool:
        """Whether this row is a finish at all. A DNF has a place and no time."""
        return self.seconds is not None
