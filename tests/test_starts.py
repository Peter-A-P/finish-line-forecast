"""Start times: the organisers' hours, the defaults, and that the weather is read from them."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline import starts
from finishline.ingest import eccc
from finishline.models import weather
from finishline.schema import Race


def race(course: str, metres: float) -> Race:
    return Race(f"{course}-2025", course, date(2025, 9, 7), metres, course, "")


def test_the_file_in_the_repository_loads_and_names_the_uniformed_services_run() -> None:
    table = starts.load()
    assert table.hour(race("usr-42195", 42_195.0)) == 7
    assert table.hour(race("usr-21097", 21_097.0)) == 8
    assert table.hour(race("usr-10000", 10_000.0)) == 9
    assert table.hour(race("tely-10-16093", 16_093.0)) == 8
    assert table.hour(race("five-and-dime-10000", 10_000.0)) == 9
    assert table.hour(race("quidi-vidi-10000", 10_000.0)) == 7, "the 2022 USR 10k, 7:30"
    assert table.hour(race("huffin-puffin-42195", 42_195.0)) == 7, "the USR under its old name"


def test_a_course_nobody_listed_takes_the_default_for_its_distance() -> None:
    table = starts.load()
    assert table.hour(race("somewhere-new-5000", 5_000.0)) == 8, "8 am is the standard"
    assert table.hour(race("huffin-puffin-42195", 42_195.0)) == 7, "marathons go at 7"


def test_no_file_means_the_defaults(tmp_path: Path) -> None:
    table = starts.load(tmp_path / "absent.toml")
    assert table.hour(race("x-10000", 10_000.0)) == starts.STANDARD_HOUR
    assert table.hour(race("x-42195", 42_195.0)) == starts.MARATHON_HOUR


def test_an_hour_that_is_not_an_hour_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "starts.toml"
    path.write_text('[courses]\n"x-5000" = 25\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not an hour"):
        starts.load(path)


class _WarmingMorning:
    """One September day that warms a degree an hour from 10 C at midnight, no wind."""

    def get(self, station: object, year: int, month: int) -> str:
        header = (
            '"Longitude (x)","Latitude (y)","Station Name","Climate ID","Date/Time (LST)",'
            '"Year","Month","Day","Time (LST)","Temp (°C)","Temp Flag",'
            '"Dew Point Temp (°C)","Rel Hum (%)","Wind Dir (10s deg)","Wind Spd (km/h)"'
        )
        rows = [
            f'"-52.75","47.62","ST JOHN\'S INTL A","8403505","2025-09-07 {h:02d}:00",'
            f'"2025","09","07","{h:02d}:00","{10 + h}.0","","8.0","80","27","20"'
            for h in range(24)
        ]
        return "\n".join([header, *rows]) + "\n"


def test_an_earlier_start_reads_a_cooler_morning() -> None:
    """The point of the file: a 7 am marathon met cooler hours than a 9 am one would have."""
    marathon = race("usr-42195", 42_195.0)
    seven, _ = weather.edition_conditions(
        [marathon], _WarmingMorning(), {}, None, {marathon.race_id: 7}
    )
    nine, _ = weather.edition_conditions(
        [marathon], _WarmingMorning(), {}, None, {marathon.race_id: 9}
    )
    assert nine[marathon.race_id][1] - seven[marathon.race_id][1] == pytest.approx(2.0)
    first, _ = eccc.race_window(42_195.0, 7)
    assert first == 7 + eccc.LST_OFFSET_HOURS
