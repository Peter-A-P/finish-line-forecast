"""How much does the sun add, measured how, and where does heat start to cost? Two tests.

A. EDITIONS. Each edition's effect against its own course's long-run level (the conditions
   layer's response), 227 editions near the airport, weighted by finishers.

B. THE SAME RUNNERS. Consecutive editions of a course, and the median change in log time
   among the runners who ran both: the edition difference with the field held fixed, which
   is what a hot morning does to a given person rather than to whoever turned up. Regressed
   on the change in each covariate, with the gap in years for ageing and form.

Candidates: the sun as cloud cover (clear fraction), global radiation / 800 W/m2, or direct
radiation / 800 (Overload's measure); a boost of 0 to 12 C for a full sun; a heat threshold
of 6 to 15.6 C of felt temperature. Heat is scaled by log(distance / 5 km) as in the model.

Scored leave-one-year-out, because weather within a year is correlated and the whole point
of item 30 is that a year can masquerade as weather. Differences between candidates carry a
95% interval from resampling years.
"""

from __future__ import annotations

import json
import math
import pickle
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np

from finishline.cli import _conditions_rows
from finishline.starts import load as load_starts
from finishline.history import History
from finishline.ingest.openmeteo import window
from finishline.models import courses as models_courses
from finishline.models.conditions import NEUTRAL_TEMP_C, NEUTRAL_WIND_KMH

SKY = Path("scratch/sky")
BOOSTS = (0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.3, 10.0, 12.0)
THRESHOLDS = (6.0, 8.0, 10.0, 12.0, 14.0, 15.6)
MEASURES = ("cloud", "global", "direct")


def sky_table(year: int) -> dict[tuple[date, int], tuple[float, float, float]]:
    path = SKY / f"{year}.json"
    if not path.exists():
        return {}
    block = json.loads(path.read_text(encoding="utf-8"))["hourly"]
    out = {}
    for i, stamp in enumerate(block["time"]):
        when = datetime.fromisoformat(stamp)
        values = (block["cloud_cover"][i], block["shortwave_radiation"][i], block["direct_radiation"][i])
        if None not in values:
            out[(when.date(), when.hour)] = tuple(float(v) for v in values)
    return out


data = pickle.loads(Path("scratch/dataset.pkl").read_bytes())
history = History.before(date.today(), data.races, data.resolved)
fitted = models_courses.fit(history, data.races, draws=1)
rows, _ = _conditions_rows(data, fitted)
tables = {year: sky_table(year) for year in range(2008, 2027)}
begins = load_starts()

editions = {}
for row in rows:
    race = data.races[row.race_id]
    first, last = window(race.distance_m, begins.hour(race), wall_clock=True)
    hours = [
        tables[race.date.year][(race.date, h)]
        for h in range(first, last + 1)
        if (race.date, h) in tables.get(race.date.year, {})
    ]
    if not hours:
        continue
    h = np.array(hours)
    editions[row.race_id] = {
        "course": row.course_id,
        "date": race.date,
        "effect": row.effect,
        "n": row.finishers,
        "temp": row.temp_c,
        "wind": row.wind_kmh - NEUTRAL_WIND_KMH,
        "tail": row.tailwind_kmh or 0.0,
        "logd": math.log(row.distance_m / 5_000.0),
        "cloud": 1.0 - float(h[:, 0].mean()) / 100.0,
        "global": min(1.0, float(h[:, 1].mean()) / 800.0),
        "direct": min(1.0, float(h[:, 2].mean()) / 800.0),
    }
ids = sorted(editions)
print(f"test A: {len(ids)} editions with an observation and a sky record")

# Test B: consecutive editions of one course, same runners.
seconds: dict[str, dict[str, float]] = defaultdict(dict)
for runner in data.resolved:
    if runner.ambiguous:
        continue
    for result in runner.results:
        if result.finished and result.seconds:
            seconds[result.race_id][runner.runner_id] = result.seconds
by_course: dict[str, list[str]] = defaultdict(list)
for race_id in ids:
    by_course[editions[race_id]["course"]].append(race_id)
pairs = []
for course, members in by_course.items():
    members.sort(key=lambda r: editions[r]["date"])
    for older, newer in zip(members, members[1:]):
        gap = (editions[newer]["date"] - editions[older]["date"]).days / 365.25
        shared = set(seconds[older]) & set(seconds[newer])
        if gap > 2.5 or len(shared) < 30:
            continue
        change = float(np.median([math.log(seconds[newer][r] / seconds[older][r]) for r in shared]))
        pairs.append((older, newer, change, len(shared), gap))
print(f"test B: {len(pairs)} consecutive edition pairs, {sum(p[3] for p in pairs):,} runner pairs")


def heat(e: dict, measure: str, boost: float, threshold: float) -> float:
    return max(0.0, e["temp"] + boost * e[measure] - threshold)


def design_a(measure: str | None, boost: float, threshold: float) -> np.ndarray:
    cols = []
    for r in ids:
        e = editions[r]
        if measure is None:  # the old linear model
            t = e["temp"] - NEUTRAL_TEMP_C
            cols.append([1.0, t, t * e["logd"], e["wind"], e["tail"]])
        else:
            h = heat(e, measure, boost, threshold)
            cols.append([1.0, h, h * e["logd"], e["wind"], e["tail"]])
    return np.array(cols)


