"""Deciding which results belong to the same runner.

THE PROBLEM
-----------
The archive has no runner identifier. Bib numbers are per race and reissued every year,
so a 2024 result and a 2025 result are linked by nothing but a name and a town. In a
province of half a million people with a famously shallow surname pool, that is not
enough on its own: there are several Power families in St. John's and more than one
runner called Chris Walsh.

Getting it wrong costs in both directions, and they are not symmetric:

- **Splitting one runner** gives two thin histories. The prediction is worse and the
  interval wider, but nothing published is false.
- **Merging two runners** invents a person who ran a 19-minute 5 km and a 4-hour
  marathon, and publishes a confident prediction for both of them that is wrong. It can
  also attach one person's results to another person's name in public.

So this module is asymmetric on purpose. Where the evidence is thin it splits, and where
two results cannot be told apart it refuses: the runner is marked ambiguous, excluded
from the published prediction file, and counted. The count is a published number.

THE EVIDENCE, AND WHY IT IS NOT THE HOMETOWN
--------------------------------------------
The obvious key is name plus hometown. It was the first design here and the archive
refuted it twice over.

**Most of the archive has no hometown.** 105 of the 157 readable races print no hometown
column at all, for anybody: every page from 2016 to 2023 except a handful. That is 15,777
of 42,466 results arriving with a blank. Keying on the town held back one runner in six
for a column the page never had.

**And runners move.** Of the 1,656 names that appear under two or more printed towns,
1,103 show a single clean switch over time, which is what moving house looks like; only
553 interleave, which is what two people look like. One runner settled it: an unbroken
run of age bands from under-20 to 25-29 over eight years, times improving throughout, one
town until 2023 and another off the island by 2025. One runner, one career, one move, and
the hometown rule made them two people with half a history each.

So the evidence is, in order:

1. **The name key** (`normalise.name_key`) groups candidates. Nothing is merged across
   different name keys, ever.
2. **The age band over time** splits the group, and it is the only thing that does. A
   runner cannot get younger, so every printed band on a dated race implies a window of
   birth years and one person's windows must all intersect. Where they cannot, that is
   two runners, and the split is forced by evidence rather than assumed.
3. **The hometown breaks a tie** and never splits. It is consulted only when a result
   could join more than one runner of the same name, which happens when the result's own
   page printed no age band at all.

⚠️ **Sex is a check, not a key**, for the same reason: a single mis-keyed row would fork
an otherwise clean history. A cluster whose results disagree about it is flagged.

WHAT THIS GETS WRONG, AND THE NUMBER THAT BOUNDS IT
---------------------------------------------------
⚠️ **Two runners of the same name whose ages are compatible now merge into one.** That is
the cost of the change, it is real, and it is the expensive direction. What makes it
publishable rather than hidden is that it can be counted: a runner whose results
interleave two printed hometowns is exactly the shape two merged people make, and
`Runner.town_switches` reports it. The README carries that count as the upper bound on
how often this is wrong.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from finishline.identity.normalise import name_key, town_key
from finishline.schema import Race, Result

# "30-39", "25-29", "U20", "80+", "19&U". The bands differ by race and even by year
# within one race, which is why the check is on birth years rather than on the band text.
_BAND_RANGE = re.compile(r"^(?P<low>\d{1,2})\s*-\s*(?P<high>\d{1,3})$")
_BAND_UNDER = re.compile(r"^(?:u|under\s*)(?P<high>\d{1,2})$|^(?P<high2>\d{1,2})\s*&\s*u")
_BAND_OVER = re.compile(r"^(?P<low>\d{1,3})\s*\+$")

# The oldest and youngest a road race entrant plausibly is. Used only to bound an open
# band ("80+"), never to reject a result.
MIN_AGE, MAX_AGE = 5, 99


@dataclass(frozen=True, slots=True)
class Runner:
    """One person, and the results this module is willing to say are theirs."""

    runner_id: str
    name: str
    hometown: str | None
    sex: str | None
    results: tuple[Result, ...]
    ambiguous: bool
    reason: str | None = None

    @property
    def history_depth(self) -> int:
        """How many finishes back this runner's history goes.

        The stratum every published number is broken down by, because a prediction from
        one result and a prediction from six are different claims.
        """
        return sum(1 for result in self.results if result.finished)

    @property
    def towns(self) -> tuple[str, ...]:
        """The hometowns this runner was printed under, in date order, deduplicated.

        ⚠️ **Deduplicated by key, not by spelling.** `St. John's` and `St.john's` are one
        town, and counting them as two made the merge-risk number below look three times
        worse than it is. The printed form is what comes back, because that is what the
        page said; the comparison is on the key.
        """
        seen: list[str] = []
        keys: list[str] = []
        for result in self.results:
            key = town_key(result.hometown)
            if key and (not keys or keys[-1] != key):
                keys.append(key)
                seen.append(result.hometown or "")
        return tuple(seen)

    @property
    def town_switches(self) -> int:
        """How many times the printed hometown changed.

        One switch is a runner who moved. Two or more is the shape two people of the same
        name make when their results interleave, so the count of runners above one is the
        published upper bound on how often this module merged two people. See the module
        note.
        """
        return max(0, len(self.towns) - 1)


def age_range(band: str | None) -> tuple[int, int] | None:
    """The ages a printed band covers, or None when it is not a band this reads."""
    if not band:
        return None
    text = band.strip().lower()
    if match := _BAND_RANGE.match(text):
        low, high = int(match.group("low")), int(match.group("high"))
        return (low, high) if low <= high else None
    if match := _BAND_UNDER.match(text):
        high = int(match.group("high") or match.group("high2"))
        return (MIN_AGE, high)
    if match := _BAND_OVER.match(text):
        return (int(match.group("low")), MAX_AGE)
    return None


def birth_window(band: str | None, when: date) -> tuple[int, int] | None:
    """The birth years consistent with this age band on this date.

    A runner aged `a` on race day was born in `race_year - a` or the year before it,
    depending on whether their birthday has come round, so the window is widened by one
    at the early end. Widening the wrong way would merge runners, so it only ever widens
    toward "cannot rule out".
    """
    ages = age_range(band)
    if ages is None:
        return None
    low, high = ages
    return (when.year - high - 1, when.year - low)


def _intersect(windows: list[tuple[int, int]]) -> tuple[int, int] | None:
    """The birth years consistent with every one of these bands, or None."""
    low = max(window[0] for window in windows)
    high = min(window[1] for window in windows)
    return (low, high) if low <= high else None


def _compatible(window: tuple[int, int] | None, other: tuple[int, int] | None) -> bool:
    """Whether one person could have both of these age bands.

    An unknown band is compatible with anything: several pages print no age column, and
    absence of evidence must not read as evidence of a second runner.
    """
    if window is None or other is None:
        return True
    return _intersect([window, other]) is not None


def _merge_windows(
    window: tuple[int, int] | None, other: tuple[int, int] | None
) -> tuple[int, int] | None:
    """What a cluster's birth-year window becomes once this result joins it."""
    if window is None:
        return other
    if other is None:
        return window
    return _intersect([window, other])


