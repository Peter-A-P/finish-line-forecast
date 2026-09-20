"""How hard each course is, measured from the results rather than from a map.

Runners cross between courses, so a course's difficulty is identifiable from finishes
alone: somebody who is slower on Cape to Cabot than their own equal-VDOT expectation every
year, and faster on Mews Memorial every year, is telling us what the hills cost without any
elevation data being involved.

The fit is two-way: a per-runner effect and a per-edition effect, alternated until they
settle. It is the same structure as the hierarchical model's `alpha_i` and `delta_r`
(PLAN.md 5.3) without the shrinkage, and its job here is to say what those effects look
like before a prior is put on them.

⚠️ **A course factor is only comparable with other courses of the same length.** The
outcome is scored against Daniels' time for VDOT 50 *at that distance*, and a runner effect
is one level for a whole career, so anything the population does differently from Daniels'
fade over distance has nowhere to go but the course effects of the long courses. It shows:
all five marathons on the archive measure between +4.5 and +11.2 percent, which would make
every marathon in the province as hilly as Signal Hill, and the Tely 10 measures +0.2
percent although it is a net-downhill course that the only other 10 mile course on record
is 4.3 points slower than. The two cannot be separated from finishes alone (every course is
run at one distance), so this module reports both numbers and neither is dressed up as the
other: `factor` against an equal-VDOT flat time, and `versus_peers` against the other
courses of the same length, which is the comparison that means what a reader thinks it
means. PLAN.md 13 item 36.

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

from collections.abc import Mapping, Sequence
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
    """One course's difficulty, as a fraction of an equal-VDOT flat time.

    `factor` carries whatever the population does differently from Daniels' fade at this
    distance; `versus_peers` is the same course against the other measured courses of the
    same length, where that departure has cancelled. Where a length has only one measured
    course (Cape to Cabot at 20 km, Run to Remember at 11 km, the ANE mile) there is nothing
    to compare with and `versus_peers` is None rather than zero.
    """

    course_id: str
    finishes: int
    editions: int
    distance_m: float
    factor: float
    low: float
    high: float
    peers: int = 0
    versus_peers: float | None = None
    peers_low: float | None = None
    peers_high: float | None = None

    @property
    def percent(self) -> float:
        return self.factor * 100

    @property
    def peers_percent(self) -> float | None:
        return None if self.versus_peers is None else self.versus_peers * 100


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

    sampled = _bootstrap(values, runner_ix, course_ix, years, course_names.size, seed, draws)
    lengths = {race.course_id: race.distance_m for race in races.values()}
    peers = _peers(course_names, lengths, counts)

    measured: dict[str, CourseFactor] = {}
    for index, name in enumerate(course_names):
        if counts[index] < MIN_FINISHES:
            continue
        low, high = _interval(sampled[:, index])
        mine = peers[index]
        against: float | None = None
        against_low: float | None = None
        against_high: float | None = None
        if mine:
            gap = course_effect[index] - float(np.mean(course_effect[list(mine)]))
            against = float(np.expm1(gap))
            drawn = _interval(_contrast(sampled, index, mine))
            against_low, against_high = float(np.expm1(drawn[0])), float(np.expm1(drawn[1]))
        measured[str(name)] = CourseFactor(
            course_id=str(name),
            finishes=int(counts[index]),
            editions=len(editions_per_course.get(index, ())),
            distance_m=float(lengths[str(name)]),
            factor=float(np.expm1(course_effect[index])),
            low=float(np.expm1(low)),
            high=float(np.expm1(high)),
            peers=len(mine),
            versus_peers=against,
            peers_low=against_low,
            peers_high=against_high,
        )
    return Fit(
        courses=measured,
        editions={
            str(name): float(np.expm1(edition_effect[i]))
            for i, name in enumerate(edition_names)
        },
    )


def _peers(
    course_names: np.ndarray, lengths: Mapping[str, float], counts: np.ndarray
) -> dict[int, tuple[int, ...]]:
    """For each measured course, the other measured courses run over the same distance.

    Grouped on the distance rounded to the metre: every length in the archive is a standard
    one, so two courses that group together really are the same race length. A course is
    never its own peer, and courses too thin to measure are not peers either, because a
    comparison against noise is not a comparison.
    """
    usable = [i for i in range(course_names.size) if counts[i] >= MIN_FINISHES]
    metres = {i: round(lengths[str(course_names[i])]) for i in usable}
    return {
        index: tuple(other for other in usable if other != index and metres[other] == metres[index])
        for index in usable
    }


def _interval(column: np.ndarray) -> tuple[float, float]:
    """A 95 percent interval over the draws that had an estimate at all."""
    if np.all(np.isnan(column)):
        return (float("nan"), float("nan"))
    return (float(np.nanpercentile(column, 2.5)), float(np.nanpercentile(column, 97.5)))


def _contrast(sampled: np.ndarray, index: int, peers: Sequence[int]) -> np.ndarray:
    """Per draw, this course against the mean of its peers in that same draw.

    The contrast is taken inside each draw rather than from the two intervals, because the
    course effects are centred together and move together: differencing the published
    intervals would report an uncertainty neither number has.
    """
    block = sampled[:, list(peers)]
    present = ~np.isnan(block)
    seen = present.sum(axis=1)
    total = np.where(present, block, 0.0).sum(axis=1)
    mean = np.where(seen > 0, total / np.maximum(seen, 1), np.nan)
    return sampled[:, index] - mean


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
) -> np.ndarray:
    """One refit per resample of the runners, as a (draws, courses) array of log effects.

    The draws come back rather than an interval, because two things are read off them: each
    course's own spread, and its gap to the courses of the same length, which only means
    anything if both sides come from the same draw.
    """
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
    return sampled
