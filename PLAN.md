# Plan: The Whole Field, Called Before the Gun

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
this line: thirty-six numbered entries, each one a design in this plan that measurement
overturned. What is open and who owns it is in [docs/todo.md](docs/todo.md).

**Build:** planned in relative weeks. Earliest start: now. The first live target fixes the
calendar: **Cape to Cabot 20 km, St. John's, Sunday 2026-10-18**, five weeks out, with **Run to Remember 11 km, 2026-11-11** as
the second live race on a frozen model and the **Tely 10 (June 2027, capped at 4,466)** as the
"field of thousands" race in Part B. **Package:** `finishline`. **Repository:**
`Peter-A-P/finish-line-forecast`, public since 2026-09-19, with the website at
https://finishline.peterparker.ca. **Fed by:** 11 (Overload), whose Daniels,
heat, wind, course-bearing and age-grading modules are copied across with attribution and
with every personal calibration detail stripped. **Feeds:** nothing.

This project calls no language model. Every number below comes either from a
rolling-origin backtest over public race results, with bootstrap intervals, or from a
prediction that was committed, tagged and public before the race it predicts.

> **The pre-registration is the point.** Every other project in the portfolio proves its
> number with a backtest a sceptic has to trust. This one commits its predictions to a
> public repository, with a tag and a hash, before the gun, and scores them against the
> official results after. The backtest exists to size the intervals and to fill the tables
> while waiting for a race; the live record is the deliverable.

---

## 0. The data-terms check, and what it changed

The brief said to check the Strava API agreement and each results provider's terms
before any code. Done 2026-09-12; the outcome reshapes step 3 of the original idea.

| Source | Finding (checked 2026-09-12) | Consequence |
|---|---|---|
| **Strava** | API Agreement effective 2026-06-01, section 2.3: "Strava Data related to other users, even if such data is publicly viewable on the Strava Platform, may not be displayed or disclosed." Section 5.1 forbids sharing a user's data with other users or third parties without explicit consent. The November 2024 revision, restated in the 2026 developer programme, forbids using API data to train AI or machine-learning models. The Acceptable Use Policy forbids collecting or harvesting information about identifiable individuals and any automated scraping. Public profile pages are being moved behind login. Standard-tier API access now requires a paid Strava subscription (about US$11.99 a month) per developer. | **Scanning registered runners' Strava profiles is out**, by API and by scraping alike. The only compliant use is **opt-in**: a runner authorises the app through OAuth, sees a prediction that uses their own training data, and nobody else does. That is deferred to Part B (section 12) and the public table never uses Strava. The plan's headline model works from public race results, which is the weaker but still checkable model the brief anticipated. |
| **NLAA results** (nlaa.ca) | Public HTML pages under `/results/rr/YYYY/`, one per race, results in a fixed-width `<pre>` block: place, bib, name (club in brackets), time, sex and sex place, age category, category place, hometown. The Tely 10 pages add gun time, chip time and pace per mile. 26 road events in 2025, 25 in 2024, results back to 1978. Footer "Copyright NLAA"; no terms of use page; no `robots.txt`. A Google custom search box, no runner profiles. | Usable as public data, with courtesy. **Peter emails NLAA** (athletics@nlaa.ca) and Athletics NorthEAST (admin@athleticsnortheast.com) before the crawler runs, saying what is fetched and how it is used; the crawl is one request a second, cached locally, never re-fetched once stored, and raw pages are never committed. Predictions publish only what the results already publish: name and hometown as printed. |
| **Registration lists** | **Athletics NorthEAST publishes live entrant lists** on its Zen Cart store (`athleticsnortheast.com/cart/index.php?main_page=page&id=4` for Cape to Cabot, `id=1` for the Uniformed Services Run), "up-to-the-minute". Cape to Cabot on 2026-09-12: 453 names with gender and shirt size (266 male, 187 female) against a cap of 500. USR on 2026-09-12, by event: marathon 79, half 277, relay 44, 10 km 272, plus kids and family runs; names only, some with a service affiliation. Neither page carries a privacy statement. Run to Remember: no list found. Tely 10: Trackie registration with a per-person confirmation lookup (first name, last name, city), not a list. The Wayback Machine holds no past editions of the ANE lists. | **Entrant-list mode is the primary mode for the two ANE races.** Gender from the Cape to Cabot list helps resolution and the cold-start group prior. Shirt size is a body-size proxy and is **not used**, by decision (section 2.8): it is not something the results publish about a runner. The lists are snapshotted daily from now (first snapshots saved 2026-09-12, gitignored) so the registered-versus-finished rate and the list-to-results name-match rate are measured on the USR of 2026-09-13 for free, before Cape to Cabot needs them. **Field-forecast mode** stays for races with no list (Run to Remember): predict for every runner in the eighteen-month history whose participation probability clears a threshold, and report coverage. |
| **Weather** | Open-Meteo forecast and archive APIs: free, no key, hourly temperature, wind speed and direction at 10 m, cloud and direct radiation. Already the weather source in 11, **which measured its modelled temperature about 6 °C off at this coast**. Environment and Climate Change Canada publishes hourly observations for St. John's Intl A (station 50089, climate ID 8403505) as a bulk CSV per month, no key; checked 2026-09-12: the 2025 Cape to Cabot morning read 8 °C, 100% humidity, wind 34 to 36 km/h from the north-east at the airport. | ECCC observations are the archive for the backtest's conditions factors, with Open-Meteo's archive as the comparison and the difference reported. The **forecast** (there is no observation of the future) comes from Open-Meteo, pulled at a fixed time before the gun and recorded with the prediction. Both are free for this use; recorded in `docs/data-terms.md`. |
| **Course profiles** | No official GPX found for the target courses. Cape to Cabot publishes the route (Cape Spear to Cabot Tower) but the elevation page is gone. Elevation from Open-Meteo's elevation API or Open Topo Data (SRTM/Copernicus 30 m) against a route Peter traces once in a mapping tool. | Course geometry is an input file per course, committed, with its provenance. The physics course factor built from it is a **prior**, not the estimate; the race-day effect is estimated from results (section 5.3). |

Everything in this table goes into `docs/data-terms.md` in the repository, with the dates.

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
must therefore be public before the first live race. A prediction made or altered after
the tag is not a prediction and is never reported as one.

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
               model), courses.md, rejected.md (one approach tried and rejected),
               predictions/<race>.md (the record)
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
parts". Only the conditions factors come from the forecast, as they always did. **Amended
again 2026-09-20, section 13 item 36:** a measured factor also carries this population's
departure from Daniels' fade at that distance, which cannot be separated from it because
every course is run at one distance. It belongs in a prediction for that course and it does
not belong in a comparison between courses of different lengths, so the factor is published
beside a second figure against the courses of the same length, and Cape to Cabot's implied
grade is a ballpark of 8 to 10 percent rather than 10.3.

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
are reported beside their conformalised versions, which is section 10's candidate 3.

**As built, 2026-09-19** (`models/gbm.py`, `finishline backtest --challenger`). Seven
quantiles, the hierarchical model's own, so the same conformal layer calibrates both. Form is
the log ratio to a VDOT-50 Daniels time rather than a "neutral VDOT": the conditions enter as
the six raw weather features the hierarchical model reads, and the trees can learn what they
cost, which is a fairer test than handing the challenger the other model's weather
correction. Refitted per calendar quarter on the history before it, like the hierarchical
model, on every finish since 2010; hyperparameters fixed before the first run and never tuned
on the backtest. Its rows are saved and keyed like the hierarchical run's, so `report`
publishes them beside the others and never refits.

**Amended 2026-09-20, section 13 items 33 to 35.** It stopped being a challenger only. It is
more accurate than the hierarchical model for every runner with a history, and what publishes
is now the average of the two on the log scale, weighted 0.65 towards the trees, with the
hierarchical model's draws moved onto the averaged centre (`models/blend.py`). The weight was
read off 2022 and 2023, never the backtest. So the challenger is fitted at freeze time as well
as at every backtest origin, and a freeze refuses when the saved challenger run does not match
the code it would publish with.

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

**Measured 2026-09-19**, the last list before the gun (00:28Z) against Athletics NorthEAST's
finish lists, by name key within each event: of 629 entrants in the four road events, 534
finished under a name on their event's list, so **15.1% were not found** (25% of the
marathon, 11% of the half, 15% of the 10 km, 19% of the 5 km). That is an upper bound on
no-shows: it also holds non-finishers and anyone whose name was printed two ways. Of 545
finishers, **2.0% were not on their event's list**, and 7 of those 11 were on another event's,
so switches rather than late entries.

**Field-forecast mode** (Run to Remember, any race without a list): a logistic participation
model on whether a runner ran this race last year, ran any NLAA race in the last six months,
their series-standings participation this year, their number of results, and the target
distance against their usual distance. Predict for everyone above a threshold chosen in the
backtest to balance the two coverage numbers; publish both numbers with the predictions so
the reader knows what a list would have added.

**Built 2026-09-21, section 13 item 42**, with two changes the backtest made: the series
standings are computed from the results rather than fetched, with a feature for how much a
runner's usual races share their crowd with this one; and the field is named by count (the
expected number of finishers times a scale set on 2022 and 2023) rather than by a probability
threshold, which named nobody at small races. On 2024 and after: recall 27.7%, precision
30.2%, and 61.5% of finishers visible to any list-free forecast at all.

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

