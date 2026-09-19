"""Turning predictions and finishes into the numbers the README publishes.

THREE RULES, AND THEY ARE ALL ABOUT HONESTY
-------------------------------------------
1. **Every reported number carries an interval.** A bare mean absolute error over four
   hundred runners looks like a fact and is an estimate. The interval here is a bootstrap
   over runners, seeded and committed, so a reader regenerates the same one.

2. **Coverage is reported beside error, never folded into it.** A model that answers for
   half the field and does well on the easy half is not better than one that answers for
   everybody. The tables carry both columns and the README puts them next to each other.

3. **Error is reported in minutes and as a percentage.** Ninety seconds is a rout in a
   5 km and a rounding error in a marathon, so an aggregate in seconds across distances
   says almost nothing. The percentage is the comparable one and the minutes are the one
   a runner feels, so both are printed and neither is called "the" error.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# The bootstrap. Seeded so the published interval regenerates exactly; 2,000 draws is
# past the point where the percentile bounds move in the second decimal.
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261018  # the date of the first race this project predicts
CONFIDENCE = 0.95

# History-depth strata. A prediction from one result and one from six are different
# claims and are never averaged together in a headline.
STRATA: tuple[tuple[str, int, int], ...] = (
    ("0", 0, 0),
    ("1", 1, 1),
    ("2 to 3", 2, 3),
    ("4 or more", 4, 10**6),
)


def stratum_of(depth: int) -> str:
    """Which history-depth stratum this runner falls in."""
    for label, low, high in STRATA:
        if low <= depth <= high:
            return label
    raise ValueError(f"no stratum for depth {depth}")


@dataclass(frozen=True, slots=True)
class Scored:
    """One runner's prediction and what they actually ran."""

    model: str
    race_id: str
    runner_id: str
    predicted: float | None
    actual: float
    depth: int
    quantiles: tuple[float, ...] = ()

    @property
    def error(self) -> float | None:
        """Predicted minus actual, in seconds. Positive means predicted too slow."""
        return None if self.predicted is None else self.predicted - self.actual


@dataclass(frozen=True, slots=True)
class Summary:
    """What one model did on one set of runners."""

    model: str
    runners: int
    answered: int
    mae_seconds: float | None
    mae_low: float | None
    mae_high: float | None
    mape: float | None
    bias_seconds: float | None

    @property
    def coverage(self) -> float:
        """The share of runners this model had anything to say about."""
        return self.answered / self.runners if self.runners else 0.0

    @property
    def mae_minutes(self) -> float | None:
        return None if self.mae_seconds is None else self.mae_seconds / 60.0


def bootstrap_mae(
    errors: Sequence[float], *, seed: int = BOOTSTRAP_SEED, draws: int = BOOTSTRAP_DRAWS
) -> tuple[float, float, float]:
    """Mean absolute error with a percentile bootstrap interval over runners.

    Resampling is over runners rather than over races, which is the weaker of the two
    assumptions available and is stated in the README: runners within one race share its
    weather and its course, so these intervals are narrower than a race-level resample
    would give. The race-level version arrives with the multi-race table, where there are
    enough races to resample.
    """
    if not errors:
        return (float("nan"), float("nan"), float("nan"))
    values = np.abs(np.asarray(errors, dtype=float))
    point = float(values.mean())
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(values), size=(draws, len(values)))
    means = values[picks].mean(axis=1)
    tail = (1.0 - CONFIDENCE) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return point, float(low), float(high)


def summarise(scored: Sequence[Scored], model: str) -> Summary:
    """One model's error over these runners, with its coverage beside it."""
    mine = [row for row in scored if row.model == model]
    answered = [row for row in mine if row.error is not None]
    if not answered:
        return Summary(model, len(mine), 0, None, None, None, None, None)

    errors = [row.error for row in answered if row.error is not None]
    point, low, high = bootstrap_mae(errors)
    percentages = [
        abs(row.error) / row.actual for row in answered if row.error is not None
    ]
    return Summary(
        model=model,
        runners=len(mine),
        answered=len(answered),
        mae_seconds=point,
        mae_low=low,
        mae_high=high,
        mape=float(statistics.mean(percentages)),
        bias_seconds=float(statistics.mean(errors)),
    )


