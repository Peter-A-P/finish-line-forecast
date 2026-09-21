"""Race-level bias against the felt-heat cost, for the no-weather, linear and felt-heat runs.

Same x for every run (the felt-heat cost at whole-archive posterior medians), so the slopes
compare the runs, not their own ideas of the weather.
"""
import json, math, pickle
from pathlib import Path
import numpy as np
from finishline.cli import _edition_weather
from finishline.models import weather as wm

data = pickle.loads(Path("scratch/dataset.pkl").read_bytes())
actual = {}
for runner in data.resolved:
    for r in runner.results:
        if r.finished and r.seconds:
            actual[(runner.runner_id, r.race_id)] = r.seconds
runs = {"old no-weather": "f00ac713ffe00e9086826bcb", "linear weather": "46dec5b3fa4608bdb1236057",
        "felt heat": "effeeda2ba8ede9b41973321", "new no-weather": "8b27fb776b630e110b9eb08e"}
conditions, _ = _edition_weather(data)
params = np.array([[0.0005, 0.0038, 0.00027, -0.00006, 2.05]])
for label, key in runs.items():
    per = {}
    for f in Path("data/cache/backtest/blocks", key).glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines()[1:]:
            row = json.loads(line)
            a = actual.get((row["runner_id"], row["race_id"]))
            if a and row["quantiles"]:
                per.setdefault(row["race_id"], []).append(math.log(a / row["quantiles"][3]))
    xs, ys, years = [], [], []
    for race, v in per.items():
        c = conditions.get(race)
        if c is None or c[0] == 0.0:
            continue
        xs.append(100 * float(wm.effect(np.array([c]), params)[0]))
        ys.append(100 * float(np.median(v)))
        years.append(data.races[race].date.year)
    xs, ys, years = map(np.array, (xs, ys, years))
    for with_year in (False, True):
        x = np.column_stack([np.ones(len(xs)), xs] + ([years - 2025.0] if with_year else []))
        beta, *_ = np.linalg.lstsq(x, ys, rcond=None)
        resid = ys - x @ beta
        se = math.sqrt(resid @ resid / (len(ys) - x.shape[1]) * np.linalg.inv(x.T @ x)[1, 1])
        print(f"{label:15s} races {len(ys)} {'+year' if with_year else '     '} slope {beta[1]:+.2f} +/- {1.96*se:.2f}")
    for race in ("20250907-USR-half-marathon", "20250907-USR-marathon", "20260628-tely10-results", "20250622-tely10-results"):
        if race in per:
            print(f"    {race}: {100*(math.exp(np.median(per[race]))-1):+.2f}%")
