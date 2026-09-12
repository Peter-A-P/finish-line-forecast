"""Everything known before a given race, and nothing known after it.

WHY THIS IS ONE OBJECT AND NOT A DATAFRAME
------------------------------------------
The single way this project could produce a flattering number and never notice is by
letting a model see a result from the race it is predicting, or from a race after it. A
backtest that does that reports skill it does not have, and nobody reading the README
could tell.

So the cut is made once, here, in the constructor. `History.before(...)` is the only way
to build one, it takes the origin date, and it keeps nothing dated on or after that day.
Every model is handed a `History` and has no other access to the archive, which turns
leakage from something to remember into something a model cannot reach.

⚠️ **The cut is on the race date, not the race id**, and it is strict. Two races on one
day (the Trapline runs four) are all excluded from each other's history. A runner who ran
the 5 km that morning is a runner whose 10 km an hour later is not yet known, which is
exactly the position the real prediction is made from.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from finishline.identity.resolve import Runner, age_range
from finishline.schema import Race, Result

# How far back "recent form" reaches. Eighteen months is the window the project brief
# names: long enough that most runners have something in it, short enough that a time
# from two build-ups ago does not set today's prediction.
RECENT = timedelta(days=548)


@dataclass(frozen=True, slots=True)
class History:
    """The archive as it stood the day before a race."""

    origin: date
    races: dict[str, Race]
    runners: dict[str, Runner]
    _by_course: dict[str, list[str]]
    _by_race: dict[str, list[Result]]

    @classmethod
    def before(
        cls, when: date, races: dict[str, Race], runners: list[Runner]
    ) -> History:
        """Everything dated strictly before `when`. The one way to build a History."""
        kept: dict[str, Runner] = {}
        by_race: dict[str, list[Result]] = defaultdict(list)
        for runner in runners:
            earlier = tuple(
                result
                for result in runner.results
                if races[result.race_id].date < when and result.finished
            )
            if not earlier:
                continue
            kept[runner.runner_id] = Runner(
                runner_id=runner.runner_id,
                name=runner.name,
                hometown=runner.hometown,
                sex=runner.sex,
                results=earlier,
                ambiguous=runner.ambiguous,
                reason=runner.reason,
            )
            for result in earlier:
                by_race[result.race_id].append(result)

        by_course: dict[str, list[str]] = defaultdict(list)
        for race_id in by_race:
            by_course[races[race_id].course_id].append(race_id)
        for race_ids in by_course.values():
            race_ids.sort(key=lambda race_id: races[race_id].date, reverse=True)

        return cls(
            origin=when,
            races={race_id: race for race_id, race in races.items() if race.date < when},
            runners=kept,
            _by_course=dict(by_course),
            _by_race=dict(by_race),
        )

    def results_of(self, runner_id: str) -> tuple[Result, ...]:
        """This runner's finishes, oldest first. Empty for a runner with no history."""
        runner = self.runners.get(runner_id)
        return runner.results if runner else ()

    def recent(self, runner_id: str, *, window: timedelta = RECENT) -> tuple[Result, ...]:
        """This runner's finishes inside the recent-form window."""
        cutoff = self.origin - window
        return tuple(
            result
            for result in self.results_of(runner_id)
            if self.races[result.race_id].date >= cutoff
        )

    def latest(self, runner_id: str) -> Result | None:
        """The most recent finish, or None."""
        results = self.results_of(runner_id)
        return results[-1] if results else None

    def previous_edition(self, course_id: str) -> str | None:
        """The most recent earlier running of this course, or None."""
        editions = self._by_course.get(course_id, [])
        return editions[0] if editions else None

    def field(self, race_id: str) -> tuple[Result, ...]:
        """Every finish in one past race."""
        return tuple(self._by_race.get(race_id, ()))

    def category_median(
        self, course_id: str, sex: str | None, age_band: str | None
    ) -> tuple[float | None, str]:
        """The median finish time of this category at the last running of this course.

        Returns the time and a one-phrase description of what it actually used, because
        the fallbacks matter: a median over "everyone who ran" is a much weaker claim
        than one over "women aged 40 to 49 who ran", and the report prints which.

        ⚠️ **Age bands are matched by overlap, not by text.** The Tely prints five-year
        bands and every other race prints ten-year ones, so `40-44` and `40-49` have to
        find each other or this falls back to the whole field for half the archive.
        """
        edition = self.previous_edition(course_id)
        if edition is None:
            return None, "no earlier running of this course"
        results = self.field(edition)
        if not results:
            return None, "no finishers recorded at the last running"

        wanted = age_range(age_band)
        if sex and wanted:
            matched = [
                result
                for result in results
                if result.sex == sex and _overlaps(age_range(result.age_band), wanted)
            ]
            if len(matched) >= 3:
                return _median(matched), f"{sex} {age_band} at the last running"
        if sex:
            matched = [result for result in results if result.sex == sex]
            if len(matched) >= 3:
                return _median(matched), f"all {sex} finishers at the last running"
        return _median(list(results)), "the whole field at the last running"


def _overlaps(left: tuple[int, int] | None, right: tuple[int, int]) -> bool:
    """Whether two age bands could describe the same runner."""
    return left is not None and left[0] <= right[1] and right[0] <= left[1]


def _median(results: list[Result]) -> float | None:
    times = [result.seconds for result in results if result.seconds is not None]
    return statistics.median(times) if times else None
