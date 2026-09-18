"""Weather covariates, and a forecast corrected by what past forecasts got wrong."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from finishline.ingest.eccc import Conditions
from finishline.models import weather
from finishline.schema import Race


def met(
    temp: float, speed: float = 20.0, east: float = 0.0, north: float = 0.0
) -> Conditions:
    return Conditions("r", 3, temp, None, None, speed, east, north, "test")


def test_a_neutral_or_unobserved_morning_is_all_zeros() -> None:
    assert weather.covariates(None, 20_000.0, 321.0) == weather.NEUTRAL
    assert weather.covariates(met(10.0), 10_000.0, None) == (0.0, 0.0, 0.0, 0.0)


def test_the_heat_term_grows_with_distance() -> None:
    temp, per_distance, wind, tail = weather.covariates(met(20.0, 30.0), 20_000.0, None)
    assert temp == 10.0
    assert per_distance == pytest.approx(10.0 * math.log(2.0))
    assert wind == 10.0
    assert tail == 0.0, "a loop course has no tailwind, whatever the wind"


def test_a_westerly_is_a_headwind_on_cape_to_cabot() -> None:
    westerly = met(10.0, 30.0, east=30.0)
    assert weather.covariates(westerly, 20_000.0, 321.0)[3] < -15


def test_bias_is_forecast_minus_observed() -> None:
    pairs = [(met(t + 6.0, 25.0, 2.0), met(t, 20.0, 0.0)) for t in (5.0, 9.0, 12.0, 15.0)]
    error = weather.measure(pairs)
    assert error.mornings == 4
    assert error.temp_bias == pytest.approx(6.0)
    assert error.temp_sd == pytest.approx(0.0)
    assert error.wind_bias == pytest.approx(5.0)
    assert error.east_bias == pytest.approx(2.0)


def test_too_few_mornings_is_a_refusal() -> None:
    with pytest.raises(ValueError, match="too few"):
        weather.measure([(met(10.0), met(9.0))])


def test_a_warm_forecast_is_cooled_by_its_bias_and_spread_by_its_error() -> None:
    """Six degrees warm, as Overload measured: the draws centre on the corrected morning."""
    error = weather.ForecastError(40, 6.0, 1.5, 0.0, 4.0, 0.0, 3.0, 0.0, 3.0)
    drawn = weather.draws(met(21.0, 20.0), error, 20_000.0, 321.0, 50_000, np.random.default_rng(1))
    assert drawn.shape == (50_000, 4)
    assert drawn[:, 0].mean() == pytest.approx(5.0, abs=0.05)  # 21 - 6 - 10
    assert drawn[:, 0].std() == pytest.approx(1.5, abs=0.05)


def test_a_drawn_tailwind_is_never_stronger_than_the_drawn_wind() -> None:
    error = weather.ForecastError(40, 0.0, 1.0, 0.0, 8.0, 0.0, 6.0, 0.0, 6.0)
    drawn = weather.draws(
        met(10.0, 5.0, east=4.0, north=1.0), error, 16_093.0, 70.0, 20_000, np.random.default_rng(2)
    )
    speed = drawn[:, 2] + 20.0
    assert (np.abs(drawn[:, 3]) <= speed + 1e-9).all()
    assert (speed >= 0).all()


class _Month:
    """A station-month cache serving one October day at 12 C with a 30 km/h westerly."""

    def get(self, station: object, year: int, month: int) -> str:
        header = (
            '"Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time (LST)",'
            '"Year","Month","Day","Time (LST)","Temp (°C)","Temp Flag",'
            '"Dew Point Temp (°C)","Rel Hum (%)","Wind Dir (10s deg)","Wind Spd (km/h)"'
        )
        rows = [
            f'"-52.75","47.62","ST JOHN\'S INTL A","8403505","2025-10-19 {h:02d}:30",'
            f'"2025","10","19","{h:02d}:30","12.0","","8.0","80","27","30"'
            for h in range(24)
        ]
        return "\n".join([header, *rows]) + "\n"


def test_editions_get_observed_covariates_and_the_rest_are_counted() -> None:
    races = [
        Race("c2c-2025", "c2c", date(2025, 10, 19), 20_000.0, "cape-to-cabot-20000", ""),
        Race("gander-2025", "g", date(2025, 10, 19), 10_000.0, "gander-10000", ""),
        Race("c2c-2025-other-day", "c2c", date(2025, 10, 20), 20_000.0, "cape-to-cabot-20000", ""),
    ]
    observed, missing = weather.edition_covariates(
        races, _Month(), {"cape-to-cabot-20000": 321.0}
    )
    assert set(observed) == {"c2c-2025"}
    assert missing == 2, "Gander is too far from the airport, and one day has no reading"
    temp, _, wind, tail = observed["c2c-2025"]
    assert temp == pytest.approx(2.0)
    assert wind == pytest.approx(10.0)
    assert tail < -15, "a westerly into Cape to Cabot's north-west bearing is a headwind"


def test_a_measurement_round_trips_through_its_file(tmp_path: Path) -> None:
    error = weather.ForecastError(37, 1.25, 1.9, -2.5, 6.1, 0.4, 5.2, -0.3, 4.8)
    path = tmp_path / "forecast_error.toml"
    weather.save(path, error, "Measured on 37 race mornings.\n\nSource: test.")
    assert weather.load(path) == error
    assert path.read_text(encoding="utf-8").startswith("# Measured on 37 race mornings.")
