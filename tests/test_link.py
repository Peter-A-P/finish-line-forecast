"""Linking start-list entrants to archive runners: refuse when in doubt, and count it."""

from __future__ import annotations

from finishline.identity import link
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant


def runner(runner_id: str, name: str, sex: str | None = "F", *, ambiguous: bool = False) -> Runner:
    return Runner(runner_id, name, None, sex, (), ambiguous)


def test_one_runner_of_that_name_links_across_spellings() -> None:
    archive = [runner("r1", "Mary O'Brien")]
    (only,) = link.link([Entrant("MARY OBRIEN", "F")], archive)
    assert only.status is link.Status.LINKED
    assert only.runner is not None and only.runner.runner_id == "r1"


def test_nobody_of_that_name_is_a_newcomer() -> None:
    (only,) = link.link([Entrant("Perpetua Sled", "F")], [runner("r1", "Mary Power")])
    assert only.status is link.Status.NEW and only.runner is None


def test_nicknames_are_not_joined() -> None:
    """normalise.py: Mike and Michael stay two people."""
    (only,) = link.link([Entrant("Mike Power", "M")], [runner("r1", "Michael Power", "M")])
    assert only.status is link.Status.NEW


def test_two_runners_of_one_name_is_a_refusal_not_a_guess() -> None:
    archive = [runner("r1", "Chris Walsh", "M"), runner("r2", "Chris Walsh", "M")]
    (only,) = link.link([Entrant("Chris Walsh", "M")], archive)
    assert only.status is link.Status.AMBIGUOUS
    assert "2 runners" in only.reason


def test_sex_separates_two_people_of_one_name() -> None:
    """Chris Walsh the woman is not Chris Walsh the man, so this one links cleanly."""
    archive = [runner("r1", "Chris Walsh", "M"), runner("r2", "Chris Walsh", "F")]
    (only,) = link.link([Entrant("Chris Walsh", "F")], archive)
    assert only.status is link.Status.LINKED
    assert only.runner is not None and only.runner.runner_id == "r2"


def test_a_listed_sex_that_contradicts_the_history_is_a_different_person() -> None:
    (only,) = link.link([Entrant("Sam Hynes", "F")], [runner("r1", "Sam Hynes", "M")])
    assert only.status is link.Status.NEW


def test_a_missing_sex_is_no_information_rather_than_a_mismatch() -> None:
    (only,) = link.link([Entrant("Sam Hynes", None)], [runner("r1", "Sam Hynes", "M")])
    assert only.status is link.Status.LINKED


def test_a_runner_the_resolver_refused_stays_refused() -> None:
    archive = [runner("r1", "Pat Kelly", ambiguous=True)]
    (only,) = link.link([Entrant("Pat Kelly", "F")], archive)
    assert only.status is link.Status.AMBIGUOUS


def test_two_entrants_claiming_one_history_are_both_excluded() -> None:
    """Two Pat Kellys on the list are two people, and at most one ran those races."""
    archive = [runner("r1", "Pat Kelly")]
    entrants = [Entrant("Pat Kelly", "F"), Entrant("Other Person", "F"), Entrant("pat kelly", "F")]
    links = link.link(entrants, archive)
    assert [item.status for item in links] == [
        link.Status.AMBIGUOUS,
        link.Status.NEW,
        link.Status.AMBIGUOUS,
    ]
    assert link.counts(links) == {"linked": 0, "new": 1, "ambiguous": 2}
