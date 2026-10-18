"""The wind leg by leg: an out-and-back is never free, and a headwind costs more than it returns."""

from __future__ import annotations

import pytest

from finishline.models import route

# Run to Remember's shape: half the distance east, half back west.
OUT_EAST_BACK_WEST = route.Route((route.Leg(90.0, 0.5), route.Leg(270.0, 0.5)))
# The air travels toward the east at 20 km/h: a westerly.
WESTERLY = (20.0, 0.0)


def test_on_an_out_and_back_the_push_cancels_and_the_squared_part_does_not() -> None:
    """Out into a westerly and back with it: the linear part cancels mile for mile, the squared
    part is the whole wind, so the morning still costs something, as a hill out and back does."""
    exposure, net = route.wind_terms(*WESTERLY, 20.0, OUT_EAST_BACK_WEST)
    assert net == pytest.approx(0.0, abs=1e-9)
    assert exposure == pytest.approx(4.0), "(20 / 10) squared, on both halves"


def test_the_same_wind_across_an_out_and_back_lies_along_none_of_it() -> None:
    southerly = (0.0, 20.0)  # the air travels north
    exposure, net = route.wind_terms(*southerly, 20.0, OUT_EAST_BACK_WEST)
    assert exposure == pytest.approx(0.0, abs=1e-9)
    assert net == pytest.approx(0.0, abs=1e-9)


def test_a_course_with_no_known_legs_faces_every_way() -> None:
    exposure, net = route.wind_terms(*WESTERLY, 20.0, None)
    assert net == 0.0
    assert exposure == pytest.approx(0.5 * 4.0), "cos squared averages a half round a circle"


def test_a_straight_road_downwind_gets_the_whole_wind_as_a_push() -> None:
    east = route.Route((route.Leg(90.0, 1.0),))
    exposure, net = route.wind_terms(*WESTERLY, 20.0, east)
    assert exposure == pytest.approx(4.0)
    assert net == pytest.approx(20.0)


def test_a_gusty_wind_with_no_steady_direction_still_counts() -> None:
    """Mean speed 20, mean vector 0: the wind boxed the compass, and the road met some of it."""
    exposure, net = route.wind_terms(0.0, 0.0, 20.0, OUT_EAST_BACK_WEST)
    assert net == 0.0
    assert exposure == pytest.approx(0.5 * 4.0)


def test_with_a_cost_on_exposure_a_headwind_leg_costs_more_than_a_tailwind_leg_gives() -> None:
    """The asymmetry the two terms exist for, with any positive exposure cost."""
    exposure_cost, net_cost = 0.002, -0.003
    into = route.Route((route.Leg(270.0, 1.0),))
    with_it = route.Route((route.Leg(90.0, 1.0),))
    cost_into = exposure_cost * route.wind_terms(*WESTERLY, 20.0, into)[0] + net_cost * (
        route.wind_terms(*WESTERLY, 20.0, into)[1]
    )
    gain_with = exposure_cost * route.wind_terms(*WESTERLY, 20.0, with_it)[0] + net_cost * (
        route.wind_terms(*WESTERLY, 20.0, with_it)[1]
    )
    assert cost_into > 0 > gain_with
    assert cost_into > -gain_with


def test_waypoints_become_legs_with_shares_of_the_length() -> None:
    # A square block, about 1 km a side, start and finish at the same corner.
    a, b = (47.5, -52.7), (47.509, -52.7)
    c, d = (47.509, -52.6867), (47.5, -52.6867)
    loop = route.from_waypoints([a, b, c, d, a])
    assert len(loop.legs) == 4
    assert sum(leg.share for leg in loop.legs) == pytest.approx(1.0)
    assert [round(leg.heading_deg / 90) % 4 for leg in loop.legs] == [0, 1, 2, 3]
    assert loop.net_share == pytest.approx(0.0, abs=0.01)
    assert route.wind_terms(*WESTERLY, 20.0, loop)[1] == pytest.approx(0.0, abs=0.2)


def test_one_point_is_not_a_route() -> None:
    with pytest.raises(ValueError):
        route.from_waypoints([(47.5, -52.7)])
