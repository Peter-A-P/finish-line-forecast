"""The grade model, and the course factors measured from results.

Two ways of answering the same question, so the last test here is the one that matters:
they have to agree on Cape to Cabot.
"""

from __future__ import annotations

import math
import tomllib
from datetime import date
from itertools import pairwise
from pathlib import Path

import pytest

from finishline.history import History
from finishline.identity.resolve import Runner
from finishline.metrics import grade
from finishline.models import courses
from finishline.schema import Race, Result

COURSES = Path("data/courses.toml")


def test_flat_running_costs_minettis_constant() -> None:
    """The one value everything else is a ratio of."""
    assert grade.cost(0.0) == pytest.approx(3.6)


def test_the_published_values_are_reproduced() -> None:
    """Spot values off Minetti's fitted curve, J/kg/m."""
    assert grade.cost(0.10) == pytest.approx(5.97, abs=0.02)
    assert grade.cost(0.20) == pytest.approx(9.01, abs=0.02)
    assert grade.cost(-0.10) == pytest.approx(2.15, abs=0.02)


def test_the_cheapest_running_is_downhill_not_flat() -> None:
    """The result Minetti is cited for, and an independent check on the coefficients.

    The curve has a minimum on the descent rather than at zero, and the paper puts it near
    -20 percent. A model that made flat the cheapest would be wrong about every descent on
    every course here, and would get Cape to Cabot's 450 m of drop badly wrong.
    """
    grades = [g / 1000 for g in range(-450, 1)]
    cheapest = min(grades, key=grade.cost)
    assert -0.25 < cheapest < -0.15, f"minimum at {cheapest:.1%}, not near -20%"
    assert grade.cost(cheapest) < grade.cost(0.0)
    # And it turns back up: very steep descents cost more than moderate ones, because
    # braking is work.
    assert grade.cost(-0.40) > grade.cost(cheapest)


def test_beyond_the_fitted_range_it_refuses_rather_than_extrapolates() -> None:
    with pytest.raises(ValueError, match="outside the range"):
        grade.cost(0.60)


def test_a_flat_course_carries_no_penalty() -> None:
    assert grade.penalty(distance_m=10_000, climb_m=0, drop_m=0, grade=0.05) == pytest.approx(0.0)


def test_the_same_climb_packed_steeper_costs_more() -> None:
    """Total gain does not determine the penalty, which is why grade is an argument."""
    gentle = grade.penalty(distance_m=20_000, climb_m=550, drop_m=450, grade=0.05)
    steep = grade.penalty(distance_m=20_000, climb_m=550, drop_m=450, grade=0.10)
    assert steep > gentle
    assert gentle == pytest.approx(0.059, abs=0.002)
    assert steep == pytest.approx(0.090, abs=0.002)


def test_a_climb_that_will_not_fit_on_the_course_is_refused() -> None:
    """550 m up at one percent needs 55 km of road, and a 20 km race has not got it."""
    with pytest.raises(ValueError, match="more than the"):
        grade.penalty(distance_m=20_000, climb_m=550, drop_m=450, grade=0.01)


def test_implied_grade_inverts_the_penalty() -> None:
    for wanted in (0.06, 0.085, 0.12, 0.20):
        solved = grade.implied_grade(
            distance_m=20_000, climb_m=550, drop_m=450, factor=wanted
        )
        assert solved is not None
        back = grade.penalty(distance_m=20_000, climb_m=550, drop_m=450, grade=solved)
        assert back == pytest.approx(wanted, abs=1e-4)


def test_a_factor_the_hills_cannot_explain_comes_back_as_none() -> None:
    """Both ends, and the low end is the one that caught a bug.

    550 m up and 450 m down over 20 km cannot cost less than about 5.9 percent: at any
    gentler grade the graded sections are longer than the race. Asked to explain a +3
    percent course, the first version quietly returned the shallowest feasible grade, which
    answers a different question. A course whose measured factor sits below its own floor
    is telling us the elevation figure and the results disagree, and that is a finding.
    """
    assert grade.implied_grade(distance_m=20_000, climb_m=550, drop_m=450, factor=0.40) is None
    assert grade.implied_grade(distance_m=20_000, climb_m=550, drop_m=450, factor=0.03) is None
    floor = grade.penalty(distance_m=20_000, climb_m=550, drop_m=450, grade=0.05)
    assert floor == pytest.approx(0.059, abs=0.002)
    assert grade.implied_grade(
        distance_m=20_000, climb_m=550, drop_m=450, factor=floor
    ) == pytest.approx(0.05, abs=1e-3)


