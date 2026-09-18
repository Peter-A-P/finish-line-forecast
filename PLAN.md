# Plan: Finish Line Forecast

**Written:** 2026-09-12. **Status as of 2026-09-16:** weeks 1 and 2 built, and the
hierarchical model is built and converges on the real archive; its backtest is running.
The archive is read and resolved, the three baselines are measured, every course's
difficulty is measured from the results with the physics as a cross-check, and the
conditions layer is fitted. Built since: Mondrian conformal intervals, the placing
simulation, the start-list linker, the prediction file, `freeze` and `score`. **Still to
build:** the hierarchical model's backtest table (running), the conditions layer wired into
the model's race effect (section 13 item 27), the LightGBM challenger, and the participation
model.

**Section 13 is the log of what the data refuted**, and it is the first thing to read after
this line: twenty-nine numbered entries, each one a design in this plan that measurement
overturned. What is open and who owns it is in [docs/todo.md](docs/todo.md).

**Build:** an alongside project, so planned in relative weeks. Earliest start: now. It waits
for nothing in the portfolio. The first live target fixes the calendar: **Cape to Cabot 20 km,
St. John's, Sunday 2026-10-18**, five weeks out, with **Run to Remember 11 km, 2026-11-11** as
the second live race on a frozen model and the **Tely 10 (June 2027, capped at 4,466)** as the
"field of thousands" race in Part B. **Package:** `finishline`. **Repository:**
`Peter-A-P/finish-line-forecast`, private until the backtest table is in. **Fed by:** 11 (Overload), whose Daniels,
heat, wind, course-bearing and age-grading modules are copied across with attribution and
with every personal calibration detail stripped. **Feeds:** nothing.

This project calls no language model, so neither the 04 gateway nor the 03 gate is on its
path. Every number below comes either from a rolling-origin backtest over public race
results, with bootstrap intervals, or from a prediction that was committed, tagged and
public before the race it predicts.

> **The pre-registration is the point.** Every other project in the portfolio proves its
> number with a backtest a sceptic has to trust. This one commits its predictions to a
> public repository, with a tag and a hash, before the gun, and scores them against the
> official results after. The backtest exists to size the intervals and to fill the tables
> while waiting for a race; the live record is the deliverable.

---

## 0. The data-terms check, and what it changed

The project file said to check the Strava API agreement and each results provider's terms
before any code. Done 2026-09-12; the outcome reshapes step 3 of the original idea.

| Source | Finding (checked 2026-09-12) | Consequence |
|---|---|---|
| **Strava** | API Agreement effective 2026-06-01, section 2.3: "Strava Data related to other users, even if such data is publicly viewable on the Strava Platform, may not be displayed or disclosed." Section 5.1 forbids sharing a user's data with other users or third parties without explicit consent. The November 2024 revision, restated in the 2026 developer programme, forbids using API data to train AI or machine-learning models. The Acceptable Use Policy forbids collecting or harvesting information about identifiable individuals and any automated scraping. Public profile pages are being moved behind login. Standard-tier API access now requires a paid Strava subscription (about US$11.99 a month) per developer. | **Scanning registered runners' Strava profiles is out**, by API and by scraping alike. The only compliant use is **opt-in**: a runner authorises the app through OAuth, sees a prediction that uses their own training data, and nobody else does. That is deferred to Part B (section 12) and the public table never uses Strava. The plan's headline model works from public race results, which is the weaker but still checkable model the project file anticipated. |
| **NLAA results** (nlaa.ca) | Public HTML pages under `/results/rr/YYYY/`, one per race, results in a fixed-width `<pre>` block: place, bib, name (club in brackets), time, sex and sex place, age category, category place, hometown. The Tely 10 pages add gun time, chip time and pace per mile. 26 road events in 2025, 25 in 2024, results back to 1978. Footer "Copyright NLAA"; no terms of use page; no `robots.txt`. A Google custom search box, no runner profiles. | Usable as public data, with courtesy. **Peter emails NLAA** (athletics@nlaa.ca) and Athletics NorthEAST (admin@athleticsnortheast.com) before the crawler runs, saying what is fetched and how it is used; the crawl is one request a second, cached locally, never re-fetched once stored, and raw pages are never committed. Predictions publish only what the results already publish: name and hometown as printed. |
| **Registration lists** | **Athletics NorthEAST publishes live entrant lists** on its Zen Cart store (`athleticsnortheast.com/cart/index.php?main_page=page&id=4` for Cape to Cabot, `id=1` for the Uniformed Services Run), "up-to-the-minute". Cape to Cabot on 2026-09-12: 453 names with gender and shirt size (266 male, 187 female) against a cap of 500. USR on 2026-09-12, by event: marathon 79, half 277, relay 44, 10 km 272, plus kids and family runs; names only, some with a service affiliation. Neither page carries a privacy statement. Run to Remember: no list found. Tely 10: Trackie registration with a per-person confirmation lookup (first name, last name, city), not a list. The Wayback Machine holds no past editions of the ANE lists. | **Entrant-list mode is the primary mode for the two ANE races.** Gender from the Cape to Cabot list helps resolution and the cold-start group prior. Shirt size is a body-size proxy and is **not used**, by decision (section 2.8): it is not something the results publish about a runner. The lists are snapshotted daily from now (first snapshots saved 2026-09-12, gitignored) so the registered-versus-finished rate and the list-to-results name-match rate are measured on the USR of 2026-09-13 for free, before Cape to Cabot needs them. **Field-forecast mode** stays for races with no list (Run to Remember): predict for every runner in the eighteen-month history whose participation probability clears a threshold, and report coverage. |
| **Weather** | Open-Meteo forecast and archive APIs: free, no key, hourly temperature, wind speed and direction at 10 m, cloud and direct radiation. Already the weather source in 11, **which measured its modelled temperature about 6 °C off at this coast**. Environment and Climate Change Canada publishes hourly observations for St. John's Intl A (station 50089, climate ID 8403505) as a bulk CSV per month, no key; checked 2026-09-12: the 2025 Cape to Cabot morning read 8 °C, 100% humidity, wind 34 to 36 km/h from the north-east at the airport. | ECCC observations are the archive for the backtest's conditions factors, with Open-Meteo's archive as the comparison and the difference reported. The **forecast** (there is no observation of the future) comes from Open-Meteo, pulled at a fixed time before the gun and recorded with the prediction. Both are free for this use; recorded in `docs/data-terms.md`. |
| **Course profiles** | No official GPX found for the target courses. Cape to Cabot publishes the route (Cape Spear to Cabot Tower) but the elevation page is gone. Elevation from Open-Meteo's elevation API or Open Topo Data (SRTM/Copernicus 30 m) against a route Peter traces once in a mapping tool. | Course geometry is an input file per course, committed, with its provenance. The physics course factor built from it is a **prior**, not the estimate; the race-day effect is estimated from results (section 5.3). |

Everything in this table goes into `docs/data-terms.md` in the repository, with the dates,
and the project file in the plan records the outcome in one line.

### 0.1 Other sources looked at, with Strava gone

Asked 2026-09-12: what else, public and permitted, says something about how fast a
registered runner is? The answer is mostly "more race results, from more places", plus
better inputs for the corrections. Nothing replaces training data; several sharpen the
model.