def by_stratum(scored: Sequence[Scored], model: str) -> dict[str, Summary]:
    """One model's error per history-depth stratum."""
    return {
        label: summarise([row for row in scored if stratum_of(row.depth) == label], model)
        for label, _low, _high in STRATA
    }


def skill(model: Summary, baseline: Summary) -> float | None:
    """How much error this model removes relative to the baseline, as a fraction.

    Positive is better. Reported rather than a raw error because "MAE 4.2 minutes" is
    not a claim anyone can evaluate without knowing what the obvious approach scored.

    ⚠️ **Compared on the runners each answered for, which are not the same runners.**
    A model that answers only for the easy half of the field can post a fine skill
    number, so the coverage columns sit beside this one in every table and the README
    says to read them together.
    """
    if model.mae_seconds is None or not baseline.mae_seconds:
        return None
    return 1.0 - model.mae_seconds / baseline.mae_seconds


def place_error(scored: Sequence[Scored], model: str) -> tuple[float | None, float | None]:
    """Mean absolute place error and Spearman correlation, within one race.

    The race director's number. Places are computed among the runners this model
    answered for, so a model that skips half the field is ranked against the half it
    kept; the coverage column is what stops that reading as a win.
    """
    mine = [
        row for row in scored if row.model == model and row.predicted is not None
    ]
    if len(mine) < 2:
        return None, None
    predicted = np.asarray([row.predicted for row in mine], dtype=float)
    actual = np.asarray([row.actual for row in mine], dtype=float)
    predicted_rank = ranks(predicted)
    actual_rank = ranks(actual)
    gap = float(np.abs(predicted_rank - actual_rank).mean())
    correlation = float(np.corrcoef(predicted_rank, actual_rank)[0, 1])
    return gap, correlation


# A race contributes to the paired placing comparison only if the two models share at least
# this many runners in it: a Spearman over three runners is one of a handful of values and
# says nothing about a field.
PAIRED_PLACING_MINIMUM = 10


@dataclass(frozen=True, slots=True)
class PairedPlacing:
    """Two models ranked over the same runners in each race, averaged over races.

    Each interval resamples races, because the runners in one race share its morning.
    """

    model: str
    baseline: str
    races: int
    runners: int
    gap: float
    baseline_gap: float
    gap_difference: tuple[float, float, float]
    spearman: float
    baseline_spearman: float
    spearman_difference: tuple[float, float, float]


def paired_placing(
    scored: Sequence[Scored],
    model: str,
    baseline: str,
    *,
    minimum: int = PAIRED_PLACING_MINIMUM,
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_DRAWS,
) -> PairedPlacing | None:
    """Place error and Spearman for two models on the runners both answered for.

    `place_error` ranks each model among its own answered runners, so a model that answers
    for the whole field is ranked over newcomers a baseline never has to place, and the two
    numbers are not about the same race. Here both are ranked among the runners they share,
    race by race, and the difference is the paired one.
    """
    by_race: dict[str, dict[str, dict[str, Scored]]] = {}
    for row in scored:
        if row.predicted is None or row.model not in (model, baseline):
            continue
        by_race.setdefault(row.race_id, {}).setdefault(row.model, {})[row.runner_id] = row

    gaps: list[tuple[float, float]] = []
    correlations: list[tuple[float, float]] = []
    runners = 0
    for race_id in sorted(by_race):
        mine = by_race[race_id].get(model, {})
        theirs = by_race[race_id].get(baseline, {})
        shared = sorted(set(mine) & set(theirs))
        if len(shared) < minimum:
            continue
        actual = ranks(np.asarray([mine[r].actual for r in shared], dtype=float))
        pair = []
        for rows in (mine, theirs):
            predicted = ranks(np.asarray([rows[r].predicted for r in shared], dtype=float))
            pair.append(
                (
                    float(np.abs(predicted - actual).mean()),
                    float(np.corrcoef(predicted, actual)[0, 1]),
                )
            )
        gaps.append((pair[0][0], pair[1][0]))
        correlations.append((pair[0][1], pair[1][1]))
        runners += len(shared)
    if not gaps:
        return None

    gap_array = np.asarray(gaps)
    rho_array = np.asarray(correlations)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(gaps), size=(draws, len(gaps)))
    tail = (1.0 - CONFIDENCE) / 2.0

    def difference(values: np.ndarray) -> tuple[float, float, float]:
        diffs = values[:, 0] - values[:, 1]
        low, high = np.quantile(diffs[picks].mean(axis=1), [tail, 1.0 - tail])
        return float(diffs.mean()), float(low), float(high)

    return PairedPlacing(
        model=model,
        baseline=baseline,
        races=len(gaps),
        runners=runners,
        gap=float(gap_array[:, 0].mean()),
        baseline_gap=float(gap_array[:, 1].mean()),
        gap_difference=difference(gap_array),
        spearman=float(rho_array[:, 0].mean()),
        baseline_spearman=float(rho_array[:, 1].mean()),
        spearman_difference=difference(rho_array),
    )


