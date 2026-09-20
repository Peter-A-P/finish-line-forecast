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

import json
import os
import tomllib
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

from finishline import report, starts, store
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
ANE_RESULTS = DATA / "cache" / "ane"
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
    begins = starts.load()
    rows: list[conditions.Observation] = []
    skipped = 0
    with eccc.Cache(WEATHER) as weather:
        for race_id, effect in fitted.editions.items():
            race = data.races[race_id]
            if not eccc.near_st_johns(race.course_id):
                skipped += 1
                continue
            try:
                met = eccc.conditions(
                    weather, race_id, race.date, race.distance_m, start_hour=begins.hour(race)
                )
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

    # The airport records no sky, and sunshine is most of what makes a warm morning hard, so
    # the cloud cover comes from the Open-Meteo archive, a year at a time.
    from finishline.ingest import openmeteo

    years = sorted({race.date.year for race in races})
    client = openmeteo.Client(OPENMETEO)
    try:
        for year in years:
            body = client.archive(year, date.today())
            hours = len(body.get("hourly", {}).get("time", []))
            typer.echo(f"  sky {year}: {hours:,} hours")
    finally:
        client.close()
    typer.echo("done; nothing here is committed (see .gitignore)")


# The settings the published hierarchical run uses. `backtest` can be asked for others to
# experiment; `report` only ever publishes a run made with these, and the same run without
# weather beside it as the ablation.
HIERARCHICAL_DEFAULTS: dict[str, int] = {
    "months": 3, "draws": 300, "tune": 400, "chains": 4, "weather": 1,
}
NO_WEATHER = "hierarchical-no-weather"

Weather = dict[str, tuple[float, ...]]


def _challenger_rows(
    data: Dataset, scored_from: int, covariates: Weather, *, fit_if_missing: bool
) -> list[score.Scored] | None:
    """The LightGBM challenger's scored rows: saved if they match, fitted if asked to.

    Keyed like the hierarchical run, on the dataset, the covariates and the source of every
    module that shapes a prediction, so `report` never publishes rows from other code.
    """
    import hashlib

    from finishline.backtest import saved
    from finishline.metrics import daniels
    from finishline.models import gbm

    parts: dict[str, object] = {
        "scored_from": scored_from,
        "months": HIERARCHICAL_DEFAULTS["months"],
        "dataset": saved.dataset_fingerprint(data.races, data.results),
        "covariates": hashlib.sha256(json.dumps(sorted(covariates.items())).encode()).hexdigest(),
    }
    sources = [
        Path(gbm.__file__),
        Path(models_courses.__file__),
        Path(daniels.__file__),
        Path(run.__file__),
        Path(__file__).with_name("history.py"),
    ]
    run_key = saved.key(parts, sources)
    path = BACKTESTS / f"{gbm.NAME}.jsonl"
    rows = saved.load(path, run_key)
    if rows is None and fit_if_missing:
        model = gbm.Challenger(months=HIERARCHICAL_DEFAULTS["months"], conditions=covariates)
        rows = run.run(data.races, data.resolved, [model], scored_from=scored_from)
        for start, fitted in model.fits:
            typer.echo(f"  block {start}: trained on {fitted:,} finishes")
        saved.save(path, run_key, rows)
    return rows


def bearings() -> dict[str, float]:
    """Each point-to-point course's bearing, from data/courses.toml."""
    return {
        course_id: float(record["bearing_deg"])
        for course_id, record in course_profiles().items()
        if "bearing_deg" in record
    }


def _edition_sun(data: Dataset) -> dict[str, float]:
    """The direct sun over each race, as a share of a clear noon, from the cached archive.

    Read from the cache only: a race whose year has never been fetched is left without sun
    rather than fetched here, so that a model fit makes no requests. `finishline weather`
    is what fills this in.
    """
    from finishline.ingest import openmeteo

    shares: dict[str, float] = {}
    begins = starts.load()
    for year in sorted({race.date.year for race in data.races.values()}):
        cached = OPENMETEO / f"archive-{openmeteo.SKY}-{year}.json"
        if not cached.exists():
            continue
        sky = openmeteo.sky_hours(json.loads(cached.read_text(encoding="utf-8"))["body"])
        for race in data.races.values():
            if race.date.year != year:
                continue
            share = openmeteo.sun_share(sky, race.date, race.distance_m, begins.hour(race))
            if share is not None:
                shares[race.race_id] = share
    return shares


