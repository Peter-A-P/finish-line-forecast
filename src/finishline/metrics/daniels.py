"""VDOT and the two ways to carry one race time to another distance.

WHERE THIS COMES FROM
---------------------
The two curves are Daniels and Gilbert, *Oxygen Power* (1979), and the power law is Pete
Riegel's. Both are published and decades old. The implementation is carried across from
the Overload project, which pins it against the reference tables to five decimals; the
constants are reproduced here with the same warning attached, and every personal
calibration in that project (its wind constant, its heart-rate model, one athlete's
history) is deliberately left behind. Nothing in this file knows about a person.

WHAT VDOT IS FOR HERE
---------------------
VDOT is the VO2max a runner with textbook running economy would need in order to have run
the performance they actually ran. It is not a measurement of anyone's physiology. What
makes it useful is that it puts a 5 km and a marathon on one scale, so "this runner's best
recent form" can be read off a race at any distance and carried to the one being
predicted. That is the **best equal-VDOT baseline** (PLAN.md 2.3), and it is what every
online race calculator does, which is exactly why it is the baseline to beat.

⚠️ **This module refuses far more often than a race calculator does, and the refusals
are a published number.** The %VO2max curve is fitted to racing durations of roughly
three minutes to four hours. Below that it climbs past 100% of VO2max and means nothing;
above it the exponentials have flattened and the curve is extrapolation. A five-hour
marathon is a real result by a real runner and this model has nothing honest to say about
it, so it returns None and the backtest reports what share of the field the calculator
baseline could not answer for. That share is a finding, not a gap: it is the part of a
race field that the standard tool silently guesses at.
"""

from __future__ import annotations

import math

# Daniels and Gilbert, Oxygen Power (1979). Fitted coefficients, not roundable
# quantities: do not tidy them.
_VO2_A, _VO2_B, _VO2_C = -4.60, 0.182258, 0.000104
_PCT_BASE = 0.8
_PCT_A1, _PCT_K1 = 0.1894393, -0.012778
_PCT_A2, _PCT_K2 = 0.2989558, -0.1932605

# Riegel's exponent, banded by target distance as the reference tables apply it. The
# exponent is the endurance term: 1.06 says a runner slows by six percent per doubling.
_RIEGEL_BANDS: tuple[tuple[float, float], ...] = (
    (2000.0, 1.08),
    (3000.0, 1.075),
    (4828.032, 1.07),
)
RIEGEL_DEFAULT_EXPONENT = 1.06

# Validity. See the module note: outside these the answer is None, not a number.
MIN_MINUTES, MAX_MINUTES = 3.0, 240.0
MIN_DISTANCE_M = 1000.0
MIN_VDOT, MAX_VDOT = 20.0, 90.0


def vo2_at_velocity(metres_per_minute: float) -> float:
    """Oxygen cost, ml/kg/min, of running at this velocity."""
    return _VO2_A + _VO2_B * metres_per_minute + _VO2_C * metres_per_minute**2


def pct_vo2max(minutes: float) -> float:
    """The fraction of VO2max a runner can hold for this many minutes of racing."""
    return (
        _PCT_BASE
        + _PCT_A1 * math.exp(_PCT_K1 * minutes)
        + _PCT_A2 * math.exp(_PCT_K2 * minutes)
    )


def vdot(distance_m: float | None, seconds: float | None) -> float | None:
    """The VDOT implied by covering this distance in this time, or None.

    Returned unrounded, because projections are solved from it and rounding to the one
    decimal a human reads costs seconds over a marathon.
    """
    if not distance_m or not seconds or distance_m <= 0 or seconds <= 0:
        return None
    if distance_m < MIN_DISTANCE_M:
        return None
    minutes = seconds / 60.0
    if not (MIN_MINUTES <= minutes <= MAX_MINUTES):
        return None
    value = vo2_at_velocity(distance_m / minutes) / pct_vo2max(minutes)
    if not (MIN_VDOT <= value <= MAX_VDOT):
        return None
    return value


def race_time(vdot_value: float | None, distance_m: float) -> float | None:
    """The time this VDOT predicts over this distance, in seconds, or None.

    There is no closed form: the duration appears on both sides of the model, so this
    solves it by bisection. VDOT falls monotonically as the time for a fixed distance
    rises, which is what makes bisection safe, and two hundred halvings of a one-second
    to one-day bracket is far past the precision of a float.
    """
    if vdot_value is None or distance_m <= 0:
        return None

    def implied(seconds: float) -> float:
        minutes = seconds / 60.0
        return vo2_at_velocity(distance_m / minutes) / pct_vo2max(minutes)

    low, high = 1.0, 86400.0
    if implied(high) > vdot_value or implied(low) < vdot_value:
        return None  # outside what the curves can represent
    for _ in range(200):
        middle = (low + high) / 2.0
        if implied(middle) > vdot_value:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def riegel_exponent(distance_m: float) -> float:
    """The exponent to use for a target distance."""
    for limit, exponent in _RIEGEL_BANDS:
        if distance_m < limit:
            return exponent
    return RIEGEL_DEFAULT_EXPONENT


def riegel(
    base_seconds: float | None,
    base_distance_m: float,
    target_distance_m: float,
    exponent: float | None = None,
) -> float | None:
    """Pete Riegel's endurance power law: T2 = T1 * (D2/D1) ** k.

    ⚠️ **The default exponent is known to be optimistic at the marathon**, and this
    project measures by how much rather than repeating it. Vickers and Vertosick (2016),
    on 2,303 recreational runners, found the standard formula well calibrated up to the
    half marathon and at least ten minutes fast for half of marathon runners. That is why
    the hierarchical model fits an endurance exponent per runner, shrunk toward the
    population (PLAN.md 5.3), and why this function takes an exponent rather than
    assuming one. Passing None gives the textbook value, which is the baseline.
    """
    if base_seconds is None or base_seconds <= 0 or base_distance_m <= 0:
        return None
    ratio = target_distance_m / base_distance_m
    power = riegel_exponent(target_distance_m) if exponent is None else exponent
    return float(base_seconds * ratio**power)


def equivalent_time(
    base_seconds: float | None, base_distance_m: float, target_distance_m: float
) -> float | None:
    """The equal-VDOT equivalent of a performance at another distance, or None.

    This is what a race calculator gives: read the fitness off one race, read the time
    back off at another distance. It round-trips exactly, unlike Riegel, which anchors on
    the entered performance and does not.
    """
    return race_time(vdot(base_distance_m, base_seconds), target_distance_m)
