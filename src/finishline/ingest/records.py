"""Turning parsed text cells into typed results.

`parse.py` answers "what did the page say"; this answers "what does it mean". The split
matters because the first question has one right answer and the second has judgement in
it, and the judgement is all here where it can be read.
"""

from __future__ import annotations

from finishline.identity.normalise import clean
from finishline.ingest import parse
from finishline.schema import Result


def to_result(row: dict[str, str], race_id: str) -> Result:
    """One parsed row as a typed result.

    The two layouts disagree about where sex and the age band live, and this is the only
    place that knows it. The general layout prints sex with its place ("M(1)") and the
    band in its own column; the Tely prints all three in one ("M25-29     1") and puts
    the overall place within sex in a separate column. Both land in the same fields.
    """
    sex, sex_place = parse.sex_and_place(row.get("sex_and_place", ""))
    age_band = row.get("age_band") or None
    category_place = parse.integer(row.get("category_place", ""))

    if "class_placing" in row:
        class_sex, class_band, class_place = parse.class_placing(row["class_placing"])
        sex = sex or class_sex
        age_band = age_band or class_band
        category_place = category_place if category_place is not None else class_place
    if "sex_place" in row:
        sex_place = parse.integer(row["sex_place"])

    name, club = parse.name_and_club(row.get("name", ""))
    hometown = clean(row.get("hometown", "")) or None
    return Result(
        race_id=race_id,
        place=parse.integer(row.get("place", "")),
        bib=parse.integer(row.get("bib", "")),
        name=clean(name),
        club=club,
        sex=sex,
        sex_place=sex_place,
        age_band=age_band,
        category_place=category_place,
        hometown=hometown,
        gun_seconds=parse.seconds(row.get("gun_seconds", "")),
        chip_seconds=parse.seconds(row.get("chip_seconds", "")),
    )


def to_results(page: str, race_id: str) -> list[Result]:
    """Every result on a page, in the order it printed them.

    A page with several tables (a field split into sections under one header) returns
    them concatenated: the place column already orders the field and the section
    headings carry nothing a result needs.
    """
    return [
        to_result(row, race_id) for table in parse.parse_tables(page) for row in table.rows
    ]
