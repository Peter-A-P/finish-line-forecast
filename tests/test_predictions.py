"""The prediction file: the 24-hour rule, a stable hash, no overwrite, and a schema that bites."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from finishline.publish import predictions as pf

NEWFOUNDLAND = timezone(timedelta(hours=-2, minutes=-30))
GUN = datetime(2026, 10, 18, 8, 0, tzinfo=NEWFOUNDLAND)


def line(name: str, seconds: float, place: float) -> pf.RunnerPrediction:
    return pf.RunnerPrediction(
        name=name,
        hometown="St. John's",
        prior_results=4,
        seconds=seconds,
        interval_80=(seconds * 0.93, seconds * 1.08),
        interval_90=(seconds * 0.90, seconds * 1.12),
        place=place,
        place_low=max(1.0, place - 1),
        place_high=min(2.0, place + 1),
    )


def doc(**overrides: Any) -> dict[str, Any]:
    base = pf.document(
        race={
            "race_id": "c2c-2026",
            "name": "Cape to Cabot",
            "date": "2026-10-18",
            "distance_m": 20000.0,
            "course_id": "cape-to-cabot-20000",
        },
        gun=GUN,
        frozen_at=GUN - timedelta(hours=30),
        snapshot={"file": "c2c-2026_ane-list_20261017T0800Z.html", "listing_sha256": "ab"},
        model={"name": "hierarchical", "commit": "0" * 40},
        conditions=None,
        entrants={"listed": 3, "linked": 1, "new": 1, "ambiguous": 1, "predicted": 2},
        runners=[line("Second Runner", 5400.0, 2.0), line("First Runner", 5100.123456, 1.0)],
    )
    base.update(overrides)
    return base


# --- the 24-hour rule ----------------------------------------------------------------


def test_a_day_and_a_minute_before_the_gun_is_allowed() -> None:
    pf.check_gun(GUN, GUN - timedelta(hours=24, minutes=1))


def test_twenty_three_hours_before_the_gun_is_refused() -> None:
    with pytest.raises(pf.FreezeRefused, match="would not count"):
        pf.check_gun(GUN, GUN - timedelta(hours=23))


def test_after_the_gun_is_refused() -> None:
    with pytest.raises(pf.FreezeRefused):
        pf.check_gun(GUN, GUN + timedelta(minutes=5))


def test_the_rule_is_about_instants_not_wall_clocks() -> None:
    """08:00 in St. John's is 10:30 UTC; a naive comparison is off by the time zone."""
    utc_now = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)  # 24.5 hours before the gun
    pf.check_gun(GUN, utc_now)
    with pytest.raises(pf.FreezeRefused):
        pf.check_gun(GUN, datetime(2026, 10, 17, 11, 0, tzinfo=UTC))


def test_a_time_without_a_zone_is_refused() -> None:
    with pytest.raises(pf.FreezeRefused, match="time zone"):
        pf.check_gun(GUN.replace(tzinfo=None), datetime(2026, 10, 1))


# --- bytes and hash ------------------------------------------------------------------


def test_the_same_prediction_is_the_same_bytes() -> None:
    first = pf.to_bytes(doc())
    second = pf.to_bytes(pf.document(**_arguments_in_another_order()))
    assert first == second
    assert first.endswith(b"\n") and b"\r\n" not in first


def _arguments_in_another_order() -> dict[str, Any]:
    original = doc()
    runners = [line("First Runner", 5100.123456, 1.0), line("Second Runner", 5400.0, 2.0)]
    return {
        "runners": runners,
        "entrants": dict(reversed(list(original["entrants"].items()))),
        "conditions": None,
        "model": {"commit": "0" * 40, "name": "hierarchical"},
        "snapshot": original["entrant_snapshot"],
        "frozen_at": GUN - timedelta(hours=30),
        "gun": GUN,
        "race": dict(reversed(list(original["race"].items()))),
    }


def test_runners_are_ordered_by_predicted_time_and_times_rounded() -> None:
    written = doc()["runners"]
    assert [runner["name"] for runner in written] == ["First Runner", "Second Runner"]
    assert written[0]["seconds"] == 5100.1


def test_a_written_file_verifies_and_an_edited_one_does_not(tmp_path: Path) -> None:
    path = tmp_path / "c2c-2026.json"
    digest = pf.write(path, doc())
    assert pf.verify(path, digest)
    path.write_bytes(path.read_bytes().replace(b"5100.1", b"5100.2"))
    assert not pf.verify(path, digest)


def test_a_prediction_file_is_never_replaced(tmp_path: Path) -> None:
    path = tmp_path / "c2c-2026.json"
    pf.write(path, doc())
    with pytest.raises(FileExistsError, match="never replaced"):
        pf.write(path, doc())


# --- the schema ------------------------------------------------------------------------


def test_a_good_file_has_no_problems() -> None:
    assert pf.validate(doc()) == []


def test_publishing_more_than_the_results_publish_is_refused() -> None:
    """PLAN.md 2.8: never the shirt size, never an age band, never an archive id."""
    bad = doc()
    bad["runners"][0]["shirt"] = "M"
    assert any("publishes more than the results do" in p for p in pf.validate(bad))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["runners"][0].update(interval_80=[1.0, 2.0]), "80% interval does not contain"),
        (lambda d: d["runners"][0].update(interval_90=[5000.0, 5200.0]), "90% interval does not"),
        (lambda d: d["runners"][0]["place"].update(high=9.0), "place range is not inside"),
        (lambda d: d.update(frozen_at=GUN.isoformat()), "less than 24 hours"),
        (lambda d: d.update(gun="2026-10-18T08:00:00"), "time zone"),
        (lambda d: d["entrants"].update(predicted=5), "entrants.predicted"),
        (lambda d: d.pop("conditions"), "null is allowed, absent is not"),
        (lambda d: d["model"].pop("commit"), "model.commit missing"),
    ],
)
def test_the_schema_bites(mutate: Any, message: str) -> None:
    bad = copy.deepcopy(doc())
    mutate(bad)
    problems = pf.validate(bad)
    assert any(message in problem for problem in problems), problems


def test_an_invalid_file_is_never_written(tmp_path: Path) -> None:
    bad = doc()
    bad["runners"][0]["interval_80"] = [1.0, 2.0]
    with pytest.raises(pf.SchemaError):
        pf.write(tmp_path / "bad.json", bad)
    assert not (tmp_path / "bad.json").exists()
