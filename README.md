# Finish Line Forecast

Before the gun, a predicted finish time and placing for every registered runner in a
field of thousands, from their public race history, published in advance, with the error
published once the results are in. For a race director that is pacing, corral and medical
staffing planned from expected finish times rather than guesses; for a runner it is a goal
time with an honest interval instead of a hunch.

**Status: building.** Eighteen years of Newfoundland road results are read, 23,713
runners resolved out of them, the three baselines are measured on every race since 2024,
every course's difficulty is measured from the results, and the hierarchical model now beats
the strongest of those baselines by 26% for the runners with four or more prior results, 5.5
minutes of mean absolute error against carry-forward's 7.4, with no bias left to speak of. No
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
| Individual road races, 2008 to 2026 | 286 |
| Distinct courses | 52 |
| Deepest course history | 17 editions (Mews Memorial 8 km, Mundy Pond 5 km), 16 (Cape to Cabot 20 km) |
| Years with no racing | 2020 |

The skip list is the coverage claim, so it distinguishes a duplicate from a hole. Most
skips are team standings, awards pages, relays, cross-country and school races, which are
other views of races already read or other disciplines; a handful are real holes, mostly
races published as a PDF. One is the same race published twice: the 2014 CHCM 10 km is on
the index as both `.htm` and `.php` with the same 162 finishers in different letter cases,
and counting it twice would have given 162 people a second result on a day they raced once.

⚠️ **Eighty of those courses were really fifty-two.** The 2008 to 2015 index titles a race
with its ordinal and whichever sponsor held the naming rights, so Burton's Pond read as six
courses of one edition each and CHCM as seven, and every fragment then fell under the
thirty-finish floor and vanished from the table below. The merge overshot once before it
settled: some races have no name but their sponsor, and stripping it collapsed six unrelated
half marathons into a single course called "unknown". [docs/data-terms.md](docs/data-terms.md) has the full table and
every page that would not parse.

**What reading all of it produced.** Written by `finishline report`; not edited by hand.

<!-- finishline:archive -->
| | |
|---|---:|
| Races read | 282 |
| Finishes parsed | 74,516 |
| Runners resolved | 23,713 |
| Runners this refuses to tell apart, and will not publish | 355 |
| Runners with one finish | 12,683 |
| Runners with two or three | 6,252 |
| Runners with four or more | 4,751 |
| Pages that would not parse | 5 |
<!-- finishline:end:archive -->

**How hard each course is, measured rather than surveyed.** Runners cross between courses,
so a course's difficulty is identifiable from finishes alone: somebody slower on Cape to
Cabot than their own equal-VDOT expectation every year, and faster on Mews Memorial every
year, is saying what the hills cost. Effects are centred on the average course somebody
actually runs, so zero is ordinary rather than flat, and the interval resamples runners
rather than finishes, because two races by one person are not independent evidence about a
hill. The last column is a check and not an input: it asks what average grade would explain
the measured factor, given the climb the race publishes.

