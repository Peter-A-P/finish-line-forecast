"""Who is who, and when the answer is "we cannot tell".

Merging two runners is the expensive mistake: it invents a person and publishes a
confident wrong prediction under a real name. Splitting one is cheap: two thin histories
and a wider interval. Every test here is written from that asymmetry.
"""

from __future__ import annotations

from datetime import date

import pytest

from finishline.identity import resolve
from finishline.schema import Race, Result


def race(race_id: str, when: date, metres: float = 10000.0) -> Race:
    return Race(
        race_id=race_id,
        name=race_id,
        date=when,
        distance_m=metres,
        course_id="course",
        url=f"https://example.invalid/{race_id}",
    )


def result(
    race_id: str,
    name: str,
    *,
    town: str | None = "St. John's",
    band: str | None = "30-39",
    sex: str | None = "F",
    seconds: float | None = 2400.0,
    place: int = 1,
) -> Result:
    return Result(
        race_id=race_id,
        place=place,
        bib=place,
        name=name,
        club=None,
        sex=sex,
        sex_place=place,
        age_band=band,
        category_place=place,
        hometown=town,
        gun_seconds=seconds,
        chip_seconds=None,
    )


RACES = {
    "r2021": race("r2021", date(2021, 6, 1)),
    "r2023": race("r2023", date(2023, 6, 1)),
    "r2025": race("r2025", date(2025, 6, 1)),
    "r2026": race("r2026", date(2026, 6, 1)),
}


@pytest.mark.parametrize(
    ("band", "expected"),
    [
        ("30-39", (30, 39)),
        ("25-29", (25, 29)),
        ("U20", (resolve.MIN_AGE, 20)),
        ("80+", (80, resolve.MAX_AGE)),
        ("19&U", (resolve.MIN_AGE, 19)),
        ("", None),
        (None, None),
        ("open", None),
    ],
)
def test_an_age_band_is_read_or_refused(band: str | None, expected: object) -> None:
    """The bands differ by race and by year, so anything unreadable is no evidence."""
    assert resolve.age_range(band) == expected


def test_a_band_implies_a_window_of_birth_years() -> None:
    """A runner aged 30 to 39 in 2025 was born between 1985 and 1995."""
    assert resolve.birth_window("30-39", date(2025, 6, 1)) == (1985, 1995)


def test_one_runner_ageing_normally_stays_one_runner() -> None:
    """30-39 in 2021 and 40-49 in 2026 is one person having a birthday, not two people."""
    results = [
        result("r2021", "Perpetua Sled", band="30-39"),
        result("r2026", "Perpetua Sled", band="40-49"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert not runners[0].ambiguous
    assert runners[0].history_depth == 2


def test_a_runner_who_got_younger_is_two_runners_and_is_not_published() -> None:
    """Two people share a name and a town, and the age bands are what give them away."""
    results = [
        result("r2021", "Chris Power", band="50-59"),
        result("r2026", "Chris Power", band="20-29"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].ambiguous
    assert runners[0].reason is not None
    assert "cannot belong to one runner" in runners[0].reason


def test_two_towns_are_two_runners() -> None:
    """Same name, different towns: split, which costs two thin histories and no lies."""
    results = [
        result("r2023", "Chris Walsh", town="St. John's"),
        result("r2025", "Chris Walsh", town="Corner Brook"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 2
    assert {runner.hometown for runner in runners} == {"St. John's", "Corner Brook"}
    assert not any(runner.ambiguous for runner in runners)


def test_a_town_spelled_two_ways_is_one_runner() -> None:
    results = [
        result("r2023", "Perpetua Sled", town="St. John's"),
        result("r2025", "Perpetua Sled", town="Saint Johns"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].history_depth == 2


def test_a_missing_town_joins_the_only_runner_of_that_name() -> None:
    """A blank is missing information, and with one candidate there is nothing to confuse."""
    results = [
        result("r2023", "Perpetua Sled", town="Paradise"),
        result("r2025", "Perpetua Sled", town=None),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].history_depth == 2
    assert runners[0].hometown == "Paradise"


def test_a_missing_town_under_an_ambiguous_name_is_not_guessed() -> None:
    """Two Chris Walshes and a blank third: the blank is nobody's, and it is counted."""
    results = [
        result("r2021", "Chris Walsh", town="St. John's"),
        result("r2023", "Chris Walsh", town="Corner Brook"),
        result("r2025", "Chris Walsh", town=None),
    ]
    runners = resolve.resolve(results, RACES)
    ambiguous = [runner for runner in runners if runner.ambiguous]
    assert len(ambiguous) == 1
    assert ambiguous[0].results[0].race_id == "r2025"
    assert ambiguous[0].reason is not None
    assert "no hometown printed" in ambiguous[0].reason
    assert sum(runner.history_depth for runner in runners if not runner.ambiguous) == 2


def test_results_that_disagree_about_sex_are_flagged() -> None:
    results = [
        result("r2023", "Sam Rideout", sex="F"),
        result("r2025", "Sam Rideout", sex="M"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].ambiguous
    assert runners[0].reason is not None
    assert "disagree about sex" in runners[0].reason


def test_different_names_are_never_merged() -> None:
    results = [
        result("r2023", "Michael Power"),
        result("r2025", "Mike Power"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 2


def test_results_come_back_in_date_order() -> None:
    """The trend term reads the order, so a shuffled history would fit a slope backwards."""
    results = [
        result("r2026", "Perpetua Sled", band="30-39"),
        result("r2021", "Perpetua Sled", band="30-39"),
        result("r2023", "Perpetua Sled", band="30-39"),
    ]
    runners = resolve.resolve(results, RACES)
    assert [row.race_id for row in runners[0].results] == ["r2021", "r2023", "r2026"]


def test_resolution_does_not_depend_on_the_order_it_reads_the_archive() -> None:
    """A prediction file has to be reproducible from the archive, whatever order it came in."""
    results = [
        result("r2021", "Chris Walsh", town="St. John's"),
        result("r2023", "Chris Walsh", town="Corner Brook"),
        result("r2025", "Perpetua Sled", town="Paradise"),
    ]
    forward = resolve.resolve(results, RACES)
    backward = resolve.resolve(list(reversed(results)), RACES)
    assert [runner.runner_id for runner in forward] == [
        runner.runner_id for runner in backward
    ]


def test_a_did_not_finish_does_not_count_toward_history_depth() -> None:
    """A DNF is a start, not a finish, and the strata are about evidence of speed."""
    results = [
        result("r2023", "Perpetua Sled"),
        result("r2025", "Perpetua Sled", seconds=None),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners[0].results) == 2
    assert runners[0].history_depth == 1


def test_a_runner_with_no_age_band_anywhere_is_not_flagged() -> None:
    """No evidence is not contrary evidence. Some older pages print no band at all."""
    results = [
        result("r2023", "Perpetua Sled", band=None),
        result("r2025", "Perpetua Sled", band=None),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert not runners[0].ambiguous