| Source | What it adds | Verdict |
|---|---|---|
| **NLAA cross-country and track results** (12 and 16 events a year on nlaa.ca, HyTek meet format, a different parser) | Extra fitness observations for the runners who also race XC or track: mostly the front of the field and juniors. Course-dependent, so they enter as observations with their own race-edition effect | Part A if week 1 has room, else Part B; a second parser, not a second source |
| **NLAA Toyota Plaza series standings** (per runner: points in each of the twelve series races) and **provincial road rankings** (best time per distance, by sex and age group, 2016 to 2025) | The standings are a per-runner participation record for the year, which is exactly the participation model's feature; the rankings are a consistency check on entity resolution, since NLAA already compiles best-per-runner and asks for consistent name spelling | Part A: standings as participation features; rankings as a resolution check |
| **Cape to Cabot's own archive** (PDF results 2007 to 2025, searchable sheets for 2024 and 2025) | Nineteen editions of one course, for the course factor and its year-to-year variance, deeper than the NLAA pages | Part A: the course-factor prior for the first live race; PDFs parsed once, cached |
| **Huffin' Puffin marathon and half** (September, St. John's; not NLAA-sanctioned in 2024 or 2025; its results site refused connections on 2026-09-12) | Another local half and full each year | Part B, if the site comes back; not on the path |
| **Away races by NL runners**: Boston (public results by state and province), Sportstats (athlete search by name; Bluenose, PEI, Toronto, Ottawa), Athlinks (aggregator, JavaScript app, terms not readable without a browser) | Marathon and half histories for the runners who travel, who are also the ones with the most local results already | Part B at most. Terms unread for Sportstats and Athlinks; Boston is a small number of runners |
| **Trail and ultra results** (ECT 50 and Steep Ultra on Ultrasignup and own sites; the Figure 8 on nlaa.ca) | Endurance signal for a handful of runners; courses too variable to normalise | No for Part A; the Figure 8 is excluded with the other trail results |
| **parkrun** (Corner Brook only; weekly 5 km with per-athlete pages) | Nothing for the Avalon races, and parkrun's terms forbid scraping | No |
| **Registration list fields**: gender, shirt size, service affiliation on the USR list | Gender: resolution and cold-start prior. Shirt size: a body-size proxy that Vickers and Vertosick found predictive through BMI | Gender yes. Shirt size **no**: the model publishes only what results publish, and a public finish-time prediction that leaned on a T-shirt size is not one anyone would thank us for |
| **Course geometry**: NRCan High Resolution DEM (lidar, open licence) and Open Topo Data for elevation over a traced route | A better grade profile than SRTM on Signal Hill's cliffs | Part A for the two live courses |
| **Registered-versus-finished history** via the Wayback Machine | Would have given past no-show rates | Nothing archived; the daily snapshots from 2026-09-12 start the record |
| Social media, race photos, club membership rolls | Would identify and profile people | No, on principle: harvesting, not publishing |

## 1. What this produces

Before the gun, a predicted finish time and placing for every runner expected at a
Newfoundland road race, from their public race history alone, with an interval that says
how sure it is, published and hashed before the start, and the error published once the
results are in.

The numbers a stranger can check:

| Number | What it shows |
|---|---|
| **Live: finish-time error on Cape to Cabot 2026**, MAE in minutes and as a percentage of finish time, model against the carry-forward baseline, bootstrap 95% CI over runners | The headline. Made before the outcome existed, verifiable from the tag's timestamp and the hash |
| **Live: interval coverage and width** at 80% and 90% nominal on the same race, overall and by history depth (0, 1, 2 to 3, 4 or more prior results) | Whether "honest interval" was honest, and where |
| **Live: placing error**, mean absolute place error and Spearman correlation between predicted and actual finishing order, with CIs | The race director's number: was the order right, not just the times |
| **Live: coverage of the field**, the share of finishers who had a published prediction, the share of published predictions who finished (the no-show rate), and the share of entrants resolved to any prior result | What the entrant list gave, what it missed (late entries, no-shows) and how many runners had no history at all |
| The same four rows for **Run to Remember 2026** on the frozen model | A second race, so the first is not a lucky draw |
| **Backtest: the same metrics over every NLAA road race from 2024 to 2026**, rolling origin, each race predicted from results strictly before it; skill against carry-forward; per history-depth stratum | The volume of evidence behind the interval widths, and where the model has nothing to say |
| **Ablation: MAE with and without the course-and-conditions normalisation**, and the estimated **course factor per NL course** with CIs (how much slower a 20 km on Cape to Cabot is than on the flat) | Whether the running domain knowledge earned its place, in minutes |
| **Hierarchical model against the gradient-boosting challenger**, paired MAE difference with CI, per stratum | Which model class wins on sparse histories, said with a number |

Every number carries an interval. The live rows are empty until the race; the README says so
and says when.

## 2. Design decisions

### 2.1 Public race results only, and said out loud

Section 0 settles it. The public model uses nothing a runner has not already had published
about them by the race. That is weaker than a model with training data, and the README's
honest limitation says so in its first sentence. It is also what makes the predictions
publishable at all.

### 2.2 The prediction is committed before the gun, or it does not count

A prediction file per race: one row per runner, predicted time, 80% and 90% intervals,
predicted place range, the forecast conditions used, the model version. Committed to the
public repository and tagged (`predictions/c2c-2026`) no later than 24 hours before the
start; the SHA-256 of the file goes into the README and the tag message. The repository
must therefore be public before the first live race, which Rule A allows because the
backtest table is a measured result. A prediction made or altered after the tag is not a
prediction and is never reported as one.

### 2.3 Baselines first

Three, reported before anything cleverer:

1. **Carry-forward.** The runner's most recent result, converted to the target distance by
   Riegel's power law with the exponent banded as 11 does it.
2. **Best recent equal-VDOT.** The best Daniels VDOT in the last eighteen months, projected
   to the target distance by equal VDOT (11's default projection). This is what every
   online calculator does and what most runners do in their heads.
3. **Category median.** The median finish time of the runner's age and sex category at the
   same race the previous year. The cold-start answer for a runner with no history, and
   the floor everything is measured against.

Every later number is reported as skill relative to carry-forward.

### 2.4 Normalise history for course and conditions before modelling

A 45-minute 10 km on a flat course in October and a 45-minute 10 km up Signal Hill in July
are not the same fitness. Every historical result is converted to a **neutral-condition
equivalent**: the time the runner would have posted on a flat, cool, still course. The
factors are multiplicative on time, the way 11 applies them:

- **Course.** A per-race-edition effect estimated inside the hierarchical model (section
  5.3), with a physics prior from the course profile: Minetti's energy cost of running by
  gradient, integrated along the traced route. 11 uses Strava's Grade Adjusted Pace, which
  is unavailable here, so this project owns its own grade model and tests it.
- **Heat.** Daniels' table 10.1 as 11 encodes it: 0.15% of time per degree Fahrenheit
  above 60, with the sun bonus from direct radiation. Temperature at the start hour from
  Open-Meteo's archive at the start line.
- **Wind.** 11's drag model integrated over the course's bearing histogram, with 11's
  calibrated constant carried across as a prior and flagged as what it is: fitted on one
  athlete's training runs. Section 9 expects it to matter on Cape to Cabot and the Tely 10,
  both exposed coastal courses, and to be nearly invisible elsewhere.

For the target race the same factors run forwards on the forecast pulled at a fixed time,
and the published prediction shows both the conditions-adjusted time and the neutral one,
so a reader can see what the weather cost.

### 2.5 A hierarchical model over sparse histories, with a challenger allowed to win

Most NL runners have one to four results in eighteen months. The model that respects that
is a Bayesian hierarchical model on log finish time (section 5.3): per-runner fitness
shrunk toward their age-sex group, a per-runner fitness trend, a per-runner endurance
exponent shrunk toward the population's (Vickers and Vertosick found Riegel's single
exponent ten minutes optimistic for half of marathoners, so the exponent is a parameter,
not a constant), and a per-race-edition effect with the physics prior. A gradient-boosting
quantile model on engineered features is the challenger. It is expected to win on runners
with deep histories and lose on the sparse majority; whichever way it falls is reported.

### 2.6 Conformal intervals, stratified by how much is known

Both models' intervals are calibrated by split conformal prediction on the rolling-origin
residuals, Mondrian by history-depth stratum, because a runner with six results and a
runner with one do not deserve the same width. Coverage is reported per stratum, and the
assumption (exchangeability of residuals within a stratum across races; violated when the
field composition shifts) is stated beside the coverage table, not glossed.

### 2.7 Placing is simulated, not ranked

Predicted place comes from sampling the whole field from each runner's predictive
distribution and counting, which gives a place interval and respects that a close field
makes places uncertain even when times are not. Ranking point predictions would report a
false certainty.

### 2.8 Names are public data and are treated with care anyway

Predictions name a runner exactly as the results already name them (name and hometown as
printed by NLAA), with no age beyond the printed category and nothing else. A runner who
asks to be removed is removed from every future prediction file, and `docs/data-terms.md`
says how to ask. No profile is built or published beyond the prediction row; the resolved
history behind it stays in the local cache. The entrant lists are used for who is running
and, where printed, sex; the shirt size they also print is never read into the model
(section 0.1), and the list snapshots are gitignored.

### 2.9 Out of scope, on purpose

- Strava, Garmin or any training data, for anyone, in the public model (section 0).
- Track, cross-country and trail results. Road only; the Figure 8 trail race is excluded.
- Any live service. Predictions and errors are static files and a static page.
- Any race outside NLAA's results pages in Part A. One results provider, parsed properly.
- Runner-facing accounts, notifications, or any contact with a runner. The project
  publishes; it does not message.

## 3. Data

