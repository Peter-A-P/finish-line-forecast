"""The measured numbers the website draws, written by the command that measures them.

`finishline report` writes the README's tables and, from the same objects in the same run,
`data/site/results.json`, which `finishline site` puts on the website. So the website and the
README cannot disagree: neither is typed by hand, and both come from one measurement.

⚠️ **No names.** The website's charts are built from this file and it is committed, so it
holds counts, errors, intervals and course facts, never a name, a hometown or a runner id. The
one place individual runners appear is the backtest scatter for each live race's course: a
predicted and an actual time, a conformal range and a history depth per finisher, sorted by
the actual time. A finish time can be matched to its line on the public results page, so a
point is not anonymous to someone who goes looking; what it adds to that line is a backtest
prediction and its range, which is less than the project publishes by name for every live
entrant. A test asserts that no name-like field gets in.
"""

from __future__ import annotations

import bisect
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from finishline.backtest import score
from finishline.conformal import coverage, split
from finishline.identity.link import Link
from finishline.models import conditions, courses
from finishline.schema import HALF_MARATHON_M, MARATHON_M, MILE_M
from finishline.store import Dataset

# What the website calls "the model" is what `freeze` publishes, and since PLAN.md 13 item 35
# that is the blend: the hierarchical model's distribution moved onto the average of the two
# models' centres. Both parents stay in the file, because a page that shows only the winner is
# not showing the measurement.
MODEL = "blend"
PARENT = "hierarchical"
BASELINE = "carry-forward"
CHALLENGER = "lightgbm"

# Written as the words a runner uses, where the course id cannot say it.
_UPPER = {"usr", "ane", "chcm", "hbc", "prc", "vocm", "nlaa"}
_LOWER = {"to", "by", "the", "and", "from", "of"}
_NAMES = {
    "tely-10-16093": "Tely 10",
    "huffin-puffin-42195": "Huffin Puffin marathon",
    "usr-old-21097": "USR half marathon, before 2026",
    "coleman-s-21097": "Coleman's half marathon",
    "740-10000": "VOCM 740 10 km",
    "ane-mile-1609": "ANE Open Mile",
    "five-and-dime-5000": "Five and Dime 5 km",
    "five-and-dime-10000": "Five and Dime 10 km",
}


def distance_label(metres: float) -> str:
    """How a runner says a distance: 10 km, half marathon, 10 mile."""
    if abs(metres - MARATHON_M) < 50:
        return "marathon"
    if abs(metres - HALF_MARATHON_M) < 50:
        return "half marathon"
    if abs(metres - 10 * MILE_M) < 50:
        return "10 mile"
    if abs(metres - MILE_M) < 5:
        return "mile"
    return f"{metres / 1000:g} km"


def course_name(course_id: str) -> str:
    """A course id as a reader would write it: `cape-to-cabot-20000` is Cape to Cabot 20 km."""
    if course_id in _NAMES:
        return _NAMES[course_id]
    *words, metres = course_id.split("-")
    try:
        distance = distance_label(float(metres))
    except ValueError:
        return course_id
    shown = [
        word.upper() if word in _UPPER else word if index and word in _LOWER else word.title()
        for index, word in enumerate(words)
    ]
    return f"{' '.join(shown)} {distance}"


def spread(rows: Sequence[score.Scored]) -> dict[str, float | None]:
    """The shape of a set of misses, not just their average.

    An average miss is read by most people as "every prediction is out by this much", which is
    not what it says: half the misses are smaller, and the tail is what makes the average bigger
    than the middle. So the median and the ninth decile are published beside it, and the page
    says them in those words.
    """
    misses = sorted(abs(row.error) for row in rows if row.error is not None)
    if not misses:
        return {"median_error_min": None, "p90_error_min": None}
    return {
        "median_error_min": _minutes(statistics.median(misses)),
        "p90_error_min": _minutes(misses[min(int(0.9 * len(misses)), len(misses) - 1)]),
    }


