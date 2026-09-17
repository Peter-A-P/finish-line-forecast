"""The `finishline` command line.

The pipeline in the order it runs:

    finishline snapshot       today's look at the two live entrant lists
    finishline catalogue      what races exist, and which are read
    finishline courses        how hard each course is, measured against its hills
    finishline crawl          fetch the results pages, once, politely
    finishline weather        fetch the observed weather for every race month
    finishline conditions     what heat and wind cost, estimated from the editions
    finishline dataset        parse, resolve runners, write the tables
    finishline backtest       score the baselines at every origin (--hierarchical: the model)
    finishline report         the tables the README publishes
    finishline freeze <race>  the prediction file, at least 24 hours before the gun
    finishline score <race>   the tagged prediction against the official results

⚠️ **`crawl` refuses to run until the courtesy notices have gone out.** That is a rail in
code rather than a line in a document, because this project reads a small volunteer
association's whole archive and the person who decided to do that politely is not the
person the command is convenient for. `finishline crawl --notices-sent` is the
acknowledgement, and `finishline notices` prints what has to be sent first.
"""

from __future__ import annotations

import os
import tomllib
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from finishline import report, store
from finishline.backtest import run, score
from finishline.history import History
from finishline.ingest import eccc, entrants, nlaa
from finishline.metrics import grade
from finishline.models import baselines, conditions
from finishline.models import courses as models_courses
from finishline.schema import Race
from finishline.store import Dataset

app = typer.Typer(add_completion=False, help=__doc__)

DATA = Path("data")
CACHE = DATA / "cache" / "nlaa"
EXTERNAL = DATA / "cache" / "raceroster"
ENTRANTS = DATA / "entrants"
WEATHER = DATA / "cache" / "eccc"
BACKTESTS = DATA / "cache" / "backtest"
COURSES = DATA / "courses.toml"


def course_profiles() -> dict[str, dict[str, Any]]:
    """Published elevation figures, keyed by course, or nothing if the file is absent."""
    if not COURSES.exists():
        return {}
    loaded: dict[str, dict[str, Any]] = tomllib.loads(COURSES.read_text(encoding="utf-8"))
    return loaded


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
    refresh_index: Annotated[
        bool,
        typer.Option(
            "--refresh-index",
            help="Read the last year's index again first, to find races posted since.",
        ),
    ] = False,
    scheduled: Annotated[
        bool,
        typer.Option(
            "--scheduled",
            help="Run as the weekly task: stand down around a live race in data/live.toml.",
        ),
    ] = False,
) -> None:
    """Fetch every road-results page in the catalogue, once, one a second.

    ⚠️ **A crawl that finds a new race makes the saved model backtest stale.** The saved rows
    are keyed on the dataset, so `report` leaves the model out and `freeze` refuses until
    `backtest --hierarchical` has been run again. Crawl before a backtest, not between one
    and a freeze; `--scheduled` enforces that around every race in data/live.toml.
    """
    if not (notices_sent or os.environ.get(NOTICES_ENV)):
        typer.echo(NOTICES, err=True)
        raise typer.Exit(code=2)
    if scheduled and _scheduled_pause():
        return

    with nlaa.Cache(CACHE) as cache:
        if refresh_index:
            # A results page never changes; the current year's index grows as races are
            # posted, and the cached copy cannot show one posted after it was fetched.
            cache.get(nlaa.INDEX.format(year=last), refetch=True)
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


def _scheduled_pause() -> bool:
    """Whether a scheduled fetch should stand down today, saying why if so."""
    from finishline.publish import freeze as freezing

    reason = freezing.crawl_paused(LIVE, date.today())
    if reason is not None:
        typer.echo(reason)
    return reason is not None


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


