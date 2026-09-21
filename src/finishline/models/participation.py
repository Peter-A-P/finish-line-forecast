"""Who will run a race that publishes no start list (PLAN.md 5.6, field-forecast mode).

Run to Remember publishes no entrant list, so the field has to be forecast before a single
time is. Every runner with a finish in the eighteen months before the race is a candidate;
a logistic regression on what the archive already says about them gives each one a
probability of finishing this race. The prediction file carries the most likely of them,
as many as the model expects to finish times a scale (`choose_scale`) set on 2022 and 2023
where the two coverage numbers below are level, never on the races it is scored on.

WHAT IT CAN AND CANNOT SEE
--------------------------
It sees only resolved runners with recent results. A runner with no finish in the window,
a first-timer, and anyone the resolver would not commit to are all invisible to it, and
they are part of every real field. So two numbers travel with the prediction, both measured
on the backtest (`coverage`):

- **recall**, the share of finishers it could have named (a finish in the window) that it
  did name;
- **precision**, the share of the runners it named who then finished.

And a third that is not the model's to improve: the share of the whole field that had no
recent result at all, which is what a start list would have added.

⚠️ **The candidate cut is the same eighteen months as `history.RECENT`.** A runner whose
last finish is older than that is not a candidate, even if they ran this race three years
ago; the backtest measures how many finishers that loses, and it is counted in recall's
denominator only if they had a finish in the window, which is the population the model is
asked about.

⚠️ **Features are computed from results strictly before the race's date**, from the same
`History` the model fits on. Training rows are every earlier race, each seen from its own
day, so a training row never knows its own race's field.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from finishline.history import RECENT, History
from finishline.identity.resolve import Runner
from finishline.schema import Race

# Candidates: a finish inside this window before the race. The same window as recent form.
WINDOW_DAYS = RECENT.days

# Training rows start here: before it the archive is too thin for "ran last year" to mean
# anything, because many courses have no earlier edition on file.
FIRST_TRAINING_YEAR = 2011

# The ridge on every coefficient but the intercept. Small: a million rows and a dozen
# features need no shrinkage to be stable, only a guard against a feature that is constant
# in a short training window.
RIDGE = 1.0

FEATURES: tuple[str, ...] = (
    "intercept",
    "ran_last_edition",  # finished the most recent earlier running of this course
    "course_finishes",  # log1p of earlier finishes on this course
    "course_share",  # of this course's editions since their first result, the share run
    "recent_60d",  # log1p of finishes in the last two months
    "recent_183d",  # log1p of finishes in the last six months
    "this_year",  # log1p of finishes this calendar year: the series proxy
    "same_season_last_year",  # a finish within 30 days of this date a year earlier
    "finishes",  # log1p of all earlier finishes
    "distance_gap",  # |log(this distance / their median distance)|
    "days_since_last",  # log of days since their last finish
    "last_field",  # log1p of finishers at the last running of this course
    "pool",  # log of how many candidates this race has
    "no_edition",  # this course has no earlier running on file
    "crowd",  # how much of their recent races' fields ran this course last time
)


@dataclass(frozen=True, slots=True)
class _Timeline:
    """One runner's finishes, as sorted arrays to bisect."""

    days: list[int]
    order: list[str]
    race_ids: frozenset[str]
    by_course: dict[str, list[int]]
    distances: list[float]


@dataclass(frozen=True, slots=True)
class Rows:
    """Candidate rows for one or more races."""

    x: np.ndarray  # (rows, features)
    finished: np.ndarray  # (rows,) 1 if the candidate finished the race
    race_ids: list[str]  # per row
    runner_ids: list[str]  # per row


def _timelines(history: History) -> dict[str, _Timeline]:
    lines: dict[str, _Timeline] = {}
    for runner_id, runner in history.runners.items():
        finishes = sorted(
            (history.races[result.race_id].date.toordinal(), result.race_id)
            for result in runner.results
            if result.finished and result.race_id in history.races
        )
        if not finishes:
            continue
        by_course: dict[str, list[int]] = defaultdict(list)
        for day, race_id in finishes:
            by_course[history.races[race_id].course_id].append(day)
        lines[runner_id] = _Timeline(
            days=[day for day, _ in finishes],
            order=[race_id for _, race_id in finishes],
            race_ids=frozenset(race_id for _, race_id in finishes),
            by_course=dict(by_course),
            distances=[history.races[race_id].distance_m for _, race_id in finishes],
        )
    return lines


