"""Who is entered: the Athletics NorthEAST registration lists.

The club publishes a live list per race on its store, and it is the difference between
predicting a field and guessing at one. Cape to Cabot's carries a name and a sex; the
Uniformed Services Run's carries a name and the event entered.

⚠️ **The shirt size on the Cape to Cabot list is deliberately not read.** It is on the
page, it is a body-size proxy, and it would probably help the model a little. It is not
something a results page has ever printed about a runner, and this project publishes only
what the results publish (PLAN.md 2.8). A public finish-time prediction that leaned on
somebody's T-shirt size is not one anyone would thank us for.

⚠️ **Nothing here is committed.** `data/entrants/` is gitignored; these are living people
who have signed up for a race, and the prediction file is the only published derivative.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import truststore

from finishline.identity.normalise import clean
from finishline.ingest.nlaa import MIN_INTERVAL, TIMEOUT, USER_AGENT

# One entrant per list item: a name, then the club's separator, then the details it
# chooses to print. The separator is four hyphens on the Cape to Cabot list and absent on
# the USR's, so it is optional and everything after it is parsed rather than assumed.
_ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
_SEX = re.compile(r"\((male|female|m|f)\)", re.IGNORECASE)

# What ends the name and begins whatever the club chose to print after it: four hyphens
# on the Cape to Cabot list, a spaced hyphen on the USR's, or an opening bracket.
#
# ⚠️ **The hyphen has to be spaced.** Hale-Ford and Doe-Smith are surnames, and
# splitting on a bare hyphen cuts them in half and invents a runner.
#
# ⚠️ **A relay entry reads the other way round** on the USR list: the team's name comes
# first and the runner's after the hyphen, so the name taken here is the team's. Relays
# are not individual results and are excluded from prediction anyway (`nlaa.NOT_ROAD`),
# but do not reuse this for a relay field expecting a person.
_SEPARATOR = re.compile(r"-{2,}|\s+-\s+|\(")

# Navigation and store furniture that share the page's markup with the entrants.
_NOT_AN_ENTRANT = {
    "home", "log in", "login", "my account", "cart", "checkout", "contact us",
    "shipping & returns", "privacy notice", "conditions of use", "gift certificate faq",
    "discount coupons", "newsletter unsubscribe", "site map", "race registrations",
    "race registrations & other items", "have you seen ...",
}

# The two lists the club publishes, and the prefix each snapshot is filed under.
#
# ⚠️ **These pages are alive.** A results page is written once and never changes, so the
# results cache fetches it once and keeps it forever. An entrant list changes every day
# until the gun, and the only chance to observe it on a given day is that day. So this
# does the opposite of the results cache: it re-fetches on every run, and it never
# overwrites what an earlier run saw.
_STORE = "https://www.athleticsnortheast.com/cart/index.php?main_page=page&id="
LISTS: dict[str, str] = {
    "c2c-2026": _STORE + "4",
    "usr-2026": _STORE + "1",
}


@dataclass(frozen=True, slots=True)
class Entrant:
    """One person on a start list, as the club printed them."""

    name: str
    sex: str | None
    event: str | None = None

    @property
    def known_before_the_gun(self) -> tuple[str, str | None]:
        """Everything a prediction may use about an entrant with no history."""
        return self.name, self.sex


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One observation of one list: what was seen, when, and whether it had moved."""

    prefix: str
    path: Path
    at: datetime
    entrants: int
    changed: bool


def _content(page: str) -> str:
    """The part of the page below its own heading.

    ⚠️ **The store's sidebar is made of list items too**, and so is a line of inline
    JavaScript near the top. Read from the whole page, five of those arrive looking like
    entrants called things like "Cape to Cabot Registration List". Everything real sits
    below the page heading, so that is where reading starts.
    """
    marker = re.search(r"<h1[^>]*id=[\"']ezPagesHeading[\"'][^>]*>", page, re.IGNORECASE)
    return page[marker.start() :] if marker else page


def _sex_of(text: str) -> str | None:
    """M or F from a printed "(Female)", or None where the list does not say."""
    match = _SEX.search(text)
    if not match:
        return None
    return match.group(1)[0].upper()


