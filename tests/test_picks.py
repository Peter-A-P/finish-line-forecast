"""Entrants the linker refused, decided by hand: what a pick may do, and how it is published."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline.identity import link, pickpage, picks
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant
from finishline.schema import Race, Result

RACES = {
    "old": Race("old", "Tely 10", date(2011, 7, 24), 16_093.0, "tely-16093", "x"),
    "here": Race("here", "Cape to Cabot", date(2025, 10, 19), 20_000.0, "c2c-20000", "x"),
}
LIVE = Race("c2c-2026", "Cape to Cabot", date(2026, 10, 18), 20_000.0, "c2c-20000", "")
TODAY = date(2026, 10, 12)


def printed(race_id: str, seconds: float | None, band: str = "40-49", sex: str = "M") -> Result:
    return Result(race_id, 1, 1, "Chris Walsh", None, sex, 1, band, 1, "Paradise", seconds, None)


def walshes() -> list[Runner]:
    """Two men of one name: one last seen in 2011, one who ran this course a year ago."""
    return [
        Runner("chriswalsh#0", "Chris Walsh", "Paradise", "M", (printed("old", 4000.0),), False),
        Runner("chriswalsh#1", "Chris Walsh", "Paradise", "M", (printed("here", 6000.0),), False),
    ]


def pick_of(runner: Runner, entrant: str = "Chris Walsh") -> picks.Pick:
    return picks.for_runner(entrant, runner, RACES, "course", "", TODAY)


def test_a_pick_links_an_entrant_the_rules_refused_and_says_a_person_did_it() -> None:
    archive = walshes()
    (refused,) = link.link([Entrant("CHRIS WALSH", "M")], archive)
    assert refused.status is link.Status.AMBIGUOUS and not refused.by_hand

    (only,) = link.link([Entrant("CHRIS WALSH", "M")], archive, [pick_of(archive[1])])
    assert only.status is link.Status.LINKED and only.by_hand
    assert only.runner is archive[1]
    assert "by hand" in only.reason


def test_a_pick_can_say_the_entrant_is_none_of_them() -> None:
    made = [picks.newcomer("Chris Walsh", "known", "moved here this year", TODAY)]
    (only,) = link.link([Entrant("Chris Walsh", "M")], walshes(), made)
    assert only.status is link.Status.NEW and only.runner is None and only.by_hand


def test_a_pick_never_overrules_a_link_the_rules_made() -> None:
    """One runner of the name is linked by rule, whatever a stale pick says."""
    archive = walshes()
    made = [pick_of(archive[0])]
    (only,) = link.link([Entrant("Chris Walsh", "M")], archive[1:], made)
    assert only.runner is archive[1] and not only.by_hand


def test_a_pick_follows_the_result_it_names_when_the_ids_move() -> None:
    """A crawl can renumber the runners of a name; the result still belongs to one of them."""
    archive = walshes()
    made = [pick_of(archive[1])]
    renumbered = [
        Runner("chriswalsh#0", "Chris Walsh", None, "M", archive[1].results, False),
        Runner("chriswalsh#1", "Chris Walsh", None, "M", archive[0].results, False),
    ]
    (only,) = link.link([Entrant("Chris Walsh", "M")], renumbered, made)
    assert only.runner is renumbered[0] and only.by_hand


def test_a_pick_of_a_history_the_archive_no_longer_commits_to_decides_nothing() -> None:
    archive = walshes()
    made = [pick_of(archive[1])]
    moved = [archive[0], Runner("chriswalsh#1", "Chris Walsh", None, "M", archive[1].results, True)]
    (only,) = link.link([Entrant("Chris Walsh", "M")], moved, made)
    assert only.status is link.Status.AMBIGUOUS and not only.by_hand


def test_a_runner_the_resolver_refused_cannot_be_picked() -> None:
    held = Runner("chriswalsh#2", "Chris Walsh", None, "M", (printed("here", 6100.0),), True)
    with pytest.raises(ValueError, match="could not place"):
        pick_of(held)


def test_a_pick_cannot_say_which_of_two_entrants_of_one_name_it_means() -> None:
    archive = walshes()
    links = link.link(
        [Entrant("Chris Walsh", "M"), Entrant("chris walsh", "M")], archive, [pick_of(archive[1])]
    )
    assert [item.status for item in links] == [link.Status.AMBIGUOUS, link.Status.AMBIGUOUS]


def test_a_picked_runner_is_predicted_as_the_sex_the_results_printed() -> None:
    """The list printed none; the models read it from the entrant, as with an overruled sex."""
    archive = walshes()
    (only,) = link.link([Entrant("Chris Walsh", None)], archive, [pick_of(archive[1])])
    assert only.entrant.sex == "M"


def test_evidence_is_one_of_the_kinds_the_page_offers() -> None:
    with pytest.raises(ValueError, match="evidence"):
        picks.newcomer("Chris Walsh", "a hunch", "", TODAY)


def test_picks_are_saved_in_one_form_and_read_back(tmp_path: Path) -> None:
    archive = walshes()
    path = picks.path_for(tmp_path, "c2c-2026")
    assert picks.load(path) == []
    first = pick_of(archive[1])
    other = picks.newcomer("Ann Hynes", "known", "", TODAY)
    picks.save(path, [first, other])
    assert picks.load(path) == [other, first], "ordered by name, whatever order they were made in"
    assert picks.to_bytes([other, first]) == picks.to_bytes([first, other])
    again = pick_of(archive[0])
    assert picks.put([first, other], again) == [other, again], "one pick per entrant"
    assert picks.drop([first, other], "CHRIS WALSH") == [other]


def test_the_age_on_race_day_is_what_every_printed_band_allows() -> None:
    results = [printed("old", 4000.0, "40-49"), printed("here", 6000.0, "50-59")]
    # 40 to 49 in 2011 and 50 to 59 in 2025: born 1965 to 1971, so 54 to 61 in 2026.
    assert picks.age_on(results, RACES, LIVE.date) == "54 to 61"
    assert picks.age_on([printed("old", 4000.0, "")], RACES, LIVE.date) == "no age printed"
    clash = [printed("old", 4000.0, "20-29"), printed("here", 6000.0, "60-69")]
    assert picks.age_on(clash, RACES, LIVE.date) == "the printed ages disagree"


# --- the page (identity/pickpage.py) ------------------------------------------------


def desk(
    tmp_path: Path, published: dict[str, tuple[str, bool]] | None = None
) -> pickpage.Desk:
    held = Runner("chriswalsh#2", "Chris Walsh", None, "M", (printed("here", 6100.0),), True)
    entered = [Entrant("Chris Walsh", "M"), Entrant("Bea Power", "F")]
    return pickpage.Desk(
        LIVE,
        entered,
        [*walshes(), held],
        RACES,
        picks.path_for(tmp_path, "c2c-2026"),
        published or {},
        TODAY,
    )


def test_the_page_shows_the_refused_entrant_beside_each_runner_of_the_name(tmp_path: Path) -> None:
    (card,) = desk(tmp_path).cases()["cards"]
    assert card["entrant"] == "Chris Walsh" and card["pick"] is None and card["decidable"]
    first, second = card["candidates"]
    assert (first["last"], first["here"]) == ("2011", 0)
    assert (second["last"], second["here"]) == ("2025", 1)
    assert second["results"][0]["here"] and second["results"][0]["time"] == "1:40:00"
    assert len(card["unplaced"]) == 1, "a refused history is evidence, never a candidate"


def test_a_decision_on_the_page_is_what_the_next_link_reads(tmp_path: Path) -> None:
    table = desk(tmp_path)
    table.decide({
        "entrant": "Chris Walsh", "action": "runner", "candidate": "chriswalsh#1",
        "evidence": "course", "note": "ran it last year",
    })
    (card,) = table.cases()["cards"]
    assert card["pick"]["candidate"] == "chriswalsh#1" and card["pick"]["stands"]
    links = link.link(table.entered, table.runners, picks.load(table.path))
    assert links[0].by_hand and links[0].runner is not None
    assert links[0].runner.runner_id == "chriswalsh#1"

    table.decide({"entrant": "Chris Walsh", "action": "clear"})
    assert picks.load(table.path) == []


def test_the_page_refuses_what_a_pick_may_not_do(tmp_path: Path) -> None:
    table = desk(tmp_path)
    ask = {"entrant": "Chris Walsh", "action": "runner", "evidence": "course", "note": ""}
    with pytest.raises(pickpage.Refused, match="could not place"):
        table.decide({**ask, "candidate": "chriswalsh#2"})
    with pytest.raises(pickpage.Refused, match="not one of"):
        table.decide({**ask, "candidate": "somebody#0"})
    with pytest.raises(pickpage.Refused, match="not one the linker refused"):
        table.decide({**ask, "entrant": "Bea Power", "candidate": "chriswalsh#1"})
    with pytest.raises(pickpage.Refused, match="say in the note"):
        table.decide({**ask, "candidate": "chriswalsh#1", "evidence": "other"})
    assert picks.load(table.path) == []


def test_a_pick_is_locked_once_its_line_is_in_a_published_file(tmp_path: Path) -> None:
    table = desk(tmp_path, {"chriswalsh": ("daily-2026-10-13.json", True)})
    with pytest.raises(pickpage.Refused, match="locked"):
        table.decide({"entrant": "Chris Walsh", "action": "clear"})
    assert table.cases()["cards"][0]["published"] == "daily-2026-10-13.json"


def test_a_line_the_rules_made_before_refusing_the_entrant_locks_nothing(tmp_path: Path) -> None:
    """PLAN.md 13 item 46: a pick there re-issues the line, which is what should happen."""
    table = desk(tmp_path, {"chriswalsh": ("daily-2026-10-11.json", False)})
    (card,) = table.cases()["cards"]
    assert card["published"] is None and card["earlier"] == "daily-2026-10-11.json"
    table.decide({"entrant": "Chris Walsh", "action": "new", "evidence": "known", "note": ""})
    assert [pick.choice for pick in picks.load(table.path)] == [picks.NEWCOMER]


def test_the_page_puts_names_in_as_text_and_ships_none() -> None:
    assert "innerHTML" not in pickpage.PAGE
    assert "Walsh" not in pickpage.PAGE
