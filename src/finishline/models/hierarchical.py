"""The hierarchical model: every runner's own parameters, shrunk toward their group.

On the log of a finish time over the time a reference runner would take at that distance:

    y = alpha_i + beta_i * log(d / 10 km) + walk_i[year] + delta_r + eps

    alpha_i       ~ Normal(mu_group[g_i], sigma_alpha)    fitness in the first year raced
    beta_i        ~ Normal(0, sigma_beta)                 fade over distance, beyond Daniels
    walk_i[year]  = walk_i[previous year raced]           form, which carries from year to
                    + Normal(mu_trend[g_i] * gap,         year and drifts with age
                             sigma_walk * sqrt(gap))
    delta_r       = course[c_r] + year[t_r]              what this road, this year and this
                    + heat_r (h0 + h1 log(d / 5 km))      morning cost; heat_r is felt heat
                    + wind terms                          above 12 C, the sun's share of it
                    + Normal(0, sigma_edition)            estimated (`models.weather`)
    year[t]       = year[t - 1] + Normal(0, sigma_year)  what every race that year shared
    eps           ~ StudentT(nu, 0, sigma_eps)            a bad day is not Gaussian

PLAN.md 5.3 is the design; what differs from it is here and in section 13.

WHY THE RESPONSE IS A RATIO TO A DANIELS TIME
---------------------------------------------
Dividing by what a VDOT-50 runner would run at that distance puts a 5 km and a marathon on
one scale before anything is fitted, which is the same move `models.courses` makes. The
population's fade over distance is then Daniels' curve, and `beta_i` is only how far this
runner's fade departs from it. A runner who has raced one distance says nothing about their
own `beta`, and it shrinks to zero.

⚠️ **There is no `mu_beta`, and the plan had one.** Every course here is run at one distance
(the distance is part of `course_id`), so a population-wide departure from Daniels'
curve, `mu_beta * log(d)`, is indistinguishable from a set of course effects that happen to
line up with distance. Fitted with both, `mu_beta` came back with R-hat 1.76 (PLAN.md 13
item 23).

WHY FORM IS A RANDOM WALK AND NOT A STRAIGHT LINE
-------------------------------------------------
⚠️ **The first version gave each runner a linear trend, and the backtest refuted it** (PLAN.md
13 items 28 and 29). Runners get faster through their first years, so a line fitted to a
career and carried to race day predicted years of improvement nobody has: 8.3 percent too
fast across 49 races, and behind carry-forward at every history depth. The residuals said
what the line was missing: a runner's miss at one race predicts their miss at the next, by
about 0.3 to 0.4 within a season and still clearly a year on. Fitness is a state that
persists and drifts, not a slope.

So each runner has a level per calendar year they raced, tied to the previous one by a step
whose spread grows with the years between them. Races in one year share the year's level,
which is what lets a result in May inform a prediction in October. A prediction starts from
the runner's latest year and walks forward to the race's, adding the group's ageing drift
and the walk's spread for each year skipped, so a runner last seen five years ago gets a
wide interval centred where they were, not a confident one centred where a line would put
them. The drift has a mean per age-sex group (`mu_trend`), because without one the edition
effects absorb population ageing: section 13 item 14.

WHY EVERY YEAR HAS ITS OWN EFFECT
---------------------------------
⚠️ **Races have been getting slower, all of them together, and a course average cannot see
it** (PLAN.md 13 item 29). Fitted with only a course effect and editions summing to zero
within their course, the 2023 and 2024 editions came out six to eight percent slower than
their courses' long-run averages, against two to three percent fast in 2011 to 2015. A race
predicted at its course's average was therefore predicted as if it were run in 2016, and the
random walk above, with nothing else changed, was still five percent fast on every 2025
race. So a shared year effect walks from calendar year to calendar year, and a race is
predicted from the latest year the fit has seen, walked forward to the race's year with the
spread that implies. What makes recent fields slower (who runs now, or how) is not
something this model claims to know; it only stops pretending it is not there.

⚠️ **The group is fixed at a runner's first race.** `alpha_i` is fitness in the first year,
so the group that prior belongs to is the one they were in then. The group comes from the
birth years their printed age bands allow (`identity.resolve.birth_window`), not from any
single band, and a runner whose pages printed no band gets an `unknown` group for their sex.

WHAT A PREDICTION IS
--------------------
Draws, not a number. Each posterior draw is a complete, mutually consistent version of the
runner, the course and the noise; pushing each through the equation above with a fresh
edition effect and a fresh bad-day term gives a distribution of finish times, and the
median of that is the point prediction the backtest scores. `Posterior.own` is the runner's
part and `Posterior.morning` the race's, so the placing simulation can share one morning
across a field without writing the equation twice.

⚠️ **A runner the fit has never seen takes their alpha from newcomers, not from everyone.**
The entrant list gives a sex and no age, so a first-timer's fitness is drawn from a mixture
over that sex's groups, weighted by the groups of runners whose first result falls in the
two years before the origin.
"""

