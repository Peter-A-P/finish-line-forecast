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

### 1. Elevation figures: all eleven courses in the file have one, and more would still help

**This blocks nothing, and since 2026-09-20 it would buy something it would not have bought
before.** Peter asked for the website's course chart to have a second view: difficulty from
the elevation profile, as an objective measure that strips the weather and any self-selection
in who turns up. It is a good idea for a reason beyond that. A factor measured from results is
measured against Daniels' reference time for the course's own distance, so it carries this
population's departure from that curve (PLAN.md 13 item 36); a factor integrated from a
gradient profile has no reference time in it at all, and is the one number here that would be
comparable straight across race lengths. **That turned out to be the important part**: the
profiles Peter supplied on 2026-09-25 are what showed that the factor against the flat
reference carries the population's fade and the factor against a course's own length does not
(PLAN.md 13 item 43).

**What it needs, and it is more than a total.** Not the climb total: the grade distribution.
550 m spread over 11 km at 5% costs 5.9% and the same 550 m packed into 5.5 km at 10% costs
9.0%, which is why `metrics/grade.penalty` takes the grade as an explicit argument. So the view
wants elevation sampled along each route, not one ascent figure, and that means a traced route
per course. As of 2026-09-25, 10 of the 50 measured courses have a climb, and eight of
those also have the grade of their steepest and fastest stretch, which is what
`metrics/grade.penalty` actually takes. The chart is worth drawing now and has not been drawn
yet; the ten dots cover 5 km to the marathon and 48,000 of the archive's finishes.

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

Courses that were worth having, in order of how much history rides on them.
Every one but the last arrived on 2026-09-25:

| Course | Editions | Finishes | Measured factor | Profile |
|---|---:|---:|---:|---|
| Tely 10 | 11 | 25,664 | +0.2% | 97 up, 222 down |
| Mews Memorial 8 km | 16 | 4,893 | -5.3% | 28 up, 103 down |
| Mundy Pond 5 km | 17 | 3,197 | -1.8% | 36 up, 33 down |
| Five and Dime 5 km | 10 | 1,052 | -3.0% | 20 up, 42 down |
| Five and Dime 10 km | 10 | 843 | -0.8% | 63 up, 84 down |
| Huffin Puffin marathon | 7 | 296 | +9.6% | 308 up, 306 down, to about 30 m |
| Harbour Front 10 km | 12 | 2,473 | -1.8% | 72 up, 66 down |

**Done, and the answer was worth more than the cross-check it was asked for (2026-09-25).**
Peter supplied Overload profiles for eight courses, five of which had no elevation figure at
all: the Five and Dime 5 km and 10 km, Mundy Pond, Flat Out, Mews Memorial, the Tely, Cape to
Cabot and the Huffin Puffin marathon, the last of which is also every pre-2026 USR and Capital
Subaru marathon. Ten of the fifty measured courses now carry a climb, which is enough dots to
draw the chart Peter asked for. They also carry the grade, which is the thing this section
said was missing and no ascent total gives. **What they showed: on all eight courses with a
peer of their own race length, the hills agree with `versus_peers` and never with the factor
against the flat reference** (PLAN.md 13 item 43 has the table). That is independent
confirmation of item 36 and the strongest argument yet that the own-length figure is the one
to lead with.

The earlier three stand, and Turkey Tea's was redrawn the same day from Strava's own segment
stream: 39 m up and 123 m down against the 38 m the summary printed, plus the grade windows
the summary never gave (the physics floor is -4.2% and the results say -5.1% against the flat
reference, -4.5% against the other 10 km courses), Flat Out (2026-09-21, read by eye, and the
2026-09-25 measurement agreed with it to within 3 m on every number, which retired the doubt),
and Run to Remember, whose 2026-09-21 figure of 56 m each way off the organisers' chart was
**replaced on 2026-09-25** by 92.5 m each way off Strava's segment stream for the same
course. The difference is smoothing scale: on a steady out-and-back a coarse chart prints the
range as the climb, and the stream counts the rolling along the top. The hills are now worth
+0.39 to +0.54% of its +1.64% instead of +0.13%, so
most of that factor is still the gravel and the race length, and the stream also confirmed
the 2025 switch of start and turnaround, which had been the page's word alone.

