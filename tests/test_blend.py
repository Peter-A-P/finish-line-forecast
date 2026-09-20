"""Blending two models: the arithmetic, and what it does to a saved backtest row."""

from __future__ import annotations

import math

import pytest

from finishline.backtest.score import Scored
from finishline.models import blend


def test_the_centre_is_the_weighted_geometric_mean() -> None:
    assert blend.centre(1000.0, 1000.0, 0.6) == pytest.approx(1000.0)
    assert blend.centre(1000.0, 1100.0, 0.0) == pytest.approx(1000.0)
    assert blend.centre(1000.0, 1100.0, 1.0) == pytest.approx(1100.0)
    assert blend.centre(1000.0, 1210.0, 0.5) == pytest.approx(1100.0), "geometric, not arithmetic"
    assert blend.factor(1000.0, 1210.0, 0.5) == pytest.approx(1.1)


def test_a_blended_row_carries_scaled_quantiles() -> None:
    quantiles = (900.0, 950.0, 1000.0, 1050.0, 1100.0, 1150.0, 1200.0)
    rows = [
        Scored("hierarchical", "r1", "a", 1050.0, 1020.0, 4, quantiles),
        Scored("lightgbm", "r1", "a", 1150.0, 1020.0, 4),
        Scored("hierarchical", "r1", "b", 1200.0, 1190.0, 1, quantiles),
    ]
    blended = blend.rows(rows, weight=0.5)
    assert [row.runner_id for row in blended] == ["a"], "a runner one model missed is dropped"
    (row,) = blended
    scale = math.sqrt(1150.0 / 1050.0)
    assert row.model == "blend"
    assert row.predicted == pytest.approx(1050.0 * scale)
    assert row.quantiles == pytest.approx(tuple(value * scale for value in quantiles))
    assert row.actual == 1020.0 and row.depth == 4


def test_a_model_with_nothing_to_say_blends_to_nothing() -> None:
    rows = [
        Scored("hierarchical", "r1", "a", None, 1020.0, 0),
        Scored("lightgbm", "r1", "a", 1150.0, 1020.0, 0),
    ]
    (row,) = blend.rows(rows)
    assert row.predicted is None and row.quantiles == ()


def test_factors_skip_a_runner_either_model_missed() -> None:
    factors = blend.factors({"a": 1000.0, "b": 1000.0}, {"a": 1210.0}, 0.5)
    assert set(factors) == {"a"} and factors["a"] == pytest.approx(1.1)
