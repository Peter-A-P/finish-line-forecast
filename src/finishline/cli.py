"""The `finishline` command line.

The pipeline in the order it runs:

    finishline snapshot       today's look at the two live entrant lists
    finishline catalogue      what races exist, and which are read
    finishline crawl          fetch the results pages, once, politely
    finishline dataset        parse, resolve runners, write the tables
    finishline backtest       score the baselines at every origin
    finishline report         the tables the README publishes

⚠️ **`crawl` refuses to run until the courtesy notices have gone out.** That is a rail in
code rather than a line in a document, because this project reads a small volunteer
association's whole archive and the person who decided to do that politely is not the
person the command is convenient for. `finishline crawl --notices-sent` is the
acknowledgement, and `finishline notices` prints what has to be sent first.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from finishline import report, store
from finishline.backtest import run
from finishline.ingest import entrants, nlaa
from finishline.models import baselines
from finishline.schema import Race
from finishline.store import Dataset

app = typer.Typer(add_completion=False, help=__doc__)

DATA = Path("data")
CACHE = DATA / "cache" / "nlaa"
EXTERNAL = DATA / "cache" / "raceroster"
ENTRANTS = DATA / "entrants"

# The archive this project reads. The pages go back to 1978.
#
# 2008 rather than 2016, changed once the 2016 boundary turned out to be an artefact
# rather than a decision: 67 of the 453 Cape to Cabot entrants had their earliest result in
# 2016 exactly, which is the shape a history makes when it has been cut off rather than
# when it began. Eighteen years covers a masters career from one age band to the next and
# doubles most courses' editions. Before 2008 the returns fall away: a result older than
# that says almost nothing about how someone will run next month, and the recent-form
# window is eighteen months regardless.
FIRST_YEAR = 2008
LAST_YEAR = date.today().year

NOTICES_ENV = "FINISHLINE_NOTICES_SENT"

NOTICES = """\
Two notes go out before the crawler reads anything, from a personal address:

  1. Newfoundland and Labrador Athletics Association, athletics@nlaa.ca
  2. Athletics NorthEAST, admin@athleticsnortheast.com

Both say the same three things: what is being fetched (the public road-running
results pages, and the two entrant lists), how (one request a second, each page
fetched once and kept locally, never re-fetched), and what it is for (published
finish-time predictions with the error published afterwards, naming runners only
as the results pages already name them). Both offer to stop on request.

The drafts are in docs/emails.md. When they have gone, either:

    finishline crawl --notices-sent

