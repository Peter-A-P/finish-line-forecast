# Finish Line Forecast

Before the gun, a predicted finish time and placing for every registered runner in a
field of thousands, from their public race history, published in advance, with the error
published once the results are in. For a race director that is pacing, corral and medical
staffing planned from expected finish times rather than guesses; for a runner it is a goal
time with an honest interval instead of a hunch.

**Status: building.** Every registered runner in a Newfoundland road race can be given a
finish time, a calibrated range and a likely place before the gun, which is a thing that did
not exist for these races: eighteen years of results pages are parsed, 23,830 runners are
resolved out of them with no runner ID to join on, every course's difficulty is measured from
the finishes, and the whole field is predicted, first-timers included, with the error published
afterwards. Two models do the predicting, a Bayesian hierarchical model and a LightGBM
challenger, and what gets published is the average of the two, which beats both; the weight
between them was chosen on 2022 and 2023 alone, so the races reported here never helped pick
it. Against the strongest simple rule this same machinery can compute, that average is 32%
closer for runners with four or more prior results, 5.0 minutes of mean absolute error against
carry-forward's 7.4, with no bias left to speak of, and it answers for the 30% of a field that
no such rule can answer for at all. No prediction has been made yet. The first live race is the Cape to Cabot 20 km in St. John's
on 2026-10-18, with a second on a frozen model on 2026-11-11; predictions are committed,
tagged and hashed in this repository before each race and scored against the official
results after it. Build plan: [PLAN.md](PLAN.md).