@app.command(name="courses")
def course_factors(
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    draws: Annotated[int, typer.Option(help="Bootstrap draws over runners.")] = 400,
) -> None:
    """How hard each course is, measured from the results, against what the hills predict.

    The measurement is the answer and the elevation is the check. Where a course publishes
    a climb, the grade that reconciles the two is printed: if it is a grade a road can
    have, the factor is the hills, and if it is not, something else is going on.
    """
    data = _dataset(first, last)
    history = History.before(date.today(), data.races, data.resolved)
    fitted = models_courses.fit(history, data.races, draws=draws)
    profiles = course_profiles()

    floor = models_courses.MIN_FINISHES
    typer.echo(f"{len(fitted.courses)} courses with {floor} or more finishes\n")
    typer.echo(f"{'course':<40}{'fin':>7}{'ed':>4}{'factor':>9}{'95% CI':>17}   implied grade")
    for measured in sorted(fitted.courses.values(), key=lambda c: -c.factor):
        record = profiles.get(measured.course_id, {})
        implied = ""
        if "climb_m" in record:
            solved = grade.implied_grade(
                distance_m=float(record["distance_m"]),
                climb_m=float(record["climb_m"]),
                drop_m=float(record["drop_m"]),
                factor=measured.factor,
            )
            implied = (
                f"{solved:.1%} over {record['climb_m']:.0f} m up"
                if solved is not None
                else "the published climb cannot explain it"
            )
        interval = f"[{measured.low * 100:+.1f}, {measured.high * 100:+.1f}]"
        typer.echo(
            f"{measured.course_id:<40}{measured.finishes:>7,}{measured.editions:>4}"
            f"{measured.percent:>8.1f}%{interval:>17}   {implied}"
        )