| Source | Size | What it gives | Access and terms |
|---|---|---|---|
| NLAA road results, 2016 to 2026 (2024 to 2026 for the backtest, older years for history depth) | About 26 events a year, roughly 8,000 to 10,000 finisher rows a year; a few hundred pages in all | Place, bib, name, club, time (gun; chip and pace on the Tely 10), sex, age category, hometown | Public web pages, copyright NLAA, no stated terms. Courtesy email before the crawl; one request a second; cached in `data/cache/`, never committed; parsed rows committed as an anonymised aggregate only where the README needs them |
| Athletics NorthEAST entrant lists (Cape to Cabot, USR) | 453 and about 670 adult names on 2026-09-12; one page each, snapshotted daily | Who is registered, sex (Cape to Cabot), event (USR); the no-show rate once results post | Public pages on the club's store, no privacy statement; courtesy note to the club with the NLAA one. Snapshots gitignored; the prediction file is the only published derivative |
| NLAA Toyota Plaza series standings and provincial rankings, 2016 to 2026 | One page per year each | Per-runner participation across the year; best-per-runner times as a resolution check | Same site and terms as the results |
| Cape to Cabot archive, 2007 to 2025 | Nineteen PDFs, two searchable sheets | Nineteen editions of the first live course | Public on capetocabot.com; parsed once, cached, never committed |
| ECCC hourly observations, St. John's Intl A (station 50089) | One CSV per month | Observed temperature, humidity, wind speed and direction at the airport for every past race morning | Open Government Licence Canada; recorded in `docs/data-terms.md` |
| Open-Meteo forecast and archive | A handful of calls per race | Forecast temperature, wind, cloud and direct radiation at the start line; archive as the comparison to ECCC | Free, no key, non-commercial use; recorded in `docs/data-terms.md` |
| Course geometry (own) | One GPX or GeoJSON per course, traced once | Bearing histogram and elevation profile for the course factor and the wind model | Own work, committed with provenance; elevation from Open-Meteo elevation or Open Topo Data, both free |
| Daniels, WMA and Minetti constants | Small | The published curves | Daniels and Gilbert (1979), WMA 2006 age factors as transcribed in 11, Minetti et al. (2002); constants committed with citations |

Nothing raw is committed; the crawler records the SHA-256 of every fetched page; every
licence and courtesy contact is recorded with its date.

## 4. Architecture

```
finishline/
  ingest/      nlaa.py (index and race pages, polite fetcher, page cache with hashes),
               parse.py (fixed-width <pre> parser, both layouts, golden tests),
               entrants.py (entrant list loader, or the field forecast),
               weather.py (Open-Meteo forecast and archive), course.py (route file, elevation,
               bearing histogram; the Minetti integral)
  identity/    normalise.py (names, clubs in brackets, accents, hyphens),
               resolve.py (same runner across races: name, hometown, category progression,
               club; ambiguity flagged, never guessed), review.py (the hand-labelled pairs)
  metrics/     daniels.py, heat.py, wind.py, agegrade.py (copied from 11 with attribution,
               personal calibration notes removed), grade.py (Minetti, own)
  normalise/   neutral.py (history to neutral-condition equivalents), factors.py
  models/      baselines.py (carry-forward, best equal-VDOT, category median),
               hierarchical.py (PyMC, section 5.3), boosting.py (LightGBM quantile),
               participation.py (who will show up, field-forecast mode)
  conformal/   split.py (Mondrian by history depth), coverage.py
  placing/     simulate.py (field sampling to place intervals)
  backtest/    origins.py (one origin per race, strictly-before rule), run.py, score.py
               (MAE, percentage error, coverage, width, place error, Spearman, bootstrap)
  publish/     predictions.py (the prediction file, schema, hash), report.py (README
               tables), page.py (static HTML per race: predictions before, errors after)
  cli.py       finishline crawl | resolve | backtest | predict <race> | freeze <race> |
               score <race> | report
docs/          data-terms.md, methods.md (the model, the conformal assumption, the grade
               model), courses.md, rejected.md (Rule C), predictions/<race>.md (the record)
site/          static output; the race pages, linked from the README
```

### Tests that matter

The fixed-width parser reproduces hand-transcribed rows from committed golden pages in
both layouts and refuses a page whose column widths it does not recognise; name
normalisation and resolution hit a stated precision and recall on a hand-labelled set of
pairs, and an ambiguous pair is flagged rather than merged; Daniels' curves reproduce 11's
reference values and round-trip across distances; the grade model returns exactly 1.0 for a
flat course and is symmetric-in-cost for an out-and-back with matched climb and descent
only where Minetti says it should be; the heat factor is 1.0 at or below 60 °F; the
backtest harness raises if any training row is dated on or after the origin race (the
leakage test); conformal coverage on a synthetic heteroscedastic fixture hits nominal per
stratum; the placing simulator returns exact places for deterministic times; the
prediction file validates against its schema and its hash matches the README; `freeze`
refuses to write a prediction file for a race whose start is under 24 hours away.

## 5. Methods

### 5.1 Crawl and parse

Index pages by year list every result page under `/results/rr/YYYY/`. Road events are
selected by name and distance; the four PDF results a year are skipped and named in
`docs/data-terms.md`. The parser handles the two observed layouts (the general one with
gun time, and the Tely 10 one with chip time and pace) by header detection, and anything
else fails loudly. Every page is fetched once, stored with its hash and fetch time, and
parsed from the cache thereafter.

### 5.2 Who is who

There is no runner identifier across races; bib numbers are per race. Resolution uses the
normalised name, the hometown, the club when printed, and consistency of the age category
over time (a runner cannot get younger, and a five-year Tely 10 band must sit inside the
ten-year band the other races print). Common names with several hometowns are split;
common names with one hometown but inconsistent categories are flagged and excluded from
the public prediction, and the count of exclusions is reported. A hand-labelled set of
about 200 pairs, drawn to over-represent the hard cases, gives the precision and recall
that the README states.

### 5.3 The hierarchical model

On log finish time for runner *i* at race edition *r* over distance *d*:

```
log T_ir = alpha_i + beta_i * log(d_r / d_0) + gamma_i * (t_r - t_i0) + delta_r + eps_ir

alpha_i ~ Normal(mu_group(i), sigma_alpha)        fitness, shrunk to age-sex group
beta_i  ~ Normal(mu_beta, sigma_beta)             endurance exponent, shrunk to population
gamma_i ~ Normal(0, sigma_gamma)                  fitness trend per year
delta_r ~ Normal(prior_r, sigma_delta)            race-edition effect; prior_r is the physics
                                                  course factor times the conditions factors
eps_ir  ~ StudentT(nu, 0, sigma_eps)              heavy tails: a bad day is not Gaussian
```

Fitted with PyMC on the CPU; tens of thousands of rows and a few thousand runners is
minutes, not hours. The target race's `delta` is drawn from its prior alone, because the
race has not happened; the width of that prior is what the backtest's per-course residuals
say it should be.

**Amended 2026-09-13, and the amendment is section 13 item 13.** This paragraph used to say
that prior was "the physics course factor times the conditions factors". It is not. The
course part is **measured from the results** (`models/courses.py`), because runners cross
between courses and 5,310 finishes pin Cape to Cabot to +9.3 percent [+9.0, +9.5] while no
elevation figure can do better than bracket it. The physics (`metrics/grade.py`) is the
prior for a course with no history and the cross-check on one that has it, and on Cape to
Cabot the two agree: +9.3 percent implies a 10.3 percent average grade from the published
550 m of climb, against a race page that says "grades of more than 10 per cent in some
parts". Only the conditions factors come from the forecast, as they always did.

⚠️ `gamma_i` is not droppable. Fitted without it, edition effects absorb population ageing
and every course drifts upward at a median of +0.60 percent a year, which reads as Cape to
Cabot getting ten points harder since 2013. With it the median drift is zero. Runners with no history take `alpha_i` from the group prior, which is the
category-median baseline with an honest width. Predictions are posterior predictive draws,
then conformalised.

**Amended 2026-09-16, and the amendments are section 13 items 21 to 26.** As built in
`models/hierarchical.py`: the response is the log of a finish time over a VDOT-50 Daniels
time, so the population's fade over distance is Daniels' curve and `beta_i ~ Normal(0,
sigma_beta)` is only a runner's departure from it (no `mu_beta`); `gamma_i` has a mean per
age-sex group; each runner's level is sampled at the middle of their own history; the race
effect is a zero-sum course effect plus an edition effect that sums to zero within its
course; courses under thirty finishes are left out of the fit; and it is sampled with
nutpie, not PyMC's own NUTS. "Minutes, not hours" above was wrong by an order of magnitude
on the sampler the plan named, and about right on the one that replaced it: eight minutes
for a fit on 60,379 finishes and 19,488 runners.