def _edition_weather(data: Dataset) -> tuple[Weather, int]:
    """Every edition's observed conditions: the airport's air and wind, the archive's sun."""
    from finishline.models import weather as weather_model

    sun = _edition_sun(data)
    hours = starts.load().by_race(data.races)
    with eccc.Cache(WEATHER) as cache:
        return weather_model.edition_conditions(
            data.races.values(), cache, bearings(), sun, hours
        )


def _hierarchical_key(
    data: Dataset, scored_from: int, settings: dict[str, int], covariates: Weather
) -> str:
    """What a saved hierarchical run has to match to be reused.

    A run with weather also has to match the covariates, because a weather month fetched
    again (`eccc.Cache.get`) changes the model's inputs as surely as a new race does.
    """
    import hashlib
    import json

    from finishline.backtest import saved
    from finishline.models import hierarchical
    from finishline.models import weather as weather_model

    parts: dict[str, object] = {
        "scored_from": scored_from,
        "dataset": saved.dataset_fingerprint(data.races, data.results),
        **settings,
    }
    if settings.get("weather"):
        parts["covariates"] = hashlib.sha256(
            json.dumps(sorted(covariates.items())).encode()
        ).hexdigest()
    sources = [
        Path(hierarchical.__file__),
        Path(weather_model.__file__),
        Path(run.__file__),
        Path(__file__).with_name("history.py"),
    ]
    return saved.key(parts, sources)


def _hierarchical_rows(
    data: Dataset,
    scored_from: int,
    settings: dict[str, int],
    covariates: Weather,
    *,
    fit_if_missing: bool,
) -> list[score.Scored] | None:
    """The hierarchical model's scored rows: saved if they match, sampled if asked to.

    The run without weather is saved to its own file and its rows are named `NO_WEATHER`,
    so the two runs sit side by side in every table as the ablation.
    """
    from dataclasses import replace

    from finishline.backtest import saved
    from finishline.models import hierarchical

    uses_weather = bool(settings.get("weather"))
    path = BACKTESTS / ("hierarchical.jsonl" if uses_weather else f"{NO_WEATHER}.jsonl")
    run_key = _hierarchical_key(data, scored_from, settings, covariates)
    rows = saved.load(path, run_key)
    if rows is None and fit_if_missing:
        weather = covariates if uses_weather else None

        def fitter(history: History) -> hierarchical.Posterior | None:
            typer.echo(f"  sampling on history before {history.origin} ...")
            return hierarchical.fit(
                history,
                draws=settings["draws"],
                tune=settings["tune"],
                chains=settings["chains"],
                weather=weather,
            )

        model = hierarchical.Hierarchical(
            months=settings["months"],
            fitter=fitter,
            weather=weather,
            checkpoint=saved.BlockStore(BACKTESTS / "blocks", run_key),
        )
        rows = run.run(data.races, data.resolved, [model], scored_from=scored_from)
        model.finish()
        for start, diagnostics in model.fits:
            typer.echo(f"  block {start}: {diagnostics}")
        saved.save(path, run_key, rows)
    if rows is None or uses_weather:
        return rows
    return [replace(row, model=NO_WEATHER) for row in rows]


def _blend_rows(
    data: Dataset, scored_from: int, covariates: Weather
) -> list[score.Scored] | None:
    """The blend's rows, from the two saved runs; None when either is missing or stale.

    Nothing is fitted here: blending is arithmetic on two saved predictions, and doing it from
    the saved rows is exactly what a freeze does to two live predictions (`models.blend`).
    """
    from finishline.models import blend

    hierarchical = _hierarchical_rows(
        data, scored_from, dict(HIERARCHICAL_DEFAULTS), covariates, fit_if_missing=False
    )
    challenger = _challenger_rows(data, scored_from, covariates, fit_if_missing=False)
    if hierarchical is None or challenger is None:
        return None
    return blend.rows([*hierarchical, *challenger])


