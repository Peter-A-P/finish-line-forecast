"""Scoring a published prediction against the official results (PLAN.md 5.7 and section 1).

Everything `finishline score` does except reading git and the network, so that the whole
scoring is testable on a prediction file and a results list built by hand.

WHAT IS SCORED
--------------
**The bytes at the tag, never the working copy.** A prediction counts because a tag holding it
predates the gun (PLAN.md 2.2), so the file that is scored is the one the tag points at, its
SHA-256 has to be the one the tag message published, and the tag has to be at least
`MINIMUM_NOTICE` before the gun. `check_tag` and `check_digest` refuse otherwise, and there is
no flag to score an untagged or late prediction: it is not a prediction.

HOW A PUBLISHED LINE FINDS ITS RESULT
-------------------------------------
The file carries a name and a hometown and nothing else, on purpose, so the match is on the
name key (`identity.normalise.name_key`), the same key the resolver and the linker use.

- **One result of that name key: matched.** A finish if the row has a time, a did-not-finish
  if it does not.
- **None: not found in the results.** Mostly a no-show. ⚠️ Also a runner the list and the
  results spell differently ("Mike" on one, "Michael" on the other), so the no-show rate this
  reports is an upper bound on the real one, and says so wherever it is printed.
- **Several: the published hometown breaks the tie** if exactly one of them printed that town,
  as in the resolver. Otherwise the line is excluded and counted, never guessed: scoring one
  person's prediction against another person's time is the same error as publishing it.
- **Two published lines of one name key are both excluded**, for the reason the linker
  excludes them.

⚠️ **Runners who did not finish are counted, never named.** The prediction file already named
everyone it predicted. Which of them then failed to appear is an inference from absence, not
something any results page printed, so the race page lists finishers only.

THE INTERVALS ON THESE NUMBERS
------------------------------
Every rate and error carries a percentile bootstrap interval, resampling runners with the
seed the backtest uses. ⚠️ **One race is one morning.** The backtest's coverage intervals
resample races because runners in one race share its weather; here there is only one race,
so the interval says how precisely these runners measured this model on this day, and nothing
about the next race. The page and the README say that beside the table.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np

from finishline.backtest.score import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    CONFIDENCE,
    STRATA,
    ranks,
    stratum_of,
)
from finishline.identity.normalise import name_key, town_key
from finishline.publish.predictions import MINIMUM_NOTICE, sha256
from finishline.schema import Result

SCHEMA_VERSION = 1
LEVELS: tuple[str, ...] = ("80", "90")


class NotPreRegistered(RuntimeError):
    """The file at the tag is not a prediction that counts."""


def check_tag(tagged_at: datetime, gun: datetime) -> None:
    """Refuse unless the tag predates the gun by at least `MINIMUM_NOTICE`.

    ⚠️ **The tagger date is the tagging machine's clock**, which a person can set. It is the
    check this command can make; the stronger evidence is the push, which GitHub records, and
    the race page links the tag there so a reader can compare the two.
    """
    if tagged_at.tzinfo is None or gun.tzinfo is None:
        raise NotPreRegistered("the tag time and the gun must both carry a time zone")
    if gun - tagged_at < MINIMUM_NOTICE:
        raise NotPreRegistered(
            f"tagged at {tagged_at.isoformat()}, {gun - tagged_at} before a gun at "
            f"{gun.isoformat()}; a prediction has to be tagged at least {MINIMUM_NOTICE} "
            "before the gun to count"
        )


def check_digest(data: bytes, tag_message: str) -> str:
    """The file's SHA-256, refusing unless the tag message published that same hash."""
    digest = sha256(data)
    if f"sha256 {digest}" not in tag_message:
        raise NotPreRegistered(
            f"the tagged file hashes to {digest}, which the tag message does not publish"
        )
    return digest