**Nothing on this list is outstanding any more.** Harbour Front, the last course with real
history and no figure, came in the same batch off its segment stream. All eleven courses in
`data/courses.toml` now carry a profile and a grade window, and the numbers are the height
series' own (project 11 delivered them the same day, PLAN.md 13 item 43), not ones typed off
chart images. That also settled Mews Memorial, whose chart had arrived without its totals:
28.2 m up and 103.2 m down, against 26 and 100 read by eye.

Still wanted, and it blocks nothing: a **printed** figure for any of these, because every one
except Cape to Cabot rests on a single recording or a single segment.

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

**Answered on 2026-09-25, with start and finish points from project 11** (stored in
`data/courses.toml`, rounded to four places):

| Course | Start to finish | Share of the course | Verdict |
|---|---:|---:|---|
| Mews Memorial 8 km | 4,699 m on 49 degrees | 59% | **point to point; wants `bearing_deg = 49`** |
| Five and Dime 5 km | 1,153 m on 49 degrees | 23% | between Flat Out and Cape to Cabot; waits on the share decision below |
| Five and Dime 10 km | 1,155 m on 48 degrees | 12% | Flat Out's territory; no bearing |
| Harbour Front 10 km | 228 m | 2% | an out-and-back by the segment's own geometry; no bearing |

The heights alone had said all three of Mews and the Five and Dimes were point to point,
because each finishes well below its start. For the Five and Dime that was wrong: both races
start and finish at the same two points, 1.15 km apart, and wander in between. Mundy Pond
(3.3 m between its ends over 5 km) and the Huffin Puffin marathon (2 m over 42 km) need no
points to be called loops. **No `bearing_deg` has been set**, for the reason in the warning
below: Mews Memorial's 49 degrees goes in with the first backtest after Cape to Cabot.

Run to Remember is an out-and-back and has none. Turkey Tea has had one since 2026-09-19 (79
degrees). Flat Out was checked on 2026-09-21 and has none on purpose: nearly two laps of one
block, start and finish 363 m apart, 7.9% of the route with a net direction, and a test
recomputes that from its waypoints.

⚠️ **Adding a bearing is not like adding a climb, and the cache will not warn you.** A climb
feeds the grade cross-check and nothing else. A bearing feeds `ingest/eccc.tailwind`, which
feeds the conditions every hierarchical fit is built on, and `backtest/saved.key` hashes the
module sources and the dataset, **not `data/courses.toml`**. So a bearing added on its own
would silently change a model input while every saved backtest still looked current and
`freeze` still ran. Add one only alongside a backtest rerun, and consider putting the file in
the key.

**A decision for after Cape to Cabot: should the tailwind be scaled by how much of a course
it describes?** A bearing is start to finish, and the legs of any route sum to that
displacement, so displacement over distance is the share of the race that runs that way:
37% for Cape to Cabot (7.4 km of 20), 7.9% for Flat Out, which is why it has none. The model
applies the whole projected wind to every course with a bearing, so a winding course and a
straight one are charged alike. Multiplying the tailwind by that share is one line in
`models/weather.py`, but that file is in the hierarchical backtest's cache key and the term
does not yet clear zero, so it waits for a backtest that is running anyway. It needs start
and finish points per bearing, which Cape to Cabot, Mews Memorial and both Five and Dimes now
store. PLAN.md 13 item 41.

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
`store.build` swaps the club's copy out automatically; `retrospect.printed_category` then
reads that page's own columns rather than borrowing, with no edit here, and
`finishline dataset` prints which outside races have been superseded (`store.borrowed`) so
the day it happens is a line of output rather than something noticed later. **What is still
open at that point is the hometown column**, which the association prints and this project
does not yet show anywhere; that is a further widening of the publishing rule and is Peter's
call, not the assistant's. The scheduled crawl stands down from ten days before each live
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

