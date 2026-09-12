# Working notes for Claude Code

This repository is Finish Line Forecast, package `finishline`: pre-registered finish-time
and placing predictions for Newfoundland road races from public results, with a
hierarchical model over sparse histories, conformal intervals and a public
prediction-then-error record. The plan is in [PLAN.md](PLAN.md).

## Read first

- [README.md](README.md): what this is and the current result tables.
- [PLAN.md](PLAN.md): the design, the data-terms outcome, the schedule. Do not deviate from
  it silently; if something in it turns out wrong, change the plan in the same commit as
  the code and say why in the commit message.
- `docs/data-terms.md` once it exists: what may be fetched, from where, and how a runner
  asks to be removed.

## Engineering standard

- Python 3.13, managed with `uv`. Typed throughout; `mypy --strict` and `ruff` clean in CI.
- Tests that fail meaningfully: golden pages for the parser, labelled pairs for
  resolution, closed-form checks for Daniels and the grade model, the leakage test on the
  backtest, coverage on a synthetic fixture, schema and hash on the prediction file.
- `pyproject.toml` with pinned major versions and a comment saying why for each pin.
- Docs ship in the same commit as the change.
- Never commit raw pages, entrant lists, the resolved history cache, credentials or `.env`.

## Rules specific to this repository

- **A prediction counts only if it was tagged before the gun.** `freeze` refuses inside 24
  hours; nothing in a prediction file is edited after its tag, ever. A defect found later
  is scored as it stands and written up.
- **No Strava, no training data, for anyone, in the public model.** The terms are in
  PLAN.md section 0. Do not add a Strava client to this repository in Part A.
- **Baselines first.** No model result is reported without carry-forward, best equal-VDOT
  and category median beside it.
- **Every reported number carries a confidence interval**, and every coverage table has
  the conformal assumption beside it.
- **Publish only what the results already publish** about a runner: name and hometown as
  printed, the prediction, nothing else. Ambiguous runners are excluded and counted.
- **Be polite to nlaa.ca**: one request a second, fetch once, cache forever, identify the
  crawler in the user agent.
- **Constants from Overload are priors, not estimates.** Say so where they are used; the
  race-edition effect is estimated from data.
- **Plain punctuation** in everything written here: no em-dashes or other typographic
  dashes, straight quotes only.

## What goes in the README

The README opens with the one-liner, the results tables and the honest limitation (no
training data, and why), before any installation instructions. `finishline report` fills
the tables; do not hand-edit them. `docs/rejected.md` records one approach tried and
rejected, with the evidence, once the work has produced it. Each race gets a page under
`docs/predictions/` with the predictions before and the errors after.
