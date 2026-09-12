# Finish Line Forecast

Before the gun, a predicted finish time and placing for every registered runner in a
field of thousands, from their public race history, published in advance, with the error
published once the results are in. For a race director that is pacing, corral and medical
staffing planned from expected finish times rather than guesses; for a runner it is a goal
time with an honest interval instead of a hunch.

**Status: week 1 of 5.** Eighteen years of Newfoundland road results are read, 23,713
runners resolved out of them, and the three baselines are measured on every race since 2024. No
prediction has been made yet. The first live race is the Cape to Cabot 20 km in St. John's
on 2026-10-18, with a second on a frozen model on 2026-11-11; predictions are committed,
tagged and hashed in this repository before each race and scored against the official
results after it. Build plan: [PLAN.md](PLAN.md).

Nothing was fetched until the two organisations whose pages this reads had been told, and
`finishline crawl` refuses until they have. That rail is in code rather than in a
document: [docs/emails.md](docs/emails.md) carries what was sent.

## Result

**What the archive holds.** Measured by `finishline catalogue` on 2026-09-12 from the year
indexes, which carry event names and dates and no runners.

| | |
|---|---|
| Individual road races, 2008 to 2026 | 287 |
| Distinct courses | 80 |
| Deepest course history | 17 editions (Mews Memorial 8 km, Mundy Pond 5 km), 16 (Cape to Cabot 20 km) |
| Years with no racing | 2020 |

The skip list is the coverage claim, so it distinguishes a duplicate from a hole. Most
skips are team standings, awards pages, relays, cross-country and school races, which are
other views of races already read or other disciplines; a handful are real holes, mostly
races published as a PDF. [docs/data-terms.md](docs/data-terms.md) has the full table and
every page that would not parse.

**What reading all of it produced.** Written by `finishline report`; not edited by hand.

<!-- finishline:archive -->
| | |
|---|---:|
| Races read | 283 |
| Finishes parsed | 74,678 |
| Runners resolved | 23,713 |
| Runners this refuses to tell apart, and will not publish | 355 |
| Runners with one finish | 12,651 |
| Runners with two or three | 6,272 |
| Runners with four or more | 4,763 |
| Pages that would not parse | 5 |
<!-- finishline:end:archive -->

**How well the obvious approaches do.** Every race from 2024 on, each predicted only from
results dated strictly before it. Coverage sits beside error in every row, because a model
that answers for the easy half of a field is not better than one that answers for all of
it.

<!-- finishline:baselines -->
| Prior results | Runners | Model | Answered | MAE, minutes (95% CI) | Mean % error | Skill vs carry-forward |
|---|---:|---|---:|---|---:|---:|
| 0 | 5594 | `carry-forward` | 0% | - | - | baseline |
|  |  | `best-equal-vdot` | 0% | - | - | - |
|  |  | `category-median` | 96% | 18.5 (18.0 to 18.9) | 18% | - |
| 1 | 2648 | `carry-forward` | 100% | 9.6 (9.2 to 10.1) | 10% | baseline |
|  |  | `best-equal-vdot` | 63% | 7.5 (7.2 to 7.9) | 8% | 22% |
|  |  | `category-median` | 97% | 16.1 (15.5 to 16.7) | 16% | -68% |
| 2 to 3 | 2833 | `carry-forward` | 100% | 9.2 (8.8 to 9.7) | 9% | baseline |
|  |  | `best-equal-vdot` | 73% | 7.7 (7.2 to 8.0) | 8% | 17% |
|  |  | `category-median` | 97% | 15.9 (15.3 to 16.5) | 16% | -72% |
| 4 or more | 7233 | `carry-forward` | 100% | 7.4 (7.2 to 7.6) | 8% | baseline |
|  |  | `best-equal-vdot` | 87% | 7.1 (6.9 to 7.3) | 7% | 4% |
|  |  | `category-median` | 97% | 14.1 (13.8 to 14.4) | 18% | -90% |
<!-- finishline:end:baselines -->

**Getting the order right**, which is the number a race director actually plans from.

<!-- finishline:placing -->
| Model | Races | Mean absolute place error | Spearman, predicted vs actual |
|---|---:|---:|---:|
| `carry-forward` | 49 | 25.8 | 0.836 |
| `best-equal-vdot` | 48 | 18.3 | 0.836 |
| `category-median` | 45 | 96.4 | 0.356 |
<!-- finishline:end:placing -->

**The live prediction tables are empty until there is a prediction.**

**Live: predicted before the gun, scored after** (bootstrap 95% CIs over runners)

| Race | Runners predicted | Field coverage | MAE, minutes (model) | MAE, minutes (carry-forward baseline) | Coverage at 80% nominal | Coverage at 90% nominal | Median 80% width, minutes | Mean absolute place error | Spearman, predicted vs actual order | Prediction tag and hash |
|---|---|---|---|---|---|---|---|---|---|---|
| Cape to Cabot 20 km, 2026-10-18 | _not yet_ | | | | | | | | | |
| Run to Remember 11 km, 2026-11-11 | | | | | | | | | | |

**Who is entered for the first live race.** Cape to Cabot, from the club's published start
list of 2026-09-12, matched against the archive.

| | 2016 on, no 2026 Tely | 2008 on, with it |
|---|---:|---:|
| Entrants on the list | 453 | 453 |
| Resolve to a runner in the archive | 386 (85%) | **419 (92%)** |
| Have a 2026 result, so current-season form | 166 (37%) | **332 (73%)** |
| Have four or more prior results | 252 | **289** |
| No history at all | 67 | **34** |

