"""What the weather on the day costs, estimated from the editions rather than assumed.

The course layer says how hard a road is. This says how much of what is left over is the
morning. It fits the edition effects that `models.courses` produces against the observed
temperature and wind, with the temperature coefficient allowed to grow with distance,
because a 5 km field meets fifteen minutes of weather and a marathon field meets four
hours of it.

⚠️ **Weight by field size or measure nothing.** Fitted unweighted over all 227 editions
near the airport, the temperature coefficient is +0.027 percent per degree with an interval
straddling zero, and the honest conclusion looks like "weather does not matter here". It
does. An edition effect estimated from thirty finishers is mostly noise, and the archive is
full of them; weighting by the field, or keeping only editions above 400 finishers, moves
the same coefficient to +0.15 and +0.29 percent per degree with intervals clear of zero.
The null was the small races shouting down the large ones.

⚠️ **The coefficient is not one number.** Split by distance it is **negative** at 5 km,
+0.13 percent per degree at 8 to 11 km and +0.31 at 15 km and up, which is the ordering
physiology predicts and a single pooled coefficient averages away. The 5 km sign is left as
measured rather than clipped to zero: at that distance heat is not the binding constraint,
and a warm morning here is a calm one, while a cold one often comes with the wind and rain
that a 5 km field is exposed to for its whole race.

The cleanest single piece of evidence is the Tely 10: eleven editions, two to four thousand
finishers each, run anywhere from 3.6 to 22.7 degrees because two COVID years pushed it into
October. **+0.41 percent per degree on its own, +0.42 controlling for year**, R-squared 0.64.
That is in the range the marathon literature reports for mid-pack runners, arrived at
independently from one road in Newfoundland.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# The conditions a "neutral" time is quoted at: a cool, breezy St. John's morning, which is
# the middle of this archive rather than a laboratory ideal. Every adjustment is relative to
# these, so their exact values cancel out of any comparison and only matter for the wording
# of a published number.
NEUTRAL_TEMP_C = 10.0
NEUTRAL_WIND_KMH = 20.0

# Distances are compared against 10 km, so the fitted intercept is the coefficient for a
# 10 km race and the slope says how it changes per e-fold of distance.
REFERENCE_DISTANCE_M = 10_000.0

# Below this an edition effect is mostly noise about its own field. Editions are not
# dropped, they are weighted, but the weight is capped so that one Tely does not become the
# whole regression.
WEIGHT_CAP = 2_000.0


@dataclass(frozen=True, slots=True)
class Observation:
    """One edition: how it ran, what it ran through, and how much it should count."""

    race_id: str
    course_id: str
    distance_m: float
    finishers: int
    effect: float
    temp_c: float
    wind_kmh: float
    # Signed, positive for a tailwind, in km/h along the course's bearing. None for a loop
    # or out-and-back, which has no net direction and feels only the speed.
    tailwind_kmh: float | None


@dataclass(frozen=True, slots=True)
class Fit:
    """The conditions model, and enough of its uncertainty to publish."""

    editions: int
    temp_at_reference: float
    temp_per_log_distance: float
    wind: float
    tailwind: float
    explained: float
    residual_sd: float
    intervals: dict[str, tuple[float, float]]

    def temp_coefficient(self, distance_m: float) -> float:
        """Fractional cost per degree above neutral, at this distance."""
        return self.temp_at_reference + self.temp_per_log_distance * float(
            np.log(distance_m / REFERENCE_DISTANCE_M)
        )

    def adjustment(
        self,
        distance_m: float,
        temp_c: float,
        wind_kmh: float,
        tailwind_kmh: float | None = None,
    ) -> float:
        """How much slower than neutral this morning makes this race, as a fraction.

        Positive is slower. Applied to a neutral predicted time by multiplying by
        `1 + adjustment`, and inverted to turn a past result into a neutral one.

        `tailwind_kmh` is signed along the course's bearing and is None for a loop or an
        out-and-back, which has no net direction. A loop still pays the speed term.
        """
        return (
            self.temp_coefficient(distance_m) * (temp_c - NEUTRAL_TEMP_C)
            + self.wind * (wind_kmh - NEUTRAL_WIND_KMH)
            + self.tailwind * (0.0 if tailwind_kmh is None else tailwind_kmh)
        )

    def neutralise(
        self,
        seconds: float,
        distance_m: float,
        temp_c: float,
        wind_kmh: float,
        tailwind_kmh: float | None = None,
    ) -> float:
        """What this time would have been on a neutral morning."""
        return seconds / (
            1.0 + self.adjustment(distance_m, temp_c, wind_kmh, tailwind_kmh)
        )


def _design(rows: list[Observation]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Columns, response and weights, all taken within course.

    ⚠️ **The response has to be demeaned within its course or this measures the hills.**
    An edition effect from `models.courses` still contains the course: a Cape to Cabot
    edition sits at about +9 percent because of Signal Hill, not because of the morning.
    Fitted on the raw effects the temperature coefficient picks up the fact that the hard
    courses here run in October and the easy ones in June, and the residual comes out at
    4.4 percent, larger than the 2.8 percent scatter it is supposed to be explaining. That
    number being too big is what gave it away.

    Demeaning is done inside the course and weighted the same way the fit is, so a course's
    mean is set by its large editions rather than by how many small ones it has had.
    """
    temp = np.array([r.temp_c for r in rows]) - NEUTRAL_TEMP_C
    wind = np.array([r.wind_kmh for r in rows]) - NEUTRAL_WIND_KMH
    log_distance = np.log(np.array([r.distance_m for r in rows]) / REFERENCE_DISTANCE_M)
    y = np.array([r.effect for r in rows])
    weights = np.minimum(np.array([float(r.finishers) for r in rows]), WEIGHT_CAP)
    weights = np.maximum(weights, 1.0)

    # ⚠️ **A wind speed is not a wind.** Peter pointed this out from the road: at the Tely
    # the prevailing wind in June and July is westerly, and the course runs east-north-east
    # from Paradise into St. John's, so the usual wind is a tailwind for almost the whole
    # race. Cape to Cabot runs north-west, so the same westerly is a headwind. Fitted as one
    # speed term for the whole province those cancel, which is exactly what the first fit
    # showed: +0.076 percent per km/h with an interval straddling zero.
    #
    # So wind enters twice. `tailwind` is signed and only exists for a point-to-point
    # course, and its coefficient should come out negative because a tailwind helps.
    # `wind` is the speed, which every course feels, because a loop loses more into the
    # wind than it gains coming back. A loop contributes only to the second.
    tailwind = np.array([0.0 if r.tailwind_kmh is None else r.tailwind_kmh for r in rows])

    courses = np.array([r.course_id for r in rows], dtype=object)
    columns = [temp, temp * log_distance, wind, tailwind]
    for course in set(courses.tolist()):
        mask = courses == course
        y[mask] -= np.average(y[mask], weights=weights[mask])
        for column in columns:
            column[mask] -= np.average(column[mask], weights=weights[mask])

    # No intercept: the within-course transformation has already removed every level there
    # was, and leaving one in would fit a global mean of zero and cost a degree of freedom.
    return np.column_stack(columns), y, weights


