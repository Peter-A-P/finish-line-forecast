"""What the hills cost, from physics rather than from the results.

Minetti et al. (2002), "Energy cost of walking and running at extreme uphill and downhill
slopes", J Appl Physiol 93:1039-1046: the metabolic cost of running one metre at gradient
*i*, in joules per kilogram, fitted over gradients from -45 to +45 percent.

⚠️ **This is a prior, not an estimate** (CLAUDE.md: constants from Overload and from the
literature are priors). The course factor this project actually uses is measured from the
results, where 5,311 finishes pin Cape to Cabot to a tenth of a percentage point and no
elevation figure can compete with that. What this module is for is the case the results
cannot answer: a course with no history, a course whose route changed, and the sanity
check that the measured factor is a hill and not an artefact of who turns up.

⚠️ **The weak input is the grade distribution, not the elevation.** Five hundred and fifty
metres of climb spread over eleven kilometres at five percent is a materially easier race
than the same climb packed into five and a half kilometres at ten percent: 5.9 percent
against 9.0 percent on this model. Total gain alone therefore does not determine the
penalty, and `penalty` takes the average grade of the graded sections as an explicit
argument rather than pretending otherwise. `implied_grade` runs it backwards, which is how
a measured course factor and a published elevation figure are checked against each other.
"""

from __future__ import annotations

# Minetti's polynomial coefficients, highest power first. Flat running costs the constant
# term, 3.6 J/kg/m, which is the denominator of every ratio here.
_COEFFICIENTS = (155.4, -30.4, -43.3, 46.3, 19.5, 3.6)

FLAT_COST = 3.6

# The range Minetti fitted. Outside it the polynomial turns over and stops meaning
# anything, so it is refused rather than extrapolated.
MIN_GRADIENT = -0.45
MAX_GRADIENT = 0.45


def cost(gradient: float) -> float:
    """Joules per kilogram to run one metre at this gradient.

    The gradient is a ratio, not a percentage: 0.08 is an eight percent climb.
    """
    if not MIN_GRADIENT <= gradient <= MAX_GRADIENT:
        raise ValueError(
            f"gradient {gradient:.3f} is outside the range Minetti fitted "
            f"({MIN_GRADIENT:+.2f} to {MAX_GRADIENT:+.2f}); the polynomial turns over past it"
        )
    total = 0.0
    for coefficient in _COEFFICIENTS:
        total = total * gradient + coefficient
    return total


def penalty(
    *, distance_m: float, climb_m: float, drop_m: float, grade: float
) -> float:
    """How much slower this course is than a flat one, as a fraction of the flat time.

    At constant metabolic power, time is proportional to the distance-weighted cost, so
    the ratio of weighted cost to flat cost is the time penalty. The course is treated as
    three parts: the climbs at `grade`, the descents at `-grade`, and whatever distance is
    left over as flat.

    Constant power is an idealisation. A real runner does not hold power up a ten percent
    wall, and the descents give less back than the model says because braking is not free.
    Both errors push the same way, so treat the result as a floor on the penalty.
    """
    if grade <= 0:
        raise ValueError("grade is the average steepness of the graded sections, so positive")
    climbing = climb_m / grade
    descending = drop_m / grade
    flat = distance_m - climbing - descending
    if flat < 0:
        raise ValueError(
            f"{climb_m:.0f} m up and {drop_m:.0f} m down at {grade:.1%} needs "
            f"{(climbing + descending) / 1000:.1f} km of graded road, more than the "
            f"{distance_m / 1000:.1f} km course; the average grade must be steeper"
        )
    weighted = climbing * cost(grade) + descending * cost(-grade) + flat * FLAT_COST
    return weighted / (distance_m * FLAT_COST) - 1.0


def implied_grade(
    *, distance_m: float, climb_m: float, drop_m: float, factor: float
) -> float | None:
    """The average grade that would explain a measured course factor, or None.

    Runs `penalty` backwards. The answer is the question "is the measured factor
    consistent with the published climb?" in a form a reader can check: if a +9 percent
    course factor needs a 30 percent average grade to explain it, the factor is not the
    hills.
    """
    # The shallowest grade the course can physically have: any gentler and the climbs and
    # descents alone are longer than the race. At that grade there is no flat left, and the
    # penalty is as small as these hills can make it.
    lower = (climb_m + drop_m) / distance_m
    upper = MAX_GRADIENT
    if lower <= 0 or lower > upper:
        return None

    floor = penalty(distance_m=distance_m, climb_m=climb_m, drop_m=drop_m, grade=lower)
    ceiling = penalty(distance_m=distance_m, climb_m=climb_m, drop_m=drop_m, grade=upper)
    # ⚠️ Outside these, no grade explains the factor, and returning the nearest feasible
    # grade would quietly answer a different question. A course measured at +3 percent whose
    # gentlest possible profile already costs +5.9 percent is telling us the elevation
    # figure and the results disagree, which is the finding, not something to round away.
    if not floor <= factor <= ceiling:
        return None

    # The penalty rises with the grade over this range, so bisection is enough and needs no
    # derivative of a fifth-order polynomial.
    for _ in range(60):
        middle = (lower + upper) / 2
        if penalty(distance_m=distance_m, climb_m=climb_m, drop_m=drop_m, grade=middle) < factor:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2
