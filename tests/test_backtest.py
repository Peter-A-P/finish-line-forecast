"""The harness, the baselines, and the one check that cannot be a comment.

If a model can see the race it is predicting, every number this project publishes is
worthless and nobody reading the README could tell. So leakage is tested from both ends:
the history refuses to carry the future, and the harness refuses to score if it does.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline.backtest import run, saved, score
from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models import baselines
from finishline.schema import HALF_MARATHON_M, Race, Result

TEN_K = 10000.0


def race(race_id: str, when: date, metres: float = TEN_K, course: str = "flat-10000") -> Race:
    return Race(race_id, race_id, when, metres, course, f"https://example.invalid/{race_id}")


def result(
    race_id: str,
    *,
    seconds: float | None = 2400.0,
    sex: str | None = "F",
    band: str | None = "30-39",
    place: int = 1,
) -> Result:
    return Result(
        race_id=race_id,
        place=place,
        bib=place,
        name="Perpetua Sled",
        club=None,
        sex=sex,
        sex_place=place,
        age_band=band,
        category_place=place,
        hometown="St. John's",
        gun_seconds=seconds,
        chip_seconds=None,
    )


def runner(runner_id: str, results: list[Result], *, sex: str | None = "F") -> Runner:
    return Runner(
        runner_id=runner_id,
        name=runner_id,
        hometown="St. John's",
        sex=sex,
        results=tuple(results),
        ambiguous=False,
    )


RACES = {
    "old": race("old", date(2023, 6, 1)),
    "mid": race("mid", date(2024, 6, 1)),
    "target": race("target", date(2025, 6, 1)),
    "same_day": race("same_day", date(2025, 6, 1), metres=5000.0, course="flat-5000"),
    "later": race("later", date(2026, 6, 1)),
}


# --- saved rows ------------------------------------------------------------------


def test_saved_rows_come_back_exactly(tmp_path: Path) -> None:
    rows = [
        score.Scored("hierarchical", "target", "a", 2410.5, 2400.0, 3, (2300.0, 2410.5, 2550.0)),
        score.Scored("hierarchical", "target", "b", None, 3000.0, 0),
    ]
    path = tmp_path / "hierarchical.jsonl"
    saved.save(path, "k1", rows)
    assert saved.load(path, "k1") == rows


def test_saved_rows_from_a_different_run_are_ignored(tmp_path: Path) -> None:
    """Last week's model must not be published under this week's name."""
    path = tmp_path / "hierarchical.jsonl"
    saved.save(path, "k1", [score.Scored("hierarchical", "target", "a", 1.0, 1.0, 0)])
    assert saved.load(path, "k2") is None
    assert saved.load(tmp_path / "absent.jsonl", "k1") is None


def test_the_key_moves_when_the_model_source_moves(tmp_path: Path) -> None:
    source = tmp_path / "model.py"
    source.write_text("a = 1\n", encoding="utf-8")
    before = saved.key({"months": 3}, [source])
    assert saved.key({"months": 3}, [source]) == before
    assert saved.key({"months": 6}, [source]) != before
    source.write_text("a = 2\n", encoding="utf-8")
    assert saved.key({"months": 3}, [source]) != before


def test_a_checkout_that_only_changes_line_endings_keeps_the_key(tmp_path: Path) -> None:
    source = tmp_path / "model.py"
    source.write_bytes(b"a = 1\nb = 2\n")
    before = saved.key({"months": 3}, [source])
    source.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert saved.key({"months": 3}, [source]) == before


def test_the_dataset_fingerprint_moves_with_one_second() -> None:
    finish = [result("target", seconds=2400.0)]
    slower = [result("target", seconds=2401.0)]
    assert saved.dataset_fingerprint(RACES, finish) != saved.dataset_fingerprint(RACES, slower)


# --- the cut ---------------------------------------------------------------------


def test_the_history_stops_the_day_before() -> None:
    person = runner("a", [result("old"), result("mid"), result("target")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert [row.race_id for row in history.results_of("a")] == ["old", "mid"]


def test_a_race_on_the_same_day_is_not_history() -> None:
    """The Trapline runs four races off one start line, and none of them knows the others."""
    person = runner("a", [result("same_day"), result("target")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert history.results_of("a") == ()
    assert "same_day" not in history.races


def test_a_later_race_is_not_history() -> None:
    person = runner("a", [result("old"), result("later")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert [row.race_id for row in history.results_of("a")] == ["old"]


def test_a_runner_with_nothing_earlier_is_absent_rather_than_empty() -> None:
    person = runner("a", [result("later")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert "a" not in history.runners
    assert history.results_of("a") == ()
    assert history.latest("a") is None


def test_a_did_not_finish_never_enters_the_history() -> None:
    person = runner("a", [result("old", seconds=None), result("mid")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert [row.race_id for row in history.results_of("a")] == ["mid"]


def test_the_harness_refuses_to_score_a_history_that_reaches_forward() -> None:
    """Belt and braces: the guard runs at every origin, not only in this test."""
    history = History.before(date(2026, 12, 31), RACES, [runner("a", [result("later")])])
    with pytest.raises(run.LeakageError, match="which is not earlier"):
        run.check_no_leakage(history, RACES["target"])


def test_the_recent_window_drops_an_old_result() -> None:
    person = runner("a", [result("old"), result("mid")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    assert len(history.results_of("a")) == 2
    assert [row.race_id for row in history.recent("a")] == ["mid"]


# --- the baselines ---------------------------------------------------------------


def test_carry_forward_scales_the_last_result_to_the_target_distance() -> None:
    person = runner("a", [result("mid", seconds=2400.0)])
    history = History.before(date(2025, 6, 1), RACES, [person])
    target = race("half", date(2025, 6, 1), metres=HALF_MARATHON_M)
    prediction = baselines.CarryForward().predict(person, target, history)
    assert prediction.answered
    assert prediction.seconds is not None
    assert 5000 < prediction.seconds < 5600  # 40 minutes for 10 km is about 88 for a half
    assert "mid" in prediction.basis


def test_carry_forward_says_nothing_for_a_runner_with_no_history() -> None:
    person = runner("a", [])
    history = History.before(date(2025, 6, 1), RACES, [person])
    prediction = baselines.CarryForward().predict(person, RACES["target"], history)
    assert not prediction.answered
    assert prediction.basis == "no prior finish"


def test_equal_vdot_takes_the_best_recent_form_not_the_last_race() -> None:
    """A good race followed by a bad one should not read as a runner who has declined."""
    person = runner("a", [result("mid", seconds=2400.0), result("target", seconds=3000.0)])
    history = History.before(date(2025, 9, 1), RACES, [person])
    target = race("t", date(2025, 9, 1))
    best = baselines.BestEqualVdot().predict(person, target, history)
    last = baselines.CarryForward().predict(person, target, history)
    assert best.seconds is not None and last.seconds is not None
    assert best.seconds < last.seconds
    assert "mid" in best.basis


def test_equal_vdot_ignores_form_older_than_the_recent_window() -> None:
    """A time from two build-ups ago is not this runner's current fitness."""
    person = runner("a", [result("old", seconds=2400.0), result("mid", seconds=3000.0)])
    history = History.before(date(2025, 9, 1), RACES, [person])
    assert [row.race_id for row in history.results_of("a")] == ["old", "mid"]
    assert [row.race_id for row in history.recent("a")] == ["mid"]
    prediction = baselines.BestEqualVdot().predict(person, RACES["later"], history)
    assert "mid" in prediction.basis, "the faster but older race is out of the window"