def design_b(measure: str | None, boost: float, threshold: float) -> np.ndarray:
    cols = []
    for older, newer, _, _, gap in pairs:
        a, b = editions[older], editions[newer]
        if measure is None:
            ta, tb = a["temp"] - NEUTRAL_TEMP_C, b["temp"] - NEUTRAL_TEMP_C
            ha, hb = ta, tb
        else:
            ha, hb = heat(a, measure, boost, threshold), heat(b, measure, boost, threshold)
        cols.append([1.0, gap, hb - ha, (hb - ha) * b["logd"], b["wind"] - a["wind"], b["tail"] - a["tail"]])
    return np.array(cols)


y_a = np.array([editions[r]["effect"] for r in ids])
w_a = np.sqrt(np.array([editions[r]["n"] for r in ids], dtype=float))
year_a = np.array([editions[r]["date"].year for r in ids])
y_b = np.array([p[2] for p in pairs])
w_b = np.sqrt(np.array([p[3] for p in pairs], dtype=float))
year_b = np.array([editions[p[1]]["date"].year for p in pairs])


def loyo(x: np.ndarray, y: np.ndarray, w: np.ndarray, years: np.ndarray) -> np.ndarray:
    """Out-of-sample residuals, each year predicted from all the others."""
    out = np.zeros(len(y))
    for year in np.unique(years):
        test = years == year
        train = ~test
        beta, *_ = np.linalg.lstsq(x[train] * w[train, None], y[train] * w[train], rcond=None)
        out[test] = y[test] - x[test] @ beta
    return out


def r2(resid: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    total = y - np.average(y, weights=w**2)
    return 1.0 - float((w**2 * resid**2).sum() / (w**2 * total**2).sum())


results: dict[str, dict[tuple, tuple[float, np.ndarray]]] = {"A": {}, "B": {}}
for test, design, y, w, years in (
    ("A", design_a, y_a, w_a, year_a),
    ("B", design_b, y_b, w_b, year_b),
):
    x = design(None, 0.0, 0.0)
    resid = loyo(x, y, w, years)
    results[test][("linear", 0.0, 0.0)] = (r2(resid, y, w), resid)
    for measure in MEASURES:
        for boost in BOOSTS:
            for threshold in THRESHOLDS:
                x = design(measure, boost, threshold)
                resid = loyo(x, y, w, years)
                results[test][(measure, boost, threshold)] = (r2(resid, y, w), resid)

rng = np.random.default_rng(20261018)


def compare(test: str, one: tuple, other: tuple) -> str:
    y, w, years = (y_a, w_a, year_a) if test == "A" else (y_b, w_b, year_b)
    ra, rb = results[test][one][1], results[test][other][1]
    uniq = np.unique(years)
    stats = []
    for _ in range(2000):
        pick = rng.choice(uniq, len(uniq), replace=True)
        sel = np.concatenate([np.where(years == yr)[0] for yr in pick])
        stats.append(r2(ra[sel], y[sel], w[sel]) - r2(rb[sel], y[sel], w[sel]))
    low, high = np.quantile(stats, [0.025, 0.975])
    diff = results[test][one][0] - results[test][other][0]
    return f"{diff:+.3f} [{low:+.3f}, {high:+.3f}]"


def label(key: tuple) -> str:
    measure, boost, threshold = key
    if measure == "linear":
        return "linear temperature (old model)"
    return f"{measure:6s} sun +{boost:4.1f} C, knee {threshold:4.1f} C"


for test, title in (("A", "EDITIONS vs their course"), ("B", "SAME RUNNERS, consecutive editions")):
    table = results[test]
    print(f"\n=== test {test}: {title}, out-of-sample R2, leave one year out ===")
    print(f"  {label(('linear', 0, 0)):36s} {table[('linear', 0.0, 0.0)][0]:+.3f}")
    print("  best twelve:")
    for key, (score, _) in sorted(table.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"    {label(key):36s} {score:+.3f}")
    print("  best threshold for each boost, by sun measure (how flat is it?):")
    header = "    boost " + "".join(f"{m:>18s}" for m in MEASURES)
    print(header)
    for boost in BOOSTS:
        cells = []
        for measure in MEASURES:
            best = max(
                ((table[(measure, boost, t)][0], t) for t in THRESHOLDS), key=lambda s: s[0]
            )
            cells.append(f"{best[0]:+.3f} @{best[1]:4.1f}")
        print(f"    {boost:5.1f} " + "".join(f"{c:>18s}" for c in cells))

    best_key = max(table, key=lambda k: table[k][0])
    print("  differences, with a 95% interval from resampling years:")
    for key in (
        ("cloud", 3.0, 10.0),
        ("direct", 8.3, 12.0),
        ("direct", 8.3, 15.6),
        ("direct", 0.0, 10.0),
        ("linear", 0.0, 0.0),
    ):
        if key != best_key:
            print(f"    best ({label(best_key)}) minus {label(key):36s} {compare(test, best_key, key)}")
