# Outstanding, and who owns each

Only things that are actually open. The schedule is in [PLAN.md](../PLAN.md) section 6 and
the design changes are in its section 13; this file is for work that has no home in either
because it is waiting on a person or on an outside event.

## Waiting on Peter

The daily entrant-list snapshot is registered with Task Scheduler as of 2026-09-13 and
first ran from it at 20:23 that evening (`scripts/register-snapshot-task.ps1`; check it with
`Get-ScheduledTask -TaskName 'FinishLine daily entrant snapshot'`, and read
`data/entrants/snapshot.log`, which every run appends to). If the working copy ever moves to
another machine, the task and the gitignored `data/` have to move with it; neither is in git.
The weekly results crawl is registered the same way (`scripts/register-crawl-task.ps1`, log in
`data/cache/nlaa/crawl.log`) and moves with it.

### 1. Elevation figures for the other courses, if and when they are easy to get

**This blocks nothing, and since 2026-09-20 it would buy something it would not have bought
before.** Peter asked for the website's course chart to have a second view: difficulty from
the elevation profile, as an objective measure that strips the weather and any self-selection
in who turns up. It is a good idea for a reason beyond that. A factor measured from results is
measured against Daniels' reference time for the course's own distance, so it carries this
population's departure from that curve (PLAN.md 13 item 36); a factor integrated from a
gradient profile has no reference time in it at all, and is the one number here that would be
comparable straight across race lengths.

**What it needs, and it is more than a total.** Not the climb total: the grade distribution.
550 m spread over 11 km at 5% costs 5.9% and the same 550 m packed into 5.5 km at 10% costs
9.0%, which is why `metrics/grade.penalty` takes the grade as an explicit argument. So the view
wants elevation sampled along each route, not one ascent figure, and that means a traced route
per course. Today 2 of the 50 measured courses publish a climb at all (Cape to Cabot and Turkey
Tea), so the second view would be a chart with two dots in it and has not been built. Six or
eight of the busiest courses would make it worth drawing.

**The rest of the case, which has not changed.** Course difficulty is measured from the results
(`finishline courses`), and on every course that matters the interval is tighter than an
elevation figure could make it. Cape to Cabot is +9.3% [+9.0, +9.5] from 5,310 finishes.

**What an elevation figure buys.** Only a cross-check, and only for a course that has one.
On Cape to Cabot the check passed and was worth having: the published 550 m of climb
against 450 m of drop implies a 10.3% average grade to produce the measured +9.3%, and the
race's own page says "grades of more than 10 per cent in some parts". Two independent
routes to one number is a better claim than either alone. The other case it would serve is
a course with no history at all, and there is not currently one that matters.

**Where they go.** `data/courses.toml`, one block per course, with the source beside every
number. A test refuses a course that states a climb with no source. Wanted per course:
total climb, total drop, and where the figure came from. An independent second figure (a
watch total, a different publication) is kept alongside rather than instead of, because the
two bracket the truth; Cape to Cabot has both.

Courses that would be worth having, in order of how much history rides on them:

| Course | Editions | Finishes | Measured factor |
|---|---:|---:|---:|
| Mews Memorial 8 km | 16 | 4,891 | -5.3% |
| Mundy Pond 5 km | 17 | 3,192 | -1.8% |
| Flat Out 5 km | 15 | 2,753 | -0.9% |
| Turkey Tea 10 km | 14 | 2,296 | -5.1% |
| Harbour Front 10 km | 12 | 2,472 | -1.8% |
| Run to Remember 11 km | 11 | 1,042 | +1.6% |
| Tely 10 | 11 | 25,620 | +0.2% |

⚠️ **Not a runner's GPS track.** A watch file is training data about an identifiable person,
which is the line this project drew for Strava and it does not move because the file
arrived by a different route. A single published ascent total about a public road is a
different thing, and is what Cape to Cabot's second figure is.

### 2. Course bearings, which are now worth more than elevations

**This is the highest-value thing anyone can add to `data/courses.toml`.** Peter's point
that the Tely's prevailing westerly is a tailwind for almost the whole race turned out to
be the fix for a term that was measuring nothing: fitted as one wind-speed number for the
whole province, a tailwind course and a headwind course cancel.

Only two courses carry a bearing so far, the Tely (70 degrees) and Cape to Cabot (321), and
27 editions is not enough to separate the tailwind coefficient from zero. It has the right
sign, -0.022 percent per km/h [-0.100, +0.054], and is published as not-yet-significant.

