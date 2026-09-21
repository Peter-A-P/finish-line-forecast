"""Where each runner finishes in the field, as a distribution (PLAN.md 2.7).

Ranking the point predictions gives every runner one place and no doubt about it, which is
false: two runners predicted a few seconds apart are close to a coin toss for the order, and
a runner in a dense part of the field can move fifty places on an ordinary day. So the whole
field is drawn together many times, placed in each draw, and each runner's place is reported
as a median and a range.

⚠️ **The morning is drawn once per simulated race, not once per runner.** Every runner in a
race shares its course and its weather. A hot day slows the field together and changes the
order hardly at all. `Posterior.predict` draws the edition effect separately for each
runner, which is right for one runner's finish-time interval and wrong for places: summed
over a field it adds rank noise of about `sigma_edition`, four percent of a finish time,
that no race actually has. Here the course and edition effects are drawn once per draw and
shared by every runner in it; only each runner's own fitness uncertainty and bad-day term
are independent.

⚠️ **The equation is written once.** A runner's part comes from `Posterior.own` and the
morning from `Posterior.morning`, the same two functions `Posterior.predict` adds up; a test
still pins that one runner's draws here match `predict`'s distribution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from finishline.models import blend
from finishline.models.hierarchical import Posterior, reference_seconds
from finishline.placing import unseen
from finishline.schema import Race

# The place range published beside the median: the middle 80 percent of simulated places.
PLACE_RANGE = (0.10, 0.90)


@dataclass(frozen=True, slots=True)
class Entrant:
    """Who is running: the id the archive knows them by, if any, and their listed sex."""

    runner_id: str
    sex: str | None


@dataclass(frozen=True, slots=True)
class Place:
    """One runner's simulated place in the field."""

    runner_id: str
    median: float
    low: float
    high: float
    field: int


def places(times: np.ndarray) -> np.ndarray:
    """Places per draw, 1 for the fastest; runners on the same time share the higher place.

    A chip-timed race prints tied runners at the same place and skips the next, so a tie
    here does the same: two runners level in second are both second, and the next is fourth.
    """
    if times.ndim != 2:
        raise ValueError("times must be (draws, runners)")
    ordered = np.sort(times, axis=1)
    result = np.empty(times.shape, dtype=np.int64)
    for draw in range(times.shape[0]):
        result[draw] = np.searchsorted(ordered[draw], times[draw], side="left") + 1
    return result


def field_draws(
    posterior: Posterior,
    entrants: Sequence[Entrant],
    target: Race,
    rng: np.random.Generator,
    conditions: np.ndarray | None = None,
    pool: unseen.Pool | None = None,
    scale: Mapping[str, float] | None = None,
) -> np.ndarray:
    """Finish-time draws in seconds, (draws, entrants), with one morning per draw.

    With a `pool` (`placing.unseen`, the biggest races only), an entrant the archive has never
    seen is drawn from how first-timers at this course finished against the returning field,
    rather than from the group prior.

    `scale` multiplies one runner's draws by one factor, which is how the blend moves a
    runner's whole distribution onto a blended centre (`models.blend`) without touching the
    shared morning that makes the places a field rather than a list. It is applied before the
    pool draws, so a pool newcomer is never scaled.
    """
    morning = posterior.morning(target, rng, conditions)
    log_ratio = np.empty((posterior.draws, len(entrants)))
    for column, entrant in enumerate(entrants):
        own = posterior.own(entrant.runner_id, entrant.sex, target, rng)
        log_ratio[:, column] = own + morning + posterior.noise(rng)
    seconds = np.exp(log_ratio) * reference_seconds(target.distance_m)
    if scale:
        seconds = seconds * np.array(
            [scale.get(entrant.runner_id, 1.0) for entrant in entrants], dtype=float
        )
    new = newcomer_columns(posterior, entrants)
    if pool is not None and new and len(new) < len(entrants):
        known = [column for column in range(len(entrants)) if column not in set(new)]
        drawn = unseen.newcomer_log_times(
            np.log(seconds[:, known]), [entrants[column].sex for column in new], pool, rng
        )
        seconds[:, new] = np.exp(drawn)
    return np.asarray(seconds)


def newcomer_columns(posterior: Posterior, entrants: Sequence[Entrant]) -> list[int]:
    """The entrants the fit has never seen."""
    return [
        column
        for column, entrant in enumerate(entrants)
        if entrant.runner_id not in posterior.design.runner_index
    ]


def simulate(
    posterior: Posterior,
    entrants: Sequence[Entrant],
    target: Race,
    rng: np.random.Generator,
    conditions: np.ndarray | None = None,
    pool: unseen.Pool | None = None,
    scale: Mapping[str, float] | None = None,
) -> list[Place]:
    """Every entrant's simulated place: median and the middle 80 percent."""
    return simulate_field(posterior, entrants, target, rng, conditions, pool, scale)[0]


