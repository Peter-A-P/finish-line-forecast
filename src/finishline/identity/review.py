"""The hand-labelled pairs that give the resolver a precision and a recall (PLAN.md 5.2).

The resolver (`identity.resolve`) decides, for every two results of one name, whether they
are one person. Nothing in the archive says whether it was right, so a person has to: this
module draws pairs of results, writes them to a sheet with the resolver's answer beside
each, and scores the sheet once someone has marked each pair `same`, `different` or
`unsure`.

WHY THE PAIRS ARE DRAWN BY STRATUM
----------------------------------
A pair drawn at random from the archive is almost always two results of one runner with one
hometown, which the resolver gets right and which teaches nothing. The plan asks for the hard
cases to be over-represented, so pairs are drawn in equal numbers from five kinds:

- **merged, one town**: two results the resolver joined, never printed under different towns;
- **merged, two towns**: two results the resolver joined across two printed towns, the shape
  two people of one name make (and also the shape of one runner who moved);
- **split by age**: two results of one name the resolver kept apart because their age bands
  cannot belong to one person;
- **held back**: a result the resolver refused to place, against one of the runners it could
  have been;
- **near names**: two results under different name keys with the same surname, a first name
  that is one a prefix of the other or one letter apart, and the same printed town. The
  resolver never joins these, so they are where its recall is lost.

⚠️ **Every figure is reweighted to the archive.** Each stratum's share of the labelled pairs
is not its share of the resolver's decisions, so the precision and recall are computed per
stratum and combined with weights equal to how many such decisions the archive holds
(`Sample.population`). The unweighted numbers would describe the sheet, not the resolver.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

from finishline.identity.normalise import name_key, town_key
from finishline.identity.resolve import Runner
from finishline.schema import Race, Result

STRATA: tuple[str, ...] = (
    "merged, one town",
    "merged, two towns",
    "split by age",
    "held back",
    "near names",
)
PER_STRATUM = 40
SEED = 20260921
LABELS = ("same", "different", "unsure")

SIDE = ("race", "date", "name", "hometown", "sex", "age_band", "time")
COLUMNS = (
    "pair",
    "stratum",
    "resolver",
    "label",
    *(f"a_{c}" for c in SIDE),
    *(f"b_{c}" for c in SIDE),
)


@dataclass(frozen=True, slots=True)
class Pair:
    """Two results and what the resolver said about them."""

    stratum: str
    resolver: str  # "same", "different" or "refused"
    a: Result
    b: Result


@dataclass(frozen=True, slots=True)
class Sample:
    """The pairs to label, and how many decisions of each kind the archive holds."""

    pairs: list[Pair]
    population: dict[str, int]


def _near(first: str, other: str) -> bool:
    """A first name that is a prefix of the other, or one edit away (Chris, Christopher)."""
    if first == other or min(len(first), len(other)) < 3:
        return False
    if first.startswith(other) or other.startswith(first):
        return True
    if abs(len(first) - len(other)) > 1:
        return False
    if len(first) == len(other):
        return sum(x != y for x, y in zip(first, other, strict=True)) == 1
    short, long = sorted((first, other), key=len)
    return any(long[:i] + long[i + 1 :] == short for i in range(len(long)))


def _split_name(name: str) -> tuple[str, str] | None:
    words = name.split()
    if len(words) < 2:
        return None
    return name_key(words[0]), name_key(words[-1])


def draw(runners: Sequence[Runner], per_stratum: int = PER_STRATUM, seed: int = SEED) -> Sample:
    """Pairs from every stratum, the same pairs for the same archive and seed."""
    rng = random.Random(seed)
    candidates: dict[str, list[Pair]] = defaultdict(list)
    population: dict[str, int] = dict.fromkeys(STRATA, 0)

    by_key: dict[str, list[Runner]] = defaultdict(list)
    for runner in runners:
        by_key[runner.runner_id.split("#")[0]].append(runner)

    for runner in runners:
        if runner.ambiguous or len(runner.results) < 2:
            continue
        results = list(runner.results)
        towns = {town_key(result.hometown) for result in results} - {""}
        if len(towns) <= 1:
            population["merged, one town"] += 1
            a, b = rng.sample(results, 2)
            candidates["merged, one town"].append(Pair("merged, one town", "same", a, b))
        else:
            population["merged, two towns"] += 1
            first = results[0]
            other = [
                r for r in results if town_key(r.hometown) not in ("", town_key(first.hometown))
            ]
            if first.hometown and other:
                candidates["merged, two towns"].append(
                    Pair("merged, two towns", "same", first, rng.choice(other))
                )

    for group in by_key.values():
        kept = [runner for runner in group if not runner.ambiguous]
        held = [runner for runner in group if runner.ambiguous]
        for left, right in combinations(kept, 2):
            population["split by age"] += 1
            candidates["split by age"].append(
                Pair(
                    "split by age", "different", rng.choice(left.results), rng.choice(right.results)
                )
            )
        for runner in held:
            population["held back"] += 1
            if kept:
                candidate = rng.choice(kept)
                candidates["held back"].append(
                    Pair("held back", "refused", runner.results[0], rng.choice(candidate.results))
                )

    # Near names: same surname and printed town, first names close but keyed apart.
    by_surname_town: dict[tuple[str, str], list[tuple[str, Runner]]] = defaultdict(list)
    for runner in runners:
        split = _split_name(runner.name)
        town = town_key(runner.hometown)
        if split is None or not town or runner.ambiguous:
            continue
        by_surname_town[(split[1], town)].append((split[0], runner))
    for people in by_surname_town.values():
        for (left_first, left), (right_first, right) in combinations(people, 2):
            if name_key(left.name) != name_key(right.name) and _near(left_first, right_first):
                population["near names"] += 1
                candidates["near names"].append(
                    Pair(
                        "near names",
                        "different",
                        rng.choice(left.results),
                        rng.choice(right.results),
                    )
                )

    pairs: list[Pair] = []
    for stratum in STRATA:
        pool = candidates[stratum]
        pairs += rng.sample(pool, min(per_stratum, len(pool)))
    return Sample(pairs, population)


def _side(result: Result, races: Mapping[str, Race]) -> list[str]:
    race = races[result.race_id]
    seconds = result.seconds
    clock = (
        ""
        if seconds is None
        else f"{int(seconds) // 3600}:{int(seconds) % 3600 // 60:02d}:{int(seconds) % 60:02d}"
    )
    return [
        race.name,
        race.date.isoformat(),
        result.name,
        result.hometown or "",
        result.sex or "",
        result.age_band or "",
        clock,
    ]


def write(path: Path, sample: Sample, races: Mapping[str, Race]) -> None:
    """The sheet to label, with the archive's counts per stratum in a second file beside it.

    ⚠️ **Refuses to overwrite**: a sheet that exists may hold someone's labels.
    """
    if path.exists():
        raise FileExistsError(f"{path} exists and may hold labels; move it aside to draw again")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        sheet = csv.writer(handle)
        sheet.writerow(COLUMNS)
        for number, pair in enumerate(sample.pairs, start=1):
            sheet.writerow(
                [
                    number,
                    pair.stratum,
                    pair.resolver,
                    "",
                    *_side(pair.a, races),
                    *_side(pair.b, races),
                ]
            )
    counts = path.with_suffix(".population.csv")
    with counts.open("w", encoding="utf-8", newline="") as handle:
        sheet = csv.writer(handle)
        sheet.writerow(("stratum", "decisions_in_archive"))
        for stratum in STRATA:
            sheet.writerow((stratum, sample.population[stratum]))


@dataclass(frozen=True, slots=True)
class Score:
    """Precision and recall, reweighted to the archive, with 95% intervals."""

    precision: tuple[float, float, float] | None
    recall: tuple[float, float, float] | None
    labelled: int
    unsure: int
    unlabelled: int
    by_stratum: dict[str, dict[str, int]]


def read(path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    """The sheet's rows and the archive's counts per stratum."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with path.with_suffix(".population.csv").open(encoding="utf-8", newline="") as handle:
        population = {
            row["stratum"]: int(row["decisions_in_archive"]) for row in csv.DictReader(handle)
        }
    return rows, population


