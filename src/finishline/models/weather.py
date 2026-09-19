"""Weather as the hierarchical model sees it, and what a day-ahead forecast gets wrong.

CONDITIONS
----------
Each race edition enters the model as six raw numbers, not as finished covariates: whether it
was observed, the air temperature, the share of a clear noon's direct sun over the race hours,
log distance over 5 km, wind speed above neutral, and tailwind along the course bearing. The
heat is computed from them inside the model, because the sun's contribution is a parameter:

    felt  = temperature + sun_boost x sun
    heat  = max(0, felt - HEAT_THRESHOLD_C)
    cost  = heat x (heat_0 + heat_1 x log(distance / 5 km)) + wind terms

An edition with no observation enters with `observed` at zero, and its weather stays in its
edition effect as before.

⚠️ **Heat, not temperature, and the sun is part of it, at a size the data sets.** A linear
temperature says a 2 C morning is as much better than a 6 C one as a 20 C morning is worse than
a 16 C one; it scored 0.184 out of sample against 0.35 for a hinge (PLAN.md 13 item 30). Where
the knee sits the two tests of item 30 disagree, editions wanting it low and the same runners
wanting it high; 12 C is the value whose worst shortfall across both is smallest. How much the
sun adds could not be settled by a grid on a 9 km reanalysis sky, so the model estimates it,
under a prior on the scale of the NWS figure TrainAI uses, 15 F for full sun.

FORECAST ERROR
--------------
A live prediction has a forecast, not an observation, and the coefficients were fitted on
observations. `ForecastError` measures, on past race mornings, how a forecast made the day
before differed from what the airport then recorded: a bias per variable and a spread. A live
forecast is corrected by the bias and then drawn with the spread, so a prediction frozen on a
forecast is as uncertain as a forecast is, and no more certain than one.

⚠️ **The wind is corrected as a vector.** Speed and the east and north components are measured
separately, and the draws perturb the components, from which both the speed and the tailwind
are recomputed. Perturbing the speed and the direction independently would produce a tailwind
stronger than the wind, which is a physical impossibility with a tidy mean.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from finishline.ingest.eccc import Conditions, NoObservation, Station, near_st_johns
from finishline.ingest.eccc import conditions as eccc_conditions
from finishline.models.conditions import NEUTRAL_WIND_KMH
from finishline.schema import Race

# One edition's conditions, in this order. Unobserved is all zeros.
CONDITIONS: tuple[str, ...] = (
    "observed", "temp_c", "sun", "log_distance_5k", "wind", "tailwind",
)
NEUTRAL: tuple[float, ...] = (0.0,) * len(CONDITIONS)

# The model's weather parameters, in the order `Posterior.weather` stores them.
PARAMETERS: tuple[str, ...] = ("heat", "heat_x_log_distance", "wind", "tailwind", "sun_boost")

# Felt temperature above which heat costs anything. Chosen, not fitted: on item 30's two tests
# the editions put the knee at 2 to 6 C and the same runners at 12 to 18 C, and 12 C is the
# value whose worst shortfall across both is smallest (0.115 of out-of-sample R2).
HEAT_THRESHOLD_C = 12.0

# The sun, as the direct (beam) radiation over the race hours as a share of a clear noon's
# 800 W/m2, which is TrainAI's measure: 100% thin cirrus and 100% storm cloud are the same
# cloud cover and not the same sky.
SUN_REFERENCE_W_M2 = 800.0

# The scale of the prior on what a full sun adds, in degrees: the US National Weather
# Service's "up to 15 F" in direct sunlight, which TrainAI (project 11) adopts. A HalfNormal on
# this scale allows anything from nothing to about twice that, so the posterior is the data's
# answer rather than the prior's.
SUN_PRIOR_SCALE_C = 15.0 * 5.0 / 9.0

# Heat is scaled by log distance over five kilometres, so that the scaling term is zero at the
# shortest distance raced here and positive above it. With both heat coefficients held
# positive in the model, the cost of a hot morning is never negative and never falls with
# distance; fitted free against ten kilometres, the same data claimed heat makes a 5 km fast.
HEAT_PIVOT_M = 5_000.0

# The start assumed when no start hour is given: the standard here (`finishline.starts`).
DEFAULT_START_HOUR = 8


class _Months(Protocol):
    """What `eccc.conditions` needs from a cache: one station-month's CSV."""

    def get(self, station: Station, year: int, month: int) -> str: ...


