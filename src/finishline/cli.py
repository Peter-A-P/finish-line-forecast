"""The `finishline` command line.

The pipeline in the order it runs:

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

from finishline.ingest import nlaa
from finishline.schema import Race

app = typer.Typer(add_completion=False, help=__doc__)

DATA = Path("data")
CACHE = DATA / "cache" / "nlaa"

# The archive this project reads. 2016 is where the ten-year history starts; the pages go
# back to 1978 and the older ones are a different era of both the sport and the software.
FIRST_YEAR = 2016
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


def cache_catalogue(
    cache: nlaa.Cache, first: int, last: int
) -> tuple[list[Race], list[tuple[str, str]]]:
    """The catalogue over a year range, as the commands want it."""
    return nlaa.catalogue(cache, range(first, last + 1))


if __name__ == "__main__":  # pragma: no cover
    app()