def error_text(minutes: float) -> str:
    """An error as a reader says it: "48 sec" under a minute, "3.6 min" over one.

    The page and the README both call this, so a fast runner's error never reads "0.8 min",
    which is a number nobody says out loud.
    """
    if minutes < 1.0:
        return f"{round(minutes * 60)} sec"
    return f"{minutes:.1f} min"


def _minutes(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds / 60.0, 2)


def _round(value: float | None, places: int = 4) -> float | None:
    return None if value is None or not math.isfinite(value) else round(value, places)


def archive(data: Dataset) -> dict[str, Any]:
    """What the archive holds, and how much history its runners have."""
    by_year: dict[int, int] = {}
    for result in data.results:
        if result.finished:
            year = data.races[result.race_id].year
            by_year[year] = by_year.get(year, 0) + 1
    unread = {race.race_id for race, _why in data.failures}
    return {
        "races": len(data.races) - len(unread),
        "courses": len({r.course_id for r in data.races.values() if r.race_id not in unread}),
        "finishes": data.finishes,
        "runners": len(data.resolved),
        "ambiguous": len(data.ambiguous),
        "unparsed": len(data.failures),
        "first_year": min(by_year),
        "last_year": max(by_year),
        "depth": data.depth_counts(),
        "finishes_by_year": [[year, by_year[year]] for year in sorted(by_year)],
    }


def backtest(
    scored: Sequence[score.Scored], names: Sequence[str], race_dates: Mapping[str, date]
) -> dict[str, Any]:
    """Error by history depth for every model, interval coverage, and paired placing."""
    strata = []
    for label, _low, _high in score.STRATA:
        rows = [row for row in scored if score.stratum_of(row.depth) == label]
        if not rows:
            continue
        baseline = score.summarise(rows, names[0])
        models = {}
        for name in names:
            summary = score.summarise(rows, name)
            models[name] = {
                "answered": _round(summary.coverage),
                "mae_min": _minutes(summary.mae_seconds),
                "low_min": _minutes(summary.mae_low),
                "high_min": _minutes(summary.mae_high),
                "mape": _round(summary.mape),
                "skill": _round(score.skill(summary, baseline)) if name != names[0] else None,
            }
        strata.append({"label": label, "runners": baseline.runners, "models": models})

    payload: dict[str, Any] = {
        "races": len({row.race_id for row in scored}),
        "predictions": sum(1 for row in scored if row.model == MODEL),
        "first_race": min(race_dates[row.race_id] for row in scored).isoformat(),
        "last_race": max(race_dates[row.race_id] for row in scored).isoformat(),
        "strata": strata,
        "coverage": [],
        "placing": None,
    }
    if MODEL not in names:
        return payload

    payload["coverage"] = _coverage(scored, MODEL, race_dates)
    if CHALLENGER in names:
        payload["challenger_coverage"] = _coverage(scored, CHALLENGER, race_dates)
        # The challenger against the model it was built to test, which is item 33's finding and
        # the reason the blend exists, and then the published blend against each parent.
        payload["challenger_paired"] = _paired(scored, CHALLENGER, PARENT)
        payload["blend_paired"] = {
            PARENT: _paired(scored, MODEL, PARENT),
            CHALLENGER: _paired(scored, MODEL, CHALLENGER),
        }
        placing = score.paired_placing(scored, CHALLENGER, BASELINE)
        if placing is not None:
            gap, gap_low, gap_high = placing.gap_difference
            payload["challenger_placing"] = {
                "places": round(placing.gap, 2),
                "baseline": round(placing.baseline_gap, 2),
                "difference": [round(gap, 2), round(gap_low, 2), round(gap_high, 2)],
                "spearman": round(placing.spearman, 3),
            }
    if PARENT in names:
        parent = score.paired_placing(scored, PARENT, BASELINE)
        if parent is not None:
            gap, gap_low, gap_high = parent.gap_difference
            payload["parent_placing"] = {
                "places": round(parent.gap, 2),
                "baseline": round(parent.baseline_gap, 2),
                "difference": [round(gap, 2), round(gap_low, 2), round(gap_high, 2)],
                "spearman": round(parent.spearman, 3),
            }
    paired = score.paired_placing(scored, MODEL, BASELINE)
    if paired is not None:
        gap, gap_low, gap_high = paired.gap_difference
        rho, rho_low, rho_high = paired.spearman_difference
        payload["placing"] = {
            "races": paired.races,
            "runners": paired.runners,
            "model": round(paired.gap, 2),
            "baseline": round(paired.baseline_gap, 2),
            "difference": [round(gap, 2), round(gap_low, 2), round(gap_high, 2)],
            "spearman": round(paired.spearman, 3),
            "baseline_spearman": round(paired.baseline_spearman, 3),
            "spearman_difference": [round(rho, 3), round(rho_low, 3), round(rho_high, 3)],
        }
    return payload