from __future__ import annotations

import gc
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from finishline.history import History
from finishline.identity.resolve import Runner, birth_window
from finishline.metrics import daniels
from finishline.models import weather as weather_model
from finishline.models.baselines import Prediction
from finishline.models.courses import MIN_FINISHES, REFERENCE_VDOT
from finishline.schema import Race, Result

if TYPE_CHECKING:
    import pymc as pm

# The distance `beta` is measured from. Any value works; 10 km is the middle of the archive,
# so `alpha` reads as fitness at the distance most people race.
REFERENCE_DISTANCE_M = 10_000.0

# Decades are coarse enough that every group has hundreds of runners in it and fine enough
# that masters and open runners are not averaged together. The ends are open.
YOUNGEST_DECADE, OLDEST_DECADE = 1, 7

# How far back "newcomers" reach when a first-timer's group has to be guessed.
NEWCOMER_WINDOW = timedelta(days=730)

# Draws kept per fit. Enough for a 5th percentile to be stable to about a percent of a
# finish time, and small enough that twenty thousand runners' draws fit in memory.
KEPT_DRAWS = 400

# The quantiles every prediction carries, for the conformal layer to calibrate.
QUANTILES: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)

# The weather parameters, in `models.weather.PARAMETERS` order (the heat pair, the wind pair
# and the sun boost), and one edition's raw conditions, in `models.weather.CONDITIONS` order.
WEATHER_TERMS = len(weather_model.PARAMETERS)
CONDITION_TERMS = len(weather_model.CONDITIONS)
Covariates = tuple[float, ...]

YEAR_DAYS = 365.25


@cache
def reference_seconds(distance_m: float) -> float:
    """What a VDOT-50 runner would run at this distance, the scale every time is put on."""
    seconds = daniels.race_time(REFERENCE_VDOT, distance_m)
    if seconds is None:
        raise ValueError(f"no reference time at {distance_m} m")
    return seconds


