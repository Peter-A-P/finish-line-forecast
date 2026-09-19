"""Forecast weather for a race morning, and the forecasts that were made for past ones.

Two Open-Meteo services, both free for non-commercial use with no key (docs/data-terms.md):

- **The forecast API** gives the forecast a live prediction is frozen with. There is no
  observation of a morning that has not happened.
- **The previous-runs API** keeps what the forecast said a day before each past morning
  (`temperature_2m_previous_day1` and so on). Set beside the airport's observation of that
  morning, it measures how wrong a day-ahead forecast is at this coast, which is the error a
  prediction frozen a day before the gun actually carries (`models.weather.ForecastError`).

⚠️ **Why the forecast is never used raw.** Overload measured Open-Meteo's modelled temperature
about six degrees off at this coast (PLAN.md section 0). The model's heat term is fitted on
observed temperatures, so a forecast that runs six degrees warm would add about three percent
to every Cape to Cabot prediction before anything else went wrong. The live prediction uses
the forecast corrected by the bias measured on past race mornings, and carries the remaining
forecast error as uncertainty.

⚠️ **Open-Meteo's hours are wall-clock, ECCC's are standard time all year.** Asked with
`timezone=America/St_Johns`, Open-Meteo returns local time with daylight saving applied, so a
race starting at 08:00 on the clock is hour 8 here and hour 7 in an ECCC file. The window is
computed for each source in its own convention (`window`), and a test pins that the two
cover the same instants.

Fetched under the same rails as every other source: an identifying user agent, one request a
second, and each response written under `data/cache/openmeteo/` with when it was fetched.
A forecast changes by the hour, so forecast responses are never reused; previous runs are
history and are fetched once.
"""

from __future__ import annotations

import json
import math
import ssl
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import truststore

from finishline.ingest.eccc import (
    LST_OFFSET_HOURS,
    TIMEOUT,
    USER_AGENT,
    Conditions,
    NoObservation,
    Observation,
    average,
    race_window,
)

# St. John's International Airport, where the observations the model is fitted on are made.
# The forecast is taken at the same point so that forecast and observation are about one place.
LATITUDE, LONGITUDE = 47.6186, -52.7519
TIMEZONE = "America/St_Johns"

FORECAST = "https://api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

VARIABLES = ("temperature_2m", "wind_speed_10m", "wind_direction_10m")
# How far behind today the reanalysis archive runs. A year fetched inside this window is
# incomplete and is fetched again later, the same rule the ECCC months follow.
ARCHIVE_LAG = timedelta(days=6)
# A clear noon's direct sun, the unit the share is measured in (TrainAI uses the same).
SUN_REFERENCE_W_M2 = 800.0
# The sun, which the airport does not record and the model needs: it is what makes a warm road
# feel hotter than the thermometer (`models.weather.heat`). Direct (beam) radiation rather than
# cloud cover, because 100% thin cirrus and 100% storm cloud are the same cloud cover and not
# the same sky, which is TrainAI's reasoning (project 11); the forecast carries it too.
SKY = "direct_radiation"
MIN_INTERVAL = 1.0

STATION = "Open-Meteo forecast, St. John's airport"


def forecast_params(day: date) -> dict[str, str]:
    """The query for one day's hourly forecast, in local wall-clock time."""
    return {
        "latitude": str(LATITUDE),
        "longitude": str(LONGITUDE),
        "timezone": TIMEZONE,
        "hourly": ",".join((*VARIABLES, SKY)),
        "wind_speed_unit": "kmh",
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
    }


def archive_params(year: int, today: date) -> dict[str, str]:
    """The query for one year of hourly direct sun, clamped to what the archive holds.

    The archive runs a few days behind, so the current year ends where it ends rather than on
    the 31st of December, and a rerun after those days have landed fetches the rest.
    """
    end = min(date(year, 12, 31), today - ARCHIVE_LAG)
    return {
        "latitude": str(LATITUDE),
        "longitude": str(LONGITUDE),
        "timezone": TIMEZONE,
        "hourly": SKY,
        "start_date": date(year, 1, 1).isoformat(),
        "end_date": end.isoformat(),
    }


# The longest lead the daily predictions need: a week before the gun.
LONGEST_LEAD_DAYS = 7