def test_the_gentlest_feasible_grade_is_not_refused_for_rounding() -> None:
    """`implied_grade` evaluates the penalty exactly at the grade where no flat is left.

    Before the fix, 35 m up and 47 m down over 4,950 m raised "needs 5.0 km of graded road,
    more than the 5.0 km course", because the graded lengths summed to the distance plus a
    few ulps; so did about a quarter of every climb, drop and distance a course could have.
    The genuinely infeasible case still raises.
    """
    grade.implied_grade(distance_m=4_950, climb_m=35, drop_m=47, factor=0.0)
    for distance in (4_950, 5_000, 10_000, 20_000):
        for climb in range(10, 120, 7):
            for drop in range(10, 130, 3):
                grade.implied_grade(distance_m=distance, climb_m=climb, drop_m=drop, factor=0.0)
    with pytest.raises(ValueError, match="more than"):
        grade.penalty(distance_m=5_000, climb_m=39, drop_m=52, grade=0.017)


def test_the_course_file_parses_and_cites_every_number() -> None:
    """A published elevation figure with no source is a rumour."""
    loaded = tomllib.loads(COURSES.read_text(encoding="utf-8"))
    assert "cape-to-cabot-20000" in loaded
    for course_id, record in loaded.items():
        assert record["name"], course_id
        if "climb_m" in record:
            assert record.get("source"), f"{course_id} states a climb with no source"


def test_cape_to_cabot_physics_agrees_with_the_measured_factor() -> None:
    """The check the whole module exists for.

    5,311 finishes over 15 editions say Cape to Cabot costs +9.2 percent [+8.9, +9.4]
    against an equal-VDOT flat time. The race publishes 550 m of climb against 450 m of
    drop over 20 km. If those two are describing the same race, the grade that reconciles
    them has to be a grade a road can actually have, and the race's own page says "grades
    of more than 10 per cent in some parts".

    The whole interval is checked, not just the point estimate, because the claim being
    made is that the physics and the results agree and a point estimate cannot support it.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["cape-to-cabot-20000"]
    shape = {
        "distance_m": record["distance_m"],
        "climb_m": record["climb_m"],
        "drop_m": record["drop_m"],
    }
    solved = grade.implied_grade(**shape, factor=0.092)
    assert solved is not None
    assert solved == pytest.approx(0.103, abs=0.005)

    for end in (0.089, 0.094):
        at_end = grade.implied_grade(**shape, factor=end)
        assert at_end is not None
        assert 0.08 < at_end < 0.13, f"implied grade {at_end:.1%} is not a road"

    # And the watch figure, six percent lower, has to land somewhere sane too or the two
    # elevation sources disagree about more than measurement noise.
    watch = grade.implied_grade(
        distance_m=record["distance_m"],
        climb_m=record["independent_climb_m"],
        drop_m=record["drop_m"],
        factor=0.092,
    )
    assert watch is not None
    assert 0.09 < watch < 0.14


def _leg(start: list[float], end: list[float]) -> complex:
    """One straight leg as a vector in metres, east as real and north as imaginary.

    Flat-earth over a few hundred metres, which is centimetres from the great circle here.
    """
    metres_per_degree = 6_371_008.8 * math.pi / 180
    north = (end[0] - start[0]) * metres_per_degree
    east = (end[1] - start[1]) * metres_per_degree * math.cos(math.radians(start[0]))
    return complex(east, north)


def test_flat_out_has_no_bearing_because_it_goes_nowhere() -> None:
    """A loop gets no bearing, and for Flat Out that is measured from its waypoints.

    Nearly two laps of one block: the legs sum to the 363 m from start to finish, which is
    under a tenth of the route. A bearing on those 363 m would put a tailwind term on 4.6 km
    of road running every other way.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["flat-out-5000"]
    assert "bearing_deg" not in record
    points = record["waypoints"]
    legs = [_leg(a, b) for a, b in pairwise(points)]
    travelled = sum(abs(leg) for leg in legs)
    net = abs(sum(legs))
    assert net == pytest.approx(363, abs=5)
    assert travelled == pytest.approx(4_604, abs=20)
    assert net / travelled < 0.10
    # The laps repeat: the second pass of the start corner and of the far corner lands
    # within a few metres of the first.
    assert abs(_leg(points[0], points[4])) < 25
    assert abs(_leg(points[3], points[7])) < 25