def forecast_places(
    posterior: Posterior,
    candidates: Sequence[Entrant],
    presence: np.ndarray,
    named: Sequence[str],
    target: Race,
    rng: np.random.Generator,
    conditions: np.ndarray | None = None,
    challenger: Mapping[str, float] | None = None,
    unseen_expected: float = 0.0,
    pool: unseen.Pool | None = None,
    scale: Mapping[str, float] | None = None,
) -> tuple[list[Place], np.ndarray]:
    """Places for a field that was forecast rather than listed (`models.participation`).

    Each simulated race draws who turns up: every candidate runs with their own probability,
    and a Poisson number of runners the archive cannot see (mean `unseen_expected`) run with
    times from this course's first-timer pool, placed against the known runners of that draw.
    A named runner's place is where they would finish **if they run**: one plus everyone who
    turned up in that draw and finished ahead of them. Returns the places and the size of
    each simulated field, which is the bound a published place range is checked against.

    `challenger` moves each candidate's draws onto the blended centre (`models.blend`) by the
    factor their own simulated median implies, so the runners who are not named are blended
    too and the field the named runners are placed in is the published model's field. A
    runner in `scale` (the named runners, whose factor `publish.freeze` fixed from their own
    line) keeps that factor, so their published time and place are one prediction.

    ⚠️ Without a pool the unseen runners are left out and the places are among runners the
    archive knows, which makes them too good by roughly the unseen share; the caller records
    which.
    """
    if len(candidates) != len(presence):
        raise ValueError("one presence probability per candidate")
    seconds = field_draws(posterior, candidates, target, rng, conditions)
    moved: dict[str, float] = {}
    if challenger:
        medians = np.median(seconds, axis=0)
        moved = blend.factors(
            {
                entrant.runner_id: float(median)
                for entrant, median in zip(candidates, medians, strict=True)
            },
            challenger,
        )
    moved.update(scale or {})
    if moved:
        seconds = seconds * np.array([moved.get(entrant.runner_id, 1.0) for entrant in candidates])
    draws = seconds.shape[0]
    present = rng.random(seconds.shape) < presence[None, :]
    column = {entrant.runner_id: index for index, entrant in enumerate(candidates)}
    wanted = np.array([column[runner_id] for runner_id in named], dtype=np.int64)
    counts = np.asarray(
        rng.poisson(unseen_expected, size=draws) if pool is not None else np.zeros(draws),
        dtype=np.int64,
    )
    placed = np.empty((draws, len(wanted)), dtype=np.int64)
    fields = np.empty(draws, dtype=np.int64)
    for draw in range(draws):
        here = np.sort(seconds[draw, present[draw]])
        mine = seconds[draw, wanted]
        ahead = np.searchsorted(here, mine, side="left")
        # A named runner absent from this draw is placed as if they had run: they are not in
        # `here`, so nobody is displaced, and the field they would join is one larger.
        missing = ~present[draw, wanted]
        extra = 0
        if pool is not None and counts[draw] > 0 and here.size:
            # The pool's offsets are against the median returning finisher, as in
            # `unseen.newcomer_log_times`; the list prints no sex for these runners.
            centre = float(np.median(np.log(here)))
            new = np.sort(np.exp(centre + pool.draw(None, int(counts[draw]), rng)))
            ahead = ahead + np.searchsorted(new, mine, side="left")
            extra = int(counts[draw])
        placed[draw] = ahead + 1
        fields[draw] = here.size + extra + int(missing.any())
    low, median, high = np.quantile(placed, [PLACE_RANGE[0], 0.5, PLACE_RANGE[1]], axis=0)
    return [
        Place(
            runner_id=runner_id,
            median=float(median[position]),
            low=float(low[position]),
            high=float(high[position]),
            field=int(np.median(fields)),
        )
        for position, runner_id in enumerate(named)
    ], fields


def simulate_field(
    posterior: Posterior,
    entrants: Sequence[Entrant],
    target: Race,
    rng: np.random.Generator,
    conditions: np.ndarray | None = None,
    pool: unseen.Pool | None = None,
    scale: Mapping[str, float] | None = None,
) -> tuple[list[Place], np.ndarray]:
    """`simulate`, and the (draws, entrants) places it summarised."""
    if not entrants:
        return [], np.empty((posterior.draws, 0), dtype=np.int64)
    placed = places(field_draws(posterior, entrants, target, rng, conditions, pool, scale))
    low, median, high = np.quantile(placed, [PLACE_RANGE[0], 0.5, PLACE_RANGE[1]], axis=0)
    return [
        Place(
            runner_id=entrant.runner_id,
            median=float(median[column]),
            low=float(low[column]),
            high=float(high[column]),
            field=len(entrants),
        )
        for column, entrant in enumerate(entrants)
    ], placed
