"""The conformal layer: exact arithmetic, the time rule, and coverage on a fixture that needs it.

The fixture is the case the layer exists for. A model that thinks every runner is eight
percent uncertain, fed runners who are really three percent (a deep history) and twenty
percent (no history at all). Its raw intervals over-cover one stratum and badly under-cover
the other, and the headline average of the two looks almost fine. Mondrian conformal has to
put both strata at nominal separately, and give the uncertain runners the wider interval.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import NormalDist

import numpy as np
import pytest

from finishline import report
from finishline.backtest.score import Scored
from finishline.conformal import coverage, split


def scored(
    actual: float,
    quantiles: tuple[float, ...],
    *,
    race_id: str = "r",
    depth: int = 0,
    runner_id: str = "a",
) -> Scored:
    median = quantiles[3] if quantiles else actual
    return Scored("m", race_id, runner_id, median, actual, depth, quantiles)


FLAT = (90.0, 92.0, 96.0, 100.0, 104.0, 108.0, 110.0)


# --- arithmetic --------------------------------------------------------------------


def test_the_interval_edges_are_read_from_the_carried_quantiles() -> None:
    assert split.bounds_for(0.80) == (1, 5)
    assert split.bounds_for(0.90) == (0, 6)
    assert split.bounds_for(0.50) == (2, 4)
    with pytest.raises(ValueError, match="no 70% interval"):
        split.bounds_for(0.70)


def test_the_score_is_log_distance_outside_and_negative_inside() -> None:
    above = split.conformity(scored(120.0, FLAT), 0.80)
    inside = split.conformity(scored(100.0, FLAT), 0.80)
    assert above == pytest.approx(math.log(120.0 / 108.0))
    # Inside, the score is the distance to the nearer edge: 108 is closer to 100 than 92.
    assert inside == pytest.approx(-math.log(108.0 / 100.0))
    assert split.conformity(scored(100.0, ()), 0.80) is None


def test_the_threshold_is_the_finite_sample_rank() -> None:
    """ceil((n + 1) level): nine scores at 80 percent is the eighth smallest, not the 7.2th."""
    assert split.threshold([float(v) for v in range(9, 0, -1)], 0.80) == 8.0
    assert split.threshold([1.0, 2.0, 3.0], 0.90) == math.inf


# --- the time rule -----------------------------------------------------------------


def test_a_race_is_never_calibrated_on_itself_or_its_morning() -> None:
    dates = {"early": date(2024, 5, 1), "same-a": date(2024, 6, 1), "same-b": date(2024, 6, 1)}
    rows = [scored(100.0, FLAT, race_id="early", runner_id=f"e{i}") for i in range(3)]
    rows += [scored(100.0, FLAT, race_id="same-a", runner_id=f"a{i}") for i in range(2)]
    rows += [scored(100.0, FLAT, race_id="same-b", runner_id=f"b{i}") for i in range(4)]
    intervals = split.rolling(rows, dates, 0.80, min_calibration=1)
    pool = {interval.row.race_id: interval.calibration for interval in intervals}
    assert pool["early"] == 0
    assert pool["same-a"] == 3, "only the earlier race, not the other race that morning"
    assert pool["same-b"] == 3


def test_too_little_calibration_is_counted_rather_than_trusted() -> None:
    dates = {"one": date(2024, 5, 1), "two": date(2024, 6, 1)}
    rows = [scored(100.0, FLAT, race_id="one"), scored(100.0, FLAT, race_id="two")]
    intervals = split.rolling(rows, dates, 0.80)
    assert not any(interval.adjusted for interval in intervals)
    (_, _, deep, _) = coverage.summarise(intervals, 0.80)
    assert deep.stratum == "2 to 3"
    first = coverage.summarise(intervals, 0.80)[0]
    assert first.unadjusted == 2 and first.conformal is None


# --- coverage on a fixture that needs it -------------------------------------------


def heteroscedastic(races: int = 60, per_race: int = 200) -> tuple[list[Scored], dict[str, date]]:
    """Deep-history runners at 3 percent noise, newcomers at 20, a model that assumes 8."""
    rng = np.random.default_rng(20261018)
    assumed = 0.08
    z = {q: NormalDist().inv_cdf(q) for q in split.QUANTILES}
    rows: list[Scored] = []
    dates: dict[str, date] = {}
    for race in range(races):
        race_id = f"race{race:02d}"
        dates[race_id] = date(2024, 1, 1) + timedelta(days=7 * race)
        # A shared morning: every runner in a race is a little fast or slow together.
        morning = rng.normal(0.0, 0.01)
        for index in range(per_race):
            depth = 0 if index % 2 else 5
            truth = 0.20 if depth == 0 else 0.03
            predicted = 3000.0
            actual = predicted * math.exp(morning + rng.normal(0.0, truth))
            quantiles = tuple(predicted * math.exp(assumed * z[q]) for q in split.QUANTILES)
            rows.append(
                Scored("m", race_id, f"{race_id}-{index}", predicted, actual, depth, quantiles)
            )
    return rows, dates


@pytest.mark.parametrize("level", [0.80, 0.90])
def test_conformal_puts_each_stratum_at_nominal_separately(level: float) -> None:
    rows, dates = heteroscedastic()
    intervals = split.rolling(rows, dates, level)
    summaries = {s.stratum: s for s in coverage.summarise(intervals, level)}
    newcomers, deep = summaries["0"], summaries["4 or more"]

    assert newcomers.raw is not None and deep.raw is not None
    assert newcomers.raw < level - 0.25, "the fixture must under-cover newcomers to test anything"
    assert deep.raw > 0.98, "and over-cover the deep histories"

    for stratum in (newcomers, deep):
        assert stratum.conformal == pytest.approx(level, abs=0.02)
        assert stratum.conformal_low is not None and stratum.conformal_high is not None
        assert stratum.conformal_low <= level <= stratum.conformal_high

    assert newcomers.conformal_width is not None and deep.conformal_width is not None
    assert newcomers.conformal_width > 4 * deep.conformal_width


def test_pooling_the_strata_would_have_hidden_both_failures() -> None:
    """The reason for Mondrian: one pool gives a fine average and two wrong strata."""
    rows, dates = heteroscedastic()
    pooled = split.rolling(rows, dates, 0.80, stratum=lambda _row: "everyone")
    by_depth = {s.stratum: s for s in coverage.summarise(pooled, 0.80)}
    overall = np.mean([bool(i.covered) for i in pooled if i.adjusted])
    assert overall == pytest.approx(0.80, abs=0.02)
    assert by_depth["0"].conformal is not None and by_depth["4 or more"].conformal is not None
    assert by_depth["0"].conformal < 0.70
    assert by_depth["4 or more"].conformal > 0.95


def test_a_live_shift_is_the_one_rolling_would_have_used_that_day() -> None:
    """freeze and the backtest must widen a race on a given date by the same amount."""
    rows, dates = heteroscedastic(races=30, per_race=100)
    last = max(dates.values())
    live = split.shifts(rows, dates, 0.80, last)
    backtest = split.rolling(rows, dates, 0.80)
    on_the_day = [
        interval
        for interval in backtest
        if dates[interval.row.race_id] == last and interval.row.depth == 0 and interval.adjusted
    ]
    assert on_the_day
    sample = on_the_day[0]
    assert sample.low is not None
    expected_low, _ = split.widen(sample.raw_low, sample.raw_high, live["0"])
    assert sample.low == pytest.approx(expected_low)


def test_a_thin_stratum_has_no_live_shift() -> None:
    rows, dates = heteroscedastic(races=2, per_race=20)
    live = split.shifts(rows, dates, 0.80, max(dates.values()) + timedelta(days=1))
    assert live == {"0": None, "4 or more": None}
    assert split.widen(90.0, 110.0, None) == (90.0, 110.0)


def test_the_published_table_carries_the_assumption_beside_the_numbers() -> None:
    """CLAUDE.md: every coverage table has the conformal assumption beside it."""
    rows, dates = heteroscedastic(races=20, per_race=60)
    summaries = {
        level: coverage.summarise(split.rolling(rows, dates, level), level)
        for level in (0.80, 0.90)
    }
    table = report.coverage_table(summaries, "hierarchical")
    assert "exchangeability" in table
    assert "resamples races" in table
    assert "| 0 | 80% |" in table and "| 4 or more | 90% |" in table
    assert "no intervals to check yet" in report.coverage_table({}, None)


def test_the_coverage_interval_resamples_races_not_runners() -> None:
    """A race where every interval misses together is one bad race, not a thousand."""
    hits = [True] * 1000 + [False] * 1000
    one_race_each = [f"r{i}" for i in range(2000)]
    two_races = ["good"] * 1000 + ["bad"] * 1000
    _, narrow_low, narrow_high = coverage.by_race_bootstrap(hits, one_race_each)
    _, wide_low, wide_high = coverage.by_race_bootstrap(hits, two_races)
    assert wide_high - wide_low > 10 * (narrow_high - narrow_low)
