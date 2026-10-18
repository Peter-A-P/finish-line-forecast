"""Results Athletics NorthEAST posts on its own sites before the association republishes them.

WHY
---
The 2026 Uniformed Services Run was timed by Athletics NorthEAST, which posts overall finish
lists on its own site the week of the race; the association republishes them on nlaa.ca
later. This project needs them before Cape to Cabot: they are the freshest results in the
province, and they are what the saved USR start list is scored against for the no-show and
name-match rates (docs/todo.md).

THE BASIS
---------
Athletics NorthEAST is already a source here (its entrant lists, docs/data-terms.md), it
timed and published these results itself, and Peter wrote to it before they were read. Each
page is fetched once, at the crawler's pace and under its name, and kept in
`data/cache/ane/`, which is gitignored.

Cape to Cabot is the club's race, and its timer posts the overall list on the race's own site,
`capetocabot.com`, the morning of the race (added 2026-10-18, at Peter's request, to score the
prediction the same day). That list prints a gender, an age group and a club as well; no
hometown.

⚠️ **Superseded the moment the association posts the same race.** When nlaa.ca carries an
edition on the same date and course, `store.build` drops the copy from here, so one race is
never counted twice and the association's page, with its sex and age columns, wins.

⚠️ **The USR pages print no sex, no age and no hometown.** Only a place, a name, a service
affiliation ("Badge"), a bib and the times. The affiliation is not a hometown or a club and
is not read. The resolver treats a missing sex or age as no information, so these results
join a runner's history by name alone where nothing contradicts it, which is weaker
evidence than any other source here gives it. A list whose header names a Gender, an Age
Group or a Club column (Cape to Cabot's) has those read as printed; no list prints a hometown.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import truststore

from finishline.identity.normalise import clean
from finishline.ingest import parse
from finishline.ingest.nlaa import TIMEOUT, USER_AGENT, decode
from finishline.schema import HALF_MARATHON_M, MARATHON_M, Race, Result

BASE = "https://www.athleticsnortheast.com/"


@dataclass(frozen=True, slots=True)
class Posted:
    """One overall finish list on the Athletics NorthEAST site."""

    race_id: str
    name: str
    date: date
    distance_m: float
    course_id: str
    page: str  # the page's name on the site, as its URL spells it
    site: str = BASE  # the club's own site, or the race's

    @property
    def url(self) -> str:
        return self.site + self.page.replace(" ", "%20") + ".htm"

    @property
    def race(self) -> Race:
        return Race(
            race_id=self.race_id,
            name=self.name,
            date=self.date,
            distance_m=self.distance_m,
            course_id=self.course_id,
            url=self.url,
        )

    @property
    def cache_name(self) -> str:
        return self.page.replace(" ", "-") + ".htm"


_USR = date(2026, 9, 13)
_C2C = date(2026, 10, 18)

# Committed, because which races were read from where is part of the published claim.
# ⚠️ The 2026 marathon and half are new routes (`nlaa.SAME_ROUTE`) and keep `usr-42195` and
# `usr-21097`, which have no history before them; the 5k has no earlier edition at all.
REGISTER: tuple[Posted, ...] = (
    Posted("20260913-usr-marathon-ane", "USR Marathon", _USR, MARATHON_M, "usr-42195",
           "USR Marathon Overall"),
    Posted("20260913-usr-half-ane", "USR Half Marathon", _USR, HALF_MARATHON_M, "usr-21097",
           "USR Half Overall"),
    Posted("20260913-usr-10k-ane", "USR Quidi Vidi Brewery 10k", _USR, 10_000.0,
           "usr-10000", "USR 10k Overall"),
    Posted("20260913-usr-5k-ane", "USR 5k", _USR, 5_000.0, "usr-5000", "USR 5k Overall"),
    Posted("20261018-c2c-20km-ane", "Capital Subaru Cape to Cabot 20k", _C2C, 20_000.0,
           "cape-to-cabot-20000", "Cape_to_Cabot_Live_Results", "https://www.capetocabot.com/"),
)


def posted_for(when: date, course_id: str) -> Posted | None:
    """The club's list for this date and course, if it posted one."""
    return next(
        (p for p in REGISTER if p.date == when and p.course_id == course_id), None
    )

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
# "1:20-29" and "1: 0-19" in Cape to Cabot's Age Group column: the place within the group, then
# the group, kept as printed.
_GROUP = re.compile(r"^(?P<place>\d+):\s*(?P<band>\d{1,2}-\d{1,3}|U\d{1,2}|\d{1,2}\+)$")


def _printed(cells: list[str], column: dict[str, int], header: str) -> str | None:
    """The cell under this header on one row, or None if the list has no such column."""
    i = column.get(header)
    return (cells[i] or None) if i is not None and i < len(cells) else None


def to_results(page: str, race_id: str) -> list[Result]:
    """Every finisher on one overall list.

    Data rows start with a place. The columns before the times vary by race (the longer
    ones print splits and a division), but every list ends with the chip time and then the
    gun time, so those are read from the end. A Gender, Age Group or Club column is read where
    the header row names one; a Badge never is.
    """
    results: list[Result] = []
    column: dict[str, int] = {}
    for row in _ROW.findall(page):
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", cell))) for cell in _CELL.findall(row)]
        if cells and cells[0] == "Place":
            column = {cell.lower(): i for i, cell in enumerate(cells) if cell}
            continue
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        name = cells[1]
        if not name:
            continue
        sex = _printed(cells, column, "gender")
        group = _GROUP.match(_printed(cells, column, "age group") or "")
        results.append(
            Result(
                race_id=race_id,
                place=int(cells[0]),
                bib=parse.integer(cells[3]),
                name=name,
                club=_printed(cells, column, "club"),
                sex=sex if sex in ("M", "F", "X") else None,
                sex_place=None,
                age_band=group["band"] if group else None,
                category_place=int(group["place"]) if group else None,
                hometown=None,
                gun_seconds=parse.seconds(cells[-1]),
                chip_seconds=parse.seconds(cells[-2]),
            )
        )
    return results


def fetch(posted: Posted, cache_dir: Path) -> str:
    """The page from disk, or fetched once and kept there."""
    path = cache_dir / posted.cache_name
    if path.exists():
        return decode(path.read_bytes())
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True, verify=context
    ) as client:
        response = client.get(posted.url)
        response.raise_for_status()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    row = {
        "race_id": posted.race_id,
        "url": posted.url,
        "path": path.name,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    with (cache_dir / "manifest.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")
    return decode(path.read_bytes())


def load(posted: Posted, cache_dir: Path) -> list[Result]:
    """This list's finishers, fetching once if the cache does not have it."""
    return to_results(fetch(posted, cache_dir), posted.race_id)