<!-- finishline:courses -->
| Course | Finishes | Editions | Slower than flat | 95% CI | Grade that would explain it |
|---|---:|---:|---:|---|---|
| usr-42195 | 126 | 3 | +13.6% | [+11.6, +15.5] |  |
| provincial-championship-42195 | 68 | 2 | +9.3% | [+6.4, +12.6] |  |
| cape-to-cabot-20000 | 5,310 | 15 | +9.3% | [+9.0, +9.5] | 10.3% average, over the published 550 m of climb |
| run-from-away-42195 | 79 | 1 | +8.0% | [+6.2, +9.7] |  |
| huffin-puffin-42195 | 149 | 3 | +6.5% | [+5.1, +7.9] |  |
| trapline-5000 | 138 | 6 | +6.4% | [-2.3, +15.6] |  |
| bell-island-blast-16093 | 181 | 3 | +4.5% | [+3.7, +5.5] |  |
| trapline-42195 | 55 | 7 | +4.4% | [+0.5, +8.7] |  |
| _... 32 more_ | | | | | |
| five-and-dime-5000 | 1,051 | 10 | -3.0% | [-3.6, -2.4] |  |
| quidi-vidi-5000 | 334 | 4 | -3.2% | [-3.9, -2.4] |  |
| ane-mile-1609 | 577 | 12 | -3.7% | [-4.8, -2.3] |  |
| provincial-championship-5000 | 907 | 8 | -4.0% | [-4.5, -3.6] |  |
| turkey-tea-10000 | 2,296 | 14 | -5.1% | [-5.4, -4.9] |  |
| mews-memorial-8000 | 4,891 | 16 | -5.3% | [-5.5, -5.1] |  |
| pearlgate-5000 | 88 | 1 | -5.7% | [-6.8, -4.8] |  |
| oceanview-5000 | 108 | 1 | -6.3% | [-7.2, -5.5] |  |
<!-- finishline:end:courses -->

**The check is worth more than either number alone.** Cape to Cabot is the only course here
with a published elevation, and the two routes to its difficulty were computed
independently: 5,310 finishes say +9.3%, and 550 m of climb against 450 m of drop over 20 km
through Minetti's cost-of-running curve needs a 10.3% average grade to produce that. The
race's own course page says "grades of more than 10 per cent in some parts". Neither number
was tuned to the other.

⚠️ **A per-runner career trend is doing more work here than it looks.** Fitted with one
constant per runner, Cape to Cabot's edition effect climbs almost monotonically from +3.8%
in 2013 to +14.4% in 2025, which reads as a course getting harder every year. It is not: a
career-long constant has nowhere to put the fact that runners age, so the edition effects
absorb it, and all thirteen well-covered courses drift upward at a median of +0.60% a year.
With a per-runner trend the median drift is +0.00% and the signs scatter. A model fitted the
first way and asked for 2026 would extrapolate ten points of course inflation that does not
exist, and the table would look entirely reasonable.

**What the morning costs.** The course layer says how hard a road is; this says how much of
what is left over is the weather. It fits the same edition effects against the observed
temperature and wind at St. John's airport, with the temperature coefficient allowed to grow
with distance, because a 5 km field meets fifteen minutes of weather and a marathon field
meets four hours of it.

<!-- finishline:conditions -->
Fitted on 227 editions near St. John's airport, 55 of 282 excluded as too far from it or without an observation. Explains **33%** of the edition-to-edition variance within a course, leaving sd 2.32%.

| Race length | Cost per degree above neutral | What a 20 C morning costs |
|---|---:|---:|
| 5 km | -0.05% | -0.5% |
| 10 km | +0.24% | +2.4% |
| Tely 10 | +0.44% | +4.4% |
| Cape to Cabot 20 km | +0.53% | +5.3% |
| marathon | +0.85% | +8.5% |

Neutral is 10 C and 20 km/h, which is the middle of this archive rather than a laboratory ideal.

| Term | Estimate | 95% CI |
|---|---:|---|
| Temperature at 10 km, per degree | +0.242% | [+0.130, +0.369] |
| Tailwind along the bearing, per km/h | -0.029% | [-0.110, +0.052] |
<!-- finishline:end:conditions -->

**The check.** The Tely 10 on its own is the cleanest natural experiment in the archive:
eleven editions of two to four thousand finishers, run anywhere from 3.6 to 22.7 C because
two COVID years pushed it into October. It gives +0.41% per degree on its own, +0.42
controlling for year, R-squared 0.64. The pooled model above, fitted across every course and
never told about the Tely, returns +0.425 at that distance. Both sit in the range the
marathon literature reports for mid-pack runners.

