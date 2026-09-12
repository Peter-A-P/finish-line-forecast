"""The catalogue: which pages are read, what each one is, and what is left out.

The skips matter as much as the races. A race wrongly kept lands in the history with the
wrong distance; a race wrongly dropped is a hole in the coverage number the README
publishes. Both are tested.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline.ingest import nlaa
from finishline.schema import HALF_MARATHON_M, MARATHON_M, MILE_M


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ("Boston Pizza Flat Out 5km", 5000.0),
        ("Body Quest Turkey Tea 10K", 10000.0),
        ("Crown & Anchor Mews Memorial 8k", 8000.0),
        ("Capital Subaru Cape to Cabot 20km", 20000.0),
        ("Run To Remember 11km", 11000.0),
        ("ANE Open Mile Road Race", MILE_M),
        ("Tely 10 Mile Road Race", 10 * MILE_M),
        ("USR - Half Marathon", HALF_MARATHON_M),
        ("USR - Provincial Marathon", MARATHON_M),
        ("Kid's Race Trapline 2025 (1km and 3km)", None),
        ("Boxing Day Handicap", None),
    ],
)
def test_the_distance_comes_from_the_event_name_or_not_at_all(
    event: str, expected: float | None
) -> None:
    """Two distances in one name is no distance. A 5 km filed as a 10 km halves a time."""
    assert nlaa.distance_m(event) == expected


def test_a_half_marathon_is_not_a_marathon() -> None:
    """The word is a substring of the other, and getting it wrong doubles the race."""
    assert nlaa.distance_m("USR - Half Marathon") == HALF_MARATHON_M
    assert nlaa.distance_m("USR - Provincial Marathon") == MARATHON_M
    assert nlaa.distance_m("Trapline Half-Marathon") == HALF_MARATHON_M


@pytest.mark.parametrize(
    ("event", "href", "expected"),
    [
        ("Capital Subaru Cape to Cabot 20km", "rr/2025/c2c.php", True),
        ("Pharmasave Figure 8 (8K) Trail Race", "rr/2025/fig8.php", False),
        ("USR - Marathon Relay", "rr/2025/relay.pdf", False),
        ("Sea-Hawks XC Season Opener - 5km", "rr/2025/xc.php", False),
        ("ANE School Mile Road Race", "rr/2025/school.pdf", False),
        ("Kid's Race Trapline (1km and 3km)", "rr/2025/kids.pdf", False),
        ("Trapline 5km Road Race (U19)", "rr/2025/u19.php", True),
        ("Tely 10 Mile Road Race - Individual Results", "rr/2025/tely.php", True),
        ("Tely 10 Mile Road Race - Team Results", "rr/2025/teams.php", False),
        ("Tely 10 Mile Road Race - Awards", "rr/2025/awards.php", False),
        ("The Tely 10 Mile Road Race: Team Awards", "rr/2018/ta.php", False),
    ],
)
def test_only_individual_road_results_are_read(event: str, href: str, expected: bool) -> None:
    """A junior road race is a road race; a trail race and a relay are not."""
    assert nlaa.is_road(event, href) is expected


def test_one_race_published_as_three_pages_is_one_race() -> None:
    """Every Tely publishes results, team standings and awards as separate index rows.

    Read as races they made nineteen editions of a race run ten times, which would have
    estimated one day's course effect three times and counted the same runners twice.
    """
    same_day = [
        ("Tely 10 Mile Road Race - Individual Results", "rr/2025/tely-results.php"),
        ("Tely 10 Mile Road Race - Team Results", "rr/2025/tely-teams.php"),
        ("Tely 10 Mile Road Race - Awards", "rr/2025/tely-awards.php"),
    ]
    kept = [event for event, href in same_day if nlaa.is_road(event, href)]
    assert kept == ["Tely 10 Mile Road Race - Individual Results"]


def test_a_course_survives_its_sponsor() -> None:
    """The sponsor is in the event name and changes; the hill does not."""
    assert nlaa.course_id("Cape to Cabot 20km", 20000.0) == nlaa.course_id(
        "Capital Subaru Cape to Cabot 20km", 20000.0
    )
    assert nlaa.course_id("Turkey Tea 10km", 10000.0) == nlaa.course_id(
        "Body Quest Turkey Tea 10K", 10000.0
    )


def test_one_event_over_two_distances_is_two_courses() -> None:
    """The Trapline starts four races from one line and they are not the same road."""
    ids = {
        nlaa.course_id("Trapline 5km", 5000.0),
        nlaa.course_id("Trapline 10km", 10000.0),
        nlaa.course_id("Trapline Half Marathon", HALF_MARATHON_M),
        nlaa.course_id("Trapline Marathon", MARATHON_M),
    }
    assert len(ids) == 4


def test_the_index_yields_the_road_section_only(index_page: str) -> None:
    """Track and cross-country are on the same page under their own headings."""
    rows = nlaa.parse_index(index_page, 2031)
    hrefs = [href for href, _event, _when in rows]
    assert all(href.startswith("rr/") for href in hrefs)
    assert len(rows) == 13


def test_the_index_reads_the_date_from_the_filename(index_page: str) -> None:
    rows = {event: when for _href, event, when in nlaa.parse_index(index_page, 2031)}
    assert rows["Capital Subaru Cape to Cabot 20km"] == date(2031, 10, 18)
    assert rows["Run To Remember 11km"] == date(2031, 11, 11)


def test_the_index_unescapes_entities_and_straightens_the_quotes(index_page: str) -> None:
    """`&#8217;` is a curly apostrophe, and a curly one is the same apostrophe.

    The index writes it curly and the results pages write it straight, so without this
    one surname sorts into two piles. See identity/normalise.py.
    """
    events = [event for _href, event, _when in nlaa.parse_index(index_page, 2031)]
    assert "Banished Brewing Five & Dime Road Race - 5km" in events
    assert "Kid's Race Trapline 2031 (1km and 3km)" in events
    assert not any(chr(0x2019) in event for event in events)


def test_the_catalogue_keeps_the_road_races_and_says_why_it_dropped_the_rest(
    index_page: str, tmp_path: Path
) -> None:
    cache = nlaa.Cache(tmp_path)
    cache.path_for(nlaa.INDEX.format(year=2031)).parent.mkdir(parents=True, exist_ok=True)
    cache.path_for(nlaa.INDEX.format(year=2031)).write_text(index_page, encoding="utf-8")

    races, skipped = nlaa.catalogue(cache, range(2031, 2032))

    assert [race.name for race in races] == [
        "Boston Pizza Flat Out 5km",
        "ANE Open Mile Road Race",
        "Banished Brewing Five & Dime Road Race - 5km",
        "Banished Brewing Five & Dime Road Race - 10km",
        "Tely 10 Mile Road Race - Individual Results",
        "USR - Half Marathon",
        "Capital Subaru Cape to Cabot 20km",
        "Run To Remember 11km",
    ]
    reasons = dict(skipped)
    assert reasons["Pharmasave Figure 8 (8K) Trail Race"] == (
        "not an individual road result (trail)"
    )
    assert reasons["USR - Marathon Relay"] == "not an individual road result (relay)"
    assert reasons["ANE School Mile Road Race"] == "not an individual road result (school)"
    assert reasons["Boxing Day Handicap"] == "no single distance in the event name"
    assert "Kid's Race Trapline 2031 (1km and 3km)" in reasons
    assert len(races) + len(skipped) == 13, "every index row is either kept or explained"


def test_a_skipped_duplicate_reads_differently_from_a_skipped_hole(index_page: str) -> None:
    """A team page is a race already held; a PDF is a race missing. Not one reason."""
    duplicate = nlaa.why_not_read("Tely 10 Mile Road Race - Team Results", "rr/t.php")
    hole = nlaa.why_not_read("ANE School Mile Road Race", "rr/s.pdf")
    assert duplicate == "not an individual road result (team)"
    assert hole == "not an individual road result (school)"
    assert nlaa.why_not_read("Turkey Tea 10K", "rr/tt.pdf") == (
        "results published as a PDF, which this does not read"
    )
    assert nlaa.why_not_read("Turkey Tea 10K", "rr/tt.php") is None


def test_an_older_page_is_not_dropped_for_its_file_extension() -> None:
    """The 2017 Turkey Tea is a .htm page and a road race like any other.

    A file extension is not evidence about a layout. The parser refuses loudly on one it
    does not know, so that decision belongs there and not here.
    """
    assert nlaa.why_not_read("16th Annual Turkey Tea 10K Road Race", "rr/2017/tt.htm") is None


def test_the_cache_fetches_once_and_records_what_it_fetched(tmp_path: Path) -> None:
    """A cached page is never re-requested, and every fetch leaves a traceable row."""
    cache = nlaa.Cache(tmp_path)
    url = nlaa.BASE + "rr/2031/20311018-c2c-20km.php"
    path = cache.path_for(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<pre>already here</pre>", encoding="utf-8")

    assert cache.cached(url)
    assert "already here" in cache.get(url)
    assert cache._client is None, "a cached page must not open a connection"


def test_the_cache_path_is_readable_and_contained(tmp_path: Path) -> None:
    """A URL becomes a filename that a person can find, and cannot escape the cache."""
    cache = nlaa.Cache(tmp_path)
    path = cache.path_for(nlaa.BASE + "rr/2025/20251019-c2c-20km.php")
    assert path.name == "rr_2025_20251019-c2c-20km.php.html"
    assert path.parent == tmp_path / "pages"
    assert cache.path_for(nlaa.BASE + "../../etc/passwd").parent == tmp_path / "pages"


def test_the_crawler_says_who_it_is() -> None:
    """An administrator who wants this to stop should not have to guess who to email."""
    assert "finishline" in nlaa.USER_AGENT
    assert "@" in nlaa.USER_AGENT
    assert nlaa.MIN_INTERVAL >= 1.0


def test_the_road_section_is_found_under_either_name_the_site_has_used(
    index_page: str,
) -> None:
    """The site renamed the heading in 2016, and matching the new name only lost 2008 to 2015.

    Eight years of road racing read as empty, with nothing raised: the same failure as a
    parser keyed on a ruler that two thirds of the pages do not draw. Matching on "Road"
    and not on the rest of the phrase is what makes it survive the next rename.
    """
    old = index_page.replace("Road Running", "Road Race Series")
    assert len(nlaa.parse_index(old, 2031)) == len(nlaa.parse_index(index_page, 2031)) > 0


def test_the_other_sections_are_still_left_alone() -> None:
    """"Road" must not start matching the cross-country or track headings."""
    page = (
        "<h4>Cross Country Running Results</h4><ol>"
        '<li><b>Sep 1</b>, <a href="xc/2031/a.php">A 5km</a></li></ol>'
        "<h4>Road Race Series</h4><ol>"
        '<li><b>Oct 1</b>, <a href="rr/2031/20311001-b-5km.php">B 5km</a></li></ol>'
    )
    rows = nlaa.parse_index(page, 2031)
    assert [href for href, _e, _w in rows] == ["rr/2031/20311001-b-5km.php"]
