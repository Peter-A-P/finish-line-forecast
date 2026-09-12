"""The one race read from a timing platform rather than from the association's pages.

The 2026 Tely 10. Its columns are the same eleven the association prints itself in every
other year, so the test that matters is that they land in the same fields a page would
produce, and that nothing about where it came from goes unrecorded.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from finishline.ingest import raceroster

PAYLOAD = {
    "_id": "x",
    "meta": {"totalResults": 3, "filteredResults": 3},
    "data": [
        {
            "id": "k779gnpstcnydzxd",
            "overallPlace": 1,
            "bib": "4395",
            "name": "Cormac Whitten",
            "gunTime": "46:51",
            "division": "M25-29",
            "divisionPlace": "1 / 285",
            "genderSexId": "Male",
            "genderPlace": "1 / 1975",
            "overallPace": "4:41 ",
            "chipTime": "46:50",
            "fromCity": "Vancouver",
        },
        {
            "id": "uzrqdrrak9dg59na",
            "overallPlace": 2,
            "bib": "2639",
            "name": "Perpetua Sled (ANER)",
            "gunTime": "56:10",
            "division": "F35-39",
            "divisionPlace": "1 / 146",
            "genderSexId": "Female",
            "genderPlace": "1 / 2172",
            "overallPace": "5:37 ",
            "chipTime": "56:10",
            "fromCity": "St. John's",
        },
        {
            "id": "mnakwqk5wrwamv4n",
            "overallPlace": 3,
            "bib": "2057",
            "name": "Ossian Crake",
            "gunTime": "3:59:09",
            "division": "",
            "divisionPlace": "",
            "genderSexId": "Male",
            "genderPlace": "1975 / 1975",
            "overallPace": "23:40 ",
            "chipTime": "3:56:33",
            "fromCity": "St. John's",
        },
    ],
}


def test_the_platforms_rows_become_the_same_records_a_page_would() -> None:
    rows = raceroster.to_results(PAYLOAD, "tely-2026")
    assert len(rows) == 3

    winner = rows[0]
    assert winner.place == 1
    assert winner.bib == 4395
    assert winner.name == "Cormac Whitten"
    assert winner.sex == "M"
    assert winner.age_band == "25-29"
    assert winner.category_place == 1
    assert winner.sex_place == 1
    assert winner.gun_seconds == pytest.approx(2811.0)
    assert winner.chip_seconds == pytest.approx(2810.0)
    assert winner.seconds == winner.chip_seconds
    assert winner.hometown == "Vancouver"


def test_a_club_in_the_name_is_taken_off_as_it_is_on_a_page() -> None:
    second = raceroster.to_results(PAYLOAD, "tely-2026")[1]
    assert second.name == "Perpetua Sled"
    assert second.club == "ANER"
    assert second.sex == "F"


def test_a_missing_division_leaves_no_age_band_rather_than_a_guess() -> None:
    """299 of the real 4,147 have no division printed, and none of them gets invented one."""
    third = raceroster.to_results(PAYLOAD, "tely-2026")[2]
    assert third.age_band is None
    assert third.category_place is None
    assert third.sex == "M"
    assert third.finished


def test_a_row_with_no_name_is_dropped_rather_than_carried() -> None:
    payload = {"data": [{"overallPlace": 1, "name": "", "gunTime": "30:00"}]}
    assert raceroster.to_results(payload, "race") == []


def test_the_register_says_what_each_external_race_is_and_why_it_was_read() -> None:
    """Which races came from where is part of what this project claims, so it is committed."""
    assert len(raceroster.REGISTER) == 1
    tely = raceroster.REGISTER[0]
    assert tely.date == date(2026, 6, 28)
    assert tely.distance_m == pytest.approx(16093.44)
    assert tely.course_id == "tely-10-16093", "the same course as every other edition"
    assert "docs/data-terms.md" in tely.basis
    assert tely.race.race_id == tely.race_id


def test_the_external_race_shares_a_course_with_the_pages_own_editions() -> None:
    """A course effect is estimated over editions, so 2026 has to join the same course."""
    from finishline.ingest.nlaa import course_id

    assert raceroster.REGISTER[0].course_id == course_id(
        "Tely 10 Mile Road Race - Individual Results", 16093.44
    )


def test_a_cached_payload_is_read_without_touching_the_network(tmp_path: Path) -> None:
    """One request per race, ever. A rerun of the pipeline costs none."""
    race = raceroster.REGISTER[0]
    (tmp_path / race.cache_name).write_text(json.dumps(PAYLOAD), encoding="utf-8")
    rows = raceroster.load(race, tmp_path)
    assert len(rows) == 3
    assert not (tmp_path / "manifest.jsonl").exists(), "nothing was fetched, so nothing logged"


def test_the_crawler_says_who_it_is_and_why() -> None:
    assert "finishline" in raceroster.USER_AGENT
    assert "@" in raceroster.USER_AGENT
    assert "organiser" in raceroster.USER_AGENT