def score(
    rows: Iterable[Mapping[str, str]], population: Mapping[str, int], draws: int = 2000
) -> Score:
    """Precision: of the pairs the resolver joined, the share that are one person.
    Recall: of the pairs that are one person, the share the resolver joined.

    A held-back pair counts as not joined, which is what it is in every published file.
    Each is computed per stratum, then weighted by the stratum's count in the archive.
    """
    table: dict[str, list[tuple[bool, bool]]] = defaultdict(list)  # (joined, truly same)
    unsure = unlabelled = 0
    tally: dict[str, dict[str, int]] = {}
    for row in rows:
        label = row.get("label", "").strip().lower()
        stratum = row["stratum"]
        counts = tally.setdefault(
            stratum, {"same": 0, "different": 0, "unsure": 0, "unlabelled": 0}
        )
        if not label:
            unlabelled += 1
            counts["unlabelled"] += 1
            continue
        if label not in LABELS:
            raise ValueError(f"pair {row['pair']}: label {label!r} is not one of {LABELS}")
        counts[label] += 1
        if label == "unsure":
            unsure += 1
            continue
        table[stratum].append((row["resolver"] == "same", label == "same"))

    rng = np.random.default_rng(SEED)

    def weighted(pick: str, resample: bool) -> float | None:
        numerator = denominator = 0.0
        for stratum, items in table.items():
            if resample and items:
                items = [items[i] for i in rng.integers(0, len(items), size=len(items))]
            if pick == "precision":
                chosen = [same for joined, same in items if joined]
            else:
                chosen = [joined for joined, same in items if same]
            if not chosen:
                continue
            weight = population.get(stratum, 0)
            numerator += weight * float(np.mean(chosen))
            denominator += weight
        return numerator / denominator if denominator else None

    def interval(pick: str) -> tuple[float, float, float] | None:
        point = weighted(pick, resample=False)
        if point is None:
            return None
        values = [
            value
            for value in (weighted(pick, resample=True) for _ in range(draws))
            if value is not None
        ]
        low, high = np.quantile(values, [0.025, 0.975])
        return point, float(low), float(high)

    return Score(
        precision=interval("precision"),
        recall=interval("recall"),
        labelled=sum(len(items) for items in table.values()),
        unsure=unsure,
        unlabelled=unlabelled,
        by_stratum=tally,
    )