def distances(
    scored: Sequence[score.Scored], metres: Mapping[str, float], model: str = MODEL
) -> list[dict[str, Any]]:
    """The published model's error by race length, in minutes and as a share of a finish time.

    An average error in minutes is not one claim across distances: a minute and a half over
    5 km and a quarter of an hour over a marathon are the same model doing about equally well.
    The bands are `report.DISTANCE_BANDS`, so the page and the README cut the field the same way.
    """
    from finishline import report

    rows = [row for row in scored if row.model == model and row.predicted is not None]
    out: list[dict[str, Any]] = []
    for label, low, high in report.DISTANCE_BANDS:
        band = [row for row in rows if low <= metres.get(row.race_id, -1.0) < high]
        if not band:
            continue
        deep = [row for row in band if score.stratum_of(row.depth) == "4 or more"]
        everyone = score.summarise(band, model)
        experienced = score.summarise(deep, model) if deep else None
        out.append({
            "label": label,
            "runners": len(band),
            "median_min": _minutes(statistics.median(row.actual for row in band)),
            "mae_min": _minutes(everyone.mae_seconds),
            "mape": _round(everyone.mape),
            "deep_runners": len(deep),
            "deep_mae_min": None if experienced is None else _minutes(experienced.mae_seconds),
            "deep_mape": None if experienced is None else _round(experienced.mape),
            **spread(band),
        })
    return out


# Where a runner finished in their own race, as a share of the field, and what the page calls
# that. The words are a runner's own: nobody minds being told they are mid-pack, and "slow" is
# not a word this project puts on a stranger. The cut is quarter, half, quarter.
SPEED_GROUPS: tuple[tuple[str, str, str, float, float], ...] = (
    ("front", "Front of the field", "fastest quarter", 0.0, 0.25),
    ("mid", "Mid-pack", "middle half", 0.25, 0.75),
    ("back", "Later finishers", "last quarter", 0.75, 1.0001),
)


def field_times(data: Dataset) -> dict[str, list[float]]:
    """Every finisher's time in each race, sorted, so a runner can be placed in their own field.

    Over every finisher of the race, not only the runners a model answered for, because "the
    front quarter of the field" means the field that ran, not the subset with a history.
    """
    times: dict[str, list[float]] = {}
    for result in data.results:
        if result.finished and result.seconds:
            times.setdefault(result.race_id, []).append(float(result.seconds))
    for finishers in times.values():
        finishers.sort()
    return times


def _share_of_field(seconds: float, sorted_times: Sequence[float]) -> float:
    """Where this finish time sits in its field: 0.0 at the front, 1.0 at the back."""
    if not sorted_times:
        return -1.0
    return (bisect.bisect_left(sorted_times, seconds) + 0.5) / len(sorted_times)