**Amended 2026-09-19, at Peter's request: a prediction week, not a single file.** From seven
days before the race, `freeze --daily` publishes a file a day holding only the entrants in no
earlier file, predicted with that morning's forecast at that lead (the forecast error is now
measured per lead, one to seven days, in `data/forecast_error_by_lead.toml`). The day before,
the final file recomputes the whole field with the day-before forecast and gives places,
naming the daily file each runner first appeared in (Peter's correction the same day: a
forecast a week old is of poor value by then, so the final file is the one that counts for
the weather). One fit serves the week and is refused
if the archive moves under it; each entrant's random numbers are seeded by the race and their
name, not their place on the list, so the same entrant gets the same numbers on any day
(`publish/daily.py`). `finishline page` renders the race page from the published files after
each one. Peter authorised `scripts/daily-predictions.ps1`, run each morning at 06:15 by Task
Scheduler, to commit, tag and push the files and the page; it commits nothing else, and
`freeze` still refuses with uncommitted code. Consequence: the repository has to be public
seven days before the rehearsal, 2026-09-27, rather than the day before.

**The website, added the same day.** `finishline site` builds one page in the style of the
other project pages on peterparker.ca: what this is and the headline backtest numbers, a race
picker (each race's course, history, entrant field by history depth, its prediction week,
the model's backtest on its last edition, and once published the predicted field, the top 20
with placeholders for expected newcomers at the biggest races, every runner with a name
search, and every file with its hash), then the whole method in sixteen illustrated parts,
each plain first with the technical detail folded away. Its numbers come from
data/site/results.json, which `finishline report` writes from the same objects as the
README's tables, so the two cannot disagree. No framework, no tracking, no third-party
request, no inline script or style (the host's content security policy refuses them); the
runners' names are only in data/predictions/, which robots.txt disallows and the host marks
noindex. Hosted like project 08, on Azure Static Web Apps'
free plan at finishline.peterparker.ca behind a Cloudflare CNAME, but deployed by the Website
workflow on every push, as peterparker.ca is, so the morning task's commit refreshes it
(docs/deploy.md). This is section 7's reserve line, now used, at CA$0.

### 5.8 What is on this year

**Added 2026-09-20, at Peter's request: the race list populates itself.** `data/live.toml`
is the right source for the races this project predicts and the wrong source for the season.
It cannot say the Trapline is on in three weeks, it cannot notice a race moving, and it goes
stale the day one is cancelled. `finishline calendar` reads
`https://www.nlaa.ca/calendar.php`, the association's own fixture list, and writes
`data/calendar.json`, which the website's race picker is built from (`ingest/calendar.py`,
docs/data-terms.md). No race is ever typed into the site by hand.

The picker has three shelves and the first two are the interesting distinction: **entries
open** means a start list has been seen with somebody on it, **announced** means the race is
on the calendar and no list has been seen, and **already run** is section 5.9. A date in the
future is not evidence that registration is open, and the only evidence this project has
either way is the snapshot.

Three things the calendar forced that the results index never did:

- **A calendar entry is a day, not a race.** The index has one row per race per distance;
  the calendar has "Uniformed Services Run Marathon/Half-Marathon/Marathon Relay/5km/10km",
  which is one row and five races. An entry therefore carries a course family and a date and
  no distance, and `retrospect.events_on` is where one becomes several.
- **"Relay" disqualifies an index row and not a calendar entry.** On the index a row that
  says relay is the relay. On the calendar it is one component of a day that also has a
  marathon, and reusing `nlaa.NOT_ROAD` unchanged dropped the whole USR. The words that mean
  a different sport (cross-country, trail, a schools meet) are kept apart from the words that
  name one component of a day.
- **Three track meets carry a road course's venue in their name.** "Pearlgate Twilight Meet"
  matches the `pearlgate` alias, so the track-and-field test has to run before the alias test
  or the calendar files a tetrathlon as a road race.

Of the 40 rows on the 2026 calendar, 15 are road races and 25 are not; exactly one row
matches nothing this project knows, and `finishline calendar` prints it first, because a new
road race with no alias yet is the only skip here that is ever a bug rather than a fact about
the sport. Races this project does not predict are listed anyway, with the reason: a list
that quietly omits them would be a list that flatters this project.

### 5.9 A race that ran before anything was published

**Added 2026-09-20.** The Uniformed Services Run went on 2026-09-13, a day after the first
entrant-list snapshot and three weeks before the first race this project freezes for. There
is a start list from before its gun, an official finish list from after it, and in between
there is what the model would have said. That is the only end-to-end demonstration this
project has before the Turkey Tea, and it is on the website
(`publish/retrospect.py`, `data/retrospect/`).

⚠️ **It is not a prediction and nothing may call it one.** Nothing was frozen, hashed or
tagged before the gun, so it is not in the public record and is not scored in `scores/`. Its
rows are the ones `backtest/run.py` already produced, held out by construction: the fit that
made them saw nothing from the quarter the race falls in or later, which for 2026-09-13 means
nothing after 2026-06-30, and `check_no_leakage` asserts it at every origin. The file lives
under `data/retrospect/`, never under `predictions/`, so no address can confuse the two, and
the card on the website opens by saying what it is not.

**Peter's question, 2026-09-20, and the answer**: are these last week's model or this one?
This one. `saved.load` refuses rows whose key does not match the dataset and the source of
every module that shapes a prediction, both saved files' keys match the code as it stands,
and the blend that publishes is computed from them at `WEIGHT = 0.65`. The four USR races are
already among the 53 test races behind every headline figure on the site; this surfaces rows
that were being published in aggregate already.

**Only an event whose road had been run before is scored**, which for the 2026 USR means the
10 km alone. Its course has nine earlier editions; the marathon and half moved to new routes
in 2026 and the 5 km had never been run, so for three of the four the model was predicting a
road with no course factor at all, and an error measured there is mostly the cost of that.
The rule is mechanical (`retrospect.scorable`: does the course have an edition before this
one?) rather than a judgement made race by race, and the three unscored events are listed on
the page with the reason, because a reader told about the 10 km and not about the marathon
beside it has been told half of it.

Measured, blend against the baselines, on the 161 of 171 finishers the archive can identify:
**4.74 min average miss** against carry-forward's 4.43 over the 136 carry-forward can answer
for at all, and **3.81 against 4.43 paired on those 136**; 78% of finishes inside the 80%
range; 14 places out at the middle. Split by where a runner finished in their own field, the
minutes grow down the field and the share of a finish time does not: 3.6 min at the front
quarter, 4.5 mid-pack, 6.4 in the last quarter, and 7.5%, 7.5%, 7.9% of a finish time. The
start list against the finish list: 198 listed in the 10 km, 171 finished, 168 found, so
15.2% not found (an upper bound on no-shows, section 5.6), and 3 finishers on no list.

**The runner table is the race that was run**, all 171 finishers in the order they crossed
the line, with the place the results page printed. The ten with no prediction are tagged
"(potential duplicate)" beside the name, carry the resolver's own sentence behind that tag,
and say "No prediction" where the range would be. See item 38 for the two versions before it
that were wrong, and why the second one was worse than the first.