or set FINISHLINE_NOTICES_SENT=1 in the environment.
"""


@app.command()
def notices() -> None:
    """Print what has to be sent before the crawler runs."""
    typer.echo(NOTICES)


@app.command()
def snapshot(
    notices_sent: Annotated[
        bool, typer.Option("--notices-sent", help="The courtesy notes have gone out.")
    ] = False,
) -> None:
    """Take today's look at the two entrant lists, and never overwrite yesterday's.

    ⚠️ **Run this every day until the gun.** The club's lists are live pages with no
    archive anywhere: the Wayback Machine holds no past edition of them, so a day not
    observed is a day gone. The no-show rate, the late-entry rate and the growth curve of
    a field are all differences between snapshots, and the first race that pays for them
    is the Uniformed Services Run, whose list can never be re-read after it starts.
    """
    if not (notices_sent or os.environ.get(NOTICES_ENV)):
        typer.echo(NOTICES, err=True)
        raise typer.Exit(code=2)

    for seen in entrants.snapshot(ENTRANTS):
        moved = "changed" if seen.changed else "unchanged since the last look"
        typer.echo(f"  {seen.prefix:<10} {seen.entrants:>4} entrants, {moved}  {seen.path.name}")
    typer.echo("nothing here is committed (see .gitignore)")


@app.command()
def catalogue(
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    skips: Annotated[bool, typer.Option(help="List what was left out, and why.")] = False,
) -> None:
    """List the road races in the archive, and what is deliberately not read.

    Reads one index page per year. The index carries event names and dates and no
    runners, so this is metadata rather than anyone's personal data.
    """
    with nlaa.Cache(CACHE) as cache:
        races, skipped = cache_catalogue(cache, first, last)

    typer.echo(f"{len(races)} road races, {first} to {last}, and {len(skipped)} rows skipped")
    by_year: dict[int, int] = {}
    for race in races:
        by_year[race.year] = by_year.get(race.year, 0) + 1
    for year in sorted(by_year):
        typer.echo(f"  {year}  {by_year[year]:>3} races")

    courses = {race.course_id for race in races}
    typer.echo(f"\n{len(courses)} distinct courses. The ones with the deepest history:")
    depth: dict[str, int] = {}
    for race in races:
        depth[race.course_id] = depth.get(race.course_id, 0) + 1
    for course, count in sorted(depth.items(), key=lambda item: (-item[1], item[0]))[:12]:
        typer.echo(f"  {count:>3} editions  {course}")

    if skips:
        typer.echo("\nSkipped:")
        for event, why in skipped:
            typer.echo(f"  {event}\n      {why}")


@app.command()
def crawl(
    notices_sent: Annotated[
        bool, typer.Option("--notices-sent", help="The courtesy notes have gone out.")
    ] = False,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """Fetch every road-results page in the catalogue, once, one a second."""
    if not (notices_sent or os.environ.get(NOTICES_ENV)):
        typer.echo(NOTICES, err=True)
        raise typer.Exit(code=2)

    with nlaa.Cache(CACHE) as cache:
        races, _skipped = cache_catalogue(cache, first, last)
        outstanding = [race for race in races if not cache.cached(race.url)]
        typer.echo(
            f"{len(races)} races, {len(races) - len(outstanding)} already cached, "
            f"{len(outstanding)} to fetch "
            f"(about {len(outstanding) * nlaa.MIN_INTERVAL / 60:.0f} minutes)"
        )
        for index, race in enumerate(outstanding, start=1):
            cache.get(race.url)
            typer.echo(f"  [{index:>3}/{len(outstanding)}] {race.race_id}")
    typer.echo("done; nothing here is committed (see .gitignore)")


@app.command()
def dataset(
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    failures: Annotated[bool, typer.Option(help="List the pages that would not parse.")] = False,
) -> None:
    """Parse every cached page and resolve the results into runners."""
    data = _dataset(first, last)
    typer.echo(
        f"{len(data.races) - len(data.failures)} races read, "
        f"{data.finishes:,} finishes, "
        f"{len(data.resolved):,} runners, "
        f"{len(data.ambiguous):,} too ambiguous to publish"
    )
    for label, count in data.depth_counts().items():
        typer.echo(f"  {count:>6,} runners with {label} prior finish(es)")

    if data.failures:
        typer.echo(f"\n{len(data.failures)} pages did not parse:")
        for race, why in data.failures if failures else data.failures[:5]:
            typer.echo(f"  {race.race_id}\n      {why[:160]}")
        if not failures and len(data.failures) > 5:
            typer.echo(f"  ... and {len(data.failures) - 5} more; pass --failures")

    if data.ambiguous:
        typer.echo("\nWhy runners were held back, most common first:")
        reasons: dict[str, int] = {}
        for runner in data.ambiguous:
            key = (runner.reason or "unknown").split("(")[0].strip()
            reasons[key] = reasons.get(key, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
            typer.echo(f"  {count:>6,}  {reason}")


@app.command()
def backtest(
    scored_from: Annotated[int, typer.Option(help="First year to score.")] = 2024,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """Score the baselines at every origin and print the tables."""
    data = _dataset(first, last)
    scored = run.run(data.races, data.resolved, baselines.BASELINES, scored_from=scored_from)
    names = [model.name for model in baselines.BASELINES]
    races = len({row.race_id for row in scored})
    typer.echo(f"{races} races scored from {scored_from}, {len(scored):,} predictions\n")
    typer.echo(report.baseline_table(scored, names))
    typer.echo()
    typer.echo(report.placing_table(scored, names))


@app.command(name="report")
def write_report(
    scored_from: Annotated[int, typer.Option(help="First year to score.")] = 2024,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """Write the measured tables into README.md, between their markers."""
    data = _dataset(first, last)
    scored = run.run(data.races, data.resolved, baselines.BASELINES, scored_from=scored_from)
    names = [model.name for model in baselines.BASELINES]

    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")
    text = report.replace_between(text, "archive", report.archive_table(data))
    text = report.replace_between(text, "baselines", report.baseline_table(scored, names))
    text = report.replace_between(text, "placing", report.placing_table(scored, names))
    readme.write_text(text, encoding="utf-8", newline="\n")
    typer.echo("README.md tables rewritten from the measurement")


def _dataset(first: int, last: int) -> Dataset:
    """The catalogue, parsed and resolved."""
    with nlaa.Cache(CACHE) as cache:
        races, _skipped = cache_catalogue(cache, first, last)
        return store.build(cache, races, external_dir=EXTERNAL)


def cache_catalogue(
    cache: nlaa.Cache, first: int, last: int
) -> tuple[list[Race], list[tuple[str, str]]]:
    """The catalogue over a year range, as the commands want it."""
    return nlaa.catalogue(cache, range(first, last + 1))


if __name__ == "__main__":  # pragma: no cover
    app()