@dataclass(frozen=True, slots=True)
class Published:
    """One line of a prediction file, read back."""

    position: int
    name: str
    hometown: str | None
    prior_results: int
    seconds: float
    interval_80: tuple[float, float]
    interval_90: tuple[float, float]
    place: float
    place_low: float
    place_high: float

    @classmethod
    def read(cls, position: int, record: Mapping[str, Any]) -> Published:
        low80, high80 = record["interval_80"]
        low90, high90 = record["interval_90"]
        place = record["place"]
        return cls(
            position=position,
            name=str(record["name"]),
            hometown=record.get("hometown"),
            prior_results=int(record["prior_results"]),
            seconds=float(record["seconds"]),
            interval_80=(float(low80), float(high80)),
            interval_90=(float(low90), float(high90)),
            place=float(place["median"]),
            place_low=float(place["low"]),
            place_high=float(place["high"]),
        )

    def interval(self, level: str) -> tuple[float, float]:
        return self.interval_80 if level == "80" else self.interval_90


def published(doc: Mapping[str, Any]) -> list[Published]:
    """Every runner line in a prediction file, in file order."""
    return [Published.read(position, record) for position, record in enumerate(doc["runners"])]


class Outcome(StrEnum):
    FINISHED = "finished"
    DID_NOT_FINISH = "did not finish"
    NOT_FOUND = "not found in the results"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class Match:
    """One published line and what the results say happened to that runner."""

    line: Published
    outcome: Outcome
    result: Result | None

    @property
    def actual(self) -> float:
        """The finish time. Only asked of a finish."""
        if self.result is None or self.result.seconds is None:
            raise ValueError(f"{self.line.name} has no finish time")
        return self.result.seconds


@dataclass(frozen=True, slots=True)
class Matching:
    """Every published line matched, and the finishers nobody predicted."""

    matches: tuple[Match, ...]
    finishers: int
    unpredicted_finishers: int

    def with_outcome(self, outcome: Outcome) -> list[Match]:
        return [item for item in self.matches if item.outcome is outcome]


def match(lines: Sequence[Published], results: Sequence[Result]) -> Matching:
    """Each published line against the results page, by name key, refusing to guess."""
    by_key: dict[str, list[Result]] = defaultdict(list)
    for result in results:
        by_key[name_key(result.name)].append(result)
    published_keys = Counter(name_key(line.name) for line in lines)

    matches: list[Match] = []
    for line in lines:
        key = name_key(line.name)
        candidates = by_key.get(key, [])
        if published_keys[key] > 1:
            matches.append(Match(line, Outcome.AMBIGUOUS, None))
            continue
        if not candidates:
            matches.append(Match(line, Outcome.NOT_FOUND, None))
            continue
        if len(candidates) > 1 and line.hometown:
            town = town_key(line.hometown)
            same_town = [c for c in candidates if c.hometown and town_key(c.hometown) == town]
            if len(same_town) == 1:
                candidates = same_town
        if len(candidates) > 1:
            matches.append(Match(line, Outcome.AMBIGUOUS, None))
            continue
        result = candidates[0]
        outcome = Outcome.FINISHED if result.finished else Outcome.DID_NOT_FINISH
        matches.append(Match(line, outcome, result))

    finishers = sum(1 for result in results if result.finished)
    predicted_finishes = sum(1 for item in matches if item.outcome is Outcome.FINISHED)
    return Matching(tuple(matches), finishers, finishers - predicted_finishes)


def _interval(values: Sequence[float] | np.ndarray) -> list[float] | None:
    """A mean with its percentile bootstrap interval over runners: [point, low, high]."""
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    picks = rng.integers(0, array.size, size=(BOOTSTRAP_DRAWS, array.size))
    means = array[picks].mean(axis=1)
    tail = (1.0 - CONFIDENCE) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return [float(array.mean()), float(low), float(high)]


def _statistic_interval(
    statistic: Callable[[np.ndarray, np.ndarray], float],
    predicted: np.ndarray,
    actual: np.ndarray,
) -> list[float] | None:
    """A statistic of paired arrays with a bootstrap interval, recomputed per resample."""
    point = statistic(predicted, actual)
    if not np.isfinite(point):
        return None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = np.empty(BOOTSTRAP_DRAWS)
    for draw in range(BOOTSTRAP_DRAWS):
        pick = rng.integers(0, predicted.size, size=predicted.size)
        values[draw] = statistic(predicted[pick], actual[pick])
    tail = (1.0 - CONFIDENCE) / 2.0
    low, high = np.nanquantile(values, [tail, 1.0 - tail])
    return [float(point), float(low), float(high)]


