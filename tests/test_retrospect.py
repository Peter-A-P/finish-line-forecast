"""A race run before this project published anything, and the rules that keep it honest.

Three of these tests exist because the obvious version of this feature is wrong:

- an already-run race must never be reachable as a prediction, so nothing here writes into
  `predictions/` and the record carries no hash and no tag;
- an event on a road with no earlier edition is not scored, because the error there is mostly
  the cost of a missing course factor;
- the start list a retrospective may use is the one from before the gun, not the latest, and
  the scheduled task went on looking at the USR list for days afterwards.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from finishline.backtest.score import Scored
from finishline.conformal.split import Interval
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant
from finishline.publish import retrospect
from finishline.schema import Race, Result
from finishline.store import Dataset

TEN_K = Race("r-2026", "Club 10k", date(2026, 9, 13), 10_000.0, "club-10000", "u")
LAST_YEAR = Race("r-2025", "Club 10k", date(2025, 9, 14), 10_000.0, "club-10000", "u")
NEW_ROAD = Race("m-2026", "Club Marathon", date(2026, 9, 13), 42_195.0, "club-42195", "u")


def result(race_id: str, place: int, name: str, seconds: float) -> Result:
    return Result(race_id, place, None, name, None, None, None, None, None, None, seconds, None)


def dataset() -> Dataset:
    results = [
        result("r-2026", 1, "Ann Hynes", 2400.0),
        result("r-2026", 2, "Bea Power", 2700.0),
        result("r-2026", 3, "Cal Noseworthy", 3000.0),
        result("r-2025", 1, "Ann Hynes", 2430.0),
        result("m-2026", 1, "Dot Squires", 12000.0),
    ]
    runners = [
        Runner("ann", "Ann Hynes", None, "F", (results[3], results[0]), False, ""),
        Runner("bea", "Bea Power", None, "F", (results[1],), False, ""),
        # Refused by the resolver: two runners of this name and nothing to choose between
        # them. They finished, and they are not in the table.
        Runner("cal", "Cal Noseworthy", None, None, (results[2],), True, "two of this name"),
        Runner("dot", "Dot Squires", None, "F", (results[4],), False, ""),
    ]
    races = {race.race_id: race for race in (TEN_K, LAST_YEAR, NEW_ROAD)}
    return Dataset(races=races, results=results, runners=runners, failures=[])


def scored_rows() -> list[Scored]:
    return [
        Scored("blend", "r-2026", "ann", 2340.0, 2400.0, 6, ()),
        Scored("blend", "r-2026", "bea", 2820.0, 2700.0, 1, ()),
        Scored("carry-forward", "r-2026", "ann", 2430.0, 2400.0, 6, ()),
    ]


def intervals() -> list[Interval]:
    rows = {row.runner_id: row for row in scored_rows() if row.model == "blend"}
    return [
        Interval(rows["ann"], 0.80, 2200.0, 2500.0, 2200.0, 2500.0, 40),
        Interval(rows["bea"], 0.80, 2600.0, 3000.0, 2600.0, 3000.0, 40),
    ]


def test_an_event_on_a_road_with_no_earlier_edition_is_not_scored() -> None:
    """The rule that decided the 2026 USR published its 10 km and not its marathon.

    Mechanical, not a judgement made race by race: the 10 km's course has a 2025 edition and
    the marathon's road is new, so the model had a course factor for one and none for the
    other, and an error on the second is mostly the cost of that.
    """
    data = dataset()
    assert retrospect.scorable(data, "r-2026")
    assert not retrospect.scorable(data, "m-2026")


def test_an_unscored_event_is_listed_rather_than_dropped() -> None:
    """A reader told about the 10 km and not about the marathon beside it is half told."""
    listed = retrospect.unscored(dataset(), ["m-2026"])
    assert [row["name"] for row in listed] == ["Club Marathon"]
    assert listed[0]["finishers"] == 1


def test_a_finisher_the_archive_cannot_identify_is_excluded_and_counted() -> None:
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    assert block["finishers"] == 3
    assert block["scored"] == 2
    assert block["ambiguous"] == 1
    assert [row["name"] for row in block["runners"]] == ["Ann Hynes", "Bea Power"]


def test_out_by_is_signed_so_a_reader_can_see_which_way_it_missed() -> None:
    """Prediction minus finish: a minus sign means the model called the runner too fast."""
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Ann Hynes"]["out_by"] == pytest.approx(-60.0)
    assert rows["Bea Power"]["out_by"] == pytest.approx(120.0)


def test_the_official_place_and_the_rank_among_the_scored_are_kept_apart() -> None:
    """Two different things, and folding them together flatters the place error.

    The official place is the place in the race that was run, ambiguous runners included.
    The two place columns are ranks inside the scored field, because a runner with no
    prediction cannot be out by any number of places.
    """
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Bea Power"]["finish_place"] == 2, "the results page printed second"
    assert rows["Bea Power"]["actual_place"] == 2, "second of the two scored, as it happens"
    assert rows["Ann Hynes"]["place"] == 1 and rows["Ann Hynes"]["places_out"] == 0


def test_the_paired_comparison_only_uses_runners_the_baseline_could_answer_for() -> None:
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    assert block["paired"] == 1, "carry-forward has nothing to say about a first-timer"
    assert block["paired_model_min"] == pytest.approx(1.0)
    assert block["paired_baseline_min"] == pytest.approx(0.5)


def test_coverage_counts_only_the_runners_who_got_a_range() -> None:
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    assert block["coverage80"] == pytest.approx(1.0), "both finishes fell inside"


def test_an_open_ended_range_is_no_range() -> None:
    """The conformal step can leave an infinite upper edge on a thin stratum."""
    rows = {row.runner_id: row for row in scored_rows() if row.model == "blend"}
    wide = [Interval(rows["ann"], 0.80, 2200.0, float("inf"), 2200.0, float("inf"), 3)]
    block = retrospect.race(dataset(), scored_rows(), wide, "r-2026", [])
    assert block is not None
    assert all(row["i80"] is None for row in block["runners"])
    assert block["coverage80"] is None


# --------------------------------------------------------------- the start list


def entrant(name: str, event: str) -> Entrant:
    return Entrant(name, None, event)


LISTED = [
    entrant("Ann Hynes", "Club 10k"),
    entrant("Bea Power", "Club 10k"),
    entrant("Cal Noseworthy", "Club 10k"),
    entrant("Eli Bursey", "Club 10k"),
    # On the day's other lists, and not in this race's field.
    entrant("Dot Squires", "Club Marathon"),
    entrant("Fay Dalton", "1k Kids Run"),
    entrant("Gus Rowe", "3k Family Run/Walk"),
    entrant("Hal Batten", "Marathon Relay"),
]


def test_only_the_entrants_in_this_race_are_this_race_s_field() -> None:
    """The list groups by event and the archive files by distance; nothing else joins them.

    The kids' run, the family walk and the relay are dropped by the same rules the results
    index is read with, so they never become part of a road race's field.
    """
    picked = [person.name for person in retrospect.entered(LISTED, TEN_K)]
    assert picked == ["Ann Hynes", "Bea Power", "Cal Noseworthy", "Eli Bursey"]


def finishers_of(race_id: str, extra: list[Result] | None = None) -> list[Result]:
    """This race's finish list, as `retrospect.race` hands it over."""
    rows = [*dataset().results, *(extra or [])]
    return [row for row in rows if row.race_id == race_id and row.finished]


