"""Observed weather, and the three ways this source lies quietly.

A station outside its years answers with a full month of blanks; the timestamps never
shift for daylight saving; and the temperature column is spelled with a degree sign. Each
one has its own test, because each would have produced a plausible number rather than an
error.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline.ingest import eccc

HEADER = (
    '"Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time (LST)",'
    '"Year","Month","Day","Time (LST)","Temp (°C)","Temp Flag",'
    '"Dew Point Temp (°C)","Rel Hum (%)","Wind Dir (10s deg)","Wind Spd (km/h)"'
)


def _month(rows: list[tuple[int, str, str, str, str, str]]) -> str:
    """A station-month CSV, as ECCC serves one."""
    lines = [HEADER]
    for hour, temp, dew, humidity, direction, speed in rows:
        lines.append(
            f'"-52.75","47.62","ST JOHN\'S INTL A","8403505",'
            f'"2025-10-19 {hour:02d}:30","2025","10","19","{hour:02d}:30",'
            f'"{temp}","","{dew}","{humidity}","{direction}","{speed}"'
        )
    return "\n".join(lines) + "\n"


FULL = _month([(hour, f"{8 + hour * 0.5:.1f}", "5.0", "80", "27", "30") for hour in range(24)])
BLANK = _month([(hour, "", "", "", "", "") for hour in range(24)])


class _Canned:
    """A cache that serves one body and counts how often it was asked."""

    def __init__(self, body: str) -> None:
        self.body = body
        self.calls = 0

    def get(self, station: eccc.Station, year: int, month: int) -> str:
        self.calls += 1
        return self.body


def test_the_temperature_column_is_found_despite_its_degree_sign() -> None:
    readings = eccc.parse_month(FULL)
    assert len(readings) == 24
    assert readings[0].temp_c == pytest.approx(8.0)
    assert readings[0].dew_point_c == pytest.approx(5.0)
    assert readings[0].humidity_pct == pytest.approx(80.0)


def test_wind_direction_is_published_in_tens_of_degrees() -> None:
    """"27" is 270 degrees, a westerly. Read as 27 it is a north-north-easterly."""
    assert eccc.parse_month(FULL)[0].wind_from_deg == pytest.approx(270.0)


def test_a_station_outside_its_years_raises_rather_than_returning_blanks() -> None:
    """The failure this module exists to prevent.

    Asking station 50089 for October 2008 returns 744 complete-looking rows with every
    temperature empty. Taken at face value the whole backtest runs with no weather and
    nothing says so, which is what a ruler-keyed parser and a renamed index heading each
    did to this project already.
    """
    with pytest.raises(eccc.NoObservation, match="not one temperature"):
        eccc.hourly(_Canned(BLANK), date(2025, 10, 19))  # type: ignore[arg-type]


def test_the_two_stations_cover_the_archive_without_a_gap_or_an_overlap() -> None:
    """Measured by asking both for May and September of 2010 to 2014."""
    assert eccc.station_for(2008).station_id == 6720
    assert eccc.station_for(2011).station_id == 6720
    assert eccc.station_for(2012).station_id == 50089
    assert eccc.station_for(2026).station_id == 50089
    years = {year for station in eccc.STATIONS for year in range(2008, 2027)}
    for year in years:
        eccc.station_for(year)  # every year of the archive resolves to exactly one station


def test_the_window_is_shifted_out_of_wall_clock_time() -> None:
    """ECCC stamps Local Standard Time in every month, including July.

    A 09:00 race is at 08:00 in the file. Reading it as 09:00 shifts every race an hour
    later into the warmth, which biases the heat term the same way every time and would
    look like a modest effect rather than a mistake.
    """
    first, last = eccc.race_window(10_000.0, start_hour=9)
    assert first == 8
    assert eccc.LST_OFFSET_HOURS == -1
    assert last > first


def test_a_longer_race_meets_more_weather() -> None:
    """A marathon field is out for hours; a 5 km field is not."""
    short = eccc.race_window(5_000.0)
    long = eccc.race_window(42_195.0)
    assert (long[1] - long[0]) > (short[1] - short[0])
    assert long[1] - long[0] >= 3


def test_conditions_average_only_the_hours_the_field_was_running() -> None:
    canned = _Canned(FULL)
    measured = eccc.conditions(
        canned,  # type: ignore[arg-type]
        "race",
        date(2025, 10, 19),
        10_000.0,
        start_hour=9,
    )
    first, last = eccc.race_window(10_000.0, start_hour=9)
    assert measured.hours == last - first + 1
    expected = [8 + hour * 0.5 for hour in range(first, last + 1)]
    assert measured.temp_c == pytest.approx(sum(expected) / len(expected))
    assert measured.apparent_load == pytest.approx(measured.temp_c + 5.0)


def test_a_race_the_airport_cannot_speak_for_is_named_not_averaged_in() -> None:
    """St. John's airport says nothing useful about a race in Labrador City."""
    assert eccc.near_st_johns("cape-to-cabot-20000")
    assert eccc.near_st_johns("mews-memorial-8000")
    assert not eccc.near_st_johns("trapline-42195")
    assert not eccc.near_st_johns("commander-gander-10000")


def test_a_month_is_fetched_once(tmp_path: Path) -> None:
    canned = _Canned(FULL)
    eccc.hourly(canned, date(2025, 10, 19))  # type: ignore[arg-type]
    eccc.hourly(canned, date(2025, 10, 19))  # type: ignore[arg-type]
    assert canned.calls == 2, "hourly does not cache; the Cache does"

    cache = eccc.Cache(tmp_path)
    station = eccc.station_for(2025)
    cache.path_for(station, 2025, 10).parent.mkdir(parents=True, exist_ok=True)
    cache.path_for(station, 2025, 10).write_text(FULL, encoding="utf-8")
    assert cache.get(station, 2025, 10) == FULL


def test_a_month_fetched_before_it_ended_is_fetched_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A race on the 13th, read on the 20th, must not leave the 27th with no weather."""
    import os
    from datetime import datetime

    cache = eccc.Cache(tmp_path)
    station = eccc.station_for(2025)
    path = cache.path_for(station, 2025, 10)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("half a month", encoding="utf-8")
    written = datetime(2025, 10, 20, 12, 0).timestamp()
    os.utime(path, (written, written))
    monkeypatch.setattr(cache, "_fetch", lambda url: FULL)
    assert cache.get(station, 2025, 10) == FULL
    assert cache.get(station, 2025, 10) == FULL, "and kept once the month is over"