def _place_gap(predicted: np.ndarray, actual: np.ndarray) -> float:
    return float(np.abs(ranks(predicted) - ranks(actual)).mean())


def _spearman(predicted: np.ndarray, actual: np.ndarray) -> float:
    left, right = ranks(predicted), ranks(actual)
    if left.std() == 0 or right.std() == 0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


def _errors(
    finishes: Sequence[Match], carry_forward: Mapping[int, float | None]
) -> dict[str, Any]:
    """Finish-time error for these runners, and against carry-forward where it answered."""
    predicted = np.asarray([item.line.seconds for item in finishes], dtype=float)
    actual = np.asarray([item.actual for item in finishes], dtype=float)
    error = predicted - actual
    record: dict[str, Any] = {
        "runners": len(finishes),
        "mae_minutes": _interval(np.abs(error) / 60.0),
        "mean_percent_error": _interval(np.abs(error) / actual * 100.0),
        "bias_minutes": _interval(error / 60.0),
    }
    answered = [
        (index, carry_forward[item.line.position])
        for index, item in enumerate(finishes)
        if carry_forward.get(item.line.position) is not None
    ]
    indices = np.asarray([index for index, _ in answered], dtype=int)
    baseline = np.asarray([seconds for _, seconds in answered], dtype=float)
    model_abs = np.abs(error[indices]) / 60.0
    baseline_abs = np.abs(baseline - actual[indices]) / 60.0
    record["carry_forward"] = {
        "runners": len(answered),
        "model_mae_minutes": _interval(model_abs),
        "carry_forward_mae_minutes": _interval(baseline_abs),
        "difference_minutes": _interval(model_abs - baseline_abs),
    }
    return record


def _intervals(finishes: Sequence[Match]) -> dict[str, Any]:
    record: dict[str, Any] = {"runners": len(finishes)}
    for level in LEVELS:
        bounds = [item.line.interval(level) for item in finishes]
        inside = [
            low <= item.actual <= high
            for item, (low, high) in zip(finishes, bounds, strict=True)
        ]
        record[level] = {
            "coverage": _interval([float(hit) for hit in inside]),
            "median_width_minutes": (
                float(np.median([(high - low) / 60.0 for low, high in bounds]))
                if bounds
                else None
            ),
        }
    return record


def _placing(
    finishes: Sequence[Match], carry_forward: Mapping[int, float | None]
) -> dict[str, Any]:
    """Order among the matched finishers, and whether the published place range held.

    ⚠️ **The place range is checked against the place the results printed**, in a field that
    has the late entries in it and the no-shows out of it, which the predicted field did not.
    That is the number a reader of the prediction would check, so it is the one scored.
    """
    predicted = np.asarray([item.line.seconds for item in finishes], dtype=float)
    actual = np.asarray([item.actual for item in finishes], dtype=float)
    enough = len(finishes) >= 3
    printed = [
        (item, item.result.place)
        for item in finishes
        if item.result is not None and item.result.place is not None
    ]
    record: dict[str, Any] = {
        "runners": len(finishes),
        "place_error": _statistic_interval(_place_gap, predicted, actual) if enough else None,
        "spearman": _statistic_interval(_spearman, predicted, actual) if enough else None,
        "range_held": _interval(
            [float(item.line.place_low <= place <= item.line.place_high) for item, place in printed]
        ),
        "range_checked": len(printed),
    }
    shared = [
        (index, carry_forward[item.line.position])
        for index, item in enumerate(finishes)
        if carry_forward.get(item.line.position) is not None
    ]
    if len(shared) >= 3:
        indices = np.asarray([index for index, _ in shared], dtype=int)
        baseline = np.asarray([seconds for _, seconds in shared], dtype=float)
        record["carry_forward"] = {
            "runners": len(shared),
            "model_place_error": _statistic_interval(
                _place_gap, predicted[indices], actual[indices]
            ),
            "carry_forward_place_error": _statistic_interval(
                _place_gap, baseline, actual[indices]
            ),
        }
    return record


