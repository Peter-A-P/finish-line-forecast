"""The website's numbers: named the way a runner would say them, and never naming a runner."""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from finishline.identity.link import Link, Status
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant
from finishline.publish import showcase
from finishline.schema import Result

COMMITTED = Path("data/site/results.json")


@pytest.mark.parametrize(
    ("course_id", "name"),
    [
        ("cape-to-cabot-20000", "Cape to Cabot 20 km"),
        ("turkey-tea-10000", "Turkey Tea 10 km"),
        ("run-to-remember-11000", "Run to Remember 11 km"),
        ("tely-10-16093", "Tely 10"),
        ("usr-42195", "USR marathon"),
        ("run-from-away-21097", "Run from Away half marathon"),
        ("ane-mile-1609", "ANE Open Mile"),
    ],
)
def test_a_course_is_named_the_way_a_runner_says_it(course_id: str, name: str) -> None:
    assert showcase.course_name(course_id) == name


def test_entrants_are_counted_by_history_and_never_listed() -> None:
    def runner(depth: int) -> Runner:
        results = tuple(
            Result(f"r{i}", 1, 1, "x", None, "F", 1, None, 1, None, 1000.0, None)
            for i in range(depth)
        )
        return Runner(f"id{depth}", "x", None, "F", results, False)

    links = [
        Link(Entrant("A", "F"), Status.LINKED, runner(5), ""),
        Link(Entrant("B", "F"), Status.LINKED, runner(1), ""),
        Link(Entrant("C", "F"), Status.NEW, None, ""),
        Link(Entrant("D", "F"), Status.AMBIGUOUS, None, ""),
    ]
    counted = showcase.entrants(links, "2026-09-19")
    assert counted == {
        "as_of": "2026-09-19",
        "listed": 4,
        "depth": {"0": 1, "1": 1, "2 to 3": 0, "4 or more": 1},
        "refused": 1,
    }


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def test_the_committed_numbers_name_nobody() -> None:
    if not COMMITTED.exists():
        pytest.skip("written by `finishline report`")
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert not _keys(payload) & {"runner_id", "hometown", "runner", "runners_named", "town"}
    for race in payload["races"].values():
        backtest = race["backtest"]
        if backtest is None:
            continue
        for point in backtest["points"]:
            assert all(value is None or isinstance(value, int) for value in point)


def test_the_committed_numbers_report_the_model_that_publishes() -> None:
    """The website's numbers are about the blend, and both its parents are still shown.

    A page that reports one model and publishes another is the failure this guards against.
    """
    if not COMMITTED.exists():
        pytest.skip("written by `finishline report`")
    from finishline.models import blend

    assert showcase.MODEL == blend.NAME
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    backtest = payload["backtest"]
    strata = {row["label"]: row["models"] for row in backtest["strata"]}
    for label, models in strata.items():
        assert blend.NAME in models, f"the published model is missing at depth {label}"
        assert showcase.PARENT in models and showcase.CHALLENGER in models, "both parents shown"
    paired = backtest["blend_paired"]
    assert set(paired) == {showcase.PARENT, showcase.CHALLENGER}
    for rows in paired.values():
        for row in rows:
            point, low, high = row["difference"]
            assert low <= point <= high, "a difference sits inside its own interval"


def test_a_rerun_that_changes_nothing_changes_no_bytes(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    showcase.write(path, {"b": 1, "a": [1.5, None]})
    first = path.read_bytes()
    showcase.write(path, {"a": [1.5, None], "b": 1})
    assert path.read_bytes() == first == b'{"a":[1.5,null],"b":1}\n'


def _profile(heights: list[float]) -> dict[str, Any]:
    """A profile file of the shape `data/profiles/` holds, around a given series."""
    return {
        "elevation_m": heights,
        "sample_m": 20,
        "climb_m": 1.0,
        "descent_m": 2.0,
        "high": {"m": max(heights), "at_m": 0},
        "low": {"m": min(heights), "at_m": 0},
        "steepest": {"grade": 0.01, "from_m": 0, "to_m": 500},
        "fastest": {"grade": -0.01, "from_m": 0, "to_m": 500},
        "origin": "recording",
        "segment_id": None,
        "edition": "2025-05-11",
    }


def test_a_long_profile_is_thinned_and_still_ends_at_the_finish() -> None:
    """A marathon is 2,110 heights on the 20 m grid; the card draws at most 400, and the
    last point is the finish line whatever the stride leaves over."""
    heights = [float(i % 37) for i in range(2110)]
    drawn = showcase.elevation(_profile(heights))
    points = drawn["points"]
    assert len(points) <= showcase.PROFILE_POINTS
    assert points[0] == [0, 0.0]
    assert points[-1] == [2109 * 20, heights[-1]]
    assert all(b[0] > a[0] for a, b in pairwise(points))


def test_a_short_profile_is_drawn_whole_with_the_files_own_totals() -> None:
    heights = [100.0 + i * 0.1 for i in range(251)]
    drawn = showcase.elevation(_profile(heights))
    assert len(drawn["points"]) == 251
    # Measured on the full series by the file, never recomputed from what is drawn.
    assert (drawn["climb_m"], drawn["descent_m"]) == (1.0, 2.0)


def test_what_the_card_draws_says_nothing_about_a_run() -> None:
    """The website gets heights and the facts about the road, and no field the profile file
    itself would be refused for (tests/test_grade.py)."""
    drawn = showcase.elevation(_profile([1.0, 2.0, 3.0]))
    assert set(drawn) == {
        "points", "climb_m", "descent_m", "high", "low", "steepest", "fastest",
        "origin", "segment_id", "edition",
    }  # fmt: skip
