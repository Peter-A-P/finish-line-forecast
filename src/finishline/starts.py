"""When each race starts, which decides what weather its field met.

⚠️ **No results page in the archive prints a start time, and the first version of the
weather layer assumed 09:00 for everything.** The organisers' times say otherwise: road races
here go at 8 am as standard, marathons at 7, and the Uniformed Services Run staggers its
distances from 7 to 10. On a warming summer morning an hour is a degree or more, and the sun
is higher, so a marathon read from 9 was met two hours of heat and sun it never ran in. The
times are in `data/starts.toml`, with where they came from.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from finishline.schema import Race

STARTS = Path("data") / "starts.toml"

# The standard here, used for any course the file does not name.
STANDARD_HOUR = 8
MARATHON_HOUR = 7
# Anything this long is run as a marathon, on a marathon's schedule.
MARATHON_M = 40_000.0


@dataclass(frozen=True, slots=True)
class Starts:
    """Start hours by course, with the defaults for a course nobody listed."""

    courses: Mapping[str, int] = field(default_factory=dict)
    standard: int = STANDARD_HOUR
    marathon: int = MARATHON_HOUR

    def hour(self, race: Race) -> int:
        """The wall-clock hour this race started."""
        if race.course_id in self.courses:
            return self.courses[race.course_id]
        return self.marathon if race.distance_m >= MARATHON_M else self.standard

    def by_race(self, races: Mapping[str, Race]) -> dict[str, int]:
        """Every race's start hour, keyed by race id."""
        return {race_id: self.hour(race) for race_id, race in races.items()}


def load(path: Path = STARTS) -> Starts:
    """The start times on file, or the defaults alone when there is no file."""
    if not path.exists():
        return Starts()
    record = tomllib.loads(path.read_text(encoding="utf-8"))
    default = record.get("default", {})
    courses = {course: int(hour) for course, hour in record.get("courses", {}).items()}
    for course, hour in courses.items():
        if not 0 <= hour <= 23:
            raise ValueError(f"{course}: {hour} is not an hour of the day")
    return Starts(
        courses=courses,
        standard=int(default.get("standard", STANDARD_HOUR)),
        marathon=int(default.get("marathon", MARATHON_HOUR)),
    )