def evaluate(
    *,
    doc: Mapping[str, Any],
    matching: Matching,
    carry_forward: Mapping[int, float | None],
    prediction: Mapping[str, Any],
    results: Mapping[str, Any],
    scored_at: datetime,
) -> dict[str, Any]:
    """The score card: every live number of PLAN.md section 1, as a plain structure.

    `carry_forward` maps a line's position in the file to the carry-forward baseline's time
    for that runner, None where it had nothing to say. It is computed by the caller from the
    archive as it stood the day before, exactly as in the backtest.
    """
    finishes = matching.with_outcome(Outcome.FINISHED)
    entrants = doc["entrants"]
    predicted_count = len(matching.matches)

    def share(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    by_stratum_errors: dict[str, Any] = {}
    by_stratum_intervals: dict[str, Any] = {}
    for label, _low, _high in STRATA:
        mine = [item for item in finishes if stratum_of(item.line.prior_results) == label]
        by_stratum_errors[label] = _errors(mine, carry_forward)
        by_stratum_intervals[label] = _intervals(mine)

    card: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "race": dict(doc["race"]),
        "gun": doc["gun"],
        "scored_at": scored_at.isoformat(),
        "prediction": dict(prediction),
        "results": dict(results),
        "field": {
            "listed": entrants["listed"],
            "linked": entrants["linked"],
            "excluded_at_freeze": entrants["ambiguous"],
            "predicted": predicted_count,
            "finished": len(finishes),
            "did_not_finish": len(matching.with_outcome(Outcome.DID_NOT_FINISH)),
            "not_found": len(matching.with_outcome(Outcome.NOT_FOUND)),
            "ambiguous": len(matching.with_outcome(Outcome.AMBIGUOUS)),
            "finishers": matching.finishers,
            "unpredicted_finishers": matching.unpredicted_finishers,
        },
        "shares": {
            "finishers_with_a_prediction": share(len(finishes), matching.finishers),
            "predictions_that_finished": share(len(finishes), predicted_count),
            "entrants_with_history": share(entrants["linked"], entrants["listed"]),
        },
        "error": {"all": _errors(finishes, carry_forward), "by_stratum": by_stratum_errors},
        "intervals": {"all": _intervals(finishes), "by_stratum": by_stratum_intervals},
        "placing": _placing(finishes, carry_forward),
    }
    forecast = doc.get("field_forecast")
    if forecast is not None:
        # A race with no start list: the file named its runners from the participation
        # model, and promised a precision from its backtest. This is that promise checked.
        test = (forecast.get("backtest") or {}).get("test") or {}
        card["field_forecast"] = {
            "named": predicted_count,
            "promised_precision": test.get("precision"),
            "measured_precision": share(len(finishes), predicted_count),
        }
    return card


# Rendering. The race page and the README row are both written from the score card alone, so
# `finishline report` can rewrite them from the committed files without the cache.


def _forecast_rows(card: Mapping[str, Any]) -> list[str]:
    """For a race with no start list, the precision its backtest promised beside the real one."""
    forecast = card.get("field_forecast")
    if not forecast or not forecast.get("promised_precision"):
        return []
    point, low, high = forecast["promised_precision"]
    return [
        f"| No start list: the runners were named by the participation model; its backtest "
        f"said {100 * point:.0f}% ({100 * low:.0f} to {100 * high:.0f}) of them would finish | "
        f"{_share(forecast['measured_precision'])} did |",
    ]


def _clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def ci(value: list[float] | None, digits: int = 1, scale: float = 1.0, unit: str = "") -> str:
    if value is None:
        return "-"
    point, low, high = (v * scale for v in value)
    return f"{point:.{digits}f}{unit} ({low:.{digits}f} to {high:.{digits}f})"


def percent(value: list[float] | None) -> str:
    return ci(value, 0, 100.0, "%")