def edition_conditions(
    races: Iterable[Race],
    cache: _Months,
    bearings: Mapping[str, float],
    sun: Mapping[str, float] | None = None,
    start_hours: Mapping[str, int] | None = None,
) -> tuple[dict[str, tuple[float, ...]], int]:
    """Every observed edition's conditions, and how many editions had no observation.

    An edition on a course the airport cannot speak for (`eccc.near_st_johns`), or on a
    morning with no reading, is left out of the mapping and so enters the model unobserved.
    The count is returned so that the number of editions carrying weather is reported rather
    than assumed. `sun` maps an edition to its share of a clear noon's direct sun; an edition
    missing from it enters with no sun, which never invents a sunny morning. `start_hours`
    maps an edition to its wall-clock start (`finishline.starts`), which sets the hours read.
    """
    observed: dict[str, tuple[float, ...]] = {}
    missing = 0
    for race in races:
        if not near_st_johns(race.course_id):
            missing += 1
            continue
        try:
            met = eccc_conditions(
                cache,  # type: ignore[arg-type]
                race.race_id,
                race.date,
                race.distance_m,
                start_hour=(start_hours or {}).get(race.race_id, DEFAULT_START_HOUR),
            )
        except NoObservation:
            missing += 1
            continue
        observed[race.race_id] = row(
            met, race.distance_m, bearings.get(race.course_id), (sun or {}).get(race.race_id, 0.0)
        )
    return observed, missing


def row(
    met: Conditions | None,
    distance_m: float,
    bearing_deg: float | None,
    sun: float = 0.0,
) -> tuple[float, ...]:
    """One edition's conditions for the model, or `NEUTRAL` when unobserved."""
    if met is None:
        return NEUTRAL
    wind = (met.wind_kmh if met.wind_kmh is not None else NEUTRAL_WIND_KMH) - NEUTRAL_WIND_KMH
    tailwind = met.tailwind(bearing_deg)
    return (
        1.0,
        met.temp_c,
        min(1.0, max(0.0, sun)),
        math.log(distance_m / HEAT_PIVOT_M),
        wind,
        0.0 if tailwind is None else tailwind,
    )


def heat(temp_c: float, sun: float, boost: float) -> float:
    """Felt heat above the threshold: zero on a cool morning, and never negative.

    ⚠️ **Sunshine has no effect of its own; it raises the temperature a runner meets.** So a
    cloudless 6 C morning still costs nothing, and the sun only matters once the air is warm
    enough for the extra degrees to cross the threshold.
    """
    return max(0.0, temp_c + boost * sun - HEAT_THRESHOLD_C)


def effect(rows: np.ndarray, parameters: np.ndarray) -> np.ndarray:
    """What each morning costs, as a log ratio, for rows and parameters drawn together.

    `rows` is (n, len(CONDITIONS)) and `parameters` (n, len(PARAMETERS)), one posterior draw
    each; the model computes the same thing inside PyMC (`hierarchical.build`), and a test
    pins the two to agree.
    """
    rows = np.asarray(rows, dtype=float)
    observed, temp, sun, log_distance, wind, tailwind = rows.T
    heat_0, heat_1, wind_cost, tail_cost, boost = np.asarray(parameters, dtype=float).T
    hot = observed * np.maximum(0.0, temp + boost * sun - HEAT_THRESHOLD_C)
    return np.asarray(
        hot * (heat_0 + heat_1 * log_distance) + wind_cost * wind + tail_cost * tailwind
    )


@dataclass(frozen=True, slots=True)
class ForecastError:
    """How a day-ahead forecast differed from the observation, over past race mornings.

    Biases are forecast minus observed, so a positive temperature bias is a forecast that
    runs warm and is corrected by subtracting it.
    """

    mornings: int
    temp_bias: float
    temp_sd: float
    wind_bias: float
    wind_sd: float
    east_bias: float
    east_sd: float
    north_bias: float
    north_sd: float

    def as_record(self) -> dict[str, float | int]:
        return {name: getattr(self, name) for name in self.__slots__}


