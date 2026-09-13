"""How hard each course is, measured from the results rather than from a map.

Runners cross between courses, so a course's difficulty is identifiable from finishes
alone: somebody who is slower on Cape to Cabot than their own equal-VDOT expectation every
year, and faster on Mews Memorial every year, is telling us what the hills cost without any
elevation data being involved.

The fit is two-way: a per-runner effect and a per-edition effect, alternated until they
settle. It is the same structure as the hierarchical model's `alpha_i` and `delta_r`
(PLAN.md 5.3) without the shrinkage, and its job here is to say what those effects look
like before a prior is put on them.

⚠️ **The per-runner career trend is not optional, and leaving it out is a trap that looks
like a finding.** Fitted without one, Cape to Cabot's edition effect climbs almost
monotonically from +3.8 percent in 2013 to +14.4 percent in 2025, which reads as a course
getting harder every year. It is not. A runner effect that is one constant for a whole
career has nowhere to put the fact that runners get slower as they age, so the edition
effects absorb it: every one of thirteen well-covered courses drifts upward, at a median
of +0.60 percent a year. Add a per-runner trend and the median drift is +0.00 percent and
the signs scatter. A model fitted the first way and asked for 2026 would extrapolate ten
points of course inflation that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from finishline.history import History
from finishline.metrics import daniels
from finishline.schema import Race, Result

# Enough to settle. The effects move by less than 1e-6 after about twenty on this data.
ROUNDS = 30

# A runner seen twice in one season can otherwise claim a forty-percent-a-year decline off
# two points. Five percent a year is already far outside anything physiological.
MAX_TREND_PER_YEAR = 0.05

# Below this a course effect is noise dressed as a measurement, and the physics prior in
# data/courses.toml is the better answer.
MIN_FINISHES = 30

# Any constant works: the runner effect absorbs the level and every course figure is a
# ratio, so the reference cancels out of everything reported.
REFERENCE_VDOT = 50.0


@dataclass(frozen=True, slots=True)
class CourseFactor:
    """One course's difficulty, as a fraction of an equal-VDOT flat time."""

    course_id: str
    finishes: int
    editions: int
    factor: float
    low: float
    high: float

    @property
    def percent(self) -> float:
        return self.factor * 100


@dataclass(frozen=True, slots=True)
class Fit:
    """Course and edition effects, and the runner effects they were separated from."""

    courses: dict[str, CourseFactor]
    editions: dict[str, float]

    def prior_for(self, course_id: str) -> float | None:
        """The course factor, or None where the history is too thin to claim one."""
        measured = self.courses.get(course_id)
        return measured.factor if measured else None


def _rows(
    history: History, races: dict[str, Race]
) -> tuple[np.ndarray, ...] | None:
    """One row per usable finish, as parallel arrays keyed by integer index."""
    runner_ix: list[int] = []
    course_ix: list[int] = []
    edition_ix: list[int] = []
    values: list[float] = []
    years: list[float] = []
    courses: dict[str, int] = {}
    editions: dict[str, int] = {}

    for index, runner_id in enumerate(sorted(history.runners)):
        mine: list[tuple[str, str, float, float]] = []
        for result in history.results_of(runner_id):
            row = _log_ratio(result, races)
            if row is not None:
                race = races[result.race_id]
                mine.append((race.course_id, race.race_id, row, float(race.date.year)))
        # A runner with one finish carries no information about which course is harder;
        # they would fit their own effect exactly and leave a zero residual.
        if len(mine) < 2:
            continue
        for course_id, race_id, value, year in mine:
            runner_ix.append(index)
            course_ix.append(courses.setdefault(course_id, len(courses)))
            edition_ix.append(editions.setdefault(race_id, len(editions)))
            values.append(value)
            years.append(year)

    if not values:
        return None
    return (
        np.array(runner_ix),
        np.array(course_ix),
        np.array(edition_ix),
        np.array(values),
        np.array(years),
        np.array(sorted(courses, key=lambda k: courses[k]), dtype=object),
        np.array(sorted(editions, key=lambda k: editions[k]), dtype=object),
    )


def _log_ratio(result: Result, races: dict[str, Race]) -> float | None:
    """Log of the time run over the time a reference runner would take here."""
    if not result.finished or result.race_id not in races:
        return None
    seconds = result.chip_seconds or result.gun_seconds
    if seconds is None or seconds <= 0:
        return None
    expected = daniels.race_time(REFERENCE_VDOT, races[result.race_id].distance_m)
    if expected is None or expected <= 0:
        return None
    return float(np.log(seconds / expected))