def _synthetic() -> tuple[dict[str, Race], list[Runner]]:
    """Runners who age, on an easy course and a hard one, every year.

    Every runner runs both courses each year and slows by two percent a year. The hard
    course is built to cost exactly ten percent. Nothing about the hard course changes over
    time, so any drift a fit reports is the fit's own.
    """
    races: dict[str, Race] = {}
    for year in range(2010, 2026):
        for course, name in (("easy-10000", "Easy"), ("hard-10000", "Hard")):
            race_id = f"{course}-{year}"
            races[race_id] = Race(
                race_id=race_id,
                name=f"{name} {year}",
                date=date(year, 6, 1),
                distance_m=10_000.0,
                course_id=course,
                url=f"https://example.invalid/{race_id}",
            )

    runners: list[Runner] = []
    for person in range(60):
        base = 2400.0 + person * 12
        results = []
        for year in range(2010, 2026):
            ageing = 1.02 ** (year - 2010)
            for course in ("easy-10000", "hard-10000"):
                hills = 1.10 if course == "hard-10000" else 1.0
                results.append(
                    Result(
                        race_id=f"{course}-{year}",
                        place=person + 1,
                        bib=None,
                        name=f"Runner {person}",
                        club=None,
                        sex="M",
                        sex_place=None,
                        age_band=None,
                        category_place=None,
                        hometown=None,
                        gun_seconds=base * ageing * hills,
                        chip_seconds=None,
                    )
                )
        runners.append(
            Runner(
                runner_id=f"r{person}",
                name=f"Runner {person}",
                hometown=None,
                sex="M",
                results=tuple(results),
                ambiguous=False,
            )
        )
    return races, runners


def test_the_measured_factor_recovers_a_known_course_effect() -> None:
    races, runners = _synthetic()
    history = History.before(date(2026, 1, 1), races, runners)
    fitted = courses.fit(history, races, draws=40)

    hard = fitted.courses["hard-10000"]
    easy = fitted.courses["easy-10000"]
    # Effects are centred, so the gap between the two is the thing that was planted.
    assert (1 + hard.factor) / (1 + easy.factor) == pytest.approx(1.10, abs=0.005)
    assert hard.low < hard.factor < hard.high


def test_the_career_trend_stops_ageing_leaking_into_the_course() -> None:
    """The trap this module's docstring is about, on data where the truth is known.

    The runners slow by two percent a year and the courses never change. Without a
    per-runner trend the edition effects absorb the ageing and climb with the calendar,
    which on the real archive reads as Cape to Cabot getting ten points harder since 2013.
    """
    races, runners = _synthetic()
    history = History.before(date(2026, 1, 1), races, runners)
    fitted = courses.fit(history, races, draws=20)

    hard = sorted(
        (races[race_id].date.year, value)
        for race_id, value in fitted.editions.items()
        if races[race_id].course_id == "hard-10000"
    )
    years = [float(year) for year, _ in hard]
    values = [value for _, value in hard]
    n = len(years)
    mean_x = sum(years) / n
    mean_y = sum(values) / n
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(years, values, strict=True)) / sum(
        (x - mean_x) ** 2 for x in years
    )
    assert math.isclose(slope, 0.0, abs_tol=0.002), (
        f"edition effects drift {slope * 100:.2f}% a year on a course that never changed"
    )


