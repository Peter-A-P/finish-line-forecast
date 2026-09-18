"""Open-Meteo forecasts: the clock, the gaps, and the wind's direction. No network."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from finishline.ingest import eccc, openmeteo

DAY = date(2026, 10, 18)


def response(
    *,
    suffix: str = "",
    temps: list[float | None] | None = None,
    speed: float = 20.0,
    direction: float = 270.0,
) -> dict[str, Any]:
    hours = [f"{DAY.isoformat()}T{hour:02d}:00" for hour in range(24)]
    return {
        "utc_offset_seconds": -9000,
        "hourly": {
            "time": hours,
            f"temperature_2m{suffix}": (
                temps if temps is not None else [float(h) for h in range(24)]
            ),
            f"wind_speed_10m{suffix}": [speed] * 24,
            f"wind_direction_10m{suffix}": [direction] * 24,
        },
    }


def test_the_two_clocks_cover_the_same_instants() -> None:
    """08:00 wall clock in October is 07:00 in ECCC's standard time; both mean one moment."""
    wall = openmeteo.window(20_000.0, 8, wall_clock=True)
    standard = openmeteo.window(20_000.0, 8, wall_clock=False)
    assert wall == (8, 10)
    assert standard == (7, 9)
    as_instants = [datetime(2026, 10, 18, h) for h in wall]
    offset = timedelta(hours=eccc.LST_OFFSET_HOURS)
    from_standard = [datetime(2026, 10, 18, h) - offset for h in standard]
    assert as_instants == from_standard


def test_a_forecast_is_averaged_over_the_race_hours_only() -> None:
    hourly = openmeteo.readings(response())
    met = openmeteo.conditions(hourly, "c2c-2026", DAY, 20_000.0, 8)
    assert met.hours == 3
    assert met.temp_c == pytest.approx(9.0)  # hours 8, 9, 10
    assert met.station == openmeteo.STATION


def test_a_westerly_forecast_is_air_moving_east() -> None:
    """Wind from 270 blows toward the east: a tailwind on the Tely, a headwind at Cape to Cabot."""
    met = openmeteo.conditions(openmeteo.readings(response()), "x", DAY, 10_000.0, 9)
    assert met.wind_east == pytest.approx(20.0)
    assert met.wind_north == pytest.approx(0.0, abs=1e-9)
    tely = met.tailwind(70.0)
    c2c = met.tailwind(321.0)
    assert tely is not None and tely > 15
    assert c2c is not None and c2c < -10


def test_a_missing_hour_is_unusable_not_zero_degrees() -> None:
    temps: list[float | None] = [10.0] * 24
    temps[8] = None
    met = openmeteo.conditions(
        openmeteo.readings(response(temps=temps)), "x", DAY, 20_000.0, 8
    )
    assert met.hours == 2
    assert met.temp_c == pytest.approx(10.0)


def test_the_day_ahead_series_is_read_by_its_suffix() -> None:
    body = response(suffix="_previous_day1", speed=12.0)
    hourly = openmeteo.readings(body, suffix="_previous_day1")
    assert hourly[9].wind_kmh == pytest.approx(12.0)
    with pytest.raises(eccc.NoObservation, match="current"):
        openmeteo.readings(body)


def test_no_hours_in_the_window_is_a_refusal() -> None:
    with pytest.raises(eccc.NoObservation, match="no forecast hour"):
        tomorrow = DAY + timedelta(days=1)
        openmeteo.conditions(openmeteo.readings(response()), "x", tomorrow, 20_000.0, 8)


def test_the_queries_ask_for_local_time_and_the_airport() -> None:
    live = openmeteo.forecast_params(DAY)
    past = openmeteo.previous_runs_params(date(2024, 1, 1), date(2024, 12, 31))
    for query in (live, past):
        assert query["timezone"] == "America/St_Johns"
        assert query["wind_speed_unit"] == "kmh"
    assert "temperature_2m_previous_day1" in past["hourly"]