⚠️ **This took two wrong answers first, and both are in [PLAN.md](PLAN.md) section 13.**
Fitted unweighted, temperature came out at +0.03% per degree with the interval through zero,
which reads as "the weather does not move a race in a climate this cool"; an edition effect
from thirty finishers is mostly noise and the small races were shouting down the large ones.
Fitted on raw edition effects rather than within-course ones, it partly measured the fact
that the hard courses here run in October and the easy ones in June. What caught the second
one was the residual coming out at 4.42%, larger than the 2.79% scatter it was supposed to
be explaining: a model cannot explain something and leave more behind than it started with.

⚠️ **A wind speed is not a wind, and the tailwind term is not yet significant.** The
prevailing wind in Tely season is westerly and the Tely runs east-north-east, so the usual
wind pushes that field along; Cape to Cabot runs north-west, so the same westerly is a
headwind, and it runs into one in 13 of its 16 editions. Fitted as a single speed for the
whole province those cancel, which is exactly what the first attempt showed. Wind now enters
as a speed, which a loop pays whichever way it blows, and as a signed tailwind along a course
bearing, which only a point-to-point course has. Only two courses carry a bearing so far, so
the tailwind coefficient has the right sign and an interval that still includes zero. It is
reported that way rather than kept quiet because the sign is pleasing.

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
|  |  | `hierarchical` | 100% | 17.8 (17.4 to 18.3) | 18% | - |
|  |  | `hierarchical-no-weather` | 100% | 17.9 (17.5 to 18.4) | 18% | - |
| 1 | 2650 | `carry-forward` | 100% | 9.6 (9.2 to 10.0) | 10% | baseline |
|  |  | `best-equal-vdot` | 63% | 7.5 (7.2 to 7.9) | 8% | 22% |
|  |  | `category-median` | 97% | 16.1 (15.5 to 16.8) | 16% | -68% |
|  |  | `hierarchical` | 100% | 9.4 (9.0 to 9.8) | 10% | 2% |
|  |  | `hierarchical-no-weather` | 100% | 9.6 (9.2 to 10.0) | 10% | 0% |
| 2 to 3 | 2831 | `carry-forward` | 100% | 9.2 (8.9 to 9.7) | 9% | baseline |
|  |  | `best-equal-vdot` | 73% | 7.7 (7.2 to 8.0) | 8% | 17% |
|  |  | `category-median` | 97% | 15.9 (15.3 to 16.5) | 16% | -72% |
|  |  | `hierarchical` | 100% | 8.5 (8.1 to 8.9) | 9% | 8% |
|  |  | `hierarchical-no-weather` | 100% | 8.6 (8.2 to 9.0) | 9% | 7% |
| 4 or more | 7233 | `carry-forward` | 100% | 7.4 (7.2 to 7.6) | 8% | baseline |
|  |  | `best-equal-vdot` | 87% | 7.1 (6.9 to 7.3) | 7% | 4% |
|  |  | `category-median` | 97% | 14.1 (13.8 to 14.4) | 18% | -90% |
|  |  | `hierarchical` | 100% | 5.4 (5.2 to 5.6) | 6% | 27% |
|  |  | `hierarchical-no-weather` | 100% | 5.5 (5.3 to 5.7) | 6% | 25% |
<!-- finishline:end:baselines -->

⚠️ **The first run of this model lost to carry-forward. This is the second run, and what
changed is in [PLAN.md](PLAN.md) section 13 items 28 and 29.** Two things were wrong at once:
each runner's improvement trend was carried in a straight line to race day, which predicts
years of improvement nobody has, and the race-edition effects were quietly absorbing a
calendar drift, so that 2023 and 2024 races came out 6 to 8% slower than their own course
averages. Form is now a random walk over the years a runner actually races, and a shared
year effect walks the whole province from one calendar year to the next. The bias is gone:
on the 12,714 runners both can answer for, predictions are 0.7% too fast on average (95% CI
1.8% too fast to 0.6% too slow), against carry-forward's 0.4% too fast (2.6% too fast to 1.9%
too slow), the intervals resampling races rather than runners. With each race's typical error
removed the model is ahead rather than level, by 0.59 percentage points of absolute log error
(95% CI 0.36 to 0.93), so it has both the level and the order of a field better than the
baseline it lost to before.

