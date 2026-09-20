"""The association's calendar: what it takes, what it refuses, and why the two differ.

The calendar is the only source here that mixes sports. A results index is all road racing by
the time `nlaa.parse_index` has found the road section; the calendar puts a marathon and a
tetrathlon in the same table, so almost every test here is about telling them apart.
"""

from __future__ import annotations

from datetime import date

import pytest

from finishline.ingest import calendar

# The shape the page has had since it was first read, cut down to the rows that matter. Each
# one is a real row: three track meets whose names carry a road course's venue, a schools
# cross-country meet, the multi-event days, and one row nothing here recognises.
PAGE = """
<table class="table table-striped table-sm">
<thead class="thead-dark"><tr><th>NLAA Provincial Events Calendar - 2026</th></tr></thead>
<tbody>
<tr><td><span class="badge badge-secondary">Sun, Apr 26</span> <a href="https://x/" target='_blank'
 title='t'>Boston Pizza Flat Out 5km Road Race&nbsp;<i class="fa"></i></a>, St. John's</td></tr>
<tr><td><span class="badge badge-secondary">Tue, Jun 2</span> <a href="https://pearlgate.ca/"
 target='_blank' title='t'>Pearlgate Twilight Meet 1 (14+, born 2012 and older)</a>,
 Mount Pearl</td></tr>
<tr><td><span class="badge badge-secondary">Fri, Jun 5-Sat, Jun 6</span> <a href="/x.php"
 target='_self' title='t'>NLAA Junior and Senior HS Championships (3 sessions)</a>,
 Mount Pearl</td></tr>
<tr><td><span class="badge badge-secondary">Sat, Aug 29</span> <a href="/y.php" target='_self'
 title='t'>Sea-Hawks XC Season Opener 5k (U14 2k)</a>, St. John's</td></tr>
<tr><td><span class="badge badge-secondary">Sun, Sep 13</span> <a href="/z.php" target='_self'
 title='t'>Uniformed Services Run Marathon/Half-Marathon/Marathon Relay/5km/10km</a>,
 St. John's</td></tr>
<tr><td><span class="badge badge-secondary">Sat, Sep 19</span> <a href="/a.php" target='_self'
 title='t'>Cross-country Running Series for Schools Meet #1</a>, St. John's</td></tr>
<tr><td><span class="badge badge-secondary">Sun, Oct 18</span> <a href="/b.php" target='_self'
 title='t'>Capital Subaru Cape to Cabot 20km</a>, St. John's</td></tr>
</tbody></table>
"""


@pytest.fixture(name="parsed")
def _parsed() -> tuple[int, list[calendar.Event]]:
    return calendar.parse(PAGE)


def test_the_year_comes_from_the_heading(parsed: tuple[int, list[calendar.Event]]) -> None:
    year, _events = parsed
    assert year == 2026


def test_every_row_is_accounted_for(parsed: tuple[int, list[calendar.Event]]) -> None:
    """Seven rows in, seven rows out. A row that is neither taken nor refused is a hole."""
    _year, events = parsed
    assert len(events) == 7
    assert len(list(calendar.road_races(events))) + len(calendar.unread(events)) == 7


def test_the_road_races_are_the_road_races(parsed: tuple[int, list[calendar.Event]]) -> None:
    _year, events = parsed
    assert [event.family for event in calendar.road_races(events)] == [
        "flat-out",
        "usr",
        "cape-to-cabot",
    ]


def test_a_relay_on_a_road_racing_day_does_not_lose_the_day() -> None:
    """The row that would be dropped by reusing the results index's rule unchanged.

    "Uniformed Services Run Marathon/Half-Marathon/Marathon Relay/5km/10km" matches
    `nlaa.NOT_ROAD` on "relay", and it is also the biggest multi-distance road race of the
    year. A calendar entry is a day, not a race, so the word is a component and not a verdict.
    """
    family, reason = calendar.classify(
        "Uniformed Services Run Marathon/Half-Marathon/Marathon Relay/5km/10km"
    )
    assert family == "usr" and reason is None


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        # A track meet named after a venue that is also a road-race course. The alias table
        # matches "pearlgate", so the track test has to run first or this is a road race.
        ("Pearlgate Twilight Meet 1 (14+, born 2012 and older)", "track and field"),
        ("Pearlgate Tetrathlons - Meet 3 (U14, born 2013 and younger)", "track and field"),
        ("NLAA Age-Class Track and Field Championships", "track and field"),
        # Cross-country carries a course alias too ("provincial"), and is not road racing.
        ("NLAA Provincial Cross-country Championships", "a different sport"),
        ("Sea-Hawks XC Season Opener 5k (U14 2k)", "a different sport"),
        ("Cross-country Running Series for Schools Meet #1", "a different sport"),
    ],
)
def test_what_is_not_a_road_race_says_which_kind_of_not(name: str, reason: str) -> None:
    family, why = calendar.classify(name)
    assert family is None
    assert why is not None and why.startswith(reason)


def test_an_unrecognised_row_is_reported_rather_than_guessed_at(
    parsed: tuple[int, list[calendar.Event]],
) -> None:
    """The one skip that is ever a bug: a road race whose name has no alias yet.

    It sorts first in `unread` for that reason, so a person running `finishline calendar`
    reads it before twenty rows of track meets.
    """
    _year, events = parsed
    first = calendar.unread(events)[0]
    assert first.name.startswith("NLAA Junior and Senior HS Championships")
    assert first.skipped == "no course this project knows is named here"


def test_a_date_range_keeps_both_ends(parsed: tuple[int, list[calendar.Event]]) -> None:
    _year, events = parsed
    ranged = next(event for event in events if event.name.startswith("NLAA Junior"))
    assert ranged.when == date(2026, 6, 5)
    assert ranged.end == date(2026, 6, 6)


def test_the_place_survives_the_external_link_icon(
    parsed: tuple[int, list[calendar.Event]],
) -> None:
    """The club's off-site links carry an icon and a non-breaking space inside the anchor."""
    _year, events = parsed
    flat_out = next(event for event in events if event.family == "flat-out")
    assert flat_out.name == "Boston Pizza Flat Out 5km Road Race"
    assert flat_out.place == "St. John's"


def test_a_page_with_no_year_is_refused_rather_than_dated_by_guess() -> None:
    with pytest.raises(ValueError, match="no year in its heading"):
        calendar.parse("<table><tbody><tr><td>nothing</td></tr></tbody></table>")


def test_the_record_carries_the_skips_too(parsed: tuple[int, list[calendar.Event]]) -> None:
    """`data/calendar.json` is the whole page, not the filtered view.

    A file that held only the road races would be a claim the reader has to take on trust.
    """
    year, events = parsed
    written = calendar.record(year, events)
    assert len(written["events"]) == 7
    assert sum(1 for row in written["events"] if row["skipped"]) == 4
    assert written["source"] == calendar.URL
    assert written["watching_since"] == calendar.WATCHING_SINCE.isoformat()
    assert [row["date"] for row in written["events"]] == sorted(
        row["date"] for row in written["events"]
    )
