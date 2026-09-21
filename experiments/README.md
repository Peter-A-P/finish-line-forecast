# Experiments: records of a search, not supported code

Four published settings and one rejected approach were chosen by scripts that sit outside the
package. They are kept here so that a reader can see exactly what was tried, not only what
won. The numbers the README reports are measured by `finishline backtest` on the 2024 and
later races; these scripts only ever looked at 2022 and 2023, or at the whole archive for a
question the backtest cannot answer.

| Script | What it chose or showed | Cited in |
|---|---|---|
| `tune_gbm.py` | The challenger's features and parameters: a 40-set random search and nine ideas, six refused | PLAN.md 13 item 34 |
| `blend_weight.py` | The blend weight, 0.65, read off 2022 and 2023 | PLAN.md 13 item 35, docs/methods.md |
| `sun_experiment.py` | Heat as a hinge on felt temperature beat a straight line, leave one year out | docs/rejected.md |
| `rejected_slope.py` | The race-level bias against the heat, per weather model | docs/rejected.md |

**What these are not.** They are not held to the package's bar: no types, no tests, and
`ruff` and `mypy` do not check this folder. They were run against the code as it stood on
the day (the commit that cites each one), and a later change to a private helper in
`finishline.cli` can stop one from running today without changing anything it recorded.
Treat them as a lab notebook: the method is here, and the results are in the documents that
cite them.

**Running one.** From the repository root, with the models extra installed. They write
their outputs under `scratch/`, which is ignored. `rejected_slope.py` and `sun_experiment.py`
read a pickled dataset first:

```
python -c "import pickle; from pathlib import Path; from finishline import cli; Path('scratch').mkdir(exist_ok=True); Path('scratch/dataset.pkl').write_bytes(pickle.dumps(cli._dataset(cli.FIRST_YEAR, cli.LAST_YEAR)))"
```

`rejected_slope.py` also reads the saved backtest blocks of the runs it compares, by their
keys, so it only reproduces on a machine that ran those backtests.
