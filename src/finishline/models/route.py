"""Which way a course runs, leg by leg, and what a wind does to a field running it.

WHY
---
Until 2026-10-18 a course carried one `bearing_deg`, the compass direction from its start to
its finish, and the model charged the whole wind along that line as if the field ran it for
the whole race. Cape to Cabot's 321 degrees is the straight line from Cape Spear to Signal
Hill; the race runs west, north-west, north, north-east and then east, so its first and last
legs face opposite ways and the line describes none of it. Run to Remember, out east and back
west, had no bearing at all, which said nothing about whether the day's wind blew along its
road or across it. PLAN.md 13 item 48.

THE ROUTE
---------
A course with `waypoints` in `data/courses.toml` (points typed onto the public road at each
turn, start first, finish last, an out-and-back's turnaround in between) is cut into legs, and
each leg keeps its compass heading and its share of the distance. Nothing about a run is in it:
the points are the road, as Flat Out's have always been.

THE TWO WIND TERMS
------------------
For a wind blowing with vector v, a leg heading along unit vector u feels v.u of it along the
road: positive behind the runners, negative in their faces. Over the whole course:

    net       = sum over legs of share x (v.u)           the push the course gets, signed
    exposure  = sum over legs of share x |v.u|        how much of the wind lies along the road
                + (2/pi) x (mean speed - |v|)         the part with no steady direction

`net` is what the old tailwind term tried to be. On an out-and-back it is zero, whatever the
wind. `exposure` is why that does not mean the wind is free there: a headwind costs more than
the same tailwind gives back, so a model with a cost on `exposure` and a (negative) cost on
`net` charges a headwind leg more than it credits a tailwind leg, and charges an out-and-back
into a wind along its road more than one with the wind across it. Crosswind is taken as free.

A course with no waypoints is taken to face every direction equally, which is the honest
statement of not knowing: `net` is zero and `exposure` is (2/pi) of the mean speed, the
average of |cos| over a circle. That is exactly the old wind-speed term, scaled.

⚠️ **Order does not matter here, and that is a simplification.** The wind is the average over
the race hours, so a leg run at 08:10 and a leg run at 09:30 see the same wind. Only the share
of the distance in each direction counts.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

# The mean of |cos| over a full circle: a wind meeting a course that faces every way equally.
EVERY_WAY = 2.0 / math.pi

_EARTH_M = 6_371_000.0


@dataclass(frozen=True, slots=True)
class Leg:
    """One straight stretch between two waypoints."""

    heading_deg: float  # compass bearing the runners travel on
    share: float  # of the route's length


@dataclass(frozen=True, slots=True)
class Route:
    """A course as its legs."""

    legs: tuple[Leg, ...]

    @property
    def net_share(self) -> float:
        """Straight-line displacement over the distance run: 1 for a straight road, 0 for a
        course that ends where it started."""
        east = sum(leg.share * math.sin(math.radians(leg.heading_deg)) for leg in self.legs)
        north = sum(leg.share * math.cos(math.radians(leg.heading_deg)) for leg in self.legs)
        return math.hypot(east, north)


def heading(a: Sequence[float], b: Sequence[float]) -> float:
    """Initial great-circle bearing from point a to point b, degrees clockwise from north."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x)) % 360.0


def distance_m(a: Sequence[float], b: Sequence[float]) -> float:
    """Great-circle distance between two points, in metres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * _EARTH_M * math.asin(math.sqrt(h))


def from_waypoints(points: Sequence[Sequence[float]]) -> Route:
    """The legs between consecutive points, each with its share of the total length."""
    if len(points) < 2:
        raise ValueError("a route needs at least two waypoints")
    pairs = list(pairwise(points))
    lengths = [distance_m(a, b) for a, b in pairs]
    total = sum(lengths)
    if total <= 0:
        raise ValueError("the waypoints do not go anywhere")
    return Route(
        tuple(
            Leg(heading(a, b), length / total)
            for (a, b), length in zip(pairs, lengths, strict=True)
            if length > 0
        )
    )


def routes(courses: Mapping[str, Mapping[str, Any]]) -> dict[str, Route]:
    """Every course in data/courses.toml that has waypoints, as its route."""
    return {
        course_id: from_waypoints(record["waypoints"])
        for course_id, record in courses.items()
        if record.get("waypoints")
    }


def wind_terms(
    east: float | None, north: float | None, speed: float | None, route: Route | None
) -> tuple[float, float]:
    """(exposure, net) in km/h for a wind of this mean vector and mean speed on this course.

    `east` and `north` are the components of the direction the air travels (`eccc`), so a
    leg's share of it is east x sin(heading) + north x cos(heading), positive behind the field.
    """
    if east is None or north is None:
        east = north = 0.0
    steady = math.hypot(east, north)
    mean_speed = steady if speed is None else max(speed, steady)
    if route is None:
        return EVERY_WAY * mean_speed, 0.0
    along = [
        (
            leg.share,
            east * math.sin(math.radians(leg.heading_deg))
            + north * math.cos(math.radians(leg.heading_deg)),
        )
        for leg in route.legs
    ]
    net = sum(share * value for share, value in along)
    exposure = sum(share * abs(value) for share, value in along)
    return exposure + EVERY_WAY * (mean_speed - steady), net
