"""Which runner in the archive, if any, an entrant on a start list is.

The start list prints a name and, for Cape to Cabot and the Trackie lists, a sex; the
Trackie lists also print a town. None prints an age or an identifier, so linking an entrant
to a history is the resolver's problem with less evidence than the resolver had. The rules
are the resolver's, made stricter to match.

**One runner of that name key, of a compatible sex: linked.** The prediction uses their
history.

**No runner of that name key: a newcomer.** Predicted from the group prior for their sex,
which is the honest answer for somebody the archive has never seen, and counted.

⚠️ **More than one runner of that name key: excluded and counted, never guessed.** The
resolver could split two Chris Walshes because their pages printed ages. The start list
prints none, so there is nothing to choose between them with, and choosing the one with
the longer history would publish one person's prediction under another person's entry.

**Unless the list prints a hometown that exactly one of them was ever printed under.**
Trackie's lists print one. It breaks a tie and nothing else: a single candidate is linked
whatever town either side printed, because people move and most results pages print no
town at all, so a mismatch is not evidence of a different person.

⚠️ **A candidate the resolver already refused (`Runner.ambiguous`) makes the entrant
ambiguous too**, for the same reason: the archive does not know who that history belongs to.

⚠️ **Two entrants who would link to the same runner are both excluded.** A list with two
people of one name is two people, and at most one of them is the runner in the archive.

⚠️ **Sex is a check here, as it is in the resolver.** An entrant listed female does not link
to a runner whose results say male; that is a different person with the same name, and the
entrant is a newcomer. A missing sex on either side is no information, not a mismatch.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from finishline.identity.normalise import name_key, town_key
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant


class Status(StrEnum):
    LINKED = "linked"
    NEW = "new"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class Link:
    """One entrant, and what the archive can say about who they are."""

    entrant: Entrant
    status: Status
    runner: Runner | None
    reason: str


def link(entrants: Sequence[Entrant], runners: Iterable[Runner]) -> list[Link]:
    """Every entrant, in list order, linked to at most one runner."""
    by_key: dict[str, list[Runner]] = defaultdict(list)
    for runner in runners:
        by_key[name_key(runner.name)].append(runner)

    first_pass: list[Link] = []
    for entrant in entrants:
        candidates = [
            runner
            for runner in by_key.get(name_key(entrant.name), [])
            if entrant.sex is None or runner.sex is None or runner.sex == entrant.sex
        ]
        if not candidates:
            first_pass.append(Link(entrant, Status.NEW, None, "no runner of this name"))
        elif any(runner.ambiguous for runner in candidates):
            first_pass.append(
                Link(
                    entrant,
                    Status.AMBIGUOUS,
                    None,
                    "the archive cannot tell apart the runners of this name",
                )
            )
        elif len(candidates) > 1 and (only := _by_town(entrant, candidates)) is not None:
            first_pass.append(
                Link(entrant, Status.LINKED, only, "the one runner of this name from this town")
            )
        elif len(candidates) > 1:
            first_pass.append(
                Link(
                    entrant,
                    Status.AMBIGUOUS,
                    None,
                    f"{len(candidates)} runners of this name and the list prints no age",
                )
            )
        else:
            first_pass.append(Link(entrant, Status.LINKED, candidates[0], "one runner"))

    claimed = Counter(
        item.runner.runner_id for item in first_pass if item.runner is not None
    )
    return [
        Link(
            item.entrant,
            Status.AMBIGUOUS,
            None,
            f"{claimed[item.runner.runner_id]} entrants on the list share this runner's name",
        )
        if item.runner is not None and claimed[item.runner.runner_id] > 1
        else item
        for item in first_pass
    ]


def _by_town(entrant: Entrant, candidates: Sequence[Runner]) -> Runner | None:
    """The one candidate ever printed under the entrant's listed hometown, if exactly one."""
    if not entrant.hometown:
        return None
    town = town_key(entrant.hometown)
    if not town:
        return None
    matching = [
        runner for runner in candidates if town in {town_key(t) for t in runner.towns}
    ]
    return matching[0] if len(matching) == 1 else None


def counts(links: Sequence[Link]) -> dict[str, int]:
    """How many entrants landed in each status, for the prediction file and the README."""
    tally = Counter(item.status.value for item in links)
    return {status.value: tally.get(status.value, 0) for status in Status}