**The website: [finishline.peterparker.ca](https://finishline.peterparker.ca)**, every live
race and its predictions, with the whole method explained in pictures.

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
| Races read | 286 |
| Finishes parsed | 75,061 |
| Runners resolved | 23,830 |
| Runners this refuses to tell apart, and will not publish | 381 |
| Runners with one finish | 12,737 |
| Runners with two or three | 6,280 |
| Runners with four or more | 4,786 |
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
| usr-42195 | 32 | 1 | +11.2% | [+7.5, +14.8] |  |
| huffin-puffin-42195 | 296 | 7 | +9.6% | [+8.3, +10.8] |  |
| provincial-championship-42195 | 68 | 2 | +9.4% | [+6.2, +12.1] |  |
| cape-to-cabot-20000 | 5,311 | 15 | +9.2% | [+9.0, +9.5] | 10.3% average, over the published 550 m of climb |
| run-from-away-42195 | 79 | 1 | +7.8% | [+6.1, +9.6] |  |
| trapline-5000 | 138 | 6 | +6.3% | [-1.9, +15.1] |  |
| bell-island-blast-16093 | 181 | 3 | +4.6% | [+3.8, +5.5] |  |
| trapline-42195 | 55 | 7 | +4.5% | [+0.5, +8.2] |  |
| _... 34 more_ | | | | | |
| five-and-dime-5000 | 1,052 | 10 | -3.0% | [-3.6, -2.4] |  |
| quidi-vidi-5000 | 334 | 4 | -3.2% | [-3.9, -2.4] |  |
| ane-mile-1609 | 577 | 12 | -3.7% | [-5.0, -2.3] |  |
| provincial-championship-5000 | 907 | 8 | -4.0% | [-4.5, -3.5] |  |
| turkey-tea-10000 | 2,296 | 14 | -5.1% | [-5.4, -4.9] | **the published climb cannot explain it** |
| mews-memorial-8000 | 4,893 | 16 | -5.3% | [-5.5, -5.1] |  |
| pearlgate-5000 | 88 | 1 | -5.7% | [-6.8, -4.7] |  |
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
Fitted on 231 editions near St. John's airport, 55 of 286 excluded as too far from it or without an observation. Explains **34%** of the edition-to-edition variance within a course, leaving sd 2.31%.

| Race length | Cost per degree above neutral | What a 20 C morning costs |
|---|---:|---:|
| 5 km | -0.05% | -0.5% |
| 10 km | +0.24% | +2.4% |
| Tely 10 | +0.45% | +4.5% |
| Cape to Cabot 20 km | +0.54% | +5.4% |
| marathon | +0.86% | +8.6% |

Neutral is 10 C and 20 km/h, which is the middle of this archive rather than a laboratory ideal.

| Term | Estimate | 95% CI |
|---|---:|---|
| Temperature at 10 km, per degree | +0.245% | [+0.135, +0.372] |
| Tailwind along the bearing, per km/h | -0.033% | [-0.101, +0.025] |
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
| 0 | 5711 | `carry-forward` | 0% | - | - | baseline |
|  |  | `best-equal-vdot` | 0% | - | - | - |
|  |  | `category-median` | 95% | 18.4 (17.9 to 18.9) | 18% | - |
|  |  | `hierarchical` | 100% | 18.3 (17.9 to 18.8) | 18% | - |
|  |  | `lightgbm` | 100% | 18.6 (18.1 to 19.1) | 17% | - |
|  |  | `blend` | 100% | 18.1 (17.6 to 18.6) | 17% | - |
| 1 | 2713 | `carry-forward` | 100% | 9.6 (9.2 to 10.0) | 10% | baseline |
|  |  | `best-equal-vdot` | 64% | 7.5 (7.1 to 8.0) | 8% | 21% |
|  |  | `category-median` | 96% | 16.1 (15.5 to 16.7) | 16% | -68% |
|  |  | `hierarchical` | 100% | 9.4 (9.0 to 9.9) | 10% | 2% |
|  |  | `lightgbm` | 100% | 8.8 (8.4 to 9.2) | 9% | 8% |
|  |  | `blend` | 100% | 8.7 (8.3 to 9.1) | 9% | 9% |
| 2 to 3 | 2910 | `carry-forward` | 100% | 9.3 (8.9 to 9.7) | 9% | baseline |
|  |  | `best-equal-vdot` | 73% | 7.8 (7.4 to 8.2) | 8% | 16% |
|  |  | `category-median` | 95% | 15.8 (15.2 to 16.4) | 16% | -70% |
|  |  | `hierarchical` | 100% | 8.5 (8.2 to 8.9) | 9% | 8% |
|  |  | `lightgbm` | 100% | 7.7 (7.4 to 8.1) | 8% | 17% |
|  |  | `blend` | 100% | 7.7 (7.4 to 8.1) | 8% | 17% |
| 4 or more | 7490 | `carry-forward` | 100% | 7.4 (7.2 to 7.6) | 8% | baseline |
|  |  | `best-equal-vdot` | 87% | 7.2 (7.0 to 7.4) | 7% | 2% |
|  |  | `category-median` | 95% | 14.0 (13.7 to 14.4) | 18% | -90% |
|  |  | `hierarchical` | 100% | 5.4 (5.2 to 5.6) | 6% | 27% |
|  |  | `lightgbm` | 100% | 5.2 (5.0 to 5.3) | 6% | 30% |
|  |  | `blend` | 100% | 5.0 (4.8 to 5.2) | 5% | 32% |

`lightgbm` against `hierarchical` on the same runners. The difference is in mean absolute error as a percent of each runner's own finish time; negative favours `lightgbm`, and the 95% CI resamples races.

| Prior results | Runners | Races | MAE, minutes, `lightgbm` vs `hierarchical` | Difference, points of a finish time (95% CI) |
|---|---:|---:|---|---|
| 0 | 5,703 | 53 | 18.6 vs 18.3 | +0.67 (-0.85 to +1.60) |
| 1 | 2,707 | 52 | 8.8 vs 9.4 | -0.91 (-1.65 to -0.57) |
| 2 to 3 | 2,904 | 52 | 7.7 vs 8.5 | -1.00 (-1.39 to -0.79) |
| 4 or more | 7,480 | 51 | 5.2 vs 5.4 | -0.39 (-0.59 to -0.21) |

`blend` against `hierarchical` on the same runners. The difference is in mean absolute error as a percent of each runner's own finish time; negative favours `blend`, and the 95% CI resamples races.

| Prior results | Runners | Races | MAE, minutes, `blend` vs `hierarchical` | Difference, points of a finish time (95% CI) |
|---|---:|---:|---|---|
| 0 | 5,703 | 53 | 18.1 vs 18.3 | +0.07 (-1.05 to +0.65) |
| 1 | 2,707 | 52 | 8.7 vs 9.4 | -0.91 (-1.44 to -0.68) |
| 2 to 3 | 2,904 | 52 | 7.7 vs 8.5 | -0.92 (-1.19 to -0.77) |
| 4 or more | 7,480 | 51 | 5.0 vs 5.4 | -0.51 (-0.63 to -0.40) |

`blend` against `lightgbm` on the same runners. The difference is in mean absolute error as a percent of each runner's own finish time; negative favours `blend`, and the 95% CI resamples races.

| Prior results | Runners | Races | MAE, minutes, `blend` vs `lightgbm` | Difference, points of a finish time (95% CI) |
|---|---:|---:|---|---|
| 0 | 5,703 | 53 | 18.1 vs 18.6 | -0.59 (-0.96 to -0.13) |
| 1 | 2,707 | 52 | 8.7 vs 8.8 | -0.00 (-0.12 to +0.23) |
| 2 to 3 | 2,904 | 52 | 7.7 vs 7.7 | +0.08 (+0.02 to +0.20) |
| 4 or more | 7,480 | 51 | 5.0 vs 5.2 | -0.12 (-0.22 to -0.03) |
<!-- finishline:end:baselines -->

**What those baselines cost, and why 32% is not the whole claim.** None of the three rules of
thumb above were lying around to be beaten. "You will run what you ran last time" is trivial for
one runner with one race in front of them and is not trivial for a field of several hundred: it
needs eighteen years of results pages parsed, the same person's results joined across them with
no runner ID to go on, the last race converted to this race's distance through Daniels' tables,
and this course's difficulty measured against every other course in the province. All of that is
this repository, and the baselines are computed by it. The comparison is therefore not this model
against something a runner can look up; it is this model against the best simple answer the same
machinery can give, on the same runners, which is the harder test and the only honest one.

**And a rule of thumb cannot answer for a third of the field.** Over the 53 scored races,
carry-forward can answer for 13,113 of 18,824 entrants (70%) and the race calculator for 10,403
(55%); 5,711 entrants, 30% of the field, have no past result to carry forward at all. The
published model answers for every one of them and reports the error it makes on them, which is
the largest error in the table and is published rather than hidden. A race director planning a
finish-line clock needs the whole field, not the two thirds of it with a history.

**The same error, by race length.** An average in minutes is not one claim across distances, so
the published model's error is broken out both ways: minutes, which a race director plans with,
and the share of a runner's own finish time, which is what compares a 5 km with a marathon.

<!-- finishline:distances -->
`blend`, every race from 2024 on, grouped by race length. The middle column pair is the whole field, the right-hand pair the runners with four or more prior results. The percent is of each runner's own finish time.

| Race length | Runners | Middle of the field | MAE, all | % of time, all | MAE, 4+ races | % of time, 4+ |
|---|---:|---:|---:|---:|---:|---:|
| 5 km | 2,491 | 28.2 | 3.5 | 10% | 1.4 | 5% |
| 8 km | 1,154 | 42.4 | 2.7 | 6% | 1.8 | 4% |
| 10 km | 1,908 | 58.2 | 4.6 | 7% | 2.7 | 5% |
| 16 km (the Tely 10) | 10,901 | 102.6 | 12.7 | 11% | 6.6 | 6% |
| 20 km | 2,017 | 129.3 | 9.5 | 7% | 6.1 | 5% |
| Marathon | 323 | 271.7 | 26.0 | 10% | 17.4 | 6% |
<!-- finishline:end:distances -->

**And the same error by where a runner finishes in their own race.** The front of a field is
predicted more tightly than the back of it, in both units, which a single average hides: a
runner's own day-to-day variation is what the model cannot know, and there is more of it further
back. Runners with four or more prior results only, so these columns differ by speed rather than
by how much history each group happens to have.

<!-- finishline:speeds -->
`blend`, every race from 2024 on, for runners with four or more prior results, by race length and by where they finished in their own race. Each cell is the mean absolute error in minutes and as a percent of the runner's own finish time.

| Race length | Front of the field (fastest quarter) | Mid-pack (middle half) | Later finishers (last quarter) |
|---|---|---|---|
| 5 km | 45 sec, 3.8% (372) | 1.3 min, 5.1% (572) | 3.4 min, 9.8% (158) |
| 8 km | 1.1 min, 3.3% (223) | 1.8 min, 4.2% (336) | 3.1 min, 5.6% (135) |
| 10 km | 1.6 min, 3.6% (319) | 2.5 min, 4.3% (441) | 4.8 min, 6.4% (192) |
| 16 km (the Tely 10) | 3.6 min, 4.7% (1,177) | 6.1 min, 5.9% (1,710) | 13.7 min, 9.3% (585) |
| 20 km | 4.3 min, 4.2% (304) | 6.1 min, 4.7% (555) | 8.5 min, 5.2% (264) |
| Marathon | 10.4 min, 4.8% (39) | 18.8 min, 6.8% (67) | 23.2 min, 6.9% (31) |
<!-- finishline:end:speeds -->

⚠️ **The LightGBM challenger is more accurate than the hierarchical model for every runner with
a history.** Gradient-boosted quantile trees on hand-built features (`models/gbm.py`: form on
the same Daniels scale, history depth and age, course difficulty, the raw weather), refitted
per quarter on the same history, with hyperparameters fixed before the first run. On the same
runners, the paired table above: 0.39 to 1.00 points of a finish time better for runners with
one or more prior results, intervals clear of zero; level for first-timers. It also orders a
field better, 4.2 places closer than carry-forward against the hierarchical model's 1.8. Its
own quantile ranges under-cover at every depth (68 to 74% at 80%) and the conformal layer
repairs them, which is the coverage table below. Its features and parameters were searched on
2022 and 2023 only, never on these races, and that search bought about one percent (PLAN.md
section 13 item 34, which also has the six ideas that made it worse). PLAN.md section 13 item 33
has the detail.

⚠️ **What is published is the average of the two models, not either one, because the average
beats both.** On the log scale, weighted 0.65 towards the challenger: the paired tables above
give 0.4 to 0.6 points of a finish time against the hierarchical model at four or more prior
results and 0.0 to 0.2 against the challenger, and the average is level with the challenger at
one prior result and a fraction behind it at two or three. The weight was read off the 2022 and
2023 races alone (`scratch/blend_weight.py`), where the curve is flat from 0.60 to 0.75 and
resampling races puts the best weight between 0.50 and 0.80; reading it off the races in these
tables would have made them report a number about themselves. The published distribution is
still the hierarchical model's, moved: each runner's posterior draws are multiplied by the one
factor that puts their median on the averaged centre, because a place in a field needs joint
draws of everyone on one shared morning and quantile trees do not give them. A first-timer drawn
from a course's newcomer pool is left out of the average, since that pool is a measurement
rather than either model's guess. `models/blend.py` and PLAN.md section 13 item 35.

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
the year effect and the group means trade off along a ridge that the sampler wanders.
Checked on the worst fit, the quantity a prediction for a returning runner reads converges
(R-hat 1.006 median, 1.08 worst, over 600 runners), so those predictions are not sampler
noise; a first-timer's starting level does not (R-hat up to 1.27), so theirs carry some, and
the conformal layer calibrating first-timers separately is what keeps their intervals
honest. The obvious fix, constraining the year effect, made every chain disagree and was
taken out. No individual coefficient from this fit should be read on its own. PLAN.md
section 13 items 29 and 31 have the detail.

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

Paired on the 18,278 predictions both runs made before the 2026 USR results were added (the
ablation is rerun overnight, and its rows are missing from the tables until then), weather lowers absolute log error by 0.0010
(95% CI -0.0019 to +0.0002), better at every depth and clear of zero only for runners with no
history. That is the size it should be: weather moves the level of a whole field by one to
five percent, individual error is around ten, and a correct level shift is close to invisible
per runner. It is not invisible to a race director planning a finish-line clock, and the check
that matters is the race level. There, the model without weather leaves bias that climbs with
the heat, +0.42 (+/- 0.30) of each point of heat cost left in the errors, and the model with
weather leaves -0.15 (+/- 0.30), which is zero. The previous weather model, linear in
temperature from 10 C, leaves +0.11 (+/- 0.31) on the same measure, so on three years of
backtest races the two weather models cannot be told apart; the case for the felt-heat
shape is eighteen years of editions, in [docs/rejected.md](docs/rejected.md). The 2025 USR, the hottest mornings in the backtest at 22 C, went from 1.0 to 1.4% too
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
| `carry-forward` | 53 | 24.6 | 0.836 |
| `best-equal-vdot` | 52 | 17.6 | 0.838 |
| `category-median` | 46 | 95.4 | 0.349 |
| `hierarchical` | 53 | 50.9 | 0.706 |
| `lightgbm` | 53 | 49.6 | 0.733 |
| `blend` | 53 | 48.7 | 0.728 |

The same runners: each model against `carry-forward`, both ranked among the runners both answered for in each race (races with at least 10 of them). Negative place error and positive Spearman differences favour the model; the 95% CI resamples races.

| Model | Races | Runners | Place error, model vs `carry-forward` | Difference (95% CI) | Spearman, model vs `carry-forward` | Difference (95% CI) |
|---|---:|---:|---|---|---|---|
| `best-equal-vdot` | 51 | 10,377 | 17.9 vs 19.0 | -1.1 (-2.4 to -0.1) | 0.849 vs 0.847 | +0.002 (-0.006 to +0.010) |
| `category-median` | 44 | 12,427 | 68.9 vs 27.9 | +41.1 (+20.3 to +66.9) | 0.368 vs 0.852 | -0.484 (-0.536 to -0.439) |
| `hierarchical` | 51 | 13,081 | 23.7 vs 25.5 | -1.8 (-3.1 to -0.7) | 0.857 vs 0.849 | +0.008 (-0.005 to +0.023) |
| `lightgbm` | 51 | 13,081 | 21.3 vs 25.5 | -4.2 (-6.7 to -2.0) | 0.875 vs 0.849 | +0.027 (+0.016 to +0.037) |
| `blend` | 51 | 13,081 | 21.3 vs 25.5 | -4.1 (-6.7 to -2.0) | 0.876 vs 0.849 | +0.027 (+0.015 to +0.039) |
<!-- finishline:end:placing -->

⚠️ **Read the second table, not the first.** The first ranks each model among the runners it
answered for, so carry-forward is ranked over the 13,113 runners who have a prior result and
the model over the whole field, the 5,711 entrants with no history included, whose order is
close to a guess. That is where its 50.9 comes from. The second ranks both over the same
runners, race by race: there the model is 1.8 places better than carry-forward (95% CI 0.7 to
3.1), 23.7 against 25.5, with Spearman 0.857 against 0.849. It orders a field better than the
baseline, by less than it times one. Both tables stay, because scoring each model only on the
subset that suits it is how a table stops being checkable.

**How often the intervals hold.** A predicted time with an interval is two claims, and the
second one is checked here: the model's own 80% and 90% intervals, and the same intervals
after conformal adjustment on the races before each one, by how much history a runner has.

<!-- finishline:coverage -->
`blend`, every race from 2024 on. Each race's intervals are adjusted using only races dated before it, separately for each history depth. Coverage is the share of runners whose finish fell inside; the 95% CI resamples races, not runners, because runners in one race share its morning.

| Prior results | Level | Runners checked | Races | Model's own interval | After conformal | Median width, minutes (own to conformal) |
|---|---:|---:|---:|---|---|---|
| 0 | 80% | 5,641 | 51 | 77% (75 to 81) | 78% (74 to 84) | 52.1 to 52.8 |
| 1 | 80% | 2,648 | 47 | 75% (73 to 78) | 74% (69 to 79) | 20.8 to 20.4 |
| 2 to 3 | 80% | 2,835 | 47 | 74% (71 to 77) | 77% (75 to 79) | 18.4 to 19.8 |
| 4 or more | 80% | 7,380 | 50 | 80% (77 to 82) | 77% (74 to 80) | 13.4 to 12.2 |
| 0 | 90% | 5,641 | 51 | 87% (85 to 90) | 89% (85 to 93) | 67.9 to 72.6 |
| 1 | 90% | 2,648 | 47 | 85% (83 to 87) | 88% (85 to 90) | 28.5 to 31.4 |
| 2 to 3 | 90% | 2,835 | 47 | 84% (82 to 87) | 88% (87 to 90) | 24.7 to 28.2 |
| 4 or more | 90% | 7,380 | 50 | 89% (87 to 91) | 88% (86 to 90) | 18.3 to 17.2 |

`hierarchical`, every race from 2024 on. Each race's intervals are adjusted using only races dated before it, separately for each history depth. Coverage is the share of runners whose finish fell inside; the 95% CI resamples races, not runners, because runners in one race share its morning.

| Prior results | Level | Runners checked | Races | Model's own interval | After conformal | Median width, minutes (own to conformal) |
|---|---:|---:|---:|---|---|---|
| 0 | 80% | 5,649 | 51 | 77% (75 to 79) | 78% (73 to 82) | 54.4 to 55.2 |
| 1 | 80% | 2,654 | 47 | 73% (70 to 75) | 77% (73 to 79) | 20.9 to 23.3 |
| 2 to 3 | 80% | 2,841 | 47 | 71% (68 to 74) | 78% (76 to 82) | 18.4 to 22.8 |
| 4 or more | 80% | 7,390 | 50 | 77% (74 to 79) | 77% (75 to 79) | 13.4 to 13.6 |
| 0 | 90% | 5,649 | 51 | 87% (86 to 89) | 89% (86 to 91) | 70.8 to 74.2 |
| 1 | 90% | 2,654 | 47 | 84% (82 to 85) | 89% (87 to 90) | 28.8 to 34.4 |
| 2 to 3 | 90% | 2,841 | 47 | 82% (80 to 84) | 88% (86 to 89) | 24.9 to 29.8 |
| 4 or more | 90% | 7,390 | 50 | 87% (85 to 88) | 88% (87 to 90) | 18.2 to 19.0 |

`lightgbm`, every race from 2024 on. Each race's intervals are adjusted using only races dated before it, separately for each history depth. Coverage is the share of runners whose finish fell inside; the 95% CI resamples races, not runners, because runners in one race share its morning.

| Prior results | Level | Runners checked | Races | Model's own interval | After conformal | Median width, minutes (own to conformal) |
|---|---:|---:|---:|---|---|---|
| 0 | 80% | 5,649 | 51 | 74% (70 to 77) | 80% (76 to 84) | 52.1 to 59.2 |
| 1 | 80% | 2,654 | 47 | 71% (67 to 77) | 76% (72 to 81) | 20.6 to 22.6 |
| 2 to 3 | 80% | 2,841 | 47 | 68% (65 to 73) | 77% (74 to 82) | 17.3 to 20.6 |
| 4 or more | 80% | 7,390 | 50 | 70% (66 to 75) | 77% (72 to 82) | 11.2 to 12.9 |
| 0 | 90% | 5,649 | 51 | 85% (83 to 88) | 89% (86 to 92) | 68.3 to 74.8 |
| 1 | 90% | 2,654 | 47 | 83% (80 to 86) | 87% (85 to 90) | 27.9 to 30.8 |
| 2 to 3 | 90% | 2,841 | 47 | 81% (78 to 86) | 87% (85 to 91) | 24.2 to 28.7 |
| 4 or more | 90% | 7,390 | 50 | 82% (79 to 85) | 88% (85 to 91) | 15.8 to 18.3 |

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
forward to race day and draws the weather from the forecast, corrected by how wrong that
forecast was on past race mornings at the same lead. The design history, including the models
the data refuted, is PLAN.md section 13; [docs/methods.md](docs/methods.md) is the short
version.
Intervals are conformalised on rolling-origin residuals, stratified by how many results a
runner has. Placing is simulated from the whole field's predictive distributions, and at the
biggest races the runners with no results here are drawn from how that course's past
first-timers finished. From a week before a race, each registered runner is predicted the
first morning they appear on the entrant list; the day before, the whole field is predicted
again with the latest forecast and given places. Every file is committed, tagged and hashed
before the gun and scored after, and the website (`finishline site`, rebuilt on every push)
shows them with a search box for anyone looking for their own name.

## Part of a portfolio

One of fifteen projects. The running arithmetic is borrowed from
[Overload](https://peterparker.ca/projects/overload/), Peter's AI coaching team for runners:
Daniels' VDOT, the heat and wind corrections and the age-grading tables, here in a public
repository with tests. Constants that came across from Overload, including the full-sun
figure it takes from the US National Weather Service, are used as priors and labelled as
priors wherever they appear; anything this archive can measure is measured here instead, and
PLAN.md section 13 item 30 has what the measurement said about that figure.

## How this was built

Design, methodology, evaluation choices and judgement are Peter Parker's, including years
of racing and coaching himself on these courses. Two of those calls are in the model: that
the Tely's prevailing westerly is a tailwind for almost the whole race, and that heat does
not act in a straight line. The weather model is the clearest case. Four reasonable designs
failed first, heat as a straight line, humidity, dew point and sunshine as an effect of its
own; what worked was the specification that came off the road rather than out of the data.
Below a threshold heat costs nothing, above it each degree costs more than the last, and it
costs more the longer the race; sunshine has no effect of its own but raises the temperature
a runner feels. Written that way it explains about twice as much of the edition-to-edition
variation as the straight line did (PLAN.md section 13 item 30). AI coding
assistants (Claude Code) were used for implementation and drafting, the way a senior
engineer uses them in 2026. Every
number in the results tables is reproducible from this repository with one command, and
every live prediction is verifiable from a tag that predates the race it predicts.