Wanted per point-to-point course: roughly where it starts and where it finishes, or just
the compass direction the field generally runs. **A loop or out-and-back has no bearing and
must not be given one**; those courses feel the wind as a cost whichever way it blows, and
`courses.toml` leaving `bearing_deg` out is how that is said.

Candidates worth checking, all with real history: Mews Memorial 8 km, Mundy Pond 5 km,
Harbour Front 10 km, Turkey Tea 10 km, Run to Remember 11 km, Flat Out 5 km.

## Waiting on an outside event

### 3. New results between now and Cape to Cabot

The 2026 USR is in, from Athletics NorthEAST's own finish lists (`ingest/ane.py`), and its
start list is scored: 15.1% of listed entrants not found, 2.0% of finishers not on their
event's list (PLAN.md 5.6). **Both numbers are now computed in the repository rather than by
hand** (`publish/retrospect.py`, written 2026-09-20), which closes the gap item 5 below
complains about for this pair at least, and the 10 km is on the website as the one race this
project has already seen run (PLAN.md 5.9). **Peter decided that column question on
2026-09-20**: the runner table carries a gender and an age group, taken from that runner's
other results on nlaa.ca, where they are public under the same name, and CLAUDE.md's
publishing rule was widened in the same commit to say so. The club's own finish lists print
no sex, no age and no hometown, so the columns are borrowed and dated on the page
(`retrospect.printed_category`); only results from before the race count, and a band the
runner has certainly grown out of is left blank rather than aged forward. 133 of the 171 USR
finishers have one. When nlaa.ca republishes the USR its own pages carry all three and
`store.build` swaps the club's copy out automatically, at which point these columns stop
being borrowed for that race and the hometown column becomes possible too. The scheduled crawl stands down from ten days before each live
race to the day after, and with the Turkey Tea rehearsal on 2026-10-04 and Cape to Cabot on
2026-10-18 the only Sunday it runs before 2026-10-25 is 2026-09-20. Results posted after that
are fetched by hand (`finishline crawl --refresh-index`) before the backtest each freeze uses,
never between that backtest and the freeze. When nlaa.ca posts the USR, its pages replace the
club's copy automatically (`store.build`).

### 3b. The Turkey Tea rehearsal, 2026-10-04 at 08:00

A prediction week (PLAN.md 5.7): daily files of new entrants from 2026-09-27, the final file
with places by 08:00 on 2026-10-03, each committed, tagged and pushed by
`scripts/daily-predictions.ps1` at 06:15 (register it with
`scripts/register-predictions-task.ps1`), and scored when NLAA posts the results. `freeze`
needs a saved backtest that matches the code and the data on the day, so nothing in
`models/`, `history.py` or `backtest/run.py` changes after the backtest it will use, `src/`
stays committed through the week. The repository is public (2026-09-19) and the website
redeploys on every push (docs/deploy.md). Cape to Cabot's week starts 2026-10-11.

## Open questions the assistant should not settle alone

### 4. The 2013 Tely 10, which the parser refuses on principle

It prints its rows with no column header at all, only the race title above them. The layout
is recognisable and the parser still refuses, because supplying column names it was not
given is the exact guess everything else here is built to avoid. Hard-coding that one
layout is defensible, but it should be a written exception rather than something slipped
in. The other four unparsed pages are named in [data-terms.md](data-terms.md) and are not
this kind of question.

### 5. The two tuning scripts are not in the repository, and two published numbers come from them

The challenger's features and parameters (PLAN.md section 13 item 34) and the blend weight
(item 35) were both chosen on the 2022 and 2023 races, by `scratch/tune_gbm.py` and
`scratch/blend_weight.py`. Both items cite those scripts, and `scratch/` is gitignored, so a
reader can check every number measured on the test races and cannot rerun the two searches
that produced the settings. That is a gap in the one rule this project is built on.

**The case for moving them in**, say to `experiments/`, is that the settings are as much a
result as the errors are: a weight of 0.65 and a 40-set random search are claims about what
was tried, and the scripts are the evidence. **The case against** is that they are scratch
code, not held to the typing and lint bar the package is, and committing them invites a
reader to treat them as part of the tool.

Either is defensible; what is not defensible is citing a file nobody else can see. A
middle course is to commit them under `experiments/` with a README saying they are records
of a search rather than supported code, excluded from `mypy --strict` the way the tests
are not. Peter's call.
