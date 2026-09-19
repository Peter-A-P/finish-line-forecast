"""The start list, and the results file an organiser sends.

Both are about people who have not run yet or whose race this project did not fetch, so
both are tested for the same thing: read exactly what was given, refuse the rest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from finishline.ingest import entrants, resultsfile

LIST_PAGE = """<html><body>
<div id="nav"><ul>
  <li><a href="/">Home</a></li>
  <li><a href="/cart">Cape to Cabot Registration List</a></li>
</ul></div>
<h1 id="ezPagesHeading">Cape to Cabot Registration List</h1>
<p>This list contains the up-to-the-minute list of registrations for the race.</p>
<ul>
  <li>Susan Abbott ---- (Female) Women's XS</li>
  <li>Drew Ackerman ---- (Male) Men's M</li>
  <li>Hollie Young ---- (Female) Women's M</li>
</ul>
</body></html>"""

USR_PAGE = """<html><body>
<h1 id="ezPagesHeading">USR Registration List</h1>
<h1>Provincial Marathon</h1>
<ul><li>Abdelrahman Ahmed</li><li>Cormac Whitten - Canadian Forces</li></ul>
<h1>Half Marathon</h1>
<ul><li>Perpetua Sled</li></ul>
</body></html>"""


def test_the_entrants_are_read_and_the_furniture_is_not() -> None:
    """The store's sidebar is made of list items too, and so is a line of script."""
    field = entrants.parse(LIST_PAGE)
    assert [row.name for row in field] == ["Susan Abbott", "Drew Ackerman", "Hollie Young"]
    assert [row.sex for row in field] == ["F", "M", "F"]


def test_the_shirt_size_is_not_read() -> None:
    """It is on the page and it would probably help. It is not what results publish."""
    field = entrants.parse(LIST_PAGE)
    assert not any("XS" in str(row) or "Women's" in str(row) for row in field)
    assert entrants.Entrant("Susan Abbott", "F").known_before_the_gun == ("Susan Abbott", "F")


def test_an_entrant_carries_the_event_they_entered() -> None:
    """One page, several races, and a marathon entry is not a half-marathon entry."""
    field = entrants.parse(USR_PAGE)
    assert [(row.name, row.event) for row in field] == [
        ("Abdelrahman Ahmed", "Provincial Marathon"),
        ("Cormac Whitten", "Provincial Marathon"),
        ("Perpetua Sled", "Half Marathon"),
    ]


def test_a_list_that_prints_no_sex_says_so_rather_than_guessing() -> None:
    assert all(row.sex is None for row in entrants.parse(USR_PAGE))


def test_the_latest_snapshot_is_the_one_used(tmp_path: Path) -> None:
    """The list is live, so a prediction records which day's copy it was frozen against."""
    for stamp in ("20260910T1200Z", "20260912T1603Z", "20260911T0900Z"):
        (tmp_path / f"c2c-2026_ane-list_{stamp}.html").write_text("x", encoding="utf-8")
    latest = entrants.latest_snapshot(tmp_path, "c2c-2026")
    assert latest is not None
    assert "20260912T1603Z" in latest.name
    assert entrants.latest_snapshot(tmp_path, "nothing-here") is None


# --- a results file an organiser sends --------------------------------------------

EXPORT = (
    "Place,Bib,First Name,Last Name,Gender,Division,Chip Time,Gun Time,City,Age,Shirt Size\n"
    "1,3152,Jordan,Fewer,M,M30-34,53:28,53:29,Corner Brook,31,L\n"
    "2,2378,Mark,Greene,M,M40-44,53:45,53:45,St. John's,44,M\n"
    "3,2639,Kate,Bazeley,F,F35-39,56:10,56:10,St. John's,38,S\n"
)


def test_a_results_export_becomes_the_same_rows_as_a_page() -> None:
    rows = resultsfile.parse_rows(EXPORT, "tely-2026")
    assert len(rows) == 3
    first = rows[0]
    assert first.name == "Jordan Fewer"
    assert first.place == 1
    assert first.sex == "M"
    assert first.age_band == "M30-34"
    assert first.hometown == "Corner Brook"
    assert first.gun_seconds == pytest.approx(3209.0)
    assert first.chip_seconds == pytest.approx(3208.0)
    assert first.seconds == first.chip_seconds


def test_the_columns_this_project_does_not_use_are_named_not_swallowed() -> None:
    """Age and shirt size are on the file and stay off the runner."""
    rows = resultsfile.parse_rows(EXPORT, "tely-2026")
    assert all("Shirt" not in str(row) for row in rows)
    assert "age" in resultsfile.IGNORED
    assert "shirt size" in resultsfile.IGNORED


def test_an_unrecognised_column_stops_the_import() -> None:
    """The same refusal the page parser makes, for the same reason."""
    with pytest.raises(resultsfile.UnknownColumns) as caught:
        resultsfile.parse_rows("Place,Name,Handicap\n1,Cormac Whitten,+3\n", "race")
    assert caught.value.headers == ("Handicap",)


def test_a_file_with_no_recorded_source_is_refused(tmp_path: Path) -> None:
    """A published number has to be traceable to the bytes it came from."""
    path = tmp_path / "tely.csv"
    path.write_text(EXPORT, encoding="utf-8")
    with pytest.raises(ValueError, match="recorded source"):
        resultsfile.load(path, "tely-2026", source="", received="2026-09-12")


def test_a_file_with_a_recorded_source_keeps_it(tmp_path: Path) -> None:
    path = tmp_path / "tely.csv"
    path.write_text(EXPORT, encoding="utf-8")
    loaded = resultsfile.load(
        path, "tely-2026", source="NLAA, by email", received="2026-09-12"
    )
    assert loaded.source == "NLAA, by email"
    assert loaded.received == "2026-09-12"
    assert len(loaded.results) == 3