def test_equal_vdot_refuses_where_the_fitness_curve_is_not_fitted() -> None:
    """A ninety-minute 10 km is a real result and this model has nothing honest for it."""
    person = runner("a", [result("mid", seconds=5400.0)])
    history = History.before(date(2025, 6, 1), RACES, [person])
    prediction = baselines.BestEqualVdot().predict(person, RACES["target"], history)
    assert not prediction.answered
    assert "range" in prediction.basis


def test_the_category_median_answers_for_a_runner_with_no_history() -> None:
    """The floor, and the only baseline that says anything about a first-timer."""
    field = [
        runner(f"r{i}", [result("mid", seconds=2400.0 + 60 * i, place=i)])
        for i in range(1, 6)
    ]
    newcomer = runner("new", [])
    history = History.before(date(2025, 6, 1), RACES, [*field, newcomer])
    prediction = baselines.CategoryMedian().predict(newcomer, RACES["target"], history)
    assert prediction.seconds == pytest.approx(2580.0)  # median of 2460 .. 2700
    assert "last running" in prediction.basis


def test_a_first_timers_age_band_is_not_read_off_the_race_being_predicted() -> None:
    """The leak the tests found: a Runner carries the result that is the answer.

    A runner who has never raced has no age band anybody could know before the gun, so
    the median falls back to their sex. Reading the band off the finishing list would
    have been the results page telling the model the answer.
    """
    field = [
        runner(f"r{i}", [result("mid", seconds=2400.0 + 60 * i, band="40-49", place=i)])
        for i in range(1, 6)
    ]
    newcomer = runner("new", [result("target", band="40-49")])
    history = History.before(date(2025, 6, 1), RACES, [*field, newcomer])
    at_start = run._as_known_at_the_start(newcomer, history)
    prediction = baselines.CategoryMedian().predict(at_start, RACES["target"], history)
    assert prediction.basis == "all F finishers at the last running"


