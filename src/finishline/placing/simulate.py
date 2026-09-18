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

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from finishline.models.hierarchical import Posterior, reference_seconds
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
) -> np.ndarray:
    """Finish-time draws in seconds, (draws, entrants), with one morning per draw."""
    morning = posterior.morning(target, rng, conditions)
    log_ratio = np.empty((posterior.draws, len(entrants)))
    for column, entrant in enumerate(entrants):
        own = posterior.own(entrant.runner_id, entrant.sex, target, rng)
        log_ratio[:, column] = own + morning + posterior.noise(rng)
    return np.asarray(np.exp(log_ratio) * reference_seconds(target.distance_m))

def simulate(
    posterior: Posterior,
    entrants: Sequence[Entrant],
    target: Race,
    rng: np.random.Generator,
    conditions: np.ndarray | None = None,
) -> list[Place]:
    """Every entrant's simulated place: median and the middle 80 percent."""
    if not entrants:
        return []
    placed = places(field_draws(posterior, entrants, target, rng, conditions))
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
    ]
