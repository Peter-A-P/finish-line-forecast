"""Entrants the linker refused, decided by a person before the race (PLAN.md 13 item 47).

`identity.link` refuses an entrant whose name more than one runner in the archive carries,
because a start list prints no age to choose between them with. That refusal is right for a
program and wasteful for a person: shown both histories side by side, somebody who knows the
local field can often see that one candidate ran this course last year and the other last
raced in 2011. This module is where that decision is written down, and `finishline review
<race>` is the page it is made on (`identity/pickpage.py`).

WHAT A PICK IS
--------------
One entrant, by the name the list printed, given either to one runner of that name or to
nobody (a newcomer), with the kind of evidence it was made on and a note.

⚠️ **The runner is named by one of their results, not by their archive id.** An id is the
name key and a counter, and the counter can move when a crawl adds a race. A result (the
race, the name as printed, the time) belongs to one runner for as long as the resolver keeps
that history together, and when it does not, `Pick.among` finds nobody and the entrant goes
back to being refused, which is the safe direction.

⚠️ **The file holds names and is never committed** (`data/links/`, gitignored). It says which
of two people of one name this project believes entered a race, which no results page
publishes. What is published is the mark on the runner's line and the count in the file's
`entrants` block, and the SHA-256 of the picks as they stood, so that a pick made after a
file was tagged cannot be passed off as one made before.

WHAT IT DOES NOT DO
-------------------
It does not touch the archive. A runner the resolver itself refused (`Runner.ambiguous`) is
in no model fit, so there is nothing to predict them from, and they cannot be picked; the
page shows their results beside the candidates as evidence and nothing more. Changing the
resolver's mind is a change to the archive and needs a new backtest.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from finishline.identity.normalise import name_key
from finishline.identity.resolve import Runner, birth_window
from finishline.schema import Race, Result

RUNNER = "runner"
NEWCOMER = "new"

# What a pick was made on. Recorded because the first three can be checked against the
# archive by anyone holding it and the fourth cannot.
EVIDENCE: dict[str, str] = {
    "recent": "The other runners of this name have not raced in years",
    "course": "This runner has run this course before",
    "town": "The hometown matches",
    "known": "I know this runner",
    "other": "Something else (say what in the note)",
}


@dataclass(frozen=True, slots=True)
class Pick:
    """One entrant, and who a person says they are."""

    entrant: str  # as the list printed it
    choice: str  # RUNNER or NEWCOMER
    evidence: str
    note: str
    picked_on: str
    # One result of the chosen runner: the race, the name as that page printed it, the time.
    race_id: str | None = None
    name: str | None = None
    seconds: float | None = None

    @property
    def key(self) -> str:
        return name_key(self.entrant)

    def among(self, runners: Iterable[Runner]) -> Runner | None:
        """The one runner holding the result this pick names, or None."""
        holding = [
            runner
            for runner in runners
            if any(
                result.race_id == self.race_id
                and result.name == self.name
                and result.seconds == self.seconds
                for result in runner.results
            )
        ]
        return holding[0] if len(holding) == 1 else None


def for_runner(
    entrant: str, runner: Runner, races: Mapping[str, Race], evidence: str, note: str, today: date
) -> Pick:
    """A pick of this runner, pinned to their latest finish."""
    if runner.ambiguous:
        raise ValueError("a runner the archive could not place cannot be picked")
    finishes = [result for result in runner.results if result.seconds is not None]
    if not finishes:
        raise ValueError("a runner with no finish has nothing to be pinned to")
    latest = max(finishes, key=lambda result: races[result.race_id].date)
    return Pick(
        entrant=entrant,
        choice=RUNNER,
        evidence=_evidence(evidence),
        note=note.strip(),
        picked_on=today.isoformat(),
        race_id=latest.race_id,
        name=latest.name,
        seconds=latest.seconds,
    )


def newcomer(entrant: str, evidence: str, note: str, today: date) -> Pick:
    """A pick that says the entrant is none of the runners of their name."""
    return Pick(entrant, NEWCOMER, _evidence(evidence), note.strip(), today.isoformat())


def _evidence(kind: str) -> str:
    if kind not in EVIDENCE:
        raise ValueError(f"evidence {kind!r} is not one of {sorted(EVIDENCE)}")
    return kind


def path_for(directory: Path, race_id: str) -> Path:
    return directory / f"{race_id}.json"


def load(path: Path) -> list[Pick]:
    """The picks for one race, or none when nobody has made any."""
    if not path.exists():
        return []
    record = json.loads(path.read_text(encoding="utf-8"))
    return [Pick(**item) for item in record["picks"]]


def to_bytes(picks: Sequence[Pick]) -> bytes:
    """The picks in one canonical form, so the same picks always hash the same."""
    ordered = sorted(picks, key=lambda pick: pick.key)
    text = json.dumps(
        {"picks": [asdict(pick) for pick in ordered]}, indent=2, sort_keys=True, ensure_ascii=False
    )
    return (text + "\n").encode("utf-8")


def save(path: Path, picks: Sequence[Pick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_bytes(picks))


def put(picks: Sequence[Pick], pick: Pick) -> list[Pick]:
    """The picks with this one in place of any earlier pick for the same entrant."""
    return [*(other for other in picks if other.key != pick.key), pick]


def drop(picks: Sequence[Pick], entrant: str) -> list[Pick]:
    return [pick for pick in picks if pick.key != name_key(entrant)]


# What the review page shows. Everything below reads the archive and decides nothing.


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return "no finish"
    whole = round(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _row(result: Result, races: Mapping[str, Race], course_id: str) -> dict[str, Any]:
    race = races[result.race_id]
    return {
        "date": race.date.isoformat(),
        "race": race.name,
        "km": round(race.distance_m / 1000, 1),
        "name": result.name,
        "town": result.hometown or "",
        "sex": result.sex or "",
        "age": result.age_band or "",
        "time": _clock(result.seconds),
        "here": race.course_id == course_id,
    }


def age_on(results: Iterable[Result], races: Mapping[str, Race], day: date) -> str:
    """The age on race day that every printed age band of these results allows, in words."""
    windows = [
        window
        for result in results
        if (window := birth_window(result.age_band, races[result.race_id].date)) is not None
    ]
    if not windows:
        return "no age printed"
    earliest = max(low for low, _ in windows)
    latest = min(high for _, high in windows)
    if earliest > latest:
        return "the printed ages disagree"
    young, old = day.year - latest - 1, day.year - earliest
    return f"{young} to {old}"


def candidate(runner: Runner, races: Mapping[str, Race], race: Race) -> dict[str, Any]:
    """One runner of the entrant's name, as the page shows them."""
    rows = sorted(
        (_row(result, races, race.course_id) for result in runner.results),
        key=lambda row: str(row["date"]),
        reverse=True,
    )
    return {
        "id": runner.runner_id,
        "pickable": not runner.ambiguous and any(row["time"] != "no finish" for row in rows),
        "refused": runner.reason if runner.ambiguous else None,
        "sex": runner.sex or "",
        "towns": list(runner.towns),
        "finishes": runner.history_depth,
        "first": rows[-1]["date"][:4] if rows else "",
        "last": rows[0]["date"][:4] if rows else "",
        "here": sum(1 for row in rows if row["here"]),
        "age": age_on(runner.results, races, race.date),
        "results": rows,
    }