@app.command()
def backtest(
    scored_from: Annotated[int, typer.Option(help="First year to score.")] = 2024,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    hierarchical: Annotated[
        bool,
        typer.Option(help="Score the hierarchical model too. Hours on first run; saved."),
    ] = False,
    weather: Annotated[
        bool,
        typer.Option(help="Fit and predict with each morning's observed weather."),
    ] = bool(HIERARCHICAL_DEFAULTS["weather"]),
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
    challenger: Annotated[
        bool,
        typer.Option(help="Score the LightGBM challenger too. Minutes on first run; saved."),
    ] = False,
) -> None:
    """Score the baselines at every origin and print the tables."""
    data = _dataset(first, last)
    scored = run.run(data.races, data.resolved, baselines.BASELINES, scored_from=scored_from)
    names = [model.name for model in baselines.BASELINES]
    model_name = None
    if hierarchical:
        settings = {
            "months": months, "draws": draws, "tune": tune, "chains": chains,
            "weather": int(weather),
        }
        covariates, missing = _edition_weather(data)
        if weather:
            typer.echo(f"{len(covariates)} editions with observed weather, {missing} without")
        rows = _hierarchical_rows(data, scored_from, settings, covariates, fit_if_missing=True)
        scored += rows or []
        model_name = "hierarchical" if weather else NO_WEATHER
        names.append(model_name)
    if challenger:
        from finishline.models import blend, gbm

        covariates, _missing = _edition_weather(data)
        scored += _challenger_rows(data, scored_from, covariates, fit_if_missing=True) or []
        names.append(gbm.NAME)
        if hierarchical:
            scored += blend.rows(scored)
            names.append(blend.NAME)
    races = len({row.race_id for row in scored})
    typer.echo(f"{races} races scored from {scored_from}, {len(scored):,} predictions\n")
    typer.echo(report.baseline_table(scored, names))
    typer.echo()
    typer.echo(report.placing_table(scored, names))
    for name in names[len(baselines.BASELINES):]:
        typer.echo()
        typer.echo(_coverage(data, scored, name))


def _coverage(
    data: Dataset, scored: list[score.Scored], model: str | None, *, assumption: bool = True
) -> str:
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
    return report.coverage_table(summaries, model, assumption=assumption)


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
    covariates, _missing = _edition_weather(data)
    saved_rows = _hierarchical_rows(
        data, scored_from, dict(HIERARCHICAL_DEFAULTS), covariates, fit_if_missing=False
    )
    if saved_rows is not None:
        scored += saved_rows
        names.append("hierarchical")
    else:
        typer.echo("no saved hierarchical run matches; its rows are left out of the tables")
    ablation = _hierarchical_rows(
        data,
        scored_from,
        {**HIERARCHICAL_DEFAULTS, "weather": 0},
        covariates,
        fit_if_missing=False,
    )
    if ablation is not None:
        scored += ablation
        names.append(NO_WEATHER)
    from finishline.models import blend, gbm

    challenger = _challenger_rows(data, scored_from, covariates, fit_if_missing=False)
    if challenger is not None:
        scored += challenger
        names.append(gbm.NAME)
    else:
        typer.echo("no saved challenger run matches; `backtest --challenger` makes one")
    blended = _blend_rows(data, scored_from, covariates)
    if blended is not None:
        scored += blended
        names.append(blend.NAME)

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
    baseline_text = report.baseline_table(scored, names)
    if saved_rows is not None and challenger is not None:
        # The challenger against the model it was built to test, and then the published blend
        # against each of its parents: the comparisons two overlapping MAE intervals cannot make.
        baseline_text += "\n\n" + report.paired_error_table(scored, gbm.NAME, "hierarchical")
        if blended is not None:
            baseline_text += "\n\n" + report.paired_error_table(
                scored, blend.NAME, "hierarchical"
            )
            baseline_text += "\n\n" + report.paired_error_table(scored, blend.NAME, gbm.NAME)
    text = report.replace_between(text, "baselines", baseline_text)
    text = report.replace_between(text, "placing", report.placing_table(scored, names))
    # The published model's coverage comes first, then each parent's, and the conformal
    # assumption is stated once, under the last table.
    published = None
    if saved_rows is not None:
        published = blend.NAME if blended is not None else "hierarchical"
    shown = [published, *(n for n in ("hierarchical", gbm.NAME) if n in names and n != published)]
    tables = [
        _coverage(data, scored, name, assumption=position == len(shown) - 1)
        for position, name in enumerate(shown)
    ]
    text = report.replace_between(text, "coverage", "\n\n".join(tables))
    readme.write_text(text, encoding="utf-8", newline="\n")
    _write_live_rows()
    typer.echo("README.md tables rewritten from the measurement")
    _write_showcase(data, scored, names, fitted, rows)
    typer.echo(f"{SHOWCASE} rewritten from the same measurement, for the website")