def test_a_page_that_differs_only_in_its_security_token_is_not_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real store puts a fresh securityToken in every response.

    Comparing the pages as fetched called every look a change, which would have written a
    new copy of five hundred names every day until the race and buried the growth curve
    under identical files. What is compared is the start list.
    """
    monkeypatch.setattr(entrants, "MIN_INTERVAL", 0.0)
    tokened = LIST_PAGE.replace(
        "<h1", "<script>var securityToken = '{token}';</script>\n<h1"
    )
    monkeypatch.setattr(entrants, "_fetch", lambda url: tokened.format(token="a" * 32))
    first = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})
    monkeypatch.setattr(entrants, "_fetch", lambda url: tokened.format(token="b" * 32))
    second = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})

    assert first[0].changed and not second[0].changed
    assert len(list(tmp_path.glob("*.html"))) == 1

    rows = [
        json.loads(line)
        for line in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["page_sha256"] != rows[1]["page_sha256"], "the bytes did differ"
    assert rows[0]["listing_sha256"] == rows[1]["listing_sha256"], "the start list did not"


def test_a_reordered_list_is_not_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The club reordering its own page is not somebody entering the race."""
    monkeypatch.setattr(entrants, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(entrants, "_fetch", lambda url: LIST_PAGE)
    entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})

    shuffled = LIST_PAGE.replace(
        "<li>Susan Abbott ---- (Female) Women's XS</li>\n  ", ""
    ).replace(
        "<li>Hollie Young",
        "<li>Susan Abbott ---- (Female) Women's XS</li>\n  <li>Hollie Young",
    )
    monkeypatch.setattr(entrants, "_fetch", lambda url: shuffled)
    again = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})
    assert not again[0].changed


def test_a_snapshot_is_written_once_and_re_observed_without_a_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two looks at an unchanged list: one file, two manifest rows.

    The file is the content and the manifest row is the observation. A list that did not
    move is still a fact worth keeping, and it is not worth a second copy of the names.
    """
    monkeypatch.setattr(entrants, "_fetch", lambda url: LIST_PAGE)
    monkeypatch.setattr(entrants, "MIN_INTERVAL", 0.0)

    first = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})
    second = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})

    assert [s.changed for s in first] == [True]
    assert [s.changed for s in second] == [False]
    assert second[0].path == first[0].path
    assert first[0].entrants == 3
    assert len(list(tmp_path.glob("*.html"))) == 1
    assert len((tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_a_changed_list_never_overwrites_the_earlier_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Yesterday's list is the only evidence of who had entered yesterday."""
    monkeypatch.setattr(entrants, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(entrants, "_fetch", lambda url: LIST_PAGE)
    entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})

    grown = LIST_PAGE.replace(
        "<li>Hollie Young", "<li>Ravi Nasser ---- (Male) Men's L</li>\n  <li>Hollie Young"
    )
    monkeypatch.setattr(entrants, "_fetch", lambda url: grown)
    # A second snapshot in the same minute would collide on the filename, so the clock is
    # what separates them; the guard here is that nothing is lost, not that it is fast.
    monkeypatch.setattr(entrants, "_filename", lambda prefix, at, url="": f"{prefix}_later.html")
    later = entrants.snapshot(tmp_path, lists={"c2c-2026": "https://example.invalid/list"})

    assert later[0].changed
    assert later[0].entrants == 4
    assert len(list(tmp_path.glob("*.html"))) == 2
    assert entrants.load(later[0].path) != entrants.load(
        next(p for p in sorted(tmp_path.glob("*.html")) if p != later[0].path)
    )


def test_the_snapshot_command_refuses_before_the_courtesy_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same rail as the crawler: this fetches from the same club's site."""
    from typer.testing import CliRunner

    from finishline import cli

    monkeypatch.delenv(cli.NOTICES_ENV, raising=False)
    monkeypatch.setattr(cli, "ENTRANTS", tmp_path)
    monkeypatch.setattr(
        entrants, "_fetch", lambda url: pytest.fail("fetched before the notes went out")
    )
    result = CliRunner().invoke(cli.app, ["snapshot"])
    assert result.exit_code == 2


# A Trackie entry list as its data request returns it: the table, then the counts. The names
# are invented; the layout is the Turkey Tea 10k's of 2026-09-19.
TRACKIE_LIST = (
    '<table><tr><th>Full Name</th><th>Gender</th><th>Medal/No Medal</th><th>Hometown</th>'
    "<th>Team Name</th></tr>"
    "<tr><td><a href='#'>Sled, Perpetua</a></td><td>Female</td><td>Medal</td>"
    "<td>Mount Pearl</td><td>Paradise Running Club</td></tr>"
    "<tr><td>Hale-Ford, Tobias</td><td>Male</td><td>No Medal</td><td>St. John&#39;s</td>"
    "<td></td></tr></table>^:|:^2^:|:^2^:|:^0^:|:^0"
)


def test_a_trackie_list_reads_name_sex_and_hometown_and_not_the_medal() -> None:
    field = entrants.parse(TRACKIE_LIST)
    assert field == [
        entrants.Entrant("Perpetua Sled", "F", hometown="Mount Pearl"),
        entrants.Entrant("Tobias Hale-Ford", "M", hometown="St. John's"),
    ]
    assert "Medal" not in repr(field)


def test_a_trackie_snapshot_is_filed_as_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entrants, "_fetch", lambda url: TRACKIE_LIST)
    url = "https://www.trackie.com/entry-list/some-race/123/"
    (seen,) = entrants.snapshot(tmp_path, lists={"tt-2026": url})
    assert seen.path.name.startswith("tt-2026_trackie-list_")
    assert seen.entrants == 2