def test_the_start_list_against_the_finish_list() -> None:
    seen = retrospect.attendance(LISTED, finishers_of("r-2026"), TEN_K)
    assert seen.listed == 4
    assert seen.finished == 3
    assert seen.found == 3, "Eli Bursey entered and did not finish"
    assert seen.not_found == pytest.approx(0.25), "an upper bound on the no-show rate"
    assert seen.not_listed == 0


def test_a_finisher_from_another_distance_is_a_switch_not_a_late_entry() -> None:
    """Counted apart, because they mean different things to a race director.

    Dot Squires was on the marathon list that morning and finished the 10 km. That is a
    runner who changed distance, not somebody who entered on the day.
    """
    extra = [result("r-2026", 4, "Dot Squires", 3300.0), result("r-2026", 5, "Ivy Snow", 3400.0)]
    seen = retrospect.attendance(LISTED, finishers_of("r-2026", extra), TEN_K)
    assert seen.not_listed == 2, "Dot from the marathon list, Ivy on no list at all"
    assert seen.switched == 1, "only Dot was on another of the morning's lists"


def test_the_snapshot_used_is_the_last_one_before_the_gun(tmp_path: Path) -> None:
    """Not the latest: the scheduled task kept looking at the USR list for days after it."""
    for stamp in ("20260912T1603Z", "20260913T0028Z", "20260917T2253Z"):
        (tmp_path / f"usr-2026_ane-list_{stamp}.html").write_text("x", encoding="utf-8")
    gun = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)
    chosen = retrospect.snapshot_before(tmp_path, "usr-2026", gun)
    assert chosen is not None and "20260913T0028Z" in chosen.name


def test_a_list_with_no_snapshot_before_the_gun_gives_nothing(tmp_path: Path) -> None:
    (tmp_path / "usr-2026_ane-list_20260917T2253Z.html").write_text("x", encoding="utf-8")
    gun = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)
    assert retrospect.snapshot_before(tmp_path, "usr-2026", gun) is None


def test_a_prefix_is_matched_or_refused_never_approximated() -> None:
    """Attaching one race's start list to another would invent a no-show rate."""
    assert retrospect.list_prefix("usr", date(2026, 9, 13), ["usr-2026", "c2c-2026"]) == "usr-2026"
    assert retrospect.list_prefix("cape-to-cabot", date(2026, 10, 18), ["c2c-2026"]) is None


def test_a_calendar_day_becomes_every_race_that_ran_on_it() -> None:
    """One entry, several races, shortest first."""
    assert retrospect.events_on(dataset(), date(2026, 9, 13), "club") == ["r-2026", "m-2026"]
    assert retrospect.events_on(dataset(), date(2026, 9, 13), "other") == []
