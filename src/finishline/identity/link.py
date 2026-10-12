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

⚠️ **Unless the archive says the listed sex is the mistake** (PLAN.md section 13 item 46). The
sex on a list is a box the entrant ticked, and some tick the wrong one: Cape to Cabot's 2026
list printed four men as female, each with a history under his name, and each was predicted
as a woman with no results. So where at least `FIRST_NAME_RUNNERS` archive runners share the
entrant's first name and no more than `FIRST_NAME_SHARE` of them are of the listed sex, the
listed sex is read as not stated. Everything above still applies: one runner of the name is
linked, two are a refusal. A linked entrant then carries the sex the results printed, because
the models read a runner's sex from the entrant. An entrant with nobody of their name in the
archive keeps the sex they listed; a first name alone is not enough to change it.

**Unless a person chose, before the race** (PLAN.md section 13 item 47, `identity.picks`). An
entrant this module refuses can be given to one of the runners of their name by hand, or
called a newcomer, on evidence the list does not print: one candidate last raced in 2011 and
the other ran this course a year ago. The pick is an input like the list is, so the line it
makes is marked (`Link.by_hand`, `resolved_by_hand` in the prediction file) and counted, and
every page that shows the runner says so. A pick decides only what this module refused: it
never overrules a link the rules made, it can only choose a runner the resolver committed to,
and it is ignored where two entrants on the list share the name, because it does not say
which of them it means.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from finishline.identity.normalise import name_key, town_key
from finishline.identity.picks import NEWCOMER, Pick
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant

# How one-sided a first name has to be in the archive before it overrules a listed sex: this
# many runners carry it, and at most this share of them are of the sex the list printed.
FIRST_NAME_RUNNERS = 20
FIRST_NAME_SHARE = 0.02


class Status(StrEnum):
    LINKED = "linked"
    NEW = "new"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class Link:
    """One entrant, and what the archive can say about who they are.

    `entrant` is the list's own line, except the sex of a linked entrant whose listed sex the
    archive overruled, which is the runner's. `by_hand` says a person made the decision this
    module would not (`identity.picks`).
    """

    entrant: Entrant
    status: Status
    runner: Runner | None
    reason: str
    by_hand: bool = False


Index = tuple[dict[str, list[Runner]], dict[str, Counter[str]]]


def index(runners: Iterable[Runner]) -> Index:
    """The archive by name key, and how each first name splits by sex."""
    by_key: dict[str, list[Runner]] = defaultdict(list)
    first_names: dict[str, Counter[str]] = defaultdict(Counter)
    for runner in runners:
        by_key[name_key(runner.name)].append(runner)
        if runner.sex is not None and not runner.ambiguous:
            first_names[_first_name(runner.name)][runner.sex] += 1
    return by_key, first_names


def candidates_for(entrant: Entrant, archive: Index) -> list[Runner]:
    """The runners of this entrant's name whose sex the list does not rule out."""
    by_key, first_names = archive
    listed = None if _overruled(entrant, first_names) else entrant.sex
    return [
        runner
        for runner in by_key.get(name_key(entrant.name), [])
        if listed is None or runner.sex is None or runner.sex == listed
    ]


def link(
    entrants: Sequence[Entrant], runners: Iterable[Runner], picks: Iterable[Pick] = ()
) -> list[Link]:
    """Every entrant, in list order, linked to at most one runner.

    `picks` are the decisions a person made about entrants this would otherwise refuse.
    """
    archive = index(runners)
    listed_names = Counter(name_key(entrant.name) for entrant in entrants)
    by_pick = {pick.key: pick for pick in picks}

    first_pass: list[Link] = []
    for entrant in entrants:
        candidates = candidates_for(entrant, archive)
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
        elif candidates[0].sex not in (None, entrant.sex) and entrant.sex is not None:
            first_pass.append(
                Link(
                    replace(entrant, sex=candidates[0].sex),
                    Status.LINKED,
                    candidates[0],
                    "one runner; the listed sex is one almost nobody of this first name has",
                )
            )
        else:
            first_pass.append(Link(entrant, Status.LINKED, candidates[0], "one runner"))
        pick = by_pick.get(name_key(entrant.name))
        if (
            pick is not None
            and first_pass[-1].status is Status.AMBIGUOUS
            and listed_names[pick.key] == 1
        ):
            first_pass[-1] = _picked(entrant, candidates, pick) or first_pass[-1]

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


def _picked(entrant: Entrant, candidates: Sequence[Runner], pick: Pick) -> Link | None:
    """The link a person chose for an entrant this module refused, or None when it cannot stand.

    It cannot stand when the runner it names is no longer one the resolver commits to: the
    archive has moved since the pick, and the entrant goes back to being refused.
    """
    committed = [runner for runner in candidates if not runner.ambiguous]
    if pick.choice == NEWCOMER:
        return Link(
            entrant,
            Status.NEW,
            None,
            f"none of the {len(candidates)} runners of this name, chosen by hand",
            by_hand=True,
        )
    chosen = pick.among(committed)
    if chosen is None:
        return None
    # The models read a runner's sex from the entrant, as where the archive overrules a list.
    listed = entrant if chosen.sex in (None, entrant.sex) else replace(entrant, sex=chosen.sex)
    return Link(
        listed,
        Status.LINKED,
        chosen,
        f"chosen by hand from the {len(candidates)} runners of this name",
        by_hand=True,
    )


def _first_name(name: str) -> str:
    words = name.split()
    return name_key(words[0]) if words else ""


def _overruled(entrant: Entrant, first_names: dict[str, Counter[str]]) -> bool:
    """Whether the archive's runners of this first name say the listed sex is a mistake."""
    if entrant.sex is None:
        return False
    seen = first_names.get(_first_name(entrant.name))
    if not seen:
        return False
    total = sum(seen.values())
    return total >= FIRST_NAME_RUNNERS and seen[entrant.sex] <= FIRST_NAME_SHARE * total


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