def _two_lengths() -> tuple[dict[str, Race], list[Runner]]:
    """Four courses at two lengths, where the only thing out of step with Daniels is a length.

    Two 10 km courses, one of them ten percent harder than the other, and two marathons with
    no hills at all. Every runner is exactly on Daniels' curve at 10 km and five percent
    slower than it at the marathon, which is what a population that does not train for the
    distance does. Any marathon difficulty a fit reports here is the fit's own.
    """
    from finishline.metrics import daniels

    lengths = {"easy-10000": 10_000.0, "hard-10000": 10_000.0}
    lengths |= {"mara-a-42195": 42_195.0, "mara-b-42195": 42_195.0}
    races: dict[str, Race] = {}
    for year in range(2018, 2026):
        for course_id, metres in lengths.items():
            race_id = f"{course_id}-{year}"
            races[race_id] = Race(
                race_id=race_id,
                name=f"{course_id} {year}",
                date=date(year, 6, 1),
                distance_m=metres,
                course_id=course_id,
                url=f"https://example.invalid/{race_id}",
            )

    runners: list[Runner] = []
    for person in range(40):
        vdot = 42.0 + person * 0.4
        results = []
        for year in range(2018, 2026):
            for course_id, metres in lengths.items():
                reference = daniels.race_time(vdot, metres)
                assert reference is not None
                hills = 1.10 if course_id == "hard-10000" else 1.0
                fade = 1.05 if metres > 40_000 else 1.0
                results.append(
                    Result(
                        race_id=f"{course_id}-{year}",
                        place=person + 1,
                        bib=None,
                        name=f"Runner {person}",
                        club=None,
                        sex="F",
                        sex_place=None,
                        age_band=None,
                        category_place=None,
                        hometown=None,
                        gun_seconds=reference * hills * fade,
                        chip_seconds=None,
                    )
                )
        runners.append(
            Runner(
                runner_id=f"p{person}",
                name=f"Runner {person}",
                hometown=None,
                sex="F",
                results=tuple(results),
                ambiguous=False,
            )
        )
    return races, runners


def test_a_populations_fade_lands_on_the_long_courses_and_not_on_their_peers() -> None:
    """The reason a course factor is only comparable inside its own race length.

    On the real archive this is what makes five ordinary marathons read as hard as Signal
    Hill and the net-downhill Tely read as average. Here the truth is known: the marathons
    are flat, and the five percent is a population that fades, so the factor against a flat
    reference has to pick it up and the factor against the other marathon must not.
    """
    races, runners = _two_lengths()
    history = History.before(date(2026, 1, 1), races, runners)
    fitted = courses.fit(history, races, draws=30)

    marathons = [fitted.courses["mara-a-42195"], fitted.courses["mara-b-42195"]]
    flat_ten = fitted.courses["easy-10000"]
    # Two flat roads, one at each length. The effects are centred, so what the artefact moves
    # is the gap between them, and it is the whole of the five percent that was planted.
    for measured in marathons:
        assert (1 + measured.factor) / (1 + flat_ten.factor) == pytest.approx(1.05, abs=0.005), (
            "a flat marathon reads as harder than a flat 10 km, though neither has a hill"
        )
    for measured in marathons:
        assert measured.peers == 1, "a marathon's peer is the other marathon, not a 10 km"
        assert measured.versus_peers == pytest.approx(0.0, abs=0.005), (
            "against each other two flat marathons are level, which is the truth"
        )
        assert measured.peers_low is not None and measured.peers_high is not None
        # Noiseless twins, so every resample gives the same zero and the interval collapses
        # onto it. It has to contain zero; on real data it has width.
        assert measured.peers_low <= 0.0 <= measured.peers_high

    hard = fitted.courses["hard-10000"]
    assert hard.versus_peers is not None
    assert 1 + hard.versus_peers == pytest.approx(1.10, abs=0.005), (
        "the ten percent that was planted in a road survives the peer comparison"
    )
