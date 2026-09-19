"""The challenger's features: only what was known the day before, and nothing invented."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

from finishline.conformal.split import QUANTILES
from finishline.models import courses, gbm
from finishline.schema import Race, Result

TARGET = Race("t", "Target", date(2025, 10, 5), 10_000.0, "tt-10000", "x")


def finish(race_id: str, seconds: float, band: str | None = "40-49") -> Result:
    return Result(race_id, 1, 1, "x", None, "F", 1, band, 1, None, seconds, None)


def race(race_id: str, when: date, metres: float = 10_000.0) -> Race:
    return Race(race_id, race_id, when, metres, f"c-{int(metres)}", "x")


def column(row: list[float], name: str) -> float:
    return row[gbm.FEATURES.index(name)]


def test_a_row_sees_nothing_from_the_race_day_or_after() -> None:
    before = (race("a", date(2025, 6, 1)), finish("a", 2400.0))
    same_day = (race("b", TARGET.date), finish("b", 1800.0))
    later = (race("c", date(2025, 11, 1)), finish("c", 1700.0))
    row = gbm.features([before, same_day, later], TARGET, "F", None, None)
    assert column(row, "results") == 1.0, "a same-morning race is not history"
    assert column(row, "last") == pytest.approx(gbm.log_ratio(before[0], 2400.0))
    assert column(row, "days_since") == (TARGET.date - date(2025, 6, 1)).days


def test_a_first_timer_has_no_form_rather_than_an_invented_one() -> None:
    row = gbm.features([], TARGET, "M", 0.05, None)
    for name in ("last", "best_recent", "mean_last3", "trend_per_year", "days_since", "age"):
        assert math.isnan(column(row, name)), name
    assert column(row, "results") == 0.0
    assert column(row, "sex_female") == 0.0
    assert column(row, "course") == pytest.approx(math.log1p(0.05))
    assert math.isnan(column(row, "temp_c")), "no morning on file is missing, not neutral"
    assert len(row) == len(gbm.FEATURES)


def test_best_recent_looks_back_eighteen_months_only() -> None:
    old_fast = (race("a", date(2022, 5, 1)), finish("a", 1900.0))
    recent_slow = (race("b", date(2025, 5, 1)), finish("b", 2600.0))
    row = gbm.features([old_fast, recent_slow], TARGET, "F", None, None)
    assert column(row, "best_recent") == pytest.approx(gbm.log_ratio(recent_slow[0], 2600.0))


def test_the_age_is_carried_forward_from_the_last_printed_band() -> None:
    printed = (race("a", date(2023, 10, 5)), finish("a", 2400.0, band="40-49"))
    unprinted = (race("b", date(2025, 6, 1)), finish("b", 2400.0, band=None))
    row = gbm.features([printed, unprinted], TARGET, "F", None, None)
    assert column(row, "age") == pytest.approx(44.5 + 2.0, abs=0.01)


def test_crossed_quantiles_come_back_in_order() -> None:
    class Constant:
        def __init__(self, value: float) -> None:
            self.value = value

        def predict(self, matrix: np.ndarray) -> np.ndarray:
            return np.full(len(matrix), self.value)

    shuffled = [0.1, -0.1, 0.0, 0.05, -0.05, 0.2, -0.2]
    fitted = gbm.Fitted(
        boosters=tuple(Constant(value) for value in shuffled),
        course_fit=courses.Fit(courses={}, editions={}),
        rows=0,
    )
    quantiles = fitted.quantiles([0.0] * len(gbm.FEATURES), TARGET)
    assert len(quantiles) == len(QUANTILES)
    assert list(quantiles) == sorted(quantiles)
    assert quantiles[QUANTILES.index(0.50)] == pytest.approx(gbm.reference(10_000.0))


def test_felt_heat_is_the_hinge_the_model_charges_for() -> None:
    warm = (1.0, 18.0, 0.5, 0.0, 0.0, 0.0)  # observed, 18 C, half sun
    cool = (1.0, 8.0, 1.0, 0.0, 0.0, 0.0)
    row = gbm.features([], TARGET, "F", None, warm)
    assert column(row, "felt_heat") == pytest.approx(18.0 + 0.5 * gbm.SUN_DEGREES - 12.0)
    assert column(row, "felt_heat_x_log_distance") == pytest.approx(
        column(row, "felt_heat") * math.log(TARGET.distance_m / 5_000.0)
    )
    assert gbm.features([], TARGET, "F", None, cool)[gbm.FEATURES.index("felt_heat")] == 0.0
    assert math.isnan(column(gbm.features([], TARGET, "F", None, None), "felt_heat"))


def test_the_best_at_this_distance_ignores_other_distances() -> None:
    fast_5k = (race("a", date(2025, 5, 1), 5_000.0), finish("a", 1080.0))
    slower_10k = (race("b", date(2025, 6, 1)), finish("b", 2400.0))
    row = gbm.features([fast_5k, slower_10k], TARGET, "F", None, None)
    assert column(row, "best_at_distance") == pytest.approx(gbm.log_ratio(slower_10k[0], 2400.0))
    assert column(row, "best_ever") == pytest.approx(
        min(gbm.log_ratio(fast_5k[0], 1080.0), gbm.log_ratio(slower_10k[0], 2400.0))
    )
    assert column(row, "distinct_courses") == 2.0
