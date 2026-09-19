"""Results Athletics NorthEAST posts on its own site before the association republishes them.

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

⚠️ **Superseded the moment the association posts the same race.** When nlaa.ca carries an
edition on the same date and course, `store.build` drops the copy from here, so one race is
never counted twice and the association's page, with its sex and age columns, wins.

⚠️ **These pages print no sex, no age and no hometown.** Only a place, a name, a service
affiliation ("Badge"), a bib and the times. The affiliation is not a hometown or a club and
is not read. The resolver treats a missing sex or age as no information, so these results
join a runner's history by name alone where nothing contradicts it, which is weaker
evidence than any other source here gives it.
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
from finishline.ingest.nlaa import TIMEOUT, USER_AGENT
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

    @property
    def url(self) -> str:
        return BASE + self.page.replace(" ", "%20") + ".htm"

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
)

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)


def to_results(page: str, race_id: str) -> list[Result]:
    """Every finisher on one overall list.

    Data rows start with a place. The columns before the times vary by race (the longer
    ones print splits and a division), but every list ends with the chip time and then the
    gun time, so those are read from the end.
    """
    results: list[Result] = []
    for row in _ROW.findall(page):
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", cell))) for cell in _CELL.findall(row)]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        name = cells[1]
        if not name:
            continue
        results.append(
            Result(
                race_id=race_id,
                place=int(cells[0]),
                bib=parse.integer(cells[3]),
                name=name,
                club=None,
                sex=None,
                sex_place=None,
                age_band=None,
                category_place=None,
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
        return path.read_text(encoding="utf-8", errors="replace")
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
    return path.read_text(encoding="utf-8", errors="replace")


def load(posted: Posted, cache_dir: Path) -> list[Result]:
    """This list's finishers, fetching once if the cache does not have it."""
    return to_results(fetch(posted, cache_dir), posted.race_id)
