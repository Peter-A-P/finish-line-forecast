"""Observed weather for a race morning, from Environment and Climate Change Canada.

Hourly observations at St. John's airport, published as one CSV per station-month under
the Open Government Licence Canada. These are observations and not a model, which is why
they are the backtest's basis: Overload measured Open-Meteo's modelled temperature about
six degrees off at this coast (PLAN.md section 0). The forecast, which has no observed
equivalent because the race has not happened, comes from Open-Meteo at freeze time and is
recorded with the prediction.

⚠️ **A station with no coverage returns 744 rows of blanks, not an error.** Asking station
50089 for October 2008 gives a complete-looking month with every temperature empty. That
is the third time this archive has offered silence instead of a refusal, after a parser
keyed on a ruler two thirds of the pages do not draw and an index heading that changed
wording in 2016. So `hourly` raises `NoObservation` rather than returning an empty tuple,
and the caller has to decide what to do about a race it has no weather for.

⚠️ **Two stations, and the handover is real.** "ST JOHN'S A" (6720) runs to the end of
2011 and "ST JOHN'S INTL A" (50089) starts in 2012; measured, not assumed, by asking both
for May and September of 2010 through 2014. A fetcher that knew only the current station
would have had no weather for the first four years of the archive and would not have said
so.

⚠️ **The timestamps are Local Standard Time all year.** ECCC does not shift for daylight
saving, so a race starting at 09:00 on a wall clock in July is at 08:00 in this file.
Every road race in this archive runs inside the daylight-saving period, so the conversion
is applied always and `LST_OFFSET_HOURS` says so out loud. Getting this wrong moves every
reading one hour earlier into the cool of the morning, which would bias the heat term the
same way every time and look like a small effect rather than an error.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Self

import httpx
import truststore

BULK = (
    "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"
    "?format=csv&stationID={station}&Year={year}&Month={month}&Day=14"
    "&timeframe=1&submit=Download+Data"
)

USER_AGENT = (
    "finishline/0.1 (Newfoundland road-race finish-time prediction; "
    "contact via github.com/Peter-A-P/finish-line-forecast)"
)
MIN_INTERVAL = 1.0
TIMEOUT = 60.0

# Newfoundland runs on daylight saving from March to November, and every road race in this
# archive falls inside it. ECCC timestamps are Local Standard Time in every month, so a
# wall-clock hour is this many hours later in the file.
LST_OFFSET_HOURS = -1


@dataclass(frozen=True, slots=True)
class Station:
    """One airport station and the years it actually carries hourly observations for."""

    station_id: int
    climate_id: str
    name: str
    first_year: int
    last_year: int


# Measured 2026-09-13 by asking both stations for May and September of 2010 to 2014: 6720
# answers through 2011 and nothing after, 50089 answers from 2012 and nothing before.
STATIONS: tuple[Station, ...] = (
    Station(6720, "8403506", "ST JOHN'S A", 1955, 2011),
    Station(50089, "8403505", "ST JOHN'S INTL A", 2012, 2100),
)


class NoObservation(Exception):
    """This station has no readings for this month, or none for this race's hours."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One hourly reading, timestamped in Local Standard Time as published."""

    at: datetime
    temp_c: float | None
    dew_point_c: float | None
    humidity_pct: float | None
    wind_kmh: float | None
    wind_from_deg: float | None

    @property
    def usable(self) -> bool:
        return self.temp_c is not None