def _solve(design: np.ndarray, y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    root = np.sqrt(weights)[:, None]
    beta, *_ = np.linalg.lstsq(design * root, y * root[:, 0], rcond=None)
    return np.asarray(beta)


def fit(rows: list[Observation], *, seed: int = 20261018, draws: int = 2000) -> Fit | None:
    """Estimate the conditions model, or None where there is not enough to estimate it.

    The interval resamples editions, because an edition is the unit that has weather. Two
    runners in one race did not each independently experience that morning.
    """
    if len(rows) < 20:
        return None
    design, y, weights = _design(rows)
    beta = _solve(design, y, weights)
    fitted = design @ beta
    # y is already within-course, so its weighted mean is zero and this is the share of the
    # edition-to-edition movement explained, not the share of the difference between courses.
    explained = 1.0 - float(np.average((y - fitted) ** 2, weights=weights)) / float(
        np.average(y**2, weights=weights)
    )

    rng = np.random.default_rng(seed)
    sampled = np.empty((draws, design.shape[1]))
    for draw in range(draws):
        # Resample editions, then rebuild the design from scratch, so that the within-course
        # demeaning is redone on the drawn sample. Reusing the already-demeaned columns
        # would treat each course's mean as known and give an interval that is too narrow.
        drawn = [rows[index] for index in rng.integers(0, len(rows), len(rows))]
        drawn_design, drawn_y, drawn_weights = _design(drawn)
        sampled[draw] = _solve(drawn_design, drawn_y, drawn_weights)

    names = ("temp_at_10km", "temp_per_log_distance", "wind", "tailwind")
    intervals = {
        name: (
            float(np.percentile(sampled[:, index], 2.5)),
            float(np.percentile(sampled[:, index], 97.5)),
        )
        for index, name in enumerate(names)
    }
    return Fit(
        editions=len(rows),
        temp_at_reference=float(beta[0]),
        temp_per_log_distance=float(beta[1]),
        wind=float(beta[2]),
        tailwind=float(beta[3]),
        explained=explained,
        residual_sd=float(np.sqrt(np.average((y - fitted) ** 2, weights=weights))),
        intervals=intervals,
    )