@app.command(name="conditions")
def weather_effect(
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """What the weather on the day costs, estimated from the editions.

    Needs the observations cached; `finishline weather` fetches them.
    """
    data = _dataset(first, last)
    history = History.before(date.today(), data.races, data.resolved)
    fitted = models_courses.fit(history, data.races, draws=1)
    rows, skipped = _conditions_rows(data, fitted)

    typer.echo(f"{len(rows)} editions with an observation; {skipped} without one")
    model = conditions.fit(rows)
    if model is None:
        typer.echo("not enough editions to estimate anything")
        raise typer.Exit(code=1)

    low, high = model.intervals["temp_at_10km"]
    typer.echo(
        f"\ntemperature at 10 km : {model.temp_coefficient(10_000.0) * 100:+.3f}% per degree "
        f"[{low * 100:+.3f}, {high * 100:+.3f}]"
    )
    low, high = model.intervals["wind"]
    typer.echo(
        f"wind speed           : {model.wind * 100:+.3f}% per km/h "
        f"[{low * 100:+.3f}, {high * 100:+.3f}]"
    )
    low, high = model.intervals["tailwind"]
    typer.echo(
        f"tailwind             : {model.tailwind * 100:+.3f}% per km/h along the bearing "
        f"[{low * 100:+.3f}, {high * 100:+.3f}]  (negative means it helps)"
    )
    typer.echo(
        f"\nexplains {model.explained * 100:.1f}% of the edition variance, "
        f"leaving sd {model.residual_sd * 100:.2f}%"
    )
    typer.echo("\nwhat a degree costs, by distance:")
    for label, metres in (
        ("5 km", 5_000.0),
        ("10 km", 10_000.0),
        ("Tely 10", 16_093.0),
        ("Cape to Cabot 20 km", 20_000.0),
        ("marathon", 42_195.0),
    ):
        typer.echo(f"  {label:<22}{model.temp_coefficient(metres) * 100:+.3f}% per degree")

    typer.echo(
        f"\nneutral is {conditions.NEUTRAL_TEMP_C:.0f} C and "
        f"{conditions.NEUTRAL_WIND_KMH:.0f} km/h; Cape to Cabot on a 20 C morning would be "
        f"{model.adjustment(20_000.0, 20.0, conditions.NEUTRAL_WIND_KMH) * 100:+.2f}%"
    )


def _conditions_rows(
    data: Dataset, fitted: models_courses.Fit
) -> tuple[list[conditions.Observation], int]:
    """Every edition the airport can speak for, with its observed weather."""
    finishers: dict[str, int] = {}
    for result in data.results:
        if result.finished:
            finishers[result.race_id] = finishers.get(result.race_id, 0) + 1

    profiles = course_profiles()
    rows: list[conditions.Observation] = []
    skipped = 0
    with eccc.Cache(WEATHER) as weather:
        for race_id, effect in fitted.editions.items():
            race = data.races[race_id]
            if not eccc.near_st_johns(race.course_id):
                skipped += 1
                continue
            try:
                met = eccc.conditions(weather, race_id, race.date, race.distance_m)
            except eccc.NoObservation:
                skipped += 1
                continue
            if met.wind_kmh is None:
                skipped += 1
                continue
            bearing = profiles.get(race.course_id, {}).get("bearing_deg")
            rows.append(
                conditions.Observation(
                    race_id=race_id,
                    course_id=race.course_id,
                    distance_m=race.distance_m,
                    finishers=finishers.get(race_id, 0),
                    effect=effect,
                    temp_c=met.temp_c,
                    wind_kmh=met.wind_kmh,
                    tailwind_kmh=met.tailwind(None if bearing is None else float(bearing)),
                )
            )
    return rows, skipped


@app.command()
def weather(
    notices_sent: Annotated[
        bool, typer.Option("--notices-sent", help="The courtesy notes have gone out.")
    ] = False,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    scheduled: Annotated[
        bool,
        typer.Option(
            "--scheduled",
            help="Run as the weekly task: stand down around a live race in data/live.toml.",
        ),
    ] = False,
) -> None:
    """Fetch the observed weather for every month that holds a race, once, one a second.

    A month fetched before it ended is fetched again (`eccc.Cache.get`). New weather changes
    the model's inputs as a new race does, so `--scheduled` pauses on the same dates.
    """
    if not (notices_sent or os.environ.get(NOTICES_ENV)):
        typer.echo(NOTICES, err=True)
        raise typer.Exit(code=2)
    if scheduled and _scheduled_pause():
        return

    with nlaa.Cache(CACHE) as cache:
        races, _skipped = cache_catalogue(cache, first, last)
    months = sorted({(race.date.year, race.date.month) for race in races})
    typer.echo(f"{len(races)} races over {len(months)} station-months")

    with eccc.Cache(WEATHER) as store_:
        for index, (year, month) in enumerate(months, start=1):
            station = eccc.station_for(year)
            already = store_.path_for(station, year, month).exists()
            store_.get(station, year, month)
            if not already:
                typer.echo(f"  [{index:>3}/{len(months)}] {year}-{month:02d}  {station.name}")
    typer.echo("done; nothing here is committed (see .gitignore)")


# The settings the published hierarchical run uses. `backtest` can be asked for others to
# experiment; `report` only ever publishes a run made with these.
HIERARCHICAL_DEFAULTS: dict[str, int] = {"months": 3, "draws": 300, "tune": 400, "chains": 4}


def _hierarchical_key(data: Dataset, scored_from: int, settings: dict[str, int]) -> str:
    """What a saved hierarchical run has to match to be reused."""
    from finishline.backtest import saved
    from finishline.models import hierarchical

    parts: dict[str, object] = {
        "scored_from": scored_from,
        "dataset": saved.dataset_fingerprint(data.races, data.results),
        **settings,
    }
    sources = [
        Path(hierarchical.__file__),
        Path(run.__file__),
        Path(__file__).with_name("history.py"),
    ]
    return saved.key(parts, sources)


def _hierarchical_rows(
    data: Dataset, scored_from: int, settings: dict[str, int], *, fit_if_missing: bool
) -> list[score.Scored] | None:
    """The hierarchical model's scored rows: saved if they match, sampled if asked to."""
    from finishline.backtest import saved
    from finishline.models import hierarchical

    path = BACKTESTS / "hierarchical.jsonl"
    run_key = _hierarchical_key(data, scored_from, settings)
    rows = saved.load(path, run_key)
    if rows is not None or not fit_if_missing:
        return rows

    def fitter(history: History) -> hierarchical.Posterior | None:
        typer.echo(f"  sampling on history before {history.origin} ...")
        return hierarchical.fit(
            history,
            draws=settings["draws"],
            tune=settings["tune"],
            chains=settings["chains"],
        )

    model = hierarchical.Hierarchical(months=settings["months"], fitter=fitter)
    rows = run.run(data.races, data.resolved, [model], scored_from=scored_from)
    for start, diagnostics in model.fits:
        typer.echo(f"  block {start}: {diagnostics}")
    saved.save(path, run_key, rows)
    return rows


@app.command()
def backtest(
    scored_from: Annotated[int, typer.Option(help="First year to score.")] = 2024,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    hierarchical: Annotated[
        bool,
        typer.Option(help="Score the hierarchical model too. Hours on first run; saved."),
    ] = False,
    months: Annotated[
        int, typer.Option(help="Months of races per model fit.")
    ] = HIERARCHICAL_DEFAULTS["months"],
    draws: Annotated[
        int, typer.Option(help="Posterior draws per chain.")
    ] = HIERARCHICAL_DEFAULTS["draws"],
    tune: Annotated[
        int, typer.Option(help="Tuning steps per chain.")
    ] = HIERARCHICAL_DEFAULTS["tune"],
    chains: Annotated[
        int, typer.Option(help="Chains, one per core.")
    ] = HIERARCHICAL_DEFAULTS["chains"],
) -> None:
    """Score the baselines at every origin and print the tables."""
    data = _dataset(first, last)
    scored = run.run(data.races, data.resolved, baselines.BASELINES, scored_from=scored_from)
    names = [model.name for model in baselines.BASELINES]
    if hierarchical:
        settings = {"months": months, "draws": draws, "tune": tune, "chains": chains}
        rows = _hierarchical_rows(data, scored_from, settings, fit_if_missing=True)
        scored += rows or []
        names.append("hierarchical")
    races = len({row.race_id for row in scored})
    typer.echo(f"{races} races scored from {scored_from}, {len(scored):,} predictions\n")
    typer.echo(report.baseline_table(scored, names))
    typer.echo()
    typer.echo(report.placing_table(scored, names))
    if hierarchical:
        typer.echo()
        typer.echo(_coverage(data, scored, "hierarchical"))


def _coverage(data: Dataset, scored: list[score.Scored], model: str | None) -> str:
    """The conformal coverage table for one model's rows, or its absence."""
    from finishline.conformal import coverage, split

    if model is None:
        return report.coverage_table({}, None)
    rows = [row for row in scored if row.model == model]
    dates = {race_id: race.date for race_id, race in data.races.items()}
    summaries = {
        level: coverage.summarise(split.rolling(rows, dates, level), level)
        for level in (0.80, 0.90)
    }
    return report.coverage_table(summaries, model)


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
    # Never samples: a report rewrites tables from what was measured, and the model's rows
    # are only published when a saved run matches today's code and data exactly.
    saved_rows = _hierarchical_rows(
        data, scored_from, dict(HIERARCHICAL_DEFAULTS), fit_if_missing=False
    )
    if saved_rows is not None:
        scored += saved_rows
        names.append("hierarchical")
    else:
        typer.echo("no saved hierarchical run matches; its rows are left out of the tables")

    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")
    text = report.replace_between(text, "archive", report.archive_table(data))
    fitted = models_courses.fit(
        History.before(date.today(), data.races, data.resolved), data.races
    )
    text = report.replace_between(
        text, "courses", report.course_table(fitted, course_profiles())
    )
    # A fresh clone has no weather cache, so this reports its own absence rather than
    # failing the whole report for the sake of one table.
    rows, skipped = _conditions_rows(data, fitted)
    text = report.replace_between(
        text,
        "conditions",
        report.conditions_table(conditions.fit(rows), len(fitted.editions), skipped),
    )
    text = report.replace_between(text, "baselines", report.baseline_table(scored, names))
    text = report.replace_between(text, "placing", report.placing_table(scored, names))
    text = report.replace_between(
        text,
        "coverage",
        _coverage(data, scored, "hierarchical" if saved_rows is not None else None),
    )
    readme.write_text(text, encoding="utf-8", newline="\n")
    _write_live_rows()
    typer.echo("README.md tables rewritten from the measurement")


OPENMETEO = DATA / "cache" / "openmeteo"
FORECAST_ERROR = DATA / "forecast_error.toml"


@app.command(name="forecast-error")
def forecast_error(
    notices_sent: Annotated[
        bool, typer.Option("--notices-sent", help="The courtesy notes have gone out.")
    ] = False,
    since: Annotated[int, typer.Option(help="First year of day-ahead forecasts to use.")] = 2024,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """How wrong a day-ahead forecast was on past race mornings, written for `freeze`.

    Pairs Open-Meteo's archived day-ahead forecast with the airport's observation over the
    same race hours, for every edition near St. John's, and writes the bias and spread to
    data/forecast_error.toml. One request per year of forecasts.
    """
    from datetime import UTC, datetime, timedelta

    from finishline.ingest import openmeteo
    from finishline.models import weather

    if not (notices_sent or os.environ.get(NOTICES_ENV)):
        typer.echo(NOTICES, err=True)
        raise typer.Exit(code=2)

    data = _dataset(first, last)
    yesterday = date.today() - timedelta(days=1)
    editions = sorted(
        (
            race
            for race in data.races.values()
            if race.date.year >= since
            and race.date <= yesterday
            and eccc.near_st_johns(race.course_id)
        ),
        key=lambda race: race.date,
    )
    client = openmeteo.Client(OPENMETEO)
    forecasts: list[eccc.Observation] = []
    try:
        for year in sorted({race.date.year for race in editions}):
            end = min(date(year, 12, 31), yesterday)
            body = client.previous_runs(date(year, 1, 1), end)
            forecasts += openmeteo.readings(body, suffix="_previous_day1")
    finally:
        client.close()

    pairs: list[tuple[eccc.Conditions, eccc.Conditions]] = []
    skipped = 0
    with eccc.Cache(WEATHER) as observed_cache:
        for race in editions:
            try:
                observed = eccc.conditions(
                    observed_cache, race.race_id, race.date, race.distance_m
                )
                predicted = openmeteo.conditions(
                    forecasts, race.race_id, race.date, race.distance_m, 9
                )
            except eccc.NoObservation:
                skipped += 1
                continue
            pairs.append((predicted, observed))

    error = weather.measure(pairs)
    typer.echo(f"{error.mornings} race mornings from {since}, {skipped} without both sources")
    typer.echo(f"  temperature  bias {error.temp_bias:+.2f} C     sd {error.temp_sd:.2f}")
    typer.echo(f"  wind speed   bias {error.wind_bias:+.2f} km/h  sd {error.wind_sd:.2f}")
    typer.echo(f"  wind east    bias {error.east_bias:+.2f} km/h  sd {error.east_sd:.2f}")
    typer.echo(f"  wind north   bias {error.north_bias:+.2f} km/h  sd {error.north_sd:.2f}")
    weather.save(
        FORECAST_ERROR,
        error,
        "How wrong Open-Meteo's day-ahead forecast was on past race mornings at St. John's\n"
        "airport, forecast minus the ECCC observation over the same race hours. Written by\n"
        f"`finishline forecast-error` on {datetime.now(UTC):%Y-%m-%d}, from race editions near\n"
        f"St. John's since {since}. Read by `finishline freeze`. Do not edit by hand.",
    )
    typer.echo(f"written to {FORECAST_ERROR}")


LIVE = DATA / "live.toml"
PREDICTIONS = Path("predictions")


@app.command()
def freeze(
    race_id: Annotated[str, typer.Argument(help="A race in data/live.toml, e.g. c2c-2026.")],
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """Write the prediction file for a race, and print the hash to publish with it.

    Refuses inside 24 hours of the gun, refuses with uncommitted changes to the code (the
    file names the commit that made it, and that commit has to be the code that ran), and
    refuses without a saved model backtest to calibrate the intervals on. It never commits
    or tags: a person does that, and the tag's time is the record.
    """
    import subprocess
    from datetime import UTC, datetime

    from finishline.conformal import split
    from finishline.identity import link
    from finishline.models import hierarchical
    from finishline.publish import freeze as freezing
    from finishline.publish import predictions

    try:
        live = freezing.load_live(LIVE, race_id)
        predictions.check_gun(live.gun, datetime.now(UTC))
    except (KeyError, ValueError, predictions.FreezeRefused) as refusal:
        typer.echo(f"refused: {refusal}", err=True)
        raise typer.Exit(code=2) from refusal

    code = ["src", "pyproject.toml", "uv.lock", "data/live.toml"]
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *code],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        typer.echo(f"uncommitted changes to the code; commit them first:\n{dirty}", err=True)
        raise typer.Exit(code=2)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    snapshot_path = entrants.latest_snapshot(ENTRANTS, live.entrant_list)
    if snapshot_path is None:
        typer.echo(f"no snapshot of the {live.entrant_list} list; run `finishline snapshot`")
        raise typer.Exit(code=2)

    data = _dataset(first, last)
    saved_rows = _hierarchical_rows(
        data, 2024, dict(HIERARCHICAL_DEFAULTS), fit_if_missing=False
    )
    if saved_rows is None:
        typer.echo("no saved model backtest matches this code; run `backtest --hierarchical`")
        raise typer.Exit(code=2)
    dates = {race_id_: race.date for race_id_, race in data.races.items()}
    calibration = {
        level: split.shifts(saved_rows, dates, level, live.race.date)
        for level in freezing.LEVELS
    }

    history = History.before(live.race.date, data.races, data.resolved)
    typer.echo(f"sampling on every result before {live.race.date} ...")
    posterior = hierarchical.fit(history)
    if posterior is None:
        typer.echo("nothing to fit")
        raise typer.Exit(code=1)

    listed = entrants.load(snapshot_path)
    doc = freezing.assemble(
        posterior=posterior,
        links=link.link(listed, data.runners),
        history=history,
        live=live,
        now=datetime.now(UTC),
        snapshot={
            "file": snapshot_path.name,
            "sha256": predictions.sha256(snapshot_path.read_bytes()),
        },
        model={
            "name": "hierarchical",
            "commit": commit,
            "fit_on_results_before": live.race.date.isoformat(),
            "diagnostics": posterior.diagnostics,
            "settings": dict(HIERARCHICAL_DEFAULTS),
        },
        calibration=calibration,
        seed=backtest_seed(race_id),
    )
    path = PREDICTIONS / f"{race_id}.json"
    digest = predictions.write(path, doc)
    counts = doc["entrants"]
    typer.echo(
        f"\nwrote {path}: {counts['predicted']} runners predicted, "
        f"{counts['ambiguous']} excluded as ambiguous, {counts['new']} with no history"
    )
    typer.echo(f"sha256 {digest}")
    typer.echo(
        "\nNothing is committed or tagged. To make it count, before "
        f"{(live.gun - predictions.MINIMUM_NOTICE).isoformat()}:\n"
        f"  git add {path.as_posix()} && git commit -m \"Prediction: {race_id}\"\n"
        f"  git tag -a predictions/{race_id} -m \"sha256 {digest}\"\n"
        f"  git push && git push origin predictions/{race_id}"
    )


SCORES = Path("scores")
RACE_PAGES = Path("docs") / "predictions"


def _git_bytes(*args: str) -> bytes | None:
    """A git command's output as bytes, or None when git refuses."""
    import subprocess

    done = subprocess.run(["git", *args], capture_output=True, check=False)
    return done.stdout if done.returncode == 0 else None


@app.command(name="score")
def score_race(
    race_id: Annotated[str, typer.Argument(help="A tagged prediction, e.g. c2c-2026.")],
    notices_sent: Annotated[
        bool, typer.Option("--notices-sent", help="The courtesy notes have gone out.")
    ] = False,
    results: Annotated[
        str | None,
        typer.Option(help="The archive race id of the results page, if the date and course "
        "match more than one."),
    ] = None,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
) -> None:
    """Score a tagged prediction against the official results, and write the race page.

    Reads the prediction file from the tag `predictions/<race>`, never from the working copy,
    and refuses unless the tag message publishes the file's hash and the tag is at least 24
    hours before the gun. Finds the results page on the association's index, refreshing that
    year's index once if the race is not on the cached copy, and fetches the page once.
    Writes scores/<race>.json, docs/predictions/<race>.md and the README's live rows.
    """
    import json
    from datetime import UTC, datetime

    from finishline.ingest import records
    from finishline.publish import predictions
    from finishline.publish import scorecard as cards

    tag = f"predictions/{race_id}"
    file = f"{PREDICTIONS.as_posix()}/{race_id}.json"
    ref = f"refs/tags/{tag}"
    fields = _git_bytes(
        "for-each-ref", ref, "--format=%(objecttype)%00%(taggerdate:iso-strict)%00%(contents)"
    )
    data = _git_bytes("cat-file", "blob", f"{tag}:{file}")
    if not fields or data is None:
        typer.echo(f"refused: no tag {tag} holding {file}; an untagged file is not a prediction",
                   err=True)
        raise typer.Exit(code=2)
    kind, tagged_text, message = fields.decode("utf-8").split("\0", 2)
    if kind != "tag":
        typer.echo(f"refused: {tag} is a lightweight tag and records no time", err=True)
        raise typer.Exit(code=2)

    doc = json.loads(data.decode("utf-8"))
    try:
        problems = predictions.validate(doc)
        if problems:
            raise cards.NotPreRegistered("the tagged file is invalid: " + "; ".join(problems))
        digest = cards.check_digest(data, message)
        tagged_at = datetime.fromisoformat(tagged_text)
        cards.check_tag(tagged_at, datetime.fromisoformat(doc["gun"]))
    except (cards.NotPreRegistered, ValueError) as refusal:
        typer.echo(f"refused: {refusal}", err=True)
        raise typer.Exit(code=2) from refusal
    working = Path(file)
    if working.exists() and working.read_bytes() != data:
        typer.echo(
            f"warning: {file} in the working copy differs from the tagged file, which is the "
            "one scored. A prediction file is never edited; find out why.",
            err=True,
        )

    target = doc["race"]
    when = date.fromisoformat(target["date"])
    with nlaa.Cache(CACHE) as cache:

        def candidates() -> list[Race]:
            races, _skipped = nlaa.catalogue(cache, range(when.year, when.year + 1))
            if results is not None:
                return [race for race in races if race.race_id == results]
            return [
                race
                for race in races
                if race.date == when and race.course_id == target["course_id"]
            ]

        found = candidates()
        if not found:
            if not (notices_sent or os.environ.get(NOTICES_ENV)):
                typer.echo(NOTICES, err=True)
                raise typer.Exit(code=2)
            typer.echo(f"not on the cached {when.year} index; reading it again, once")
            cache.get(nlaa.INDEX.format(year=when.year), refetch=True)
            found = candidates()
        if not found:
            typer.echo(f"no results posted yet for {target['course_id']} on {when}")
            raise typer.Exit(code=1)
        if len(found) > 1:
            names = ", ".join(race.race_id for race in found)
            typer.echo(f"several pages match ({names}); pass --results with one", err=True)
            raise typer.Exit(code=2)
        race = found[0]
        if not cache.cached(race.url) and not (notices_sent or os.environ.get(NOTICES_ENV)):
            typer.echo(NOTICES, err=True)
            raise typer.Exit(code=2)
        page = cache.get(race.url)

    if abs(race.distance_m - float(target["distance_m"])) > 1.0:
        typer.echo(
            f"refused: {race.race_id} is {race.distance_m:.0f} m and the prediction was for "
            f"{target['distance_m']} m",
            err=True,
        )
        raise typer.Exit(code=2)

    rows = records.to_results(page, race.race_id)
    lines = cards.published(doc)
    matching = cards.match(lines, rows)

    # Carry-forward from the archive as it stood the day before, as in the backtest.
    archive = _dataset(first, last)
    history = History.before(when, archive.races, archive.resolved)
    runner_of = {
        result: runner
        for runner in archive.resolved
        for result in runner.results
        if result.race_id == race.race_id
    }
    carry = baselines.CarryForward()
    carry_forward: dict[int, float | None] = {}
    for item in matching.with_outcome(cards.Outcome.FINISHED):
        runner = runner_of.get(item.result) if item.result is not None else None
        carry_forward[item.line.position] = (
            None if runner is None else carry.predict(runner, race, history).seconds
        )

    card = cards.evaluate(
        doc=doc,
        matching=matching,
        carry_forward=carry_forward,
        prediction={
            "file": file,
            "sha256": digest,
            "tag": tag,
            "tagged_at": tagged_at.isoformat(),
            "model": doc["model"]["name"],
            "commit": doc["model"]["commit"],
        },
        results={
            "race_id": race.race_id,
            "url": race.url,
            "sha256": predictions.sha256(page.encode("utf-8")),
        },
        scored_at=datetime.now(UTC),
    )
    SCORES.mkdir(exist_ok=True)
    (SCORES / f"{race_id}.json").write_bytes(predictions.to_bytes(card))
    RACE_PAGES.mkdir(parents=True, exist_ok=True)
    (RACE_PAGES / f"{race_id}.md").write_text(
        cards.race_page(card, matching), encoding="utf-8", newline="\n"
    )
    _write_live_rows()

    field = card["field"]
    errors = card["error"]["all"]
    typer.echo(
        f"{field['finished']} of {field['predicted']} predicted runners finished; "
        f"{field['unpredicted_finishers']} finishers had no prediction"
    )
    typer.echo(f"MAE {cards.ci(errors['mae_minutes'])} minutes")
    typer.echo(
        f"model minus carry-forward on {errors['carry_forward']['runners']} runners: "
        f"{cards.ci(errors['carry_forward']['difference_minutes'])} minutes"
    )
    for level in cards.LEVELS:
        held = card['intervals']['all'][level]['coverage']
        typer.echo(f"{level}% interval held: {cards.percent(held)}")
    typer.echo(
        f"wrote scores/{race_id}.json, docs/predictions/{race_id}.md and the README live rows"
    )


def _write_live_rows() -> None:
    """The README's live table, from every committed score card."""
    import json

    from finishline.publish import scorecard as cards

    loaded = [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(SCORES.glob("*.json"))
    ]
    readme = Path("README.md")
    text = report.replace_between(
        readme.read_text(encoding="utf-8"), "live", cards.live_table(loaded)
    )
    readme.write_text(text, encoding="utf-8", newline="\n")


def backtest_seed(race_id: str) -> int:
    """A seed fixed by the race, so a re-run of an unchanged freeze draws the same numbers."""
    import zlib

    return zlib.crc32(race_id.encode())


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