**That second row is why one race mattered more than the other 282.** The 2026 Tely 10 is
not on the association's own site: it timed the race on Race Roster in June and its Tely
page links out, where every edition from 2018 to 2025 is published in place. It is 4,147
finishers, the largest field in the province, and adding it doubles the share of this field
whose current-season form the prediction can see. The basis for reading it, which is the
association's ownership of the race and its knowledge of this project rather than the
platform's terms, is set out in [docs/data-terms.md](docs/data-terms.md).

**Course and conditions.** Week 2 fills this; the normalisation is not built yet.

| Course | Estimated course factor (95% CI) | Physics prior | MAE without normalisation | MAE with normalisation |
|---|---|---|---|---|
| _not yet_ | | | | |

### What the baselines already say

**A third of the runners in any race have never raced here before.** 5,594 of the 18,308
runners predicted across those 49 races had no prior result at all, even with eighteen
years of archive behind them, and for those runners the only answer any of these models can
give is the middle of their age and sex category, which is out by 18.5 minutes on average.
That number, not the model comparison, is the size of the real problem. Adding eight more
years of history moved it by less than three hundred runners, which is worth knowing: the
cold start is not a gap in the archive, it is people who have genuinely never raced here.

**The race calculator beats the last result, but only where it will answer.** Reading the
best recent form off Daniels' curve is 19 percent better than carrying the last race
forward for runners with one prior result, and it gains four percent on runners with four
or more. What
moves is coverage: it answers for 63 percent of the thin histories and 90 percent of the
deep ones, because a runner with more results is likelier to have one inside the range the
curve is fitted for. A calculator that quietly extrapolated instead would have posted a
better-looking average over a worse-defined group.

**Nobody has said anything about an interval yet.** These three produce a time and no
sense of how sure it is, which is the gap the hierarchical model and the conformal layer
exist to fill.

## What this does not do

- **It uses no training data.** The original idea included each runner's public Strava
  activity. Strava's API agreement (effective 2026-06-01) forbids displaying or disclosing
  other users' data even when public, forbids training models on API data, and its
  acceptable use policy forbids scraping. The public model here works from public race
  results only, which is weaker, and this page says so first. An opt-in channel, where a
  runner sees a prediction from their own data and nobody else does, is deferred.
- It does not know who will start. Where the race publishes an entrant list, as Athletics
  NorthEAST does for Cape to Cabot, it predicts for that list and publishes the no-show
  rate afterwards. Where there is no list, it predicts for the runners its history says are
  likely to run and publishes how many of the actual finishers it covered.
- **It will sometimes merge two runners who share a name.** Hometown is not allowed to
  split them, for the reasons above, so two people of the same name and a compatible age
  become one runner with one muddled history. The number that bounds it is published:
  a measured 2.7 percent of resolved runners have a printed hometown that changes back and
  forth rather than once, which is the shape two merged people make. Reading them
  shows most are one person spelling their own town differently across entry forms
  (`Paradise` and `Pradise`, `Conception Bay South` and `Cbs`), so the true number is
  lower than 416, and 416 is what gets published because it is the one that can be checked.
- It does not predict a runner it cannot tell apart from another runner of the same name.
  355 were held back on the current archive, and they are counted rather than guessed at.
- It does not publish anything about a runner beyond what the race results already
  publish: name and hometown as printed, and the prediction.
- Its intervals are calibrated on past races. Coverage is guaranteed on average within a
  history-depth group under exchangeability, not for any one runner or one race, and the
  tables above say where it held.

## How it works

See [PLAN.md](PLAN.md). Public road-race results from the Newfoundland and Labrador
Athletics Association are crawled once, parsed and resolved to runners across races.
There is no runner identifier anywhere in that archive, and most of the readable races
print no hometown either, so the resolver works from the name and from the one piece of
evidence the pages give away for free: a runner cannot get younger. Every printed age band
on a dated race implies a window of birth years, and one person's windows have to
intersect. That is the only thing allowed to split a name into two runners. The hometown
breaks a tie and never splits, because runners move: of the 1,656 names appearing under
two or more towns, 1,103 show a single clean switch over time. Where a result could belong
to either of two runners and the page printed no age band, it is held back and counted.
Every past result is converted to a neutral-condition equivalent using a course factor
from the route's elevation profile, Daniels' heat correction and a calibrated wind model.
A Bayesian hierarchical model on log finish time shrinks each runner's fitness, trend and
endurance exponent toward their group, with a race-day effect whose prior comes from the
course and the weather forecast; a gradient-boosting quantile model is the challenger.
Intervals are conformalised on rolling-origin residuals, stratified by how many results a
runner has. Placing is simulated from the whole field's predictive distributions. The
prediction file is committed, tagged and hashed before the gun and scored after.

## Part of a portfolio

One of fifteen projects. It reuses the running arithmetic from Overload, the AI coaching
team for runners: Daniels' VDOT, the heat and wind corrections and the age-grading tables,
here in a public repository with tests.

## How this was built

Design, methodology, evaluation choices and judgement are Peter Parker's, including years
of racing and coaching himself on these courses. AI coding assistants (Claude Code) were
used for implementation and drafting, the way a senior engineer uses them in 2026. Every
number in the results tables is reproducible from this repository with one command, and
every live prediction is verifiable from a tag that predates the race it predicts.
