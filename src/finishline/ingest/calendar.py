"""What is being run this year, from the association's own calendar of events.

WHY
---
The website's list of races used to be whatever a person had last typed into
`data/live.toml`. That file is the right source for the races this project *predicts*, and
the wrong source for the question a reader actually asks, which is what is on this year. It
cannot say that the Trapline is on in three weeks, it cannot notice that a race moved, and
it goes stale the day a race is cancelled. `https://www.nlaa.ca/calendar.php` is the only
public statement of the year's fixtures, and it is on the same site, under the same terms,
as the results this project already reads (docs/data-terms.md).

⚠️ **This page is alive, like an entrant list and unlike a results page.** A results page is
written once and never changes, so the results cache fetches it once and keeps it forever.
The calendar gains and loses races all year, so the cached copy is not the truth: `fetch`
always re-fetches, and the copy on disk is replaced rather than kept as a series. It holds
nothing about any person, so unlike the entrant snapshots the file it writes is committed.

⚠️ **A calendar entry is not a race.** The results index has one row per race per distance,
so its row is a race. The calendar has one row per *day*: "Uniformed Services Run
Marathon/Half-Marathon/Marathon Relay/5km/10km" is one entry and five races, and the
Trapline is one entry and four. So an entry here carries a course family and a date, never a
distance, and nothing downstream may treat it as a single race.

⚠️ **"Relay" does not disqualify an entry here, and it does disqualify a results row.** On
the results index a row that says relay *is* the relay, and `nlaa.NOT_ROAD` is right to drop
it. On the calendar the word is one component of a day that also has a marathon and a 10 km,
and dropping the entry would lose the whole USR. The words that genuinely mean "not this
sport at all" (cross-country, trail, a schools meet) are kept apart from the words that only
name one component of a day (`_ANOTHER_SPORT` against `nlaa.NOT_ROAD`).

⚠️ **Nothing is guessed.** An entry that matches no course this project knows is reported as
unrecognised by `finishline calendar` rather than filed under a derived slug. The skip list
is the coverage claim, the same as it is for the results catalogue: a reader has to be able
to see that the calendar had forty rows and this took fourteen, and why the other twenty-six
went.
"""

from __future__ import annotations

import html
import re
import ssl
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import truststore

from finishline.ingest.nlaa import COURSE_ALIASES, MIN_INTERVAL, NOT_ROAD, TIMEOUT, USER_AGENT

URL = "https://www.nlaa.ca/calendar.php"

# The day the first entrant-list snapshot was taken, which is the day this project started
# watching races rather than reading an archive of them. A race before it is history; a race
# after it is one this project could in principle have predicted, and the website says so.
WATCHING_SINCE = date(2026, 9, 12)

# The calendar is one table, one row per entry: a date badge, a linked event name, and the
# place after the link. The year is in the table's own heading and nowhere else.
_ROW = re.compile(r"<tr><td>(.*?)</td></tr>", re.DOTALL)
_HEADING = re.compile(r"<th>[^<]*Calendar[^<]*?(\d{4})\s*</th>", re.IGNORECASE)
_BADGE = re.compile(r'<span class="badge[^"]*">(.*?)</span>', re.DOTALL)
_LINK = re.compile(r"<a\s[^>]*href=['\"]([^'\"]*)['\"][^>]*>(.*?)</a>", re.DOTALL)

# ⚠️ **Track and field, in the association's own words.** The calendar is mostly track: meets,
# camps, clinics, tetrathlons and the summer games. None of it is a road race, and three of
# them ("Pearlgate Twilight Meet", "Pearlgate Tetrathlons", "Pearlgate Memorial Meet") carry
# the name of a venue that is also a road-race course, so the alias test alone files them as
# road races. This runs first for that reason.
_TRACK_AND_FIELD = re.compile(
    r"\b(track|field|trackfest|tetrathlons?|twilight|clinic|camp|games|indoor"
    r"|all[- ]comers|meet)\b",
    re.IGNORECASE,
)