SHOWCASE = DATA / "site" / "results.json"


def _write_showcase(
    data: Dataset,
    scored: list[score.Scored],
    names: list[str],
    fitted: models_courses.Fit,
    weather_rows: list[conditions.Observation],
) -> None:
    """The website's numbers, from the objects the README's tables were just written from."""
    from finishline.conformal import split
    from finishline.identity import link
    from finishline.publish import showcase

    dates = {race_id: race.date for race_id, race in data.races.items()}
    live: dict[str, Any] = tomllib.loads(LIVE.read_text(encoding="utf-8"))
    temperatures = showcase.temperatures(weather_rows)
    model_rows = [row for row in scored if row.model == showcase.MODEL]
    intervals = split.rolling(model_rows, dates, 0.80) if model_rows else []
    profiles = course_profiles()
    races: dict[str, Any] = {}
    for race_id, record in live.items():
        course_id = str(record["course_id"])
        measured = fitted.courses.get(course_id)
        profile = profiles.get(course_id, {})
        story: dict[str, Any] = {
            "course_id": course_id,
            "course": showcase.course_name(course_id),
            "factor": None if measured is None else round(measured.factor, 4),
            "factor_low": None if measured is None else round(measured.low, 4),
            "factor_high": None if measured is None else round(measured.high, 4),
            "climb_m": profile.get("climb_m"),
            "drop_m": profile.get("drop_m"),
            "editions": showcase.editions(data, course_id, temperatures),
            "backtest": showcase.course_backtest(scored, intervals, data, course_id),
            "entrants": None,
        }
        listing = record.get("entrant_list")
        snapshot = entrants.latest_snapshot(ENTRANTS, str(listing)) if listing else None
        if snapshot is not None:
            links = link.link(entrants.load(snapshot), data.runners)
            as_of = date.fromtimestamp(snapshot.stat().st_mtime).isoformat()
            story["entrants"] = showcase.entrants(links, as_of)
        races[race_id] = story
    showcase.write(
        SHOWCASE,
        {
            "archive": showcase.archive(data),
            "backtest": showcase.backtest(scored, names, dates),
            "courses": showcase.course_list(
                fitted, {str(r["course_id"]): rid for rid, r in live.items()}
            ),
            "races": races,
        },
    )


OPENMETEO = DATA / "cache" / "openmeteo"
FORECAST_ERROR = DATA / "forecast_error.toml"
# The same measurement at every lead from one day to a week, for the daily files.
FORECAST_ERROR_BY_LEAD = DATA / "forecast_error_by_lead.toml"


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
    by_lead: dict[int, list[eccc.Observation]] = {}
    try:
        for lead in range(1, openmeteo.LONGEST_LEAD_DAYS + 1):
            by_lead[lead] = []
            for year in sorted({race.date.year for race in editions}):
                end = min(date(year, 12, 31), yesterday)
                body = client.previous_runs(date(year, 1, 1), end, lead)
                by_lead[lead] += openmeteo.readings(body, suffix=f"_previous_day{lead}")
    finally:
        client.close()

    begins = starts.load()

    def pairs_at(lead: int) -> tuple[list[tuple[eccc.Conditions, eccc.Conditions]], int]:
        pairs: list[tuple[eccc.Conditions, eccc.Conditions]] = []
        skipped = 0
        with eccc.Cache(WEATHER) as observed_cache:
            for race in editions:
                hour = begins.hour(race)
                try:
                    observed = eccc.conditions(
                        observed_cache, race.race_id, race.date, race.distance_m, start_hour=hour
                    )
                    predicted = openmeteo.conditions(
                        by_lead[lead], race.race_id, race.date, race.distance_m, hour
                    )
                except eccc.NoObservation:
                    skipped += 1
                    continue
                pairs.append((predicted, observed))
        return pairs, skipped

    pairs, skipped = pairs_at(1)
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

    tables = [
        "# How wrong Open-Meteo's forecast was on past race mornings at St. John's airport, by",
        "# how many days ahead it was made: forecast minus the ECCC observation over the same",
        f"# race hours. Written by `finishline forecast-error` on {datetime.now(UTC):%Y-%m-%d},",
        f"# from race editions near St. John's since {since}. Read by `finishline freeze --daily`,",
        "# which predicts each entrant with the forecast of the morning they were first",
        "# published. Do not edit by hand.",
    ]
    for lead in sorted(by_lead):
        at_lead = weather.measure(pairs_at(lead)[0])
        typer.echo(
            f"  {lead} day(s) ahead: temperature sd {at_lead.temp_sd:.2f} C, "
            f"wind sd {at_lead.wind_sd:.2f} km/h, {at_lead.mornings} mornings"
        )
        tables += ["", f'["{lead}"]']
        tables += [f"{name} = {value!r}" for name, value in at_lead.as_record().items()]
    FORECAST_ERROR_BY_LEAD.write_text(
        "\n".join(tables) + "\n", encoding="utf-8", newline="\n"
    )
    typer.echo(f"written to {FORECAST_ERROR_BY_LEAD}")


