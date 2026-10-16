# Architecture

How the project is put together, in three pictures: the whole system, one live race from the
entrant list to a scored prediction, and the model itself. For the long version, read
[methods.md](methods.md). For the design history, read [PLAN.md](../PLAN.md). The same three
pictures are on the live site at
[finishline.peterparker.ca/architecture.html](https://finishline.peterparker.ca/architecture.html).

## The system

![Public results pages are crawled once and resolved into runner histories that can only be read before a date; a hierarchical model and a boosted challenger are blended, conformalised by history depth and simulated as a field; from a week out each race's predictions are frozen, tagged and hashed, then scored against the official results on a public site.](architecture/system.svg)

The diagram reads left to right: reading the results, modelling them, and publishing.

The results come from public pages run by the provincial athletics association and Athletics
NorthEast. They were read once, one request a second, after the clubs had been told, and kept.
Working out who is who is the hard part, because results carry only a name. The one free
clue is that nobody gets younger, so a printed age band on a dated race is the only thing
allowed to split one name into two runners. A runner's history can only be read as it stood
before a given date, which makes it impossible for a model to see the future by accident. The
entrant lists for upcoming races are saved each morning.

The model puts every finish on one scale, comparing each time with a reference for its
distance. A hierarchical model gives each runner a fitness and each race its course, year and
weather effects. A second model, gradient-boosted trees, is blended in. The range around each
prediction is calibrated by how much history the runner has, and the whole field is simulated
together to turn times into places.

Publishing has three parts. A backtest replays past years, carries the test that no future data
leaks in, and writes the README's tables. Before each race, its predictions are committed,
tagged and fingerprinted, so they cannot be changed after the gun. After the race, they are
read back from that tag and scored against the official results, and this site is built from
the same files.

Where it lives: `finishline.ingest`, `finishline.identity`, `finishline.history`,
`finishline.metrics.daniels`, `finishline.models`, `finishline.conformal`, `finishline.placing`,
`finishline.backtest`, `finishline.report`, `finishline.publish` and `web/`.

## One live race

![From a week out a scheduled task on the laptop snapshots the entrant list each morning, predicts the new entrants, and the day before predicts the whole field with the latest forecast and its places; every file is committed, tagged and hashed before the gun and freeze refuses inside 24 hours of it; after the results post, score reads each prediction back from its tag and writes the record.](architecture/live-race.svg)

This is what happens for each race, from a week before it to after the results are posted.

Every morning from seven days out, a scheduled task on a laptop saves the entrant list and
publishes predictions for anyone who has entered since the last file. The day before the race,
it publishes the final file: the whole field, the latest weather forecast for race morning, and
everyone's likely place.

Each file is committed, tagged, fingerprinted and pushed. The publishing step refuses to run
inside 24 hours of the start, and refuses to run with any uncommitted code, so what was
published is exactly what the code produced.

When the official results are posted, each prediction is read back from its tag and scored, and
the live record and the race's page are written. Nothing in a prediction file is ever edited
after it is tagged, not even to fix a mistake found later; the mistake is written up instead.
The site rebuilds itself whenever anything is pushed.

Where it lives: `scripts/daily-predictions.ps1`, `finishline.publish.daily`,
`finishline.publish.freeze`, `finishline.ingest.resultsfile`, `finishline.backtest.score`,
`predictions/` and `scores/`.

## The model

![Every finish is put on one scale; a hierarchical model gives each runner a fitness, a distance fade and a form that walks year to year, shrunk towards their age and sex group, and each race its measured course difficulty, calendar year and that morning's heat and wind; a boosted challenger is blended in, the range is conformalised by history depth, and places come from drawing the whole field together.](architecture/model.svg)

Every finish is turned into one number: how its time compares with a standard reference time
for that distance. That puts a 5 km and a marathon on the same scale before anything is fitted.

The main model gives every runner three things: a fitness level, how much they slow down over
longer distances, and a form that drifts from one racing year to the next. Each is pulled
towards the typical values for the runner's age and sex, so a runner with only a few races
borrows strength from everyone like them. Every race gets its course's difficulty, measured
from runners who have raced on more than one course, a shared effect for its year, and the heat
and wind recorded at the airport that morning.

That model is blended with a gradient-boosted model, weighted 0.65 towards the boosted one, a
weight chosen on 2022 and 2023 alone. The range around each prediction comes from how wrong
past predictions were, grouped by how many results a runner has, so a first-timer is not given
a veteran's confidence. Entrants with no results at all are predicted from how that course's
past first-timers finished. Finally, the whole field is drawn together on one shared race
morning, so the places add up to a real race. Each runner gets a time, 80% and 90% ranges, and
a likely place.

Where it lives: `finishline.models.hierarchical`, `finishline.models.courses`,
`finishline.models.weather`, `finishline.models.gbm`, `finishline.models.blend`,
`finishline.conformal`, `finishline.placing.unseen` and `finishline.placing.simulate`.
