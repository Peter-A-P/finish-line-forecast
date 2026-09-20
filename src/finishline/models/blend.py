"""The two models together: the hierarchical model's distribution, moved to a blended centre.

PLAN.md section 13 item 35. The hierarchical model and the LightGBM challenger make different
mistakes, so the average of the two is better than either, and the backtest says by how much.
Blending is on the log scale, which is the scale everything here is measured on:

    log(blend) = (1 - WEIGHT) * log(hierarchical) + WEIGHT * log(challenger)

WHY THE DISTRIBUTION IS THE HIERARCHICAL MODEL'S, MOVED
-------------------------------------------------------
A published prediction is not one number. It carries an 80% and a 90% range, and a place in
a field of several hundred, which needs every runner drawn together on one shared morning
(`placing.simulate`). Quantile trees give seven numbers per runner and no joint draws, so
there is nothing to simulate a field from. So the blend keeps the hierarchical model's draws
and multiplies each runner's by a single factor, the one that moves their median onto the
blended centre:

    factor_i = (challenger_i / hierarchical_i) ** WEIGHT

Each runner's whole distribution shifts with their median; its shape and width are the
hierarchical model's, and the conformal layer then calibrates the blend's intervals on the
blend's own backtest errors, which is what makes the published coverage honest.

⚠️ **The weight is chosen on 2022 and 2023, never on the backtest** (`scratch/blend_weight.py`),
for the reason the challenger's own tuning was (item 34): a weight read off the 2024+ races
would make the number those races report a number about themselves.

⚠️ **A newcomer drawn from a course's first-timer pool is not blended.** At the biggest races
an entrant with no result here is drawn from how first-timers actually finished on that course
(`placing.unseen`), which is a measurement rather than either model's prediction, and the
challenger has no more to say about them than the group prior does.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from finishline.backtest.score import Scored

NAME = "blend"

# Read off 2022 and 2023 only, never the backtest (`scratch/blend_weight.py`, PLAN.md 13 item
# 35): both models run over the same window the challenger was tuned on, 34 races and 7,602
# runners they both answered for. The curve is flat from 0.60 to 0.75, and resampling races puts
# the best weight between 0.50 and 0.80, so what the window establishes is the direction, lean
# about two thirds on the challenger, rather than this second decimal.
WEIGHT = 0.65


def centre(hierarchical: float, challenger: float, weight: float = WEIGHT) -> float:
    """The blended prediction, in seconds."""
    if hierarchical <= 0 or challenger <= 0:
        raise ValueError("a finish time is positive")
    return math.exp((1 - weight) * math.log(hierarchical) + weight * math.log(challenger))


def factor(hierarchical: float, challenger: float, weight: float = WEIGHT) -> float:
    """What every draw of this runner's is multiplied by to sit on the blended centre."""
    return centre(hierarchical, challenger, weight) / hierarchical


def factors(
    hierarchical: Mapping[str, float],
    challenger: Mapping[str, float],
    weight: float = WEIGHT,
) -> dict[str, float]:
    """One factor per runner both models answered for; a runner missing from either is 1.0."""
    return {
        runner_id: factor(median, challenger[runner_id], weight)
        for runner_id, median in hierarchical.items()
        if runner_id in challenger and median > 0 and challenger[runner_id] > 0
    }


def rows(
    scored: Sequence[Scored],
    hierarchical: str = "hierarchical",
    challenger: str = "lightgbm",
    weight: float = WEIGHT,
) -> list[Scored]:
    """Blend two models' saved backtest rows, exactly as a live prediction blends them.

    The quantiles are the hierarchical model's scaled by the same factor, which is what
    multiplying its draws does, so the backtest calibrates the intervals a freeze will write.
    """
    pairs: dict[tuple[str, str], dict[str, Scored]] = {}
    for row in scored:
        if row.model in (hierarchical, challenger):
            pairs.setdefault((row.race_id, row.runner_id), {})[row.model] = row
    blended: list[Scored] = []
    for pair in pairs.values():
        left, right = pair.get(hierarchical), pair.get(challenger)
        if left is None or right is None:
            continue
        if left.predicted is None or right.predicted is None or left.predicted <= 0:
            blended.append(Scored(NAME, left.race_id, left.runner_id, None, left.actual,
                                  left.depth))
            continue
        scale = factor(left.predicted, right.predicted, weight)
        blended.append(
            Scored(
                model=NAME,
                race_id=left.race_id,
                runner_id=left.runner_id,
                predicted=left.predicted * scale,
                actual=left.actual,
                depth=left.depth,
                quantiles=tuple(value * scale for value in left.quantiles),
            )
        )
    return blended