def test_the_category_median_matches_a_five_year_band_to_a_ten_year_one() -> None:
    """The Tely prints 40-44 and every other race prints 40-49. They are one runner."""
    field = [
        runner(f"r{i}", [result("mid", seconds=2400.0 + 60 * i, band="40-49", place=i)])
        for i in range(1, 6)
    ]
    person = runner("p", [result("old", band="40-44")])
    history = History.before(date(2025, 6, 1), RACES, [*field, person])
    _seconds, basis = history.category_median("flat-10000", "F", "40-44")
    assert basis == "F 40-44 at the last running"


def test_the_category_median_says_which_fallback_it_used() -> None:
    """A median over the whole field is a much weaker claim than one over a category."""
    field = [runner(f"r{i}", [result("mid", sex="M", place=i)]) for i in range(1, 6)]
    person = runner("p", [], sex="F")
    history = History.before(date(2025, 6, 1), RACES, [*field, person])
    prediction = baselines.CategoryMedian().predict(person, RACES["target"], history)
    assert prediction.basis == "the whole field at the last running"


def test_the_category_median_has_nothing_for_a_course_never_run_before() -> None:
    person = runner("p", [result("mid")])
    history = History.before(date(2025, 6, 1), RACES, [person])
    target = race("new", date(2025, 6, 1), course="a-course-nobody-has-run")
    prediction = baselines.CategoryMedian().predict(person, target, history)
    assert not prediction.answered
    assert prediction.basis == "no earlier running of this course"


# --- scoring ---------------------------------------------------------------------


def test_a_perfect_model_scores_zero_with_a_zero_interval() -> None:
    rows = [score.Scored("m", "r", f"a{i}", 2400.0, 2400.0, 2) for i in range(20)]
    summary = score.summarise(rows, "m")
    assert summary.mae_seconds == pytest.approx(0.0)
    assert summary.mae_low == pytest.approx(0.0)
    assert summary.mae_high == pytest.approx(0.0)
    assert summary.coverage == 1.0


def test_the_interval_brackets_the_point_estimate() -> None:
    rows = [
        score.Scored("m", "r", f"a{i}", 2400.0 + 10 * i, 2400.0, 2) for i in range(50)
    ]
    summary = score.summarise(rows, "m")
    assert summary.mae_low is not None and summary.mae_high is not None
    assert summary.mae_low < summary.mae_seconds < summary.mae_high  # type: ignore[operator]


def test_the_interval_is_the_same_every_time_it_is_computed() -> None:
    """A published interval a reader cannot regenerate is not evidence."""
    rows = [score.Scored("m", "r", f"a{i}", 2400.0 + 13 * i, 2400.0, 2) for i in range(40)]
    assert score.bootstrap_mae([r.error or 0.0 for r in rows]) == score.bootstrap_mae(
        [r.error or 0.0 for r in rows]
    )


def test_coverage_is_reported_separately_from_error() -> None:
    """A model that answers for the easy half must not look better than one that answers."""
    rows = [score.Scored("m", "r", "a", 2400.0, 2400.0, 2)] + [
        score.Scored("m", "r", f"b{i}", None, 3600.0, 0) for i in range(9)
    ]
    summary = score.summarise(rows, "m")
    assert summary.runners == 10
    assert summary.answered == 1
    assert summary.coverage == pytest.approx(0.1)
    assert summary.mae_seconds == pytest.approx(0.0)