**"Out by" is the finish minus the prediction** (changed 2026-09-20 at Peter's request):
somebody who took two minutes longer than the model called reads +2:00. That is the opposite
sign to `score.Scored.error` and to every bias table in this repository, which are read on the
model and stay as they are. The flip is at the last step before the page, so nothing measured
moves with it.

**Green in that table marks the published range holding**, and briefly marked a miss under a
minute, which is a threshold nobody declared and this project does not measure: a runner whose
finish landed inside their own range could read as a failure. It is now the same green, with
the same meaning, as the scatter plot directly above it.

Two things this cannot do, and the page says both. **A place here is a rank, not a
simulation**: a published place is drawn from thousands of simulated races and needs a
posterior, and the backtest kept its scored rows rather than its fits, so the predicted place
is the order of the predicted times and carries no range. **The club's finish lists print no
hometown, no sex and no age band**: a place, a name, a service affiliation, a bib and the
times, and nothing else.

**The gender and age group columns are therefore borrowed, and dated** (added 2026-09-20 at
Peter's request; the decision it settles was parked in `docs/todo.md`). They are what the
association's own results last printed for that runner before this race, which is public on
nlaa.ca under the same name, and the page says at which race and on what date. **This race's
own page wins as soon as it has them**: `store.build` drops the club's copy the moment nlaa.ca
carries the same date and course, `printed_category` then reads the new page's own columns,
and `store.borrowed` (printed by `finishline dataset`) is where that swap can be seen having
happened. The swap was always automatic and was always silent, which for a swap that changes
what may be published about a person is not good enough. 136 of the 171
have a gender and 133 an age group. Three rules keep it honest, all in
`retrospect.printed_category`: only results dated before this race count, because a
description taken from a later page would be the one thing on a held-out page a reader cannot
check; a band the runner has certainly grown out of since is left blank rather than aged
forward, tested against the resolver's own birth-year windows (`still_possible`, which drops
two of the 135 and would drop a 20-29 printed in 2016); and a finisher with no prediction gets
neither column, because that row exists to say this project does not know which person it is.
The bands differ in width, 30-39 beside 45-49, because the races that printed them do, and
widening them all to decades would print a band no page printed. This is a widening of
CLAUDE.md's publishing rule, made in the same commit as the code.

## 6. Week by week

Relative weeks, anchored to the first live race. Evenings and weekends.

| Week | Dates | Built | Done when |
|---|---|---|---|
| 1 | Sep 14 to 20 | `docs/data-terms.md`; courtesy emails to NLAA and Athletics NorthEAST (Peter); daily snapshot of the two entrant lists (a scheduled local fetch, from Sep 12); crawler, cache, parser with golden tests, including the Cape to Cabot archive PDFs and the series standings; name normalisation and resolution with the labelled pairs; the USR list of Sep 12 resolved against the USR results when posted, giving the first no-show and name-match rates; the dataset with checks; the three baselines; the rolling-origin harness with the leakage test | Every 2016 to 2026 road result parsed; resolution precision and recall stated; USR no-show and match rates measured; baseline MAE per stratum in a table with CIs |
| 2 | Sep 21 to 27 | Course files for Cape to Cabot, Run to Remember and the five or six courses that carry most of the history; Minetti grade model; Open-Meteo archive for every race edition; the neutral-condition layer; the hierarchical model; LightGBM challenger; Mondrian conformal; the backtest table | Backtest tables filled: skill, coverage, width, place error per stratum; ablation of the normalisation; course factors with CIs |
| 3 | Sep 28 to Oct 4 | Placing simulation; participation model; prediction file, schema, hash, `freeze` and `score`; race page; README with backtest tables and the honest limitation; CI; **repository public**; dress rehearsal: freeze and publish predictions for Turkey Tea 10 km (Oct 4) if the pipeline is ready by Oct 2, else for the Trapline 10 km (Oct 11) | A prediction file for a real race committed and tagged before its gun, and scored after |
| 4 | Oct 5 to 11 | Fix what the rehearsal broke; freeze the model version for Cape to Cabot; `docs/methods.md`; the rejected-approach evidence and `docs/rejected.md` | Model version tagged; nothing in `models/` changes after this week |
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
| **Wind and course constants from 11 do not transfer** (fitted on one athlete's training runs) | They are priors with stated width, and the race-edition effect is estimated from data; section 10's candidate 2 measures exactly this |

## 10. Candidates for the rejected approach

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

Whichever produces the clearest evidence becomes `docs/rejected.md`. Strava is not a
candidate: it was rejected on terms, not on evidence, and belongs in `docs/data-terms.md`.

**Settled 2026-09-19: none of the three.** The clearest evidence the work produced was for
a fourth design, weather as a straight line in temperature (section 13 items 29 and 30),
rejected on two leave-one-year-out tests with intervals that clear zero. That is
`docs/rejected.md`. Candidate 1 is in the README tables already (best equal-VDOT answers for
63 to 87% of runners and has no interval); candidate 2 was not refuted, since the Minetti
check on Cape to Cabot agreed with the measurement; candidate 3 now has its evidence (section
13 item 33: LightGBM's raw quantiles under-cover at every depth and conformal repairs them),
but it was never tried as a published design, so it is recorded there rather than here.

## 11. Definition of done

- [x] Data-terms check done for Strava and for the results provider, recorded here (2026-09-12)
- [x] `docs/data-terms.md` in the repository with dates, the NLAA courtesy contact and the removal path (notices sent 2026-09-12)
- [ ] Every NLAA road result 2016 to 2026 parsed; resolution precision and recall stated. **Open on both halves (2026-09-21):** the pages not read are named in docs/data-terms.md (a few PDFs, the 2017 Turkey Tea's HTML table), and the hand-labelled pairs of section 5.2 have not been labelled, so no precision or recall is stated yet (docs/todo.md item 6)
- [x] Baselines (carry-forward, best equal-VDOT, category median) reported first, with every later result as skill against carry-forward
- [x] Rolling-origin backtest over 2024 to 2026 editions: MAE, percentage error, coverage at 80% and 90%, width, place error and Spearman, per history-depth stratum, bootstrap CIs
- [ ] Normalisation ablation and course factors per course with CIs. **Half done (2026-09-21):** course factors with CIs and the weather ablation are in the README; an ablation of the course normalisation is not
- [x] Hierarchical model against the challenger, paired, per stratum (and the blend against each)
- [x] Conformal assumption stated beside every coverage table
- [ ] A dress-rehearsal prediction file tagged before a real race and scored after
- [ ] Predictions for Cape to Cabot 2026 committed, tagged and hashed at least 24 hours before the gun
- [ ] Error published after Cape to Cabot 2026: finish-time MAE in minutes, coverage, placing error, field coverage
- [ ] The same for Run to Remember 2026 on the frozen model
- [x] One rejected approach documented with evidence (`docs/rejected.md`; the scripts behind it are in `experiments/`)
- [x] Public name decided (Finish Line Forecast, 2026-09-06; renamed The Whole Field, Called Before the Gun, 2026-09-20)
- [x] Repository public before the first live race (2026-09-19); `v0.1.0` tagged after the first scored race

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
   clean switch over time. One runner settled it: a consistent ageing sequence with times
   improving throughout, cut into two half-histories by a move out of the province. The age
   bands are now the only thing that splits a name, because a runner cannot get younger, and
   the hometown only breaks a tie. Runners held back fell from 2,608 to 119 and runners with
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

    ⚠️ **The weather ablation is a null and the coefficients are not, which took three
    measurements and two wrong conclusions to establish.** The same eight fits without the
    weather terms give 17.9, 9.6, 8.6 and 5.5 minutes, inside the full model's interval at
    every depth; paired on the 18,278 predictions both runs make, the gain is 0.0003 (95% CI
    -0.0008 to +0.0002). Nor is that the weak form of the test: every target race falls after
    its block's origin, so neither model has an edition effect for it, and `predict` is handed
    the airport's observed temperature and wind for that morning rather than a forecast, which
    is the position a freeze is in with better information than a freeze has.

    The first conclusion drawn from that, that observed weather carries no signal, was wrong.
    Fitted on the whole archive (`scratch/weather_coefficients.py`), the four coefficients are:

    | Term | Per unit | 95% interval | ESS bulk | R-hat |
    |---|---:|---|---:|---:|
    | temperature above neutral | +0.120% | +0.074 to +0.164 | 18 | 1.17 |
    | temperature x log distance | +0.209% | +0.143 to +0.275 | 34 | 1.11 |
    | wind speed above neutral | +0.0247% | +0.0087 to +0.0425 | 14 | 1.24 |
    | tailwind along the bearing | +0.001% | -0.040 to +0.038 | 9 | 1.35 |

    which is a degree costing -0.02% at 5 km, +0.12% at 10 km, +0.27% on Cape to Cabot and
    +0.42% at a marathon, all but the tailwind with the whole posterior on one side of zero.
    A weather term that moves the level of a field by one to three percent cannot show up in
    a mean absolute error of ten percent per runner. The ablation measured the wrong quantity
    for the question, and the README now says so.

    ⚠️ **What is genuinely open: the fit applies about half the weather its own residuals
    still want.** The conditions layer, fitted on edition effects alone, puts a degree at
    10 km at +0.233% (+0.129 to +0.342), about twice the joint fit's +0.120%. Race-level
    median bias across the 32 backtest races with an observation slopes -0.69 (+/- 0.27)
    against the conditions adjustment, and -0.68 (+/- 0.28) with calendar year and a summer
    indicator in the regression, so it is not the year effect wearing a hat. The 2025 USR half
    marathon at 13.6 degrees above neutral came out 3.7% too fast and the 2026 Tely 10 at 10.1
    above 3.4% too fast. Two candidates, neither settled: bulk ESS of 14 to 34 on these terms
    is thin enough that the posterior mean may sit below the truth, and one multiplicative
    coefficient assumes heat costs the front and the back of a field the same fraction, which
    a hot race does not look like. Owed before Cape to Cabot is frozen. The scripts are
    `scratch/weather_posthoc.py` and `scratch/weather_confound.py`.

    ⚠️ **The placing table is not a like-for-like comparison and must not be read as one.**
    Places are scored among the runners each model answered for, so carry-forward is ranked
    over the 12,714 runners with a prior result and the model over the whole field, the 5,594
    entrants with no history included, which is why its mean absolute place error is 53.4
    against carry-forward's 25.8. Scoring the model on carry-forward's subset is the missing
    measurement; it belongs beside the current table, not instead of it, and it is owed before
    the first freeze.

    **Measured 2026-09-19, on item 30's backtest** (`score.paired_placing`, a second table
    `finishline report` writes under the first). Ranked among the runners both answered for,
    race by race, in the 47 races with at least ten of them (12,682 runners), the model's mean
    absolute place error is 24.9 against carry-forward's 26.8, a paired difference of -1.9
    places (95% CI -3.4 to -0.8, resampling races), and Spearman 0.858 against 0.850 (+0.008,
    -0.005 to +0.023). So on the same runners the model orders a field better than the
    baseline, if by less than it times one, and the 53.4 was the newcomers. Best equal-VDOT on
    its own shared runners is -1.3 (-2.6 to -0.2) against carry-forward.

    **One operational note, because it cost a night.** A fit on the whole archive commits
    about 27 GB on this machine, and the eighth block failed three times on a 216 MiB
    allocation with the Windows commit limit at 48 GB. Blocks are now written as they finish
    (`backtest/saved.py`, `BlockStore`), so a failed run resumes instead of restarting, and
    the pagefile was raised to a fixed 64 GB. The freeze fit is the same size as that eighth
    block, so this is a constraint on October 17, not a one-off.

30. **Heat is a hinge on felt temperature, the sun is part of the temperature, and the
    calendar-year effect had been carrying the weather.** Found on 2026-09-18 by asking why
    the 2026 Tely 10 was predicted 3.4% too fast when the 2024 edition, on the same kind of
    morning, was not. Four designs failed on the way, and each is written down.

    The same runners ran the 2026 Tely 4.5% slower than the 2025 one (1,874 of them), and the
    2025 one 5.3% faster than 2024's; the Tely swings like this in every consecutive pair since
    2022. Humidity and dew point explain none of what the model leaves over (dew point
    +0.010% per degree, CI -0.110 to +0.182; relative humidity R2 0.085), and the heavy StudentT
    tail is not suppressing the weather: held at nu = 8 instead of the fitted 1.63, the weather
    coefficients are unchanged to the third decimal, though mixing improves five to ten times.
    Solar radiation on its own explains nothing either, and 2024 and 2026 were the same
    cloudless 16 C morning with residuals of -0.6% and -3.4%.

    What does explain it: Peter's specification, that sunshine has no effect of its own but
    raises the temperature a runner feels, and that the cost of that felt temperature is not
    linear. A first grid, five random folds over 227 editions, put the sun at +3 C of cloud
    cover and the knee at 10 C (out-of-sample R2 0.320 against 0.163 for the linear model).
    Peter then pointed out that Overload uses +15 F, 8.3 C, for a full sun, and
    asked what the data says across versions. The answer took two tests, scored leave one year
    out so that a warm year cannot pose as weather:

    - **A, editions against their own course** (227 editions): best knee 2 to 6 C, with a
      small sun of 2 to 6 C adding at most +0.03, inside the noise. Linear temperature 0.184,
      the best hinge 0.367; Overload's exact pair (8.3 C of direct sun, knee 15.6 C) is 0.139
      behind the best, interval +0.057 to +0.229.
    - **B, the same runners in consecutive editions** (121 pairs, 19,035 runner pairs), which
      holds the field fixed: every weighting prefers no sun, and the knee rises with how much
      the Tely counts, 15.6 to 18 C weighted by runners (the Tely is 60% of the pairs), 14 to
      15.6 capped at 200, 12 to 14 with every pair equal, and nothing distinguishable without
      the Tely at all.

    What is robust is that heat is a hinge, that cold is not a bonus, and that the old linear
    term is the worst option in both. The knee is set at 12 C, the value whose worst shortfall
    against the best of any single test is smallest (0.115). The sun is not settled by either:
    test A barely sees it and test B is better without it, which is what a real effect measured
    through a 9 km reanalysis sky looks like as much as it is what no effect looks like, and
    Overload's own 45 days of thermometer readings at this coast caught that sky reporting full
    cloud with the runner in sun. So the sun's size is estimated inside the model rather than
    chosen: the direct radiation over the race hours as a share of a clear noon (Overload's
    measure), and a boost in degrees with a HalfNormal prior on the NWS scale of 8.3 C, which
    puts nothing and twice that in reach. The fitted boost is below.

    Fitted free, a linear distance scaling claims that a hot 5 km is 7% fast and a hot marathon
    26% slow, which is summer short races being quick for reasons that are not the weather. So
    heat is scaled by log distance over 5 km rather than over 10, and both heat coefficients
    are HalfNormal: the cost of a hot morning cannot be negative and cannot fall as a race
    gets longer.

    ⚠️ **The constants were chosen on editions that include the backtest's own races**, 2024 to
    2026 among them. Two round values chosen on 18 years flatter a backtest of three only a
    little, but they flatter it, and the backtest tables are read with that in mind.

    ⚠️ **The calendar-year effect of item 29 was mostly weather.** Averaged by year, the
    editions' course-relative effect tracks the year's average temperature at +0.403% per
    degree (correlation +0.63 over 18 years), and taking the edition-level weather adjustment
    out collapses it to +0.019%: 2023 from +4.47% to +1.17%, 2024 from +2.47% to -0.07%, 2026
    from +2.69% to -0.25%. The "calendar drift" that item 29's year effect was built to absorb
    was substantially a run of warm Junes. A year level that walks forward, fed by weather
    it should not have been given, then carries a cool 2025 into 2026 as if the runners had
    got faster, which is exactly the 2026 Tely. It is also why the linear weather terms came
    out at half the edition-level estimate: collinear with the year's average, they were
    identified only by differences between races within a year.

    **What the whole archive says the sun adds: about a degree.** One fit on everything, knee
    at 12 C, the sun estimated: a full direct sun adds a median 1.0 C to the felt temperature
    (50% interval 0.4 to 2.0, 95% 0.04 to 6.2), against a prior whose median was 5.6. The
    posterior is a third as wide as the prior, so this is the data speaking, and it puts
    Overload's 8.3 C outside its 95% interval. It says what the sun is worth *as this archive
    measures it*, through a reanalysis cell, and a noisy measure of a real effect is pulled
    toward zero; so it bounds what this model can use, not what the sun does to a runner.
    Overload's own observed sun share is the better witness, and its 15 F stays untouched there.

    With the knee at 12 C the heat costs more per degree than the linear model claimed: per
    degree of felt heat, +0.06% at 5 km, +0.26% at 10 km, +0.40% on the Tely, +0.47% on Cape to
    Cabot and +0.69% at a marathon. An overcast 18 C Tely costs +2.4% (95% interval 1.9 to
    2.9); a 22 C one with 70% of a clear noon's sun +4.4% (3.5 to 5.5). Wind +0.028% per km/h
    (0.012 to 0.045); the tailwind still a null.

    The year effect still leans on the heat a little: correlated with each year's mean felt
    heat at +0.36 once both are detrended, and +0.23 in year-to-year changes, against +0.46
    and +0.23 under the first heat term. On 18 years neither is distinguishable from zero, so
    the year walk is left as it is and the backtest, which scores the 2026 Tely directly, is
    the test. `sigma_year` still mixes badly (R-hat 1.44, ESS 8), which is item 29's ridge.

    **Start times, supplied by Peter on 2026-09-18, and they matter.** No results page prints
    a start, and every weather read above assumed 9 am. The organisers' times are 8 am as
    standard and 7 am for a marathon, with the Uniformed Services Run staggered 7, 8, 9 and 10
    by distance and the Five and Dime 10k at 9 (`data/starts.toml`, `finishline/starts.py`).
    The same series ran on the same schedule under earlier names: the Provincial and Huffin
    Puffin marathons with the Nautilus half, and in 2022 the Capital Subaru marathon and half,
    whose 10k the archive files as `quidi-vidi-10000` after the brewery that named it and
    which started at 7:30, read as the 7:00 hour. Half-hour starts are taken as the hour they
    begin in, because the readings are hourly.
    Read from the real start, both tests of this item sharpen, the same-runner test most: its
    best out-of-sample R2 rises from 0.485 to 0.672 weighted by runners and from 0.417 to 0.532
    capped, and without the Tely from 0.18 to 0.23, which is what a covariate with less error
    in it looks like. The editions test still prefers a low knee (0.38 at 4 C with a little
    sun) and the same runners a high one (14 to 15.6 C, no sun). Ranked by worst shortfall
    across the editions test and the capped and equal same-runner tests, knees of 10, 12 and
    14 C are within 0.04 of each other (0.148, 0.169, 0.188), so the knee stays at 12 C, the
    middle of a range the data cannot split, rather than moving on a criterion that close. The
    day-ahead forecast error was remeasured over the real hours: 1.5 C cold and 7.2 km/h calm,
    against 1.4 and 7.7 read from 9 am.

    **The gate refitted from the real start times, 2026-09-19** (`scratch/sun_fit.py`, output
    `scratch/sun_fit.txt`). The numbers above were read from 9 am and are kept as they were
    measured; these supersede them. A full sun adds a median 2.1 C (50% 0.9 to 4.2, 95% 0.1 to
    9.2), the posterior half the prior's spread, so Overload's 8.3 C is now inside the 95%
    interval though far from the middle of it: earlier starts meet less sun, and less of the
    sun signal was being mislaid onto the heat. Per degree of felt heat: +0.05% at 5 km (0.00
    to 0.13), +0.31% at 10 km (0.23 to 0.39), +0.50% on the Tely (0.37 to 0.61), +0.58% on Cape
    to Cabot (0.43 to 0.71), +0.87% at a marathon (0.64 to 1.06); wind +0.027% per km/h (0.011
    to 0.045); tailwind a null. An overcast 18 C Tely costs +3.0% (2.2 to 3.6), a 22 C one with
    70% sun +5.9% (4.4 to 7.5). The year effect against felt heat: +0.53 raw, +0.31 detrended,
    +0.20 in year-to-year changes, still indistinguishable from zero on 18 years, so
    `sigma_year` is left alone; it still mixes worst (R-hat 1.29, bulk ESS 10).

    **The backtest, 2026-09-19.** Both runs from scratch, eight quarterly fits each, the
    weather run at 152 minutes and the ablation at 163, neither needing a retry. Mean absolute
    error in minutes with the felt-heat model: 17.8 at no prior results, 9.4 at one, 8.5 at two
    or three, 5.4 at four or more (27% skill against carry-forward's 7.4); without weather
    17.9, 9.6, 8.6, 5.5. Paired on 18,278 predictions the weather gain is 0.0010 of absolute
    log error (95% CI -0.0019 to +0.0002, resampling races), better at every depth, clear of
    zero only at no prior results. Against carry-forward on the 12,714 runners both answer
    for: 0.0743 against 0.0881, race-centred 0.0722 against 0.0780, a paired difference of
    -0.0059 (-0.0093 to -0.0036); bias -0.7% (-1.8 to +0.6) against carry-forward's -0.4%
    (-2.6 to +1.9). Coverage and widths as before within a point.

    **Rerun the same day on the data with the 2026 USR results and both route splits** (53
    backtest races, 184 minutes, weather run only; the ablation reruns when the CPU is free):
    18.3 at no prior results (the category median 18.4), 9.4 at one, 8.5 at two or three, 5.4
    at four or more, still 27% skill against carry-forward's 7.4. Paired placing against
    carry-forward on 13,081 runners in 51 races: 1.8 places better (95% CI 0.7 to 3.1).
    Nothing that mattered moved.

    The test this item was built for is the race level, and it passes. Across the 32 backtest
    races with an observation, median race bias regressed on the weather cost the model
    applied (whole-archive posterior medians, so approximate): the no-weather run leaves
    +0.42 (+/- 0.30) of each point of heat cost in its errors, the felt-heat run -0.15 (+/-
    0.30), and -0.14 with calendar year in the regression. Item 29's linear run, regressed on
    the same felt-heat cost (`experiments/rejected_slope.py`), leaves +0.11 (+/- 0.31): the
    backtest cannot tell the two weather models apart, and item 29's "-0.69, half the effect
    unapplied" was measured against the conditions layer's own adjustment, a different
    regressor, so it does not compare with these. The case for the hinge rests on the
    eighteen-year tests above and is written up in docs/rejected.md. The 2025 USR, 22 C for the half, moved from 1.0 to
    1.4% too fast to 0.6 to 1.2% too slow; the 2025 Tely from 2.2% too slow to 0.7%. The 2026
    Tely is not fixed: 18.4 C, 29% sun, calm with a tailwind, charged 3.1% and still 3.0% too
    fast. Heat does not account for it, and it stays an open question rather than a reason to
    move the knee. Per-fit diagnostics: no divergences with weather, worst R-hat by fit 1.41,
    1.46, 1.77, 1.68, 1.50, 1.58, 1.87 and 2.15, smallest bulk ESS 5 to 9; the ablation has
    13 divergences over two fits and R-hat 1.39 to 1.82. Scripts: `scratch/felt_heat_readme.py`,
    `scratch/model_vs_cf.py`, `scratch/race_bias.py`.

31. **The model's poor mixing reaches first-timers' predictions and not returning runners',
    and the obvious constraint made it worse everywhere.** Measured 2026-09-19 on the
    2026-07-01 origin, the backtest's worst fit (R-hat 2.15), with the backtest's settings
    (`scratch/ridge_check.py`, output `scratch/ridge_check.txt`). Deriving the quantities a
    prediction actually reads, per chain: a returning runner's level in the last fitted year
    (fitness, form, ageing and the year effect together) converges, R-hat median 1.006 and
    worst 1.08 over 600 sampled runners, bulk ESS median 500 to 900. A first-timer's starting
    level, `mu_group` plus the latest year effect, does not: R-hat up to 1.27, ESS 11. The
    hyperparameters that mix worst are `sigma_year` (1.32), `sigma_alpha` (1.26), the latest
    year (1.26) and `mu_group` (up to 1.30). The age-period-cohort line itself, a common
    shift in every group's ageing drift against a slope in the year walk, mixes acceptably
    (R-hat 1.05, ESS 129), so the wandering is in the level of the year walk against the
    group means rather than in its slope.

    **Refuted: removing the year walk's least-squares line, and starting first-timers from
    recent first-timers' fitted levels.** The constraint pins both the level and the slope of
    the year walk, which is where the theory put the trouble. Fitted on the same origin with
    the same settings (`scratch/ridge_check_fixed.txt`; the code is kept as
    `scratch/hierarchical_item31_refuted.py`), every quantity got worse: returning runners'
    levels to R-hat median 1.66 and ESS 7, `sigma_course`, `sigma_edition`, `sigma_year` and
    the latest year to 2.4 to 2.6, `mu_group` to 3.0. The chains no longer agree on anything,
    which is the signature of a posterior the constraint made harder to move through rather
    than easier. The model is back as it was, and the backtest numbers in item 30 stand.

    What this leaves: the published predictions for runners with a history rest on quantities
    that converge; predictions for first-timers carry sampler noise beyond their stated
    interval, which is one reason their year-to-year bias swings (3.7% too fast in 2024, 2.1%
    too fast in 2025, 3.3% too slow in 2026). Longer tuning is the untried, cheap next step;
    the conformal layer, calibrated per history depth, is what keeps first-timers' intervals
    honest in the meantime, and their coverage table is the check.

32. **At the biggest races, a newcomer is not an average newcomer.** Peter's point, 2026-09-19:
    runners from away, often with no result here at all, take top places at the Tely and Cape
    to Cabot, and a model that predicts every newcomer from the group prior puts all of them
    mid-pack, so its predicted top ten misses them and every local runner's place comes out a
    place or two too good. Measured (`scratch/outsiders.py`): at the Tely about four of the top
    ten have been from away in recent years, one or two of them with no result here (2nd in
    2025, 3rd and 4th in 2026); Cape to Cabot has about one a year in its top ten. In the
    backtest the model's predicted top ten held 5 to 9 of each big race's actual top ten, and
    first-timers were among the misses.

    The design (`placing/unseen.py`, switched on per race by `newcomers = "course"` in
    data/live.toml, set for Cape to Cabot and meant for the Tely, not for smaller races): a
    newcomer's log time is the known field's median in the same simulated draw plus an offset
    drawn from how this course's first-timers finished against the returning field of their
    own edition, pooled over editions from 2013 and split by sex. It does not say which
    newcomer is fast, because the list cannot; it puts the right number of unknowns near the
    top, and the race page shows those places as placeholders beside the named runners, with
    the expected count and its range. It lives in the placing and freeze code, so the model and
    its backtest are untouched.

    Checked against history (`scratch/unseen_check.py`: each edition from 2016, the pool from
    earlier editions only, returning finishers at their actual times so only the newcomer part
    is tested): Tely, first-timers in the top ten expected 5.0 over seven editions against 6
    actual, top twenty 9.0 against 9; Cape to Cabot, top ten 4.0 over nine editions against 7,
    top twenty 11.5 against 16. So it is about right at the Tely and **still short at Cape to
    Cabot by about a third**, whose first-timers are faster than its pooled history says (2021
    alone had three in its top ten). Reported as it stands rather than tuned before the race.


33. **The challenger is more accurate than the model it was meant to test.** Section 5.4's
    LightGBM, backtested 2026-09-19 on the same 53 races (`models/gbm.py`, eight quarterly fits
    of about a minute each against the hierarchical model's twenty-odd). On the same runners,
    with the difference in points of a finish time and races resampled (`score.paired_error`):
    runners with one prior result -0.87 (-1.72 to -0.41), two or three -0.84 (-1.26 to -0.62),
    four or more -0.25 (-0.47 to -0.07), all favouring LightGBM; first-timers +0.96 (-0.85 to
    +2.42), level. In minutes: 8.8 against 9.4, 7.9 against 8.5, 5.3 against 5.4, 18.9 against
    18.3. It also orders a field better: 3.9 places closer than carry-forward on the same
    runners (1.9 to 6.4) against the hierarchical model's 1.8, Spearman 0.873 against 0.857.
    Two marginal MAE intervals overlap at every depth, which is why the paired test is the one
    reported: the same runner's two errors move together.

    Section 10's candidate 3 has its evidence at the same time: LightGBM's own 80% quantile
    ranges held 68 to 72% of finishes and its 90% ranges 82 to 84%, under-covering at every
    depth; the conformal layer brings them to 75 to 77% and 87 to 88%, and at four or more
    prior results its calibrated 80% range is 12.7 minutes wide against the hierarchical
    model's 13.6. So the challenger's point predictions are better and its raw intervals are
    worse, which is the result the candidate predicted, and a reason the conformal layer is not
    optional for either model.

    What it does not settle, and is not settled here: the published predictions are the
    hierarchical model's, because the placing simulation needs joint draws of a whole field on
    one shared morning and the forecast's error as noise, which quantile trees do not give. A
    first look at an average of the two models' medians was better than either at four or more
    prior results (5.05 minutes) and for first-timers; it is not a published number until it
    has its own paired interval. **Settled in item 35**: the average publishes, weighted 0.65
    towards the challenger, with the hierarchical model's draws moved onto the averaged centre
    so that a place and a time stay one prediction. That covers Turkey Tea and Cape to Cabot
    alike, so the sentence this item first ended on, that Turkey Tea would be predicted by the
    hierarchical model as built, no longer holds.

34. **Tuning the challenger bought about one percent, and six of the nine ideas made it
    worse.** Peter asked whether more could be squeezed out of the challenger, which is fair:
    item 33's configuration was fixed before its first run and never touched. Doing that on
    the 2024+ backtest would turn the test set into a validation set, so the search
    (`experiments/tune_gbm.py`) runs on **2022 and 2023 only**: each half-year's races predicted
    from history strictly before it, the same block scheme as the backtest, 7,598 finishes
    scored on mean absolute log error, and the 2024+ rows rerun once afterwards with what the
    search chose. Numbers below are points of a finish time (0.10 is a tenth of a percent),
    "all" over every row and "known" over runners with a prior result.

    | Change | All | Known | Against the first configuration (95% CI, races resampled) |
    |---|---:|---:|---|
    | The first configuration | 9.705 | 6.913 | baseline |
    | Random search, 40 parameter sets | 9.625 | 6.845 | -0.079 (-0.148 to +0.007) |
    | **Search plus a second batch of features** | **9.610** | **6.838** | **-0.095 (-0.170 to -0.012)** |
    | Course-and-edition normalised form features | 9.989 | 7.280 | worse |
    | The same, with raw form removed | 10.150 | 7.530 | worse |
    | Every feature at once | 9.963 | 7.283 | +0.258 (+0.043 to +0.474) |
    | Trees started from the runner's last result | 9.773 | 6.968 | worse |
    | Linear-leaf trees | 13.296 | 11.507 | much worse |
    | Training rows weighted by recency (3 y half-life) | 9.665 | 6.963 | worse |
    | Training rows from 2014 on only | 9.692 | 7.019 | worse |
    | Averaging three seeds | 9.622 | 6.846 | nothing |
    | Huber loss for the median | 9.577 | 6.890 | better overall, worse at depth 1 to 3 |

    What was kept: the parameters the search found (learning rate 0.03, 15 leaves, 20 rows a
    leaf, L2 1.0, 1,200 rounds) and ten more features, each either a shape the hierarchical
    model is told about or a number a coach reads off a history: the felt heat above 12 C and
    its interaction with log distance, the best ever and the best at this distance, the gap
    from the last result to the best, the spread of a runner's results, distinct courses, the
    change between the last twelve months and the twelve before, races a year, and a
    recency-weighted form average.

    What the refusals say. **Normalising form by the course and the edition, which is what the
    hierarchical model does internally, made the trees worse**, and worse again when it replaced
    the raw form: the adjustment is itself estimated, and it takes a real part of the signal
    (a runner's choice of race) out with the noise. **Starting the trees from the last result**
    (LightGBM `init_score`) is the standard trick for a target this close to one feature, and
    it lost 0.07: the residual after the last result is less predictable than the whole. And
    **the huber loss buys accuracy for first-timers and loses it for everyone with a history**,
    so it was refused: seven pinball quantiles from one objective are a coherent set of
    intervals, and a centre fitted under a different loss would not be the same prediction the
    intervals belong to. The kept gain is about one percent, and the challenger's lead over the
    hierarchical model in item 33 is therefore not a tuning artefact: it was there before any
    tuning, and tuning moved it by a tenth of what it is.

    **Rerun on the backtest, once, with what the search chose** (2026-09-19, same 53 races):
    18.6 minutes at no prior results, 8.8 at one, 7.7 at two or three, 5.2 at four or more,
    against 18.9, 8.8, 7.9 and 5.3 before, and 30% skill against carry-forward at four or more
    where the first configuration had 28%. Paired against the hierarchical model, in points of
    a finish time: one prior result -0.91 (-1.65 to -0.57), two or three -1.00 (-1.39 to
    -0.79), four or more -0.39 (-0.59 to -0.21), first-timers +0.67 (-0.85 to +1.60). Placing
    4.2 places closer than carry-forward on the same runners, against the hierarchical model's
    1.8. The tuning window said about one percent and the test set agrees, which is the point
    of having kept them apart.

35. **Neither model publishes: the average of the two does, and the weight was chosen where
    the backtest could not see it.** Item 33 left a question open. The challenger is more
    accurate than the hierarchical model for every runner with a history, but the hierarchical
    model is what a published prediction is made of: a set of joint draws of a whole field on
    one shared morning, which is what a place in a field of several hundred needs and what
    seven quantiles per runner cannot supply. A first look at averaging the two medians was
    better than either at four or more prior results and was written up as not yet a number.
    This is that number.

    **What is published** (`models/blend.py`). The average is on the log scale, the scale
    everything here is measured on, log(published) = 0.35 log(hierarchical) + 0.65 log(trees).
    The distribution is the hierarchical model's, moved: each runner's draws are multiplied by
    the single factor that puts their median on the averaged centre, so their 80% and 90%
    ranges and their simulated place move with their time, and the shared morning that makes
    the places a field rather than a list is untouched. The conformal layer then calibrates on
    the average's own backtest errors, which is what keeps the published coverage honest. A
    newcomer drawn from a course's first-timer pool (`placing/unseen.py`, the biggest races
    only) is left out of the average: that pool is a measurement of how first-timers actually
    finished there, and the trees have nothing to add to it.

    **Where the weight came from** (`experiments/blend_weight.py`). Both models were run over 2022
    and 2023 with the same quarterly block scheme as the backtest, the same window the
    challenger's features and parameters were tuned on in item 34, for the reason given there:
    a weight read off the 2024+ races would make those races report a number about themselves.
    On that window, 34 races and 7,602 runners both models answered for, the best weight was
    0.65 at 9.540 points of a finish time, against 9.996 for the hierarchical model alone and
    9.681 for the trees alone. The curve is flat: 9.545 at 0.60, 9.540 at 0.65 and 0.70, 9.548
    at 0.75. Resampling races 2,000 times and re-reading the weight on each draw puts it
    between 0.50 and 0.80 with a median of 0.70, and no draw below 0.40. So what the window
    establishes is the direction, lean about two thirds on the trees, rather than the second
    decimal, and 0.65 is what the code uses.

    **What it buys on the test set** (2026-09-20, the same 53 races from 2024, paired on
    runners with races resampled). Against the hierarchical model, in points of a finish time:
    one prior result -0.91 (-1.44 to -0.68), two or three -0.92 (-1.19 to -0.77), four or more
    -0.51 (-0.63 to -0.40), first-timers +0.07 (-1.05 to +0.65), level. Against the challenger:
    first-timers -0.59 (-0.96 to -0.13), four or more -0.12 (-0.22 to -0.03), one prior result
    -0.00 (-0.12 to +0.23), level, two or three +0.08 (+0.02 to +0.20), a shade behind. Over
    every depth at once, -0.455 (-0.847 to -0.255) against the hierarchical model and -0.217
    (-0.327 to -0.040) against the challenger. In minutes: 18.1 at no prior results, 8.7 at
    one, 7.7 at two or three, 5.0 at four or more, and 32% skill against carry-forward at four
    or more where the hierarchical model had 27% and the challenger 30%. The window predicted
    a gain of 0.46 points against the hierarchical model and 0.14 against the trees; the test
    set returned 0.46 and 0.22. Placing: 48.7 mean absolute place error over the whole field
    against the hierarchical model's 50.9, and on the same runners 4.1 places closer than
    carry-forward, with the rank correlation 0.876 against carry-forward's 0.849.

    **A side benefit that was not the aim.** The average's own uncalibrated ranges hold better
    than either parent's at the 80% level: 80% at four or more prior results against the
    hierarchical model's 77% and the trees' 70%, and 74% at two or three against 71% and 68%.
    Averaging two centres and keeping one model's spread makes the spread slightly too wide for
    the sharper centre, which is the right direction to err in. After calibration all three sit
    between 74 and 80%, so this changes the published intervals very little; it is recorded because
    the opposite would have been a reason not to ship the average.

    **What is honest about the size of this.** The gain is a few tenths of a percent of a
    finish time, which is seconds, not minutes, and against the challenger alone it is small
    enough to be behind at one depth. Averaging models that make different mistakes is the
    oldest trick in forecasting and it worked here about as well as it usually does. It ships
    because it is measured on races that never chose it, at both ends, and the alternative was
    publishing a model that a simpler method already beat.

    **Decided here.** All predictions are the average from now on, including the Turkey Tea
    10 km dress rehearsal on 2026-10-04 and Cape to Cabot on 2026-10-18, and the prediction
    file's `model` block records the weight, the formula and how many runners the challenger
    answered for, so a reader can tell which of the two moved their time. A run with no saved
    challenger backtest matching the code refuses to freeze rather than quietly publishing the
    hierarchical model with intervals calibrated on something else.

36. **A course factor is only comparable inside its own race length, and the chart was
    inviting the other comparison.** Peter, 2026-09-20, on the website's course chart: the
    Tely 10 is one of the fastest 10 mile courses anywhere, net downhill with the prevailing
    westerly behind the field, and the chart had it at +0.2 percent, an ordinary road. His
    guess was the field: a big recreational race dragging the average down. That is not the
    mechanism, because the fit removes each runner's own level and trend, so who turns up
    cannot move a course effect. The second half of his message named the real one: "for an
    individual measure for 10 mile from VDOT the race would exceed their typical
    predictions". The outcome is a finish over Daniels' time for VDOT 50 **at that
    distance**, and a runner carries one level for a whole career, so a population that
    fades over distance differently from Daniels' curve has nowhere to put that difference
    except the effects of the long courses. `models/courses.py` said this was unidentifiable
    and section 5.4 of the page said it too. What neither said is that a chart which then
    ranks all fifty courses on one axis is asking the reader to make exactly the comparison
    the number cannot support.

    **How large it is.** Unweighted mean factor by race length: 5 km -1.3, 8 km -2.7, 10 km
    -0.9, 11 km +1.6, 15 km +1.2, 10 mile +2.4, half marathon +1.2, marathon +8.5 percent.
    Across the fifty courses the factor correlates 0.68 with log distance, about +3.8 points
    per e-fold, or +8 points from 5 km to the marathon. The marathons are the tell: all five
    read between +4.5 and +11.2 percent, which would make every marathon in the province
    about as hard as Signal Hill, and measured against each other they spread from -4.6 to
    +3.1 and mostly straddle zero, which is what five ordinary road marathons should do.

    **The mechanism, caught in the act.** Refitting on runners split by what else they race:
    the Tely reads -0.37 percent from runners who also race a half marathon or longer and
    +0.90 percent from runners who never go beyond 15 km, a gap of 1.3 points in the
    predicted direction, while the Bell Island Blast, a genuinely hilly 10 mile course, is
    +4.55 and +4.71 in the two subgroups, unmoved. A road is a road to everybody; a distance
    is not.

    **What is published now.** `CourseFactor` carries `versus_peers`, the same course against
    the other measured courses of the same length, with its interval taken inside the same
    bootstrap draws rather than differenced off two published intervals, which would report
    an uncertainty neither number has. The Tely is **-4.1 percent [-5.0, -3.4] against the
    only other 10 mile course on the archive**, which is Peter's point measured: a fast road,
    and clear of zero. Turkey Tea is -4.5 [-5.0, -3.9] against the other fourteen 10 km
    courses. The chart is now a column per race length with the typical course of that length
    drawn in it, the hover gives both figures, the README table has both, and `finishline
    courses` prints in blocks by length with "compare inside a block" over it. Where a length
    has one measured course (Cape to Cabot at 20 km, Run to Remember at 11 km, the ANE mile)
    `versus_peers` is None and the page says there is nothing to compare it with, rather than
    printing a zero.

    **What this costs item 13's claim, honestly.** Cape to Cabot's +9.2 percent has no peer
    at 20 km, so it still carries whatever the reference does at that distance. Courses of
    nearby length read about a point above flat, which puts the road's share near +8 and the
    grade that explains it near 8.3 percent rather than 10.3. The race's course page says
    "grades of more than 10 per cent in some parts", which is not an average anyway, so the
    two routes still agree, but the agreement is a ballpark and the README, the plan and the
    page now say so instead of matching to a decimal.

    **No prediction moves.** A course factor is only ever applied to that course, at its own
    distance, where the race length belongs in the answer: the entanglement is a problem for
    reading a chart, not for making a prediction. Nothing in the hierarchical model, the
    challenger or the blend changed, and no saved hierarchical run went stale. The challenger's
    cache key hashes `models/courses.py`, so its rows were refitted and came back identical.
    A synthetic test (two 10 km courses, one ten percent harder, and two flat marathons with a
    five percent population fade planted at the distance) asserts what the fit must do: the
    flat marathon reads harder than the flat 10 km against the reference, level against the
    other marathon, and the planted ten percent survives in the peer comparison.

37. **The rule that reads the results index deleted the year's biggest multi-distance race
    from the calendar (2026-09-20).** The calendar (section 5.8) is the first source here
    that mixes sports on one page, and the first two attempts at telling road racing out of
    it both failed on real rows.

    **Reusing `nlaa.NOT_ROAD` unchanged dropped the USR.** On the results index a row that
    says "relay" is the relay, and refusing it is right. The association's calendar has one
    row per *day*: "Uniformed Services Run Marathon/Half-Marathon/Marathon Relay/5km/10km" is
    a marathon, a half, a 10 km, a 5 km and a relay in one line, and the same pattern deleted
    all five. The fix is not a longer pattern but a distinction the index never needed:
    **a word that means a different sport** (cross-country, trail, a schools meet) disqualifies
    an entry, and **a word that names one component of a day** (relay, walk, kids, teams,
    awards) does not. `ingest/calendar.py` imports `NOT_ROAD` and does not call it, so a
    rename there fails here rather than quietly changing what is read.

    **Matching the course aliases first filed three track meets as road races.** "Pearlgate
    Twilight Meet 1", "Pearlgate Tetrathlons" and "Pearlgate Memorial Meet" all match the
    `pearlgate` alias, because the venue is also a road-race course; "NLAA Provincial
    Cross-country Championships" matches `provincial` the same way. Positive identification
    by alias is still the test that a road race has to pass, but the track-and-field
    exclusion has to run before it, and cross-country before that. Order is the whole design
    and the tests pin it row by row.

    **What the page settles for rather than guesses.** Of 40 rows, 15 are road races and 25
    are not. Exactly one, "NLAA Junior and Senior HS Championships (3 sessions)", matches no
    rule and no alias; it is reported as unrecognised and sorted to the top of the skip list,
    because a new road race whose name has no alias yet looks exactly like that and is the
    only skip here that is ever a bug. Nothing is filed under a derived slug, which is the
    same refusal the parser makes about a results page with no column headers.

38. **A table that renumbered a race printed the man who finished second as its winner
    (2026-09-20).** The USR retrospective (section 5.9) shows every finisher, but only 161 of
    the 171 have a prediction: the other ten are runners the resolver refused, because the
    archive holds more than one person their result could belong to. The first version of the
    table dropped those ten and ranked what was left among itself.

    **What that printed.** Adam Guy won the 10 km in 36:17 and is one of the ten. So Brian
    Caines, who finished second, appeared as "actual place 1", beside a column saying he
    finished second, beside "nought places out". Peter read it as an index off by one. It was
    not off by one; it was a second race, invented by deletion, printed next to the real one.

    **The first fix made it worse.** Adding the restricted actual place as a column of its
    own, so the arithmetic was visible, plus a note explaining the two populations. The
    numbers were then internally consistent and the table still asserted, in print, that a man
    who finished second finished first. Peter, on being shown it: "you are changing reality,
    everyone sees you're lying and your credibility is ruined." He was right, and the general
    rule is worth more than this table: **a published number about a real event may be
    incomplete, and may not be restated.** A footnote does not buy the right to renumber a
    race.

    **What is published now.** Every finisher, in finishing order, at the place the results
    page printed. A finisher with no prediction keeps their row, their place and their time,
    and carries the resolver's own words where the prediction would be ("2 runners of this
    name could be this result, and the page printed no age band to tell them apart"; for two
    of them, "results under this name disagree about sex"). To make a predicted place
    comparable with a real one, the ten are held at the place they actually finished and the
    161 are ordered around them: the model is not asked to place runners it could not
    identify, and is not charged for them. Caines now reads: finished 2, predicted to finish
    2, nought places out.

    **The third version separates showing from scoring, and costs nothing.** The second put
    the predicted order back onto real places by holding the ten where they finished, which
    made the two place columns comparable and quietly charged the model for the gaps: the real
    places of the predicted runners have holes in them where the others finished, so the same
    ordering scores worse the more people the resolver had to refuse. Peter: "it's not the
    model's fault that some people couldn't be identified... can we display them along the
    predictions without any metrics being affected?" Yes, and the way to is to stop asking one
    column to do two jobs. The table prints the real place and no absolute predicted place at
    all; beside it is "places out", the model's ordering error over the field it was actually
    given, the predicted runners ranked among themselves by prediction against the same
    runners ranked among themselves by result. Nothing about the ten reaches it.

    **What each version measured**, on the same predictions, which is the reason to write this
    down: 19.4 places mean and 14 median over the predicted field, against 20.4 and 15 when
    the ranks were mapped back onto real places. The band table the same way: 12.3, 24.2, 16.7
    places from the front quarter to the last, against 12.5, 25.4, 18.3. The published numbers
    are the first pair. No time prediction moved at any point: the MAE, the paired comparison
    and the coverage were always over the same 161 runners.

    **The rule that falls out of it.** A number about a real event may be incomplete and may
    not be restated; and the fix for an incomplete number is a row that says why it is
    missing, not a rescaling of the rows around it.

39. **The grade check crashed on a quarter of the courses it could be given, and a loop's
    bearing was measured rather than assumed (2026-09-21).** Adding Flat Out 5 km to
    `data/courses.toml` (39 m up, 52 m down, read by eye off a profile image Peter supplied;
    the race's own page prints no figure) turned up two things.

    **`implied_grade` raised on inputs it should answer.** It evaluates the penalty exactly
    at the gentlest feasible grade, where the flat is zero by construction, and the division
    lands a few ulps either side of zero. `penalty` read the negative side as "more graded
    road than the course" and raised. Over climbs of 10 to 120 m, drops of 10 to 130 m and
    five race lengths, 5,615 of 22,000 combinations crashed, among them 35 m and 47 m over
    4,950 m, a reading of this very profile. Cape to Cabot and Turkey Tea happened to miss
    it, so `finishline courses` and `finishline report` would have fallen over on the next
    course added with about one chance in four. Fixed by treating a shortfall under a
    millionth of the distance as rounding; the genuinely infeasible case still raises, and a
    test sweeps the grid.

    **The hills and the results agree, narrowly, and the read decides which side of the
    line.** Measured -0.93% [-1.27, -0.60] from 2,753 finishes. Through Minetti, 39 m and
    52 m give -0.98% at the gentlest grade and need a 2.0% average grade for the point
    estimate; 38 m and 50 m put the floor at -0.90%, just past it. Nothing rides on it: a
    course with fifteen editions is measured far better than any profile, and no prediction
    moves. Turkey Tea, for contrast, is a real disagreement: its segment figures bottom out
    at -4.3% against a measured -5.1% [-5.4, -4.9].

    **No bearing, with the number that says why.** The race's page calls it "almost two
    complete loops"; nine waypoints along it put start and finish 363 m apart, and the eight
    legs' headings sum to those same 363 m out of 4,604 m, so 7.9% of the route has a net
    direction. A bearing on that would charge the whole field for a wind that is behind them
    for a few hundred metres. The waypoints are in `courses.toml` and a test recomputes the
    figure. No elevation was taken from Google Maps, where the waypoints were placed: its
    terms bar extracting content and its elevation service may not be stored or shown away
    from its own map (docs/data-terms.md, which also gains the Turkey Tea row it was missing).

40. **Run to Remember's course factor is not its hills (2026-09-21).** The organisers' page
    (Stride Running NL) gives 56 m of gain and 56 m of loss on an 11 km out-and-back along
    the T'Railway, a gravel rail trail, with the profile one steady grade of about 1% from
    about 165 m down to 114 m at the turnaround. **Superseded in part on 2026-09-25 by item
    43's profile, which measures 91 m each way off Strava's segment stream and puts the solved
    grade at 7.7% rather than 12.7%; the conclusion below is unchanged and the arithmetic in it
    is the 56 m reading.** Through Minetti that is worth +0.13% at the
    grade the profile shows and +0.39% at 3%, steeper than a rail bed is built. The course
    measures +1.64% [+1.17, +2.10] from 1,042 finishes; `implied_grade` solves it at 12.7%,
    which is arithmetic and not a trail, and a test now asserts exactly that so nobody reads
    the number as a finding about the grade.

    Where the other point and a half most likely comes from: the surface, which nothing in
    this project models, and the race length, since this is the only 11 km course and has no
    peers to cancel the population's fade against Daniels' reference (item 36), which is
    about a point at Cape to Cabot. They cannot be separated with one course. **No prediction
    moves**: the factor used is the measured one, and an out-and-back gets no bearing.

    The same page says the start and turnaround were switched for 2025. On an out-and-back
    that turns downhill-then-uphill into the reverse with the same climb, drop and physics,
    so the 2025 edition stays pooled with the ten before it. If the 2026 freeze wants a
    check on that, the 2025 edition effect against the earlier ones is where to look.

41. **A course bearing describes only part of a course, and now says how much (2026-09-21).**
    Checking Cape to Cabot against the race's own 2006 chart and a course map: the published
    550 m up and 450 m down stand, and two coarser readings (the chart's labelled heights,
    about 496 m and 415 m; a profile trace of the certified course, about 495 m and 395 m)
    undercount them the way coarse sampling does, as the watch's 519 m does. Each still needs
    a road's grade for the measured +9.2%, 11.7 to 12.3% against 10.3%; the final 150 m from
    the bottom of Temperance Street to Cabot Tower in under 2 km is where the race's "more
    than 10 per cent" lives.

    **The new number is the share of the course its bearing covers.** The legs of any route
    sum to the displacement from start to finish, so displacement over distance is exactly
    the share with a net direction: 7.4 km of 20 km, 37%, for Cape to Cabot; 7.9% for Flat
    Out (item 39). The tailwind term projects the whole wind onto the bearing as though the
    field ran that way throughout, so it charges a course that winds (Cape to Cabot) the same
    as one that mostly runs straight. Scaling the tailwind by the share is the obvious fix and
    is **not made**: `models/weather.py` is in the hierarchical backtest's cache key, the
    freeze is on 2026-10-17, and the tailwind coefficient does not yet clear zero, so the
    change waits for a backtest that runs anyway and is measured then (docs/todo.md).
    `courses.toml` now stores Cape to Cabot's start and finish, and a test recomputes the
    bearing from them and the 37%.

42. **The field forecast names about three runners in ten correctly, and the rule it names them
    by is a count, not a threshold (2026-09-21).** Section 5.6's participation model is built
    (`models/participation.py`, `finishline participation`, `data/participation.json`), for
    Run to Remember, which publishes no start list. Every resolved runner with a finish in the
    eighteen months before the race is a candidate; a ridge logistic regression on fourteen
    features computed from results before the race's own day gives each a probability of
    finishing it. Two departures from the paragraph in 5.6, both measured:

    - **The series standings are not read.** They are points in the association's series
      races, and those races' results are already in the archive, so "this year's
      participation" is computed from them directly (`this_year`, `recent_60d`,
      `recent_183d`). Fetching and parsing a second page type for a number the archive
      already holds bought nothing. What the plan did not have, and turned out to matter
      more, is **`crowd`**: of the runner's recent races, how much of the field also ran this
      course last time. A small club race shares its crowd with another; the Tely shares
      little. Adding it raised the race-mean recall on 2022-2023 from 28.9% to 31.8% at the
      same precision.
    - **The field is named by count, not by a probability threshold.** A single threshold
      balanced the pooled numbers and named nobody at all at ten of the thirty-four tuning
      races, because a small race's candidates all sit below it; at the 2025 Run to Remember
      it named 13 of an expected 104. The rule shipped names the most likely runners, as many
      as the model expects to finish times a scale, and the scale is where recall and
      precision are level on 2022 and 2023: **0.9**. Numbers are means over races, not
      pooled over runners, because pooled, the Tely is half of every figure.

    **Measured on the 53 races from 2024** (a model fitted before each race's year, races
    resampled for the intervals): **recall 27.7% (23.9 to 31.6)** of the finishers who had a
    recent result were named, **precision 30.2% (24.8 to 35.3)** of the runners named
    finished, and **61.5% (56.4 to 66.3)** of all finishers had a recent result at all, which
    is the ceiling any list-free forecast works under. On Run to Remember's own three scored
    editions: recall 25.4%, precision 23.8% (16.9 to 34.0), and 86% of its finishers visible,
    because it is a race of regulars; that is also why a count of 104 to 145 named is the
    right size and why most of them will still be the wrong 104 to 145. The archive has no
    2024 edition of it, so "ran last time" reaches back two years for 2025 and for 2026.

    **What the file does with it.** The named runners are predicted exactly as listed
    entrants are. Their places come from a simulation that also draws who turns up: every
    candidate runs with their own probability, and a Poisson number of runners the archive
    cannot see (the expected count scaled by the course's visible share) run with times from
    the course's first-timer pool (`simulate.forecast_places`). A place is where the runner
    finishes if they run. The file's `field_forecast` block carries the backtest's recall and
    precision with their intervals, so a reader knows before the gun that about seven in ten
    of the names will not be there; `finishline score` sets the promised precision beside the
    measured one. `freeze` refuses a daily file for such a race and refuses without a
    `data/participation.json` whose key matches the archive and the code.

    **Whether to publish names that are mostly wrong is a real question** and is left open in
    docs/todo.md: a list of 120 people of whom about 30 will run is what the plan asked for
    and what the numbers support, but it is not the only defensible choice.

43. **The elevation cross-check was built to check the course factors, and what it did instead
    was say which of the two factors to read (2026-09-25).** Peter supplied elevation profiles
    for eleven courses, built by project 11 (Overload): eight from his own recordings of each
    route, being Five and Dime 5 km and 10 km, Mundy Pond, Flat Out, Mews Memorial, the Tely,
    Cape to Cabot and the Huffin Puffin marathon, which is also every pre-2026 USR and Capital
    Subaru marathon (`nlaa.SAME_ROUTE`), and three, Turkey Tea, Run to Remember and Harbour
    Front, drawn from Strava's own segment streams, which carry no clock, no heart rate and no
    splits at all. That is every course in `data/courses.toml`. **Seven of the eleven had no
    elevation figure of any kind**, the Tely among them, and one, Run to Remember, had a figure
    the profile contradicts: 56 m each way off the organisers' chart against 91 m off the
    stream, which is the difference between a range and a cumulative climb. Each
    chart prints the climb and descent of a distance-sampled, smoothed series and, for the
    first time here, **the grade**: the steepest and the fastest window on the course. Only the
    road is taken from them; the pace, the moving time and the one heart rate are not in this
    repository and the images are not committed (docs/data-terms.md).

    **The result.** Item 36 split every course factor in two: against Daniels' flat reference
    at the course's own distance, which carries this population's departure from Daniels' fade,
    and against the courses of the same race length, which does not. Eleven courses now have an
    elevation figure, and nine of those have a peer of their own length. The Minetti penalty
    the profile implies lands inside the own-length interval and outside the flat one on five
    of the nine; inside both on two, whose intervals are too wide to separate them; and outside
    both on two, Mundy Pond and Harbour Front, by a tenth of a point and by nine tenths against
    their own length, and by two and a half points against the flat reference. **Not one of the
    nine picks the flat reference**, and no course lands inside the flat interval and outside
    the own-length one, which is the comparison that would have refuted this.

    **The two misses are the same shape and are reported rather than averaged away.** Mundy
    Pond and Harbour Front are the two rolling courses here with essentially no net drop, +3 m
    over 5 km and +7 m over 10 km. On both, the grade model charges for the undulation, +0.6%
    and +0.7%, and the results decline to pay it. Every course with a real net descent or climb
    lands where the own-length factor says. Whether that is the constant-power model
    overstating what rolling ground costs, or something about these two roads, two cases cannot
    say; it is the obvious thing to test if a third rolling course ever gets a profile.

    | Course | Race length | Profile | The hills, through Minetti | Against the flat reference | Against its own length |
    |---|---|---|---|---:|---:|
    | Five and Dime 5 km | 5 km | 20 up, 42 down | -2.18 to -1.93% | -2.99% [-3.59, -2.37] | -1.78% [-2.82, -0.76] |
    | Mundy Pond 5 km | 5 km | 36 up, 33 down | +0.57 to +0.61% | -1.80% [-2.11, -1.53] | -0.47% [-1.36, +0.45] |
    | Flat Out 5 km | 5 km | 38 up, 49 down | -0.80 to -0.41% | -0.93% [-1.27, -0.60] | +0.48% [-0.50, +1.33] |
    | Mews Memorial 8 km | 8 km | 26 up, 100 down | -4.69 to -4.41% | -5.32% [-5.52, -5.12] | -5.19% [-5.83, -4.60] |
    | Five and Dime 10 km | 10 km | 63 up, 84 down | -0.86 to -0.55% | -0.83% [-1.96, -0.07] | +0.12% [-1.09, +1.03] |
    | Harbour Front 10 km | 10 km | 72 up, 64 down | +0.67 to +0.83% | -1.77% [-2.09, -1.41] | -0.88% [-1.44, -0.26] |
    | Turkey Tea 10 km | 10 km | 39 up, 123 down | -4.21 to -3.96% | -5.12% [-5.40, -4.88] | -4.51% [-5.01, -3.93] |
    | Run to Remember 11 km | 11 km | 91 up, 91 down | +0.35 to +0.51% | +1.64% [+1.17, +2.10] | no course of this length |
    | Tely 10 | 10 mile | 93 up, 217 down | -3.69 to -3.02% | +0.24% [+0.11, +0.37] | -4.14% [-4.98, -3.42] |
    | Cape to Cabot 20 km | 20 km | 508 up, 400 down | +5.56 to +7.93% | +9.24% [+8.99, +9.48] | no course of this length |
    | Huffin Puffin marathon | marathon | 273 up, 270 down | +0.25 to +0.29% | +9.62% [+8.31, +10.78] | +1.33% [-0.45, +3.08] |

    The band is the penalty from the gentlest grade the totals allow to the steepest grade the
    chart labels, which is an upper bound on the typical graded-section grade. A test asserts
    the whole table.

    **The gap changes sign at about 10 km, which is what item 36 predicted and could not
    measure.** Flat reference minus hills: -0.9, -2.4, -0.3 at 5 km, -0.8 at 8 km, -0.1 and
    -0.9 at 10 km, then +1.5 at 11 km, +3.6 at 16.1 km, +2.5 at 20 km and +9.4 at the
    marathon. Short courses measure faster than their hills can account for and long ones
    slower, because the reference is a VDOT-50 time at the course's own distance and this
    population fades more over distance than Daniels' curve does. It is not a straight line in
    distance, and the 20 km reading is under the 16 km one.

    **Two courses moved from "the hills agree" to "the hills agree with one of the two
    numbers".** The Tely is the widest gap in the archive, on its best-measured course: 25,664
    finishes read +0.24% against the flat reference and -4.14% against the only other 10 mile
    course, and a course that drops 124 m does not cost a runner time. Cape to Cabot's check
    is now weaker than the published totals made it look: 508 m up and 400 m down need an
    11.1% average over the graded sections to give the measured +9.24%, and no 1.3 km of the
    race is steeper than +8.7%. The race's "grades of more than 10 per cent in some parts"
    survives, because a 1.3 km window is a smoothing; the claim that the physics and the
    results land on the same number does not.

    **No prediction moves and no cache goes stale.** `climb_m` and `drop_m` feed the grade
    cross-check, `finishline courses`, the README column and the website's course cards, and
    nothing else; the model uses the factor measured from results. `courses.toml` is not in the
    backtest cache key, and no bearing was added, which is the field that would have changed a
    model input without changing that key. That hazard is written down in docs/todo.md item 2.

    **What the profiles also settled, for free.** Mews Memorial finishes 74 m below where it
    starts and the Five and Dime 5 km and 10 km 22 and 21 m below theirs, so all three are
    point to point and want bearings; Mundy Pond returns to within 4 m of its starting height
    over 5 km and the marathon to within 3 m over 42 km, so neither does. None of the images
    carries a position, so no bearing could be computed from them.
