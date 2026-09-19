"""The hierarchical model's arithmetic, checked without a sampler.

Sampling is slow and stochastic, so what these pin is everything around it: which group a
runner belongs to, what the design matrix says, and that a prediction is exactly the
equation in the module note when every source of noise is switched off. A recovery test on
synthetic runners, which does sample, is at the bottom and skips unless asked for.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models import hierarchical as hm
from finishline.models import weather
from finishline.schema import Race, Result


def race(race_id: str, when: date, metres: float = 10_000.0, course: str = "flat") -> Race:
    return Race(race_id, race_id, when, metres, course, f"https://example.invalid/{race_id}")


def result(race_id: str, seconds: float | None, band: str | None = "40-49") -> Result:
    return Result(
        race_id=race_id,
        place=1,
        bib=1,
        name="Perpetua Sled",
        club=None,
        sex="F",
        sex_place=1,
        age_band=band,
        category_place=1,
        hometown=None,
        gun_seconds=seconds,
        chip_seconds=None,
    )


def runner(
    runner_id: str,
    results: list[Result],
    *,
    sex: str | None = "F",
    ambiguous: bool = False,
) -> Runner:
    return Runner(runner_id, runner_id, None, sex, tuple(results), ambiguous)


RACES = {
    "a": race("a", date(2020, 6, 1)),
    "b": race("b", date(2022, 6, 1), metres=5_000.0, course="hilly"),
    "c": race("c", date(2023, 6, 1)),
    "target": race("target", date(2024, 6, 1), metres=20_000.0, course="hilly"),
}


# --- groups ------------------------------------------------------------------------


def test_bands_of_two_widths_agree_on_one_decade() -> None:
    """The Tely prints 40-44 and everyone else 40-49; both are one woman in her forties."""
    person = runner("p", [result("a", 2400.0, "40-44"), result("b", 1200.0, "40-49")])
    assert hm.age_group(person, RACES, date(2020, 6, 1)) == "F 40s"


def test_the_decade_is_the_one_at_the_first_race() -> None:
    """Fitness at t = 0 belongs to the group the runner was in at t = 0."""
    person = runner("p", [result("a", 2400.0, "35-39"), result("c", 2400.0, "40-44")])
    assert hm.age_group(person, RACES, date(2020, 6, 1)) == "F 30s"


def test_no_band_anywhere_is_its_own_group_and_not_a_guess() -> None:
    person = runner("p", [result("a", 2400.0, None)], sex="M")
    assert hm.age_group(person, RACES, date(2020, 6, 1)) == "M unknown"


def test_open_ended_bands_land_in_the_end_decades() -> None:
    young = runner("y", [result("a", 2400.0, "U19")])
    old = runner("o", [result("a", 2400.0, "70+")])
    assert hm.age_group(young, RACES, date(2020, 6, 1)) == "F 10s"
    assert hm.age_group(old, RACES, date(2020, 6, 1)) == "F 70s"


# --- the design ----------------------------------------------------------------------


def test_the_design_is_the_equation_on_the_page() -> None:
    person = runner("p", [result("a", 2400.0), result("b", 1260.0)])
    history = History.before(date(2024, 6, 1), RACES, [person])
    data = hm.design(history, min_finishes=1)
    assert data is not None

    assert data.rows == 2
    assert data.runner_ids == ("p",)
    first, second = 0, 1
    assert data.y[first] == pytest.approx(math.log(2400.0 / hm.reference_seconds(10_000.0)))
    assert data.x[second] == pytest.approx(math.log(0.5))
    assert data.season[first] != data.season[second], "two calendar years, two seasons"
    assert data.season_gap[data.season[first]] == 0.0, "a first season has no step"
    assert data.season_gap[data.season[second]] == 2.0
    assert int(data.last_year[0]) == 2022
    assert data.courses[int(data.edition_course[data.edition[second]])] == "hilly"


def test_an_ambiguous_runner_is_not_fitted() -> None:
    """Two people's history is a confident number about nobody."""
    clear = runner("clear", [result("a", 2400.0)])
    muddled = runner("muddled", [result("a", 2000.0), result("c", 3000.0)], ambiguous=True)
    data = hm.design(History.before(date(2024, 6, 1), RACES, [clear, muddled]), min_finishes=1)
    assert data is not None
    assert data.runner_ids == ("clear",)
    assert data.rows == 1


