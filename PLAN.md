# Plan: Finish Line Forecast

**Written:** 2026-09-12. **Status:** plan only, nothing built.

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
minutes, not hours. The target race's `delta` is drawn from its prior alone (the course
factor from the profile, the conditions factors from the forecast), because the race has
not happened; the width of that prior is what the backtest's per-course residuals say it
should be. Runners with no history take `alpha_i` from the group prior, which is the
category-median baseline with an honest width. Predictions are posterior predictive draws,
then conformalised.

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
| **The Tely 10, June 2027**: the field of thousands, chip times, a public entrant lookup, and fifty years of history | The Tely 10 parser layout is built in Part A because the history needs it; the entrant lookup is one loader |
| Away results by NL runners (Boston, Sportstats, Athlinks) and the Huffin' Puffin, once their terms are read | `ingest/` is one module per provider behind one row schema; the model takes a result from any provider |
| NLAA cross-country and track results as extra observations | A second parser for the HyTek meet layout; the schema already has a discipline column |
| A runner-facing goal-time tool | The prediction function is pure and importable; a static page over it is a weekend |
| Chip against gun time as separate targets | The Tely 10 rows carry both; the schema has both columns, nullable |
| Weather as a distribution rather than a point forecast | `delta_r`'s prior already has a width; feeding an ensemble forecast widens it by data rather than by assumption |
