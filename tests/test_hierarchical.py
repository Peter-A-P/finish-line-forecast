"""The hierarchical model's arithmetic, checked without a sampler.

Sampling is slow and stochastic, so what these pin is everything around it: which group a
runner belongs to, what the design matrix says, and that a prediction is exactly the
equation in the module note when every source of noise is switched off. A recovery test on
synthetic runners, which does sample, is at the bottom and skips unless asked for.
"""

from __future__ import annotations

import math
import os
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models import hierarchical as hm
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
    assert data.since[first] == 0.0
    assert data.since[second] == pytest.approx((date(2022, 6, 1) - date(2020, 6, 1)).days / 365.25)
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
        gamma=np.full((draws, runners), 0.01, dtype=np.float32),
        mu_group=np.tile(np.arange(groups, dtype=float) * 0.1, (draws, 1)),
        sigma_alpha=np.zeros(draws),
        sigma_beta=np.zeros(draws),
        course=np.tile(np.linspace(0.05, -0.05, courses), (draws, 1)),
        sigma_course=np.zeros(draws),
        sigma_edition=np.zeros(draws),
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

    years = (target.date - date(2020, 6, 1)).days / 365.25
    hilly = float(fitted.course[0, data.course_index["hilly"]])
    expected = math.exp(0.10 + 0.02 * math.log(2.0) + 0.01 * years + hilly)
    assert np.allclose(seconds, expected * hm.reference_seconds(20_000.0), rtol=1e-5)


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
        gamma=np.zeros((20_000, 2), dtype=np.float32),
        mu_group=np.zeros((20_000, len(data.groups))),
        sigma_alpha=np.zeros(20_000),
        sigma_beta=np.zeros(20_000),
        course=np.zeros((20_000, len(data.courses))),
        sigma_course=np.zeros(20_000),
        sigma_edition=np.zeros(20_000),
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
    assert float(np.median(fitted.gamma)) == pytest.approx(0.01, abs=0.003)