def ranks(values: np.ndarray) -> np.ndarray:
    """Ranks from 1, ties averaged, which is what Spearman needs.

    Ties are real here: a chip-timed field has dozens of runners sharing a second, and
    breaking those ties by array order would invent a placing the race did not make.
    """
    order = values.argsort(kind="stable")
    positions = np.empty(len(values), dtype=float)
    positions[order] = np.arange(1, len(values) + 1, dtype=float)
    _unique, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    totals = np.zeros(len(counts), dtype=float)
    np.add.at(totals, inverse, positions)
    return (totals / counts)[inverse]


@dataclass(frozen=True, slots=True)
class PairedError:
    """Two models' errors on the same runners, and the difference with a race-level interval."""

    model: str
    other: str
    races: int
    runners: int
    model_mae_seconds: float
    other_mae_seconds: float
    # Mean absolute log error, model minus other, in percentage points of a finish time.
    difference: tuple[float, float, float]


def paired_error(
    scored: Sequence[Scored],
    model: str,
    other: str,
    *,
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_DRAWS,
) -> PairedError | None:
    """Two models on exactly the runners both answered for, resampling races.

    The comparison two overlapping MAE intervals cannot make: the same runner's two errors
    are strongly correlated, so a real, consistent gap can sit inside both marginal
    intervals. Here each runner is one pair, the difference is on the log scale (a percent
    of their own finish time, so a marathoner does not outweigh a 5 km runner), and the
    interval resamples whole races, because runners in one race share its morning.
    """
    by_key: dict[tuple[str, str], dict[str, Scored]] = {}
    for row in scored:
        if row.predicted is None or row.model not in (model, other):
            continue
        by_key.setdefault((row.race_id, row.runner_id), {})[row.model] = row
    per_race: dict[str, list[tuple[float, float, float]]] = {}
    for (race_id, _runner), pair in by_key.items():
        if len(pair) != 2:
            continue
        mine, theirs = pair[model], pair[other]
        actual = mine.actual
        per_race.setdefault(race_id, []).append(
            (
                abs(float(np.log(float(mine.predicted or 0.0) / actual)))
                - abs(float(np.log(float(theirs.predicted or 0.0) / actual))),
                abs(float(mine.predicted or 0.0) - actual),
                abs(float(theirs.predicted or 0.0) - actual),
            )
        )
    if not per_race:
        return None
    races = sorted(per_race)
    sums = np.asarray([[sum(v[i] for v in per_race[r]) for i in range(3)] for r in races])
    counts = np.asarray([len(per_race[r]) for r in races], dtype=float)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(races), size=(draws, len(races)))
    resampled = sums[picks, 0].sum(axis=1) / counts[picks].sum(axis=1)
    tail = (1.0 - CONFIDENCE) / 2.0
    low, high = np.quantile(resampled, [tail, 1.0 - tail])
    total = counts.sum()
    return PairedError(
        model=model,
        other=other,
        races=len(races),
        runners=int(total),
        model_mae_seconds=float(sums[:, 1].sum() / total),
        other_mae_seconds=float(sums[:, 2].sum() / total),
        difference=(
            float(sums[:, 0].sum() / total * 100),
            float(low * 100),
            float(high * 100),
        ),
    )
