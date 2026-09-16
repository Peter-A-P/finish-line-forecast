"""How often the intervals held, per stratum, with an interval on that too.

⚠️ **Raw and conformal coverage are compared on the same runners.** The first races of the
backtest have no calibration pool yet, so their rows have a raw interval and no adjusted one.
Comparing the model's raw coverage over every row with the conformal coverage over the later
rows would compare two different sets of races, and the difference would partly be the
calendar. Both columns here are computed over the rows that were adjusted, and the rows that
could not be are counted in their own column.

⚠️ **The interval on a coverage rate resamples races, not runners.** Runners in one race share
its morning, so when a race runs hot every interval in it misses together. Resampling runners
treats four thousand Tely finishers as four thousand independent checks of the interval, and
gives a band too narrow to mean anything. The race is the unit that is independent, so the
bootstrap draws races.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from finishline.backtest.score import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    CONFIDENCE,
    STRATA,
    stratum_of,
)
from finishline.conformal.split import Interval


@dataclass(frozen=True, slots=True)
class Coverage:
    """One stratum's coverage at one level, before and after conformal adjustment."""

    stratum: str
    level: float
    rows: int
    unadjusted: int
    races: int
    raw: float | None
    raw_low: float | None
    raw_high: float | None
    conformal: float | None
    conformal_low: float | None
    conformal_high: float | None
    raw_width: float | None
    conformal_width: float | None


def by_race_bootstrap(
    hits: Sequence[bool], races: Sequence[str], *, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float, float]:
    """A rate with a percentile interval from resampling whole races."""
    values = np.asarray(hits, dtype=float)
    labels = np.asarray(races)
    unique, inverse = np.unique(labels, return_inverse=True)
    totals = np.bincount(inverse, weights=values, minlength=unique.size)
    counts = np.bincount(inverse, minlength=unique.size).astype(float)
    point = float(totals.sum() / counts.sum())
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, unique.size, size=(BOOTSTRAP_DRAWS, unique.size))
    rates = totals[picks].sum(axis=1) / counts[picks].sum(axis=1)
    tail = (1.0 - CONFIDENCE) / 2.0
    low, high = np.quantile(rates, [tail, 1.0 - tail])
    return point, float(low), float(high)


def summarise(intervals: Sequence[Interval], level: float) -> list[Coverage]:
    """Coverage per history-depth stratum at this level."""
    summaries: list[Coverage] = []
    for label, _low, _high in STRATA:
        mine = [
            interval
            for interval in intervals
            if interval.level == level and stratum_of(interval.row.depth) == label
        ]
        adjusted = [interval for interval in mine if interval.adjusted]
        if not adjusted:
            summaries.append(
                Coverage(label, level, len(mine), len(mine), 0, *([None] * 8))
            )
            continue
        races = [interval.row.race_id for interval in adjusted]
        raw, raw_low, raw_high = by_race_bootstrap(
            [interval.raw_covered for interval in adjusted], races
        )
        hit, hit_low, hit_high = by_race_bootstrap(
            [bool(interval.covered) for interval in adjusted], races
        )
        summaries.append(
            Coverage(
                stratum=label,
                level=level,
                rows=len(mine),
                unadjusted=len(mine) - len(adjusted),
                races=len(set(races)),
                raw=raw,
                raw_low=raw_low,
                raw_high=raw_high,
                conformal=hit,
                conformal_low=hit_low,
                conformal_high=hit_high,
                raw_width=float(
                    np.median([interval.raw_high - interval.raw_low for interval in adjusted])
                ),
                conformal_width=float(
                    np.median(
                        [
                            (interval.high or 0.0) - (interval.low or 0.0)
                            for interval in adjusted
                        ]
                    )
                ),
            )
        )
    return summaries
