"""Reading nlaa.ca: the year index, the race catalogue, and a cache that fetches once.

THE MANNERS ARE PART OF THE DESIGN
----------------------------------
The Newfoundland and Labrador Athletics Association publishes every road result back to
1978 on a small site with no terms page, no `robots.txt` and, judging by the markup, no
budget for bandwidth. This project needs about three hundred of those pages, once. So:

- one request at a time, never concurrent, with at least `MIN_INTERVAL` seconds between
  the end of one and the start of the next;
- a user agent that says what this is and how to reach the person running it, because an
  administrator who wants it to stop should not have to guess;
- every page written to disk on arrival and read from disk forever after, so a rerun of
  the whole pipeline costs zero requests;
- the SHA-256 and the fetch time recorded per page, so a number published in October can
  be traced to the bytes it was computed from.

⚠️ **Nothing in `data/cache/` is committed.** The pages carry thousands of identifiable
people, and the repository publishes only predictions. `.gitignore` enforces it; this
note is here because the reason is not obvious from the filename.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Self

import httpx
import truststore

from finishline.identity.normalise import clean
from finishline.schema import HALF_MARATHON_M, MARATHON_M, MILE_M, Race

BASE = "https://www.nlaa.ca/results/"
INDEX = BASE + "index.php?year={year}"

USER_AGENT = (
    "finishline/0.1 (Finish Line Forecast, a personal running-analytics project; "
    "one request per second, each page fetched once; peter.alexander.parker@outlook.com)"
)

# Seconds between requests. One a second is slower than a person clicking through the
# archive and the whole crawl still finishes inside five minutes.
MIN_INTERVAL = 1.0
TIMEOUT = 30.0

# Results this project does not model, recognised from the event name. Trail races are
# not comparable to a road course at all; relays are not individual results; the school
# cross-country series is a different discipline on grass. Each is skipped by name and
# the skip is reported, never silently dropped.
#
# ⚠️ **"Team" and "Awards" are here because one race is three pages.** Every Tely 10
# publishes its individual results, its team standings and its awards as separate rows on
# the index, all with the same date and the same distance in the name. Read as races they
# made nineteen editions of a race that has been run ten times, which is how this was
# found: a course prior would have been estimated from the same day three times over and
# the team page's runners would have entered the history twice.
NOT_ROAD = re.compile(
    r"\b(trail|relay|cross[- ]country|\bxc\b|school|kid'?s?|walk(?:ers)?"
    r"|teams?|awards?)\b",
    re.IGNORECASE,
)

# The heading over the road results, which the site renamed in 2016.
#
# ⚠️ **Every index from 2008 to 2015 calls it "Road Race Series"**, and matching only the
# current wording read eight years of the archive as having no road racing in them at all,
# silently. The same failure as the missing ruler: nothing raised, the coverage number
# simply wrong. Matching on "road" and not on the rest of the phrase is what makes it
# survive the next rename.
ROAD_SECTION = r"<h4[^>]*>\s*Road\b[^<]*</h4>(.*?)(?=<h4|\Z)"

_KM = re.compile(r"(\d+(?:\.\d+)?)\s*k(?:m\b|\b)", re.IGNORECASE)
_MILE = re.compile(r"(\d+(?:\.\d+)?)\s*mi(?:le)?s?\b", re.IGNORECASE)
_FILE_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def distance_m(event: str) -> float | None:
    """The distance an event name declares, in metres, or None when it does not.

    None is the answer for "Kid's Race Trapline (1km & 3km)", which is two races on one
    page, and for anything whose name carries no distance at all. The catalogue reports
    those rather than guessing, because a 5 km result filed as a 10 km would land in the
    history as a runner who halved their time.
    """
    text = event.lower()
    if "half marathon" in text or "half-marathon" in text:
        return HALF_MARATHON_M
    if "marathon" in text:
        return MARATHON_M

    kms = {float(m.group(1)) for m in _KM.finditer(text)}
    miles = {float(m.group(1)) for m in _MILE.finditer(text)}
    if len(kms) + len(miles) > 1:
        return None  # two distances on one page; the catalogue reports it
    if kms:
        return kms.pop() * 1000.0
    if miles:
        return miles.pop() * MILE_M
    if re.search(r"\bmile\b", text):
        return MILE_M
    return None


def why_not_read(event: str, href: str) -> str | None:
    """Why this index row is not read, or None when it is.

    ⚠️ **The two reasons are kept apart on purpose.** A team page is a different view of
    a race this project already has; a PDF is a race it does not have at all. Reported as
    one reason, the skip list said "not an individual road result, or a PDF" for both,
    and a reader could not tell a duplicate from a hole. The skip list is the coverage
    claim, so it has to distinguish them.

    ⚠️ **Only PDFs are excluded by extension, not everything that is not `.php`.** The
    2017 Turkey Tea is published as `.htm` and is a road race like any other; filtering
    on the extension dropped it for a reason that has nothing to do with its contents. A
    file extension is not evidence about a layout, and the parser already refuses loudly
    on a layout it does not know, so the decision belongs there. A PDF is genuinely not
    text and stays out.
    """
    if match := NOT_ROAD.search(event):
        return f"not an individual road result ({match.group(0).lower()})"
    if href.lower().endswith(".pdf"):
        return "results published as a PDF, which this does not read"
    return None


def is_road(event: str, href: str) -> bool:
    """Whether this row is an individual road result this project reads."""
    return why_not_read(event, href) is None


def race_id(href: str, event: str) -> str:
    """A stable id for one edition: its date and the page that holds it."""
    stem = href.rsplit("/", 1)[-1].removesuffix(".php")
    return stem if _FILE_DATE.match(stem) else f"{event.lower().replace(' ', '-')}-{stem}"


# The event a name belongs to, found by a phrase that survives the sponsor.
#
# ⚠️ **The sponsor is in the event name and changes every few years.** The same road up
# Signal Hill has been the "Cape to Cabot 20km" and the "Capital Subaru Cape to Cabot
# 20km"; the 10 km in Mount Pearl has been the "Turkey Tea" under three different
# sponsors. Deriving a course from the whole name splits one course into several, and a
# course effect estimated on four editions instead of nineteen is a wider prior for no
# reason. So the match is on the part of the name that is the race rather than the
# cheque. Extended from the crawl: `finishline catalogue --skips` prints every event
# name that fell through to the derived slug.
COURSE_ALIASES: tuple[tuple[str, str], ...] = (
    ("cape to cabot", "cape-to-cabot"),
    ("tely", "tely-10"),
    ("turkey tea", "turkey-tea"),
    ("mundy pond", "mundy-pond"),
    ("flat out", "flat-out"),
    ("mews", "mews-memorial"),
    ("five & dime", "five-and-dime"),
    ("five and dime", "five-and-dime"),
    ("run from away", "run-from-away"),
    ("trapline", "trapline"),
    ("woodward", "trapline"),
    ("uniformed services", "usr"),
    ("usr", "usr"),
    ("run to remember", "run-to-remember"),
    ("run 2 remember", "run-to-remember"),
    ("huffin", "huffin-puffin"),
    # From 2008 to 2015 the index titles races with an ordinal and whichever sponsor held
    # the naming rights that year, so these courses fragmented into single editions until
    # the archive was widened. The phrase that survives is the place.
    ("burton", "burtons-pond"),
    ("chcm", "chcm"),
    ("blueberry harvest", "blueberry-harvest"),
    ("harbour front", "harbour-front"),
    ("harbourfront", "harbour-front"),
    ("quidi vidi", "quidi-vidi"),
    ("commander gander", "commander-gander"),
    ("carved by the sea", "carved-by-the-sea"),
    ("figure 8", "prc-figure-8"),
    ("figure-8", "prc-figure-8"),
    ("not so hilly", "not-so-hilly"),
    ("bell island", "bell-island-blast"),
    ("discovery dash", "discovery-dash"),
    ("pearlgate", "pearlgate"),
    ("oceanview", "oceanview"),
    ("garnish", "garnish"),
    ("mercury", "mercury"),
    ("paradise dime", "five-and-dime"),
    ("paradise five", "five-and-dime"),
    # ⚠️ Order matters below here. "Provincial 5k championship" has been run under the
    # NLAA's own name, Nautilus's and Timex's; "open mile" and "ANE mile" are the same
    # mile. Both must be matched before the generic "provincial" and "mile" slugs are
    # derived, or the fragments come back.
    ("open mile", "ane-mile"),
    ("ane mile", "ane-mile"),
    ("provincial", "provincial-championship"),
)

# Boilerplate that says nothing about which road was run, in two tiers.
#
# Ordinals are the big one: "30th Annual Burton's Pond" and "31st Annual Burton's Pond" are
# one course, and treating them as two gives six courses of one edition where there are six
# editions of one course.
#
# ⚠️ **Sponsors are stripped only when something is left.** Some races have no name but
# their sponsor: the Toyota Plaza 15 km and the Nautilus Half-Marathon are not the Toyota
# Plaza and the Nautilus anything-else, they are those races. Stripping the sponsor from
# them leaves an empty slug, and an empty slug collapsed six unrelated half marathons into
# one course called "unknown". So the tiers are tried hardest first and the first one that
# leaves a name wins.
_ALWAYS_BOILERPLATE = re.compile(
    r"\b(\d+(st|nd|rd|th)|annual|road\s+race|race|results?|individual|open|championships?)\b"
)
_SPONSORS = re.compile(
    r"\b(timex|vocm|nautilus|molson|toyota\s+plaza|boston\s+pizza|capital\s+subaru|"
    r"penney\s+mazda|the\s+max|coors\s+light|crown\s+&\s+anchor|banished\s+brewing|"
    r"liveby\s+wealth)\b"
)


def course_id(event: str, metres: float) -> str:
    """The course an edition runs on, shared across editions and split by distance.

    The distance is part of the identity because a race that offers 5 km and 10 km runs
    two different routes from one start line, and the Trapline offers four. The event is
    matched against COURSE_ALIASES first, and falls back to a slug of the name with the
    distance and the boilerplate stripped out.
    """
    text = event.lower()
    for phrase, alias in COURSE_ALIASES:
        if phrase in text:
            return f"{alias}-{round(metres)}"
    base = re.sub(r"\d+(\.\d+)?\s*(km|k|mi|mile|miles)\b", " ", text)
    # Hardest strip first, falling back until a name survives. The distance is already part
    # of the identity, so dropping "half marathon" only costs information when it is the
    # whole name, which the last tier covers.
    for strip_distance, strip_sponsor in ((True, True), (True, False), (False, False)):
        stripped = base
        if strip_distance:
            stripped = re.sub(r"\b(half[- ]marathon|marathon)\b", " ", stripped)
            stripped = _ALWAYS_BOILERPLATE.sub(" ", stripped)
        if strip_sponsor:
            stripped = _SPONSORS.sub(" ", stripped)
        slug = re.sub(r"[^a-z0-9]+", "-", stripped).strip("-")
        if slug:
            return f"{slug}-{round(metres)}"
    return f"unknown-{round(metres)}"


def parse_index(page: str, year: int) -> list[tuple[str, str, date | None]]:
    """Every road-running row on a year index: (href, event name, date).

    The index groups results by discipline under an `<h4>`, so the road section is taken
    on its own and the track and cross-country lists are left alone.
    """
    section = re.search(
        ROAD_SECTION, page, re.DOTALL | re.IGNORECASE
    )
    if not section:
        return []
    rows: list[tuple[str, str, date | None]] = []
    for item in re.finditer(
        r"<li[^>]*>(?:\s*<b[^>]*>(?P<when>.*?)</b>\s*,)?\s*"
        r"<a[^>]+href=\"(?P<href>[^\"]+)\"[^>]*>(?P<event>.*?)</a>",
        section.group(1),
        re.DOTALL | re.IGNORECASE,
    ):
        href = item.group("href").strip()
        event = clean(html.unescape(re.sub(r"<[^>]+>", "", item.group("event"))))
        rows.append((href, event, _date_from(href, item.group("when"), year)))
    return rows


def _date_from(href: str, when: str | None, year: int) -> date | None:
    """The edition's date: from the filename if it carries one, else the printed day.

    The filename wins because it is written by whoever uploaded the results and the
    printed date is occasionally the entry deadline.
    """
    stem = href.rsplit("/", 1)[-1]
    if match := _FILE_DATE.match(stem):
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    if when:
        text = re.sub(r"<[^>]+>", "", when).strip()
        for fmt in ("%B %d", "%b %d"):
            try:
                return datetime.strptime(f"{text} {year}", f"{fmt} %Y").date()
            except ValueError:
                continue
    return None


class Cache:
    """Pages on disk, fetched at most once, with a manifest of what came from where."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.pages = root / "pages"
        self.manifest = root / "manifest.jsonl"
        self._last_request = 0.0
        self._client: httpx.Client | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def path_for(self, url: str) -> Path:
        """Where this URL lives on disk. Readable, so the cache can be inspected."""
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url.removeprefix(BASE)).strip("_")
        return self.pages / f"{slug[:120]}.html"

    def cached(self, url: str) -> bool:
        return self.path_for(url).exists()

    def get(self, url: str, *, refetch: bool = False) -> str:
        """This page's text, from disk when it is there and from the network when not."""
        path = self.path_for(url)
        if path.exists() and not refetch:
            return path.read_text(encoding="utf-8", errors="replace")

        body = self._fetch(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        self._record(url, path, body)
        return body

    def _fetch(self, url: str) -> str:
        if self._client is None:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._client = httpx.Client(
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                follow_redirects=True,
                verify=context,
            )
        wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.get(url)
            response.raise_for_status()
        finally:
            self._last_request = time.monotonic()
        return response.text

    def _record(self, url: str, path: Path, body: str) -> None:
        row = {
            "url": url,
            "path": path.name,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "bytes": len(body.encode("utf-8")),
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row) + "\n")


