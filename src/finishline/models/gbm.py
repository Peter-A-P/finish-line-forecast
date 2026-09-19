"""The challenger: gradient-boosted quantile trees on hand-built features (PLAN.md 5.4).

The question it answers is the one a sceptical reader asks of the hierarchical model: is a
Bayesian model worth its complexity, or would a standard machine-learning model on sensible
features do as well? LightGBM with pinball loss, one model per quantile, fitted once per
block of origins on the history before the block, exactly as the hierarchical model is, so
the two are compared on the same races with the same information.

WHAT IT SEES
------------
Every row is one finish, described only by what was known the day before it:

- the runner's form, as the log of each earlier finish over a VDOT-50 Daniels time at that
  distance (`metrics.daniels`), the same scale the hierarchical model works on: the latest,
  the best of the last eighteen months, the mean of the last three, and a fitted trend;
- how much history there is and how old it is: results, days since the last, years racing;
- who they are, as far as the pages say: sex, and an age from the latest printed age band
  carried forward to race day;
- the race: log distance over 10 km, the distance of the runner's last race against this
  one, the course's measured difficulty (`models.courses`, on the same history), the month;
- the morning: the six raw conditions the hierarchical model reads (`models.weather`),
  observed in the backtest as they are for that model.

The target is the log ratio of the finish over the same Daniels time, so a prediction is a
multiple of a reference time and every distance is on one scale. A runner with no history
has every form feature missing, which LightGBM handles natively, so the challenger answers
for first-timers from sex, age where known, course and morning, as the hierarchical model's
group prior does.

⚠️ **The course feature is fitted on the training rows' own races.** It is a course-level
constant from `models.courses` on the history before the block, so a training row's course
difficulty includes that row's own race among a course's many editions. That is mild target
leakage inside training only; a predicted race is never in the history its features come
from. Said here rather than discovered later.

⚠️ **Tuned on 2022 and 2023 only, never on the backtest.** Choosing features or parameters on
the 2024-onward races would make the backtest a validation set and flatter the challenger. The
search (`scratch/tune_gbm.py`) predicts the 2022 and 2023 races from history before each
half-year, exactly as the backtest does, and the 2024+ rows were run once afterwards with what
it chose. It bought about one percent: a random search over forty parameter sets gained 0.08
points of a finish time, and the second batch of features below another 0.02. What it refused
is worth as much as what it kept, and is in PLAN.md section 13 item 34: course-and-edition
normalised form features (worse), starting the trees from the runner's last result (worse),
linear-leaf trees (much worse), recency-weighted training rows (worse), training on recent
years only (worse), averaging several seeds (nothing).

⚠️ **Quantiles are fitted separately and can cross.** Each row's quantiles are sorted before
use, which is the standard repair and never widens an interval's claim.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from finishline.conformal.split import QUANTILES
from finishline.history import History
from finishline.identity.resolve import Runner, age_range
from finishline.metrics import daniels
from finishline.models import courses
from finishline.models.baselines import Prediction
from finishline.models.hierarchical import block_start
from finishline.schema import Race, Result

NAME = "lightgbm"
REFERENCE_VDOT = 50.0
RECENT_DAYS = 548  # eighteen months, as `History.recent`
# Training rows start here: before it, a runner's "first" result is only the archive's first.
FIRST_TRAINING_YEAR = 2010

FEATURES: tuple[str, ...] = (
    "last",
    "best_recent",
    "mean_last3",
    "trend_per_year",
    "results",
    "days_since",
    "years_racing",
    "sex_female",
    "age",
    "log_distance",
    "last_distance_ratio",
    "course",
    "month",
    "observed",
    "temp_c",
    "sun",
    "log_distance_5k",
    "wind",
    "tailwind",
    # The second batch, from the 2022-2023 search: the shapes the hierarchical model is told
    # about and trees would have to discover, and what a coach reads off a history.
    "felt_heat",
    "felt_heat_x_log_distance",
    "best_ever",
    "best_at_distance",
    "gap_to_best",
    "consistency",
    "distinct_courses",
    "improvement_12m",
    "races_per_year",
    "form_weighted",
)

# The half-life of the weighting in `form_weighted`: a result a year old counts half.
FORM_HALF_LIFE_DAYS = 365.0
# What a full sun is worth in felt degrees, as the hierarchical model estimates it (PLAN.md
# 13 item 30), used here only to give the trees the same shape rather than to fit anything.
SUN_DEGREES = 2.1

# Fixed before the first run (see the module docstring). Deterministic: one thread, a seed.
PARAMETERS: dict[str, Any] = {
    "objective": "quantile",
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 1.0,
    "lambda_l2": 1.0,
    "max_bin": 255,
    "seed": 20261018,
    # Deterministic and row-wise, so a rerun on the same data gives the same model whatever
    # the machine has spare; `deterministic` alone is not enough once threads vary.
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 4,
    "verbose": -1,
}
ROUNDS = 1200

Conditions = Mapping[str, tuple[float, ...]]


def reference(distance_m: float) -> float:
    """What a VDOT-50 runner would run at this distance, in seconds."""
    seconds = daniels.race_time(REFERENCE_VDOT, distance_m)
    if seconds is None:
        raise ValueError(f"no Daniels time at {distance_m} m")
    return seconds


def log_ratio(race: Race, seconds: float) -> float:
    return math.log(seconds / reference(race.distance_m))


def _age_on(prior: Sequence[tuple[Race, Result]], when: date) -> float:
    """The latest printed age band's middle, carried forward to `when`, or missing."""
    for race, result in reversed(prior):
        ages = age_range(result.age_band)
        if ages is not None:
            low, high = ages
            return (low + min(high, low + 10)) / 2.0 + (when - race.date).days / 365.25
    return math.nan