@dataclass(frozen=True, slots=True)
class Conditions:
    """What a field ran through, averaged over the hours they were out there.

    Wind is kept twice, and the difference matters. `wind_kmh` is the mean speed, which is
    what a loop course feels: the wind costs you more into it than it gives back with it,
    whatever direction it is from. `wind_east` and `wind_north` are the mean *vector*,
    which is what a point-to-point course feels, and only the vector can tell a tailwind
    from a headwind. Averaging speeds and then asking about direction would answer the
    wrong question.
    """

    race_id: str
    hours: int
    temp_c: float
    dew_point_c: float | None
    humidity_pct: float | None
    wind_kmh: float | None
    wind_east: float | None
    wind_north: float | None
    station: str

    def tailwind(self, bearing_deg: float | None) -> float | None:
        """The wind's help along a course running on this bearing, in km/h.

        Positive is a tailwind. `bearing_deg` is the direction the runners travel, as a
        compass bearing; None for a loop or out-and-back course, where a net bearing is
        meaningless and the answer is None rather than zero.
        """
        if bearing_deg is None or self.wind_east is None or self.wind_north is None:
            return None
        radians = math.radians(bearing_deg)
        return self.wind_east * math.sin(radians) + self.wind_north * math.cos(radians)

    @property
    def apparent_load(self) -> float | None:
        """Temperature plus dew point, the sum runners and coaches actually use.

        Not a physiological model. Daniels' own guidance and most race heat policies key
        off the sum of temperature and dew point in the same units, because evaporative
        cooling fails when the air is already wet. It is used here as one number to put on
        the x-axis, and the hierarchical model estimates its coefficient rather than
        assuming one.
        """
        if self.dew_point_c is None:
            return None
        return self.temp_c + self.dew_point_c


def station_for(year: int) -> Station:
    """The station carrying hourly observations that year."""
    for station in STATIONS:
        if station.first_year <= year <= station.last_year:
            return station
    raise NoObservation(f"no St. John's station carries hourly observations for {year}")


