"""The published curves, pinned to their source and to each other.

The reference values are transcribed from the Daniels and Gilbert tables, so these tests
are self-contained: nobody needs the source spreadsheet to work on this file.
"""

from __future__ import annotations

import pytest

from finishline.metrics import daniels
from finishline.schema import HALF_MARATHON_M, MARATHON_M, MILE_M


def test_the_percent_of_vo2max_curve_matches_the_published_table() -> None:
    """16.5 minutes of racing is 96.575 percent of VO2max."""
    assert daniels.pct_vo2max(16.5) == pytest.approx(0.96575, abs=1e-5)


def test_a_five_kilometre_race_scores_the_published_vdot() -> None:
    """5 km in 16:30 is VDOT 62.3 in the tables."""
    assert daniels.vdot(5000.0, 16.5 * 60) == pytest.approx(62.3, abs=0.05)


def test_the_curve_falls_as_the_race_lengthens() -> None:
    fractions = [daniels.pct_vo2max(t) for t in (5, 15, 30, 60, 120, 180)]
    assert fractions == sorted(fractions, reverse=True)


def test_a_faster_time_over_the_same_distance_scores_higher() -> None:
    quick = daniels.vdot(10000.0, 35 * 60)
    slow = daniels.vdot(10000.0, 45 * 60)
    assert quick is not None and slow is not None
    assert quick > slow


def test_equivalent_performances_agree_across_distances() -> None:
    """One fitness, read off two distances, is one number. This is what VDOT is for."""
    five = daniels.vdot(5000.0, 16.5 * 60)
    ten = daniels.vdot(10000.0, daniels.race_time(five, 10000.0) or 0.0)
    assert five is not None and ten is not None
    assert five == pytest.approx(ten, abs=1e-6)


def test_race_time_inverts_vdot(
) -> None:
    for metres in (5000.0, 10000.0, HALF_MARATHON_M, MARATHON_M):
        seconds = daniels.race_time(55.0, metres)
        assert seconds is not None
        assert daniels.vdot(metres, seconds) == pytest.approx(55.0, abs=1e-6)


def test_a_projection_round_trips_between_distances() -> None:
    """Project a 10 km to the marathon and back, and the 10 km comes back."""
    start = 40 * 60.0
    marathon = daniels.equivalent_time(start, 10000.0, MARATHON_M)
    back = daniels.equivalent_time(marathon, MARATHON_M, 10000.0)
    assert back == pytest.approx(start, abs=0.5)


def test_longer_races_are_slower_per_kilometre() -> None:
    paces = [
        (daniels.race_time(55.0, metres) or 0.0) / (metres / 1000.0)
        for metres in (5000.0, 10000.0, HALF_MARATHON_M, MARATHON_M)
    ]
    assert paces == sorted(paces)


@pytest.mark.parametrize(
    ("distance", "seconds", "why"),
    [
        (5000.0, 8 * 60.0, "faster than any human; outside the fitted band"),
        (800.0, 2 * 60.0, "under a kilometre, where GPS error alone moves VDOT"),
        (MARATHON_M, 5 * 3600.0, "five hours is past where the curve is fitted"),
        (10000.0, 0.0, "no time"),
        (0.0, 1800.0, "no distance"),
    ],
)
def test_an_out_of_range_performance_is_refused_rather_than_guessed(
    distance: float, seconds: float, why: str
) -> None:
    """A missing number is recoverable. A confident wrong one gets published."""
    assert daniels.vdot(distance, seconds) is None, why


def test_a_slow_marathon_is_refused_and_that_is_the_point() -> None:
    """The share of a field this baseline cannot answer for is a published number."""
    assert daniels.vdot(MARATHON_M, 4 * 3600.0) is not None
    assert daniels.vdot(MARATHON_M, 4.5 * 3600.0) is None


def test_riegel_matches_its_own_arithmetic() -> None:
    """T2 = T1 * (D2/D1) ** 1.06 from the half to the marathon."""
    half = 90 * 60.0
    expected = half * 2.0 ** daniels.RIEGEL_DEFAULT_EXPONENT
    assert daniels.riegel(half, HALF_MARATHON_M, MARATHON_M) == pytest.approx(
        expected, rel=1e-9
    )


@pytest.mark.parametrize(
    ("metres", "expected"),
    [(1500.0, 1.08), (MILE_M, 1.08), (2000.0, 1.075), (3000.0, 1.07), (5000.0, 1.06)],
)
def test_the_riegel_exponent_is_banded_by_target_distance(
    metres: float, expected: float
) -> None:
    """The mile is under two kilometres, so it takes the shortest band's exponent."""
    assert daniels.riegel_exponent(metres) == expected


def test_riegel_takes_a_fitted_exponent() -> None:
    """The endurance term is a parameter, because the textbook value is optimistic.

    Vickers and Vertosick found the standard exponent at least ten minutes fast at the
    marathon for half of recreational runners, so a runner whose own exponent is higher
    must be able to say so.
    """
    half = 90 * 60.0
    textbook = daniels.riegel(half, HALF_MARATHON_M, MARATHON_M)
    weaker = daniels.riegel(half, HALF_MARATHON_M, MARATHON_M, exponent=1.10)
    assert textbook is not None and weaker is not None
    assert weaker > textbook + 300, "a higher exponent must cost real minutes"


def test_the_two_projections_agree_for_a_fast_runner_and_not_for_a_slow_one() -> None:
    """Both baselines are defensible, and where they part is where the field is.

    Carried from the half to the marathon, the power law and equal VDOT are four seconds
    apart for a ninety-minute half and nearly two and a half minutes apart for a
    two-hour one. Two baselines that agree on the front of the field and disagree on the
    back of it is worth having, because the back of the field is most of it.
    """
    fast_riegel = daniels.riegel(90 * 60.0, HALF_MARATHON_M, MARATHON_M)
    fast_vdot = daniels.equivalent_time(90 * 60.0, HALF_MARATHON_M, MARATHON_M)
    slow_riegel = daniels.riegel(120 * 60.0, HALF_MARATHON_M, MARATHON_M)
    slow_vdot = daniels.equivalent_time(120 * 60.0, HALF_MARATHON_M, MARATHON_M)
    assert None not in (fast_riegel, fast_vdot, slow_riegel, slow_vdot)
    assert abs(fast_riegel - fast_vdot) < 30  # type: ignore[operator]
    assert abs(slow_riegel - slow_vdot) > 120  # type: ignore[operator]
