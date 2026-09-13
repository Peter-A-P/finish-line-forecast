"""The conditions model, and the weighting mistake that hid it.

The first test here is the one that matters: on data built so that small editions are pure
noise and large ones carry a planted heat effect, the unweighted fit must miss it and the
weighted fit must find it. That is what happened on the real archive, and a test that only
checked the weighted path would not have caught it.
"""

from __future__ import annotations

import numpy as np
import pytest

from finishline.models import conditions


def _rows(
    *,
    slope_at_10km: float,
    slope_per_log_distance: float = 0.0,
    wind: float = 0.0,
    noise_on_small: float = 0.0,
    seed: int = 7,
) -> list[conditions.Observation]:
    """Editions with a planted effect, a mix of field sizes and a spread of weather."""
    rng = np.random.default_rng(seed)
    rows: list[conditions.Observation] = []
    for index in range(240):
        big = index % 8 == 0
        finishers = int(rng.integers(1500, 4000)) if big else int(rng.integers(25, 80))
        distance = float(rng.choice([5000.0, 10000.0, 16093.0, 42195.0]))
        temp = float(rng.uniform(-3.0, 24.0))
        breeze = float(rng.uniform(5.0, 55.0))
        planted = (
            slope_at_10km + slope_per_log_distance * np.log(distance / 10000.0)
        ) * (temp - conditions.NEUTRAL_TEMP_C) + wind * (breeze - conditions.NEUTRAL_WIND_KMH)
        # A small field's effect is mostly noise about itself; a large field's is not.
        scatter = 0.0 if big else rng.normal(0.0, noise_on_small)
        rows.append(
            conditions.Observation(
                race_id=f"r{index}",
                course_id=f"course{index % 12}",
                distance_m=distance,
                tailwind_kmh=None,
                finishers=finishers,
                effect=planted + scatter,
                temp_c=temp,
                wind_kmh=breeze,
            )
        )
    return rows


def test_unweighted_noise_from_small_fields_hides_a_real_effect() -> None:
    """Why `fit` weights, stated as a failing alternative rather than a comment.

    On the real archive the unweighted coefficient was +0.027 percent per degree with an
    interval straddling zero, which reads as "weather does not matter in Newfoundland". It
    does; the small races were shouting down the large ones.
    """
    rows = _rows(slope_at_10km=0.003, noise_on_small=0.08)
    design, y, weights = conditions._design(rows)

    unweighted = conditions._solve(design, y, np.ones_like(weights))
    weighted = conditions._solve(design, y, weights)

    truth = 0.003
    assert abs(unweighted[0] - truth) > abs(weighted[0] - truth), (
        "weighting by field size did not improve the estimate"
    )
    assert weighted[0] == pytest.approx(truth, abs=0.0006)


def test_a_planted_heat_effect_is_recovered() -> None:
    fitted = conditions.fit(_rows(slope_at_10km=0.004, noise_on_small=0.02), draws=200)
    assert fitted is not None
    assert fitted.temp_coefficient(10_000.0) == pytest.approx(0.004, abs=0.0008)
    low, high = fitted.intervals["temp_at_10km"]
    assert low < 0.004 < high


def test_the_coefficient_grows_with_distance_when_it_was_built_to() -> None:
    """A marathon field meets four hours of weather; a 5 km field meets fifteen minutes."""
    fitted = conditions.fit(
        _rows(slope_at_10km=0.003, slope_per_log_distance=0.002, noise_on_small=0.02),
        draws=200,
    )
    assert fitted is not None
    assert fitted.temp_coefficient(42_195.0) > fitted.temp_coefficient(10_000.0)
    assert fitted.temp_coefficient(10_000.0) > fitted.temp_coefficient(5_000.0)


def test_neutral_conditions_cost_nothing_and_invert_exactly() -> None:
    fitted = conditions.fit(_rows(slope_at_10km=0.004, noise_on_small=0.02), draws=100)
    assert fitted is not None
    assert fitted.adjustment(
        10_000.0, conditions.NEUTRAL_TEMP_C, conditions.NEUTRAL_WIND_KMH
    ) == pytest.approx(0.0, abs=1e-12)

    # A hot day's time, neutralised, then put back into that hot day, is where it started.
    hot = fitted.neutralise(3600.0, 16_093.0, 24.0, 30.0)
    assert hot < 3600.0, "a hot morning should make a given time better than it looks"
    back = hot * (1.0 + fitted.adjustment(16_093.0, 24.0, 30.0))
    assert back == pytest.approx(3600.0)


def test_too_little_evidence_returns_nothing_rather_than_a_number() -> None:
    assert conditions.fit(_rows(slope_at_10km=0.004)[:10]) is None


def test_a_very_large_field_counts_no_more_than_a_large_one() -> None:
    """What the weight cap is actually for.

    The Tely is 25,620 of the archive's finishes across eleven editions, and the next
    biggest course has a fifth of that. Uncapped, the conditions model would be a model of
    the Tely with the rest of the province as a rounding error. Capped, a 4,000-finisher
    edition and a 40,000-finisher edition count the same.

    ⚠️ The cap bounds weight, not leverage. An edition whose *effect* is absurd still moves
    the fit, and nothing here defends against that, because an edition effect is itself a
    fitted quantity and a wild one is a bug upstream rather than a weighting question.
    """
    rows = _rows(slope_at_10km=0.003, noise_on_small=0.02)
    _, _, weights = conditions._design(rows)
    assert weights.max() <= conditions.WEIGHT_CAP

    enormous = [
        conditions.Observation(
            race_id=r.race_id,
            course_id=r.course_id,
            distance_m=r.distance_m,
            tailwind_kmh=r.tailwind_kmh,
            finishers=r.finishers * 100,
            effect=r.effect,
            temp_c=r.temp_c,
            wind_kmh=r.wind_kmh,
        )
        for r in rows
        if r.finishers >= conditions.WEIGHT_CAP
    ]
    capped = conditions.fit([*rows, *enormous], draws=100)
    plain = conditions.fit(
        [*rows, *[r for r in rows if r.finishers >= conditions.WEIGHT_CAP]], draws=100
    )
    assert capped is not None and plain is not None
    assert capped.temp_coefficient(10_000.0) == pytest.approx(
        plain.temp_coefficient(10_000.0), abs=1e-9
    ), "multiplying a big field by a hundred changed the fit; the cap is not binding"