**Amended 2026-09-17, and the amendment is section 13 item 29.** The per-runner linear
trend is gone. Each runner's form is a random walk over the calendar years they raced, with
a drift per age-sex group; every race shares a year effect that walks from year to year; and
the observed weather at the airport enters the race effect through four coefficients (heat,
heat by distance, wind, tailwind), so item 27 is closed. A prediction walks the runner's form
and the year effect forward from the last year the fit saw, and a live prediction draws the
weather from the corrected forecast (`models.weather.draws`).

### 5.4 The challenger

LightGBM with pinball loss at the 5th, 10th, 50th, 90th and 95th percentiles on: last
neutral VDOT, best neutral VDOT in eighteen months, number of results, days since last,
fitted trend, age category midpoint, sex, log distance ratio, course prior, forecast
factors, months of the year. Trained rolling-origin like everything else. Its raw quantiles
are reported beside their conformalised versions, which is Rule C candidate 3.

### 5.5 Rolling origin

One origin per race edition from 2024 onward: fit on every result strictly before that
race's date, predict its field, score. The 2016 to 2023 results are history for the early
origins and never targets. This gives roughly 70 scored editions and the residuals the
conformal layer calibrates on, stratified by history depth. The live prediction uses every
result before the target date, which is the same procedure with one more origin.

**Amended 2026-09-16 for the hierarchical model, section 13 item 26.** The baselines still
run at every origin. The hierarchical model is fitted once per calendar quarter, on the
history strictly before the quarter's first day, and predicts every race in the quarter
from that fit. It therefore knows less than the baselines beside it about any race late in
a quarter, never more.

### 5.6 Who is running

**Entrant-list mode** (Cape to Cabot, USR): the list snapshot taken at freeze time is the
field. Each name is resolved against the history exactly as results are resolved against
each other (section 5.2); an entrant with no match is predicted from the group prior with
their listed sex, and counted. The no-show rate and the late-entry rate are measured on the
USR of 2026-09-13, whose list was saved on 2026-09-12, and reported with the Cape to Cabot
prediction as the expected gap between the list and the finishers.

**Field-forecast mode** (Run to Remember, any race without a list): a logistic participation
model on whether a runner ran this race last year, ran any NLAA race in the last six months,
their series-standings participation this year, their number of results, and the target
distance against their usual distance. Predict for everyone above a threshold chosen in the
backtest to balance the two coverage numbers; publish both numbers with the predictions so
the reader knows what a list would have added.

### 5.7 Freeze, publish, score

`finishline freeze c2c-2026` pulls the forecast, writes the prediction file and its hash,
renders the race page and refuses if the gun is under 24 hours away. Peter commits, tags
and pushes; the tag time is the record. After NLAA posts the results, `finishline score
c2c-2026` fetches the page, resolves the field against the prediction file, writes the
error tables and re-renders the race page with predictions and results side by side.
Nothing in the prediction file is ever edited; a defect found after the tag is scored as
it stands and written up.

**Amended 2026-09-16, as built in `publish/scorecard.py`.** Five things the paragraph above
did not say:

- `score` reads the prediction **from its tag, not the working copy**, and refuses one whose
  tag message does not publish the file's SHA-256, or whose tag is less than 24 hours before
  the gun. There is no override.
- It matches published lines to the results page **by name key, not by the resolver**. The
  file carries a name and a hometown and nothing else, on purpose. The hometown breaks a tie
  between results of one name; anything still tied is excluded and counted. A line with no
  result of its name is "not found", an upper bound on the no-show rate, because a list and a
  results page can spell one runner two ways.
- **Runners who did not finish are counted and never named** on the race page. That they did
  not appear is an inference from absence, and no results page printed it.
- The carry-forward baseline is recomputed from the archive as it stood the day before, and
  compared on the runners it could answer for, as a paired difference with an interval.
- Intervals resample runners, because one race has one morning; the page and the README say
  what that does and does not cover. `freeze` renders no race page yet; `score` writes it,
  with every finisher's prediction beside their result.

## 6. Week by week

Relative weeks, anchored to the first live race. Evenings and weekends.

| Week | Dates | Built | Done when |
|---|---|---|---|
| 1 | Sep 14 to 20 | `docs/data-terms.md`; courtesy emails to NLAA and Athletics NorthEAST (Peter); daily snapshot of the two entrant lists (a scheduled local fetch, from Sep 12); crawler, cache, parser with golden tests, including the Cape to Cabot archive PDFs and the series standings; name normalisation and resolution with the labelled pairs; the USR list of Sep 12 resolved against the USR results when posted, giving the first no-show and name-match rates; the dataset with checks; the three baselines; the rolling-origin harness with the leakage test | Every 2016 to 2026 road result parsed; resolution precision and recall stated; USR no-show and match rates measured; baseline MAE per stratum in a table with CIs |
| 2 | Sep 21 to 27 | Course files for Cape to Cabot, Run to Remember and the five or six courses that carry most of the history; Minetti grade model; Open-Meteo archive for every race edition; the neutral-condition layer; the hierarchical model; LightGBM challenger; Mondrian conformal; the backtest table | Backtest tables filled: skill, coverage, width, place error per stratum; ablation of the normalisation; course factors with CIs |
| 3 | Sep 28 to Oct 4 | Placing simulation; participation model; prediction file, schema, hash, `freeze` and `score`; race page; README with backtest tables and the honest limitation; CI; **repository public**; dress rehearsal: freeze and publish predictions for Turkey Tea 10 km (Oct 4) if the pipeline is ready by Oct 2, else for the Trapline 10 km (Oct 11) | A prediction file for a real race committed and tagged before its gun, and scored after |
| 4 | Oct 5 to 11 | Fix what the rehearsal broke; freeze the model version for Cape to Cabot; `docs/methods.md`; Rule C evidence and `docs/rejected.md` | Model version tagged; nothing in `models/` changes after this week |
| 5 | Oct 12 to 18 | Forecast pull and `freeze c2c-2026` on Oct 17 morning; commit, tag, push; hash in the README; race Oct 18 | The pre-registered prediction exists in public before the gun |
| 6 | Oct 19 to 25 | `score c2c-2026` when NLAA posts; error tables into the README; race page updated; `v0.1.0` | Live rows of section 1 filled |
| 7 to 9 | Oct 26 to Nov 15 | Second live race, frozen model: freeze Nov 10, race Nov 11, score when posted; `v0.2.0` | Second set of live rows filled; the two compared |

First to drop if behind: the LightGBM challenger (the hierarchical model and the baselines
stay); the wind term (heat and course stay); the participation model, if an entrant list
arrives; the dress rehearsal on Turkey Tea, in favour of Trapline. Not droppable: the
baselines, the normalisation ablation, conformal coverage per stratum, the placing
simulation, the pre-gun tag, and the honest limitation.

**Added 2026-09-13, and it is not droppable either: the per-runner career trend.** It looks
like a refinement and it is not. Without it the edition effects absorb population ageing at
+0.60 percent a year and a prediction for 2026 inherits ten points of course inflation that
does not exist, silently and with a plausible-looking table. Measured in section 13 item 14.

