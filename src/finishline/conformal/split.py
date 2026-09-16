"""Split conformal intervals, Mondrian by history depth, rolled forward through time.

WHAT THIS DOES
--------------
A model's own 80 percent interval is a claim. This checks the claim against races that have
already been run and moves the interval until it holds. For every past prediction it
computes a conformity score: how far outside the model's interval the finish fell, or how
far inside, as a negative number. The adjusted interval for a new race is the model's
interval stretched (or shrunk) by the finite-sample quantile of those scores. This is
conformalised quantile regression (Romano, Patterson and Candes, 2019), and its guarantee
is that the adjusted interval covers at the nominal rate on average, whatever the model got
wrong, provided the new race behaves like the old ones.

THREE CHOICES, AND WHY
----------------------
**The score is on the log scale.** A four-minute miss is a rout in a 5 km and noise in a
marathon, so a score in seconds would let the long races set everyone's width. On the log
scale a score of 0.05 means five percent of a finish time wherever it was run.

**Mondrian by history depth** (PLAN.md 2.6). A runner with six results and a runner with none
are not exchangeable: the model knows one of them and guesses the other. Pooled, the
calibration would be set by whichever stratum is largest and the others would over- or
under-cover in ways that cancel in the headline. Each stratum is calibrated on its own rows.

**Rolled forward, never backward.** Each race is calibrated only on races dated strictly
before it, the same rule the backtest applies to the models. Calibrating on the whole backtest
at once would use a race's own residuals, and later races', to set its interval: a coverage
number that could not have been achieved live.

⚠️ **The assumption, stated where the numbers are.** Coverage is guaranteed on average over
races within a stratum under exchangeability of scores across races. It is violated when the
field or the weather shifts in a way the calibration races did not see, and a Cape to Cabot
run in a gale is exactly that. The coverage table reports what happened, and this assumption
sits beside it in the README.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from finishline.backtest.score import Scored, stratum_of

# The quantile levels every model prediction carries, in order. Mirrors
# `models.hierarchical.QUANTILES`, restated here so this module does not import a model.
QUANTILES: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)

# Below this many scores in a stratum, the finite-sample quantile at 90 percent is the
# maximum or beyond it, and the interval is either unbounded or set by one bad day. Such a
# row is left unadjusted and counted, rather than published with a width nobody could trust.
MIN_CALIBRATION = 50


def bounds_for(level: float) -> tuple[int, int]:
    """Positions in `QUANTILES` of the lower and upper edge of a central interval."""
    low, high = round((1.0 - level) / 2.0, 4), round(1.0 - (1.0 - level) / 2.0, 4)
    rounded = [round(q, 4) for q in QUANTILES]
    if low not in rounded or high not in rounded:
        raise ValueError(f"no {level:.0%} interval in the quantiles carried: {QUANTILES}")
    return rounded.index(low), rounded.index(high)


def conformity(row: Scored, level: float) -> float | None:
    """How far outside its interval this finish fell, on the log scale; negative is inside."""
    if not row.quantiles or row.actual <= 0:
        return None
    lower, upper = bounds_for(level)
    low, high = row.quantiles[lower], row.quantiles[upper]
    if low <= 0 or high <= 0:
        return None
    actual = math.log(row.actual)
    return max(math.log(low) - actual, actual - math.log(high))


def threshold(scores: Sequence[float], level: float) -> float:
    """The finite-sample conformal quantile: the ceil((n + 1) level)-th smallest score.

    Infinite when there are too few scores for the level to be reachable, which is the honest
    answer: fifty scores cannot promise 99 percent.
    """
    n = len(scores)
    rank = math.ceil((n + 1) * level)
    if rank > n:
        return math.inf
    return float(np.sort(np.asarray(scores, dtype=float))[rank - 1])


@dataclass(frozen=True, slots=True)
class Interval:
    """One runner's interval before and after conformal adjustment."""

    row: Scored
    level: float
    raw_low: float
    raw_high: float
    low: float | None
    high: float | None
    calibration: int

    @property
    def adjusted(self) -> bool:
        return self.low is not None and self.high is not None

    @property
    def raw_covered(self) -> bool:
        return self.raw_low <= self.row.actual <= self.raw_high

    @property
    def covered(self) -> bool | None:
        if self.low is None or self.high is None:
            return None
        return self.low <= self.row.actual <= self.high


def shifts(
    rows: Sequence[Scored],
    race_dates: Mapping[str, date],
    level: float,
    before: date,
    *,
    stratum: Callable[[Scored], str] = lambda row: stratum_of(row.depth),
    min_calibration: int = MIN_CALIBRATION,
) -> dict[str, float | None]:
    """Each stratum's log-scale widening for a race on `before`, from every earlier race.

    What a live prediction uses: the same threshold `rolling` would apply to a race on that
    date, computed once per stratum. None where the stratum has too few earlier scores to be
    trusted, and the live interval is then the model's own, said so in the file.
    """
    pool: dict[str, list[float]] = {}
    for row in rows:
        if race_dates[row.race_id] >= before:
            continue
        score = conformity(row, level)
        if score is not None:
            pool.setdefault(stratum(row), []).append(score)
    return {
        label: (threshold(scores, level) if len(scores) >= min_calibration else None)
        for label, scores in pool.items()
    }


def widen(low: float, high: float, shift: float | None) -> tuple[float, float]:
    """An interval moved out (or in) by a log-scale shift; unchanged when there is none."""
    if shift is None:
        return low, high
    if not math.isfinite(shift):
        return 0.0, math.inf
    return low * math.exp(-shift), high * math.exp(shift)


def rolling(
    rows: Sequence[Scored],
    race_dates: Mapping[str, date],
    level: float,
    *,
    stratum: Callable[[Scored], str] = lambda row: stratum_of(row.depth),
    min_calibration: int = MIN_CALIBRATION,
) -> list[Interval]:
    """Every row's interval, each calibrated on its stratum's scores from earlier races only."""
    lower, upper = bounds_for(level)
    usable = [row for row in rows if row.quantiles]
    by_date: dict[date, list[Scored]] = {}
    for row in usable:
        by_date.setdefault(race_dates[row.race_id], []).append(row)

    pool: dict[str, list[float]] = {}
    intervals: list[Interval] = []
    for when in sorted(by_date):
        today = by_date[when]
        # Everything dated today is scored against yesterday's pool, then joins it. Two
        # races on one morning are not each other's calibration, for the reason they are not
        # each other's history.
        for row in today:
            scores = pool.get(stratum(row), [])
            raw_low, raw_high = row.quantiles[lower], row.quantiles[upper]
            if len(scores) < min_calibration:
                low = high = None
            else:
                shift = threshold(scores, level)
                low = raw_low * math.exp(-shift) if math.isfinite(shift) else 0.0
                high = raw_high * math.exp(shift) if math.isfinite(shift) else math.inf
            intervals.append(
                Interval(row, level, raw_low, raw_high, low, high, calibration=len(scores))
            )
        for row in today:
            score = conformity(row, level)
            if score is not None:
                pool.setdefault(stratum(row), []).append(score)
    return intervals