⚠️ **It still samples badly, and the tables above are what that badly-sampled model
predicts.** Across the eight quarterly fits the worst R-hat runs from 1.41 to 2.15 and the
smallest bulk ESS is about 5, with no divergences. The cause is identification, not tuning:
years since a runner's first race and the calendar year move together, so the group drift,
the year effect and the group means trade off along a ridge that the sampler wanders. The
predictions use only the combination that is invariant along that ridge, which is why they
are accurate anyway, but no individual coefficient from this fit should be read on its own.
PLAN.md section 13 item 29 has the comparison and the caveat in full.

⚠️ **Weather is the felt heat above 12 C, with the sun estimated, and it is worth about a
percent of a field's level, not of a runner's error.** The model reads each morning at St.
John's airport over the hours the field was actually out, from each race's published start
time, and charges nothing below 12 C. Above it, each degree of felt heat costs a fraction that
grows with distance, and full sun adds degrees to the felt temperature, how many being a
parameter the data estimates. Fitted on the whole archive, a degree above the knee costs
+0.05% at 5 km (95% CI +0.00 to +0.13), +0.31% at 10 km (+0.23 to +0.39), +0.50% on the Tely
(+0.37 to +0.61), +0.58% on Cape to Cabot (+0.43 to +0.71) and +0.87% at a marathon (+0.64 to
+1.06); a km/h of wind +0.027% (+0.011 to +0.045). A full sun adds 2.1 C of felt temperature
(95% CI 0.1 to 9.2), which the data narrowed to half its prior's spread without pinning down,
because only six of 281 mornings in the archive had strong sun. The tailwind term stays the
null it has always been, because only two courses carry a bearing.

Paired on the 18,278 predictions both runs make, weather lowers absolute log error by 0.0010
(95% CI -0.0019 to +0.0002), better at every depth and clear of zero only for runners with no
history. That is the size it should be: weather moves the level of a whole field by one to
five percent, individual error is around ten, and a correct level shift is close to invisible
per runner. It is not invisible to a race director planning a finish-line clock, and the check
that matters is the race level. There, the model without weather leaves bias that climbs with
the heat, +0.42 (+/- 0.30) of each point of heat cost left in the errors, and the model with
weather leaves -0.15 (+/- 0.30), which is zero. The previous weather model, linear in
temperature from 10 C, left -0.69 (+/- 0.27): it applied about half the heat a warm morning
costs. The 2025 USR, the hottest mornings in the backtest at 22 C, went from 1.0 to 1.4% too
fast to 0.6 to 1.2% too slow.

⚠️ **One hot race the heat does not explain: the 2026 Tely 10 is still 3.0% too fast.** 18 C,
light sun, calm, with a tailwind. The model charges it 3.1% and it ran about 6% slower than a
neutral morning. The whole-archive fit is the source of the charged figure, not the backtest's
own quarterly fit, so this is approximate; either way the gap is not heat, since no setting of
the knee or the sun closes it without breaking the other hot races. The conditions table above
is the older linear check on edition effects alone, kept as the independent cross-check it was
built to be; PLAN.md section 13 item 30 has the felt-heat model, the alternatives it was
measured against, and why the knee is fixed at 12 C rather than fitted.

**Getting the order right**, which is the number a race director actually plans from.

<!-- finishline:placing -->
| Model | Races | Mean absolute place error | Spearman, predicted vs actual |
|---|---:|---:|---:|
| `carry-forward` | 49 | 25.8 | 0.836 |
| `best-equal-vdot` | 48 | 18.3 | 0.836 |
| `category-median` | 45 | 96.4 | 0.356 |
| `hierarchical` | 49 | 53.4 | 0.717 |
| `hierarchical-no-weather` | 49 | 53.4 | 0.715 |
<!-- finishline:end:placing -->