def features(
    prior: Sequence[tuple[Race, Result]],
    target: Race,
    sex: str | None,
    course_factor: float | None,
    conditions: tuple[float, ...] | None,
) -> list[float]:
    """One row, from finishes strictly before the target race, oldest first."""
    earlier = [
        (race, result)
        for race, result in prior
        if race.date < target.date and result.finished and result.seconds
    ]
    ratios = [log_ratio(race, float(result.seconds or 0.0)) for race, result in earlier]
    nan = math.nan
    last = ratios[-1] if ratios else nan
    recent = [
        value
        for (race, _result), value in zip(earlier, ratios, strict=True)
        if (target.date - race.date).days <= RECENT_DAYS
    ]
    trend = nan
    if len(ratios) >= 3:
        years = np.array([(race.date - earlier[0][0].date).days / 365.25 for race, _ in earlier])
        if years[-1] - years[0] >= 0.5:
            trend = float(np.polyfit(years, np.array(ratios), 1)[0])
    weather = conditions if conditions is not None else (nan,) * 6
    return [
        last,
        min(recent) if recent else nan,
        float(np.mean(ratios[-3:])) if ratios else nan,
        trend,
        float(len(ratios)),
        float((target.date - earlier[-1][0].date).days) if earlier else nan,
        (target.date - earlier[0][0].date).days / 365.25 if earlier else nan,
        {"F": 1.0, "M": 0.0}.get(sex or "", nan),
        _age_on(earlier, target.date),
        math.log(target.distance_m / 10_000.0),
        math.log(target.distance_m / earlier[-1][0].distance_m) if earlier else nan,
        nan if course_factor is None else math.log1p(course_factor),
        float(target.date.month),
        *(float(value) for value in weather),
        *_second_batch(earlier, ratios, target, conditions),
    ]


def _second_batch(
    earlier: Sequence[tuple[Race, Result]],
    ratios: Sequence[float],
    target: Race,
    conditions: tuple[float, ...] | None,
) -> list[float]:
    """The features the 2022-2023 search kept, in `FEATURES` order after the weather."""
    nan = math.nan
    # The felt heat the hierarchical model charges for, handed over as a number rather than
    # left for the trees to find in a threshold times an interaction.
    heat = nan
    if conditions is not None and conditions[0]:
        heat = max(0.0, conditions[1] + SUN_DEGREES * conditions[2] - 12.0)
    log_distance_5k = math.log(target.distance_m / 5_000.0)
    if not earlier:
        return [heat, heat * log_distance_5k, *([nan] * 8)]
    values = np.asarray(ratios, dtype=float)
    ages = np.asarray([(target.date - race.date).days for race, _ in earlier], dtype=float)
    at_distance = [
        value
        for (race, _result), value in zip(earlier, ratios, strict=True)
        if abs(math.log(target.distance_m / race.distance_m)) < 0.2
    ]
    last_year = values[ages <= 365]
    year_before = values[(ages > 365) & (ages <= 730)]
    span = max((float(ages.max()) - float(ages.min())) / 365.25, 0.5)
    return [
        heat,
        heat * log_distance_5k,
        float(values.min()),
        float(min(at_distance)) if at_distance else nan,
        float(values[-1] - values.min()),
        float(values.std()) if values.size >= 2 else nan,
        float(len({race.course_id for race, _ in earlier})),
        float(last_year.mean() - year_before.mean())
        if last_year.size and year_before.size
        else nan,
        float(values.size / span),
        float(np.average(values, weights=0.5 ** (ages / FORM_HALF_LIFE_DAYS))),
    ]