LIVE = DATA / "live.toml"
# The fit a prediction week reuses (publish/daily.py). Local: it is every runner's draws.
FREEZE_FITS = DATA / "cache" / "freeze"
PREDICTIONS = Path("predictions")


@app.command()
def freeze(
    race_id: Annotated[str, typer.Argument(help="A race in data/live.toml, e.g. c2c-2026.")],
    daily_file: Annotated[
        bool,
        typer.Option(
            "--daily", help="A daily file: only entrants no earlier daily file predicted."
        ),
    ] = False,
    first: Annotated[int, typer.Option(help="First year to read.")] = FIRST_YEAR,
    last: Annotated[int, typer.Option(help="Last year to read.")] = LAST_YEAR,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Assemble and report, but write no file: a rehearsal."),
    ] = False,
) -> None:
    """Write the prediction file for a race, and print the hash to publish with it.

    With `--daily`, from seven days out: a file of only the entrants in no earlier daily file
    (`publish/daily.py`). Without it, the day before: the final file with everyone and their
    places, published runners carried unchanged.

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
    from finishline.publish import daily, predictions
    from finishline.publish import freeze as freezing

    try:
        live = freezing.load_live(LIVE, race_id)
        predictions.check_gun(live.gun, datetime.now(UTC))
    except (KeyError, ValueError, predictions.FreezeRefused) as refusal:
        typer.echo(f"refused: {refusal}", err=True)
        raise typer.Exit(code=2) from refusal
    today = datetime.now(UTC).astimezone(live.gun.tzinfo).date()
    lead_days = (live.race.date - today).days
    if daily_file and lead_days > daily.FIRST_LEAD_DAYS:
        typer.echo(
            f"refused: daily files start {daily.FIRST_LEAD_DAYS} days out; "
            f"this race is {lead_days} away",
            err=True,
        )
        raise typer.Exit(code=2)

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
    covariates, _missing = _edition_weather(data)
    # The intervals are calibrated on the published model's own backtest errors, and the
    # published model is the blend (PLAN.md 13 item 35), so both saved runs have to match
    # this code and this data or there is nothing honest to calibrate on.
    saved_rows = _blend_rows(data, 2024, covariates)
    if saved_rows is None:
        typer.echo(
            "no saved backtest of the blend matches this code and data; run "
            "`backtest --hierarchical --challenger`"
        )
        raise typer.Exit(code=2)
    dates = {race_id_: race.date for race_id_, race in data.races.items()}
    calibration = {
        level: split.shifts(saved_rows, dates, level, live.race.date)
        for level in freezing.LEVELS
    }

    history = History.before(live.race.date, data.races, data.resolved)
    # One fit for the whole week (publish/daily.py): made on the first day, reused after, and
    # refused if the archive or the model code moved in between.
    fit_meta = {
        "race_id": race_id,
        "key": _hierarchical_key(data, 2024, dict(HIERARCHICAL_DEFAULTS), covariates),
    }
    saved_fit = daily.posterior_path(FREEZE_FITS, race_id)
    try:
        posterior = daily.load_posterior(saved_fit, fit_meta)
    except ValueError as refusal:
        typer.echo(f"refused: {refusal}", err=True)
        raise typer.Exit(code=2) from refusal
    if posterior is None:
        typer.echo(f"sampling on every result before {live.race.date} ...")
        posterior = hierarchical.fit(history, weather=covariates)
        if posterior is None:
            typer.echo("nothing to fit")
            raise typer.Exit(code=1)
        daily.save_posterior(saved_fit, posterior, {**fit_meta, "commit": commit})
    else:
        typer.echo(f"the week's fit, from {saved_fit}")
    conditions, conditions_record = _forecast(
        live, posterior.draws, backtest_seed(race_id), lead_days
    )
    already = daily.published(PREDICTIONS, race_id)
    pool = None
    if live.newcomers == "course":
        from finishline.placing import unseen

        pool = unseen.pool(
            list(history.runners.values()), history.races, live.race.course_id, live.race.date
        )
        if pool is not None:
            typer.echo(
                f"newcomers drawn from {pool.everyone.size} first-timers over {pool.editions} "
                f"editions of {pool.course_id}"
            )

    listed = entrants.load(snapshot_path)
    links_ = link.link(listed, data.runners)
    challenger = _challenger_predictions(history, links_, live, covariates, conditions)
    doc = freezing.assemble(
        posterior=posterior,
        links=links_,
        history=history,
        live=live,
        now=datetime.now(UTC),
        snapshot={
            "file": snapshot_path.name,
            "sha256": predictions.sha256(snapshot_path.read_bytes()),
        },
        model=_model_record(commit, live, posterior, challenger),
        calibration=calibration,
        seed=backtest_seed(race_id),
        conditions=conditions,
        conditions_record=conditions_record,
        already=already,
        only_new=daily_file,
        pool=pool,
        challenger=challenger,
    )
    if daily_file:
        path = daily.daily_path(PREDICTIONS, race_id, today)
        tag = f"predictions/{race_id}/daily-{today.isoformat()}"
        if not doc["runners"]:
            typer.echo("no entrant is new since the last daily file; nothing written")
            return
    else:
        path = PREDICTIONS / f"{race_id}.json"
        tag = f"predictions/{race_id}"
    if dry_run:
        problems = predictions.validate(doc)
        counted = doc["entrants"]
        typer.echo(
            f"\ndry run: {counted['predicted']} runners would be written to {path}, "
            f"{counted['ambiguous']} excluded as ambiguous, {counted['new']} with no history"
        )
        digest = predictions.sha256(predictions.to_bytes(doc))
        typer.echo(f"sha256 of what it would write: {digest}")
        typer.echo("schema: " + ("clean" if not problems else f"{len(problems)} problems"))
        for problem in problems[:5]:
            typer.echo(f"  {problem}")
        return
    digest = predictions.write(path, doc)
    counts = doc["entrants"]
    typer.echo(
        f"\nwrote {path}: {counts['predicted']} runners predicted, "
        f"{counts['ambiguous']} excluded as ambiguous, {counts['new']} with no history"
    )
    typer.echo(f"sha256 {digest}")
    typer.echo(f"tag {tag}")
    typer.echo(
        "\nNothing is committed or tagged. To make it count, before "
        f"{(live.gun - predictions.MINIMUM_NOTICE).isoformat()}:\n"
        f"  git add {path.as_posix()} && git commit -m \"Prediction: {race_id}\"\n"
        f"  git tag -a {tag} -m \"sha256 {digest}\"\n"
        f"  git push && git push origin {tag}"
    )


def _challenger_predictions(
    history: History,
    links: list[Any],
    live: Any,
    covariates: Weather,
    conditions: Any,
) -> dict[str, float]:
    """The challenger's predicted seconds per entrant, keyed as `freeze` keys its runners.

    Fitted here on the same history the posterior was fitted on, which is fixed for the whole
    prediction week (the scheduled crawl stands down around a live race), so every morning of
    a week refits the same model on the same rows and gets the same numbers back.

    The trees take one morning rather than a draw per morning: the middle of the corrected
    forecast, which is the same forecast the posterior's draws are spread around.
    """
    import numpy as np

    from finishline.identity.link import Status
    from finishline.models import gbm
    from finishline.publish import freeze as freezing

    fitted = gbm.fit(history, covariates)
    if fitted is None:
        typer.echo("the challenger has nothing to fit on; the blend falls back to the model")
        return {}
    morning = None if conditions is None else tuple(np.median(conditions, axis=0))
    factor = fitted.course_fit.prior_for(live.race.course_id)
    predicted = [item for item in links if item.status is not Status.AMBIGUOUS]
    answers: dict[str, float] = {}
    for runner_id, item in zip(freezing.entrant_ids(links), predicted, strict=True):
        prior = (
            gbm.history_rows(item.runner, history.races) if item.runner is not None else []
        )
        row = gbm.features(prior, live.race, item.entrant.sex, factor, morning)
        answers[runner_id] = fitted.quantiles(row, live.race)[gbm.QUANTILES.index(0.50)]
    typer.echo(f"the challenger, fitted on {fitted.rows:,} finishes, answered for {len(answers)}")
    return answers


def _model_record(
    commit: str, live: Any, posterior: Any, challenger: dict[str, float]
) -> dict[str, Any]:
    """What the prediction file says made it."""
    from finishline.models import blend, gbm

    record: dict[str, Any] = {
        "name": blend.NAME if challenger else "hierarchical",
        "commit": commit,
        "fit_on_results_before": live.race.date.isoformat(),
        "diagnostics": posterior.diagnostics,
        "settings": dict(HIERARCHICAL_DEFAULTS),
    }
    if challenger:
        record["blend"] = {
            "weight": blend.WEIGHT,
            "centre": f"(1 - w) * log(hierarchical) + w * log({gbm.NAME})",
            "distribution": "the hierarchical model's draws, scaled onto the blended centre",
            "challenger_answered": len(challenger),
        }
    return record


def _forecast(
    live: Any, draws: int, seed: int, lead_days: int = 1
) -> tuple[Any, dict[str, Any] | None]:
    """Covariate draws from today's forecast for the race, corrected, and what to record.

    The forecast is Open-Meteo's for the airport over the hours the field is running, taken
    at freeze time, corrected by the bias measured on past race mornings and spread by their
    error (`models.weather.draws`). A course the airport cannot speak for, or a forecast that
    cannot be had, predicts an average morning, and the file says which and why.
    """
    import httpx
    import numpy as np

    from finishline.ingest import openmeteo
    from finishline.models import weather as weather_model

    race = live.race
    if not eccc.near_st_johns(race.course_id):
        return None, {"used": False, "reason": "the airport cannot speak for this course"}
    client = openmeteo.Client(OPENMETEO)
    try:
        body = client.forecast(race.date)
        met = openmeteo.conditions(
            openmeteo.readings(body), race.race_id, race.date, race.distance_m, live.gun.hour
        )
        sun_share = openmeteo.sun_share(
            openmeteo.sky_hours(body), race.date, race.distance_m, live.gun.hour
        )
    except (OSError, ValueError, eccc.NoObservation, httpx.HTTPError) as failure:
        typer.echo(f"no usable forecast ({failure}); predicting an average morning", err=True)
        return None, {"used": False, "reason": f"no usable forecast: {failure}"}
    finally:
        client.close()

    from finishline.publish import daily

    # The error measured at this lead: a week out, the forecast is worse than the day before.
    error = daily.forecast_error_for(FORECAST_ERROR_BY_LEAD, FORECAST_ERROR, lead_days)
    bearing = bearings().get(race.course_id)
    # No forecast sun is treated as none, which never adds sunshine nobody forecast.
    sun = 0.0 if sun_share is None else sun_share
    drawn = weather_model.draws(
        met, error, race.distance_m, bearing, draws, np.random.default_rng(seed), sun
    )
    typer.echo(
        f"forecast {met.temp_c:.1f} C, wind {met.wind_kmh} km/h, sun {sun:.0%} of a clear noon "
        f"over {met.hours} hours; corrected by {-error.temp_bias:+.1f} C and "
        f"{-error.wind_bias:+.1f} km/h"
    )
    return drawn, {
        "used": True,
        "source": openmeteo.STATION,
        "hours": met.hours,
        "forecast": {
            "temp_c": round(met.temp_c, 2),
            "wind_kmh": None if met.wind_kmh is None else round(met.wind_kmh, 2),
            "wind_east_kmh": None if met.wind_east is None else round(met.wind_east, 2),
            "wind_north_kmh": None if met.wind_north is None else round(met.wind_north, 2),
            "sun_share": None if sun_share is None else round(sun_share, 3),
        },
        "bearing_deg": bearing,
        "lead_days": lead_days,
        "forecast_error": {
            key: round(value, 4) if isinstance(value, float) else value
            for key, value in error.as_record().items()
        },
        "conditions_mean": dict(
            zip(
                weather_model.CONDITIONS,
                (round(float(v), 4) for v in drawn.mean(axis=0)),
                strict=True,
            )
        ),
    }


SCORES = Path("scores")
RACE_PAGES = Path("docs") / "predictions"


def _git_bytes(*args: str) -> bytes | None:
    """A git command's output as bytes, or None when git refuses."""
    import subprocess

    done = subprocess.run(["git", *args], capture_output=True, check=False)
    return done.stdout if done.returncode == 0 else None


