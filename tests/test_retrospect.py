"""A race run before this project published anything, and the rules that keep it honest.

Most of these tests exist because the obvious version of this feature is wrong:

- an already-run race must never be reachable as a prediction, so nothing here writes into
  `predictions/` and the record carries no hash and no tag;
- an event on a road with no earlier edition is not scored, because the error there is mostly
  the cost of a missing course factor;
- a finisher the resolver refused keeps their row and their real place, and reaches none of
  the figures, because showing somebody and scoring them are different jobs (PLAN 13 item 38);
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


def result(
    race_id: str,
    place: int,
    name: str,
    seconds: float,
    *,
    sex: str | None = None,
    band: str | None = None,
) -> Result:
    """One line on a results page. `sex` and `band` are None wherever the page printed none,
    which is every line of the one race these tests are about."""
    return Result(race_id, place, None, name, None, sex, None, band, None, None, seconds, None)


def dataset() -> Dataset:
    results = [
        result("r-2026", 1, "Ann Hynes", 2400.0),
        result("r-2026", 2, "Bea Power", 2700.0),
        result("r-2026", 3, "Cal Noseworthy", 3000.0),
        # The year before, on the association's own page, which prints both. This race does
        # not, and the two columns on the site are borrowed from here.
        result("r-2025", 1, "Ann Hynes", 2430.0, sex="F", band="40-49"),
        result("m-2026", 1, "Dot Squires", 12000.0),
    ]
    runners = [
        Runner("ann", "Ann Hynes", None, "F", (results[3], results[0]), False, ""),
        Runner("bea", "Bea Power", None, "F", (results[1],), False, ""),
        # Refused by the resolver: two runners of this name and nothing to choose between
        # them. They finished, so they are in the table, with no prediction and a reason.
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


def test_a_finisher_with_no_prediction_keeps_their_row_and_says_why() -> None:
    """The rule item 38 is about: a real result may be incomplete, never restated.

    Cal Noseworthy finished third and the resolver refused him, so he has no prediction. He is
    still in the table, still third, still at his own time, carrying the reason.
    """
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    assert block["finishers"] == 3
    assert block["scored"] == 2, "the figures above the table are over the two predicted"
    assert block["ambiguous"] == 1
    assert [row["name"] for row in block["runners"]] == [
        "Ann Hynes", "Bea Power", "Cal Noseworthy"
    ], "every finisher, in finishing order"
    cal = block["runners"][2]
    assert cal["place"] == 3, "the place the results page printed"
    assert cal["actual"] == pytest.approx(3000.0)
    assert cal["excluded"] == "two of this name"
    assert cal["seconds"] is None
    assert cal["places_out"] is None, "a runner with no prediction is out by no places"


def test_no_row_is_renumbered_when_a_finisher_ahead_has_no_prediction() -> None:
    """A table that deletes the winner and calls the runner-up first is a second race.

    The whole of PLAN.md 13 item 38. The only place printed is the place in the race that was
    run; the ordering error beside it is a difference over the predicted field and never an
    absolute place, so there is no second scale to be mistaken for the first.
    """
    results = [
        result("r-2026", 1, "Cal Noseworthy", 2300.0),  # refused by the resolver
        result("r-2026", 2, "Ann Hynes", 2400.0),
        result("r-2026", 3, "Bea Power", 2700.0),
    ]
    runners = [
        Runner("ann", "Ann Hynes", None, "F", (results[1],), False, ""),
        Runner("bea", "Bea Power", None, "F", (results[2],), False, ""),
        Runner("cal", "Cal Noseworthy", None, None, (results[0],), True, "two of this name"),
    ]
    data = Dataset(races={TEN_K.race_id: TEN_K}, results=results, runners=runners, failures=[])
    block = retrospect.race(data, scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Cal Noseworthy"]["place"] == 1, "he won it, and the table says so"
    assert rows["Ann Hynes"]["place"] == 2, "second, not first"
    assert "predicted_place" not in rows["Ann Hynes"], "no absolute place on a second scale"
    # The winner having no prediction changes nothing about the order of the two who do.
    assert rows["Ann Hynes"]["places_out"] == 0
    assert rows["Bea Power"]["places_out"] == 0


def test_a_finisher_with_no_prediction_does_not_move_the_place_error() -> None:
    """The model is not charged for somebody the resolver could not identify.

    The same two predicted runners, in the same order, with a third finisher dropped in ahead
    of them who has no prediction. Their place error must not notice.
    """
    plain = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    results = [
        result("r-2026", 1, "Cal Noseworthy", 2300.0),
        result("r-2026", 2, "Ann Hynes", 2400.0),
        result("r-2026", 3, "Bea Power", 2700.0),
    ]
    runners = [
        Runner("ann", "Ann Hynes", None, "F", (results[1],), False, ""),
        Runner("bea", "Bea Power", None, "F", (results[2],), False, ""),
        Runner("cal", "Cal Noseworthy", None, None, (results[0],), True, "two of this name"),
    ]
    ahead = retrospect.race(
        Dataset(races={TEN_K.race_id: TEN_K}, results=results, runners=runners, failures=[]),
        scored_rows(), intervals(), "r-2026", [],
    )
    assert plain is not None and ahead is not None
    assert plain["places_out"] == ahead["places_out"]
    assert plain["median_places_out"] == ahead["median_places_out"]


def test_out_by_is_the_finish_minus_the_prediction_not_the_other_way_round() -> None:
    """A runner who took a minute longer than they were told reads +1:00, not -1:00.

    The opposite sign to `score.Scored.error` and to every bias table, and deliberately so:
    a bias is read on the model, and a row in this table is read on the runner. Ann was
    called at 39:00 and ran 40:00, which is a minute longer than she was told.
    """
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Ann Hynes"]["out_by"] == pytest.approx(60.0)
    assert rows["Bea Power"]["out_by"] == pytest.approx(-120.0)


def test_the_gender_and_age_group_are_borrowed_and_say_where_from() -> None:
    """This race printed neither, so the columns come from the runner's other results.

    Ann's 2025 line on the association's own page printed F and 40-49. That is public under
    her name there, it is what the site shows here, and the row carries the race and the date
    it was printed at so a reader is never told it came off this finish list.
    """
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Ann Hynes"]["sex"] == "F"
    assert rows["Ann Hynes"]["age"] == "40-49"
    assert rows["Ann Hynes"]["age_from"] == "Club 10k, 2025-09-14"
    # Bea has one result and it printed nothing, so there is nothing to show and no guess.
    assert rows["Bea Power"]["age"] is None
    assert rows["Bea Power"]["age_from"] is None
    assert block["with_age"] == 1


def test_a_band_the_runner_has_certainly_grown_out_of_is_not_printed() -> None:
    """20-29 in 2016 puts a runner at 30 to 40 in 2026, so the band is dropped, not aged.

    Aging it forward would be inventing a band no page printed. Leaving it as printed would
    be putting a claim about a person's age on the website that is certainly false. The row
    goes blank, which is the only one of the three that is true.
    """
    assert not retrospect.still_possible("20-29", date(2016, 4, 24), date(2026, 9, 13))
    # Three months on, a runner printed 45-49 may have turned 50 and may not, so the band
    # they were printed under is still one they could be in.
    assert retrospect.still_possible("45-49", date(2026, 6, 28), date(2026, 9, 13))
    # An open band at the top never expires; one at the bottom does.
    assert retrospect.still_possible("80+", date(2016, 4, 24), date(2026, 9, 13))
    assert not retrospect.still_possible("U20", date(2001, 4, 24), date(2026, 9, 13))


def test_a_finisher_with_no_prediction_gets_no_age_or_gender_either() -> None:
    """The row says the archive cannot tell which runner this is. Then it may not say her age.

    Cal's cluster here has a sex and a printed band on it. It is still two people, which is
    why the row has no prediction, so putting one of them's age beside the other's finish
    would invent exactly the thing the row exists to say is unknown.
    """
    data = dataset()
    older = result("r-2025", 9, "Cal Noseworthy", 3100.0, sex="F", band="30-39")
    cal = next(runner for runner in data.runners if runner.runner_id == "cal")
    runners = [runner for runner in data.runners if runner.runner_id != "cal"]
    runners.append(Runner("cal", cal.name, None, "F", (older, *cal.results), True, cal.reason))
    data = Dataset(
        races=data.races, results=[*data.results, older], runners=runners, failures=[]
    )
    block = retrospect.race(data, scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Cal Noseworthy"]["excluded"]
    assert rows["Cal Noseworthy"]["sex"] is None
    assert rows["Cal Noseworthy"]["age"] is None


def test_a_band_printed_after_this_race_is_not_borrowed() -> None:
    """Nothing after the gun reaches this page, including a column that is only description.

    The whole claim of a retrospective is that the model saw nothing after the quarter before
    the race. A description taken from a later page would not move a number, and would still
    be the one thing a reader has no way to check.
    """
    data = dataset()
    later = Race("r-2027", "Club 10k", date(2027, 5, 1), 10_000.0, "club-10000", "u")
    after = result("r-2027", 1, "Ann Hynes", 2450.0, sex="F", band="50-59")
    ann = next(runner for runner in data.runners if runner.runner_id == "ann")
    runners = [runner for runner in data.runners if runner.runner_id != "ann"]
    runners.append(Runner("ann", ann.name, None, "F", (*ann.results, after), False, ""))
    data = Dataset(
        races={**data.races, "r-2027": later},
        results=[*data.results, after],
        runners=runners,
        failures=[],
    )
    block = retrospect.race(data, scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Ann Hynes"]["age"] == "40-49", "the 2027 page may not describe a 2026 row"


def test_places_out_is_signed_so_a_reader_can_see_which_way_the_order_missed() -> None:
    block = retrospect.race(dataset(), scored_rows(), intervals(), "r-2026", [])
    assert block is not None
    rows = {row["name"]: row for row in block["runners"]}
    assert rows["Ann Hynes"]["place"] == 1
    assert rows["Ann Hynes"]["places_out"] == 0
    assert rows["Bea Power"]["place"] == 2 and rows["Bea Power"]["places_out"] == 0


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