⚠️ **The model predicts times better than it predicts places, and this table flatters the
baselines.** Places are computed among the runners each model answered for, so carry-forward
is ranked over the 12,714 runners who have a prior result, while the model is ranked over the
whole field, the 5,594 entrants with no history included, and ordering those is close to
guessing. The two columns are therefore not measuring the same race. It is printed this way
because the alternative, scoring each model on the subset that suits it, is how a table
stops being checkable. Scoring the model on the runners carry-forward can also answer is the
next measurement, and it belongs beside this one rather than instead of it.

**How often the intervals hold.** A predicted time with an interval is two claims, and the
second one is checked here: the model's own 80% and 90% intervals, and the same intervals
after conformal adjustment on the races before each one, by how much history a runner has.

<!-- finishline:coverage -->
`hierarchical`, every race from 2024 on. Each race's intervals are adjusted using only races dated before it, separately for each history depth. Coverage is the share of runners whose finish fell inside; the 95% CI resamples races, not runners, because runners in one race share its morning.

| Prior results | Level | Runners checked | Races | Model's own interval | After conformal | Median width, minutes (own to conformal) |
|---|---:|---:|---:|---|---|---|
| 0 | 80% | 5,532 | 47 | 77% (76 to 80) | 79% (74 to 83) | 54.4 to 55.6 |
| 1 | 80% | 2,591 | 43 | 74% (70 to 76) | 77% (74 to 79) | 20.7 to 23.2 |
| 2 to 3 | 80% | 2,762 | 43 | 72% (68 to 75) | 78% (76 to 82) | 18.5 to 22.1 |
| 4 or more | 80% | 7,133 | 46 | 76% (73 to 79) | 77% (74 to 79) | 13.4 to 13.5 |
| 0 | 90% | 5,532 | 47 | 87% (86 to 90) | 89% (87 to 92) | 70.8 to 74.7 |
| 1 | 90% | 2,591 | 43 | 84% (81 to 86) | 89% (87 to 90) | 28.3 to 33.7 |
| 2 to 3 | 90% | 2,762 | 43 | 82% (80 to 84) | 88% (86 to 89) | 24.9 to 30.0 |
| 4 or more | 90% | 7,133 | 46 | 87% (85 to 89) | 88% (87 to 90) | 18.1 to 19.1 |

**The assumption.** Conformal coverage is guaranteed on average over races within a history-depth group, provided a new race's errors look like the earlier races' errors (exchangeability). It is not a promise about any one runner or any one race, and it fails when a race meets conditions or a field the earlier races did not: a gale on Signal Hill is exactly that. The first races of the backtest have too few earlier errors to calibrate on (under 50 per group) and are left out of this table rather than given an interval nobody could trust.
<!-- finishline:end:coverage -->

**Live: predicted before the gun, scored after.** Cape to Cabot 20 km on 2026-10-18, then Run
to Remember 11 km on 2026-11-11 on the same frozen model. `finishline score` reads each
prediction from its tag, refuses one tagged less than 24 hours before the gun, and writes a
row here and a race page under `docs/predictions/` with every finisher's
prediction beside their result.

<!-- finishline:live -->
_No prediction has been scored yet. `finishline score <race>` fills a row here once a tagged prediction's official results are posted._
<!-- finishline:end:live -->

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
Each finish is put on one scale as a ratio to a Daniels reference time. A Bayesian
hierarchical model on that ratio gives every runner a fitness level and a distance fade shrunk
toward their age-sex group, and a form that walks from one racing year to the next; every race
gets its course's measured difficulty, a shared effect for its calendar year, and the heat and
wind observed at St. John's airport that morning. A live prediction walks each runner's form
forward to race day and draws the weather from the day-ahead forecast, corrected by how wrong
that forecast was on past race mornings. The design history, including three models the data
refuted, is PLAN.md section 13.
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
