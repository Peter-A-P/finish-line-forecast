"""Newcomers at the biggest races, drawn from how this course's past first-timers finished."""

from __future__ import annotations

from datetime import date

import numpy as np

from finishline.identity.resolve import Runner
from finishline.placing import unseen
from finishline.schema import Race, Result

RACES = {
    "old": Race("old", "old", date(2014, 6, 1), 10_000.0, "elsewhere-10000", "x"),
    "e1": Race("e1", "e1", date(2015, 10, 1), 20_000.0, "c2c-20000", "x"),
    "e2": Race("e2", "e2", date(2016, 10, 1), 20_000.0, "c2c-20000", "x"),
    "early": Race("early", "early", date(2010, 10, 1), 20_000.0, "c2c-20000", "x"),
}


def result(race_id: str, seconds: float) -> Result:
    return Result(race_id, 1, 1, "x", None, "M", 1, "40-49", 1, None, seconds, None)


def archive() -> list[Runner]:
    """40 returning runners at 6000 s in each edition, and first-timers faster and slower."""
    people = [
        Runner(f"r{k}", f"r{k}", None, "M",
               (result("old", 2400.0), result("e1", 6000.0), result("e2", 6000.0)), False)
        for k in range(40)
    ]
    people.append(Runner("fast", "fast", None, "M", (result("e1", 4800.0),), False))
    people.append(Runner("slow", "slow", None, "M", (result("e2", 7200.0),), False))
    people.append(Runner("ancient", "ancient", None, "M", (result("early", 3000.0),), False))
    return people


def test_first_timers_are_measured_against_the_returning_field_of_their_edition() -> None:
    found = unseen.pool(archive(), RACES, "c2c-20000", date(2026, 10, 18))
    assert found is not None
    assert found.editions == 2
    assert sorted(np.round(found.everyone, 4)) == [
        round(float(np.log(4800 / 6000)), 4), round(float(np.log(7200 / 6000)), 4)
    ]


def test_editions_before_the_pool_year_and_after_the_race_are_not_read() -> None:
    found = unseen.pool(archive(), RACES, "c2c-20000", date(2016, 1, 1))
    assert found is not None and found.editions == 1, "2016 is after this origin"
    assert unseen.pool(archive(), RACES, "nowhere-5000", date(2026, 1, 1)) is None


def test_a_newcomer_stands_against_the_known_field_of_the_same_draw() -> None:
    source = unseen.Pool("c", {}, np.array([0.1]), 1)
    known = np.log(np.array([[100.0, 200.0, 300.0], [1000.0, 2000.0, 3000.0]]))
    drawn = unseen.newcomer_log_times(known, ["F"], source, np.random.default_rng(0))
    assert np.allclose(np.exp(drawn[:, 0]), [200 * np.exp(0.1), 2000 * np.exp(0.1)])


def test_the_expected_count_near_the_top_and_where_it_falls() -> None:
    # Three draws of a field of four; column 3 is the newcomer, placed 1st, 2nd and 4th.
    places = np.array([[2, 3, 4, 1], [1, 3, 4, 2], [1, 2, 3, 4]])
    mean, low, high = unseen.expected_in_top(places, [3], 2)
    assert mean == 2 / 3 and (low, high) == (0, 1)
    assert unseen.likely_places(places, [3], 2) == [1]
    assert unseen.likely_places(places, [], 2) == []