def test_a_course_under_the_floor_is_not_fitted() -> None:
    """Seven finishes on a road said nothing about it, and let one chain call them outliers."""
    busy = race("busy", date(2021, 6, 1), course="busy")
    quiet = race("quiet", date(2022, 6, 1), metres=42_195.0, course="quiet")
    races = {"busy": busy, "quiet": quiet}
    people = [
        runner("p0", [result("busy", 2400.0), result("quiet", 12000.0)]),
        runner("p1", [result("busy", 2401.0), result("quiet", 12100.0)]),
        runner("p2", [result("busy", 2402.0)]),
    ]
    data = hm.design(History.before(date(2024, 1, 1), races, people), min_finishes=3)
    assert data is not None
    assert data.courses == ("busy",)
    assert data.rows == 3


def test_the_design_never_reaches_past_the_origin() -> None:
    person = runner("p", [result("a", 2400.0), result("c", 2300.0), result("target", 5200.0)])
    data = hm.design(History.before(date(2023, 6, 1), RACES, [person]), min_finishes=1)
    assert data is not None
    assert set(data.editions) == {"a"}


def test_nothing_to_fit_is_none_rather_than_an_empty_model() -> None:
    person = runner("p", [result("a", 1.0)])
    assert hm.design(History.before(date(2019, 1, 1), RACES, [person]), min_finishes=1) is None


# --- prediction, with the noise switched off -----------------------------------------


