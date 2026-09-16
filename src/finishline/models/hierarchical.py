"""The hierarchical model: every runner's own parameters, shrunk toward their group.

On the log of a finish time over the time a reference runner would take at that distance:

    y = alpha_i + beta_i * log(d / 10 km) + gamma_i * (years since first race) + delta_r + eps

    alpha_i  ~ Normal(mu_group[g_i], sigma_alpha)          fitness when first seen
    beta_i   ~ Normal(0, sigma_beta)                       fade over distance, beyond Daniels
    gamma_i  ~ Normal(mu_gamma[g_i], sigma_gamma)          career trend, per year
    delta_r  = course[c_r] + Normal(0, sigma_edition)      what this morning on this road cost
    eps      ~ StudentT(nu, 0, sigma_eps)                  a bad day is not Gaussian

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
line up with distance. Fitted with both, `mu_beta` came back from the 2025-01-01 origin with
R-hat 1.76, which is what a parameter the data cannot see looks like. Without it, whatever
the population's fade is relative to Daniels lives in the course effects, which is where a
course at a distance the archive already races picks it up. A course at a distance the
archive has never seen would not, and none is on the calendar.

That fit also had `sigma_course` and `sigma_edition` unconverged, and removing `mu_beta` was
expected to fix them too. It did not (R-hat 1.56 and 2.11 without it), which is how the
real cause, in the note in `build` on edition effects, was found.

⚠️ **The trend has a group mean, which the plan did not give it.** PLAN.md 5.3 wrote
`gamma_i ~ Normal(0, sigma_gamma)`. With a zero mean, a runner with two results has their
trend shrunk almost to nothing, and the ageing their results do show has nowhere to go but
the edition effects: section 13 item 14 all over again, arriving through the prior instead of
through a missing term. So `mu_gamma` is estimated per age-sex group, because a runner in
their sixties and a runner in their twenties do not age at the same rate.

⚠️ **The group is fixed at a runner's first race.** `alpha_i` is fitness at `t = 0`, their
first result, so the group that prior belongs to is the one they were in then. The group
comes from the birth years their printed age bands allow (`identity.resolve.birth_window`),
not from any single band, so a runner printed as `40-44` at the Tely and `40-49` elsewhere
lands in one decade. A runner whose pages printed no band at all gets an `unknown` group
for their sex, estimated from data like any other.

WHAT A PREDICTION IS
--------------------
Draws, not a number. Each posterior draw is a complete, mutually consistent version of the
runner, the course and the noise; pushing each through the equation above with a fresh
edition effect and a fresh bad-day term gives a distribution of finish times, and the
median of that is the point prediction the backtest scores. The same draws taken together
across a field are the placing simulation (PLAN.md 2.7).

⚠️ **A runner the fit has never seen takes their alpha from newcomers, not from everyone.**
The entrant list gives a sex and no age, so a first-timer's group is unknown and their
fitness is drawn from a mixture over that sex's groups. The mixture weights are the groups
of runners whose first result falls in the two years before the origin, because the
people entering their first race are younger and newer to running than the archive as a
whole, and weighting by the whole archive would predict them as the average veteran.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from typing import TYPE_CHECKING, Any

import numpy as np

from finishline.history import History
from finishline.identity.resolve import Runner, birth_window
from finishline.metrics import daniels
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
    """One row per finish in the history, as integer indexes into the things fitted."""

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
    y: np.ndarray
    x: np.ndarray
    since: np.ndarray
    runner_index: dict[str, int]
    course_index: dict[str, int]
    # Each runner's own mean of `x` and `since`, where their level is sampled; see `build`.
    x_centre: np.ndarray
    since_centre: np.ndarray

    @property
    def rows(self) -> int:
        return int(self.y.size)


def design(history: History, *, min_finishes: int = MIN_FINISHES) -> Design | None:
    """The history as arrays, or None when there is nothing to fit.

    Ambiguous runners are left out: their history is two people's, and a fitness estimate
    from it would be a confident number about nobody.

    ⚠️ **So are courses with fewer than `courses.MIN_FINISHES` finishes**, the same floor the
    course layer publishes at. On the 2025-01-01 origin one chain in four put a seven-finisher
    marathon (`eastern-42195`) at -1.50, seventy-eight percent faster than an ordinary road,
    where the other three had it at +0.04. With tails as heavy as this archive's (nu near
    2), calling seven finishes seven outliers is a local mode the sampler can fall into and
    not climb out of, and because courses sum to zero it moved every other course by 0.035
    and left `sigma_course` at R-hat 1.57. A course that small says nothing reliable about
    its road, so its results are left out of the fit, and a race on it is predicted with a
    course effect drawn from the course prior, which is what a road with no history gets.
    """
    runner_ids: list[str] = []
    first_seen: list[date] = []
    group_of: list[int] = []
    groups: dict[str, int] = {}
    courses: dict[str, int] = {}
    editions: dict[str, int] = {}
    runner_ix: list[int] = []
    edition_ix: list[int] = []
    y: list[float] = []
    x: list[float] = []
    since: list[float] = []

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
            y.append(float(np.log(result.seconds / reference_seconds(race.distance_m))))
            x.append(float(np.log(race.distance_m / REFERENCE_DISTANCE_M)))
            since.append((race.date - first).days / YEAR_DAYS)

    if not y:
        return None
    edition_course = np.array(
        [courses[history.races[race_id].course_id] for race_id in editions], dtype=np.int64
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
        y=np.array(y),
        x=np.array(x),
        since=np.array(since),
        runner_index={runner_id: position for position, runner_id in enumerate(runner_ids)},
        course_index=dict(courses),
        x_centre=np.bincount(rows, weights=np.array(x), minlength=len(runner_ids)) / counts,
        since_centre=np.bincount(rows, weights=np.array(since), minlength=len(runner_ids))
        / counts,
    )


def build(data: Design) -> pm.Model:
    """The PyMC model. Non-centred throughout, because most runners have one or two rows.

    A centred `alpha_i ~ Normal(mu, sigma)` with one observation per runner is the funnel
    NUTS cannot sample: as `sigma_alpha` shrinks, twenty thousand `alpha`s have to squeeze
    with it. Written as `mu + sigma * z` with `z ~ Normal(0, 1)` the geometry is flat.

    Priors are on the log-ratio scale, where 0.1 is ten percent of a finish time. They are
    weak on purpose and every one is narrower than nothing only where physiology already
    says so: nobody's trend is fifty percent a year.

    ⚠️ **Each runner's level is sampled at the middle of their own history, not at t = 0.**
    A runner with results from 2012 to 2024 pins their fitness in 2018 far better than in
    2012, and sampled at 2012 the level and the trend trade off against each other along a
    long thin ridge, twenty thousand times over: exactly the geometry that sends NUTS to its
    maximum tree depth. The same holds between the level and the distance fade for anyone
    who has raced more than one distance. So the level is sampled at each runner's mean
    `since` and mean `x`, its prior mean moved there by the group's own trend, and
    `alpha` at t = 0 and 10 km is recovered afterwards. Predictions read `alpha`, so nothing
    downstream changes. The prior's width now applies at mid-career rather than at the first
    race, which for the half of the archive with one result is the same place.
    """
    import pymc as pm
    import pytensor.tensor as pt

    runners = len(data.runner_ids)
    group = data.runner_group
    with pm.Model() as model:
        # No population mean for the fade: see the note on `mu_beta` in the module docstring.
        sigma_beta = pm.HalfNormal("sigma_beta", 0.05)
        z_beta = pm.Normal("z_beta", 0.0, 1.0, shape=runners)
        beta = sigma_beta * z_beta

        mu_gamma = pm.Normal("mu_gamma", 0.0, 0.02, shape=len(data.groups))
        sigma_gamma = pm.HalfNormal("sigma_gamma", 0.02)
        z_gamma = pm.Normal("z_gamma", 0.0, 1.0, shape=runners)
        gamma = mu_gamma[group] + sigma_gamma * z_gamma

        # Fitness at 10 km when first seen. 0.3 is a typical recreational runner, VDOT 38.
        mu_group = pm.Normal("mu_group", 0.3, 0.5, shape=len(data.groups))
        sigma_alpha = pm.HalfNormal("sigma_alpha", 0.3)
        z_alpha = pm.Normal("z_alpha", 0.0, 1.0, shape=runners)
        level = mu_group[group] + mu_gamma[group] * data.since_centre + sigma_alpha * z_alpha
        alpha = level - beta * data.x_centre - gamma * data.since_centre

        # Zero-sum, because a constant can move from every course to every runner and the
        # likelihood cannot tell; pinning the courses' sum takes that direction away from
        # the sampler rather than leaving it to a prior to discourage.
        sigma_course = pm.HalfNormal("sigma_course", 0.1)
        course = pm.ZeroSumNormal("course", sigma=sigma_course, shape=len(data.courses))
        # ⚠️ Edition effects sum to zero within their course, for the same reason. Left free,
        # every edition of a course can move up together while the course moves down, and
        # the likelihood cannot tell; the cost of that move is the edition prior, which is
        # nearly nothing once `sigma_edition` is large. So a chain that drifted to a large
        # `sigma_edition` could wander the course levels freely, and on the 2025-01-01
        # origin `sigma_course` and `sigma_edition` came back with R-hat 1.56 and 2.11 while
        # every other scale had converged. Projecting out each course's mean edition takes
        # that direction away: the course effect is the course's average morning and an
        # edition is only how this morning differed. The projected-out mean is left to its
        # N(0, 1) prior, which the likelihood never touches, so it samples as a free normal.
        sigma_edition = pm.HalfNormal("sigma_edition", 0.05)
        z_edition = pm.Normal("z_edition", 0.0, 1.0, shape=len(data.editions))
        per_course = np.bincount(data.edition_course, minlength=len(data.courses))
        course_sum = pt.zeros(len(data.courses))[data.edition_course].inc(z_edition)
        z_within = z_edition - (course_sum / per_course)[data.edition_course]
        delta = course[data.edition_course] + sigma_edition * z_within

        row = data.runner
        mean = (
            level[row]
            + beta[row] * (data.x - data.x_centre[row])
            + gamma[row] * (data.since - data.since_centre[row])
            + delta[data.edition]
        )
        nu = pm.Gamma("nu", 2.0, 0.1)
        sigma_eps = pm.HalfNormal("sigma_eps", 0.1)
        pm.StudentT("y", nu=nu, mu=mean, sigma=sigma_eps, observed=data.y)

        pm.Deterministic("alpha", alpha)
        pm.Deterministic("beta", beta)
        pm.Deterministic("gamma", gamma)
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
    gamma: np.ndarray
    mu_group: np.ndarray  # (draws, groups)
    sigma_alpha: np.ndarray  # (draws,)
    sigma_beta: np.ndarray
    course: np.ndarray  # (draws, courses)
    sigma_course: np.ndarray
    sigma_edition: np.ndarray
    nu: np.ndarray
    sigma_eps: np.ndarray
    newcomer_share: dict[str, np.ndarray]  # sex -> weights over groups
    diagnostics: dict[str, float]

    @property
    def draws(self) -> int:
        return int(self.sigma_alpha.size)

    def predict(
        self, runner_id: str, sex: str | None, target: Race, rng: np.random.Generator
    ) -> np.ndarray:
        """Finish-time draws in seconds for this runner at this race."""
        data = self.design
        n = self.draws
        index = data.runner_index.get(runner_id)
        if index is not None:
            alpha = self.alpha[:, index].astype(float)
            beta = self.beta[:, index].astype(float)
            years = (target.date - data.first_seen[index]).days / YEAR_DAYS
            trend = self.gamma[:, index].astype(float) * years
        else:
            weights = self.newcomer_share.get(sex or "U")
            if weights is None:
                weights = np.ones(len(data.groups)) / len(data.groups)
            chosen = rng.choice(len(data.groups), size=n, p=weights)
            alpha = self.mu_group[np.arange(n), chosen] + self.sigma_alpha * rng.standard_normal(n)
            beta = self.sigma_beta * rng.standard_normal(n)
            trend = np.zeros(n)

        course_index = data.course_index.get(target.course_id)
        if course_index is not None:
            course = self.course[:, course_index]
        else:
            course = self.sigma_course * rng.standard_normal(n)
        edition = self.sigma_edition * rng.standard_normal(n)
        # A Student-t draw: a normal over the root of a scaled chi-squared.
        noise = self.sigma_eps * rng.standard_normal(n) / np.sqrt(rng.chisquare(self.nu) / self.nu)

        x = float(np.log(target.distance_m / REFERENCE_DISTANCE_M))
        log_ratio = alpha + beta * x + trend + course + edition + noise
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
) -> Posterior | None:
    """Sample the model on everything in this history, or None with nothing to fit.

    ⚠️ **nutpie, not PyMC's own NUTS, and the difference is not a tuning detail.** On the
    2025-01-01 origin (60,386 finishes, 19,488 runners) PyMC's sampler ran every chain to its
    maximum tree depth, took 1,117 seconds for 100 tuning steps and 100 draws, diverged 314
    times and finished with R-hat above 2 on the noise and fitness scales: four chains that
    had not agreed on how much of a finish time is the runner and how much is the day.
    nutpie, on the same model, took 463 seconds for 300 and 300 at tree depth 6 with no
    divergences, because its mass-matrix adaptation learns forty thousand scales quickly
    where PyMC's windowed adaptation had not started to.
    """
    data = design(history)
    if data is None:
        return None
    import pymc as pm

    model = build(data)
    with model:
        trace: Any = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            progressbar=False,
            compute_convergence_checks=False,
            nuts_sampler="nutpie",
            var_names=[
                "alpha", "beta", "gamma", "mu_group", "sigma_alpha", "sigma_beta",
                "mu_gamma", "sigma_gamma", "course", "sigma_course", "sigma_edition",
                "nu", "sigma_eps",
            ],
        )
    return _reduce(data, trace, seed)


# The parameters whose convergence is checked and logged for every fit. Runner-level
# parameters number in the tens of thousands and are not individually diagnosed; these are
# the ones that set every runner's shrinkage.
HYPERPARAMETERS: tuple[str, ...] = (
    "sigma_alpha", "sigma_beta", "sigma_gamma", "sigma_course", "sigma_edition", "nu",
    "sigma_eps", "mu_group", "mu_gamma",
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

    return Posterior(
        design=data,
        alpha=kept("alpha", np.float32),
        beta=kept("beta", np.float32),
        gamma=kept("gamma", np.float32),
        mu_group=kept("mu_group"),
        sigma_alpha=kept("sigma_alpha"),
        sigma_beta=kept("sigma_beta"),
        course=kept("course"),
        sigma_course=kept("sigma_course"),
        sigma_edition=kept("sigma_edition"),
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


class Hierarchical:
    """The model as the backtest sees it: one fit per block of origins, many predictions.

    ⚠️ **A block fit knows less than the race it predicts, never more.** Sampling the model
    at every one of seventy-odd origins is days of compute, so races are grouped into
    blocks and each block is predicted from one fit on the history strictly before the
    block's first day. A race late in a quarter is therefore predicted without the results
    from earlier in that quarter, which the baselines beside it do see. The comparison is
    tilted against this model, on purpose: the other direction would be a leak.

    The history-depth stratum a row is scored under still comes from the race's own
    history, so a runner whose first result was earlier in the same block is scored as
    depth one while this model predicts them as a newcomer. That is the price of the tilt,
    and it lands on exactly the runners the model is meant to help.
    """

    def __init__(
        self, *, months: int = 3, fitter: Fitter | None = None, seed: int = 20261018
    ) -> None:
        self._months = months
        self._fitter: Fitter = fitter if fitter is not None else fit
        self._seed = seed
        self._block: date | None = None
        self._posterior: Posterior | None = None
        self.fits: list[tuple[date, dict[str, float]]] = []

    @property
    def name(self) -> str:
        return "hierarchical"

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        start = block_start(target.date, self._months)
        if start != self._block:
            # Origins arrive in date order, so a block is never revisited and only the
            # current fit is kept; twenty thousand runners' draws are not free.
            cut = History.before(start, history.races, list(history.runners.values()))
            self._posterior = self._fitter(cut)
            self._block = start
            diagnostics = self._posterior.diagnostics if self._posterior else {}
            self.fits.append((start, diagnostics))
        if self._posterior is None:
            return Prediction(runner.runner_id, None, "nothing before this block to fit")

        # Seeded by runner and race, so a rerun draws the same numbers in any order.
        key = zlib.crc32(f"{runner.runner_id}|{target.race_id}".encode())
        rng = np.random.default_rng([self._seed, key])
        draws = self._posterior.predict(runner.runner_id, runner.sex, target, rng)
        quantiles = summarise(draws)
        seen = runner.runner_id in self._posterior.design.runner_index
        basis = (
            f"fitted on history before {start.isoformat()}"
            if seen
            else f"group prior, history before {start.isoformat()}"
        )
        return Prediction(
            runner.runner_id, quantiles[QUANTILES.index(0.50)], basis, quantiles=quantiles
        )
