"""Reading a results file an organiser sends, rather than a page this project fetched.

WHY THIS EXISTS
---------------
Some races are not on nlaa.ca. The 2026 Tely 10 is the one that matters: 4,000-odd
finishers in June 2026, the largest field in the province and the most recent big race
before Cape to Cabot in October, and 72% of the Cape to Cabot entrants have run a Tely
before. It was timed on a commercial platform whose terms do not permit this project to
extract it (`docs/data-terms.md`), and the association that owns the race can export it
in one click.

So this module reads a file rather than a site. It takes whatever the timing platform
exports, maps its columns onto the same `Result` rows every other source produces, and
refuses to guess at a column it does not recognise, exactly as the page parser does.

⚠️ **A file arrives with no provenance of its own**, so `load` records who sent it and
when into the import note beside it, and `docs/data-terms.md` carries the permission. A
results file with no recorded source is not usable by this project: the whole claim is
that a published number can be traced to where it came from.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from finishline.identity.normalise import clean
from finishline.ingest import parse
from finishline.schema import Result

# Column names seen in timing-platform exports, flattened the same way the page parser
# flattens a header. Extend deliberately, with a fixture, the way CANONICAL is extended.
COLUMNS: dict[str, str] = {
    "place": "place",
    "overall place": "place",
    "overall": "place",
    "pos": "place",
    "rank": "place",
    "bib": "bib",
    "bib bib": "bib",
    "bib number": "bib",
    "name": "name",
    "full name": "name",
    "athlete": "name",
    "first name": "first_name",
    "last name": "last_name",
    "gender": "sex",
    "sex": "sex",
    "division": "age_band",
    "category": "age_band",
    "age group": "age_band",
    "age category": "age_band",
    "class": "age_band",
    "city": "hometown",
    "hometown": "hometown",
    "location": "hometown",
    "club": "club",
    "team": "club",
    "chip time": "chip_seconds",
    "net time": "chip_seconds",
    "time": "gun_seconds",
    "gun time": "gun_seconds",
    "clock time": "gun_seconds",
    "finish time": "gun_seconds",
    "gender place": "sex_place",
    "division place": "category_place",
    "category place": "category_place",
}

# Columns a timing export carries that this project has no use for. Named rather than
# ignored wholesale, so a genuinely unrecognised column still stops the import.
IGNORED: frozenset[str] = frozenset(
    {
        "age", "email", "phone", "address", "postal code", "zip", "country", "state",
        "province", "registration id", "wave", "corral", "shirt size", "t shirt size",
        "emergency contact", "pace", "avg pace", "splits", "status", "bib bib number",
    }
)


class UnknownColumns(parse.ParseError):
    """A column this importer will not guess at."""

    def __init__(self, headers: tuple[str, ...]) -> None:
        self.headers = headers
        super().__init__(
            "unrecognised columns "
            + ", ".join(repr(h) for h in headers)
            + ". Add them to resultsfile.COLUMNS, or to IGNORED if they carry nothing this "
            "project uses, rather than letting the rows land in the wrong fields."
        )


@dataclass(frozen=True, slots=True)
class Import:
    """A results file, and where it came from."""

    race_id: str
    source: str
    received: str
    results: list[Result]


def _mapped(header: list[str]) -> dict[int, str]:
    """Which column of the file feeds which field, refusing anything unrecognised."""
    mapping: dict[int, str] = {}
    unknown: list[str] = []
    for index, raw in enumerate(header):
        key = parse.flatten_header(raw)
        if not key or key in IGNORED:
            continue
        if key in COLUMNS:
            mapping[index] = COLUMNS[key]
        else:
            unknown.append(raw)
    if unknown:
        raise UnknownColumns(tuple(unknown))
    return mapping


def _name_of(row: dict[str, str]) -> str:
    """One name, whether the file gives it whole or in two columns."""
    if whole := row.get("name"):
        return clean(whole)
    parts = [row.get("first_name", ""), row.get("last_name", "")]
    return clean(" ".join(part for part in parts if part))


def parse_rows(text: str, race_id: str) -> list[Result]:
    """Every finisher in a delimited results export."""
    reader = csv.reader(text.splitlines(), dialect=csv.Sniffer().sniff(text[:4096]))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []
    mapping = _mapped(rows[0])

    results: list[Result] = []
    for raw in rows[1:]:
        row = {
            mapping[index]: cell
            for index, cell in enumerate(raw)
            if index in mapping and cell.strip()
        }
        name = _name_of(row)
        if not name:
            continue
        cleaned, club = parse.name_and_club(name)
        sex = (row.get("sex") or "").strip()[:1].upper() or None
        results.append(
            Result(
                race_id=race_id,
                place=parse.integer(row.get("place", "")),
                bib=parse.integer(row.get("bib", "")),
                name=cleaned,
                club=club or (clean(row["club"]) if row.get("club") else None),
                sex=sex if sex in {"M", "F"} else None,
                sex_place=parse.integer(row.get("sex_place", "")),
                age_band=clean(row.get("age_band", "")) or None,
                category_place=parse.integer(row.get("category_place", "")),
                hometown=clean(row.get("hometown", "")) or None,
                gun_seconds=parse.seconds(row.get("gun_seconds", "")),
                chip_seconds=parse.seconds(row.get("chip_seconds", "")),
            )
        )
    return results


def load(path: Path, race_id: str, *, source: str, received: str) -> Import:
    """A results file, with the record of where it came from attached.

    `source` names who supplied it and under what permission, and `received` is the date.
    Both end up in `docs/data-terms.md`; neither is optional, because a number this
    project publishes has to be traceable to the bytes it came from.
    """
    if not source.strip() or not received.strip():
        raise ValueError(
            "a results file needs a recorded source and date; see docs/data-terms.md"
        )
    return Import(
        race_id=race_id,
        source=source,
        received=received,
        results=parse_rows(path.read_text(encoding="utf-8-sig", errors="replace"), race_id),
    )