def distance_groups(
    scored: Sequence[score.Scored],
    metres: Mapping[str, float],
    field: Mapping[str, Sequence[float]],
    model: str = MODEL,
    depth: str = "4 or more",
) -> dict[str, Any]:
    """The same error by race length, split by where a runner finishes in their own race.

    A five-minute miss is not the same claim for somebody racing the front of the field as for
    somebody out there twice as long: the minutes grow with the time on the road, and the share
    of a finish time is what compares them. Reported for runners with `depth` prior results, the
    same population as the page's headline figure, so switching between the two is not a change
    of subject.
    """
    from finishline import report

    rows = [
        row
        for row in scored
        if row.model == model
        and row.predicted is not None
        and score.stratum_of(row.depth) == depth
    ]
    groups: dict[str, Any] = {"depth": depth, "labels": {}, "rows": {}}
    for key, label, note, low, high in SPEED_GROUPS:
        groups["labels"][key] = f"{label} ({note})"
        picked = [
            row
            for row in rows
            if low <= _share_of_field(row.actual, field.get(row.race_id, ())) < high
        ]
        band_rows = []
        for band_label, band_low, band_high in report.DISTANCE_BANDS:
            band = [row for row in picked if band_low <= metres.get(row.race_id, -1.0) < band_high]
            if len(band) < MIN_IN_BAND:
                continue
            summary = score.summarise(band, model)
            band_rows.append({
                "label": band_label,
                "runners": len(band),
                "median_min": _minutes(statistics.median(row.actual for row in band)),
                "mae_min": _minutes(summary.mae_seconds),
                "mape": _round(summary.mape),
                **spread(band),
            })
        groups["rows"][key] = band_rows
    return groups


# Below this many runners a race-length row is a handful of people, not a measurement.
MIN_IN_BAND = 30


def _paired(scored: Sequence[score.Scored], model: str, other: str) -> list[dict[str, Any]]:
    """One model against another on the same runners, by history depth.

    `model_min` is the first model named, `other_min` the second, and `difference` is negative
    when the first is more accurate. Races are resampled for the interval, because two marginal
    error intervals overlap even where one model is consistently ahead (`score.paired_error`).
    """
    out = []
    for label, _low, _high in score.STRATA:
        same = [row for row in scored if score.stratum_of(row.depth) == label]
        both = score.paired_error(same, model, other)
        if both is None:
            continue
        out.append({
            "label": label,
            "runners": both.runners,
            "races": both.races,
            "model_min": _minutes(both.model_mae_seconds),
            "other_min": _minutes(both.other_mae_seconds),
            "difference": [round(value, 3) for value in both.difference],
        })
    return out


def _coverage(
    scored: Sequence[score.Scored], model: str, race_dates: Mapping[str, date]
) -> list[dict[str, Any]]:
    """How often one model's intervals held, raw and conformal, by depth and level."""
    rows = [row for row in scored if row.model == model]
    out = []
    for level in (0.80, 0.90):
        for held in coverage.summarise(split.rolling(rows, race_dates, level), level):
            out.append({
                "stratum": held.stratum,
                "level": level,
                "checked": held.rows - held.unadjusted,
                "raw": _round(held.raw),
                "raw_low": _round(held.raw_low),
                "raw_high": _round(held.raw_high),
                "conformal": _round(held.conformal),
                "conformal_low": _round(held.conformal_low),
                "conformal_high": _round(held.conformal_high),
                "raw_width_min": _minutes(held.raw_width),
                "conformal_width_min": _minutes(held.conformal_width),
            })
    return out


# How many of the busiest courses the chart names. A reader looking for the province's big
# races should find them without hovering fifty dots, and the Tely is not a live race here.
NAMED = 4


def course_list(fit: courses.Fit, live_courses: Mapping[str, str]) -> list[dict[str, Any]]:
    """Every measured course, hardest first, with the live races and the busiest ones marked."""
    ranked = sorted(fit.courses.values(), key=lambda c: -c.factor)
    busiest = {
        measured.course_id
        for measured in sorted(fit.courses.values(), key=lambda c: -c.finishes)[:NAMED]
    }
    return [
        {
            "course_id": measured.course_id,
            "name": course_name(measured.course_id),
            "finishes": measured.finishes,
            "editions": measured.editions,
            "factor": round(measured.factor, 4),
            "low": round(measured.low, 4),
            "high": round(measured.high, 4),
            "live": live_courses.get(measured.course_id),
            "named": measured.course_id in busiest,
        }
        for measured in ranked
    ]