def posterior(data: hm.Design, **overrides: object) -> hm.Posterior:
    """A posterior of identical draws, so a prediction is arithmetic rather than sampling."""
    draws = 50
    runners, groups, courses = len(data.runner_ids), len(data.groups), len(data.courses)
    base = hm.Posterior(
        design=data,
        alpha=np.full((draws, runners), 0.10, dtype=np.float32),
        beta=np.full((draws, runners), 0.02, dtype=np.float32),
        form=np.full((draws, runners), 0.03, dtype=np.float32),
        mu_group=np.tile(np.arange(groups, dtype=float) * 0.1, (draws, 1)),
        mu_trend=np.full((draws, groups), 0.01),
        sigma_alpha=np.zeros(draws),
        sigma_beta=np.zeros(draws),
        sigma_walk=np.zeros(draws),
        course=np.tile(np.linspace(0.05, -0.05, courses), (draws, 1)),
        sigma_course=np.zeros(draws),
        sigma_edition=np.zeros(draws),
        latest_year=np.zeros(draws),
        sigma_year=np.zeros(draws),
        weather=np.zeros((draws, hm.WEATHER_TERMS)),
        nu=np.full(draws, 5.0),
        sigma_eps=np.zeros(draws),
        newcomer_share=hm.newcomer_shares(data),
        diagnostics={},
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def two_runner_design() -> hm.Design:
    people = [
        runner("p", [result("a", 2400.0), result("b", 1260.0)]),
        runner("q", [result("c", 3000.0, "20-29")], sex="M"),
    ]
    data = hm.design(History.before(date(2024, 6, 1), RACES, people), min_finishes=1)
    assert data is not None
    return data


def test_a_known_runner_is_the_equation_exactly() -> None:
    data = two_runner_design()
    fitted = posterior(data)
    target = RACES["target"]
    seconds = fitted.predict("p", "F", target, np.random.default_rng(1))

    years = 2024 - 2022  # from the runner's latest season to the race's
    hilly = float(fitted.course[0, data.course_index["hilly"]])
    expected = math.exp(0.10 + 0.02 * math.log(2.0) + 0.03 + 0.01 * years + hilly)
    assert np.allclose(seconds, expected * hm.reference_seconds(20_000.0), rtol=1e-5)


def test_the_walk_widens_with_the_years_since_a_runner_was_last_seen() -> None:
    """Five years away is a wide interval centred where they were, not a confident guess."""
    data = two_runner_design()
    wide = replace(
        posterior(data),
        alpha=np.full((20_000, 2), 0.1, dtype=np.float32),
        beta=np.zeros((20_000, 2), dtype=np.float32),
        form=np.zeros((20_000, 2), dtype=np.float32),
        mu_group=np.zeros((20_000, len(data.groups))),
        mu_trend=np.zeros((20_000, len(data.groups))),
        sigma_alpha=np.zeros(20_000),
        sigma_beta=np.zeros(20_000),
        sigma_walk=np.full(20_000, 0.04),
        course=np.zeros((20_000, len(data.courses))),
        sigma_course=np.zeros(20_000),
        sigma_edition=np.zeros(20_000),
        latest_year=np.zeros(20_000),
        sigma_year=np.zeros(20_000),
        weather=np.zeros((20_000, hm.WEATHER_TERMS)),
        nu=np.full(20_000, 5.0),
        sigma_eps=np.zeros(20_000),
    )
    same_year = race("soon", date(2022, 9, 1), course="flat")
    later = race("later", date(2027, 9, 1), course="flat")
    near = np.log(wide.predict("p", "F", same_year, np.random.default_rng(5)))
    far = np.log(wide.predict("p", "F", later, np.random.default_rng(6)))
    assert near.std() == pytest.approx(0.0, abs=1e-9), "the same season carries its form"
    assert far.std() == pytest.approx(0.04 * math.sqrt(5), rel=0.05)
    assert np.median(far) == pytest.approx(np.median(near), abs=0.005)


def test_observed_weather_moves_the_morning_by_its_coefficients() -> None:
    data = two_runner_design()
    # heat, heat x log distance, wind, tailwind, and a full sun worth 6 degrees
    coefficients = np.tile(np.array([0.003, 0.001, 0.0005, -0.0002, 6.0]), (50, 1))
    fitted = posterior(data, weather=coefficients)
    target = RACES["target"]
    log_distance = math.log(2.0)
    # 18 C in half a clear noon's sun: felt 21, nine degrees of heat over the 12 C knee.
    hot = np.array([1.0, 18.0, 0.5, log_distance, 5.0, -20.0])
    calm = fitted.predict("p", "F", target, np.random.default_rng(7))
    warm = fitted.predict("p", "F", target, np.random.default_rng(7), hot)
    shift = float(np.log(warm / calm)[0])
    expected = 9.0 * (0.003 + 0.001 * log_distance) + 0.0005 * 5.0 - 0.0002 * -20.0
    assert shift == pytest.approx(expected)


def test_the_parameters_the_model_stores_are_the_ones_the_prediction_reads() -> None:
    """`build` stores the weather parameters in one order and `weather.effect` reads them in
    one order; a swap would put the sun boost where a heat cost goes, silently."""
    pytensor = pytest.importorskip("pytensor")

    person = runner("p", [result("a", 2400.0), result("b", 1260.0)])
    history = History.before(date(2024, 6, 1), RACES, [person])
    rows = {"a": (1.0, 21.0, 0.8, 0.5, 3.0, -4.0), "b": (1.0, 9.0, 1.0, 0.0, -2.0, 0.0)}
    data = hm.design(history, min_finishes=1, weather=rows)
    assert data is not None
    model = hm.build(data)
    # The values replace the random variables, as they do when sampling; the positive
    # parameters are sampled on the log scale.
    values = [model.rvs_to_values[model[name]] for name in ("heat", "air", "sun_boost")]
    (output,) = model.replace_rvs_by_values([model["weather"]])
    compute = pytensor.function(values, output)
    stored = np.asarray(
        compute(np.log([0.004, 0.002]), np.array([0.001, -0.0005]), np.log(7.0))
    )
    assert stored.tolist() == pytest.approx([0.004, 0.002, 0.001, -0.0005, 7.0])
    for race_id, conditions in rows.items():
        read = float(weather.effect(np.array([conditions]), np.array([stored]))[0])
        _, temp, sun, log_distance, wind, tail = conditions
        heat = max(0.0, temp + 7.0 * sun - weather.HEAT_THRESHOLD_C)
        by_hand = heat * (0.004 + 0.002 * log_distance) + 0.001 * wind - 0.0005 * tail
        assert read == pytest.approx(by_hand), race_id


def test_editions_carry_their_covariates_and_the_rest_are_neutral() -> None:
    person = runner("p", [result("a", 2400.0), result("b", 1260.0)])
    history = History.before(date(2024, 6, 1), RACES, [person])
    conditions = (1.0, 18.0, 0.5, 1.2, 3.0, 4.0)
    data = hm.design(history, min_finishes=1, weather={"a": conditions})
    assert data is not None and data.uses_weather
    assert data.weather[data.editions.index("a")].tolist() == list(conditions)
    assert data.weather[data.editions.index("b")].tolist() == [0.0] * hm.CONDITION_TERMS
    plain = hm.design(history, min_finishes=1)
    assert plain is not None and not plain.uses_weather


def test_a_course_the_fit_never_saw_is_drawn_from_the_course_prior() -> None:
    data = two_runner_design()
    fitted = posterior(data, sigma_course=np.full(50, 0.04))
    new_road = race("new", date(2024, 6, 1), metres=10_000.0, course="never-raced")
    seconds = fitted.predict("p", "F", new_road, np.random.default_rng(2))
    assert seconds.std() > 0, "an unseen course is uncertain, not exactly average"


def test_a_first_timer_is_drawn_only_from_their_own_sex() -> None:
    """The entrant list gives sex and no age, so the mixture is over that sex's groups."""
    data = two_runner_design()
    fitted = posterior(data)
    target = race("flat-day", date(2024, 6, 1), metres=10_000.0, course="flat")
    seconds = fitted.predict("stranger", "M", target, np.random.default_rng(3))

    men = [i for i, label in enumerate(data.groups) if label.startswith("M ")]
    flat = float(fitted.course[0, data.course_index["flat"]])
    allowed = {
        round(math.exp(i * 0.1 + flat) * hm.reference_seconds(10_000.0), 3) for i in men
    }
    assert {round(float(value), 3) for value in seconds} <= allowed


def test_newcomers_weight_the_groups_of_recent_first_timers() -> None:
    old_hand = runner("old", [result("a", 2400.0, "60-69")])
    newcomer = runner("new", [result("c", 3000.0, "20-29")])
    data = hm.design(History.before(date(2024, 6, 1), RACES, [old_hand, newcomer]), min_finishes=1)
    assert data is not None
    shares = hm.newcomer_shares(data)["F"]
    assert shares[data.groups.index("F 20s")] == 1.0
    assert shares[data.groups.index("F 60s")] == 0.0


def test_the_noise_is_heavy_tailed() -> None:
    """With nu = 3 the draws should put far more past three scale units than a normal would."""
    data = two_runner_design()
    fitted = posterior(
        data,
        sigma_eps=np.full(20_000, 0.05),
        nu=np.full(20_000, 3.0),
        alpha=np.full((20_000, 2), 0.1, dtype=np.float32),
        beta=np.zeros((20_000, 2), dtype=np.float32),
        form=np.zeros((20_000, 2), dtype=np.float32),
        mu_group=np.zeros((20_000, len(data.groups))),
        mu_trend=np.zeros((20_000, len(data.groups))),
        sigma_alpha=np.zeros(20_000),
        sigma_beta=np.zeros(20_000),
        sigma_walk=np.zeros(20_000),
        course=np.zeros((20_000, len(data.courses))),
        sigma_course=np.zeros(20_000),
        sigma_edition=np.zeros(20_000),
        latest_year=np.zeros(20_000),
        sigma_year=np.zeros(20_000),
        weather=np.zeros((20_000, hm.WEATHER_TERMS)),
    )
    target = race("flat-day", date(2020, 6, 1), metres=10_000.0, course="flat")
    seconds = fitted.predict("p", "F", target, np.random.default_rng(4))
    logs = np.log(seconds / hm.reference_seconds(10_000.0))
    beyond = float(np.mean(np.abs(logs - 0.1) > 3 * 0.05))
    assert beyond > 0.03, f"a normal puts 0.27% past three sigma; got {beyond:.2%}"


# --- blocks of origins ---------------------------------------------------------------


def test_a_block_is_a_calendar_slice_aligned_to_january() -> None:
    assert hm.block_start(date(2025, 8, 17), 3) == date(2025, 7, 1)
    assert hm.block_start(date(2025, 1, 1), 3) == date(2025, 1, 1)
    assert hm.block_start(date(2025, 12, 31), 6) == date(2025, 7, 1)
    assert hm.block_start(date(2025, 8, 17), 1) == date(2025, 8, 1)
    with pytest.raises(ValueError, match="divide the year"):
        hm.block_start(date(2025, 8, 17), 5)


class RecordingFitter:
    """Stands in for the sampler and remembers what it was shown."""

    def __init__(self) -> None:
        self.seen: list[History] = []

    def __call__(self, history: History) -> hm.Posterior | None:
        self.seen.append(history)
        data = hm.design(history, min_finishes=1)
        return None if data is None else posterior(data)


def test_a_block_fit_never_sees_the_block_it_predicts() -> None:
    """The leak this class could make: a race earlier in the quarter informing a later one.

    That would not be a result from after the target, so `check_no_leakage` would not
    catch it, and it would still be information the model claims not to have.
    """
    races = {
        "spring": race("spring", date(2024, 5, 1)),
        "july": race("july", date(2024, 7, 6)),
        "august": race("august", date(2024, 8, 20)),
    }
    person = runner("p", [result("spring", 2400.0), result("july", 2350.0)])
    fitter = RecordingFitter()
    model = hm.Hierarchical(months=3, fitter=fitter)

    history = History.before(races["august"].date, races, [person])
    assert "july" in history.races, "the race's own history does hold July"
    model.predict(person, races["august"], history)

    (shown,) = fitter.seen
    assert set(shown.races) == {"spring"}
    assert all(r.date < date(2024, 7, 1) for r in shown.races.values())


def test_one_fit_per_block_however_many_runners() -> None:
    races = {
        "spring": race("spring", date(2024, 5, 1)),
        "july": race("july", date(2024, 7, 6)),
        "august": race("august", date(2024, 8, 20)),
        "october": race("october", date(2024, 10, 5)),
    }
    people = [runner(f"p{i}", [result("spring", 2400.0 + i)]) for i in range(5)]
    fitter = RecordingFitter()
    model = hm.Hierarchical(months=3, fitter=fitter)
    for target in ("july", "august", "october"):
        history = History.before(races[target].date, races, people)
        for person in people:
            prediction = model.predict(person, races[target], history)
            assert prediction.seconds is not None
            assert len(prediction.quantiles) == len(hm.QUANTILES)
    assert [h.origin for h in fitter.seen] == [date(2024, 7, 1), date(2024, 10, 1)]


def test_a_prediction_is_the_same_whatever_order_runners_arrive_in() -> None:
    races = {"spring": race("spring", date(2024, 5, 1)), "july": race("july", date(2024, 7, 6))}
    people = [runner(f"p{i}", [result("spring", 2400.0 + 60 * i)]) for i in range(3)]
    history = History.before(races["july"].date, races, people)

    def noisy(h: History) -> hm.Posterior | None:
        data = hm.design(h, min_finishes=1)
        return None if data is None else posterior(data, sigma_edition=np.full(50, 0.03))

    forward = hm.Hierarchical(fitter=noisy)
    backward = hm.Hierarchical(fitter=noisy)
    ahead = {p.runner_id: forward.predict(p, races["july"], history).quantiles for p in people}
    behind = {
        p.runner_id: backward.predict(p, races["july"], history).quantiles
        for p in reversed(people)
    }
    assert ahead == behind


def test_nothing_before_the_block_is_no_answer_rather_than_a_guess() -> None:
    races = {"july": race("july", date(2024, 7, 6)), "august": race("august", date(2024, 8, 20))}
    person = runner("p", [result("july", 2400.0)])
    model = hm.Hierarchical(fitter=RecordingFitter())
    history = History.before(races["august"].date, races, [person])
    assert model.predict(person, races["august"], history).seconds is None


# --- recovery, with the sampler ------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("FINISHLINE_SLOW"),
    reason="samples a model; set FINISHLINE_SLOW=1 to run",
)
def test_the_sampler_recovers_what_synthetic_runners_were_given() -> None:
    """Runners who age one percent a year on a course five percent hard; get both back."""
    rng = np.random.default_rng(20261018)
    races = {
        f"r{year}{course}": race(
            f"r{year}{course}", date(year, 6, 1), metres=10_000.0, course=course
        )
        for year in range(2010, 2024)
        for course in ("flat", "hilly")
    }
    people = []
    for index in range(300):
        fitness = rng.normal(0.3, 0.1)
        entries = []
        for year in range(2010, 2024):
            for course in ("flat", "hilly"):
                if rng.random() < 0.3:
                    log_ratio = (
                        fitness
                        + 0.01 * (year - 2010)
                        + (0.05 if course == "hilly" else 0.0)
                        + rng.normal(0, 0.02)
                    )
                    seconds = math.exp(log_ratio) * hm.reference_seconds(10_000.0)
                    entries.append(result(f"r{year}{course}", seconds))
        if entries:
            people.append(runner(f"p{index}", entries))

    fitted = hm.fit(
        History.before(date(2025, 1, 1), races, people), draws=300, tune=300, chains=2
    )
    assert fitted is not None
    design = fitted.design
    hilly, flat = design.course_index["hilly"], design.course_index["flat"]
    hard = fitted.course[:, hilly] - fitted.course[:, flat]
    assert float(np.median(hard)) == pytest.approx(0.05, abs=0.01)
    assert float(np.median(fitted.mu_trend)) == pytest.approx(0.01, abs=0.003)


