"""Feature and hyperparameter search for the LightGBM challenger, on 2022-2023 only.

The 2024+ backtest is the test set and is never looked at here. Each tuning block is a
half-year; its races are predicted from history strictly before the block, exactly as the
backtest does, and scored on the median (mean absolute log error), by history depth.

    python experiments/tune_gbm.py build      # feature tables per block, cached
    python experiments/tune_gbm.py search     # feature sets and a random search over parameters
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np

from finishline import cli
from finishline.history import History
from finishline.models import courses, gbm

OUT = Path("scratch/tune")
BLOCKS = [date(2022, 1, 1), date(2022, 7, 1), date(2023, 1, 1), date(2023, 7, 1), date(2024, 1, 1)]
HALF_LIFE_DAYS = 365.0

EXTRA = (
    "adj_last", "adj_best_recent", "adj_mean_last3", "adj_median", "adj_ewm", "adj_std",
    "adj_trend", "recent_count", "course_last_adj", "course_count", "near_distance_adj",
    "best_ever_adj", "last_gap_adj",
)
# A second batch: the shapes the model knows about and trees have to discover, plus the
# personal-best and consistency features a coach would look at.
EXTRA2 = (
    "felt_heat", "felt_heat_x_logd", "best_ever", "pb_at_distance", "gap_to_pb",
    "consistency", "distinct_courses", "improvement_12m", "races_per_year", "ewm_raw",
)
ALL = gbm.FEATURES + EXTRA + EXTRA2


def adjusted(race, seconds, fit):
    raw = gbm.log_ratio(race, seconds)
    if race.race_id in fit.editions:
        return raw - math.log1p(fit.editions[race.race_id])
    factor = fit.prior_for(race.course_id)
    return raw - math.log1p(factor) if factor is not None else raw


def extra2(prior, target, conditions):
    earlier = [(r, x) for r, x in prior if r.date < target.date and x.finished and x.seconds]
    nan = math.nan
    heat = nan
    if conditions is not None and conditions[0]:
        felt = conditions[1] + 2.1 * conditions[2]
        heat = max(0.0, felt - 12.0)
    logd = math.log(target.distance_m / 5_000.0)
    if not earlier:
        return [heat, heat * logd] + [nan] * (len(EXTRA2) - 2)
    ratios = np.array([gbm.log_ratio(r, float(x.seconds)) for r, x in earlier])
    ages = np.array([(target.date - r.date).days for r, _ in earlier], dtype=float)
    near = [
        value
        for (r, _), value in zip(earlier, ratios, strict=True)
        if abs(math.log(target.distance_m / r.distance_m)) < 0.2
    ]
    last_year = ratios[ages <= 365]
    year_before = ratios[(ages > 365) & (ages <= 730)]
    span = max((ages.max() - ages.min()) / 365.25, 0.5)
    return [
        heat,
        heat * logd,
        float(ratios.min()),
        float(min(near)) if near else nan,
        float(ratios[-1] - ratios.min()),
        float(ratios.std()) if len(ratios) >= 2 else nan,
        float(len({r.course_id for r, _ in earlier})),
        float(last_year.mean() - year_before.mean()) if last_year.size and year_before.size else nan,
        float(len(ratios) / span),
        float(np.average(ratios, weights=0.5 ** (ages / HALF_LIFE_DAYS))),
    ]


def extra(prior, target, fit):
    earlier = [(r, x) for r, x in prior if r.date < target.date and x.finished and x.seconds]
    nan = math.nan
    if not earlier:
        row = [nan] * len(EXTRA)
        row[EXTRA.index("recent_count")] = 0.0
        row[EXTRA.index("course_count")] = 0.0
        return row
    adj = np.array([adjusted(r, float(x.seconds), fit) for r, x in earlier])
    ages = np.array([(target.date - r.date).days for r, _ in earlier], dtype=float)
    recent = adj[ages <= gbm.RECENT_DAYS]
    weights = 0.5 ** (ages / HALF_LIFE_DAYS)
    trend = nan
    if len(adj) >= 3:
        years = (ages.max() - ages) / 365.25
        if years.max() - years.min() >= 0.5:
            trend = float(np.polyfit(years, adj, 1)[0])
    same = [a for (r, _), a in zip(earlier, adj, strict=True) if r.course_id == target.course_id]
    near = [
        a for (r, _), a in zip(earlier, adj, strict=True)
        if abs(math.log(target.distance_m / r.distance_m)) < 0.35
    ]
    return [
        float(adj[-1]),
        float(recent.min()) if recent.size else nan,
        float(adj[-3:].mean()),
        float(np.median(adj)),
        float(np.average(adj, weights=weights)),
        float(adj.std()) if len(adj) >= 2 else nan,
        trend,
        float((ages <= 365).sum()),
        same[-1] if same else nan,
        float(len(same)),
        float(np.mean(near[-3:])) if near else nan,
        float(adj.min()),
        float(adj[-1] - adj[-2]) if len(adj) >= 2 else nan,
    ]


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = cli._dataset(cli.FIRST_YEAR, cli.LAST_YEAR)
    cov, _ = cli._edition_weather(data)
    runners = [r for r in data.resolved]
    for start, end in zip(BLOCKS, BLOCKS[1:], strict=False):
        t = time.time()
        cut = History.before(start, data.races, runners)
        fit = courses.fit(cut, cut.races, draws=1)
        rows, ys, depth = [], [], []
        for runner in cut.runners.values():
            timeline = gbm.history_rows(runner, cut.races)
            for i, (race, res) in enumerate(timeline):
                if race.date.year < gbm.FIRST_TRAINING_YEAR or not res.seconds:
                    continue
                prior = timeline[:i]
                rows.append(
                    gbm.features(prior, race, runner.sex, fit.prior_for(race.course_id),
                                 cov.get(race.race_id))
                    + extra(prior, race, fit)
                    + extra2(prior, race, cov.get(race.race_id))
                )
                ys.append(gbm.log_ratio(race, float(res.seconds)))
                depth.append(float(race.date.year))
        test, ty, tdepth, trace = [], [], [], []
        for runner in runners:
            timeline = gbm.history_rows(runner, data.races)
            for i, (race, res) in enumerate(timeline):
                if not (start <= race.date < end) or not res.seconds:
                    continue
                prior = [(r, x) for r, x in timeline[:i] if r.date < race.date]
                test.append(
                    gbm.features(prior, race, runner.sex, fit.prior_for(race.course_id),
                                 cov.get(race.race_id))
                    + extra(prior, race, fit)
                    + extra2(prior, race, cov.get(race.race_id))
                )
                ty.append(gbm.log_ratio(race, float(res.seconds)))
                tdepth.append(len(prior))
                trace.append(race.race_id)
        np.savez_compressed(
            OUT / f"{start}.npz", x=np.array(rows), y=np.array(ys), tx=np.array(test),
            ty=np.array(ty), tdepth=np.array(tdepth), trace=np.array(trace),
            year=np.array(depth),
        )
        print(start, len(ys), "train", len(ty), "test", f"{time.time() - t:.0f}s", flush=True)


def load():
    return [np.load(OUT / f"{start}.npz") for start in BLOCKS[:-1]]


def score(blocks, columns, params, rounds):
    index = [ALL.index(c) for c in columns]
    errs, depths = [], []
    for b in blocks:
        data = lgb.Dataset(b["x"][:, index], label=b["y"], free_raw_data=False)
        booster = lgb.train({**params, "alpha": 0.5}, data, num_boost_round=rounds)
        pred = booster.predict(b["tx"][:, index])
        errs.append(np.abs(pred - b["ty"]))
        depths.append(b["tdepth"])
    e, d = np.concatenate(errs), np.concatenate(depths)
    strata = {
        "0": e[d == 0].mean(), "1": e[d == 1].mean(), "2-3": e[(d >= 2) & (d <= 3)].mean(),
        "4+": e[d >= 4].mean(),
    }
    return float(e.mean()), float(e[d >= 1].mean()), {k: round(float(v) * 100, 3) for k, v in strata.items()}


BASE = {**gbm.PARAMETERS, "num_threads": 8}

SETS = {
    "v1": gbm.FEATURES,
    "v1+adjusted": gbm.FEATURES + EXTRA,
    "adjusted-only-form": tuple(
        f for f in gbm.FEATURES if f not in ("last", "best_recent", "mean_last3", "trend_per_year")
    ) + EXTRA,
}


def search() -> None:
    blocks = load()
    results = []
    for name, cols in SETS.items():
        overall, known, strata = score(blocks, cols, BASE, gbm.ROUNDS)
        print(f"{name:22} all {overall*100:.3f} known {known*100:.3f} {strata}", flush=True)
        results.append({"set": name, "params": "default", "all": overall, "known": known, "strata": strata})
    best_set = min(results, key=lambda r: r["all"])["set"]
    cols = SETS[best_set]
    rng = np.random.default_rng(7)
    for trial in range(40):
        params = {
            **BASE,
            "learning_rate": float(rng.choice([0.02, 0.03, 0.05, 0.08])),
            "num_leaves": int(rng.choice([15, 31, 63, 127])),
            "min_data_in_leaf": int(rng.choice([20, 50, 100, 200, 400])),
            "feature_fraction": float(rng.choice([0.6, 0.75, 0.9, 1.0])),
            "bagging_fraction": float(rng.choice([0.6, 0.8, 1.0])),
            "lambda_l2": float(rng.choice([0.0, 1.0, 5.0, 20.0])),
            "max_bin": int(rng.choice([63, 255])),
        }
        rounds = int(rng.choice([200, 400, 800, 1200]))
        overall, known, strata = score(blocks, cols, params, rounds)
        keep = {k: params[k] for k in ("learning_rate", "num_leaves", "min_data_in_leaf",
                                       "feature_fraction", "bagging_fraction", "lambda_l2", "max_bin")}
        print(f"trial {trial:2} all {overall*100:.3f} known {known*100:.3f} {strata} {keep} rounds={rounds}", flush=True)
        results.append({"set": best_set, "params": keep, "rounds": rounds, "all": overall, "known": known, "strata": strata})
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    best = min(results, key=lambda r: r["all"])
    print("BEST", json.dumps(best))




def offsets(x, y):
    """Where the trees start: the runner's own last result, or their group's middle."""
    last = x[:, ALL.index("last")]
    female = x[:, ALL.index("sex_female")]
    base = np.nanmedian(y) if y is not None else 0.0
    if y is not None:
        by_sex = {s: float(np.median(y[(female == s) & np.isnan(last)])) if
                  ((female == s) & np.isnan(last)).sum() > 50 else base for s in (0.0, 1.0)}
        offsets.by_sex = by_sex
        offsets.base = float(base)
    by_sex = getattr(offsets, "by_sex", {0.0: 0.0, 1.0: 0.0})
    fallback = np.where(female == 1.0, by_sex.get(1.0, offsets.base), by_sex.get(0.0, offsets.base))
    return np.where(np.isnan(last), fallback, last)


def score2(blocks, columns, params, rounds, *, offset=False):
    index = [ALL.index(c) for c in columns]
    errs, depths = [], []
    for b in blocks:
        init = offsets(b["x"], b["y"]) if offset else None
        data = lgb.Dataset(b["x"][:, index], label=b["y"], init_score=init, free_raw_data=False)
        booster = lgb.train({**params, "alpha": 0.5}, data, num_boost_round=rounds)
        pred = booster.predict(b["tx"][:, index])
        if offset:
            pred = pred + offsets(b["tx"], None)
        errs.append(np.abs(pred - b["ty"]))
        depths.append(b["tdepth"])
    e, d = np.concatenate(errs), np.concatenate(depths)
    strata = {"0": e[d == 0].mean(), "1": e[d == 1].mean(),
              "2-3": e[(d >= 2) & (d <= 3)].mean(), "4+": e[d >= 4].mean()}
    return float(e.mean()), float(e[d >= 1].mean()), {k: round(float(v) * 100, 3) for k, v in strata.items()}


BEST_PARAMS = {
    **BASE, "learning_rate": 0.03, "num_leaves": 15, "min_data_in_leaf": 20,
    "feature_fraction": 0.9, "bagging_fraction": 1.0, "lambda_l2": 1.0, "max_bin": 255,
}


def ideas() -> None:
    blocks = load()
    trials = [
        ("default, v1", gbm.FEATURES, BASE, gbm.ROUNDS, False),
        ("tuned, v1", gbm.FEATURES, BEST_PARAMS, 1200, False),
        ("tuned + offset", gbm.FEATURES, BEST_PARAMS, 1200, True),
        ("default + offset", gbm.FEATURES, BASE, gbm.ROUNDS, True),
        ("tuned + offset + adjusted", ALL, BEST_PARAMS, 1200, True),
        ("linear tree", gbm.FEATURES, {**BEST_PARAMS, "linear_tree": True, "lambda_l1": 0.0}, 600, False),
        ("linear tree + offset", gbm.FEATURES, {**BEST_PARAMS, "linear_tree": True}, 600, True),
    ]
    for name, cols, params, rounds, offset in trials:
        t = time.time()
        overall, known, strata = score2(blocks, cols, params, rounds, offset=offset)
        print(f"{name:28} all {overall*100:.3f} known {known*100:.3f} {strata} {time.time()-t:.0f}s", flush=True)




def score3(blocks, columns, params, rounds, *, half_life=None):
    """As the backtest scores it, with optional exponential weights on the training rows."""
    index = [ALL.index(c) for c in columns]
    errs, depths, races = [], [], []
    for b in blocks:
        weight = None
        if half_life:
            age = b["year"].max() - b["year"]
            weight = 0.5 ** (age / half_life)
        data = lgb.Dataset(b["x"][:, index], label=b["y"], weight=weight, free_raw_data=False)
        booster = lgb.train({**params, "alpha": 0.5}, data, num_boost_round=rounds)
        errs.append(np.abs(booster.predict(b["tx"][:, index]) - b["ty"]))
        depths.append(b["tdepth"])
        races.append(b["trace"])
    return np.concatenate(errs), np.concatenate(depths), np.concatenate(races)


def report(name, e, d, t0=None):
    strata = {"0": e[d == 0].mean(), "1": e[d == 1].mean(),
              "2-3": e[(d >= 2) & (d <= 3)].mean(), "4+": e[d >= 4].mean()}
    print(f"{name:34} all {e.mean()*100:.3f} known {e[d>=1].mean()*100:.3f} "
          f"{ {k: round(float(v)*100, 3) for k, v in strata.items()} }"
          f"{'' if t0 is None else f' {time.time()-t0:.0f}s'}", flush=True)


def paired(a, b, races, seed=20261018, draws=2000):
    """Mean difference a - b with a 95% interval resampling races, as the README does."""
    names = sorted(set(races.tolist()))
    index = {name: i for i, name in enumerate(names)}
    ix = np.array([index[r] for r in races])
    diff = a - b
    sums = np.bincount(ix, weights=diff, minlength=len(names))
    counts = np.bincount(ix, minlength=len(names)).astype(float)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(names), size=(draws, len(names)))
    resampled = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    low, high = np.quantile(resampled, [0.025, 0.975])
    return diff.mean() * 100, low * 100, high * 100


def batch2() -> None:
    blocks = load()
    base_e, d, races = score3(blocks, gbm.FEATURES, BASE, gbm.ROUNDS)
    report("default, v1", base_e, d)
    runs = {
        "tuned, v1": (gbm.FEATURES, BEST_PARAMS, 1200, None),
        "tuned, v1+batch2": (gbm.FEATURES + EXTRA2, BEST_PARAMS, 1200, None),
        "tuned, v1+batch2, weights 3y": (gbm.FEATURES + EXTRA2, BEST_PARAMS, 1200, 3.0),
        "tuned, v1+batch2, weights 6y": (gbm.FEATURES + EXTRA2, BEST_PARAMS, 1200, 6.0),
        "tuned, v1, weights 3y": (gbm.FEATURES, BEST_PARAMS, 1200, 3.0),
        "tuned, all features": (ALL, BEST_PARAMS, 1200, None),
    }
    for name, (cols, params, rounds, half) in runs.items():
        t0 = time.time()
        e, d2, _ = score3(blocks, cols, params, rounds, half_life=half)
        report(name, e, d2, t0)
        point, low, high = paired(e, base_e, races)
        print(f"{'':34} against default: {point:+.3f} ({low:+.3f} to {high:+.3f}) points", flush=True)




def score4(blocks, columns, params, rounds, *, min_year=None, seeds=1):
    index = [ALL.index(c) for c in columns]
    errs, depths, races = [], [], []
    for b in blocks:
        keep = b["year"] >= min_year if min_year else np.ones(len(b["y"]), dtype=bool)
        preds = []
        for seed in range(seeds):
            data = lgb.Dataset(b["x"][keep][:, index], label=b["y"][keep], free_raw_data=False)
            booster = lgb.train(
                {**params, "alpha": 0.5, "seed": params.get("seed", 1) + seed * 101,
                 "bagging_seed": 7 + seed, "feature_fraction_seed": 13 + seed},
                data, num_boost_round=rounds,
            )
            preds.append(booster.predict(b["tx"][:, index]))
        errs.append(np.abs(np.mean(preds, axis=0) - b["ty"]))
        depths.append(b["tdepth"])
        races.append(b["trace"])
    return np.concatenate(errs), np.concatenate(depths), np.concatenate(races)


def batch3() -> None:
    blocks = load()
    base_e, d, races = score3(blocks, gbm.FEATURES, BASE, gbm.ROUNDS)
    report("default, v1", base_e, d)
    cols = gbm.FEATURES + EXTRA2
    runs = {
        "tuned+batch2": dict(),
        "tuned+batch2, rows 2014+": dict(min_year=2014),
        "tuned+batch2, rows 2016+": dict(min_year=2016),
        "tuned+batch2, 3 seeds": dict(seeds=3),
        "tuned+batch2, 5 seeds": dict(seeds=5),
    }
    for name, kwargs in runs.items():
        t0 = time.time()
        e, d2, _ = score4(blocks, cols, BEST_PARAMS, 1200, **kwargs)
        report(name, e, d2, t0)
        print(f"{'':34} against default: {paired(e, base_e, races)}", flush=True)
    for objective in ("regression_l1", "huber"):
        t0 = time.time()
        params = {**BEST_PARAMS, "objective": objective}
        e, d2, _ = score4(blocks, cols, params, 1200)
        report(f"tuned+batch2, {objective}", e, d2, t0)
        print(f"{'':34} against default: {paired(e, base_e, races)}", flush=True)


if __name__ == "__main__":
    {"build": build, "search": search, "ideas": ideas, "batch2": batch2, "batch3": batch3}[sys.argv[1]]()
