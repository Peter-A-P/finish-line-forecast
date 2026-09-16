"""The placing simulation: exact places, one morning per race, and agreement with the model."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models import hierarchical as hm
from finishline.placing import simulate
from finishline.schema import Race, Result


def race(race_id: str, when: date, metres: float = 10_000.0, course: str = "flat") -> Race:
    return Race(race_id, race_id, when, metres, course, f"https://example.invalid/{race_id}")


def result(race_id: str, seconds: float, band: str = "40-49") -> Result:
    return Result(race_id, 1, 1, "Perpetua Sled", None, "F", 1, band, 1, None, seconds, None)


RACES = {
    "a": race("a", date(2022, 6, 1)),
    "b": race("b", date(2023, 6, 1), metres=5_000.0, course="hilly"),
}
TARGET = race("target", date(2024, 6, 1), metres=20_000.0, course="hilly")


def fitted(draws: int, **values: float) -> hm.Posterior:
    """Three known runners and a posterior of constant draws, set by keyword."""
    people = [
        Runner(f"p{i}", f"p{i}", None, "F", (result("a", 2400.0 + 60 * i),), False)
        for i in range(3)
    ]
    data = hm.design(History.before(date(2024, 1, 1), RACES, people), min_finishes=1)
    assert data is not None
    runners, groups, courses = len(data.runner_ids), len(data.groups), len(data.courses)
    return hm.Posterior(
        design=data,
        alpha=np.tile(np.array([0.10, 0.20, 0.30], dtype=np.float32), (draws, 1)),
        beta=np.zeros((draws, runners), dtype=np.float32),
        gamma=np.full((draws, runners), values.get("gamma", 0.0), dtype=np.float32),
        mu_group=np.full((draws, groups), 0.25),
        sigma_alpha=np.full(draws, values.get("sigma_alpha", 0.0)),
        sigma_beta=np.full(draws, values.get("sigma_beta", 0.0)),
        course=np.full((draws, courses), 0.05),
        sigma_course=np.full(draws, values.get("sigma_course", 0.0)),
        sigma_edition=np.full(draws, values.get("sigma_edition", 0.0)),
        nu=np.full(draws, values.get("nu", 5.0)),
        sigma_eps=np.full(draws, values.get("sigma_eps", 0.0)),
        newcomer_share=hm.newcomer_shares(data),
        diagnostics={},
    )


def test_places_are_exact_for_fixed_times() -> None:
    assert simulate.places(np.array([[300.0, 100.0, 200.0]])).tolist() == [[3, 1, 2]]


def test_tied_runners_share_the_higher_place_and_the_next_is_skipped() -> None:
    """As a results page prints it: two in second, then fourth."""
    assert simulate.places(np.array([[100.0, 200.0, 200.0, 300.0]])).tolist() == [[1, 2, 2, 4]]


def test_a_shared_morning_moves_the_field_without_reordering_it() -> None:
    posterior = fitted(500, sigma_edition=0.05)
    entrants = [simulate.Entrant(f"p{i}", "F") for i in range(3)]
    rng = np.random.default_rng(1)

    times = simulate.field_draws(posterior, entrants, TARGET, rng)
    assert times[:, 0].std() > 0, "the morning does move finish times"
    assert (simulate.places(times) == np.array([1, 2, 3])).all()


def test_drawing_the_morning_per_runner_would_invent_place_noise() -> None:
    """The mistake the module note describes, measured: independent mornings reorder runners."""
    posterior = fitted(500, sigma_edition=0.05)
    rng = np.random.default_rng(2)
    independent = np.column_stack(
        [posterior.predict(f"p{i}", "F", TARGET, rng) for i in range(3)]
    )
    assert (simulate.places(independent) != np.array([1, 2, 3])).any()


@pytest.mark.parametrize("runner_id", ["p1", "stranger"])
def test_each_runners_draws_match_the_models_own_prediction(runner_id: str) -> None:
    """The equation is written twice; this is what stops the copies drifting apart."""
    draws = 40_000
    posterior = fitted(
        draws,
        sigma_edition=0.04,
        sigma_eps=0.03,
        nu=4.0,
        gamma=0.01,
        sigma_alpha=0.15,
        sigma_beta=0.02,
    )
    field = simulate.field_draws(
        posterior, [simulate.Entrant(runner_id, "F")], TARGET, np.random.default_rng(3)
    )[:, 0]
    alone = posterior.predict(runner_id, "F", TARGET, np.random.default_rng(4))
    for q in (0.10, 0.50, 0.90):
        assert np.quantile(field, q) == pytest.approx(np.quantile(alone, q), rel=0.01)


def test_the_summary_is_a_median_and_a_range_for_everyone() -> None:
    posterior = fitted(400, sigma_eps=0.08, nu=5.0)
    entrants = [simulate.Entrant(f"p{i}", "F") for i in range(3)]
    placed = simulate.simulate(posterior, entrants, TARGET, np.random.default_rng(5))
    assert [p.runner_id for p in placed] == ["p0", "p1", "p2"]
    assert all(p.field == 3 and 1 <= p.low <= p.median <= p.high <= 3 for p in placed)
    assert placed[0].median < placed[2].median
    assert placed[0].high > placed[0].low, "close runners have uncertain places"