def test_a_race_after_the_last_fitted_year_walks_the_year_effect_forward() -> None:
    """The latest year's level, carried to the race's year with the spread that implies."""
    data = two_runner_design()
    assert data.last_year_fitted == 2023
    n = 20_000
    fitted = replace(
        posterior(data),
        alpha=np.zeros((n, 2), dtype=np.float32),
        beta=np.zeros((n, 2), dtype=np.float32),
        form=np.zeros((n, 2), dtype=np.float32),
        mu_group=np.zeros((n, len(data.groups))),
        mu_trend=np.zeros((n, len(data.groups))),
        sigma_alpha=np.zeros(n),
        sigma_beta=np.zeros(n),
        sigma_walk=np.zeros(n),
        course=np.zeros((n, len(data.courses))),
        sigma_course=np.zeros(n),
        sigma_edition=np.zeros(n),
        latest_year=np.full(n, 0.06),
        sigma_year=np.full(n, 0.02),
        weather=np.zeros((n, hm.WEATHER_TERMS)),
        nu=np.full(n, 5.0),
        sigma_eps=np.zeros(n),
    )
    ten = hm.reference_seconds(10_000.0)
    rng = np.random.default_rng(8)
    same = np.log(fitted.predict("p", "F", race("s", date(2023, 9, 1)), rng) / ten)
    later = np.log(fitted.predict("p", "F", race("l", date(2027, 9, 1)), rng) / ten)
    assert np.allclose(same, 0.06), "a race in the last fitted year gets that year's level"
    assert np.median(later) == pytest.approx(0.06, abs=0.002)
    assert later.std() == pytest.approx(0.02 * 2.0, rel=0.05)


