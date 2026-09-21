# Methods

How a prediction is made, in the order the pipeline makes it. Each step names the module
that does it; the module's own docstring has the detail and the reasons, and
[PLAN.md](../PLAN.md) section 13 has every design the data refuted on the way here. Nothing
below is a claim about accuracy: the numbers are in the [README](../README.md), each with its
interval.

## 1. Results

Every individual road race on the Newfoundland and Labrador Athletics Association's results
pages from 2008 to 2026, fetched once at one request a second and kept in a local cache
(`ingest/nlaa.py`). Pages are fixed-width text with no column contract, so the parser reads
the header row of each page and refuses a page it cannot read rather than guessing; five of
288 are refused and named in [data-terms.md](data-terms.md). Each edition is assigned a
course: the event name with the sponsor and the ordinal stripped, plus the distance, because
a race offering 5 km and 10 km runs two roads. Where one road ran under several names, or one
name over two roads, a short table says so (`nlaa.SAME_ROUTE`).

## 2. Who is who

The archive has no runner identifier, so results are joined into runners by name, sex and
the birth years each printed age band allows (`identity/resolve.py`). The resolver is
asymmetric on purpose: splitting one runner into two costs accuracy, merging two into one
publishes a confident prediction built from somebody else's results, so where two results
cannot be told apart it refuses, marks the runner ambiguous, and they are excluded from
every published file and counted.

## 3. The scale

Every finish time is divided by what a runner of VDOT 50 would run at that distance on
Daniels' tables (`metrics/daniels.py`), and the model works on the log of that ratio. A 5 km
and a marathon are then on one scale before anything is fitted, and 0.05 means five percent
of a finish time wherever it was run.

The scale is a reference, not a claim that this population runs Daniels' curve. It does not
quite: measured against the reference, the marathons on this archive read about eight points
harder than the 5 km races, which is a field that has not trained for the distance rather
than a province of hilly marathons. A per-runner fade coefficient (`beta_i`, section 4) takes
part of it, and what is left is in the course effects of the long courses. Section 13 item 36
has the size of it and what it does and does not reach.

## 4. The model

A hierarchical Bayesian model, fitted with PyMC and the nutpie sampler
(`models/hierarchical.py`). For runner `i` at edition `r`:

    log(time / Daniels time) = alpha_i + beta_i * log(d / 10 km) + walk_i[year]
                               + course[c] + year[t] + heat and wind + edition + noise

- **`alpha_i`, fitness in the runner's first year**, drawn from their age-and-sex group
  (decade and sex at their first race). Most runners have one or two results, so this
  shrinkage is most of what a prediction for them is.
- **`beta_i`, how this runner fades with distance** beyond Daniels' curve; zero for anyone
  who has raced one distance.
- **`walk_i`, form**, a random walk over the calendar years the runner raced, drifting with
  their group's ageing. Races in one year share the year's level, and a runner last seen
  years ago is walked forward with a spread that grows with the gap.
- **`course[c]`**, how hard the road is, shared by every edition on it. ⚠️ It carries one
  thing that is not the road: the population's own departure from Daniels' fade at that
  distance. Every course is run at one distance, so the two cannot be separated from
  finishes, and the difference lands on the courses that are long. It is harmless in a
  prediction, because a course effect is only ever applied to that course at its own
  distance, but it means a factor is comparable only with other courses of the same length,
  which is what `CourseFactor.versus_peers` and the columns in the website's course chart
  report. PLAN.md section 13 item 36.
- **`year[t]`**, what every race in a calendar year shared, as a walk from year to year.
  A steady drift here cannot be fully told apart from ageing or from later starters being
  slower, and the sampler mixes poorly along that line; PLAN.md section 13 item 31 has what
  that does and does not reach in a prediction, and a constraint that was tried and made it
  worse.
- **Heat and wind**, from the hourly observations at St. John's airport over the hours the
  field was out, from each race's published start (`models/weather.py`, `data/starts.toml`).
  Heat is the felt temperature above 12 C, where the sun adds a number of degrees the model
  estimates, and its cost per degree grows with distance; wind is a speed, and on the two
  point-to-point courses with a known bearing also a tailwind. Races too far from the airport
  carry no weather term. [rejected.md](rejected.md) is the straight-line design this replaced.
