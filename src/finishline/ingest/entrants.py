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

import html
import re
from dataclasses import dataclass
from pathlib import Path

from finishline.identity.normalise import clean

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