def age_group(runner: Runner, races: dict[str, Race], first: date) -> str:
    """The runner's sex and age decade at their first race, from every band they printed."""
    sex = runner.sex or "U"
    windows = [
        window
        for result in runner.results
        if (window := birth_window(result.age_band, races[result.race_id].date)) is not None
    ]
    if not windows:
        return f"{sex} unknown"
    low = max(window[0] for window in windows)
    high = min(window[1] for window in windows)
    if low > high:
        # The resolver only merges results whose windows intersect, so this is a runner
        # printed under bands that disagree on one page. The latest band wins.
        low, high = windows[-1]
    age = first.year - (low + high) / 2.0
    decade = int(min(max(age // 10, YOUNGEST_DECADE), OLDEST_DECADE))
    return f"{sex} {decade * 10}s"


@dataclass(frozen=True, slots=True)
class Design:
    """One row per finish in the history, as integer indexes into the things fitted.

    A season is one runner's one calendar year with a finish in it. Seasons are ordered by
    runner and then year, so each runner's are contiguous and the walk is a cumulative sum.
    """

    origin: date
    runner_ids: tuple[str, ...]
    first_seen: tuple[date, ...]
    groups: tuple[str, ...]
    courses: tuple[str, ...]
    editions: tuple[str, ...]
    runner_group: np.ndarray
    edition_course: np.ndarray
    runner: np.ndarray
    edition: np.ndarray
    season: np.ndarray  # row -> season
    y: np.ndarray
    x: np.ndarray
    runner_index: dict[str, int]
    course_index: dict[str, int]
    # Each runner's own mean `x`, where their level is sampled; see `build`.
    x_centre: np.ndarray
    season_runner: np.ndarray  # season -> runner
    season_gap: np.ndarray  # years since the runner's previous season; 0 for their first
    season_first: np.ndarray  # season -> the runner's first season
    last_season: np.ndarray  # runner -> their latest season
    last_year: np.ndarray  # runner -> the calendar year of it
    # Per edition, the raw conditions (`models.weather.CONDITIONS`); zeros where unobserved.
    weather: np.ndarray
    uses_weather: bool
    edition_year: np.ndarray  # edition -> calendar year
    first_year: int
    last_year_fitted: int

    @property
    def rows(self) -> int:
        return int(self.y.size)


def design(
    history: History,
    *,
    min_finishes: int = MIN_FINISHES,
    weather: Mapping[str, Covariates] | None = None,
) -> Design | None:
    """The history as arrays, or None when there is nothing to fit.

    Ambiguous runners are left out: their history is two people's, and a fitness estimate
    from it would be a confident number about nobody.

    ⚠️ **So are courses with fewer than `courses.MIN_FINISHES` finishes**, the same floor the
    course layer publishes at. On the 2025-01-01 origin one chain in four put a seven-finisher
    marathon at -1.50, seventy-eight percent faster than an ordinary road, where the other
    three had it at +0.04 (PLAN.md 13 item 25). A race on such a course is predicted with a
    course effect drawn from the course prior, which is what a road with no history gets.

    `weather` maps an edition to its observed covariates (`models.weather.edition_covariates`).
    An edition missing from it enters at neutral, and its weather stays in its edition effect.
    """
    runner_ids: list[str] = []
    first_seen: list[date] = []
    group_of: list[int] = []
    groups: dict[str, int] = {}
    courses: dict[str, int] = {}
    editions: dict[str, int] = {}
    runner_ix: list[int] = []
    edition_ix: list[int] = []
    year_of_row: list[int] = []
    y: list[float] = []
    x: list[float] = []

    def usable(result: Result) -> bool:
        return result.seconds is not None and result.seconds > 0

    size: dict[str, int] = {}
    for runner in history.runners.values():
        if runner.ambiguous:
            continue
        for result in runner.results:
            if usable(result):
                course_id = history.races[result.race_id].course_id
                size[course_id] = size.get(course_id, 0) + 1

    for runner_id in sorted(history.runners):
        runner = history.runners[runner_id]
        finishes = [
            result
            for result in runner.results
            if usable(result)
            and size[history.races[result.race_id].course_id] >= min_finishes
        ]
        if runner.ambiguous or not finishes:
            continue
        first = min(history.races[result.race_id].date for result in finishes)
        index = len(runner_ids)
        runner_ids.append(runner_id)
        first_seen.append(first)
        label = age_group(runner, history.races, first)
        group_of.append(groups.setdefault(label, len(groups)))

        for result in finishes:
            race = history.races[result.race_id]
            assert result.seconds is not None
            runner_ix.append(index)
            courses.setdefault(race.course_id, len(courses))
            edition_ix.append(editions.setdefault(race.race_id, len(editions)))
            year_of_row.append(race.date.year)
            y.append(float(np.log(result.seconds / reference_seconds(race.distance_m))))
            x.append(float(np.log(race.distance_m / REFERENCE_DISTANCE_M)))

    if not y:
        return None

    # Seasons, ordered by runner then year: `runner_ids` is already sorted into index order.
    keys = sorted(set(zip(runner_ix, year_of_row, strict=True)))
    season_of = {key: position for position, key in enumerate(keys)}
    season_runner = np.array([key[0] for key in keys], dtype=np.int64)
    season_gap = np.zeros(len(keys))
    season_first = np.zeros(len(keys), dtype=np.int64)
    last_season = np.zeros(len(runner_ids), dtype=np.int64)
    for position, (runner_index, year) in enumerate(keys):
        previous = keys[position - 1] if position else None
        if previous is not None and previous[0] == runner_index:
            season_gap[position] = year - previous[1]
            season_first[position] = season_first[position - 1]
        else:
            season_first[position] = position
        last_season[runner_index] = position
    last_year = np.array([keys[int(s)][1] for s in last_season], dtype=np.int64)

    covariates = np.zeros((len(editions), CONDITION_TERMS))
    if weather:
        for race_id, position in editions.items():
            if race_id in weather:
                covariates[position] = weather[race_id]

    edition_course = np.array(
        [courses[history.races[race_id].course_id] for race_id in editions], dtype=np.int64
    )
    edition_year = np.array(
        [history.races[race_id].date.year for race_id in editions], dtype=np.int64
    )
    rows = np.array(runner_ix, dtype=np.int64)
    counts = np.bincount(rows, minlength=len(runner_ids)).astype(float)
    return Design(
        origin=history.origin,
        runner_ids=tuple(runner_ids),
        first_seen=tuple(first_seen),
        groups=tuple(groups),
        courses=tuple(courses),
        editions=tuple(editions),
        runner_group=np.array(group_of, dtype=np.int64),
        edition_course=edition_course,
        runner=rows,
        edition=np.array(edition_ix, dtype=np.int64),
        season=np.array(
            [season_of[key] for key in zip(runner_ix, year_of_row, strict=True)], dtype=np.int64
        ),
        y=np.array(y),
        x=np.array(x),
        runner_index={runner_id: position for position, runner_id in enumerate(runner_ids)},
        course_index=dict(courses),
        x_centre=np.bincount(rows, weights=np.array(x), minlength=len(runner_ids)) / counts,
        season_runner=season_runner,
        season_gap=season_gap,
        season_first=season_first,
        last_season=last_season,
        last_year=last_year,
        weather=covariates,
        uses_weather=weather is not None,
        edition_year=edition_year,
        first_year=int(edition_year.min()),
        last_year_fitted=int(edition_year.max()),
    )


def build(data: Design) -> pm.Model:
    """The PyMC model. Non-centred throughout, because most runners have one or two rows.

    A centred `alpha_i ~ Normal(mu, sigma)` with one observation per runner is the funnel
    NUTS cannot sample. Written as `mu + sigma * z` with `z ~ Normal(0, 1)` the geometry is
    flat, and the walk's steps are written the same way.

    Priors are on the log-ratio scale, where 0.1 is ten percent of a finish time. They are
    weak on purpose.

    ⚠️ **The level is sampled at each runner's mean distance**, and `alpha` at 10 km is
    recovered afterwards: for anyone who has raced more than one distance, the level and the
    distance fade otherwise trade off along a ridge (PLAN.md 13 item 22).
    """
    import pymc as pm
    import pytensor.tensor as pt

    runners = len(data.runner_ids)
    group = data.runner_group
    with pm.Model() as model:
        # No population mean for the fade: see the note on `mu_beta` in the module docstring.
        sigma_beta = pm.HalfNormal("sigma_beta", 0.05)
        beta = sigma_beta * pm.Normal("z_beta", 0.0, 1.0, shape=runners)

        # Fitness at 10 km in the first year. 0.3 is a typical recreational runner, VDOT 38.
        mu_group = pm.Normal("mu_group", 0.3, 0.5, shape=len(data.groups))
        sigma_alpha = pm.HalfNormal("sigma_alpha", 0.3)
        level = mu_group[group] + sigma_alpha * pm.Normal("z_alpha", 0.0, 1.0, shape=runners)

        # Form from season to season. A runner's first season is their level, so its step is
        # zero; every later step drifts by the group's ageing and spreads with the years.
        mu_trend = pm.Normal("mu_trend", 0.0, 0.02, shape=len(data.groups))
        sigma_walk = pm.HalfNormal("sigma_walk", 0.05)
        z_walk = pm.Normal("z_walk", 0.0, 1.0, shape=len(data.season_gap))
        later = (data.season_gap > 0).astype(float)
        step = later * (
            mu_trend[group[data.season_runner]] * data.season_gap
            + sigma_walk * np.sqrt(data.season_gap) * z_walk
        )
        total = pt.cumsum(step)  # type: ignore[no-untyped-call]
        walk = total - total[data.season_first]

        # Zero-sum, because a constant can move from every course to every runner and the
        # likelihood cannot tell (PLAN.md 13 item 24 for the editions).
        sigma_course = pm.HalfNormal("sigma_course", 0.1)
        course = pm.ZeroSumNormal("course", sigma=sigma_course, shape=len(data.courses))
        sigma_edition = pm.HalfNormal("sigma_edition", 0.05)
        z_edition = pm.Normal("z_edition", 0.0, 1.0, shape=len(data.editions))
        per_course = np.bincount(data.edition_course, minlength=len(data.courses))
        course_sum = pt.zeros(len(data.courses))[data.edition_course].inc(z_edition)
        z_within = z_edition - (course_sum / per_course)[data.edition_course]
        delta = course[data.edition_course] + sigma_edition * z_within

        # The shared year effect, a walk anchored at zero in the first year: the level of
        # every race that year relative to the first, with `mu_group` carrying the rest.
        sigma_year = pm.HalfNormal("sigma_year", 0.05)
        z_year = pm.Normal("z_year", 0.0, 1.0, shape=data.last_year_fitted - data.first_year + 1)
        steps = pt.set_subtensor((sigma_year * z_year)[0], 0.0)  # type: ignore[no-untyped-call]
        year = pt.cumsum(steps)  # type: ignore[no-untyped-call]
        delta = delta + year[data.edition_year - data.first_year]
        pm.Deterministic("latest_year", year[-1])
        if data.uses_weather:
            # Per degree of felt heat, per km/h: a percent a degree would be an extreme cost,
            # so the prior is wide at that scale and the archive does the rest.
            #
            # ⚠️ **The two heat coefficients are positive by construction, and that is a claim
            # about the world, not a convenience.** Heat can slow a race and cannot speed one,
            # and its cost cannot fall as the race gets longer. Fitted free, the same editions
            # will buy a better fit to a hot marathon by asserting that a hot 5 km is quick,
            # because summer short races are also fast for reasons that have nothing to do with
            # the weather. The scaling column is zero at 5 km (`weather.HEAT_PIVOT_M`), so a
            # positive pair means non-negative and non-decreasing in distance, everywhere.
            heat = pm.HalfNormal("heat", 0.01, shape=2)
            air = pm.Normal("air", 0.0, 0.01, shape=2)
            # What a full sun adds to the felt temperature, in degrees, estimated rather than
            # set: a grid over 227 editions and 121 same-runner pairs could not pin it on a
            # reanalysis sky (PLAN.md 13 item 30), and the whole field of every race can.
            # HalfNormal on the scale of the NWS figure, so nothing and twice that are both in
            # reach and the posterior is the data's answer.
            boost = pm.HalfNormal("sun_boost", weather_model.SUN_PRIOR_SCALE_C)
            pm.Deterministic(
                "weather",
                pt.concatenate([heat, air, pt.stack([boost])]),  # type: ignore[no-untyped-call]
            )
            observed, temp, sun, log_distance, wind, tailwind = (
                data.weather[:, k] for k in range(CONDITION_TERMS)
            )
            hot = observed * pt.maximum(temp + boost * sun - weather_model.HEAT_THRESHOLD_C, 0.0)
            delta = delta + (
                hot * (heat[0] + heat[1] * log_distance) + air[0] * wind + air[1] * tailwind
            )

        row = data.runner
        mean = (
            level[row]
            + beta[row] * (data.x - data.x_centre[row])
            + walk[data.season]
            + delta[data.edition]
        )
        nu = pm.Gamma("nu", 2.0, 0.1)
        sigma_eps = pm.HalfNormal("sigma_eps", 0.1)
        pm.StudentT("y", nu=nu, mu=mean, sigma=sigma_eps, observed=data.y)

        pm.Deterministic("alpha", level - beta * data.x_centre)
        pm.Deterministic("beta", beta)
        pm.Deterministic("form", walk[data.last_season])
    return model


@dataclass(frozen=True, slots=True)
class Posterior:
    """A fit reduced to the draws a prediction needs, as plain arrays.

    Runner-level draws are float32 and thinned to `KEPT_DRAWS`, which is what keeps twenty
    thousand runners in a few hundred megabytes rather than a few gigabytes.
    """

    design: Design
    alpha: np.ndarray  # (draws, runners)
    beta: np.ndarray
    form: np.ndarray  # (draws, runners): the walk at each runner's latest season
    mu_group: np.ndarray  # (draws, groups)
    mu_trend: np.ndarray  # (draws, groups)
    sigma_alpha: np.ndarray  # (draws,)
    sigma_beta: np.ndarray
    sigma_walk: np.ndarray
    course: np.ndarray  # (draws, courses)
    sigma_course: np.ndarray
    sigma_edition: np.ndarray
    latest_year: np.ndarray  # (draws,): the year effect of the last calendar year fitted
    sigma_year: np.ndarray
    weather: np.ndarray  # (draws, WEATHER_TERMS), `models.weather.PARAMETERS`; zeros without
    nu: np.ndarray
    sigma_eps: np.ndarray
    newcomer_share: dict[str, np.ndarray]  # sex -> weights over groups
    diagnostics: dict[str, float]

    @property
    def draws(self) -> int:
        return int(self.sigma_alpha.size)

    def own(
        self, runner_id: str, sex: str | None, target: Race, rng: np.random.Generator
    ) -> np.ndarray:
        """The runner's part of the log ratio at this race: fitness, fade and form."""
        data = self.design
        n = self.draws
        x = float(np.log(target.distance_m / REFERENCE_DISTANCE_M))
        index = data.runner_index.get(runner_id)
        if index is None:
            weights = self.newcomer_share.get(sex or "U")
            if weights is None:
                weights = np.ones(len(data.groups)) / len(data.groups)
            chosen = rng.choice(len(data.groups), size=n, p=weights)
            return np.asarray(
                self.mu_group[np.arange(n), chosen]
                + self.sigma_alpha * rng.standard_normal(n)
                + self.sigma_beta * rng.standard_normal(n) * x
            )
        years = max(target.date.year - int(data.last_year[index]), 0)
        group = int(data.runner_group[index])
        return np.asarray(
            self.alpha[:, index].astype(float)
            + self.beta[:, index].astype(float) * x
            + self.form[:, index].astype(float)
            + self.mu_trend[:, group] * years
            + self.sigma_walk * np.sqrt(years) * rng.standard_normal(n)
        )

    def morning(
        self, target: Race, rng: np.random.Generator, conditions: np.ndarray | None = None
    ) -> np.ndarray:
        """The race's part: its course, its weather and the rest of its morning.

        `conditions` is the target's raw conditions (`models.weather.CONDITIONS`), either one
        row for an observed morning or one row per draw for a forecast. None is a neutral one.
        """
        data = self.design
        n = self.draws
        course_index = data.course_index.get(target.course_id)
        if course_index is not None:
            course = self.course[:, course_index]
        else:
            course = self.sigma_course * rng.standard_normal(n)
        years = max(target.date.year - data.last_year_fitted, 0)
        year = self.latest_year + self.sigma_year * np.sqrt(years) * rng.standard_normal(n)
        effect = course + year + self.sigma_edition * rng.standard_normal(n)
        if conditions is not None:
            rows = np.broadcast_to(np.asarray(conditions, dtype=float), (n, CONDITION_TERMS))
            effect = effect + weather_model.effect(rows, self.weather)
        return np.asarray(effect)

    def noise(self, rng: np.random.Generator) -> np.ndarray:
        """A bad-day draw per posterior draw: a normal over the root of a scaled chi-squared."""
        n = self.draws
        return np.asarray(
            self.sigma_eps * rng.standard_normal(n) / np.sqrt(rng.chisquare(self.nu) / self.nu)
        )

    def predict(
        self,
        runner_id: str,
        sex: str | None,
        target: Race,
        rng: np.random.Generator,
        conditions: np.ndarray | None = None,
    ) -> np.ndarray:
        """Finish-time draws in seconds for this runner at this race."""
        log_ratio = (
            self.own(runner_id, sex, target, rng)
            + self.morning(target, rng, conditions)
            + self.noise(rng)
        )
        return np.asarray(np.exp(log_ratio) * reference_seconds(target.distance_m))


def newcomer_shares(data: Design) -> dict[str, np.ndarray]:
    """For each sex, the share of recent first-timers in each group."""
    cutoff = data.origin - NEWCOMER_WINDOW
    shares: dict[str, np.ndarray] = {}
    for sex in {label.split(" ")[0] for label in data.groups}:
        counts = np.zeros(len(data.groups))
        fallback = np.zeros(len(data.groups))
        for position, first in enumerate(data.first_seen):
            label = data.groups[int(data.runner_group[position])]
            if label.split(" ")[0] != sex:
                continue
            fallback[data.runner_group[position]] += 1
            if first >= cutoff:
                counts[data.runner_group[position]] += 1
        chosen = counts if counts.sum() > 0 else fallback
        shares[sex] = chosen / chosen.sum()
    return shares


def fit(
    history: History,
    *,
    draws: int = 300,
    tune: int = 400,
    chains: int = 4,
    seed: int = 20261018,
    weather: Mapping[str, Covariates] | None = None,
) -> Posterior | None:
    """Sample the model on everything in this history, or None with nothing to fit.

    ⚠️ **nutpie, not PyMC's own NUTS, and the difference is not a tuning detail.** On the
    2025-01-01 origin PyMC's sampler ran every chain to its maximum tree depth, diverged 314
    times and finished with R-hat above 2 on the noise and fitness scales; nutpie, on the same
    model, sampled cleanly (PLAN.md 13 item 21).
    """
    data = design(history, weather=weather)
    if data is None:
        return None
    import pymc as pm

    model = build(data)
    names = [
        "alpha", "beta", "form", "mu_group", "mu_trend", "sigma_alpha", "sigma_beta",
        "sigma_walk", "course", "sigma_course", "sigma_edition", "latest_year", "sigma_year",
        "nu", "sigma_eps",
    ]
    if data.uses_weather:
        names.append("weather")
    with model:
        trace: Any = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            progressbar=False,
            compute_convergence_checks=False,
            nuts_sampler="nutpie",
            var_names=names,
        )
    reduced = _reduce(data, trace, seed)
    # The full trace is several gigabytes at this size; let it go before the next fit asks.
    del trace, model
    gc.collect()
    return reduced


# The parameters whose convergence is checked and logged for every fit. Runner-level
# parameters number in the tens of thousands and are not individually diagnosed; these are
# the ones that set every runner's shrinkage.
HYPERPARAMETERS: tuple[str, ...] = (
    "sigma_alpha", "sigma_beta", "sigma_walk", "sigma_course", "sigma_edition", "sigma_year",
    "nu", "sigma_eps", "mu_group", "mu_trend", "weather",
)


def _reduce(data: Design, trace: Any, seed: int) -> Posterior:
    """Flatten chains, thin to `KEPT_DRAWS`, and keep only what prediction reads."""
    posterior = trace.posterior

    def flat(name: str) -> np.ndarray:
        values = np.asarray(posterior[name].values)
        return values.reshape(values.shape[0] * values.shape[1], *values.shape[2:])

    total = flat("sigma_alpha").shape[0]
    rng = np.random.default_rng(seed)
    keep = np.sort(rng.choice(total, size=min(KEPT_DRAWS, total), replace=False))

    def kept(name: str, dtype: type = np.float64) -> np.ndarray:
        return np.ascontiguousarray(flat(name)[keep], dtype=dtype)

    weather = (
        kept("weather") if "weather" in posterior else np.zeros((keep.size, WEATHER_TERMS))
    )
    return Posterior(
        design=data,
        alpha=kept("alpha", np.float32),
        beta=kept("beta", np.float32),
        form=kept("form", np.float32),
        mu_group=kept("mu_group"),
        mu_trend=kept("mu_trend"),
        sigma_alpha=kept("sigma_alpha"),
        sigma_beta=kept("sigma_beta"),
        sigma_walk=kept("sigma_walk"),
        course=kept("course"),
        sigma_course=kept("sigma_course"),
        sigma_edition=kept("sigma_edition"),
        latest_year=kept("latest_year"),
        sigma_year=kept("sigma_year"),
        weather=weather,
        nu=kept("nu"),
        sigma_eps=kept("sigma_eps"),
        newcomer_share=newcomer_shares(data),
        diagnostics=_diagnostics(trace, total),
    )


def _diagnostics(trace: Any, total: int) -> dict[str, float]:
    """Divergences, and the worst R-hat and bulk ESS over the hyperparameters."""
    import arviz as az

    names = [name for name in HYPERPARAMETERS if name in trace.posterior]
    summary = az.summary(trace, var_names=names, kind="diagnostics")
    return {
        "draws": float(total),
        "divergences": float(np.asarray(trace.sample_stats["diverging"].values).sum()),
        "max_rhat": float(summary["r_hat"].max()),
        "min_ess_bulk": float(summary["ess_bulk"].min()),
    }


def summarise(samples: np.ndarray, quantiles: Sequence[float] = QUANTILES) -> tuple[float, ...]:
    """The quantiles of a set of finish-time draws, in seconds."""
    return tuple(float(value) for value in np.quantile(samples, quantiles))


def block_start(when: date, months: int) -> date:
    """The first day of the block of `months` calendar months that holds this date.

    Blocks are aligned to January, so a three-month block is a calendar quarter and every
    race in one quarter is predicted from the same fit.
    """
    if not 1 <= months <= 12 or 12 % months:
        raise ValueError(f"a block must divide the year; got {months} months")
    month = (when.month - 1) // months * months + 1
    return date(when.year, month, 1)


Fitter = Callable[[History], Posterior | None]
Quantiles = tuple[float, ...]


class Checkpoint(Protocol):
    """Where finished blocks are kept (`backtest.saved.BlockStore`)."""

    def load(
        self, start: date
    ) -> tuple[dict[str, float], dict[tuple[str, str], Quantiles]] | None: ...

    def save(
        self,
        start: date,
        diagnostics: Mapping[str, float],
        predictions: Mapping[tuple[str, str], Quantiles],
    ) -> None: ...


class Hierarchical:
    """The model as the backtest sees it: one fit per block of origins, many predictions.

    ⚠️ **A block fit knows less than the race it predicts, never more.** Sampling the model
    at every one of seventy-odd origins is days of compute, so races are grouped into
    blocks and each block is predicted from one fit on the history strictly before the
    block's first day. A race late in a quarter is therefore predicted without the results
    from earlier in that quarter, which the baselines beside it do see. The comparison is
    tilted against this model, on purpose: the other direction would be a leak.

    ⚠️ **With `weather`, a target race is predicted with the weather observed that morning.**
    That is a perfect forecast, which a live prediction never has; the live prediction
    carries the measured day-ahead forecast error instead (`models.weather.draws`), and the
    README says the backtest is the kinder of the two.
    """

    def __init__(
        self,
        *,
        months: int = 3,
        fitter: Fitter | None = None,
        seed: int = 20261018,
        weather: Mapping[str, Covariates] | None = None,
        checkpoint: Checkpoint | None = None,
    ) -> None:
        self._months = months
        self._fitter: Fitter = fitter if fitter is not None else fit
        self._seed = seed
        self._weather = weather
        self._checkpoint = checkpoint
        self._block: date | None = None
        self._posterior: Posterior | None = None
        self._restored: dict[tuple[str, str], Quantiles] | None = None
        self._pending: dict[tuple[str, str], Quantiles] = {}
        self.fits: list[tuple[date, dict[str, float]]] = []

    def finish(self) -> None:
        """Write the block in progress, if it was sampled here. Call after the last origin."""
        if self._checkpoint is None or self._block is None or self._restored is not None:
            return
        diagnostics = self.fits[-1][1] if self.fits else {}
        self._checkpoint.save(self._block, diagnostics, self._pending)
        self._pending = {}

    @property
    def name(self) -> str:
        return "hierarchical"

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        start = block_start(target.date, self._months)
        if start != self._block:
            # Origins arrive in date order, so a block is never revisited and only the
            # current fit is kept; twenty thousand runners' draws are not free.
            self.finish()
            self._block = start
            self._posterior = None
            self._restored = None
            restored = self._checkpoint.load(start) if self._checkpoint else None
            if restored is not None:
                diagnostics, self._restored = restored
                self.fits.append((start, {**diagnostics, "restored": 1.0}))
            else:
                # The last block's posterior is let go before the next fit allocates its own.
                gc.collect()
                cut = History.before(start, history.races, list(history.runners.values()))
                self._posterior = self._fitter(cut)
                diagnostics = self._posterior.diagnostics if self._posterior else {}
                self.fits.append((start, diagnostics))

        key = (runner.runner_id, target.race_id)
        if self._restored is not None:
            if key not in self._restored:
                raise RuntimeError(
                    f"the saved block {start} has no prediction for {key}; delete it and rerun"
                )
            saved = self._restored[key]
            if not saved:
                return Prediction(runner.runner_id, None, "nothing before this block to fit")
            return Prediction(
                runner.runner_id,
                saved[QUANTILES.index(0.50)],
                f"saved block {start.isoformat()}",
                quantiles=saved,
            )
        if self._posterior is None:
            self._pending[key] = ()
            return Prediction(runner.runner_id, None, "nothing before this block to fit")

        conditions = None
        if self._weather is not None and target.race_id in self._weather:
            conditions = np.asarray(self._weather[target.race_id], dtype=float)
        # Seeded by runner and race, so a rerun draws the same numbers in any order.
        seed = zlib.crc32(f"{runner.runner_id}|{target.race_id}".encode())
        rng = np.random.default_rng([self._seed, seed])
        draws = self._posterior.predict(runner.runner_id, runner.sex, target, rng, conditions)
        quantiles = summarise(draws)
        self._pending[key] = quantiles
        seen = runner.runner_id in self._posterior.design.runner_index
        basis = (
            f"fitted on history before {start.isoformat()}"
            if seen
            else f"group prior, history before {start.isoformat()}"
        )
        return Prediction(
            runner.runner_id, quantiles[QUANTILES.index(0.50)], basis, quantiles=quantiles
        )