- **The edition**, what is left of that morning, and **noise**, a Student-t with heavy
  tails, because a bad day is not Gaussian.

Priors are weak on the log scale, and the few constants taken from elsewhere (Daniels'
tables, the 12 C knee, the prior scale for the sun from the US National Weather Service's
15 F) are named where they are used.

## 5. The second model, and the average that publishes

A LightGBM quantile challenger runs beside the hierarchical model on the same information
(`models/gbm.py`): form on the same Daniels scale, history depth and age, course difficulty and
the six raw weather features, seven quantiles from pinball loss, refitted per quarter. It is
more accurate than the hierarchical model for every runner with a history (PLAN.md section 13
items 33 and 34).

What publishes is neither model alone but the average of the two on the log scale
(`models/blend.py`, PLAN.md section 13 item 35):

    log(published) = 0.35 * log(hierarchical) + 0.65 * log(challenger)

The distribution stays the hierarchical model's, moved. Each runner's draws are multiplied by
the one factor that puts their median on the averaged centre, because a place in a field needs
joint draws of everyone on one shared morning and seven quantiles per runner cannot give them;
their whole range moves with their time, so a published time and a published place are the same
prediction. The conformal layer then calibrates on the average's own errors, not the
hierarchical model's. A newcomer drawn from a course's first-timer pool (section 8) is left out
of the average, since that pool is a measurement rather than either model's guess.

The weight was read off the 2022 and 2023 races alone (`scratch/blend_weight.py`), the same
window the challenger's own settings were tuned on, so that the races the backtest scores
(section 10) never helped choose it. On that window the best weight was 0.65, the curve was flat from 0.60
to 0.75, and resampling races put it between 0.50 and 0.80.

## 6. A prediction

Draws, not a number (`Posterior.predict`), moved onto the averaged centre as section 5
describes. Each posterior draw is a complete version of the
runner, the course and the year; each is walked forward to race day and given a fresh
morning and a fresh bad day, and the median of the resulting finish times is the point
prediction. A runner the archive has never seen is drawn from their sex's age groups,
weighted by the groups of recent first-timers. For a live race the weather
is the day-ahead forecast, with its measured error at this airport added as noise
(`data/forecast_error.toml`); in the backtest it is the observation, which is the kinder of
the two and is said so beside the tables.

## 7. Intervals

The model's own 80% and 90% intervals are checked against races already run and moved until
they hold: split conformal on the log scale, calibrated separately for runners with no, one,
two or three, and four or more prior results, and only ever on races dated before the one
being predicted (`conformal/split.py`). The guarantee is on average over races within a
group, provided a new race behaves like the earlier ones, and that assumption is printed
beside every coverage table.

## 8. Places

The whole field is simulated together many times, with one morning per simulated race
shared by every runner in it, and each runner's place is reported as a median and a range
(`placing/simulate.py`). A hot day slows a field together and changes its order hardly at
all, which ranking independent draws would get wrong.

At the few biggest races, where visitors with no results here reach the top ten, a newcomer is
drawn from how first-timers at earlier editions of the same course finished against the
returning field, rather than from the group prior (`placing/unseen.py`). It cannot say which
newcomer will be fast, so the race page shows the places they are expected to take as
placeholders, with the expected count and its range.

## 9. Who is running

For a race with a public entrant list (Athletics NorthEAST's, or Trackie's), the list at
freeze time is the field. Each entrant is linked to at most one runner by name key and sex
(`identity/link.py`): one candidate is linked, none is a newcomer, and more than one is
excluded and counted, because the list prints no age to choose between them, unless the list
prints a hometown that exactly one of them was ever printed under. Races without a
list need a participation model, which is not built yet (PLAN.md 5.6).

Which races exist at all comes from the association's own calendar of events
(`ingest/calendar.py`), read by `finishline calendar` into `data/calendar.json`, so the
website's race list is the season rather than whatever was last typed into `data/live.toml`.
A calendar entry is a day and not a race: "Uniformed Services Run
Marathon/Half-Marathon/Marathon Relay/5km/10km" is one row and five races, which is why an
entry carries a course family and a date and no distance. Road races this project does not
predict are listed with the reason rather than left out.