# The words that mean a different sport rather than one component of a road-racing day.
# Everything else `nlaa.NOT_ROAD` matches (relay, walk, kids, teams, awards) is a component,
# and the module docstring says why the distinction has to exist here and not there.
_ANOTHER_SPORT = re.compile(r"\b(trail|cross[- ]country|\bxc\b|school)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Event:
    """One row of the calendar: a day, a name, a place, and what it is."""

    # Named `when` rather than `date`, so that the `end` field below can still be annotated
    # with the type this module imports. A dataclass field shadows the name for every
    # annotation after it.
    when: date
    name: str
    place: str
    url: str | None
    # The course family the name gives (`nlaa.COURSE_ALIASES`), without a distance, because
    # a calendar entry can be four races on one road. None when nothing matched.
    family: str | None
    # The last day, for the entries the calendar prints as a range. None for a single day.
    end: date | None = None
    # Why this entry is not a road race, or None when it is.
    skipped: str | None = None

    @property
    def road(self) -> bool:
        return self.skipped is None


def classify(name: str) -> tuple[str | None, str | None]:
    """The course family this entry names, or why it is not a road race.

    Returns `(family, None)` for a road race and `(None, reason)` for anything else. The
    order is the whole design: the track exclusion runs before the alias test because three
    track meets carry a road course's venue name, and the component words (relay, walk) are
    never consulted at all.
    """
    if match := _ANOTHER_SPORT.search(name):
        return None, f"a different sport ({match.group(0).lower()})"
    if match := _TRACK_AND_FIELD.search(name):
        return None, f"track and field ({match.group(0).lower()})"
    lowered = name.lower()
    for phrase, alias in COURSE_ALIASES:
        if phrase in lowered:
            return alias, None
    return None, "no course this project knows is named here"


def _dates(badge: str, year: int) -> tuple[date, date | None]:
    """The day, and the last day when the calendar prints a range.

    The badge reads "Sun, Oct 4" or "Fri, Jun 5-Sat, Jun 6". The weekday is printed and is
    not read: it is the month and the day that carry the date, and trusting the weekday
    would break on the first year the association typed one wrong.
    """
    parts = [part.strip() for part in badge.split("-") if part.strip()]
    parsed: list[date] = []
    for part in parts:
        text = part.split(",", 1)[-1].strip()
        for fmt in ("%b %d", "%B %d"):
            try:
                parsed.append(datetime.strptime(f"{text} {year}", f"{fmt} %Y").date())
                break
            except ValueError:
                continue
    if not parsed:
        raise ValueError(f"no date in calendar badge {badge!r}")
    return parsed[0], parsed[1] if len(parsed) > 1 else None


def _text(markup: str) -> str:
    """Markup as the page reads it, with the non-breaking spaces the link icons leave."""
    return html.unescape(re.sub(r"<[^>]+>", " ", markup)).replace("\xa0", " ").strip()


def parse(page: str) -> tuple[int, list[Event]]:
    """The calendar's year, and every row on it, road races and skips alike.

    ⚠️ **The skips come back too.** They are the coverage claim: a reader has to be able to
    see that the page had forty rows and fourteen of them were road races, and why the rest
    were not. `finishline calendar` prints them.
    """
    heading = _HEADING.search(page)
    if heading is None:
        raise ValueError("the calendar page has no year in its heading; the layout moved")
    year = int(heading.group(1))

    events: list[Event] = []
    for row in _ROW.findall(page):
        badge = _BADGE.search(row)
        if badge is None:
            continue
        link = _LINK.search(row)
        if link is None:
            name, url, after = _text(row.split("</span>", 1)[-1]), None, ""
        else:
            url = link.group(1)
            name = _text(link.group(2))
            after = _text(row.split("</a>", 1)[-1])
        name = name.strip(" ,")
        if not name:
            continue
        when, end = _dates(_text(badge.group(1)), year)
        family, skipped = classify(name)
        events.append(
            Event(
                when=when,
                name=name,
                place=after.strip(" ,"),
                url=url,
                family=family,
                end=end,
                skipped=skipped,
            )
        )
    return year, events


def fetch(path: Path) -> str:
    """Read the calendar now, at the crawler's pace and under its name, and keep a copy.

    ⚠️ **Always a request.** There is no cache-hit path, by design: a calendar read from disk
    is last week's fixtures, and the whole reason this source exists is that `live.toml` went
    stale. One request per run of `finishline calendar`, which is not on a schedule.
    """
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True, verify=context
    ) as client:
        time.sleep(MIN_INTERVAL)
        response = client.get(URL)
        response.raise_for_status()
    body = response.text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return body


def road_races(events: Sequence[Event]) -> Iterator[Event]:
    return (event for event in events if event.road)


def record(
    year: int, events: Sequence[Event], *, fetched_at: datetime | None = None
) -> dict[str, Any]:
    """The calendar as `data/calendar.json` keeps it, for the website to read.

    Every row is here, road race or not, with the reason beside the ones that are not, so the
    file is the whole page and not a filtered view somebody has to take on trust.
    """
    when = fetched_at or datetime.now(UTC)
    return {
        "source": URL,
        "year": year,
        "fetched_at": when.isoformat(timespec="seconds"),
        "watching_since": WATCHING_SINCE.isoformat(),
        "events": [
            {
                "date": event.when.isoformat(),
                "end": None if event.end is None else event.end.isoformat(),
                "name": event.name,
                "place": event.place,
                "url": event.url,
                "family": event.family,
                "skipped": event.skipped,
            }
            for event in sorted(events, key=lambda item: (item.when, item.name))
        ],
    }


def unread(events: Sequence[Event]) -> list[Event]:
    """The rows that are not road races, in the order the reasons should be read.

    Unrecognised first, because that is the one a reader has to act on: a new road race the
    aliases do not know yet looks exactly like this, and it is the only skip that is ever a
    bug rather than a fact about the sport.
    """
    rest = [event for event in events if not event.road]
    return sorted(
        rest,
        key=lambda event: (not str(event.skipped).startswith("no course"), event.when),
    )


# `NOT_ROAD` is imported so that a reader of this module can see what it deliberately does
# not use, and so that a rename there fails here rather than silently changing what is read.
_COMPONENT_WORDS = NOT_ROAD
