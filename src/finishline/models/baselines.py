"""The three answers a runner could get without this project, and what each costs.

Rule: no model result is reported without these beside it (PLAN.md 2.3), and everything
later is reported as skill relative to carry-forward. A portfolio project that skips this
is not credible to anyone who has predicted anything for a living.

The three are chosen to span what people actually do:

**Carry-forward** is what a runner does in their head: take the last race, scale it with
Riegel's power law. It needs one prior result and nothing else, so it answers for almost
everybody, and it is the number to beat.

**Best equal-VDOT** is what every online race calculator does: find the best form in the
last eighteen months, whatever distance it was run at, and read the target distance off
the same fitness curve. It is a better answer than carry-forward when a runner has raced
well recently at some other distance, and it says nothing at all for runners whose times
fall outside the fitted band (`metrics/daniels.py`), which is a share of the field this
project publishes rather than hides.

**Category median** is the only one that answers for a runner with no history: the middle
time of their age and sex category at the last running of this course. It is the floor.
Anything that cannot beat it on runners with several results has learned nothing.

⚠️ **None is an answer here, and it is counted.** A baseline that quietly falls back to
another baseline would flatter itself and hide exactly the coverage difference that makes
these three worth comparing. Each returns None where it genuinely has nothing to say, and
the backtest reports coverage beside error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.metrics import daniels
from finishline.schema import Race


@dataclass(frozen=True, slots=True)
class Prediction:
    """One predicted finish time, and what it was worked out from."""

    runner_id: str
    seconds: float | None
    basis: str
    # Finish-time quantiles at `hierarchical.QUANTILES`, for a model that has a distribution.
    # Empty for the baselines, which give a time and no sense of how sure it is.
    quantiles: tuple[float, ...] = ()

    @property
    def answered(self) -> bool:
        return self.seconds is not None


class Model(Protocol):
    """What the backtest needs from anything that predicts a finish time.

    `name` is a read-only property rather than an attribute so that a frozen dataclass
    satisfies it: a model that can be renamed after it has been scored is a model whose
    results table can be relabelled after the fact.
    """

    @property
    def name(self) -> str: ...

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction: ...


@dataclass(frozen=True, slots=True)
class CarryForward:
    """The most recent result, carried to the target distance by Riegel's power law.

    The baseline every later number is reported against. It needs one prior finish and
    is otherwise indifferent to how much history a runner has, which is its weakness:
    a runner's single result from a bad day on a hot course sets their whole prediction.
    """

    name: str = "carry-forward"

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        latest = history.latest(runner.runner_id)
        if latest is None or latest.seconds is None:
            return Prediction(runner.runner_id, None, "no prior finish")
        base = history.races[latest.race_id]
        seconds = daniels.riegel(latest.seconds, base.distance_m, target.distance_m)
        return Prediction(
            runner.runner_id,
            seconds,
            f"{base.name} on {base.date.isoformat()}",
        )


@dataclass(frozen=True, slots=True)
class BestEqualVdot:
    """The best form of the last eighteen months, read off at the target distance.

    What every race calculator does. It refuses where the fitness curve is not fitted,
    which is most of the back of a marathon field, and that refusal is the point.
    """

    name: str = "best-equal-vdot"

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        best: tuple[float, str] | None = None
        for result in history.recent(runner.runner_id):
            race = history.races[result.race_id]
            value = daniels.vdot(race.distance_m, result.seconds)
            if value is not None and (best is None or value > best[0]):
                best = (value, f"{race.name} on {race.date.isoformat()}")
        if best is None:
            return Prediction(
                runner.runner_id,
                None,
                "no recent result inside the fitness model's range",
            )
        return Prediction(
            runner.runner_id, daniels.race_time(best[0], target.distance_m), best[1]
        )


@dataclass(frozen=True, slots=True)
class CategoryMedian:
    """The middle time of this runner's category at the last running of this course.

    The cold-start answer, and the floor. It uses no information about the runner except
    their sex and age band, so a model that cannot beat it on runners with a history has
    not earned its complexity.
    """

    name: str = "category-median"

    def predict(self, runner: Runner, target: Race, history: History) -> Prediction:
        band = _latest_band(runner, history)
        seconds, basis = history.category_median(target.course_id, runner.sex, band)
        return Prediction(runner.runner_id, seconds, basis)


def _latest_band(runner: Runner, history: History) -> str | None:
    """The age band this runner was printed under most recently, in the history.

    ⚠️ **History only, never the runner's own results.** A `Runner` carries every result
    including the race being predicted, and reading the band off that one would take it
    from the finishing list of the race in question. A runner who has never raced has no
    band, and the median falls back to sex or to the whole field, which is the honest
    answer. See `backtest.run._as_known_at_the_start`.
    """
    for result in reversed(history.results_of(runner.runner_id)):
        if result.age_band:
            return result.age_band
    return None


BASELINES: tuple[Model, ...] = (CarryForward(), BestEqualVdot(), CategoryMedian())
