"""Choose the blend weight on 2022-2023, where the 2024+ backtest cannot see it.

Both models are run over the same tuning window the challenger's features and parameters were
chosen on (PLAN.md 13 item 34), with the same quarterly block scheme as the real backtest, and
the weight is read off there. The 2024+ rows are then scored once with that weight.

    python experiments/blend_weight.py run     # ~3 hours: 8 hierarchical fits and 8 LightGBM fits
    python experiments/blend_weight.py choose  # the weight, and what it buys, on the window

⚠️ It writes to scratch/, never to data/cache/backtest/, so the saved 2024+ runs that the
Turkey Tea freeze depends on are untouched.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

from finishline import cli
from finishline.backtest import run, saved, score
from finishline.history import History
from finishline.models import gbm
from finishline.models import hierarchical as hm

OUT = Path("scratch/tuning-window")
ROWS = OUT / "rows.jsonl"
KEY = "tuning-window-2022-2023"
FIRST, LAST = 2022, 2023


def go() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = cli._dataset(cli.FIRST_YEAR, LAST)
    weather, missing = cli._edition_weather(data)
    print(f"{len(data.races)} races to {LAST}, {len(weather)} with observed weather ({missing} without)", flush=True)

    def fitter(history: History) -> hm.Posterior | None:
        print(f"  sampling on history before {history.origin} ...", flush=True)
        started = time.time()
        posterior = hm.fit(history, draws=300, tune=400, chains=4, weather=weather)
        print(f"    {time.time() - started:.0f}s", flush=True)
        return posterior

    models = [
        hm.Hierarchical(
            months=3,
            fitter=fitter,
            weather=weather,
            checkpoint=saved.BlockStore(OUT / "blocks", KEY),
        ),
        gbm.Challenger(months=3, conditions=weather),
    ]
    rows = run.run(data.races, data.resolved, models, scored_from=FIRST)
    models[0].finish()
    saved.save(ROWS, KEY, rows)
    print(f"{len(rows):,} rows over {len({r.race_id for r in rows})} races", flush=True)


def in_window(race_id: str) -> bool:
    """Is this race inside the tuning window?

    `cli._dataset(FIRST_YEAR, LAST)` bounds the NLAA catalogue by year, but the external and
    Athletics NorthEAST results are read whole, so the run also scored five 2026 races (the
    2026 Tely alone is a third of all the rows). Those are test-set races. A weight read with
    them in it would be a weight partly chosen on the races the published numbers come from,
    which is the thing this script exists to avoid.
    """
    return FIRST <= int(race_id[:4]) <= LAST


def choose() -> None:
    rows = saved.load(ROWS, KEY)
    if rows is None:
        raise SystemExit("run it first")
    outside = {row.race_id for row in rows if not in_window(row.race_id)}
    if outside:
        print(f"ignoring {len(outside)} races outside {FIRST} to {LAST}: {', '.join(sorted(outside))}\n")
    rows = [row for row in rows if in_window(row.race_id)]
    by_key: dict[tuple[str, str], dict[str, score.Scored]] = {}
    for row in rows:
        if row.predicted:
            by_key.setdefault((row.race_id, row.runner_id), {})[row.model] = row
    paired = [
        (race, math.log(pair["hierarchical"].predicted or 1), math.log(pair[gbm.NAME].predicted or 1),
         math.log(pair["hierarchical"].actual), score.stratum_of(pair["hierarchical"].depth))
        for (race, _runner), pair in by_key.items()
        if len(pair) == 2
    ]
    print(f"{len(paired):,} runners in {len({p[0] for p in paired})} races, {FIRST} to {LAST}\n")
    strata = ("0", "1", "2 to 3", "4 or more", "all")
    print(f"{'w':>5}" + "".join(f"{s:>11}" for s in strata))
    best = None
    for step in range(0, 21):
        w = step / 20
        line = []
        for stratum in strata:
            errors = [
                abs((1 - w) * h + w * g - a)
                for _race, h, g, a, s in paired
                if stratum == "all" or s == stratum
            ]
            line.append(100 * float(np.mean(errors)))
        print(f"{w:5.2f}" + "".join(f"{value:11.3f}" for value in line))
        if best is None or line[-1] < best[1]:
            best = (w, line[-1])
    assert best is not None
    print(f"\nbest weight on the window: {best[0]:.2f} ({best[1]:.3f} points of a finish time)")

    # What that weight buys against each model alone, resampling races.
    races = sorted({p[0] for p in paired})
    index = {race: i for i, race in enumerate(races)}
    rng = np.random.default_rng(score.BOOTSTRAP_SEED)
    picks = rng.integers(0, len(races), size=(score.BOOTSTRAP_DRAWS, len(races)))
    for name, take in (("hierarchical", lambda h, g: h), ("lightgbm", lambda h, g: g)):
        diff = np.array([
            abs((1 - best[0]) * h + best[0] * g - a) - abs(take(h, g) - a)
            for _race, h, g, a, _s in paired
        ])
        ix = np.array([index[p[0]] for p in paired])
        sums = np.bincount(ix, weights=diff, minlength=len(races))
        counts = np.bincount(ix, minlength=len(races)).astype(float)
        resampled = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
        low, high = np.quantile(resampled, [0.025, 0.975])
        print(
            f"blend vs {name:13} {diff.mean() * 100:+.3f} "
            f"({low * 100:+.3f} to {high * 100:+.3f}) points of a finish time"
        )


if __name__ == "__main__":
    {"run": go, "choose": choose}[sys.argv[1]]()
