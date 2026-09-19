"""Entrants the archive has never seen, at the races where that matters (Peter, 2026-09-19).

THE PROBLEM
-----------
At the biggest races a runner with no Newfoundland result is not an average newcomer. At the
Tely 10 about four of the top ten have come from away in recent years, and one or two of those
have no result here at all; they were 2nd in 2025 and 3rd and 4th in 2026. Cape to Cabot has
about one a year in its top ten (`scratch/outsiders.py`). The model gives every newcomer the
group prior for their sex, which puts all of them mid-pack, so the predicted top ten was
missing a runner or two, and every local runner's predicted place was a place or two too good.

WHAT THIS DOES
--------------
For a race that asks for it (`newcomers = "course"` in data/live.toml, set only for the few
biggest races), a newcomer's time is drawn from how first-timers at earlier editions of the
same course actually finished, relative to the returning runners in the same edition:

    r = log(first-timer's time) - median log time of that edition's returning finishers

pooled over editions and split by sex. On race day a newcomer's log time is the median of the
known entrants' log times in that draw plus an `r` drawn from the pool. The pool carries the
fast tail the group prior does not: the handful of visitors who win.

⚠️ **This does not say which newcomer is fast.** Each newcomer gets the same distribution; the
list prints nothing that tells a visiting 2:20 marathoner from a first-timer out for the day.
What changes is the field: the simulation now puts some newcomers into the top ten about as
often as history did, so the named local runners' places are no longer a place or two too
good, and the race page says how many places near the top are expected to go to runners with
no results here (`expected_in_top`).

⚠️ **Editions before 2013 are left out of the pool.** The archive starts in 2008, and in its
first years every runner is a "first-timer" because nothing before them was read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from finishline.identity.resolve import Runner
from finishline.schema import Race

# The first edition year whose first-timers are really first-timers (the archive starts 2008).
FIRST_POOL_YEAR = 2013
# A pool smaller than this for one sex falls back to both sexes together.
MIN_POOL = 30


@dataclass(frozen=True, slots=True)
class Pool:
    """How first-timers finished at this course, relative to the returning field."""

    course_id: str
    by_sex: Mapping[str, np.ndarray]
    everyone: np.ndarray
    editions: int

    def draw(self, sex: str | None, n: int, rng: np.random.Generator) -> np.ndarray:
        values = self.by_sex.get(sex or "", np.empty(0))
        if values.size < MIN_POOL:
            values = self.everyone
        return np.asarray(rng.choice(values, size=n, replace=True))


def pool(
    runners: Sequence[Runner], races: Mapping[str, Race], course_id: str, before: date
) -> Pool | None:
    """First-timers' finishes relative to returning finishers, over this course's editions.

    None when the course has no usable edition, and the caller falls back to the group prior.
    """
    firsts: dict[str, date] = {}
    finishes: dict[str, list[tuple[str, float]]] = {}
    for runner in runners:
        if runner.ambiguous:
            continue
        for result in runner.results:
            race = races.get(result.race_id)
            if race is None or not result.finished or not result.seconds or race.date >= before:
                continue
            first = firsts.get(runner.runner_id)
            if first is None or race.date < first:
                firsts[runner.runner_id] = race.date
            if race.course_id == course_id and race.date.year >= FIRST_POOL_YEAR:
                finishes.setdefault(result.race_id, []).append(
                    (runner.runner_id, float(np.log(result.seconds)))
                )
    sexes = {runner.runner_id: runner.sex or "" for runner in runners}
    by_sex: dict[str, list[float]] = {}
    everyone: list[float] = []
    editions = 0
    for race_id, rows in finishes.items():
        when = races[race_id].date
        returning = [t for runner_id, t in rows if firsts[runner_id] < when]
        new = [(runner_id, t) for runner_id, t in rows if firsts[runner_id] == when]
        if len(returning) < MIN_POOL or not new:
            continue
        centre = float(np.median(returning))
        editions += 1
        for runner_id, t in new:
            by_sex.setdefault(sexes[runner_id], []).append(t - centre)
            everyone.append(t - centre)
    if not everyone:
        return None
    return Pool(
        course_id=course_id,
        by_sex={sex: np.asarray(values) for sex, values in by_sex.items()},
        everyone=np.asarray(everyone),
        editions=editions,
    )


def newcomer_log_times(
    known_log_times: np.ndarray,
    newcomers: Sequence[str | None],
    source: Pool,
    rng: np.random.Generator,
) -> np.ndarray:
    """(draws, newcomers) log times: each draw's known-field median plus a drawn offset.

    `known_log_times` is (draws, known entrants). With no known entrant there is no field to
    stand against, which a race with a start list and an archive never is.
    """
    if known_log_times.shape[1] == 0:
        raise ValueError("no known entrant to place newcomers against")
    centre = np.median(known_log_times, axis=1)
    draws = known_log_times.shape[0]
    columns = [centre + source.draw(sex, draws, rng) for sex in newcomers]
    return np.column_stack(columns) if columns else np.empty((draws, 0))


def expected_in_top(
    places: np.ndarray, newcomer_columns: Sequence[int], top: int
) -> tuple[float, int, int]:
    """How many of the top `top` places go to newcomers: the mean and the middle 80% range."""
    if not newcomer_columns:
        return 0.0, 0, 0
    counts = (places[:, list(newcomer_columns)] <= top).sum(axis=1)
    low, high = np.quantile(counts, [0.10, 0.90])
    return float(counts.mean()), round(float(low)), round(float(high))


def likely_places(places: np.ndarray, newcomer_columns: Sequence[int], top: int) -> list[int]:
    """The places near the top a newcomer most often takes, as many as are expected there.

    What the race page marks as "a runner with no results here", so the named runners' rows
    and these together fill the top of the table the way the simulation fills it.
    """
    if not newcomer_columns:
        return []
    held = places[:, list(newcomer_columns)]
    share = np.array([(held == place).any(axis=1).mean() for place in range(1, top + 1)])
    expected = round(float((held <= top).sum(axis=1).mean()))
    chosen = np.argsort(-share, kind="stable")[:expected]
    return sorted(int(index) + 1 for index in chosen)
