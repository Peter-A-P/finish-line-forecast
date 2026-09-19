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
- **`course[c]`**, how hard the road is, shared by every edition on it.
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

## 5. A prediction

Draws, not a number (`Posterior.predict`). Each posterior draw is a complete version of the
runner, the course and the year; each is walked forward to race day and given a fresh
morning and a fresh bad day, and the median of the resulting finish times is the point
prediction. A runner the archive has never seen is drawn from their sex's age groups,
weighted by the groups of recent first-timers. For a live race the weather
is the day-ahead forecast, with its measured error at this airport added as noise
(`data/forecast_error.toml`); in the backtest it is the observation, which is the kinder of
the two and is said so beside the tables.

## 6. Intervals

The model's own 80% and 90% intervals are checked against races already run and moved until
they hold: split conformal on the log scale, calibrated separately for runners with no, one,
two or three, and four or more prior results, and only ever on races dated before the one
being predicted (`conformal/split.py`). The guarantee is on average over races within a
group, provided a new race behaves like the earlier ones, and that assumption is printed
beside every coverage table.

## 7. Places

The whole field is simulated together many times, with one morning per simulated race
shared by every runner in it, and each runner's place is reported as a median and a range
(`placing/simulate.py`). A hot day slows a field together and changes its order hardly at
all, which ranking independent draws would get wrong.

## 8. Who is running

For a race with a public entrant list (Athletics NorthEAST's, or Trackie's), the list at
freeze time is the field. Each entrant is linked to at most one runner by name key and sex
(`identity/link.py`): one candidate is linked, none is a newcomer, and more than one is
excluded and counted, because the list prints no age to choose between them, unless the list
prints a hometown that exactly one of them was ever printed under. Races without a
list need a participation model, which is not built yet (PLAN.md 5.6).

## 9. The backtest

Every race from 2024 on is predicted from results dated strictly before it (`backtest/`). The
model is fitted once per calendar quarter on the history before the quarter's first day, so
it knows less about a race late in a quarter than the baselines beside it do. Three baselines
are always reported first: the runner's last result carried forward, the best recent result
projected by equal VDOT, and the median of the runner's category. Errors are reported in
minutes and in percent, per history depth, with bootstrap intervals; placing is compared both
as each model ranks its own runners and on the runners both models answered for.

## 10. Freeze and score

`finishline freeze` writes the prediction file, its SHA-256 and the entrant snapshot it used,
and refuses inside 24 hours of the gun. The file is committed and tagged, with the hash in the
tag message; the tag time is the record. After the results are posted, `finishline score`
reads the prediction from its tag, never from the working copy, refuses a late or unhashed
tag, and publishes the errors against the same baselines. Nothing in a prediction file is
edited after its tag; a defect found later is scored as it stands and written up.

The file publishes, per runner, only what results pages already publish: the name as the
start list printed it, the hometown as the results last printed it, and the prediction.
