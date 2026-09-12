"""What the parser must keep doing.

Every test here is a bug that was really in the code, or a property whose failure would
put a wrong number in a published prediction. None of them assert that the parser ran.
"""

from __future__ import annotations

import pytest

from conftest import cached
from finishline.ingest import parse, records


def test_the_general_layout_lands_in_the_right_columns(general_page: str) -> None:
    table = parse.parse_tables(general_page)[0]
    assert table.fields == (
        "place", "bib", "name", "gun_seconds", "sex_and_place",
        "age_band", "category_place", "hometown",
    )
    assert table.rows[0] == {
        "place": "1", "bib": "645", "name": "Cormac Whitten (ANER)", "gun_seconds": "32:51",
        "sex_and_place": "M(1)", "age_band": "30-39", "category_place": "1",
        "hometown": "Harbourmouth",
    }


def test_the_tely_layout_lands_in_the_right_columns(tely_page: str) -> None:
    """The two-line header resolves, and the chip time is its own column."""
    table = parse.parse_tables(tely_page)[0]
    assert table.fields == (
        "place", "bib", "name", "gun_seconds", "class_placing",
        "sex_place", "pace_per_mile", "chip_seconds", "hometown",
    )


def test_the_tely_gender_place_does_not_eat_the_pace(tely_page: str) -> None:
    """The ruler sits right of the data, so slicing by it stole a digit from the pace.

    This is the bug that the measured boundaries exist to prevent. Read by the dashes,
    the first row's gender place came out '1  5' and its pace came out ':03'.
    """
    rows = parse.parse_tables(tely_page)[0].rows
    assert rows[0]["sex_place"] == "1"
    assert rows[0]["pace_per_mile"] == "5:03"
    assert rows[0]["chip_seconds"] == "50:28"
    assert rows[0]["hometown"] == "Harbourmouth"
    assert rows[-1]["sex_place"] == "2222"
    assert rows[-1]["pace_per_mile"] == "20:33"


def test_the_rule_under_the_last_row_is_not_a_second_table(general_page: str) -> None:
    """A closing rule turned the last two finishers into column headers."""
    tables = parse.parse_tables(general_page)
    assert len(tables) == 1
    assert len(tables[0].rows) == 10
    assert tables[0].rows[-1]["place"] == "332"
    assert tables[0].rows[-1]["name"] == "Perpetua Sled (PRCA)"


def test_a_name_wider_than_its_dashes_is_kept_whole(tely_page: str) -> None:
    """The Tely's name column runs six characters past its ruler on the longer names."""
    names = [row["name"] for row in parse.parse_tables(tely_page)[0].rows]
    assert "Ignatius Hale-Ford" in names
    assert "Barnaby Quill-Rowe" in names


def test_a_single_row_table_does_not_split_the_name() -> None:
    """With one row every space is blank in every row, so the measurement over-splits.

    The union back onto the ruler segment is what puts the name together again. A table
    this short is a real case: some category pages have one finisher.
    """
    page = (
        "<pre>POS   BIB   NAME              TIME   \n"
        "----- ----- ----------------- -------\n"
        "    1   645 Cormac Whitten      32:51\n"
        "</pre>"
    )
    rows = parse.parse_tables(page)[0].rows
    assert list(rows) == [
        {"place": "1", "bib": "645", "name": "Cormac Whitten", "gun_seconds": "32:51"}
    ]


def test_an_unknown_header_is_named_rather_than_guessed_at() -> None:
    page = (
        "<pre>POS   BIB   NAME              SPLIT  \n"
        "----- ----- ----------------- -------\n"
        "    1   645 Cormac Whitten      32:51\n"
        "</pre>"
    )
    with pytest.raises(parse.UnknownColumns) as caught:
        parse.parse_tables(page)
    assert caught.value.headers == ("SPLIT",)
    assert "SPLIT" in str(caught.value)


def test_a_page_with_no_pre_block_yields_nothing() -> None:
    assert parse.parse_tables("<html><body><p>Results to follow.</p></body></html>") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("32:51", 1971.0),
        ("1:15:42", 4542.0),
        ("50:28", 3028.0),
        ("3:30:19", 12619.0),
        ("32:51.4", 1971.4),
        ("", None),
        ("DNF", None),
        ("DNS", None),
        ("-", None),
        ("1:2:3:4", None),
    ],
)
def test_times_parse_or_refuse(text: str, expected: float | None) -> None:
    assert parse.seconds(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cormac Whitten (ANER)", ("Cormac Whitten", "ANER")),
        ("Perpetua Sled", ("Perpetua Sled", None)),
        ("Ignatius Hale-Ford (PRCA)", ("Ignatius Hale-Ford", "PRCA")),
        ("Bree Tullamore (nee Vance)", ("Bree Tullamore (nee Vance)", None)),
    ],
)
def test_a_club_is_taken_off_the_name_and_a_parenthesis_is_not(
    text: str, expected: tuple[str, str | None]
) -> None:
    """Only a short upper-case code is a club. A name is not ours to edit."""
    assert parse.name_and_club(text) == expected


def test_the_general_layouts_sex_column_splits_into_sex_and_place() -> None:
    assert parse.sex_and_place("M(1)") == ("M", 1)
    assert parse.sex_and_place("F(191)") == ("F", 191)
    assert parse.sex_and_place("") == (None, None)


def test_the_telys_class_column_splits_into_three() -> None:
    assert parse.class_placing("M25-29     1") == ("M", "25-29", 1)
    assert parse.class_placing("F40-44   266") == ("F", "40-44", 266)
    assert parse.class_placing("nonsense") == (None, None, None)


def test_both_layouts_produce_the_same_shape_of_result(
    general_page: str, tely_page: str
) -> None:
    """The two layouts disagree about where sex lives; a Result does not."""
    general = records.to_results(general_page, "general")[0]
    tely = records.to_results(tely_page, "tely")[0]
    for row in (general, tely):
        assert row.sex == "M"
        assert row.place == 1
        assert row.name == "Cormac Whitten"
        assert row.seconds is not None
    assert general.age_band == "30-39"
    assert tely.age_band == "25-29"
    assert general.club == "ANER"
    assert tely.club is None


def test_a_chip_time_beats_the_gun_time(tely_page: str) -> None:
    """Only the Tely records both, and the chip time is the one the runner ran."""
    slowest = records.to_results(tely_page, "tely")[-1]
    assert slowest.gun_seconds == pytest.approx(12619.0)
    assert slowest.chip_seconds == pytest.approx(12324.0)
    assert slowest.seconds == slowest.chip_seconds


def test_a_result_with_no_time_is_not_a_finish() -> None:
    page = (
        "<pre>POS   BIB   NAME              TIME   \n"
        "----- ----- ----------------- -------\n"
        "    1   645 Cormac Whitten        DNF\n"
        "</pre>"
    )
    row = records.to_results(page, "race")[0]
    assert row.seconds is None
    assert not row.finished


# --- the real pages, when the cache has them --------------------------------------


@pytest.mark.parametrize(
    ("page", "finishers"),
    [
        ("rr_2025_20251005-turkey-tea-10k.php.html", 332),
        ("rr_2025_20251019-c2c-20km.php.html", 459),
        ("rr_2025_20250622-tely10-results.php.html", 4094),
    ],
)
def test_the_real_pages_yield_every_finisher(page: str, finishers: int) -> None:
    """Volume is the thing a golden fixture cannot check: one table, every row, no drift."""
    tables = parse.parse_tables(cached(page))
    assert len(tables) == 1
    assert len(tables[0].rows) == finishers
    assert [int(row["place"]) for row in tables[0].rows] == list(range(1, finishers + 1))