@app.command(name="due")
def due() -> None:
    """Which live races want a prediction file today, and which kind: one line per race.

    `daily` from seven days before the race to two, `final` the day before. Read by
    scripts/daily-predictions.ps1, which runs each morning in the prediction week.
    """
    from datetime import UTC, datetime

    from finishline.publish import daily
    from finishline.publish import freeze as freezing

    records: dict[str, Any] = tomllib.loads(LIVE.read_text(encoding="utf-8"))
    for race_id in sorted(records):
        if "entrant_list" not in records[race_id]:
            continue
        try:
            live = freezing.load_live(LIVE, race_id)
        except (KeyError, ValueError):
            continue
        lead = (live.race.date - datetime.now(UTC).astimezone(live.gun.tzinfo).date()).days
        if lead == 1:
            typer.echo(f"{race_id} final")
        elif 2 <= lead <= daily.FIRST_LEAD_DAYS:
            typer.echo(f"{race_id} daily")


@app.command(name="site")
def site(
    out: Annotated[Path, typer.Option(help="Where to write the website.")] = Path("site"),
) -> None:
    """Build the public website from data/live.toml and the committed prediction files.

    Run by the Website workflow on every push (docs/deploy.md), so it reads nothing that is
    not committed.
    """
    from finishline.publish import site as website

    pages = website.build(out, LIVE, PREDICTIONS, SCORES, date.today())
    typer.echo(f"wrote {len(pages)} pages to {out}")


