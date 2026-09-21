"""Who will run a race with no start list: the participation model and its backtest."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models import participation as pm
from finishline.schema import Race, Result


def edition(year: int, course: str = "r2r-11000", month: int = 11, day: int = 11) -> Race:
    return Race(f"{course}-{year}", course, date(year, month, day), 11_000.0, course, "")


def finish(race: Race, seconds: float = 3000.0) -> Result:
    return Result(race.race_id, 1, None, "x", None, "F", None, None, None, None, seconds, None)


YEARS = range(2016, 2026)
REMEMBER = {year: edition(year) for year in YEARS}
SUMMER = {year: edition(year, "tely-16093", 6, 28) for year in YEARS}
RACES = {race.race_id: race for race in [*REMEMBER.values(), *SUMMER.values()]}


def archive() -> list[Runner]:
    """A regular who runs both races every year, and summer-only runners who never come back."""
    regular = Runner(
        "regular",
        "Ann Regular",
        "Paradise",
        "F",
        tuple(finish(race) for year in YEARS for race in (SUMMER[year], REMEMBER[year])),
        False,
    )
    summer = [
        Runner(
            f"summer{index}",
            f"Summer {index}",
            None,
            "M",
            tuple(finish(SUMMER[year]) for year in YEARS),
            False,
        )
        for index in range(6)
    ]
    return [regular, *summer]


def test_every_candidate_row_is_built_from_results_before_the_race() -> None:
    target = edition(2026)
    history = History.before(target.date, RACES, archive())
    ids, x = pm._Archive(history).rows(target)
    assert ids == ["regular", *[f"summer{index}" for index in range(6)]]
    assert x.shape == (7, len(pm.FEATURES))
    ran_last = x[:, pm.FEATURES.index("ran_last_edition")]
    assert ran_last.tolist() == [1.0, 0, 0, 0, 0, 0, 0]


def test_a_runner_outside_the_window_is_not_a_candidate() -> None:
    lapsed = Runner("lapsed", "Old Timer", None, "M", (finish(REMEMBER[2016]),), False)
    target = edition(2026)
    history = History.before(target.date, RACES, [*archive(), lapsed])
    assert "lapsed" not in pm._Archive(history).candidates(target.date)


def test_the_regular_is_named_and_the_summer_runners_are_not() -> None:
    target = edition(2026)
    history = History.before(target.date, RACES, archive())
    model = pm.fit(history)
    assert model is not None
    field = pm.forecast(model, history, target)
    by_id = dict(zip(field.runner_ids, field.probabilities, strict=True))
    assert by_id["regular"] > 0.5 > max(by_id[f"summer{index}"] for index in range(6))
    assert [runner_id for runner_id, _ in field.named(1.0)] == ["regular"]


def test_the_number_named_is_the_expected_count_times_the_scale() -> None:
    probabilities = np.array([0.9, 0.6, 0.3, 0.2])  # 2.0 expected
    assert pm.size(probabilities, 1.0) == 2
    assert pm.size(probabilities, 1.5) == 3
    assert pm.size(probabilities, 10.0) == 4


def scored(race_id: str, year: int, p: list[float], ran: list[int], everyone: int) -> pm.Scored:
    return pm.Scored(race_id, year, np.array(p), np.array(ran, dtype=float), everyone)


def test_coverage_is_a_mean_over_races_not_a_pool_of_runners() -> None:
    small = scored("small", 2024, [0.9, 0.1], [1, 0], 1)  # names 1, it finishes: 100% / 100%
    # Names 50 of 100 candidates, 25 of them finish, of 50 visible finishers: 50% / 50%.
    big = scored("big", 2024, [0.5] * 100, [1] * 25 + [0] * 25 + [1] * 25 + [0] * 25, 100)
    measured = pm.coverage([small, big], 1.0, draws=50)
    assert measured.recall[0] == pytest.approx(0.75)
    assert measured.precision[0] == pytest.approx(0.75)
    assert measured.visible[0] == pytest.approx((1.0 + 0.5) / 2)


def test_the_scale_is_chosen_on_the_tuning_years_only() -> None:
    # In the tuning years the model is well calibrated; in 2024 it would ask for a wider net.
    tuning = [
        scored(f"t{index}", 2022, [0.8, 0.8, 0.1, 0.1, 0.1, 0.1], [1, 1, 0, 0, 0, 0], 2)
        for index in range(3)
    ]
    later = [scored("later", 2024, [0.2] * 10, [1] * 10, 10)]
    assert pm.choose_scale([*tuning, *later]) == pm.choose_scale(tuning)
    with pytest.raises(ValueError, match="tuning"):
        pm.choose_scale(later)
