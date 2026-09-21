# Working notes for Claude Code

This repository is The Whole Field, Called Before the Gun, package `finishline`: pre-registered finish-time
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
- **[PLAN.md](PLAN.md) section 13 is the log of designs the data refuted.** Thirty-eight entries
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
finishline calendar     this year's fixtures from nlaa.ca/calendar.php, so the website's race
                        list is the season and not a hand-kept file (needs --notices-sent;
                        the page is alive, so it always re-fetches; writes data/calendar.json)
finishline crawl        fetch the results pages, once, one a second  (needs --notices-sent;
                        --refresh-index finds races posted since; a new race makes the
                        saved model backtest stale, so crawl before a backtest, never
                        between one and a freeze; the weekly task runs it with --scheduled,
                        which pauses around every race in data/live.toml)
finishline weather      fetch the ECCC observations per race month   (needs --notices-sent)
finishline dataset      parse, resolve runners, print what came out, and which races are
                        still read from outside the association (`store.borrowed`: the
                        swap to nlaa.ca's own page is automatic, this is where it shows)
finishline courses      how hard each course is, against what its hills predict
finishline conditions   what heat and wind cost, by distance
finishline backtest     score the baselines at every origin (--hierarchical adds the model)
finishline report       rewrite the README tables from the measurement, and
                        data/site/results.json, the website's numbers, from the same run
                        (also data/retrospect/<race>.json, runner by runner, for a race that
                        ran with no prediction tagged before it: publish/retrospect.py)
finishline participation the field forecast for a race with no start list: backtested,
                        written to data/participation.json, which `freeze` reads
finishline freeze <race> the prediction file, hashed, refused inside 24 hours of the gun
                        (--daily from seven days out: only entrants no earlier file had)
finishline due          which live races want a daily or final file today
finishline page <race>  the race page, rendered from the published prediction files
finishline site         the public website: web/ filled from data/site/results.json,
                        data/live.toml, data/calendar.json and the prediction files
finishline serve        preview it locally with the host's headers (docs/deploy.md)
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
- **A race that ran with no tag is a retrospective, never a prediction.** The website shows
  one (`publish/retrospect.py`, PLAN.md 5.9): the backtest's own held-out rows for a race
  run since 2026-09-12. It lives in `data/retrospect/`, never in `predictions/`; it gets no
  hash and no tag; it is not scored in `scores/`; and the card that draws it opens by saying
  what it is not. Keep those two directories, and those two words, apart.
- **No Strava, no training data, for anyone, in the public model.** The terms are in
  PLAN.md section 0. Do not add a Strava client to this repository in Part A.
- **Baselines first.** No model result is reported without carry-forward, best equal-VDOT
  and category median beside it.
- **Every reported number carries a confidence interval**, and every coverage table has
  the conformal assumption beside it.
- **Publish only what the results already publish** about a runner: the name and hometown as
  printed, the gender and age group the association's own results printed, the prediction,
  nothing else. Never the shirt size or anything else an entrant list alone holds. Ambiguous
  runners are excluded from every figure and counted, and a runner the resolver would not
  commit to gets no gender and no age either, because the row is there to say this project
  does not know which person it is. Widened from "name and hometown, the prediction, nothing
  else" on 2026-09-20 at Peter's request, for the runner table of an already-run race: the
  club's finish lists print no sex and no age, so the two columns are borrowed from that
  runner's other results on nlaa.ca, where they are public under the same name, and the page
  says which race and date they were printed at (`retrospect.printed_category`). Only results
  from before the race count and a band the runner has certainly grown out of is left blank.
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