**Decided by Peter, 2026-09-25: the Turkey Tea results go into Cape to Cabot's predictions.**
64 of Cape to Cabot's 499 entrants are on the Turkey Tea list, and their race two weeks
before is the freshest result they will have. The window is 2026-10-04 to 06:15 on
2026-10-11, between the Turkey Tea's gun and Cape to Cabot's first daily file, and it is free
now that the Trapline is not predicted (PLAN.md 13 item 44). In order, as soon as NLAA posts
the results:

1. `finishline crawl --refresh-index` (the scheduled crawl is standing down around both races,
   so this is by hand).
2. `finishline backtest --hierarchical --challenger`: 8 to 10 hours, checkpointed per block, so
   start it by the morning of 2026-10-10 at the latest to have it finished before 06:15 on
   2026-10-11.
3. `finishline report`, then commit and push, so the site and README follow.
4. `finishline score tt-2026` any time after step 1; scoring has no deadline.

⚠️ **Nothing enters the archive after step 2 starts** until Cape to Cabot's final file on
2026-10-17: every file in its week needs a backtest that matches the archive. If the Turkey Tea
results are not posted in time to finish step 2 before 06:15 on 2026-10-11, Cape to Cabot runs
on the pre-week backtest without them, and they are fetched after 2026-10-17.

## Open questions the assistant should not settle alone

### 4. The 2013 Tely 10, which the parser refuses on principle

It prints its rows with no column header at all, only the race title above them. The layout
is recognisable and the parser still refuses, because supplying column names it was not
given is the exact guess everything else here is built to avoid. Hard-coding that one
layout is defensible, but it should be a written exception rather than something slipped
in. The other four unparsed pages are named in [data-terms.md](data-terms.md) and are not
this kind of question.

### 5. Whether Run to Remember's file should name a field that is mostly wrong

Run to Remember publishes no start list, so its field is forecast (`models/participation.py`,
PLAN.md 5.6 and section 13 item 42). The backtest says about 30% of the runners named that way
finish (24% on Run to Remember's own three scored editions), so a final file of about 120
names will hold about 30 people who run and 90 who do not. The file says so beside the names,
and the score afterwards checks the promise. That is what the plan asked for and it is built:
`freeze r2r-2026` runs on 2026-11-10 unless told otherwise.

**The case against** is that a public list saying a named person is predicted to run a race
they had no intention of running is a small claim about them that the results never made.
**The alternatives**, both one change to `freeze`: publish the field forecast as counts only
(expected finishers, their predicted spread and the places) with no names; or name only the
runners the model gives at least an even chance, which on the races from 2024 was right about
70% of the time but named 8% of the finishers and nobody at all at 19 of 53 races (at Run to
Remember: 31, 34 and 2 names, of whom 11, 15 and 2 ran). Peter's call, before 2026-11-10.

## Waiting on Peter's labels

### 6. The resolver's precision and recall: 200 pairs to mark

PLAN.md 5.2 promises a precision and recall for runner resolution from about 200 hand-labelled
pairs, and the definition of done lists it; nothing had measured it. The sheet is now drawn:
`data/labels/resolution-pairs.csv` (from `finishline pairs`, 2026-09-21), 40 pairs from each
of five kinds of decision (joined with one town, joined across two towns, split by age, held
back, and near names the resolver never joins), with the resolver's answer beside each. Mark
the `label` column `same`, `different` or `unsure`, then `finishline pairs --score` prints
both numbers reweighted to how often each decision occurs in the archive (8,710 / 2,361 /
280 / 381 / 259), with 95% intervals. The sheet holds names, towns, age bands and times as the
results printed them, and is gitignored until Peter decides whether a labelled sample of named
people belongs in the public repository; the published figure is only reproducible if it does.