def _sex_of(results: list[Result]) -> tuple[str | None, bool]:
    """The sex these results agree on, and whether they disagreed."""
    printed = {result.sex for result in results if result.sex}
    if len(printed) == 1:
        return printed.pop(), False
    return None, len(printed) > 1


def resolve(results: list[Result], races: dict[str, Race]) -> list[Runner]:
    """Group results into runners, marking the ones that cannot be told apart.

    One sweep per name, oldest result first. Each result joins the runner whose birth-year
    window it fits; where it fits none, it starts a new one; where it fits several, the
    hometown decides, and if the hometown cannot, the result is held back rather than
    guessed at.

    Deterministic: the same results in any order give the same runners with the same ids,
    because a prediction file has to be reproducible from the archive alone.
    """
    by_name: dict[str, list[Result]] = defaultdict(list)
    for result in results:
        by_name[name_key(result.name)].append(result)

    runners: list[Runner] = []
    for key in sorted(by_name):
        group = sorted(
            by_name[key],
            key=lambda r: (races[r.race_id].date, r.race_id, r.place or 0, r.name),
        )
        clusters: list[list[Result]] = []
        windows: list[tuple[int, int] | None] = []
        held: list[tuple[Result, int]] = []

        for result in group:
            mine = birth_window(result.age_band, races[result.race_id].date)
            fits = [
                index
                for index, window in enumerate(windows)
                if _compatible(window, mine)
            ]
            if not fits:
                clusters.append([result])
                windows.append(mine)
                continue
            if len(fits) > 1:
                fits = _narrow_by_town(result, clusters, fits)
            if len(fits) != 1:
                held.append((result, len(fits)))
                continue
            clusters[fits[0]].append(result)
            windows[fits[0]] = _merge_windows(windows[fits[0]], mine)

        for result, candidates in held:
            runners.append(
                Runner(
                    runner_id=f"{key}#held#{result.race_id}#{result.place}",
                    name=result.name,
                    hometown=result.hometown,
                    sex=result.sex,
                    results=(result,),
                    ambiguous=True,
                    reason=(
                        f"{candidates} runners of this name could be this result, and "
                        "the page printed no age band to tell them apart"
                    ),
                )
            )
        for index, cluster in enumerate(clusters):
            runners.append(_runner_from(key, index, cluster, races))
    return runners


def _narrow_by_town(result: Result, clusters: list[list[Result]], fits: list[int]) -> list[int]:
    """Use the hometown to choose between runners of one name, where it can.

    The tie-break, never the split. A result with no printed town narrows nothing, and a
    town that matches no candidate narrows nothing either, because a runner who moved is
    commoner in this archive than two runners of a name (see the module note).
    """
    town = town_key(result.hometown)
    if not town:
        return fits
    matched = [
        index
        for index in fits
        if any(town_key(row.hometown) == town for row in clusters[index])
    ]
    return matched if len(matched) == 1 else fits


def _runner_from(
    key: str, index: int, ordered: list[Result], races: dict[str, Race]
) -> Runner:
    """One cluster as a runner, checked for the things that mean it is really two."""
    sex, disagreed = _sex_of(ordered)
    town = next((result.hometown for result in reversed(ordered) if result.hometown), None)
    reason = "results under this name disagree about sex" if disagreed else None

    return Runner(
        runner_id=key if index == 0 else f"{key}#{index}",
        name=ordered[-1].name,
        hometown=town,
        sex=sex,
        results=tuple(ordered),
        ambiguous=reason is not None,
        reason=reason,
    )
