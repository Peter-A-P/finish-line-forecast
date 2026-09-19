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


def test_a_runner_who_got_younger_is_two_runners() -> None:
    """Two people share a name, and the age bands are the only thing that gives them away.

    This is the one split this module makes, and it is forced by evidence: nobody is
    50-59 in 2021 and 20-29 in 2026. Both come out clean, with one result each.
    """
    results = [
        result("r2021", "Chris Power", band="50-59"),
        result("r2026", "Chris Power", band="20-29"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 2
    assert not any(runner.ambiguous for runner in runners)
    assert [runner.history_depth for runner in runners] == [1, 1]
    assert len({runner.runner_id for runner in runners}) == 2


def test_a_runner_who_moved_is_still_one_runner() -> None:
    """The case the archive settled: a runner raced in St. John's and then moved away.

    Of the 1,656 names in this archive with two or more printed hometowns, 1,103 show a
    single clean switch over time, which is what moving house looks like. Splitting on the
    town gave them two half-histories and a worse prediction for both.
    """
    results = [
        result("r2023", "Pat Example", town="St. John's", band="20-24"),
        result("r2025", "Pat Example", town="Corner Brook", band="25-29"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].history_depth == 2
    assert runners[0].towns == ("St. John's", "Corner Brook")
    assert runners[0].town_switches == 1
    assert not runners[0].ambiguous


def test_a_second_town_switch_is_counted_as_the_risk_it_is() -> None:
    """Interleaved towns are the shape two merged people make, so they are countable.

    This module cannot tell them apart and says so; the count bounds how often it is
    wrong, and the README publishes it.
    """
    results = [
        result("r2021", "Chris Walsh", town="St. John's"),
        result("r2023", "Chris Walsh", town="Corner Brook"),
        result("r2025", "Chris Walsh", town="St. John's"),
    ]
    runners = resolve.resolve(results, RACES)
    assert len(runners) == 1
    assert runners[0].town_switches == 2


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


def test_a_result_that_could_be_either_runner_is_held_back() -> None:
    """Two Chris Walshes of different ages, and a third result whose page printed no band.

    It fits both and the page gives nothing to choose with, so it is held back and
    counted rather than attached to whichever came first.
    """
    results = [
        result("r2021", "Chris Walsh", band="50-59", town=None),
        result("r2023", "Chris Walsh", band="20-29", town=None),
        result("r2025", "Chris Walsh", band=None, town=None),
    ]
    runners = resolve.resolve(results, RACES)
    held = [runner for runner in runners if runner.ambiguous]
    assert len(held) == 1
    assert held[0].results[0].race_id == "r2025"
    assert held[0].reason is not None
    assert "no age band" in held[0].reason
    assert sum(runner.history_depth for runner in runners if not runner.ambiguous) == 2


def test_a_hometown_breaks_the_tie_where_it_can() -> None:
    """The town is the tie-break and never the split. Here it decides, so nothing is held."""
    results = [
        result("r2021", "Chris Walsh", band="50-59", town="Corner Brook"),
        result("r2023", "Chris Walsh", band="20-29", town="St. John's"),
        result("r2025", "Chris Walsh", band=None, town="Corner Brook"),
    ]
    runners = resolve.resolve(results, RACES)
    assert not any(runner.ambiguous for runner in runners)
    older = next(r for r in runners if r.results[0].race_id == "r2021")
    assert [row.race_id for row in older.results] == ["r2021", "r2025"]


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
