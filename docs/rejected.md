# Tried and rejected: weather as a straight line in temperature

One approach this project built, backtested, published and then took out, with the
evidence. The full log of designs the data refuted is [PLAN.md](../PLAN.md) section 13; this
is the one worth reading if you read one, because it is the obvious design, it looked fine
in the headline table, and it is the wrong shape.

## What it was

Every edition's morning, read at St. John's airport, entered the race effect as

    cost = (a + b * log(distance / 10 km)) * (T - 10 C) + w * (wind - 20 km/h) + tailwind term

a straight line in temperature from a neutral 10 C, steeper for longer races, with the
coefficients estimated inside the hierarchical model (PLAN.md section 13 item 29). It is the
design most race-time models use, it has the right sign, and the fitted slope looked
reasonable: +0.120% per degree at 10 km (95% CI +0.074 to +0.164), +0.27% on Cape to Cabot,
+0.42% at a marathon.

## Why it looked fine

The per-runner accuracy table could not see a problem. Removing the weather terms entirely
changed mean absolute error by nothing measurable: paired on 18,278 backtest predictions the
gain was 0.0003 of absolute log error (95% CI -0.0008 to +0.0002). That is not the evidence
against it. A term that moves a whole field by one to five percent is close to invisible in a
per-runner error of around ten, so this table cannot tell a right weather model from a wrong
one, and it was first misread as "weather does not matter here", which is in PLAN.md section
13 as the wrong conclusion it was.

## The evidence against it

**The straight line is the worst shape the data was offered, by a margin the intervals
clear.** Two tests, each scored leave one year out so that a warm year cannot pose as
weather, and each difference given a 95% interval from resampling years
(`scratch/sun_experiment.py`, read from a 9 am start before the organisers' start times were
on file):

| Test | Linear from 10 C | Best hinge on felt heat | Best minus linear |
|---|---:|---:|---|
| A: 227 editions against their own course, out-of-sample R2 | 0.184 | 0.360 | +0.176 (+0.078 to +0.276) |
| B: 121 pairs of consecutive editions, the 19,035 runners who ran both | -0.354 | 0.485 | +0.839 (+0.282 to +2.821) |

Test B is the sharper one, because the same people ran both editions, so a hot year cannot
be a slower field. A negative R2 there means the linear model predicted the change between
two editions worse than predicting no change at all. The shape explains why: a cool morning
is not a bonus and a warm one costs more than a line allows, so a line fitted across both is
too shallow where it matters and wrong where it does not.

**It hid inside the calendar-year effect.** Averaged by year, the editions' course-relative
effect tracked the year's average temperature at +0.403% per degree (correlation +0.63 over
18 years). With a year effect in the model and a linear weather term collinear with each
year's average, the weather was identified only by differences between races within a year,
and the year walk carried the rest forward: a cool 2025 into 2026 as if the runners had got
faster.

## What replaced it

Heat as a hinge on felt temperature: nothing below 12 C; above it, a cost per degree that
grows with distance; and the sun raising the felt temperature by a number of degrees the
model estimates rather than assumes (PLAN.md section 13 item 30). On the same backtest, with
each run's race-level bias regressed on one common measure of the heat (the felt-heat cost at
the whole-archive estimates, `scratch/rejected_slope.py`):

| | No weather | Linear from 10 C | Felt heat above 12 C |
|---|---:|---:|---:|
| Race-level bias against the heat, slope (+/- 95%) | +0.42 (+/- 0.30) | +0.11 (+/- 0.31) | -0.15 (+/- 0.30) |
| 2025 USR half marathon, the hottest morning in the backtest | 3.7% too fast | 1.4% too fast | 0.9% too slow |
| 2025 Tely 10 | 2.7% too slow | 2.2% too slow | 0.7% too slow |
| Paired gain in absolute log error over no weather | | 0.0003 (-0.0008 to +0.0002) | 0.0010 (-0.0019 to +0.0002) |

⚠️ **The backtest does not separate the two weather models, and this page does not pretend
it does.** Both take out the bias that grows with the heat, which the no-weather run leaves at
+0.42; the difference between +0.11 and -0.15 is inside either interval, and so is the
difference in paired error. Three years of backtest races, of which a handful were warm, is
not enough to tell two sensible heat models apart. The case for the hinge is the two tests
above, which have eighteen years in them, and a shape that says a cool morning costs nothing.

## What it did not fix

The 2026 Tely 10 is still predicted 3.0% too fast. It was 18 C, lightly sunny and calm, the
model charges it 3.1% for heat, and it ran about 6% slower than a neutral morning. The linear
model missed it by as much. It is recorded as open rather than tuned away.

## The caveat

The knee at 12 C was chosen on editions that include the backtest's own races. One round
value chosen on eighteen years flatters a backtest of three only a little, but it flatters
it, and the comparison above is read with that in mind. The live races are the test that
cannot be flattered.