def parse(page: str) -> list[Entrant]:
    """Every entrant on one of the club's list pages.

    The USR list groups its entrants under an `<h1>` per event, so the headings are
    tracked as the page is read and each entrant carries the event they entered. The Cape
    to Cabot list is one race and carries none.
    """
    entrants: list[Entrant] = []
    event: str | None = None
    for chunk in re.split(r"(<h1[^>]*>.*?</h1>)", _content(page), flags=re.DOTALL | re.IGNORECASE):
        heading = re.match(r"<h1[^>]*>(.*?)</h1>", chunk, re.DOTALL | re.IGNORECASE)
        if heading:
            event = clean(html.unescape(re.sub(r"<[^>]+>", "", heading.group(1))))
            continue
        for raw in _ITEM.findall(chunk):
            text = clean(html.unescape(re.sub(r"<[^>]+>", " ", raw)))
            name = clean(_SEPARATOR.split(text, maxsplit=1)[0])
            if not name or name.lower() in _NOT_AN_ENTRANT or len(name) < 3:
                continue
            entrants.append(Entrant(name=name, sex=_sex_of(text), event=event))
    return entrants


def load(path: Path) -> list[Entrant]:
    """Entrants from a saved snapshot of a list page."""
    return parse(path.read_text(encoding="utf-8", errors="replace"))


def latest_snapshot(directory: Path, prefix: str) -> Path | None:
    """The most recent snapshot for a race, by the timestamp in its filename.

    The list is live and changes daily, so a prediction records which snapshot it was
    frozen against. Snapshots are never overwritten.
    """
    snapshots = sorted(directory.glob(f"{prefix}_*.html"))
    return snapshots[-1] if snapshots else None


def _fetch(url: str) -> str:
    """One list page, at the same pace and under the same name as the results crawler."""
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
        verify=context,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def snapshot(directory: Path, *, lists: dict[str, str] | None = None) -> list[Snapshot]:
    """Take today's look at each list, and write down what was seen.

    Two things are recorded and they are not the same thing. The **file** is the start
    list, written only when the start list is new; the **manifest row** is the observation,
    written every time, whether or not anything moved. A day on which nobody entered is a
    fact about the race, and it costs nothing to keep it, but it does not need a second
    copy of five hundred names on disk.

    ⚠️ **"Changed" means the entrants changed, not the bytes.** The store puts a fresh
    `securityToken` in every response, so no two fetches of an unmoved list are ever byte
    equal. Comparing the pages as fetched called every single look a change, which would
    have written a new copy of both lists every day until the race and made the growth
    curve unreadable. The comparison is over the parsed entrants; the page's own hash still
    goes in the manifest, because that is the provenance of the file on disk.
    """
    pages = lists if lists is not None else LISTS
    directory.mkdir(parents=True, exist_ok=True)
    seen: list[Snapshot] = []
    for index, (prefix, url) in enumerate(sorted(pages.items())):
        if index:
            time.sleep(MIN_INTERVAL)
        body = _fetch(url)
        at = datetime.now(UTC)
        entered = parse(body)
        listing = _listing_digest(entered)
        previous = latest_snapshot(directory, prefix)
        if previous is not None and _listing_digest(load(previous)) == listing:
            path, changed = previous, False
        else:
            path, changed = directory / _filename(prefix, at), True
            path.write_text(body, encoding="utf-8", newline="\n")
        _record(
            directory,
            prefix,
            url,
            path,
            page=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            listing=listing,
            at=at,
            changed=changed,
        )
        seen.append(
            Snapshot(prefix=prefix, path=path, at=at, entrants=len(entered), changed=changed)
        )
    return seen


def _filename(prefix: str, at: datetime) -> str:
    return f"{prefix}_ane-list_{at.strftime('%Y%m%dT%H%M')}Z.html"


def _listing_digest(entered: list[Entrant]) -> str:
    """A hash of the start list itself: who is entered, and in what.

    Sorted, so that the club reordering its own page is not mistaken for somebody
    entering. Order on these pages is roughly registration order and is not otherwise
    meaningful, and the growth curve is what the snapshots are for.
    """
    rows = sorted(f"{e.name}\x1f{e.sex or ''}\x1f{e.event or ''}" for e in entered)
    return hashlib.sha256("\x1e".join(rows).encode("utf-8")).hexdigest()


def _record(
    directory: Path,
    prefix: str,
    url: str,
    path: Path,
    *,
    page: str,
    listing: str,
    at: datetime,
    changed: bool,
) -> None:
    """One row per look, whether or not the list moved.

    Both hashes are kept. `page_sha256` is the provenance of the bytes on disk, and it
    differs on every fetch because of the store's per-request token; `listing_sha256` is
    the start list, and it is the one that says whether anything happened.
    """
    row = {
        "list": prefix,
        "url": url,
        "path": path.name,
        "page_sha256": page,
        "listing_sha256": listing,
        "changed": changed,
        "fetched_at": at.isoformat(timespec="seconds"),
    }
    with (directory / "manifest.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")
