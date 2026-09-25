"""Assembling a prediction file from a fitted model and a start list (PLAN.md 5.7).

Everything `finishline freeze` does except sampling the model and touching the disk, so that
the whole assembly is testable against a posterior built by hand. The command fits the model
on every result before the race, links the latest start list, reads the conformal shifts
from the saved backtest, and hands all of it here.

What happens to each entrant:

1. **Excluded if the linker refused them** (`identity.link`), and counted in `entrants`.
2. **A finish-time distribution** from `Posterior.predict`: the linked runner's own history,
   or the group prior for their listed sex.
3. **Intervals adjusted by the conformal shift for their history depth**, measured on every
   backtest race before this one (`conformal.split.shifts`). Where a depth has too few
   earlier races to calibrate on, the model's own interval is published and the file says so
   in `model.calibration`.
4. **A place range** from simulating the whole predicted field with one shared morning
   (`placing.simulate`).

**A race with no start list** (Run to Remember) has its field forecast instead
(`models.participation`, PLAN.md 5.6): the caller links the named runners as if a list had
printed them, and hands the whole candidate pool over as a `FieldForecast`. Their lines are
made exactly as above; their places come from a simulation that also draws who turns up
(`simulate.forecast_places`), and the file carries the backtest's recall and precision so a
reader knows how many of the names to expect at the start.

⚠️ **Two repairs, and why they are allowed.** Conformal shifts are computed separately per
level and may be negative, so an adjusted 80 percent interval can in principle shrink past the
median, and an adjusted 90 can come out narrower than the adjusted 80 on one side. Both would
be absurd to publish. The repair takes the outer edge in each case: the interval is widened to
contain the median, and the 90 to contain the 80. Widening never reduces coverage, so neither
repair can make a published interval less honest than the calibration measured.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from finishline.backtest.score import stratum_of
from finishline.conformal.split import bounds_for, widen
from finishline.history import History
from finishline.identity.link import Link, Status, counts
from finishline.models import blend
from finishline.models.hierarchical import QUANTILES, Posterior, summarise
from finishline.placing import simulate, unseen
from finishline.publish import daily
from finishline.publish.predictions import RunnerPrediction, check_gun, document
from finishline.schema import Race

LEVELS: tuple[float, ...] = (0.80, 0.90)


@dataclass(frozen=True, slots=True)
class LiveRace:
    """A race this project will publish a prediction for, as `data/live.toml` describes it."""

    race: Race
    gun: datetime
    # None for a race that publishes no start list: its field is forecast (PLAN.md 5.6).
    entrant_list: str | None
    # "course" draws newcomers from this course's past first-timers (`placing.unseen`); set
    # only for the few biggest races, where visitors with no results here reach the top ten.
    newcomers: str | None = None
    # The events on a shared entrant list that are this race (`entrants.for_events`). Empty
    # for a list that is one race. The Trapline's one list covers four races and kids' ones.
    entrant_events: tuple[str, ...] = ()
    # Races on one morning with one archive have one fit, not one each: the posterior depends
    # on the date and the data and nothing else about the race, and a fit on the whole
    # archive is half an hour and 27 GB. None means the race's own id.
    fit: str | None = None

    @property
    def fit_id(self) -> str:
        """Which saved fit this race uses and makes."""
        return self.fit or self.race.race_id


def load_live(path: Path, race_id: str) -> LiveRace:
    """One race from the live-race file, refusing anything a prediction cannot be frozen on.

    ⚠️ **The gun time must be written down with its zone, by a person.** It is not guessed
    from past editions: the 24-hour rule is measured from it, and a start time that is wrong
    by an hour moves the deadline by an hour in whichever direction it is wrong.
    """
    records: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    if race_id not in records:
        raise KeyError(f"{race_id} is not in {path}")
    record = records[race_id]
    gun_text = record.get("gun")
    if not gun_text:
        raise ValueError(f"{race_id} has no gun time in {path}; confirm it with the race")
    gun = datetime.fromisoformat(str(gun_text))
    if gun.tzinfo is None:
        raise ValueError(f"{race_id} gun time {gun_text} has no time zone")
    race = Race(
        race_id=race_id,
        name=str(record["name"]),
        date=date.fromisoformat(str(record["date"])),
        distance_m=float(record["distance_m"]),
        course_id=str(record["course_id"]),
        url=str(record.get("url", "")),
    )
    if gun.date() != race.date:
        raise ValueError(f"{race_id} gun {gun_text} is not on the race date {race.date}")
    newcomers = record.get("newcomers")
    if newcomers not in (None, "course"):
        raise ValueError(f"{race_id}: newcomers = {newcomers!r} is not a method this knows")
    listing = record.get("entrant_list")
    events = record.get("entrant_events", [])
    if events and listing is None:
        raise ValueError(f"{race_id}: entrant_events names events on a list it does not have")
    fit = record.get("fit")
    return LiveRace(
        race=race,
        gun=gun,
        entrant_list=None if listing is None else str(listing),
        newcomers=None if newcomers is None else str(newcomers),
        entrant_events=tuple(str(event) for event in events),
        fit=None if fit is None else str(fit),
    )


# How long before a live race the scheduled crawl stops, and how long after it resumes.
#
# ⚠️ A crawl that finds a new race makes the saved model backtest stale, and `freeze` refuses
# without a matching one. The final backtest before a freeze runs about a week out and takes
# hours, so the weekly crawl stands down ten days before the race and comes back the day
# after, when the race's own results are what it is waiting for.
CRAWL_PAUSE_BEFORE = timedelta(days=10)
CRAWL_PAUSE_AFTER = timedelta(days=1)


def crawl_paused(path: Path, today: date) -> str | None:
    """Why the scheduled crawl should not run today, or None when it may.

    Reads only the dates in the live-race file, so a race whose gun time is not confirmed
    yet still pauses the crawl around it.
    """
    if not path.exists():
        return None
    records: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    for race_id, record in sorted(records.items()):
        when = date.fromisoformat(str(record["date"]))
        if when - CRAWL_PAUSE_BEFORE <= today <= when + CRAWL_PAUSE_AFTER:
            return (
                f"paused from {when - CRAWL_PAUSE_BEFORE} to {when + CRAWL_PAUSE_AFTER} "
                f"around {race_id}, so no new race makes the saved backtest stale before "
                "its freeze"
            )
    return None


@dataclass(frozen=True, slots=True)
class FieldForecast:
    """Who might run a race with no start list, for the placing simulation and the file.

    `presence` holds every candidate the participation model scored, named or not, because
    the named runners are placed against everyone who might turn up, not only each other.
    `unseen_expected` is how many finishers are expected with no result in the window, drawn
    from `pool` when there is one. `record` is what the file says about all of it.
    """

    presence: Mapping[str, float]
    sexes: Mapping[str, str | None]
    unseen_expected: float
    record: dict[str, Any]


def entrant_ids(links: Sequence[Link]) -> list[str]:
    """The id each predicted entrant is known by, in list order.

    A newcomer needs an id the posterior cannot mistake for an archive runner, and the caller
    needs the same ids to hand over anything keyed by runner (the challenger's predictions,
    for the blend).
    """
    predicted = [item for item in links if item.status is not Status.AMBIGUOUS]
    return [
        item.runner.runner_id if item.runner is not None else f"entrant:{position}"
        for position, item in enumerate(predicted)
    ]


def assemble(
    *,
    posterior: Posterior,
    links: Sequence[Link],
    history: History,
    live: LiveRace,
    now: datetime,
    snapshot: dict[str, Any],
    model: dict[str, Any],
    calibration: Mapping[float, Mapping[str, float | None]],
    seed: int,
    conditions: np.ndarray | None = None,
    conditions_record: dict[str, Any] | None = None,
    already: daily.Published | None = None,
    only_new: bool = False,
    pool: unseen.Pool | None = None,
    challenger: Mapping[str, float] | None = None,
    forecast: FieldForecast | None = None,
) -> dict[str, Any]:
    """The prediction file for this race, validated by the caller's `write`.

    `conditions` is one row of weather covariates per posterior draw, from the corrected
    forecast (`models.weather.draws`), and `conditions_record` is what the file says about
    it. Both None predict an average morning, and the file says `null`.

    `already` is what the daily files have published (`daily.published`). With `only_new`
    this writes a daily file: the entrants in none of them, and no places. Without it, the
    final file: everyone, recomputed with the day-before forecast (Peter, 2026-09-19: a
    forecast made a week out is of poor value by then), the daily file each was first
    published in named beside them, and places for the whole field. The fit and each
    entrant's random numbers are the same as in the daily files, so the weather is the only
    thing that moves a runner's time between their daily line and their final one.

    `pool`, for the biggest races only (`placing.unseen`), draws every newcomer from how
    first-timers at this course finished against the returning field, in the simulation and
    in their own line, and the final file says how many top places are expected to go to
    runners with no results here. A newcomer's interval is then the spread of that pool,
    which is itself a measurement, and no conformal shift is added to it.

    `challenger` is the LightGBM prediction in seconds per entrant (`models.gbm`). With it,
    every runner both models answered for has their draws multiplied onto the blended centre
    (`models.blend`), in their own line and in the simulated field alike, so a published place
    and a published time are the same prediction. A runner drawn from the newcomer pool is
    left alone.

    `forecast`, for a race with no start list, replaces the simulation of a listed field with one
    that also draws who turns up (`simulate.forecast_places`); `links` are then the runners
    the participation model named, and `pool` places the runners it cannot see.
    """
    check_gun(live.gun, now)
    if forecast is not None and only_new:
        raise ValueError("a forecast field has no daily files: nobody enters it day by day")
    race = live.race
    earlier = already or {}

    predicted = [item for item in links if item.status is not Status.AMBIGUOUS]
    _new, carried, streams = daily.split(
        [daily.entrant_key(item.entrant) for item in predicted], earlier
    )
    ids = entrant_ids(links)
    field = [
        simulate.Entrant(runner_id, item.entrant.sex)
        for runner_id, item in zip(ids, predicted, strict=True)
    ]
    # First pass: each runner's own draws, from their own stream, which fix the factor that
    # moves them onto the blended centre. Drawing again below with the same stream repeats
    # them exactly, so the line, the simulated field and the factor are one prediction.
    scale: dict[str, float] = {}
    if challenger:
        for position, (runner_id, item) in enumerate(zip(ids, predicted, strict=True)):
            if runner_id not in challenger or (pool is not None and item.runner is None):
                continue
            drawn = posterior.predict(
                runner_id,
                item.entrant.sex,
                race,
                daily.runner_rng(seed, streams[position]),
                conditions,
            )
            median = float(summarise(drawn)[QUANTILES.index(0.50)])
            scale[runner_id] = blend.factor(median, challenger[runner_id])

    places: dict[str, simulate.Place] = {}
    newcomers: dict[str, Any] | None = None
    field_sizes: np.ndarray | None = None
    if forecast is not None:
        candidates = sorted(forecast.presence)
        placed_field, field_sizes = simulate.forecast_places(
            posterior,
            [
                simulate.Entrant(runner_id, forecast.sexes.get(runner_id))
                for runner_id in candidates
            ],
            np.array([forecast.presence[runner_id] for runner_id in candidates]),
            ids,
            race,
            np.random.default_rng(seed),
            conditions,
            challenger,
            forecast.unseen_expected,
            pool,
            scale,
        )
        places = {place.runner_id: place for place in placed_field}
    elif not only_new:
        simulated, placed = simulate.simulate_field(
            posterior, field, race, np.random.default_rng(seed), conditions, pool, scale
        )
        places = {place.runner_id: place for place in simulated}
        if pool is not None:
            columns = simulate.newcomer_columns(posterior, field)
            newcomers = {
                "method": "course pool",
                "course_id": pool.course_id,
                "pool_editions": pool.editions,
                "pool_first_timers": int(pool.everyone.size),
                "likely_places_top_20": unseen.likely_places(placed, columns, 20),
            }
            for top in (10, 20):
                mean, fewest, most = unseen.expected_in_top(placed, columns, top)
                newcomers[f"expected_in_top_{top}"] = {
                    "mean": round(mean, 2), "low": fewest, "high": most,
                }
    # A newcomer drawn from the pool stands against the known field of the same morning.
    known_field: np.ndarray | None = None
    if pool is not None and forecast is None:
        known = [entrant for entrant in field if entrant.runner_id in posterior.design.runner_index]
        if known:
            known_field = np.log(
                simulate.field_draws(
                    posterior,
                    known,
                    race,
                    daily.runner_rng(seed, "known-field"),
                    conditions,
                    scale=scale,
                )
            )

    lines: list[RunnerPrediction] = []
    for position, (runner_id, item) in enumerate(zip(ids, predicted, strict=True)):
        place = places.get(runner_id)
        median_place = None if place is None else place.median
        low_place = None if place is None else place.low
        high_place = None if place is None else place.high
        if position in carried and only_new:
            continue
        source = carried[position][0] if position in carried else None
        rng = daily.runner_rng(seed, streams[position])
        from_pool = pool is not None and known_field is not None and item.runner is None
        if from_pool:
            assert pool is not None and known_field is not None
            draws = np.exp(
                unseen.newcomer_log_times(known_field, [item.entrant.sex], pool, rng)[:, 0]
            )
        else:
            draws = posterior.predict(runner_id, item.entrant.sex, race, rng, conditions)
            draws = draws * scale.get(runner_id, 1.0)
        quantiles = summarise(draws)
        median = quantiles[QUANTILES.index(0.50)]
        depth = len(history.results_of(runner_id)) if item.runner is not None else 0
        stratum = stratum_of(depth)

        intervals: dict[float, tuple[float, float]] = {}
        for level in LEVELS:
            lower, upper = bounds_for(level)
            shift = None if from_pool else calibration.get(level, {}).get(stratum)
            low, high = widen(quantiles[lower], quantiles[upper], shift)
            if not (math.isfinite(low) and math.isfinite(high)):
                raise ValueError(f"an unbounded {level:.0%} interval for stratum {stratum}")
            intervals[level] = (min(low, median), max(high, median))
        low80, high80 = intervals[0.80]
        low90, high90 = intervals[0.90]
        intervals[0.90] = (min(low90, low80), max(high90, high80))

        lines.append(
            RunnerPrediction(
                name=item.entrant.name,
                hometown=item.runner.hometown if item.runner is not None else None,
                prior_results=depth,
                seconds=median,
                interval_80=intervals[0.80],
                interval_90=intervals[0.90],
                place=median_place,
                place_low=low_place,
                place_high=high_place,
                first_published=source,
            )
        )

    tally = counts(links)
    entrants = {
        "listed": len(links),
        "linked": tally[Status.LINKED.value],
        "new": tally[Status.NEW.value],
        "ambiguous": tally[Status.AMBIGUOUS.value],
        "predicted": len(lines),
    }
    if earlier:
        entrants["published_before"] = len(carried)
    doc = document(
        race={
            "race_id": race.race_id,
            "name": race.name,
            "date": race.date.isoformat(),
            "distance_m": race.distance_m,
            "course_id": race.course_id,
        },
        gun=live.gun,
        frozen_at=now,
        snapshot=snapshot,
        model={
            **model,
            "calibration": {
                f"{level * 100:.0f}": dict(sorted(calibration.get(level, {}).items()))
                for level in LEVELS
            },
        },
        conditions=conditions_record,
        entrants=entrants,
        runners=lines,
        daily=only_new,
    )
    if pool is not None and forecast is None:
        doc["newcomers"] = newcomers or {"method": "course pool", "course_id": pool.course_id}
    if forecast is not None:
        assert field_sizes is not None
        low, middle, high = np.quantile(field_sizes, [0.10, 0.5, 0.90])
        doc["field_forecast"] = {
            **forecast.record,
            "unseen_expected": round(forecast.unseen_expected, 1),
            "unseen_placed_from": None if pool is None else f"course pool: {pool.course_id}",
            "simulated_field": {
                "median": round(float(middle)),
                "low": round(float(low)),
                "high": round(float(high)),
                "largest": int(field_sizes.max()),
            },
        }
    return doc