Block = tuple[dict[str, float], dict[tuple[str, str], tuple[float, ...]]]


class MemoryStore:
    """A checkpoint that keeps blocks in a dict, as `saved.BlockStore` keeps them on disk."""

    def __init__(self) -> None:
        self.blocks: dict[date, Block] = {}

    def load(self, start: date) -> Block | None:
        return self.blocks.get(start)

    def save(
        self,
        start: date,
        diagnostics: Mapping[str, float],
        predictions: Mapping[tuple[str, str], tuple[float, ...]],
    ) -> None:
        self.blocks[start] = (dict(diagnostics), dict(predictions))


def test_a_finished_block_is_kept_and_a_rerun_does_not_sample_it_again() -> None:
    """Seven hours of blocks lost to one out-of-memory error is why this exists."""
    races = {
        "spring": race("spring", date(2024, 5, 1)),
        "july": race("july", date(2024, 7, 6)),
        "october": race("october", date(2024, 10, 5)),
    }
    people = [runner(f"p{i}", [result("spring", 2400.0 + 60 * i)]) for i in range(3)]
    store = MemoryStore()

    def predictions(model: hm.Hierarchical) -> list[tuple[float, ...]]:
        out = []
        for target in ("july", "october"):
            history = History.before(races[target].date, races, people)
            out += [model.predict(p, races[target], history).quantiles for p in people]
        model.finish()
        return out

    first_fitter = RecordingFitter()
    first = predictions(hm.Hierarchical(fitter=first_fitter, checkpoint=store))
    assert set(store.blocks) == {date(2024, 7, 1), date(2024, 10, 1)}

    second_fitter = RecordingFitter()
    second = predictions(hm.Hierarchical(fitter=second_fitter, checkpoint=store))
    assert second_fitter.seen == [], "nothing is sampled twice"
    assert second == first
