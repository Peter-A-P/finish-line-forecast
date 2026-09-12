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

THE EVIDENCE, IN ORDER
----------------------
1. **The name key** (`normalise.name_key`) groups candidates. Nothing is merged across
   different name keys, ever.
2. **The hometown** splits a name group. Two different printed towns are two runners.
   A blank town joins the only cluster when there is exactly one, and is ambiguous when
   there are more, because a blank is missing information and not a match.
3. **The age band over time** is the check that catches the rest, and it is the one piece
   of real evidence the pages hand us for free. A runner cannot get younger. Every
   printed band on a dated race implies a window of birth years, and one person's windows
   must intersect. Two runners sharing a name and a town are usually caught here, because
   two people of the same name in the same town are rarely the same age.

⚠️ **Sex is a check, not a key.** It is printed for almost every result, and a group
whose results disagree about it is two runners. But it is not used to split, because a
single mis-keyed row would then fork an otherwise clean history.
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


def _cluster_by_town(results: list[Result]) -> tuple[list[list[Result]], list[Result]]:
    """Split one name group by hometown, and hand back the rows that cannot be placed.

    ⚠️ **The clusters come back in sorted order, not in the order the archive was read.**
    They used to come back in first-seen order, which made the runner ids depend on which
    year the crawler happened to parse first. A prediction file has to be reproducible
    from the archive alone, so the order is fixed here rather than hoped for.
    """
    towns: dict[str, list[Result]] = defaultdict(list)
    blank: list[Result] = []
    for result in results:
        key = town_key(result.hometown)
        (blank if key == "" else towns[key]).append(result)

    if not towns:
        return ([blank] if blank else []), []
    if len(towns) == 1:
        only = next(iter(towns.values()))
        return [only + blank], []
    return [towns[key] for key in sorted(towns)], blank


def _sex_of(results: list[Result]) -> tuple[str | None, bool]:
    """The sex these results agree on, and whether they disagreed."""
    printed = {result.sex for result in results if result.sex}
    if len(printed) == 1:
        return printed.pop(), False
    return None, len(printed) > 1


def resolve(results: list[Result], races: dict[str, Race]) -> list[Runner]:
    """Group results into runners, marking the ones that cannot be told apart.

    Deterministic: the same results in any order give the same runners with the same
    ids, because a prediction file has to be reproducible from the archive alone.
    """
    by_name: dict[str, list[Result]] = defaultdict(list)
    for result in results:
        by_name[name_key(result.name)].append(result)

    runners: list[Runner] = []
    for key in sorted(by_name):
        clusters, unplaceable = _cluster_by_town(by_name[key])

        for result in unplaceable:
            runners.append(
                Runner(
                    runner_id=f"{key}#blank#{result.race_id}",
                    name=result.name,
                    hometown=None,
                    sex=result.sex,
                    results=(result,),
                    ambiguous=True,
                    reason=(
                        "no hometown printed, and this name appears under "
                        f"{len(clusters)} different hometowns"
                    ),
                )
            )

        for cluster in clusters:
            ordered = sorted(
                cluster, key=lambda r: (races[r.race_id].date, r.race_id, r.place or 0)
            )
            runners.append(_runner_from(key, ordered, races))
    return runners


def _runner_from(key: str, ordered: list[Result], races: dict[str, Race]) -> Runner:
    """One cluster as a runner, checked for the things that mean it is really two."""
    windows = [
        window
        for result in ordered
        if (window := birth_window(result.age_band, races[result.race_id].date))
    ]
    consistent = _intersect(windows) if windows else None
    sex, disagreed = _sex_of(ordered)

    town = next((result.hometown for result in reversed(ordered) if result.hometown), None)
    runner_id = f"{key}#{town_key(town)}" if town else key

    reason: str | None = None
    if windows and consistent is None:
        bands = ", ".join(
            f"{result.age_band} in {races[result.race_id].date.year}"
            for result in ordered
            if result.age_band
        )
        reason = f"age bands cannot belong to one runner ({bands})"
    elif disagreed:
        reason = "results under this name and hometown disagree about sex"

    return Runner(
        runner_id=runner_id,
        name=ordered[-1].name,
        hometown=town,
        sex=sex,
        results=tuple(ordered),
        ambiguous=reason is not None,
        reason=reason,
    )