@app.command(name="serve")
def serve(
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8080,
    directory: Annotated[Path, typer.Option(help="The built site.")] = Path("site"),
) -> None:
    """Serve the built site locally with the headers the host will send.

    A plain file server sends none of the headers in `staticwebapp.config.json`, so it shows
    a page the content security policy would partly refuse; on project 08 that hid a broken
    chart on the live site for two weeks. This sends what Azure will send.
    """
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    config = directory / "staticwebapp.config.json"
    if not config.exists():
        typer.echo(f"no {config}; run `finishline site` first")
        raise typer.Exit(code=1)
    declared = json.loads(config.read_text(encoding="utf-8"))
    headers: dict[str, str] = declared.get("globalHeaders", {})

    class Handler(SimpleHTTPRequestHandler):
        """A file server that adds the host's headers to every response."""

        def end_headers(self) -> None:
            for key, value in headers.items():
                self.send_header(key, value)
            super().end_headers()

    typer.echo(f"serving {directory} on http://localhost:{port} with {len(headers)} headers")
    handler = partial(Handler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as http:
        try:
            http.serve_forever()
        except KeyboardInterrupt:
            typer.echo("stopped")


@app.command(name="page")
def race_page(
    race_id: Annotated[str, typer.Argument(help="A race in data/live.toml, e.g. tt-2026.")],
) -> None:
    """Rewrite the race's page from every prediction file published for it so far.

    Reads predictions/<race>/daily-*.json and predictions/<race>.json and nothing else, so the
    page never says more than the files do. `score` replaces it after the race.
    """
    from finishline.publish import daily, predictions, racepage

    paths = sorted((PREDICTIONS / race_id).glob(f"{daily.DAILY_PREFIX}*.json"))
    final = PREDICTIONS / f"{race_id}.json"
    if final.exists():
        paths.append(final)
    if not paths:
        typer.echo(f"no prediction file for {race_id} yet")
        raise typer.Exit(code=2)
    files = [
        (path.name, json.loads(path.read_text(encoding="utf-8")),
         predictions.sha256(path.read_bytes()))
        for path in paths
    ]
    RACE_PAGES.mkdir(parents=True, exist_ok=True)
    page = RACE_PAGES / f"{race_id}.md"
    page.write_text(racepage.before_the_gun(files), encoding="utf-8", newline="\n")
    typer.echo(f"wrote {page} from {len(files)} file(s)")


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
        return store.build(cache, races, external_dir=EXTERNAL, ane_dir=ANE_RESULTS)


def cache_catalogue(
    cache: nlaa.Cache, first: int, last: int
) -> tuple[list[Race], list[tuple[str, str]]]:
    """The catalogue over a year range, as the commands want it."""
    return nlaa.catalogue(cache, range(first, last + 1))


if __name__ == "__main__":  # pragma: no cover
    app()