def fit(
    history: History, races: dict[str, Race], *, seed: int = 20261018, draws: int = 400
) -> Fit:
    """Measure every course's factor, with an interval over runners.

    The interval is a bootstrap over runners rather than over finishes, because two
    finishes by the same person are not independent evidence about a hill.
    """
    prepared = _rows(history, races)
    if prepared is None:
        return Fit(courses={}, editions={})
    runner_ix, course_ix, edition_ix, values, years, course_names, edition_names = prepared

    course_effect = _alternate(values, runner_ix, course_ix, years)
    edition_effect = _alternate(values, runner_ix, edition_ix, years)

    counts = np.bincount(course_ix, minlength=course_names.size)
    editions_per_course: dict[int, set[int]] = {}
    for course, edition in zip(course_ix, edition_ix, strict=True):
        editions_per_course.setdefault(int(course), set()).add(int(edition))

    spread = _bootstrap(values, runner_ix, course_ix, years, course_names.size, seed, draws)

    measured: dict[str, CourseFactor] = {}
    for index, name in enumerate(course_names):
        if counts[index] < MIN_FINISHES:
            continue
        low, high = spread[index]
        measured[str(name)] = CourseFactor(
            course_id=str(name),
            finishes=int(counts[index]),
            editions=len(editions_per_course.get(index, ())),
            factor=float(np.expm1(course_effect[index])),
            low=float(np.expm1(low)),
            high=float(np.expm1(high)),
        )
    return Fit(
        courses=measured,
        editions={
            str(name): float(np.expm1(edition_effect[i]))
            for i, name in enumerate(edition_names)
        },
    )


def _alternate(
    y: np.ndarray,
    runner: np.ndarray,
    group: np.ndarray,
    years: np.ndarray,
    *,
    groups: int | None = None,
) -> np.ndarray:
    """Runner effects and group effects, alternated until they settle.

    Each runner gets a level and a slope: their starting fitness and what a year of career
    costs them. Both are fitted groupwise with sums rather than a loop over runners, which
    is what makes thirty rounds over sixty thousand finishes take under a second.
    """
    people = int(runner.max()) + 1
    # ⚠️ The caller must say how many courses there are when this is used on a resample.
    # A bootstrap draw can miss a course entirely, and sizing the answer from the data in
    # hand then returns a shorter array for that draw, silently shifting every course after
    # the missing one by a place. That is the kind of error that produces a plausible table.
    groups = groups if groups is not None else int(group.max()) + 1
    effect = np.zeros(groups)
    n_runner = np.bincount(runner, minlength=people).astype(float)
    n_group = np.bincount(group, minlength=groups).astype(float)

    # Years measured from each runner's own first race, so the level is where they started.
    first = np.full(people, np.inf)
    np.minimum.at(first, runner, years)
    since = years - first[runner]

    sx = np.bincount(runner, weights=since, minlength=people)
    sxx = np.bincount(runner, weights=since**2, minlength=people)
    denominator = n_runner * sxx - sx**2
    usable = denominator > 1e-9
    safe = np.where(usable, denominator, 1.0)

    for _ in range(ROUNDS):
        residual = y - effect[group]
        sy = np.bincount(runner, weights=residual, minlength=people)
        sxy = np.bincount(runner, weights=since * residual, minlength=people)
        slope = np.where(usable, (n_runner * sxy - sx * sy) / safe, 0.0)
        slope = np.clip(slope, -MAX_TREND_PER_YEAR, MAX_TREND_PER_YEAR)
        level = (sy - slope * sx) / np.maximum(n_runner, 1)
        fitted = level[runner] + slope[runner] * since
        effect = np.bincount(group, weights=y - fitted, minlength=groups) / np.maximum(
            n_group, 1
        )
        # Centred on the finish-weighted mean, so "zero" is the average course somebody
        # actually runs rather than the average of the course list.
        effect -= np.average(effect, weights=n_group)
    return effect


def _bootstrap(
    y: np.ndarray,
    runner: np.ndarray,
    group: np.ndarray,
    years: np.ndarray,
    groups: int,
    seed: int,
    draws: int,
) -> list[tuple[float, float]]:
    """A 95 percent interval per course, resampling runners rather than finishes."""
    rng = np.random.default_rng(seed)
    people = int(runner.max()) + 1
    order = np.argsort(runner, kind="stable")
    starts = np.searchsorted(runner[order], np.arange(people + 1))

    sampled = np.full((draws, groups), np.nan)
    for draw in range(draws):
        chosen = rng.integers(0, people, size=people)
        take = np.concatenate([order[starts[c] : starts[c + 1]] for c in chosen])
        # Reindex the drawn runners so a person picked twice counts as two people; picking
        # the same person twice and calling them one would shrink the interval.
        sizes = starts[chosen + 1] - starts[chosen]
        relabelled = np.repeat(np.arange(chosen.size), sizes)
        effect = _alternate(y[take], relabelled, group[take], years[take], groups=groups)
        # A course nobody in this draw ran has no estimate in this draw. Left as NaN it is
        # dropped from that course's interval; recorded as zero it would be read as "this
        # course is exactly average", which is a claim the draw did not make.
        present = np.bincount(group[take], minlength=groups) > 0
        sampled[draw, present] = effect[present]

    intervals: list[tuple[float, float]] = []
    for g in range(groups):
        column = sampled[:, g]
        if np.all(np.isnan(column)):
            intervals.append((float("nan"), float("nan")))
            continue
        intervals.append(
            (float(np.nanpercentile(column, 2.5)), float(np.nanpercentile(column, 97.5)))
        )
    return intervals