class Cache:
    """Station-months on disk, fetched at most once, with a manifest of what came from where.

    An observation of a past hour does not change, so a month fetched is a month kept. The
    same contract as the results cache, and for the same reason: a full rerun of the
    pipeline should cost zero requests.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.months = root / "months"
        self.manifest = root / "manifest.jsonl"
        self._last_request = 0.0
        self._client: httpx.Client | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def path_for(self, station: Station, year: int, month: int) -> Path:
        return self.months / f"{station.station_id}_{year}{month:02d}.csv"

    def get(self, station: Station, year: int, month: int) -> str:
        path = self.path_for(station, year, month)
        if path.exists():
            return path.read_text(encoding="utf-8")
        body = self._fetch(BULK.format(station=station.station_id, year=year, month=month))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        self._record(station, year, month, body)
        return body

    def _fetch(self, url: str) -> str:
        if self._client is None:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._client = httpx.Client(
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                follow_redirects=True,
                verify=context,
            )
        wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.get(url)
            response.raise_for_status()
        finally:
            self._last_request = time.monotonic()
        # The bulk endpoint serves a byte-order mark; left in place it becomes part of the
        # first column's name and the temperature column is never found.
        return response.text.lstrip("﻿")

    def _record(self, station: Station, year: int, month: int, body: str) -> None:
        row = {
            "station_id": station.station_id,
            "climate_id": station.climate_id,
            "year": year,
            "month": month,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "bytes": len(body.encode("utf-8")),
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row) + "\n")


def _column(row: dict[str, str | None], prefix: str) -> str:
    """A value by the start of its column name, because the headers carry a degree sign.

    The temperature column is spelled "Temp (°C)". Matching it literally means writing
    that character into the source, and matching it by prefix does not.
    """
    for name, value in row.items():
        if name and name.strip().lower().startswith(prefix):
            return (value or "").strip()
    return ""


def _number(text: str) -> float | None:
    """A reading, or None where the station recorded none.

    ECCC puts a flag character in the value column for a missing or estimated reading, so
    anything that is not a number is not a reading.
    """
    try:
        return float(text)
    except ValueError:
        return None


def parse_month(body: str) -> tuple[Observation, ...]:
    """Every hourly row in one station-month CSV, readings and blanks alike."""
    observations: list[Observation] = []
    for row in csv.DictReader(io.StringIO(body)):
        stamp = _column(row, "date/time")
        if not stamp:
            continue
        try:
            at = datetime.strptime(stamp[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        wind_tens = _number(_column(row, "wind dir"))
        observations.append(
            Observation(
                at=at,
                temp_c=_number(_column(row, "temp (")),
                dew_point_c=_number(_column(row, "dew point temp (")),
                humidity_pct=_number(_column(row, "rel hum")),
                wind_kmh=_number(_column(row, "wind spd")),
                # Published in tens of degrees: "33" is 330 degrees, wind from the
                # north-north-west.
                wind_from_deg=None if wind_tens is None else wind_tens * 10.0,
            )
        )
    return tuple(observations)


def hourly(cache: Cache, when: date) -> tuple[Observation, ...]:
    """Every reading for one day, in Local Standard Time.

    Raises `NoObservation` rather than returning nothing, because a station outside its
    years answers with a full month of blanks and a caller that took that at face value
    would quietly run the whole backtest with no weather.
    """
    station = station_for(when.year)
    body = cache.get(station, when.year, when.month)
    month = parse_month(body)
    if not any(observation.usable for observation in month):
        raise NoObservation(
            f"station {station.station_id} ({station.name}) returned "
            f"{len(month)} rows for {when:%Y-%m} and not one temperature; "
            f"its coverage in STATIONS is probably wrong"
        )
    day = tuple(o for o in month if o.at.date() == when)
    if not any(observation.usable for observation in day):
        raise NoObservation(f"no reading at {station.name} on {when}")
    return day


def race_window(distance_m: float, start_hour: int = 9) -> tuple[int, int]:
    """The Local Standard Time hours a field of this distance is out on the road.

    ⚠️ **No results page in this archive prints a start time**, so the start is an
    assumption: 09:00 on a wall clock, which is when Newfoundland road races go. The window
    then runs to roughly when the back of the field finishes, because the last runner in a
    marathon meets four hours of weather and the winner of a 5 km meets fifteen minutes of
    it. Both ends are stated here rather than buried, and `start_hour` is an argument so
    the assumption can be moved and the effect measured.
    """
    hours = max(1, round(distance_m / 1000.0 * 0.09))
    first = start_hour + LST_OFFSET_HOURS
    return first, first + hours


def conditions(
    cache: Cache, race_id: str, when: date, distance_m: float, *, start_hour: int = 9
) -> Conditions:
    """The average conditions a field met, over the hours it was running."""
    first, last = race_window(distance_m, start_hour)
    readings = [o for o in hourly(cache, when) if first <= o.at.hour <= last and o.usable]
    if not readings:
        raise NoObservation(f"no reading between {first}:00 and {last}:00 LST on {when}")
    return average(race_id, readings, station_for(when.year).name)


def average(race_id: str, readings: list[Observation], station: str) -> Conditions:
    """The mean of a race's hourly readings, with the wind averaged as a vector.

    Shared by the observations and the forecast (`ingest.openmeteo`), because the two have
    to be averaged identically or the forecast error measured between them is partly the
    arithmetic.
    """
    if not readings:
        raise NoObservation(f"no readings for {race_id}")

    def mean(values: list[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return sum(present) / len(present) if present else None

    temperature = mean([o.temp_c for o in readings])
    if temperature is None:
        raise NoObservation(f"no temperature in the readings for {race_id}")

    # The vector mean. ECCC publishes the direction the wind comes *from*, so the air
    # travels the opposite way and both components carry a minus sign. Getting that
    # backwards turns every tailwind into a headwind and would fit a coefficient of exactly
    # the wrong sign, which is the sort of error that still produces a tidy table.
    east: list[float | None] = []
    north: list[float | None] = []
    for reading in readings:
        if reading.wind_kmh is None or reading.wind_from_deg is None:
            continue
        radians = math.radians(reading.wind_from_deg)
        east.append(-reading.wind_kmh * math.sin(radians))
        north.append(-reading.wind_kmh * math.cos(radians))

    return Conditions(
        race_id=race_id,
        hours=len(readings),
        temp_c=temperature,
        dew_point_c=mean([o.dew_point_c for o in readings]),
        humidity_pct=mean([o.humidity_pct for o in readings]),
        wind_kmh=mean([o.wind_kmh for o in readings]),
        wind_east=mean(east),
        wind_north=mean(north),
        station=station,
    )


# The races this station can speak for. St. John's airport is a fair proxy for a race on
# the Avalon and says nothing useful about one in Gander, Garnish, Bay Roberts or Labrador
# City, so those are named and excluded rather than quietly averaged in.
AWAY_FROM_ST_JOHNS = re.compile(
    r"gander|garnish|carved-by-the-sea|trapline|trappers|woodward|discovery-dash|"
    r"bell-island|run-from-away|oceanview|not-so-hilly"
)


def near_st_johns(course_id: str) -> bool:
    """Whether this course is close enough to the airport for its weather to mean anything."""
    return not AWAY_FROM_ST_JOHNS.search(course_id)