def previous_runs_params(start: date, end: date, lead: int = 1) -> dict[str, str]:
    """The query for what the forecast said `lead` days ahead, over a range of past days."""
    if not 1 <= lead <= LONGEST_LEAD_DAYS:
        raise ValueError(f"a lead of {lead} days is not one the previous-runs API keeps")
    return {
        "latitude": str(LATITUDE),
        "longitude": str(LONGITUDE),
        "timezone": TIMEZONE,
        "hourly": ",".join(f"{name}_previous_day{lead}" for name in VARIABLES),
        "wind_speed_unit": "kmh",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def window(distance_m: float, start_hour: int, *, wall_clock: bool) -> tuple[int, int]:
    """The hours a field is out on the road, in this source's clock.

    `eccc.race_window` returns standard-time hours; Open-Meteo's are wall-clock, one hour
    later through the whole racing season, so the offset is taken back out here.
    """
    first, last = race_window(distance_m, start_hour)
    if wall_clock:
        return first - LST_OFFSET_HOURS, last - LST_OFFSET_HOURS
    return first, last


def readings(body: dict[str, Any], *, suffix: str = "") -> list[Observation]:
    """Hourly readings from an Open-Meteo response, as observations in wall-clock time.

    `suffix` selects a previous-runs series, `_previous_day1`. A missing value (the API
    returns null where a model run is absent) makes that hour unusable rather than zero.
    """
    hourly = body.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise NoObservation(f"no hourly block in the response: {sorted(body)}")
    times = hourly["time"]
    temps = hourly.get(f"temperature_2m{suffix}")
    speeds = hourly.get(f"wind_speed_10m{suffix}")
    directions = hourly.get(f"wind_direction_10m{suffix}")
    if temps is None or speeds is None or directions is None:
        raise NoObservation(f"the response carries no {suffix or 'current'} series")
    out: list[Observation] = []
    for at, temp, speed, direction in zip(times, temps, speeds, directions, strict=True):
        out.append(
            Observation(
                at=datetime.fromisoformat(at),
                temp_c=_number(temp),
                dew_point_c=None,
                humidity_pct=None,
                wind_kmh=_number(speed),
                wind_from_deg=_number(direction),
            )
        )
    return out


def _number(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)  # type: ignore[arg-type]
    return None if math.isnan(number) else number


def sky_hours(body: dict[str, Any]) -> dict[tuple[date, int], float]:
    """Direct radiation per day and wall-clock hour, in W/m2, from any response."""
    hourly = body.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly or SKY not in hourly:
        raise NoObservation(f"the response carries no {SKY} series")
    out: dict[tuple[date, int], float] = {}
    for at, cover in zip(hourly["time"], hourly[SKY], strict=True):
        value = _number(cover)
        if value is None:
            continue
        when = datetime.fromisoformat(at)
        out[(when.date(), when.hour)] = value
    return out


def sun_share(
    sky: dict[tuple[date, int], float], day: date, distance_m: float, start_hour: int = 8
) -> float | None:
    """The direct sun over the hours this field was out, as a share of a clear noon, 0 to 1.

    None when the archive has no hour of that morning, which leaves the edition without sun
    rather than sunny: the model may not invent sunshine nobody recorded.
    """
    first, last = window(distance_m, start_hour, wall_clock=True)
    beams = [sky[(day, hour)] for hour in range(first, last + 1) if (day, hour) in sky]
    if not beams:
        return None
    return min(1.0, sum(beams) / len(beams) / SUN_REFERENCE_W_M2)


def conditions(
    hourly: Sequence[Observation],
    race_id: str,
    day: date,
    distance_m: float,
    start_hour: int,
    *,
    station: str = STATION,
) -> Conditions:
    """The average of a forecast over the hours this field will be running."""
    first, last = window(distance_m, start_hour, wall_clock=True)
    chosen = [
        reading
        for reading in hourly
        if reading.at.date() == day and first <= reading.at.hour <= last and reading.usable
    ]
    if not chosen:
        raise NoObservation(f"no forecast hour between {first}:00 and {last}:00 on {day}")
    return average(race_id, chosen, station)


class Client:
    """The polite fetcher: one connection, one request a second, every response kept."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._last = 0.0
        self._client = httpx.Client(
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )

    def close(self) -> None:
        self._client.close()

    def forecast(self, day: date) -> dict[str, Any]:
        """Today's forecast for a day. Never cached for reuse: a forecast is a moment."""
        return self._get(FORECAST, forecast_params(day), f"forecast-{day.isoformat()}")

    def archive(self, year: int, today: date) -> dict[str, Any]:
        """A year of hourly direct sun, fetched once, and again while the year is unfinished.

        ⚠️ **A year fetched before it ended is not that year.** The reanalysis runs about a
        week behind, so a request made in September returns January to September and nothing
        else; served back next spring it would leave every race of the autumn overcast, which
        is a silent wrong answer rather than a missing one. The cached response is reused only
        when it reaches the last day the archive could have held when it was fetched.
        """
        name = f"archive-{SKY}-{year}"
        cached = self.root / f"{name}.json"
        if cached.exists():
            record = json.loads(cached.read_text(encoding="utf-8"))
            body: dict[str, Any] = record["body"]
            wanted = archive_params(year, today)["end_date"]
            times = body.get("hourly", {}).get("time") or [""]
            if str(times[-1])[:10] >= wanted:
                return body
        return self._get(ARCHIVE, archive_params(year, today), name, keep=True)

    def previous_runs(self, start: date, end: date, lead: int = 1) -> dict[str, Any]:
        """Forecasts made `lead` days ahead for past days. History, so fetched once and kept."""
        name = f"previous-day{lead}-{start.isoformat()}-{end.isoformat()}"
        cached = self.root / f"{name}.json"
        if cached.exists():
            stored: dict[str, Any] = json.loads(cached.read_text(encoding="utf-8"))["body"]
            return stored
        return self._get(PREVIOUS_RUNS, previous_runs_params(start, end, lead), name, keep=True)

    def _get(
        self, url: str, params: dict[str, str], name: str, *, keep: bool = False
    ) -> dict[str, Any]:
        wait = MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        response = self._client.get(url, params=params)
        self._last = time.monotonic()
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        fetched = datetime.now(UTC)
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = "" if keep else f"-{fetched:%Y%m%dT%H%M%SZ}"
        record = {"url": str(response.url), "fetched_at": fetched.isoformat(), "body": body}
        (self.root / f"{name}{stamp}.json").write_text(
            json.dumps(record, sort_keys=True), encoding="utf-8"
        )
        return body