## 9b. A race that ran with no prediction tagged

The Uniformed Services Run of 2026-09-13 ran between the first entrant-list snapshot and the
first freeze. It is on the website and it is **not a prediction**: nothing was tagged before
its gun, so it is not in the public record and is not scored. What is shown is the
rolling-origin backtest's own rows for that race, which are held out by construction, from a
fit that saw no result from the quarter the race falls in or later. Its file is
`data/retrospect/<race>.json`, never `predictions/`, and it carries no hash and no tag
(`publish/retrospect.py`, PLAN.md 5.9). Only an event whose course has an earlier edition is
scored, because a road the model has never seen has no course factor and the error there is
mostly the cost of that; the unscored events of the same day are listed with the reason. The
order behind the place error there is the rank of the predicted times and has no range,
because a published place needs a posterior and the backtest kept its scored rows rather than
its fits, so no absolute predicted place is printed for a runner at all.

Every finisher is in the runner table, and the only place printed is the place in the race
that was run. A finisher the resolver would not commit to is tagged "(potential duplicate)"
with its reason behind the tag, has no prediction, and reaches none of the figures: showing
somebody and scoring them are different jobs, and the place error is measured over the
predicted runners ranked among themselves so that a runner the archive cannot identify
neither helps nor hurts the model (PLAN.md 13 item 38). "Out by" is the finish minus the
prediction, so a runner who took two minutes longer than the model called reads +2:00; that
is the opposite sign to `score.Scored.error` and to the bias tables, which are read on the
model rather than on the runner, and the flip happens at the last step before the page.

The gender and age group in that table come from this race's own page where it has them, and
are borrowed where it does not. The club's finish lists print neither, nor a hometown, so for
the USR they are what the association's own results last printed for that runner before this
race, public on nlaa.ca under the same name, with the race and date they were printed at on
the page. Only results before the race count, a band the runner has certainly grown out of
since is left blank rather than aged forward (`retrospect.still_possible`, from the resolver's
own birth-year windows), and a finisher with no prediction gets neither column, because the
row exists to say this project does not know which runner it is.

**A race read from outside the association gives way the moment the association posts it**,
and that is the one swap that changes what may be published about a runner. `store.build` has
always dropped an outside copy where nlaa.ca carries the same date and course, so no edition
is counted twice; `store.borrowed` now says which races that has happened to, and
`finishline dataset` prints it every run. On the day the USR is republished, its own page
carries a sex, an age band and a hometown, `retrospect.printed_category` reads those instead
of borrowing, and the page says so without anything here being edited.

## 10. The backtest

Every race from 2024 on is predicted from results dated strictly before it (`backtest/`). The
model is fitted once per calendar quarter on the history before the quarter's first day, so
it knows less about a race late in a quarter than the baselines beside it do. Three baselines
are always reported first: the runner's last result carried forward, the best recent result
projected by equal VDOT, and the median of the runner's category. Errors are reported in
minutes and in percent, per history depth, with bootstrap intervals; placing is compared both
as each model ranks its own runners and on the runners both models answered for.

## 11. Freeze and score

From seven days before the race, `finishline freeze --daily` publishes a file a day with the
entrants no earlier file predicted, each with that morning's forecast at that lead; the day
before, the final file recomputes everyone with the day-before forecast and gives places
(`publish/daily.py`). One fit serves the whole week, and each entrant's random
numbers are seeded by their name, so a runner's prediction is the same whichever day computes
it. `finishline freeze` writes each file, its SHA-256 and the entrant snapshot it used,
and refuses inside 24 hours of the gun. The file is committed and tagged, with the hash in the
tag message; the tag time is the record. After the results are posted, `finishline score`
reads the prediction from its tag, never from the working copy, refuses a late or unhashed
tag, and publishes the errors against the same baselines. Nothing in a prediction file is
edited after its tag; a defect found later is scored as it stands and written up.

The file publishes, per runner, only what results pages already publish: the name as the
start list printed it, the hometown as the results last printed it, and the prediction.