**Also settled early, which frees the elevation work from the critical path.** The course
factors are measured from the results and are already tight on every course that matters,
so the profile work in week 2 is a cross-check rather than a dependency. Cape to Cabot has
its figures (from the race and from Peter's watch) and they agree with the measurement.
Other courses can acquire a profile when one is offered, and nothing waits for them.

## 7. Cost

No model vendor is called. Everything runs on the laptop's CPU: PyMC in minutes on data of
this size, LightGBM in seconds, the crawl in under an hour once. The race pages are static
files in the repository, served by GitHub or by the portfolio site; no new hosting.

| Item | Basis | CA$ |
|---|---|---:|
| Compute | Laptop CPU | 0 |
| Data | Public pages, free APIs | 0 |
| Hosting | Static files in the public repository; the portfolio site links them | 0 |
| Reserve | A subdomain page on Azure Static Web Apps if the race pages outgrow the README | 0 |
| Strava developer subscription (Part B only, if Part B happens) | About US$12 a month while the opt-in channel is live | 0 in Part A |
| **Total, Part A** | | **0** |



## 8. Handover and reuse

`finishline` v0.1.0 after the first scored race. `metrics/` is the shared running arithmetic
(Daniels, heat, wind, age grading) now in a public repository with tests, which 11 can point
at when it opens. `conformal/` and `placing/` are small and importable. Nothing downstream
depends on this project.

## 9. Risks

| Risk | Handling |
|---|---|
| **The ANE entrant list goes away or changes shape** before Oct 17 | Daily snapshots from Sep 12 mean the latest good one is never more than a day stale; field-forecast mode is the fallback and its coverage is a published number either way |
| **No-shows and late entries** make the list a poor proxy for the field | Both rates are measured on the USR a month earlier and published with the prediction; the placing simulation samples participation from the measured no-show rate |
| **NLAA objects to the crawl** | The courtesy email goes first. If NLAA declines, the project stops and says so in the plan; there is no second results source in NL worth building on |
| **Entity resolution is worse than hoped** on a small province's common surnames | Precision and recall are measured and stated; ambiguous runners are excluded from the public file and counted; the interval for a runner resolved with low confidence widens by construction because their history is thinner |
| **The forecast is wrong on the day** | The published prediction shows the neutral time and the conditions used; the scoring reports the error against both, so a weather miss is separable from a fitness miss |
| **The hierarchical model does not beat carry-forward on one-result runners** | Expected and reported; the honest reading is that one result is one result. The interval width is the product for those runners |
| **A runner objects to being named** | Removed from every future file within a day; the request path is in `docs/data-terms.md`; the removal is logged without the name |
| **Wind and course constants from 11 do not transfer** (fitted on one athlete's training runs) | They are priors with stated width, and the race-edition effect is estimated from data; Rule C candidate 2 measures exactly this |

## 10. Rule C candidates

1. **Equal-VDOT projection from the single best recent result** (what every calculator does)
   against the hierarchical model. Expected: competitive on 5 km to 10 km for runners with
   recent results, optimistic on 20 km and longer, and overconfident everywhere because it
   has no interval at all; the per-stratum table and the coverage of a naive plus-or-minus
   band are the evidence.
2. **The physics course factor used as the estimate rather than the prior.** Expected: the
   Minetti integral over-corrects Cape to Cabot the way 11's raw wind model over-corrected
   by a factor of four, because published energy-cost curves are measured on treadmills at
   steady state and a race is neither. The estimated race effects against the priors, per
   course, are the evidence.
3. **The challenger's own quantiles as the interval.** Expected: LightGBM's pinball
   quantiles under-cover on the sparse strata by a wide margin and conformalisation fixes it
   at the cost of width; the coverage table with and without conformal is the evidence.

Whichever produces the clearest evidence becomes `docs/rejected.md`. Strava is not a Rule C
candidate: it was rejected on terms, not on evidence, and belongs in `docs/data-terms.md`.

## 11. Definition of done

- [x] Data-terms check done for Strava and for the results provider, recorded here and in the project file (2026-09-12)
- [ ] `docs/data-terms.md` in the repository with dates, the NLAA courtesy contact and the removal path
- [ ] Every NLAA road result 2016 to 2026 parsed; resolution precision and recall stated
- [ ] Baselines (carry-forward, best equal-VDOT, category median) reported first, with every later result as skill against carry-forward
- [ ] Rolling-origin backtest over 2024 to 2026 editions: MAE, percentage error, coverage at 80% and 90%, width, place error and Spearman, per history-depth stratum, bootstrap CIs
- [ ] Normalisation ablation and course factors per course with CIs
- [ ] Hierarchical model against the challenger, paired, per stratum
- [ ] Conformal assumption stated beside every coverage table
- [ ] A dress-rehearsal prediction file tagged before a real race and scored after
- [ ] Predictions for Cape to Cabot 2026 committed, tagged and hashed at least 24 hours before the gun
- [ ] Error published after Cape to Cabot 2026: finish-time MAE in minutes, coverage, placing error, field coverage
- [ ] The same for Run to Remember 2026 on the frozen model
- [ ] One rejected approach documented with evidence (Rule C)
- [x] Public name decided (Finish Line Forecast, 2026-09-06)
- [ ] Repository public before the first live race; `v0.1.0` tagged after the first scored race

## 12. Deferred

| Deferred | Kept so the door stays open |
|---|---|
| **Part B: opt-in Strava channel.** A runner authorises through OAuth; their recent runs feed 11's per-run VDOT into their own prediction; they alone see it; nothing pooled, nothing trained on it, and the public file never changes. Needs the paid developer tier and a fresh read of the agreement on the day | `models/` takes a per-runner fitness override with a stated source; the prediction schema has an optional `private_channel` flag that the public renderer never reads |
| **The Tely 10, June 2027**: the field of thousands, chip times, a public entrant lookup, and fifty years of history | The Tely 10 parser layout is built and tested in Part A because the history needs it; the entrant lookup is one loader |
| **The Tely 10's own archive** at `/tely10/results/`, which holds the editions the main results index does not carry (2016, 2017 and, so far, 2026) | One loader against a second index, feeding the same row schema; the layout is already parsed |
| Away results by NL runners (Boston, Sportstats, Athlinks) and the Huffin' Puffin, once their terms are read | `ingest/` is one module per provider behind one row schema; the model takes a result from any provider |
| NLAA cross-country and track results as extra observations | A second parser for the HyTek meet layout; the schema already has a discipline column |
| A runner-facing goal-time tool | The prediction function is pure and importable; a static page over it is a weekend |
| Chip against gun time as separate targets | The Tely 10 rows carry both; the schema has both columns, nullable |
| Weather as a distribution rather than a point forecast | `delta_r`'s prior already has a width; feeding an ensemble forecast widens it by data rather than by assumption |

---

## 13. Changes to this plan

Recorded here in the commit that made them, so a reader can tell a decision from a drift.

**2026-09-12, week 1 built.**

1. **The crawl is a rail in code, not a line in a plan.** Section 0 said Peter emails NLAA
   and Athletics NorthEAST before the crawler runs. `finishline crawl` now refuses until
   told the notices have gone, CI asserts that it refuses, and `finishline notices` prints
   what to send. The reason for the change is that the plan's version was enforceable only
   by whoever remembered it, and that person is the one the command is convenient for.

2. **The catalogue is a week-1 deliverable of its own.** It reads one index page per year,
   which carries event names and dates and no runners, so it produces a real measured
   number (160 races, 45 courses, 39 explained skips) without fetching anybody's results.
   It was going to be a step inside the crawl; splitting it out is what made the two
   findings below visible before a single results page was read.

3. **A race is published as three pages, and two of them are not races.** Every Tely 10
   has an individual result page, a team-standings page and an awards page, all on the
   index with the same date and the same distance in the name. Read as races they made
   nineteen editions of a race run seven times, which would have estimated one day's
   course effect three times over. Excluded by name; the count is now seven, and section 3
   understated how much cleaning the index needs.

4. **The skip list has to name its reason per row.** It reported "not an individual road
   result, or a PDF" for everything, which cannot distinguish a duplicate from a hole. The
   skip list is the coverage claim in section 1, so it now names the reason, and doing that
   immediately turned up the 2017 Turkey Tea being dropped for having a `.htm` extension.
   Only PDFs are now excluded by extension: an extension is not evidence about a layout,
   and the parser refuses loudly on one it does not know.

5. **Two leaks the tests found, both closed.** Races on the same day are not each other's
   history, which matters because the Trapline starts four races from one line. And the
   runner object handed to a model carries every result including the one being predicted,
   so the category-median baseline was reading a first-timer's age band off the finishing
   list of the race in question. Section 5.6 did not anticipate either.

**2026-09-12, later the same day: the crawl ran and the archive answered back.**

7. **The archive has three layouts, not two, and two thirds of it has no ruler.** Section
   5.1 said the parser handles "the two observed layouts by header detection". Both counts
   were wrong. Every page from 2016 to mid-2018 prints its header and then its rows with no
   rule between them, so a parser keyed on the ruler read 108 of 160 races as empty and
   raised nothing at all: the coverage number was simply wrong and nothing said so. The
   ruler was never load-bearing, because the boundaries are measured from the rows either
   way. The third layout is the 2022 Tely, with a class code, a place-of-field and a net
   time, its ruler drawn across three columns at once and its header printed several
   characters left of its own data; it is read by counting, since nine header columns and
   nine measured columns agree about the shape of the table. One page remains unread, an
   HTML table from 2017, and is recorded as a hole.

8. **Entity resolution was keyed on the wrong thing, and the archive said so twice.**
   Section 5.2 made the hometown a splitting key. But 105 of the 159 readable races print
   no hometown column at all, so the key held back one runner in six for a column the page
   never had; and runners move, with 1,103 of the 1,656 multi-town names showing a single
   clean switch over time. Pat Example settled it: a consistent ageing sequence with times
   improving throughout, cut into two half-histories by a move to the mainland. The age bands
   are now the only thing that splits a name, because a runner cannot get younger, and the
   hometown only breaks a tie. Runners held back fell from 2,608 to 119 and runners with
   four or more finishes rose from 2,363 to 3,005.

9. **The merge risk that change creates is published rather than argued about.** Two
   runners of one name and a compatible age now merge. 416 of 15,689 resolved runners have
   a printed hometown that changes back and forth rather than once, which is the shape two
   merged people make, and that is the bound the README carries. Reading them shows most
   are one person spelling their own town differently between entry forms, so the true
   figure is lower; 416 is published because it is the one a reader can check.

10. **The first measured result reframes the project.** Across 48 races from 2024, a third
    of every field (4,457 of 14,205 runners) had never raced in this archive before, and
    for them the only available answer is the middle of their category, 17 minutes out.
    Section 1 treated the cold start as one stratum among four; it is the largest one, and
    the hierarchical model's group prior (section 5.3) is therefore the most important
    single piece of the build rather than a fallback.

6. **Section 3's page-count estimate stands but its shape was wrong.** The Tely 10's own
   archive at `/tely10/results/` is a second loader, not an optional extra: the main index
   carries no Tely for 2016, 2017 or 2026, so the largest field in the province is missing
   its most recent edition. Added to Deferred; it does not block Cape to Cabot.

**2026-09-12, late: the entrant lists are now snapshotted by a command rather than by
hand.**

11. **A live page has no archive, and the first race that needed one was nine hours away.**
    Section 0 said the two Athletics NorthEAST lists would be snapshotted daily from
    Sep 12 so that the no-show and late-entry rates could be measured on the Uniformed
    Services Run of Sep 13, a month before Cape to Cabot needs them. The snapshots on Sep
    12 were taken by hand, and nothing in the repository would have taken the next one.
    `finishline snapshot` now does it, under the same courtesy rail as the crawler and at
    the same one-request-a-second, and CI asserts that it refuses without the notices in
    the same way `crawl` does. It writes a file only when the page has changed and a
    manifest row every time, because a day on which nobody entered is an observation and
    not a reason to keep a second copy of five hundred names.

    The last pre-gun look, 2026-09-13T00:14Z: **Cape to Cabot 458 entrants, up five in
    the eight hours since the first snapshot, none withdrawn; the USR 896**, of whom 629
    are in the four individual road events that will produce results (277 half, 198 10 km,
    79 marathon, 75 5 km) and the rest are the kids' 1 km, the family 3 km and the marathon
    relay. Section 0's note that the USR list held "10 km 272" was a miscount from before
    the parser tracked the event headings: that figure was the 10 km and the 5 km together.

    **No prediction was made for the USR.** The gun is inside twenty-four hours and the
    rule in CLAUDE.md says `freeze` refuses inside twenty-four hours, which is a rule worth
    more on the first occasion it is inconvenient than on any later one. The USR still pays
    for itself: the final list is preserved, so when NLAA posts the results the no-show
    rate, the late-entry rate and the list-to-results name-match rate are all measurable,
    which is what section 5.6 wanted from it.

12. **The snapshot's idea of "changed" was wrong within an hour of being written, and the
    live page said so.** The first version compared the page as fetched against the page
    on disk. The club's store puts a fresh `securityToken` in every response, so no two
    fetches of an unmoved list are ever byte equal: the second run reported both lists as
    changed with the counts identical. Left alone it would have written a fresh copy of
    458 and 896 names every day for the 35 days to Cape to Cabot and buried the growth
    curve, which is the whole point of the exercise, under identical files. "Changed" now
    means the parsed start list changed, sorted so that the club reordering its own page
    is not mistaken for an entry; both hashes go in the manifest, the page's for the
    provenance of the bytes and the listing's for whether anything happened. Two tests pin
    it, one of them the token itself.

    Worth noting for what it says about the rest of the build: this was caught only
    because the command printed its count next to its verdict and the two disagreed. The
    manifest rows written at 00:14Z and 00:28Z are labelled `changed` and are left as they
    are; they were what the tooling believed at the time.

**2026-09-13, week 2 begins: the course layer, and what measuring it first changed.**

13. **Section 5.3 had the course factor the wrong way round.** The plan said the target
    race's `delta_r` is drawn from a prior that is "the physics course factor times the
    conditions factors". That treats the elevation model as the source and the results as
    a check. It is the other way round. Runners cross between courses, so a course's
    difficulty is identifiable from finishes alone, and on the courses that matter it is
    identified far more tightly than any elevation figure could manage: **Cape to Cabot is
    +9.3 percent [+9.0, +9.5] against an equal-VDOT flat time, from 5,310 finishes over 15
    editions**. No profile, no DEM, no GPX. The physics is now the prior and the check, and
    it is used where the results cannot answer: a course with no history, a course whose
    route changed, and the question of whether a measured factor is a hill or an artefact
    of who turns up.

    **The check passes, and that is the point of doing both.** Peter supplied the
    elevation: the race publishes 550 m of climb against 450 m of drop, and his own watch
    recorded 519 m of climb on the 2025 edition. Put through Minetti's cost-of-running
    curve, +9.3 percent implies an average grade of **10.3 percent on the graded sections**,
    and the race's own course page says "grades of more than 10 per cent in some parts".
    Two independent routes, one from physics and one from revealed performance, agreeing on
    a course nobody has surveyed for this project. `metrics/grade.py` and `data/courses.toml`
    hold it, and a test asserts the agreement across the whole interval rather than at the
    point estimate.

    Three notes on what the physics can and cannot do here. The weak input is **not** the
    elevation, it is the **grade distribution**: 550 m of climb spread over 11 km at 5
    percent costs 5.9 percent and the same climb packed into 5.5 km at 10 percent costs 9.0
    percent, so total gain alone does not determine the penalty and `penalty` takes the
    grade as an explicit argument. `implied_grade` refuses rather than rounding when no
    grade explains a factor, which is a finding and not a nuisance. And the constant-power
    idealisation means the result is a floor: a real runner does not hold power up a ten
    percent wall and braking is not free, both of which push the same way.

14. **A per-runner career trend is load-bearing, and leaving it out produces a finding that
    is not true.** Fitted with one constant per runner, Cape to Cabot's edition effect
    climbs almost monotonically from +3.8 percent in 2013 to +14.4 percent in 2025, which
    reads as a course getting harder every year. It is not. A career-long constant has
    nowhere to put the fact that runners get slower as they age, so the edition effects
    absorb it: **all thirteen well-covered courses drift upward, median +0.60 percent a
    year**. Add a per-runner trend and the **median drift is +0.00 percent** and the signs
    scatter. Section 5.3's `gamma_i` was already in the plan; this is the measurement that
    says it cannot be the first thing dropped when time is short. A model fitted the other
    way and asked for 2026 would extrapolate ten points of course inflation that does not
    exist, and would do it silently. A test on synthetic runners who age two percent a year
    on courses that never change pins it.

15. **Eighty courses were really fifty-two, for the same reason eight years went missing.**
    The 2008 to 2015 index titles a race with its ordinal and whichever sponsor held the
    naming rights, so Burton's Pond was six courses of one edition each, CHCM was seven, and
    the ANE Mile, the Harbour Front and the provincial 5 km championship were three apiece.
    Every fragment then fell under the thirty-finish floor and vanished from the table
    entirely. `course_id` now strips ordinals and sponsors, and Harbour Front goes from two
    fragments to 12 editions, CHCM to 9, the ANE Mile to 12.

    ⚠️ **The merge overshot first, and the sign of it was a course called "unknown".**
    Some races have no name but their sponsor: the Toyota Plaza 15 km and the Nautilus
    Half-Marathon are those races, not the Toyota Plaza anything-else. Stripping the sponsor
    left an empty slug, and empty slugs collapsed six unrelated half marathons and 1,041
    finishes into one course. Boilerplate is now stripped in tiers, hardest first, and the
    first tier that leaves a name wins.

16. **The 2014 CHCM 10 km was in the archive twice.** It is on the index as both `.htm` and
    `.php`, the same 162 finishers in title case on one page and upper case on the other.
    Counted twice it inflated the archive by a race and, worse, gave 162 people a second
    result on a day they raced once, which inflates their history depth and hands the
    resolver two copies of one person. The catalogue now drops a race that repeats a
    course, a date **and** an event name, keeping the `.php` copy and naming the dropped one
    in the skip list. The name has to be part of the test: the Trapline runs an open 5 km
    and a U19 5 km on the same road on the same morning, and those are two races.

    Archive after all three: **286 races, 52 courses, 282 read, 74,516 finishes, 23,713
    runners, 355 held back.**

**2026-09-13, the conditions layer: two wrong answers before the right one.**

17. **The weather looked like it did not matter, and that was a weighting mistake.** The
    first pass regressed 227 edition effects near the airport on observed temperature and
    wind, unweighted, and got **+0.027 percent per degree with an interval straddling
    zero**: the honest-looking conclusion that in a climate this cool the morning does not
    move a race. It does. An edition effect estimated from thirty finishers is mostly noise
    and this archive is full of them, so the small races were shouting down the large ones.
    Weighted by field the same coefficient is +0.15, and on editions above 400 finishers
    +0.29, both clear of zero. The null was an artefact of counting a 30-runner 5 km and a
    4,000-runner Tely equally.

18. **The second wrong answer was worse, because it was a plausible number.** Wired up, the
    model fitted the raw edition effects, which still contain the course: a Cape to Cabot
    edition sits near +9 percent because of Signal Hill, not because of the morning. The
    temperature coefficient was then partly measuring that the hard courses here run in
    October and the easy ones in June. What gave it away was the residual: **4.42 percent,
    larger than the 2.79 percent within-course scatter it was supposed to be explaining**. A
    model cannot explain something and leave more behind than it started with. Demeaned
    within course and weighted, it explains **32.3 percent of the edition variance and
    leaves sd 2.34 percent**.

19. **The temperature coefficient is a function of distance, not a number**, and the
    ordering is the one physiology predicts: **-0.05 percent per degree at 5 km, +0.23 at
    10 km, +0.43 at the Tely, +0.51 at Cape to Cabot, +0.81 at a marathon.** The 5 km sign
    is left as measured rather than clipped, because at that distance heat is not the
    binding constraint and a warm morning here is usually a calm one.

    **The check that makes this credible.** The Tely 10 on its own, eleven editions of two
    to four thousand finishers each, run between 3.6 and 22.7 degrees because two COVID
    years pushed it into October, gives **+0.41 percent per degree, +0.42 controlling for
    year, R-squared 0.64**. The pooled model with its distance term, fitted across every
    course and never told about the Tely, returns **+0.425** for that distance. Two routes
    to the same coefficient, and it sits in the range the marathon literature reports.

20. **A wind speed is not a wind, and Peter said so from the road before the data did.**
    The prevailing wind in Tely season is westerly, and the Tely runs east-north-east from
    Paradise into St. John's, so the usual wind is a tailwind for almost the whole race.
    Cape to Cabot runs north-west from Cape Spear to Signal Hill, so the same westerly is a
    headwind. Fitted as one speed term for the whole province those cancel, which is what
    the first fit showed: +0.076 percent per km/h, interval through zero.

    Wind now enters twice: the **speed**, which a loop or out-and-back feels whichever way
    it blows because it loses more into the wind than it gains coming back, and the signed
    **tailwind along the course bearing**, which only a point-to-point course has. Bearings
    are in `data/courses.toml`, great-circle from start to finish, 70 degrees for the Tely
    and 321 for Cape to Cabot. A 30 km/h westerly is +28.5 km/h of tailwind on one and 18.5
    km/h against on the other.

    ⚠️ **The tailwind coefficient has the right sign and does not yet clear zero**:
    -0.022 percent per km/h [-0.100, +0.054], negative meaning it helps. There is variation
    to fit, the Tely ranging -14.8 to +29.2 km/h of tailwind and Cape to Cabot -38.5 to
    +16.0, but only two courses carry a bearing, which is 27 editions. More bearings is now
    the highest-value thing anyone can add to `courses.toml`, and it is in `docs/todo.md`.
    It is reported as not-yet-significant rather than quietly kept because the sign is
    pleasing.

    One fact that falls out and is worth the race director's attention: **Cape to Cabot runs
    into a headwind in 13 of its 16 editions**, four of them above 25 km/h against.

**2026-09-16, the hierarchical model: five things the plan said that the sampler refused.**

All measured on one origin, 2025-01-01: 60,386 finishes, 19,488 runners, 250 editions, 47
courses, 17 age-sex groups. The numbers are from `az.summary` over four chains.

21. **PyMC's own NUTS could not sample the model, and the plan named it.** 100 tuning steps
    and 100 draws took 1,117 seconds, every chain ran to its maximum tree depth (mean 9.4 of
    10), 314 draws diverged and R-hat on the fitness and noise scales was above 2: four
    chains that had not agreed how much of a finish time is the runner and how much is the
    day. **nutpie on the same model: 300 and 300 in 463 seconds, tree depth 6, no
    divergences.** Its mass-matrix adaptation learns forty thousand scales in the time
    PyMC's windowed adaptation spends starting to. PyMC stays as the modelling language;
    nutpie is pinned beside it in `pyproject.toml` with the reason.

22. **Anchoring each runner's level at their first race was the obvious parameterisation and
    was measured to be no help.** A runner with results from 2012 to 2024 pins their 2018
    fitness far better than their 2012 fitness, so level and trend trade off along a ridge,
    and the fix is to sample the level at each runner's own mean year and distance. It was
    tried first, on PyMC's sampler, because it was the likeliest cause of the tree depth.
    It did not move it: uncentred, every chain hit maximum tree depth and 100 and 100 took
    1,187 seconds; centred, every chain still hit it (mean 9.4 of 10) and it took 1,117. It
    is kept, because it is the right geometry and costs nothing, but the thing that fixed
    the sampling was item 21.

23. **`mu_beta` is not identifiable here, and the plan had one.** Every course is run at one
    distance, so a population-wide fade `mu_beta * log(d)` is indistinguishable from course
    effects that happen to line up with distance. Fitted with both it came back at R-hat
    1.76. It is gone; the population's fade relative to Daniels lives in the course effects.

24. **Two convergence failures that looked like one, and the first guess at the cause was
    wrong.** With `mu_beta` fixed, `sigma_course` and `sigma_edition` still sat at R-hat
    1.56 and 2.11. They were expected to have been dragged by `mu_beta` and were not. The
    edition effects had a free direction: every edition of a course moving up while the
    course moves down, which the likelihood cannot see and the prior barely charges for
    once `sigma_edition` is large. Editions now sum to zero within their course.
    `sigma_edition` went to 1.21 and a tight 0.043.

25. **One chain in four called a seven-finisher marathon seventy-eight percent fast.**
    `sigma_course` stayed at 1.57 after item 24, and splitting the course effects by chain
    showed why: three chains put `eastern-42195` at +0.04, the fourth at -1.50, and because
    courses sum to zero that moved every other course by 0.035. With tails this heavy (nu
    near 2) calling seven finishes seven outliers is a local mode a chain can fall into and
    not leave. The course layer already refuses to publish a course under thirty finishes
    as "noise dressed as a measurement"; the model now applies the same floor, which
    removes seven finishes. **Every scale then converged: R-hat 1.02 to 1.07, no
    divergences, the course effects agreeing across chains to 0.003.**

    Worth the reader's attention: the tails. nu comes back at 2.02 with a residual scale of
    2.8 percent, which says most runners repeat themselves closely and a minority of
    results are wildly off (a walk, an injury, a pacing duty, a wrong name match). A normal
    likelihood would have spent the whole fit explaining those.

26. **The model is fitted per quarter, not per origin.** At eight minutes a fit, a fit at
    each of seventy-odd origins is ten hours; one per calendar quarter from 2024 is about
    ten fits. Each is fitted on the history strictly before the quarter's first day, so a
    race late in a quarter is predicted without that quarter's earlier results, which the
    baselines beside it do see. The tilt is against the model on purpose, since the other
    direction is a leak, and a test pins that a block fit never sees its own block.

27. **The model does not use the weather yet, and the prediction file says so.** Section 5.3
    puts the conditions factors into the race effect's prior. As built, the race effect is
    the course plus an edition deviation the model learns only from past editions, so a
    predicted race gets its course's average morning and the full spread of mornings as
    uncertainty. The conditions layer (items 17 to 20) is measured and not yet wired in, and
    `freeze` writes `"conditions": null` rather than a forecast the model did not use. Wiring
    it in means fitting the edition effects net of observed weather, which changes the model
    and therefore needs its backtest rerun; it is next after the first backtest table.

    **Closed 2026-09-17 by item 29:** the observed weather is in the race effect, the backtest
    is run with and without it, and `freeze` records the corrected forecast it used.

28. **The first model backtest lost to carry-forward, and most of the loss is one line of
    `predict`.** Measured 2026-09-16 over 49 races from 2024: MAE 9.3 minutes against
    carry-forward's 7.4 for runners with four or more prior results, 10.9 against 9.2 with
    two or three, 10.9 against 9.6 with one, and level with the category median (18.6
    against 18.5) for runners with none. The tables above are published as measured.

    **The order is right and the level is wrong.** On the saved rows, the model's
    predictions are 8.3 percent too fast on average (95% CI 6.7 to 9.6, resampling races),
    where carry-forward's are off by 0.4 percent (-2.6 to +2.0). With each race's median error
    taken out, the two are level: mean absolute log error 0.0773 for the model against 0.0780,
    a difference of -0.0007 (-0.0040 to +0.0019). The bias grows with the time between the
    middle of a runner's history and the race: 3.8 percent within six months, 11.6 percent
    past eight years.

    **The cause is the trend, carried to race day.** `gamma_i` is a straight line in years
    since a runner's first race, and runners get faster through their first years (the mean
    runner trend is -0.5 percent a year), so extending that line to the race predicts years
    of improvement nobody has. Tested on the 2025-01-01 posterior against the 4,469 finishes
    of twenty 2025 races, at posterior means (mean absolute log error, then median error):
    the trend carried to race day, 0.1011 and -6.4 percent; the trend held at the runner's
    last result, 0.0919 and -5.2; the level at the middle of the runner's history, 0.0871
    and -3.1; carry-forward, 0.0968 and +3.8. `gamma_i` stays in the fit, because without it
    the edition effects absorb ageing (section 5.3); the change is to how far a prediction
    extends it.

    ⚠️ **About three percent is not explained yet.** The leading suspect is the likelihood:
    with nu near 2 the Student-t location sits nearer the mode than the median, and race
    errors are skewed (a bad day is slow; nobody has a wildly fast one), so the model aims
    for a good day.

    ⚠️ **Item 25's convergence claim did not hold across the backtest.** Over the eight
    quarterly fits the largest R-hat on the hyperparameters, `mu_group` and `mu_gamma`
    included, is 1.24 to 1.37 and the smallest bulk ESS 9 to 13, with no divergences. Item 25
    looked at the scales at one origin, where they were fine; the group means were not
    checked there.

    **The conformal layer did its job on a biased model.** For runners with four or more
    results the model's own 80 percent interval held 46 percent of the time and the
    adjusted one 79 percent, which is the calibration working, paid for in width: a median
    of 14.0 minutes became 24.3. The place error of 54.5 against carry-forward's 25.8 is not
    a like-for-like comparison: places are ranked among the runners each model answered,
    and the model answered for the newcomers too.

29. **Form is a random walk and every year has its own level, because the line and the
    course average were both wrong.** Tested on history before 2025-01-01 against the 4,469
    finishes of twenty 2025 races (mean absolute log error, then median error; posterior
    means; carry-forward from each race's own history):

    | Model | Error | Median | Race-centred |
    |---|---:|---:|---:|
    | Linear trend (item 28's model) | 0.1007 | -6.9% | 0.0750 |
    | Linear trend, level held at the middle of history, half the last residual added | 0.0816 | +0.7% | 0.0800 |
    | Random walk on form | 0.0888 | -5.0% | 0.0737 |
    | Random walk, mean-reverting (AR(1)) | 0.0885 | -5.0% | 0.0736 |
    | **Random walk and a year effect** | **0.0766** | **+1.6%** | 0.0738 |
    | Random walk and a year effect, no group drift | 0.0790 | +2.5% | 0.0744 |
    | Carry-forward | 0.0912 | +1.6% | 0.0786 |

    Three findings, each of which refuted the one before. First, residuals persist: a
    runner's miss at one race predicts their miss at the next by 0.3 to 0.4 within a season,
    so fitness is a state, not a slope, and the walk fixed the ordering (race-centred error
    0.074 against carry-forward's 0.079). Second, the remaining five percent was not
    regression to the mean: fitted with mean reversion, the persistence came back at 0.99.
    Third, it was the calendar. Edition effects, measured against their course's long-run
    average, run from two to three percent fast in 2011 to 2015 to six to eight percent slow
    in 2023 and 2024, in every course and group, so a course average predicts a 2025 race as
    if it were run a decade ago. A shared year effect, walked forward, took the bias to
    carry-forward's and the error to sixteen percent below it. Why recent fields are slower
    (who runs, or how) is not something this model claims to know.

    ⚠️ **The year effect is not well identified, and the diagnostics say so.** Years since a
    runner's first race and the calendar year rise together for every runner, the age,
    period and cohort problem, so the group drift, the year effect and the group levels trade
    off along a ridge: worst R-hat 1.68 with the drift, 1.40 without it, bulk ESS near ten on
    `sigma_year`. Predictions are made along the ridge's invariant (form plus the latest year)
    and were the most accurate of all, so the model with the drift is used, and every fit's
    diagnostics are published with the backtest rather than presented as converged.

    **The full backtest, run overnight on 2026-09-17 to 18, and the README tables carry it.**
    Eight quarterly fits, 49 races from 2024 on, 73,232 predictions, each race predicted only
    from results dated strictly before it. Mean absolute error in minutes:

    | Prior results | Runners | Carry-forward | Model | Skill |
    |---|---:|---:|---:|---:|
    | 0 | 5,594 | not answered | 17.9 | against the category median's 18.5 |
    | 1 | 2,650 | 9.6 | 9.5 | 1% |
    | 2 to 3 | 2,831 | 9.2 | 8.5 | 8% |
    | 4 or more | 7,233 | 7.4 | 5.5 | 26% |

    On the 12,714 runners both models answer for, mean absolute log error is 0.0751 against
    carry-forward's 0.0881, and with each race's median error removed 0.0722 against 0.0780,
    a paired difference of -0.0059 (95% CI -0.0093 to -0.0032, resampling races). Bias is
    -0.4% (-2.0 to +1.2) against carry-forward's -0.4% (-2.7 to +2.0), so item 28's 8.3% is
    gone. The intervals moved as much as the point predictions: own-interval coverage at four
    or more prior results went from 46% to 76% at the 80% level, and conformal now widens the
    median interval from 13.5 to 13.6 minutes where it had to stretch 14.0 to 24.3.

    Per-fit diagnostics, published as promised rather than summarised away: no divergences in
    any of the eight fits, worst R-hat by block 1.35, 1.51, 1.51, 1.67, 1.71, 1.73, 1.74 and
    1.84, smallest bulk ESS about 6. The ablation without weather is the same picture, with
    four divergences in its 2025-04-01 fit. This is the single-origin ridge again, unchanged
    at every origin, and the predictions are still read along its invariant.

    ⚠️ **The weather coefficients are a null result and the row stays in the README.** The
    same eight fits without them give 17.9, 9.6, 8.6 and 5.5 minutes, inside the full model's
    confidence interval at every depth. Paired on the 18,278 predictions both runs make, the
    weather model's mean absolute log error is lower by 0.0003 (95% CI -0.0008 to +0.0002,
    resampling races), which is three hundredths of a percent of a finish time.

    ⚠️ **And the ablation is the strong form of the test, not the weak one.** Every target
    race in the backtest is after its block's origin, so the model has no edition effect for
    it and draws one from the prior, exactly as a frozen prediction does; the weather
    covariates handed to `predict` are the airport's *observed* temperature and wind for that
    morning, not a forecast. So this measures a model that knew the weather perfectly against
    one that did not, in the same position a freeze is in, and it found nothing. Splitting by
    how far the morning sat from neutral does not rescue it: at nine degrees or more from
    neutral, six races and 5,031 runners, the gain is 0.0004 (-0.0051 to +0.0001), and on the
    four windiest races the weather model is very slightly worse. The one race where it
    behaves as the physics says it should is the 2025 USR half marathon, fourteen degrees
    above neutral, where 275 runners are predicted better by 0.0079 of log error.

    The terms stay in anyway, on three grounds that are worth stating plainly because they
    are judgement and not measurement: the sign is right where heat is extreme, the cost is
    indistinguishable from zero, and without them a live forecast has no way into the
    prediction at all, so a Cape to Cabot morning at 20 C would be predicted as if it were
    neutral. If the freeze needs a reason to drop them, this entry is it.

    ⚠️ **The placing table is not a like-for-like comparison and must not be read as one.**
    Places are scored among the runners each model answered for, so carry-forward is ranked
    over the 12,714 runners with a prior result and the model over the whole field, the 5,594
    entrants with no history included, which is why its mean absolute place error is 53.4
    against carry-forward's 25.8. Scoring the model on carry-forward's subset is the missing
    measurement; it belongs beside the current table, not instead of it, and it is owed before
    the first freeze.

    **One operational note, because it cost a night.** A fit on the whole archive commits
    about 27 GB on this machine, and the eighth block failed three times on a 216 MiB
    allocation with the Windows commit limit at 48 GB. Blocks are now written as they finish
    (`backtest/saved.py`, `BlockStore`), so a failed run resumes instead of restarting, and
    the pagefile was raised to a fixed 64 GB. The freeze fit is the same size as that eighth
    block, so this is a constraint on October 17, not a one-off.
