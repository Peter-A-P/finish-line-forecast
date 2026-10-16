# Architecture

Three figures: the system as a whole, one live race from the entrant list to a scored
prediction, and the model itself. Each names the module that implements what it shows;
[methods.md](methods.md) gives the long version and [PLAN.md](../PLAN.md) the design history.

## The system

![Public results pages are crawled once and resolved into runner histories that can only be read before a date; a hierarchical model and a boosted challenger are blended, conformalised by history depth and simulated as a field; from a week out each race's predictions are frozen, tagged and hashed, then scored against the official results on a public site.](architecture/system.svg)

The left column reads. Public results pages from the NLAA and Athletics NorthEast are crawled
once, one request a second, after the courtesy notices have gone out, and cached
(`finishline.ingest`). The resolver (`finishline.identity`) works from the name and the one
free piece of evidence, that a runner cannot get younger, so printed age bands on dated races
are the only thing allowed to split a name into two runners. `History.before(date)`
(`finishline.history`) is the only way to build a history and keeps nothing dated on or after
that day, which is what turns leakage into something a model cannot reach. Entrant lists are
snapshotted from Race Roster each morning (`finishline.ingest.raceroster`). The middle column
models: every finish goes on one scale, the log of its time over a Daniels reference for the
distance (`finishline.metrics.daniels`); the hierarchical model in PyMC
(`finishline.models.hierarchical`) takes the runner effects and the course, year and weather
effects (`finishline.models.courses`, `finishline.ingest.eccc`, `finishline.ingest.openmeteo`);
a LightGBM quantile challenger is blended in at 0.65 towards the trees
(`finishline.models.gbm`, `finishline.models.blend`); the range is conformalised by history
depth (`finishline.conformal`); and the field is simulated together for places
(`finishline.placing`). The right column publishes: the rolling-origin backtest
(`finishline.backtest`) carries the leakage test and writes the README tables through
`finishline.report`; `freeze` commits, tags and hashes each race's predictions before the gun
(`finishline.publish.freeze`, `predictions/`); `score` reads them back from the tag against the
official results (`finishline.backtest.score`, `scores/`); and the site at
finishline.peterparker.ca is built from the same files (`finishline.publish.site`, `web/`).

## One live race

![From a week out a scheduled task on the laptop snapshots the entrant list each morning, predicts the new entrants, and the day before predicts the whole field with the latest forecast and its places; every file is committed, tagged and hashed before the gun and freeze refuses inside 24 hours of it; after the results post, score reads each prediction back from its tag and writes the record.](architecture/live-race.svg)

A Windows scheduled task on the laptop, "FinishLine daily predictions"
(`scripts/daily-predictions.ps1`), runs each morning from seven days before a race. It
snapshots the entrant list and publishes a daily file for the entrants no earlier file
predicted (`finishline.publish.daily`); the day before the race it publishes the final file
with the whole field, the latest Open-Meteo forecast for the morning and the simulated places
(`finishline.publish.freeze`). Each file and its race page are committed, tagged, hashed and
pushed; `freeze` refuses inside 24 hours of the gun and refuses to run with uncommitted code,
and the task commits nothing else. After the official results are posted
(`finishline.ingest.resultsfile`), `finishline score` reads each prediction back from its tag
and writes the live record and the race page (`README`, `docs/predictions/`); nothing in a
prediction file is edited after it is tagged, including a defect found later, which is written
up instead. The Website workflow rebuilds finishline.peterparker.ca on push.

## The model

![Every finish is put on one scale; a hierarchical model gives each runner a fitness, a distance fade and a form that walks year to year, shrunk towards their age and sex group, and each race its measured course difficulty, calendar year and that morning's heat and wind; a boosted challenger is blended in, the range is conformalised by history depth, and places come from drawing the whole field together.](architecture/model.svg)

Every finish is the log of its time over a Daniels reference time for the distance, so a 5 km
and a marathon are comparable before anything is fitted. The hierarchical model gives every
runner a fitness level and a distance fade shrunk towards their age and sex group, and a form
that walks from one racing year to the next; every race gets its course's difficulty measured
from runners crossing between courses (`finishline.models.courses`), a shared effect for its
calendar year, and the heat and wind observed at the airport that morning
(`finishline.models.weather`). The posterior from PyMC (`finishline.models.hierarchical`) is
blended on the log scale with a LightGBM quantile challenger on hand-built features
(`finishline.models.gbm`, `finishline.models.blend`) at 0.65 towards the trees, a weight read
off 2022 and 2023 alone. The range comes from rolling-origin residuals stratified by how many
results a runner has (`finishline.conformal`), so a first-timer's range is not borrowed from a
veteran's; entrants with no results here are drawn from how that course's past first-timers
finished (`finishline.placing.unseen`); and places come from drawing the whole field together
on one shared morning (`finishline.placing.simulate`), so the places add up to a race. Each
runner gets a time, 80% and 90% ranges and a likely place.