def editions(
    data: Dataset, course_id: str, temperatures: Mapping[str, float]
) -> list[dict[str, Any]]:
    """Every edition of one course: its field, its middle and front, and its morning."""
    times: dict[str, list[float]] = {}
    for result in data.results:
        race = data.races[result.race_id]
        if race.course_id == course_id and result.finished and result.seconds:
            times.setdefault(result.race_id, []).append(result.seconds)
    out = []
    for race_id in sorted(times, key=lambda rid: data.races[rid].date):
        values = sorted(times[race_id])
        out.append({
            "date": data.races[race_id].date.isoformat(),
            "finishers": len(values),
            "median_s": round(statistics.median(values), 1),
            "fastest_s": round(values[0], 1),
            "temp_c": _round(temperatures.get(race_id), 1),
        })
    return out


def course_backtest(
    scored: Sequence[score.Scored],
    intervals: Sequence[split.Interval],
    data: Dataset,
    course_id: str,
) -> dict[str, Any] | None:
    """How the model did at this course's most recent edition in the backtest.

    Points are (predicted, actual, conformal 80% low, high) in seconds, sorted by actual time
    so the list's order carries nothing a results page does not.
    """
    races = sorted(
        {row.race_id for row in scored if data.races[row.race_id].course_id == course_id},
        key=lambda rid: data.races[rid].date,
    )
    if not races:
        return None
    race_id = races[-1]
    model = [row for row in scored if row.race_id == race_id and row.model == MODEL]
    baseline = {
        row.runner_id: row
        for row in scored
        if row.race_id == race_id and row.model == BASELINE and row.predicted is not None
    }
    if not model:
        return None
    bounds = {
        (item.row.race_id, item.row.runner_id): item
        for item in intervals
        if item.row.race_id == race_id
    }
    points: list[tuple[int, int, int | None, int | None, int]] = []
    for row in sorted(model, key=lambda r: r.actual):
        if row.predicted is None:
            continue
        found = bounds.get((row.race_id, row.runner_id))
        low = found.low if found is not None and found.adjusted else None
        high = found.high if found is not None and found.adjusted else None
        points.append((
            round(row.predicted),
            round(row.actual),
            None if low is None else round(low),
            None if high is None or not math.isfinite(high) else round(high),
            min(row.depth, 4),
        ))
    if not points:
        return None
    both = [row for row in model if row.runner_id in baseline and row.predicted is not None]
    ranged = [
        (actual, low, high)
        for _predicted, actual, low, high, _depth in points
        if low is not None and high is not None
    ]
    held = sum(1 for actual, low, high in ranged if low <= actual <= high)
    race = data.races[race_id]
    return {
        "race": course_name(course_id),
        "date": race.date.isoformat(),
        "runners": len(points),
        "mae_min": _minutes(statistics.mean(abs(p[0] - p[1]) for p in points)),
        "coverage80": _round(held / len(ranged) if ranged else None),
        "paired": len(both),
        "paired_model_min": _minutes(
            statistics.mean(abs((r.predicted or 0) - r.actual) for r in both) if both else None
        ),
        "paired_baseline_min": _minutes(
            statistics.mean(abs((baseline[r.runner_id].predicted or 0) - r.actual) for r in both)
            if both
            else None
        ),
        "points": [list(point) for point in points],
    }


def entrants(links: Sequence[Link], as_of: str) -> dict[str, Any]:
    """Who is on the list, by how much history the archive has for them. Counts only."""
    depth = {label: 0 for label, _low, _high in score.STRATA}
    refused = 0
    for item in links:
        if item.runner is None:
            if item.status.value == "new":
                depth["0"] += 1
            else:
                refused += 1
            continue
        depth[score.stratum_of(item.runner.history_depth)] += 1
    return {"as_of": as_of, "listed": len(links), "depth": depth, "refused": refused}


def temperatures(rows: Sequence[conditions.Observation]) -> dict[str, float]:
    return {row.race_id: row.temp_c for row in rows}


def write(path: Path, payload: Mapping[str, Any]) -> None:
    """One file, sorted and compact, so a rerun that changes nothing changes no bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