def test_a_model_that_answers_for_nobody_reports_nothing_rather_than_zero() -> None:
    rows = [score.Scored("m", "r", f"a{i}", None, 2400.0, 0) for i in range(5)]
    summary = score.summarise(rows, "m")
    assert summary.answered == 0
    assert summary.mae_seconds is None
    assert summary.coverage == 0.0


def test_bias_keeps_its_sign_where_the_error_does_not() -> None:
    """Whether a model runs fast or slow is a different question from how far out it is."""
    rows = [
        score.Scored("m", "r", "a", 2500.0, 2400.0, 2),
        score.Scored("m", "r", "b", 2500.0, 2400.0, 2),
    ]
    summary = score.summarise(rows, "m")
    assert summary.bias_seconds == pytest.approx(100.0)
    assert summary.mae_seconds == pytest.approx(100.0)


@pytest.mark.parametrize(
    ("depth", "label"), [(0, "0"), (1, "1"), (2, "2 to 3"), (3, "2 to 3"), (9, "4 or more")]
)
def test_runners_land_in_the_right_history_depth_stratum(depth: int, label: str) -> None:
    assert score.stratum_of(depth) == label


def test_skill_is_relative_to_the_baseline() -> None:
    better = score.Summary("m", 10, 10, 60.0, 50.0, 70.0, 0.02, 0.0)
    baseline = score.Summary("b", 10, 10, 120.0, 110.0, 130.0, 0.04, 0.0)
    assert score.skill(better, baseline) == pytest.approx(0.5)
    assert score.skill(baseline, baseline) == pytest.approx(0.0)


def test_the_order_is_scored_as_well_as_the_time() -> None:
    """A race director cares whether the order was right, not only the clock."""
    rows = [
        score.Scored("m", "r", "a", 2400.0, 2400.0, 2),
        score.Scored("m", "r", "b", 2500.0, 2500.0, 2),
        score.Scored("m", "r", "c", 2600.0, 2600.0, 2),
    ]
    gap, correlation = score.place_error(rows, "m")
    assert gap == pytest.approx(0.0)
    assert correlation == pytest.approx(1.0)


def test_an_order_predicted_backwards_scores_as_such() -> None:
    rows = [
        score.Scored("m", "r", "a", 2600.0, 2400.0, 2),
        score.Scored("m", "r", "b", 2500.0, 2500.0, 2),
        score.Scored("m", "r", "c", 2400.0, 2600.0, 2),
    ]
    gap, correlation = score.place_error(rows, "m")
    assert gap == pytest.approx(4 / 3)
    assert correlation == pytest.approx(-1.0)


# --- end to end ------------------------------------------------------------------


def test_the_harness_scores_every_model_on_every_runner_who_finished() -> None:
    people = [
        runner("a", [result("old", place=1), result("mid", place=1), result("target", place=1)]),
        runner(
            "b",
            [
                result("mid", seconds=2700.0, place=2),
                result("target", seconds=2700.0, place=2),
            ],
        ),
        runner("c", [result("target", seconds=3000.0, place=3)]),
    ]
    races = {key: RACES[key] for key in ("old", "mid", "target")}
    scored = run.run(races, people, baselines.BASELINES, scored_from=2024)

    predicted = {(row.model, row.race_id, row.runner_id) for row in scored}
    assert ("carry-forward", "target", "a") in predicted
    assert ("category-median", "target", "c") in predicted
    assert {row.race_id for row in scored} == {"mid", "target"}

    depths = {row.runner_id: row.depth for row in scored if row.race_id == "target"}
    assert depths == {"a": 2, "b": 1, "c": 0}


def test_an_ambiguous_runner_is_never_predicted_for() -> None:
    """Not published, and not scored either: a number about them is a number about nobody."""
    unclear = Runner("x", "Chris Walsh", "St. John's", "F", (result("target"),), True, "two")
    scored = run.run(
        {key: RACES[key] for key in ("old", "target")},
        [unclear],
        baselines.BASELINES,
        scored_from=2024,
    )
    assert scored == []