def _share(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


ASSUMPTION = (
    "**One race is one morning.** The intervals above resample this race's runners, so they "
    "say how precisely these runners measured the model on this day. Runners in one race share "
    "its weather and its course, and when the morning surprises the model every runner misses "
    "together, which no resampling of one race can show. A second race is the only thing that "
    "narrows that, and it is why a frozen model is scored on two."
)

NOT_FOUND_NOTE = (
    "\"Not found in the results\" is mostly no-shows and partly names the start list and the "
    "results spell differently, so it is an upper bound on the no-show rate. Runners who did not "
    "finish are counted here and never named."
)


def race_page(card: Mapping[str, Any], matching: Matching) -> str:
    """The race's page: the counts, the error tables, and every finisher side by side."""
    race = card["race"]
    prediction = card["prediction"]
    field = card["field"]
    lines = [
        f"# {race['name']}, {race['date']}: predicted, then scored",
        "",
        f"Written by `finishline score {race['race_id']}`; not edited by hand.",
        "",
        f"**The prediction.** [`{prediction['file']}`](../../{prediction['file']}), SHA-256 "
        f"`{prediction['sha256']}`, tagged `{prediction['tag']}` at {prediction['tagged_at']} "
        f"for a gun at {card['gun']}. Model `{prediction['model']}` at commit "
        f"`{prediction['commit'][:12]}`. Scored against {card['results']['url']} "
        f"(SHA-256 `{card['results']['sha256'][:16]}`) on {card['scored_at'][:10]}.",
        "",
        "## Who was predicted, and who ran",
        "",
        "| | |",
        "|---|---:|",
        f"| On the start list at freeze | {field['listed']} |",
        f"| Linked to a history in the archive | {field['linked']} |",
        f"| Excluded at freeze as ambiguous | {field['excluded_at_freeze']} |",
        f"| Predicted | {field['predicted']} |",
        f"| Predicted and finished | {field['finished']} |",
        f"| Predicted, did not finish | {field['did_not_finish']} |",
        f"| Predicted, not found in the results | {field['not_found']} |",
        f"| Predicted, too ambiguous to score | {field['ambiguous']} |",
        f"| Finishers in the results | {field['finishers']} |",
        f"| Finishers with no prediction | {field['unpredicted_finishers']} |",
        f"| Share of finishers with a prediction | "
        f"{_share(card['shares']['finishers_with_a_prediction'])} |",
        f"| Share of predictions that finished | "
        f"{_share(card['shares']['predictions_that_finished'])} |",
        *_forecast_rows(card),
        "",
        NOT_FOUND_NOTE,
        "",
        "## Finish time",
        "",
        "| Prior results | Runners | MAE, minutes (95% CI) | Mean % error | Bias, minutes "
        "| Carry-forward answered | MAE on those: model | MAE on those: carry-forward "
        "| Model minus carry-forward, minutes |",
        "|---|---:|---|---|---|---:|---|---|---|",
    ]
    errors = card["error"]
    for label, record in [("All", errors["all"]), *errors["by_stratum"].items()]:
        paired = record["carry_forward"]
        lines.append(
            f"| {label} | {record['runners']} | {ci(record['mae_minutes'])} "
            f"| {ci(record['mean_percent_error'], unit='%')} | {ci(record['bias_minutes'])} "
            f"| {paired['runners']} | {ci(paired['model_mae_minutes'])} "
            f"| {ci(paired['carry_forward_mae_minutes'])} "
            f"| {ci(paired['difference_minutes'])} |"
        )
    lines += [
        "",
        "Negative in the last column means the model was closer. Bias is predicted minus actual, "
        "so positive means predicted too slow.",
        "",
        "## Intervals",
        "",
        "| Prior results | Runners | 80% held (95% CI) | Median 80% width, minutes "
        "| 90% held (95% CI) | Median 90% width, minutes |",
        "|---|---:|---|---:|---|---:|",
    ]
    intervals = card["intervals"]
    for label, record in [("All", intervals["all"]), *intervals["by_stratum"].items()]:
        cells = []
        for level in LEVELS:
            width = record[level]["median_width_minutes"]
            cells.append(percent(record[level]["coverage"]))
            cells.append("-" if width is None else f"{width:.1f}")
        lines.append(f"| {label} | {record['runners']} | " + " | ".join(cells) + " |")

    placing = card["placing"]
    lines += [
        "",
        "## Placing",
        "",
        "| | Runners | Estimate (95% CI) |",
        "|---|---:|---|",
        f"| Mean absolute place error, among predicted finishers | {placing['runners']} "
        f"| {ci(placing['place_error'])} |",
        f"| Spearman, predicted vs actual order | {placing['runners']} "
        f"| {ci(placing['spearman'], 3)} |",
        f"| Printed place inside the published place range | {placing['range_checked']} "
        f"| {percent(placing['range_held'])} |",
    ]
    if "carry_forward" in placing:
        paired = placing["carry_forward"]
        lines += [
            f"| Place error on the runners carry-forward answered: model | {paired['runners']} "
            f"| {ci(paired['model_place_error'])} |",
            f"| Place error on the same runners: carry-forward | {paired['runners']} "
            f"| {ci(paired['carry_forward_place_error'])} |",
        ]
    lines += [
        "",
        "The published place range was simulated in the predicted field; the printed place is in "
        "the field that ran, with late entries in it and no-shows out of it.",
        "",
        ASSUMPTION,
        "",
        "## Runner by runner",
        "",
        "Finishers only, in predicted order, as the prediction file and the results printed them.",
        "",
        "| Name | Hometown | Prior results | Predicted | 80% interval | Actual | Error "
        "| Place range | Printed place |",
        "|---|---|---:|---:|---|---:|---:|---|---:|",
    ]
    for item in sorted(
        matching.with_outcome(Outcome.FINISHED), key=lambda m: (m.line.seconds, m.line.name)
    ):
        line = item.line
        low, high = line.interval_80
        error = line.seconds - item.actual
        sign = "+" if error >= 0 else "-"
        place = item.result.place if item.result is not None else None
        lines.append(
            f"| {line.name} | {line.hometown or ''} | {line.prior_results} "
            f"| {_clock(line.seconds)} | {_clock(low)} to {_clock(high)} "
            f"| {_clock(item.actual)} | {sign}{_clock(abs(error))} "
            f"| {line.place_low:.0f} to {line.place_high:.0f} "
            f"| {'' if place is None else place} |"
        )
    return "\n".join(lines) + "\n"


def live_table(cards: Sequence[Mapping[str, Any]]) -> str:
    """The README's live rows, one per scored race, oldest first."""
    if not cards:
        return (
            "_No prediction has been scored yet. `finishline score <race>` fills a row here "
            "once a tagged prediction's official results are posted._"
        )
    lines = [
        "| Race | Finishers scored | Finishers with a prediction | Predictions that finished "
        "| MAE, minutes: model | Model minus carry-forward, minutes | 80% held | 90% held "
        "| Place error | Spearman | Prediction |",
        "|---|---:|---:|---:|---|---|---|---|---|---|---|",
    ]
    for card in sorted(cards, key=lambda c: str(c["race"]["date"])):
        race = card["race"]
        prediction = card["prediction"]
        errors = card["error"]["all"]
        intervals = card["intervals"]["all"]
        placing = card["placing"]
        lines.append(
            f"| [{race['name']}, {race['date']}](docs/predictions/{race['race_id']}.md) "
            f"| {card['field']['finished']} "
            f"| {_share(card['shares']['finishers_with_a_prediction'])} "
            f"| {_share(card['shares']['predictions_that_finished'])} "
            f"| {ci(errors['mae_minutes'])} "
            f"| {ci(errors['carry_forward']['difference_minutes'])} "
            f"| {percent(intervals['80']['coverage'])} | {percent(intervals['90']['coverage'])} "
            f"| {ci(placing['place_error'])} | {ci(placing['spearman'], 3)} "
            f"| `{prediction['tag']}`, sha256 `{prediction['sha256'][:12]}` |"
        )
    lines += [
        "",
        "95% CIs resample runners within each race, so each describes that race's morning "
        "and not the next one: runners in one race share its weather, and when the morning "
        "surprises the model they miss together. "
        "Model minus carry-forward is on the runners carry-forward could answer for; negative "
        "means the model was closer.",
    ]
    return "\n".join(lines)