def catalogue(cache: Cache, years: range) -> tuple[list[Race], list[tuple[str, str]]]:
    """Every road race in these years, and the rows deliberately left out with the reason.

    The skips are returned rather than logged away because they are the coverage claim:
    a reader who wants to know what is missing from the history should be able to see the
    list, and `docs/data-terms.md` prints it.
    """
    races: list[Race] = []
    skipped: list[tuple[str, str]] = []
    for year in years:
        page = cache.get(INDEX.format(year=year))
        for href, event, when in parse_index(page, year):
            if reason := why_not_read(event, href):
                skipped.append((event, reason))
                continue
            if when is None:
                skipped.append((event, "no date on the index row or in the filename"))
                continue
            metres = distance_m(event)
            if metres is None:
                skipped.append((event, "no single distance in the event name"))
                continue
            races.append(
                Race(
                    race_id=race_id(href, event),
                    name=event,
                    date=when,
                    distance_m=metres,
                    course_id=course_id(event, metres),
                    url=BASE + href,
                )
            )
    return _deduplicate(races, skipped)


def _deduplicate(
    races: list[Race], skipped: list[tuple[str, str]]
) -> tuple[list[Race], list[tuple[str, str]]]:
    """Drop the same race published at two URLs, and say which copy was dropped.

    ⚠️ **The 2014 CHCM 10 km is on the index twice**, once as `.htm` and once as `.php`,
    with the same 162 finishers in title case on one page and upper case on the other. Left
    in, it counts that race twice and hands 162 people a phantom second result on a day
    they only raced once, which inflates their history depth and gives the resolver two
    copies of one person to reconcile.

    The test is the course, the date **and** the event name, not the course and date alone.
    The Trapline runs an open 5 km and a U19 5 km on the same road on the same morning;
    those are two races and the names say so.
    """
    kept: dict[tuple[str, object, str], Race] = {}
    for race in races:
        key = (race.course_id, race.date, _name_key(race.name))
        existing = kept.get(key)
        if existing is None:
            kept[key] = race
            continue
        # Prefer the .php page: it is the form every other year uses, and the stray .htm
        # copies are leftovers. Failing that, the shorter URL, so the choice is never
        # decided by the order the index happened to list them in.
        better, worse = max(
            (existing, race), key=_preference
        ), min((existing, race), key=_preference)
        kept[key] = better
        skipped.append(
            (worse.name, f"the same race is published at {better.url}; this copy is a duplicate")
        )
    return list(kept.values()), skipped


def _preference(race: Race) -> tuple[bool, int, str]:
    """Which copy of a duplicated race to keep. Higher wins, and it is total.

    The `.php` page is the form every other year uses and the stray `.htm` copies are
    leftovers; after that the shorter URL, and then the URL itself so that the choice never
    depends on the order the index happened to list them in.
    """
    return (race.url.endswith(".php"), -len(race.url), race.url)


def _name_key(event: str) -> str:
    """An event name reduced to what distinguishes one race from another that day."""
    return re.sub(r"[^a-z0-9]+", "", event.lower())