def _history_rows(runner: Runner, races: Mapping[str, Race]) -> list[tuple[Race, Result]]:
    rows = [(races[result.race_id], result) for result in runner.results if result.finished]
    return sorted(rows, key=lambda pair: pair[0].date)


def training_table(
    history: History, course_fit: courses.Fit, conditions: Conditions | None
) -> tuple[np.ndarray, np.ndarray]:
    """Every finish in the history since FIRST_TRAINING_YEAR, featured from what came before."""
    rows: list[list[float]] = []
    targets: list[float] = []
    for runner in history.runners.values():
        if runner.ambiguous:
            continue
        timeline = _history_rows(runner, history.races)
        for index, (race, result) in enumerate(timeline):
            if race.date.year < FIRST_TRAINING_YEAR or not result.seconds:
                continue
            factor = course_fit.prior_for(race.course_id)
            weather = conditions.get(race.race_id) if conditions else None
            rows.append(features(timeline[:index], race, runner.sex, factor, weather))
            targets.append(log_ratio(race, float(result.seconds)))
    return np.asarray(rows, dtype=float), np.asarray(targets, dtype=float)


@dataclass(frozen=True, slots=True)
class Fitted:
    """One block's quantile models and the course difficulties its features used."""

    boosters: tuple[Any, ...]
    course_fit: courses.Fit
    rows: int

    def quantiles(self, row: list[float], target: Race) -> tuple[float, ...]:
        matrix = np.asarray([row], dtype=float)
        logs = sorted(float(booster.predict(matrix)[0]) for booster in self.boosters)
        base = reference(target.distance_m)
        return tuple(base * math.exp(value) for value in logs)


def fit(history: History, conditions: Conditions | None) -> Fitted | None:
    """One LightGBM quantile model per quantile, on the history before a block."""
    import lightgbm as lgb

    course_fit = courses.fit(history, history.races, draws=1)
    x, y = training_table(history, course_fit, conditions)
    if y.size < 1000:
        return None
    data = lgb.Dataset(x, label=y, feature_name=list(FEATURES), free_raw_data=False)
    boosters = tuple(
        lgb.train({**PARAMETERS, "alpha": quantile}, data, num_boost_round=ROUNDS)
        for quantile in QUANTILES
    )
    return Fitted(boosters=boosters, course_fit=course_fit, rows=int(y.size))


class Challenger:
    """The challenger as the backtest sees it: one fit per block, like `Hierarchical`."""

    def __init__(self, *, months: int = 3, conditions: Conditions | None = None) -> None:
        self._months = months
        self._conditions = conditions
        self._block: date | None = None
        self._fitted: Fitted | None = None
        self.fits: list[tuple[date, int]] = []

    @property
    def name(self) -> str:
        return NAME

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        start = block_start(target.date, self._months)
        if start != self._block:
            self._block = start
            cut = History.before(start, history.races, list(history.runners.values()))
            self._fitted = fit(cut, self._conditions)
            self.fits.append((start, self._fitted.rows if self._fitted else 0))
        if self._fitted is None:
            return Prediction(runner.runner_id, None, "nothing before this block to fit")
        prior = _history_rows(runner, history.races)
        weather = self._conditions.get(target.race_id) if self._conditions else None
        row = features(
            prior, target, runner.sex, self._fitted.course_fit.prior_for(target.course_id),
            weather,
        )
        quantiles = self._fitted.quantiles(row, target)
        return Prediction(
            runner.runner_id,
            quantiles[QUANTILES.index(0.50)],
            f"LightGBM, history before {start.isoformat()}",
            quantiles=quantiles,
        )
