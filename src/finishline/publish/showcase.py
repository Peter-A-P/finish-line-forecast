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

MODEL = "hierarchical"
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
        payload["challenger_paired"] = []
        for label, _low, _high in score.STRATA:
            same = [row for row in scored if score.stratum_of(row.depth) == label]
            both = score.paired_error(same, CHALLENGER, MODEL)
            if both is None:
                continue
            payload["challenger_paired"].append({
                "label": label,
                "runners": both.runners,
                "races": both.races,
                "challenger_min": _minutes(both.model_mae_seconds),
                "model_min": _minutes(both.other_mae_seconds),
                "difference": [round(value, 3) for value in both.difference],
            })
        placing = score.paired_placing(scored, CHALLENGER, BASELINE)
        if placing is not None:
            gap, gap_low, gap_high = placing.gap_difference
            payload["challenger_placing"] = {
                "places": round(placing.gap, 2),
                "baseline": round(placing.baseline_gap, 2),
                "difference": [round(gap, 2), round(gap_low, 2), round(gap_high, 2)],
                "spearman": round(placing.spearman, 3),
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


def course_list(fit: courses.Fit, live_courses: Mapping[str, str]) -> list[dict[str, Any]]:
    """Every measured course, hardest first, with the live races marked."""
    ranked = sorted(fit.courses.values(), key=lambda c: -c.factor)
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
