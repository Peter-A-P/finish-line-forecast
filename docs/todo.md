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

### 1. Run to Remember's 2026 gun time

Cape to Cabot's is confirmed (08:00 on 2026-10-18, NDT) and in `data/live.toml`, which puts
its freeze deadline at 08:00 on 2026-10-17. `finishline freeze` refuses a race without a
confirmed gun time, on purpose: the 24-hour rule is measured from it. Run to Remember needs
the same before 2026-11-10, on standard time (`-03:30`).

### 2. Elevation figures for the other courses, if and when they are easy to get

**This blocks nothing.** It is worth being clear about that, because it was a dependency in
the original plan and is not one any more. Course difficulty is measured from the results
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

### 2b. Course bearings, which are now worth more than elevations

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

### 3. Score the Uniformed Services Run against its start list

The USR ran on 2026-09-13 with 629 entrants across its four individual road events, and the
final pre-gun list is saved. When NLAA posts the results, three numbers fall out that Cape
to Cabot needs a month later: the no-show rate, the late-entry rate, and the
list-to-results name-match rate. No prediction was made for it, because the gun was inside
twenty-four hours and `freeze` refuses inside twenty-four hours.

## Open questions the assistant should not settle alone

### 4. The 2013 Tely 10, which the parser refuses on principle

It prints its rows with no column header at all, only the race title above them. The layout
is recognisable and the parser still refuses, because supplying column names it was not
given is the exact guess everything else here is built to avoid. Hard-coding that one
layout is defensible, but it should be a written exception rather than something slipped
in. The other four unparsed pages are named in [data-terms.md](data-terms.md) and are not
this kind of question.
