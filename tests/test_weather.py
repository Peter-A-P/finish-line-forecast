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


def test_an_unobserved_morning_is_all_zeros_and_costs_nothing() -> None:
    assert weather.row(None, 20_000.0, 321.0) == weather.NEUTRAL
    parameters = np.array([[0.01, 0.01, 0.01, 0.01, 8.0]])
    assert weather.effect(np.array([weather.NEUTRAL]), parameters)[0] == 0.0


def test_a_row_carries_the_raw_morning() -> None:
    morning = weather.row(met(20.0, 30.0), 20_000.0, None, 0.6)
    observed, temp, sun, log_distance, wind, tail = morning
    assert (observed, temp, sun, wind, tail) == (1.0, 20.0, 0.6, 10.0, 0.0)
    assert log_distance == pytest.approx(math.log(4.0)), "pivoted at 5 km"
    assert weather.row(met(20.0), 5_000.0, None)[3] == 0.0
    assert weather.row(met(20.0), 10_000.0, None, 1.7)[2] == 1.0, "a share is at most a clear noon"


def cost(temp: float, sun: float, boost: float, distance_m: float = 5_000.0) -> float:
    rows = np.array([weather.row(met(temp), distance_m, None, sun)])
    rows[0, 4] = 0.0  # no wind, so only the heat is measured
    return float(weather.effect(rows, np.array([[0.01, 0.005, 0.0, 0.0, boost]]))[0])


def test_a_cold_morning_costs_nothing_and_is_not_a_bonus() -> None:
    """The hinge: below the threshold there is no heat, and no negative heat either."""
    assert cost(2.0, 0.0, 8.0) == 0.0
    assert cost(-8.0, 1.0, 8.0) == 0.0
    assert weather.heat(5.0, 1.0, 5.0) == 0.0


def test_sunshine_only_matters_once_it_is_warm() -> None:
    """Sun raises the felt temperature; on a cool morning that is still under the threshold."""
    knee = weather.HEAT_THRESHOLD_C
    assert cost(knee - 6.0, 1.0, 5.0) == 0.0, "a cloudless cool morning is still a cool one"
    assert cost(knee + 4.0, 0.0, 5.0) == pytest.approx(0.04)
    assert cost(knee + 4.0, 1.0, 5.0) == pytest.approx(0.09)
    assert cost(knee + 4.0, 0.5, 5.0) == pytest.approx(0.065)
    assert cost(knee + 4.0, 1.0, 0.0) == cost(knee + 4.0, 0.0, 5.0), "no boost, no sun"


def test_heat_costs_more_the_longer_the_race() -> None:
    assert cost(20.0, 0.0, 0.0, 42_195.0) > cost(20.0, 0.0, 0.0, 10_000.0) > cost(20.0, 0.0, 0.0)


def test_an_edition_without_a_sky_record_has_no_sun() -> None:
    """Missing sky may not invent sunshine."""
    assert weather.row(met(16.0), 10_000.0, None)[2] == 0.0


def test_a_westerly_is_a_headwind_on_cape_to_cabot() -> None:
    westerly = met(10.0, 30.0, east=30.0)
    assert weather.row(westerly, 20_000.0, 321.0)[5] < -15


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
    assert drawn.shape == (50_000, len(weather.CONDITIONS))
    assert drawn[:, 1].mean() == pytest.approx(15.0, abs=0.05)  # 21 - 6
    assert drawn[:, 1].std() == pytest.approx(1.5, abs=0.05)
    assert (drawn[:, 0] == 1.0).all()


def test_a_forecast_draw_carries_the_forecast_sun_as_given() -> None:
    error = weather.ForecastError(40, 0.0, 3.0, 0.0, 4.0, 0.0, 3.0, 0.0, 3.0)
    drawn = weather.draws(met(18.0), error, 20_000.0, None, 2_000, np.random.default_rng(3), 0.7)
    assert (drawn[:, 2] == 0.7).all(), "the sun carries no forecast error yet, and says so"
    assert np.allclose(drawn[:, 3], math.log(4.0))


def test_a_drawn_tailwind_is_never_stronger_than_the_drawn_wind() -> None:
    error = weather.ForecastError(40, 0.0, 1.0, 0.0, 8.0, 0.0, 6.0, 0.0, 6.0)
    drawn = weather.draws(
        met(10.0, 5.0, east=4.0, north=1.0), error, 16_093.0, 70.0, 20_000, np.random.default_rng(2)
    )
    speed = drawn[:, 4] + 20.0
    assert (np.abs(drawn[:, 5]) <= speed + 1e-9).all()
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
    observed, missing = weather.edition_conditions(
        races, _Month(), {"cape-to-cabot-20000": 321.0}
    )
    assert set(observed) == {"c2c-2025"}
    assert missing == 2, "Gander is too far from the airport, and one day has no reading"
    _, temp, sun, _, wind, tail = observed["c2c-2025"]
    assert temp == pytest.approx(12.0)
    assert sun == 0.0, "no sky record, no sun"
    assert wind == pytest.approx(10.0)
    assert tail < -15, "a westerly into Cape to Cabot's north-west bearing is a headwind"

    sunny, _ = weather.edition_conditions(
        races, _Month(), {"cape-to-cabot-20000": 321.0}, {"c2c-2025": 0.9}
    )
    assert sunny["c2c-2025"][2] == pytest.approx(0.9)


def test_a_measurement_round_trips_through_its_file(tmp_path: Path) -> None:
    error = weather.ForecastError(37, 1.25, 1.9, -2.5, 6.1, 0.4, 5.2, -0.3, 4.8)
    path = tmp_path / "forecast_error.toml"
    weather.save(path, error, "Measured on 37 race mornings.\n\nSource: test.")
    assert weather.load(path) == error
    assert path.read_text(encoding="utf-8").startswith("# Measured on 37 race mornings.")