def measure(pairs: Sequence[tuple[Conditions, Conditions]]) -> ForecastError:
    """Bias and spread from (forecast, observed) pairs for the same race hours."""
    usable = [
        (forecast, observed)
        for forecast, observed in pairs
        if None
        not in (
            forecast.wind_kmh,
            observed.wind_kmh,
            forecast.wind_east,
            observed.wind_east,
            forecast.wind_north,
            observed.wind_north,
        )
    ]
    if len(usable) < 3:
        raise ValueError(f"{len(usable)} usable mornings is too few to measure a forecast")

    def spread(values: list[float]) -> tuple[float, float]:
        array = np.asarray(values, dtype=float)
        return float(array.mean()), float(array.std(ddof=1))

    temp = spread([f.temp_c - o.temp_c for f, o in usable])
    wind = spread([float(f.wind_kmh) - float(o.wind_kmh) for f, o in usable])  # type: ignore[arg-type]
    east = spread([float(f.wind_east) - float(o.wind_east) for f, o in usable])  # type: ignore[arg-type]
    north = spread([float(f.wind_north) - float(o.wind_north) for f, o in usable])  # type: ignore[arg-type]
    return ForecastError(len(usable), *temp, *wind, *east, *north)


def save(path: Path, error: ForecastError, provenance: str) -> None:
    """Write the measurement where `freeze` reads it, with where it came from."""
    lines = [f"# {line}" if line else "#" for line in provenance.splitlines()]
    lines.append("")
    lines += [f"{name} = {value!r}" for name, value in error.as_record().items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def load(path: Path) -> ForecastError:
    record = tomllib.loads(path.read_text(encoding="utf-8"))
    return ForecastError(**record)


def draws(
    forecast: Conditions,
    error: ForecastError,
    distance_m: float,
    bearing_deg: float | None,
    n: int,
    rng: np.random.Generator,
    sun: float = 0.0,
) -> np.ndarray:
    """(n, 6) condition draws for a forecast morning: corrected for bias, spread by the error.

    The spread is widened by `sqrt(1 + 1/mornings)`, the predictive allowance for a bias that
    was itself estimated from a few dozen mornings rather than known.

    ⚠️ **The forecast sun is used as given, with no error of its own.** Temperature and wind
    carry a measured day-ahead error and are drawn with it; the direct radiation is not, so a
    prediction is that much more confident about the sun than it has earned. At most it moves
    the felt temperature by the fitted sun boost, and that is written down here rather than
    hidden.
    """
    widen = math.sqrt(1.0 + 1.0 / error.mornings)
    temp = forecast.temp_c - error.temp_bias + widen * error.temp_sd * rng.standard_normal(n)
    if forecast.wind_east is None or forecast.wind_north is None:
        east = np.zeros(n)
        north = np.zeros(n)
    else:
        east = (
            forecast.wind_east - error.east_bias + widen * error.east_sd * rng.standard_normal(n)
        )
        north = (
            forecast.wind_north
            - error.north_bias
            + widen * error.north_sd * rng.standard_normal(n)
        )
    speed_mean = (
        forecast.wind_kmh if forecast.wind_kmh is not None else NEUTRAL_WIND_KMH
    ) - error.wind_bias
    speed = np.maximum(speed_mean + widen * error.wind_sd * rng.standard_normal(n), 0.0)
    # The mean speed can never be less than the speed of the mean vector.
    speed = np.maximum(speed, np.hypot(east, north))

    log_distance = math.log(distance_m / HEAT_PIVOT_M)
    if bearing_deg is None:
        tailwind = np.zeros(n)
    else:
        radians = math.radians(bearing_deg)
        tailwind = east * math.sin(radians) + north * math.cos(radians)
    return np.column_stack(
        [
            np.ones(n),
            temp,
            np.full(n, min(1.0, max(0.0, sun))),
            np.full(n, log_distance),
            speed - NEUTRAL_WIND_KMH,
            tailwind,
        ]
    )
