"""Turning a cache full of pages into the two tables everything else reads.

`build` parses every race in the catalogue, resolves the results into runners and hands
back both, along with the pages it could not read. **A page that fails to parse is
reported, never skipped quietly**: the parser refuses on a layout it does not recognise
(see `ingest/parse.py`), and the whole point of that refusal is that somebody looks at the
page and decides, rather than a race silently going missing from a coverage number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from finishline.identity.resolve import Runner, resolve
from finishline.ingest import ane, nlaa, parse, raceroster, records
from finishline.schema import Race, Result


@dataclass(frozen=True, slots=True)
class Dataset:
    """Every result this project could read, and every page it could not."""

    races: dict[str, Race]
    results: list[Result]
    runners: list[Runner]
    failures: list[tuple[Race, str]]

    @property
    def finishes(self) -> int:
        return sum(1 for result in self.results if result.finished)

    @property
    def resolved(self) -> list[Runner]:
        """The runners a prediction may be published for."""
        return [runner for runner in self.runners if not runner.ambiguous]

    @property
    def ambiguous(self) -> list[Runner]:
        """The runners this project refuses to tell apart, and will not publish."""
        return [runner for runner in self.runners if runner.ambiguous]

    def depth_counts(self) -> dict[str, int]:
        """How many resolved runners sit in each history-depth stratum."""
        from finishline.backtest.score import STRATA, stratum_of

        counts = {label: 0 for label, _low, _high in STRATA}
        for runner in self.resolved:
            counts[stratum_of(runner.history_depth)] += 1
        return counts


def build(
    cache: nlaa.Cache,
    races: list[Race],
    *,
    external_dir: Path | None = None,
    ane_dir: Path | None = None,
) -> Dataset:
    """Parse and resolve everything in the catalogue that the cache already holds.

    `external_dir` adds the races that are not on the association's own pages, from
    `ingest/raceroster.REGISTER`. There is one so far, the 2026 Tely 10, and the reason
    it is read from elsewhere is in that module and in `docs/data-terms.md`. Passing None
    leaves them out, which is what the tests do. `ane_dir` adds the finish lists Athletics
    NorthEAST posts on its own site before the association does (`ingest/ane.REGISTER`).

    ⚠️ **A race read from elsewhere is dropped once nlaa.ca carries the same one**, the same
    date on the same course, so no edition is ever counted twice and the association's own
    page wins.
    """
    by_id = {race.race_id: race for race in races}
    results: list[Result] = []
    failures: list[tuple[Race, str]] = []

    for race in races:
        if not cache.cached(race.url):
            failures.append((race, "not fetched yet; run 'finishline crawl'"))
            continue
        page = cache.get(race.url)
        try:
            rows = records.to_results(page, race.race_id)
        except parse.ParseError as error:
            failures.append((race, str(error)))
            continue
        if not rows:
            failures.append((race, "no results table on the page"))
            continue
        results.extend(rows)

    posted = {(race.date, race.course_id) for race in races}
    if external_dir is not None:
        for entry in raceroster.REGISTER:
            if (entry.date, entry.course_id) in posted:
                continue
            by_id[entry.race_id] = entry.race
            try:
                results.extend(raceroster.load(entry, external_dir))
            except (OSError, ValueError) as error:
                failures.append((entry.race, f"external source unavailable: {error}"))
    if ane_dir is not None:
        for listed in ane.REGISTER:
            if (listed.date, listed.course_id) in posted:
                continue
            by_id[listed.race_id] = listed.race
            try:
                results.extend(ane.load(listed, ane_dir))
            except (OSError, ValueError, httpx.HTTPError) as error:
                failures.append((listed.race, f"external source unavailable: {error}"))

    return Dataset(
        races=by_id,
        results=results,
        runners=resolve(results, by_id),
        failures=failures,
    )
