"""The rolling origin: predict every race from the archive that existed before it.

One origin per race edition. At each one, the history is cut the day before (see
`finishline.history`), every model predicts the field that actually ran, and the
predictions are scored against what those runners did. That is the same procedure the
live prediction uses, with one more origin on the end, which is the point: the backtest
is not a different code path from the thing being published.

⚠️ **The field is the runners who finished, not the runners who entered.** For a past
race that is all the archive records, so the backtest scores prediction accuracy and says
nothing about who shows up. The live prediction has the entrant list and reports the
no-show rate separately (PLAN.md 5.6); the two numbers are kept apart on purpose, because
folding them together would let a good prediction hide a bad field forecast.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from finishline.backtest.score import Scored
from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.models.baselines import Model
from finishline.schema import Race, Result


class LeakageError(AssertionError):
    """A model was about to be shown a result from the race it is predicting, or later."""


@dataclass(frozen=True, slots=True)
class Origin:
    """One race, and the runners whose finish is being predicted."""

    race: Race
    finishers: tuple[tuple[Runner, Result], ...]


def origins(
    races: dict[str, Race], runners: Sequence[Runner], *, scored_from: int
) -> list[Origin]:
    """Every race from `scored_from` onward, with the runners who finished it.

    Earlier races are history for these origins and are never targets themselves, which
    is what gives the first scored race something to learn from.
    """
    finishers: dict[str, list[tuple[Runner, Result]]] = {}
    for runner in runners:
        if runner.ambiguous:
            continue
        for result in runner.results:
            if result.finished:
                finishers.setdefault(result.race_id, []).append((runner, result))

    return [
        Origin(race=race, finishers=tuple(finishers.get(race_id, ())))
        for race_id, race in sorted(races.items(), key=lambda item: item[1].date)
        if race.date.year >= scored_from and finishers.get(race_id)
    ]


def check_no_leakage(history: History, target: Race) -> None:
    """Refuse to score if anything in the history is dated on or after the target race.

    The one check that cannot be allowed to be a comment. It runs at every origin.
    """
    for race in history.races.values():
        if race.date >= target.date:
            raise LeakageError(
                f"history for {target.race_id} ({target.date}) contains "
                f"{race.race_id} ({race.date}), which is not earlier"
            )


def run(
    races: dict[str, Race],
    runners: Sequence[Runner],
    models: Iterable[Model],
    *,
    scored_from: int,
) -> list[Scored]:
    """Score every model at every origin, and return one row per runner per model."""
    models = list(models)
    scored: list[Scored] = []
    for origin in origins(races, runners, scored_from=scored_from):
        history = History.before(origin.race.date, races, list(runners))
        check_no_leakage(history, origin.race)

        for runner, actual in origin.finishers:
            if actual.seconds is None:
                continue
            at_start = _as_known_at_the_start(runner, history)
            depth = len(at_start.results)
            for model in models:
                prediction = model.predict(at_start, origin.race, history)
                scored.append(
                    Scored(
                        model=model.name,
                        race_id=origin.race.race_id,
                        runner_id=runner.runner_id,
                        predicted=prediction.seconds,
                        actual=actual.seconds,
                        depth=depth,
                        quantiles=prediction.quantiles,
                    )
                )
    return scored


def _as_known_at_the_start(runner: Runner, history: History) -> Runner:
    """The runner as they were knowable the day before, not as the results page has them.

    ⚠️ **This exists because of a leak that the tests found.** A `Runner` carries every
    result, including the one being predicted, and the category-median baseline read the
    age band off the most recent of them. For a first-timer that band came from the
    finishing list of the race being predicted, which is the answer sheet. So the runner
    handed to a model carries only the results the history carries.

    **Sex is deliberately kept**, and the distinction is worth stating. A runner's sex is
    printed on the entrant list that the live prediction works from (PLAN.md 0), so
    knowing it before the gun is not a leak; knowing their finishing age band when they
    have never raced before is. Where the archive is the only source, sex comes from the
    same results page, and the backtest is therefore very slightly kinder to the
    category-median baseline than the live run will be. Said here rather than discovered
    later.
    """
    known = history.runners.get(runner.runner_id)
    return Runner(
        runner_id=runner.runner_id,
        name=runner.name,
        hometown=runner.hometown,
        sex=runner.sex,
        results=known.results if known else (),
        ambiguous=runner.ambiguous,
        reason=runner.reason,
    )
