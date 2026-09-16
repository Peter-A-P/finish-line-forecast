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
- [docs/data-terms.md](docs/data-terms.md): what may be fetched, from where, under what
  terms, and how a runner asks to be removed. Add a source's row before fetching it.
- **[PLAN.md](PLAN.md) section 13 is the log of designs the data refuted.** Twenty-seven entries
  and growing. Read it before changing the parser, the resolver, the course layer or the
  conditions layer: most of what looks like an odd choice in those modules is there because
  the obvious choice was measured and was wrong.
- [docs/todo.md](docs/todo.md): what is open and who owns it. Things waiting on Peter, on an
  outside event, or on a decision that is not the assistant's to make. Nothing that has a
  home in PLAN.md's schedule belongs there.

## Running it

Everything reads from a local cache, so a rerun costs no requests. The order:

```
finishline notices      what has to be sent before anything is fetched
finishline snapshot     today's look at the two live entrant lists   (daily, needs --notices-sent)
finishline catalogue    what races exist, and which are deliberately not read
finishline crawl        fetch the results pages, once, one a second  (needs --notices-sent)
finishline weather      fetch the ECCC observations per race month   (needs --notices-sent)
finishline dataset      parse, resolve runners, print what came out
finishline courses      how hard each course is, against what its hills predict
finishline conditions   what heat and wind cost, by distance
finishline backtest     score the baselines at every origin (--hierarchical adds the model)
finishline report       rewrite the README tables from the measurement
finishline freeze <race> the prediction file, hashed, refused inside 24 hours of the gun
finishline score <race>  the tagged prediction against the results   (fetches: --notices-sent)
```

`crawl`, `weather` and `snapshot` refuse to run until the courtesy notices have gone out,
and CI asserts that they refuse. The env var is `FINISHLINE_NOTICES_SENT=1`.

Checks: `uv run ruff check .`, `uv run mypy`, `uv run pytest`. On this machine the venv
interpreter is `.venv/Scripts/python.exe`.

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
