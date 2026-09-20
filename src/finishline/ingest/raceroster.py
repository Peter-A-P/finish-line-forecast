"""Races that are not on nlaa.ca, read from the timing platform the organiser used.

WHY THERE IS A SECOND SOURCE AT ALL
-----------------------------------
The 2026 Tely 10 is the largest field in the province, 4,147 finishers in June, four
months before the first race this project predicts, and 72% of the Cape to Cabot entrants
have run a Tely at some point. It is the single most valuable result in the archive and it
is not in the archive: the association timed it on Race Roster in 2026 and its own Tely
page links out rather than publishing the results itself, as it did every year from 2018
to 2025.

THE BASIS FOR READING IT, WHICH IS NOT "IT WAS POSSIBLE"
--------------------------------------------------------
Recorded in full in `docs/data-terms.md`, and in short:

- **The association owns the race and the data.** Race Roster is its timing vendor. Every
  other edition of this race is published by the association on its own site, in public,
  with the same columns.
- **The association was told.** Peter wrote to them before any of this, saying he intended
  to use the Tely data for this project, and they can say stop at any point.
- **The results host invites crawlers**: `results.raceroster.com/robots.txt` allows
  `User-agent: *`, and the results are public with no login.
- **One request, not four thousand.** The listing endpoint takes a limit, and the
  application's own "show all" path uses a single call, so that is what this does. The
  payload is written to the cache and read from disk forever after.

⚠️ **This is a judgement, and it is Peter's rather than the code's.** An earlier read of
the same facts said no, on the grounds that the platform's own terms are broad. What
changed it is the ownership: the results are the association's, published by them
everywhere else, and taken here with their knowledge. The reasoning is written down so
that a reader can disagree with it, which they could not do if it were unstated.

⚠️ **Nothing fetched here is committed.** `data/cache/` is gitignored. The registry below
is committed, because which races were read from where is part of the published claim.
"""

from __future__ import annotations

import hashlib
import json
import ssl
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import truststore

from finishline.identity.normalise import clean
from finishline.ingest import parse
from finishline.schema import Race, Result

BASE = "https://results.raceroster.com/v2/api"
RESULTS = BASE + "/result-events/{event_id}/sub-events/{sub_event_id}/results"
TIMEOUT = 60.0

# Both names, for the reason in `nlaa.USER_AGENT`: the organiser was told about this
# project under its first one.
USER_AGENT = (
    "finishline/0.1 (The Whole Field, Called Before the Gun, formerly Finish Line Forecast, "
    "a personal running-analytics project using NLAA race results with the organiser's "
    "knowledge; one request per race; peter.alexander.parker@outlook.com)"
)


@dataclass(frozen=True, slots=True)
class External:
    """A race read from a timing platform rather than from the association's own pages.

    Committed, because which races came from where is part of what this project claims.
    `basis` is the one-line reason it was read at all, and it is printed in the report.
    """

    race_id: str
    name: str
    date: date
    distance_m: float
    course_id: str
    event_id: int
    sub_event_id: int
    url: str
    basis: str

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
        return f"{self.race_id}_results.json"


# The register of races read from elsewhere. One entry so far.
REGISTER: tuple[External, ...] = (
    External(
        race_id="20260628-tely10-results",
        name="Tely 10 Mile Road Race - Individual Results",
        date=date(2026, 6, 28),
        distance_m=10 * 1609.344,
        course_id="tely-10-16093",
        event_id=104891,
        sub_event_id=297123,
        url="https://results.raceroster.com/v3/events/jwnadebsh5bdru7c/race/297123",
        basis=(
            "NLAA's own race and data, published by them for every other edition, read "
            "with their knowledge; see docs/data-terms.md"
        ),
    ),
)


def fetch(race: External, cache_dir: Path, *, refetch: bool = False) -> dict[str, Any]:
    """This race's results, from disk when they are there and the network when not.

    One request for the whole field. The endpoint accepts a limit and the platform's own
    listing page asks for everything in a single call, so paginating would mean forty
    requests where one does, which is worse manners rather than better.
    """
    path = cache_dir / race.cache_name
    if path.exists() and not refetch:
        return _loaded(path)

    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=TIMEOUT,
        follow_redirects=True,
        verify=context,
    ) as client:
        response = client.get(
            RESULTS.format(event_id=race.event_id, sub_event_id=race.sub_event_id),
            params={"start": 0, "limit": 10000},
        )
        response.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    _record(race, path, response.content, cache_dir)
    return _loaded(path)


def _loaded(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _record(race: External, path: Path, body: bytes, cache_dir: Path) -> None:
    """Leave the same trail the page crawler leaves: what, from where, when, and its hash."""
    row = {
        "race_id": race.race_id,
        "url": RESULTS.format(event_id=race.event_id, sub_event_id=race.sub_event_id),
        "path": path.name,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "basis": race.basis,
    }
    with (cache_dir / "manifest.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")


def _sex(value: str) -> str | None:
    """"Male" or "Female" as the one letter every other source uses."""
    first = value.strip()[:1].upper()
    return first if first in {"M", "F"} else None


def to_results(payload: dict[str, Any], race_id: str) -> list[Result]:
    """The platform's rows as the same `Result` records the pages produce.

    The columns line up one for one with what the association prints on its own Tely
    pages: place, bib, name, gun time, division, division place, gender, gender place,
    pace and chip time. `division` is "M25-29" and `divisionPlace` is "1 / 285", both of
    which the page parser already knows how to read.
    """
    results: list[Result] = []
    for row in payload.get("data", []):
        name, club = parse.name_and_club(clean(str(row.get("name") or "")))
        if not name:
            continue
        code_sex, band = parse.class_code(str(row.get("division") or ""))
        results.append(
            Result(
                race_id=race_id,
                place=parse.integer(str(row.get("overallPlace") or "")),
                bib=parse.integer(str(row.get("bib") or "")),
                name=name,
                club=club,
                sex=_sex(str(row.get("genderSexId") or "")) or code_sex,
                sex_place=parse.place_of(str(row.get("genderPlace") or "")),
                age_band=band,
                category_place=parse.place_of(str(row.get("divisionPlace") or "")),
                hometown=clean(str(row.get("fromCity") or "")) or None,
                gun_seconds=parse.seconds(str(row.get("gunTime") or "")),
                chip_seconds=parse.seconds(str(row.get("chipTime") or "")),
            )
        )
    return results


def load(race: External, cache_dir: Path) -> list[Result]:
    """This race's finishers, fetching once if the cache does not have them."""
    return to_results(fetch(race, cache_dir), race.race_id)