class _Archive:
    """What every candidate row is computed from: timelines, editions and field sizes."""

    def __init__(self, history: History) -> None:
        self.history = history
        self.lines = _timelines(history)
        fields: dict[str, set[str]] = defaultdict(set)
        for runner_id, line in self.lines.items():
            for race_id in line.order:
                fields[race_id].add(runner_id)
        self.fields = dict(fields)
        self.field = {race_id: len(people) for race_id, people in fields.items()}
        editions: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for race in history.races.values():
            editions[race.course_id].append((race.date.toordinal(), race.race_id))
        self.editions = {course: sorted(items) for course, items in editions.items()}
        # Every finish as (day, runner), sorted, to find a window's candidates by bisection.
        self.finishes = sorted(
            (day, runner_id) for runner_id, line in self.lines.items() for day in line.days
        )
        self.finish_days = [day for day, _ in self.finishes]

    def candidates(self, when: date) -> list[str]:
        """Runners with a finish in the window before `when`, strictly before it."""
        end = when.toordinal()
        low = bisect.bisect_left(self.finish_days, end - WINDOW_DAYS)
        high = bisect.bisect_left(self.finish_days, end)
        return sorted({runner_id for _, runner_id in self.finishes[low:high]})

    def rows(self, target: Race) -> tuple[list[str], np.ndarray]:
        """Every candidate for `target` and their features, from results before its date."""
        day = target.date.toordinal()
        people = self.candidates(target.date)
        editions = self.editions.get(target.course_id, [])
        earlier = editions[: bisect.bisect_left(editions, (day, ""))]
        last = earlier[-1][1] if earlier else None
        edition_days = [edition_day for edition_day, _ in earlier]
        last_field = math.log1p(self.field.get(last, 0)) if last else 0.0
        pool = math.log(max(len(people), 1))
        try:
            a_year_ago = target.date.replace(year=target.date.year - 1).toordinal()
        except ValueError:  # 29 February
            a_year_ago = (target.date - timedelta(days=365)).toordinal()
        year_start = date(target.date.year, 1, 1).toordinal()
        # For each race in the window, the share of its field that ran this course last time:
        # a small club race shares most of its crowd with another, the Tely shares little.
        regulars = self.fields.get(last, set()) if last else set()
        share: dict[str, float] = {}

        def crowd_of(race_id: str) -> float:
            if race_id not in share:
                field = self.fields.get(race_id, set())
                share[race_id] = len(field & regulars) / len(field) if field else 0.0
            return share[race_id]

        x = np.empty((len(people), len(FEATURES)))
        for row, runner_id in enumerate(people):
            line = self.lines[runner_id]
            k = bisect.bisect_left(line.days, day)
            days = line.days[:k]
            window = line.order[bisect.bisect_left(days, day - WINDOW_DAYS) : k]
            crowd = max((crowd_of(race_id) for race_id in window), default=0.0)
            on_course = bisect.bisect_left(line.by_course.get(target.course_id, []), day)
            since_first = len(edition_days) - bisect.bisect_left(edition_days, days[0])
            season = bisect.bisect_left(days, a_year_ago - 30) < bisect.bisect_right(
                days, a_year_ago + 30
            )
            x[row] = (
                1.0,
                1.0 if last is not None and last in line.race_ids else 0.0,
                math.log1p(on_course),
                on_course / since_first if since_first else 0.0,
                math.log1p(k - bisect.bisect_left(days, day - 61)),
                math.log1p(k - bisect.bisect_left(days, day - 183)),
                math.log1p(k - bisect.bisect_left(days, year_start)),
                1.0 if season else 0.0,
                math.log1p(k),
                abs(math.log(target.distance_m / float(np.median(line.distances[:k])))),
                math.log(day - days[-1]),
                last_field,
                pool,
                0.0 if last else 1.0,
                crowd,
            )
        return people, x


