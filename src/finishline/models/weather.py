"""Weather as the hierarchical model sees it, and what a day-ahead forecast gets wrong.

COVARIATES
----------
Each race edition enters the model with four numbers, the same terms the conditions layer
measured (`models.conditions`, PLAN.md section 13 items 17 to 20): degrees above neutral, the
same multiplied by log distance (a marathon meets four hours of heat, a 5 km fifteen minutes),
wind speed above neutral, and tailwind along the course bearing. An edition with no observation
enters at neutral, all zeros, so its weather is left in its edition effect as before.

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
from finishline.models.conditions import (
    NEUTRAL_TEMP_C,
    NEUTRAL_WIND_KMH,
    REFERENCE_DISTANCE_M,
)
from finishline.schema import Race

COLUMNS: tuple[str, ...] = ("temp", "temp_x_log_distance", "wind", "tailwind")
NEUTRAL: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


class _Months(Protocol):
    """What `eccc.conditions` needs from a cache: one station-month's CSV."""

    def get(self, station: Station, year: int, month: int) -> str: ...


def edition_covariates(
    races: Iterable[Race],
    cache: _Months,
    bearings: Mapping[str, float],
) -> tuple[dict[str, tuple[float, float, float, float]], int]:
    """Every edition's observed covariates, and how many editions had no observation.

    An edition on a course the airport cannot speak for (`eccc.near_st_johns`), or on a
    morning with no reading, is left out of the mapping and so enters the model at neutral.
    The count is returned so that the number of editions carrying weather is reported rather
    than assumed.
    """
    observed: dict[str, tuple[float, float, float, float]] = {}
    missing = 0
    for race in races:
        if not near_st_johns(race.course_id):
            missing += 1
            continue
        try:
            met = eccc_conditions(cache, race.race_id, race.date, race.distance_m)  # type: ignore[arg-type]
        except NoObservation:
            missing += 1
            continue
        observed[race.race_id] = covariates(met, race.distance_m, bearings.get(race.course_id))
    return observed, missing


def covariates(
    met: Conditions | None, distance_m: float, bearing_deg: float | None
) -> tuple[float, float, float, float]:
    """The model's four weather numbers for one edition, or neutral when unobserved."""
    if met is None:
        return NEUTRAL
    temp = met.temp_c - NEUTRAL_TEMP_C
    wind = (met.wind_kmh if met.wind_kmh is not None else NEUTRAL_WIND_KMH) - NEUTRAL_WIND_KMH
    tailwind = met.tailwind(bearing_deg)
    return (
        temp,
        temp * math.log(distance_m / REFERENCE_DISTANCE_M),
        wind,
        0.0 if tailwind is None else tailwind,
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
) -> np.ndarray:
    """(n, 4) covariate draws for a forecast morning: corrected for bias, spread by the error.

    The spread is widened by `sqrt(1 + 1/mornings)`, the predictive allowance for a bias that
    was itself estimated from a few dozen mornings rather than known.
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

    log_distance = math.log(distance_m / REFERENCE_DISTANCE_M)
    temp_above = temp - NEUTRAL_TEMP_C
    if bearing_deg is None:
        tailwind = np.zeros(n)
    else:
        radians = math.radians(bearing_deg)
        tailwind = east * math.sin(radians) + north * math.cos(radians)
    return np.column_stack(
        [temp_above, temp_above * log_distance, speed - NEUTRAL_WIND_KMH, tailwind]
    )
