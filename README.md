# Finish Line Forecast

Before the gun, a predicted finish time and placing for every registered runner in a
field of thousands, from their public race history, published in advance, with the error
published once the results are in. For a race director that is pacing, corral and medical
staffing planned from expected finish times rather than guesses; for a runner it is a goal
time with an honest interval instead of a hunch.

**Status: planning.** Nothing has run yet. The plan is in [PLAN.md](PLAN.md): a five-week
build, alongside other work, aimed at the Cape to Cabot 20 km in St. John's on
2026-10-18, with a second race on a frozen model on 2026-11-11. Predictions are committed
and tagged in this repository before each race and scored against the official results
after it.

## Result

Not yet measured. The build fills these tables.

**Live: predicted before the gun, scored after** (bootstrap 95% CIs over runners)

| Race | Runners predicted | Field coverage | MAE, minutes (model) | MAE, minutes (carry-forward baseline) | Coverage at 80% nominal | Coverage at 90% nominal | Median 80% width, minutes | Mean absolute place error | Spearman, predicted vs actual order | Prediction tag and hash |
|---|---|---|---|---|---|---|---|---|---|---|
| Cape to Cabot 20 km, 2026-10-18 | _not yet_ | | | | | | | | | |
| Run to Remember 11 km, 2026-11-11 | | | | | | | | | | |

**Backtest: every NLAA road race 2024 to 2026, each predicted from results strictly before it**

| Prior results per runner | Runners | Carry-forward MAE | Best equal-VDOT MAE | Hierarchical MAE | Challenger MAE | Coverage at 80% | Coverage at 90% | Median width |
|---|---|---|---|---|---|---|---|---|
| 0 | _not yet_ | | | | | | | |
| 1 | | | | | | | | |
| 2 to 3 | | | | | | | | |
| 4 or more | | | | | | | | |

**Course and conditions**

| Course | Estimated course factor (95% CI) | Physics prior | MAE without normalisation | MAE with normalisation |
|---|---|---|---|---|
| _not yet_ | | | | |

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
- It does not predict a runner it cannot tell apart from another runner of the same name.
  Those are excluded and counted.
- It does not publish anything about a runner beyond what the race results already
  publish: name and hometown as printed, and the prediction.
- Its intervals are calibrated on past races. Coverage is guaranteed on average within a
  history-depth group under exchangeability, not for any one runner or one race, and the
  tables above say where it held.

## How it works

See [PLAN.md](PLAN.md). Public road-race results from the Newfoundland and Labrador
Athletics Association are crawled once, parsed and resolved to runners across races.
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