def training_rows(history: History, first_year: int = FIRST_TRAINING_YEAR) -> Rows:
    """One row per candidate per earlier race, each race seen from its own day."""
    archive = _Archive(history)
    blocks: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    race_ids: list[str] = []
    runner_ids: list[str] = []
    for race in sorted(history.races.values(), key=lambda race: (race.date, race.race_id)):
        if race.date.year < first_year:
            continue
        people, x = archive.rows(race)
        if not people:
            continue
        blocks.append(x)
        labels.append(
            np.array([race.race_id in archive.lines[person].race_ids for person in people], float)
        )
        race_ids += [race.race_id] * len(people)
        runner_ids += people
    if not blocks:
        return Rows(np.empty((0, len(FEATURES))), np.empty(0), [], [])
    return Rows(np.vstack(blocks), np.concatenate(labels), race_ids, runner_ids)


def fit_logistic(x: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    """Ridge-penalised logistic regression by Newton's method; the intercept is not shrunk."""
    beta = np.zeros(x.shape[1])
    penalty = ridge * np.eye(x.shape[1])
    penalty[0, 0] = 0.0
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-(x @ beta)))
        weight = p * (1.0 - p)
        hessian = x.T @ (x * weight[:, None]) + penalty
        gradient = x.T @ (y - p) - penalty @ beta
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if float(np.abs(step).max()) < 1e-8:
            break
    return beta


@dataclass(frozen=True, slots=True)
class Model:
    """A fitted participation model: the coefficients and what they were fitted on."""

    beta: np.ndarray
    rows: int
    races: int

    def probability(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(1.0 / (1.0 + np.exp(-(x @ self.beta))))


def fit(history: History) -> Model | None:
    """The model on every race in `history`, or None when there is nothing to learn from."""
    rows = training_rows(history)
    if rows.x.shape[0] == 0 or rows.finished.sum() == 0:
        return None
    return Model(fit_logistic(rows.x, rows.finished), rows.x.shape[0], len(set(rows.race_ids)))


@dataclass(frozen=True, slots=True)
class Forecast:
    """The field a race is expected to have, among runners the archive can name."""

    runner_ids: list[str]
    probabilities: np.ndarray

    @property
    def expected(self) -> float:
        """How many of the candidates are expected to finish: the sum of their probabilities."""
        return float(self.probabilities.sum())

    def named(self, scale: float) -> list[tuple[str, float]]:
        """The most likely `size(scale)` candidates, most likely first, ties by id."""
        ranked = sorted(
            zip(self.runner_ids, (float(p) for p in self.probabilities), strict=True),
            key=lambda item: (-item[1], item[0]),
        )
        return ranked[: size(self.probabilities, scale)]


def size(probabilities: np.ndarray, scale: float) -> int:
    """How many runners to name: the expected number of finishers, times `scale`."""
    return min(len(probabilities), round(scale * float(probabilities.sum())))


def forecast(model: Model, history: History, target: Race) -> Forecast:
    """Every candidate's probability of finishing `target`, from `history` alone."""
    people, x = _Archive(history).rows(target)
    probabilities = model.probability(x) if people else np.empty(0)
    return Forecast(people, probabilities)


# ---------------------------------------------------------------------------------------
# The backtest: the scale on 2022 and 2023, the coverage numbers on 2024 and after.
# ---------------------------------------------------------------------------------------

TUNING_YEARS = (2022, 2023)
SCORED_FROM = 2024
# Name this many times the expected number of finishers. 1.0 is a field of the size the
# model expects; the tuning years choose where recall and precision are level.
SCALES: tuple[float, ...] = tuple(round(0.1 * step, 1) for step in range(5, 16))


@dataclass(frozen=True, slots=True)
class Scored:
    """One race's candidates, as predicted by a model fitted before its year."""

    race_id: str
    year: int
    probabilities: np.ndarray
    finished: np.ndarray
    finishers: int  # everyone who finished, including runners the model could not see


def backtest(
    races: dict[str, Race], runners: Sequence[Runner], first_year: int = TUNING_YEARS[0]
) -> list[Scored]:
    """Each race from `first_year`, predicted by a model fitted on everything before its year.

    One fit per year rather than per race: the model has fifteen coefficients learned from
    hundreds of thousands of rows, and a few more months of rows moves them in the third
    decimal. The features themselves are always computed from each race's own day.
    """
    resolved = [runner for runner in runners if not runner.ambiguous]
    finishers: dict[str, int] = defaultdict(int)
    for runner in runners:
        for result in runner.results:
            if result.finished:
                finishers[result.race_id] += 1
    years = sorted({race.date.year for race in races.values() if race.date.year >= first_year})
    scored: list[Scored] = []
    for year in years:
        model = fit(History.before(date(year, 1, 1), races, resolved))
        if model is None:
            continue
        in_year = sorted(
            (race for race in races.values() if race.date.year == year),
            key=lambda race: (race.date, race.race_id),
        )
        for race in in_year:
            ids, x = _Archive(History.before(race.date, races, resolved)).rows(race)
            if not ids:
                continue
            ran = _finishers_of(race.race_id, resolved)
            scored.append(
                Scored(
                    race_id=race.race_id,
                    year=year,
                    probabilities=model.probability(x),
                    finished=np.array([runner_id in ran for runner_id in ids], dtype=float),
                    finishers=finishers.get(race.race_id, 0),
                )
            )
    return scored


def _finishers_of(race_id: str, runners: Iterable[Runner]) -> set[str]:
    return {
        runner.runner_id
        for runner in runners
        if any(result.race_id == race_id and result.finished for result in runner.results)
    }


Interval = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Coverage:
    """The coverage numbers at one scale, each a mean over races with a 95% interval.

    Means over races, not pooled over runners: pooled, the Tely is half of every number,
    and the question a reader of one race's file is asking is about one race.
    """

    scale: float
    recall: Interval  # of finishers with a finish in the window, the share named
    precision: Interval  # of the runners named, the share who finished
    visible: Interval  # of everyone who finished, the share with a finish in the window
    races: int
    named: int
    finished_named: int
    finishers_visible: int
    finishers: int

    def as_record(self) -> dict[str, object]:
        def rounded(value: Interval) -> list[float]:
            return [round(part, 3) for part in value]

        return {
            "scale": self.scale,
            "recall": rounded(self.recall),
            "precision": rounded(self.precision),
            "visible": rounded(self.visible),
            "races": self.races,
            "named": self.named,
            "finished_named": self.finished_named,
            "finishers_visible": self.finishers_visible,
            "finishers": self.finishers,
        }


def coverage(
    scored: Sequence[Scored], scale: float, *, seed: int = 20261111, draws: int = 2000
) -> Coverage:
    """Recall, precision and the visible share at a scale, races resampled for the interval."""
    usable = [item for item in scored if item.finished.sum() > 0 and item.finishers > 0]
    if not usable:
        raise ValueError("no race with a finisher the model could see")
    named = np.array([float(size(item.probabilities, scale)) for item in usable])
    hits = np.array(
        [
            float(item.finished[np.argsort(-item.probabilities, kind="stable")[: int(k)]].sum())
            for item, k in zip(usable, named, strict=True)
        ]
    )
    visible = np.array([float(item.finished.sum()) for item in usable])
    everyone = np.array([float(item.finishers) for item in usable])
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(usable), size=(draws, len(usable)))

    def mean(values: np.ndarray) -> Interval:
        low, high = np.quantile(values[picks].mean(axis=1), [0.025, 0.975])
        return float(values.mean()), float(low), float(high)

    return Coverage(
        scale=scale,
        recall=mean(hits / visible),
        precision=mean(np.divide(hits, named, out=np.zeros_like(hits), where=named > 0)),
        visible=mean(visible / everyone),
        races=len(usable),
        named=int(named.sum()),
        finished_named=int(hits.sum()),
        finishers_visible=int(visible.sum()),
        finishers=int(everyone.sum()),
    )


def choose_scale(scored: Sequence[Scored]) -> float:
    """The scale at which recall and precision are level on the tuning years.

    That is the plan's "balance the two coverage numbers" (PLAN.md 5.6): a field named about
    as often wrongly as it misses, rather than padded to catch everyone or cut to be sure.
    """
    window = [item for item in scored if item.year in TUNING_YEARS]
    if not window:
        raise ValueError("no race in the tuning years")
    gaps: dict[float, float] = {}
    for scale in SCALES:
        measured = coverage(window, scale, draws=1)
        gaps[scale] = abs(measured.recall[0] - measured.precision[0])
    return min(gaps, key=lambda scale: (gaps[scale], scale))
