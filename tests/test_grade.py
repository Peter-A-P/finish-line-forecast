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


def test_run_to_remembers_hills_are_not_its_course_factor() -> None:
    """The check can fail, and here it does: the measurement is not the hills.

    1,042 finishes put Run to Remember at +1.64 percent [+1.17, +2.10]. The segment stream
    gives 91 m up and 91 m down over 11 km of rail trail with nothing steeper than 2.4 percent
    over 700 m anywhere on it, and at that grade they cost half a point, under half the fast
    end of that interval. The arithmetic will still solve for a grade; it asks for more than
    three times the steepest stretch the course has, so the grade is not a rail trail.

    ⚠️ **The numbers moved on 2026-09-25 and the conclusion did not**, which is the useful
    part. The organisers' chart gave 56 m each way and put the solved grade at 12.7 percent;
    the measured stream gives 91 and 7.7 percent. Both are miles off a rail bed.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["run-to-remember-11000"]
    assert "bearing_deg" not in record
    shape = {
        "distance_m": record["distance_m"],
        "climb_m": record["climb_m"],
        "drop_m": record["drop_m"],
    }
    steepest = 0.024  # the steepest 700 m the profile labels
    assert grade.penalty(**shape, grade=steepest) < 0.0117 * 0.5
    solved = grade.implied_grade(**shape, factor=0.0164)
    assert solved is not None
    assert solved > 3 * steepest, f"{solved:.1%} would be a grade this trail could have"

    # And the reading it replaced reached the same verdict from different totals.
    older = {
        **shape,
        "climb_m": record["independent_climb_m"],
        "drop_m": record["independent_drop_m"],
    }
    was = grade.implied_grade(**older, factor=0.0164)
    assert was is not None and was > solved


def _leg(start: list[float], end: list[float]) -> complex:
    """One straight leg as a vector in metres, east as real and north as imaginary.

    Flat-earth over a few hundred metres, which is centimetres from the great circle here.
    """
    metres_per_degree = 6_371_008.8 * math.pi / 180
    north = (end[0] - start[0]) * metres_per_degree
    east = (end[1] - start[1]) * metres_per_degree * math.cos(math.radians(start[0]))
    return complex(east, north)


def test_cape_to_cabots_bearing_is_its_start_and_finish_and_covers_a_third_of_it() -> None:
    """The stored bearing is computed from the two ends, and says how much of the race it is.

    The legs of any route sum to the displacement from start to finish, so displacement over
    distance is the share of the course that has a net direction: 7.4 km of 20 km here.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["cape-to-cabot-20000"]
    net = _leg(record["start"], record["finish"])
    bearing = math.degrees(math.atan2(net.real, net.imag)) % 360
    assert bearing == pytest.approx(record["bearing_deg"], abs=1)
    assert abs(net) / record["distance_m"] == pytest.approx(0.37, abs=0.01)


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


# A course factor measured against Daniels' flat reference at the course's own distance
# carries this population's departure from that curve, and the same factor measured against
# the courses of the same race length does not (PLAN.md 13 item 36). Until 2026-09-25 there
# was no way to say which of the two the hills agreed with, because four courses had an
# elevation figure and none of them had the grades. These are the ten that do now: the
# measured pair from `finishline courses` on the 2026-09-25 archive, and the grade window
# each profile labels. PLAN.md 13 item 43.
#
# course_id, steepest labelled grade either way, (factor, low, high), (peers, low, high)
PROFILED: tuple[
    tuple[str, float, tuple[float, float, float], tuple[float, float, float] | None], ...
] = (
    ("five-and-dime-5000", 0.028, (-0.0299, -0.0359, -0.0237), (-0.0178, -0.0282, -0.0076)),
    ("mundy-pond-5000", 0.016, (-0.0180, -0.0211, -0.0153), (-0.0047, -0.0136, 0.0045)),
    ("flat-out-5000", 0.035, (-0.0093, -0.0127, -0.0060), (0.0048, -0.0050, 0.0133)),
    ("mews-memorial-8000", 0.029, (-0.0532, -0.0552, -0.0512), (-0.0519, -0.0583, -0.0460)),
    ("five-and-dime-10000", 0.031, (-0.0083, -0.0196, -0.0007), (0.0012, -0.0109, 0.0103)),
    ("harbour-front-10000", 0.023, (-0.0177, -0.0209, -0.0141), (-0.0088, -0.0144, -0.0026)),
    ("turkey-tea-10000", 0.028, (-0.0512, -0.0540, -0.0488), (-0.0451, -0.0501, -0.0393)),
    ("run-to-remember-11000", 0.024, (0.0164, 0.0117, 0.0210), None),
    ("tely-10-16093", 0.046, (0.0024, 0.0011, 0.0037), (-0.0414, -0.0498, -0.0342)),
    ("cape-to-cabot-20000", 0.087, (0.0924, 0.0899, 0.0948), None),
    ("huffin-puffin-42195", 0.015, (0.0962, 0.0831, 0.1078), (0.0133, -0.0045, 0.0308)),
)


def _physics(course_id: str, steepest: float) -> tuple[float, float]:
    """What the hills are worth, from the gentlest grade the totals allow to the steepest
    grade the profile labels, which is an upper bound on the typical graded-section grade."""
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))[course_id]
    shape = {
        "distance_m": float(record["distance_m"]),
        "climb_m": float(record["climb_m"]),
        "drop_m": float(record["drop_m"]),
    }
    gentlest = (shape["climb_m"] + shape["drop_m"]) / shape["distance_m"]
    low = grade.penalty(**shape, grade=gentlest)
    high = grade.penalty(**shape, grade=max(gentlest, steepest))
    return low, high


def _overlaps(band: tuple[float, float], interval: tuple[float, float, float]) -> bool:
    return not (band[1] < interval[1] or band[0] > interval[2])


def test_the_profiles_side_with_the_own_length_factor_and_never_with_the_flat_one() -> None:
    """The elevation cross-check was built to check the measurement. It ended up saying
    which measurement to read, and this test is the claim in PLAN.md 13 item 43.

    For each course with a profile and at least one other course of its race length: does
    the Minetti penalty the profile implies fall inside the factor measured against Daniels'
    flat reference, inside the factor measured against the courses of its own length, inside
    both (the intervals are too wide to separate them) or inside neither?
    """
    verdicts: dict[str, list[str]] = {"flat": [], "peers": [], "both": [], "neither": []}
    for course_id, steepest, flat, peers in PROFILED:
        if peers is None:
            continue
        band = _physics(course_id, steepest)
        with_flat = _overlaps(band, flat)
        with_peers = _overlaps(band, peers)
        key = (
            "both"
            if with_flat and with_peers
            else "flat"
            if with_flat
            else ("peers" if with_peers else "neither")
        )
        verdicts[key].append(course_id)

    assert verdicts["flat"] == [], (
        "no course's hills should agree with the flat reference alone; these do: "
        f"{verdicts['flat']}"
    )
    assert len(verdicts["peers"]) == 5, verdicts["peers"]
    # Flat Out and the Five and Dime 10 km have intervals wide enough to hold either answer.
    assert set(verdicts["both"]) == {"flat-out-5000", "five-and-dime-10000"}, verdicts["both"]
    # The two rolling courses with no net drop, where the model charges for undulation and
    # the results do not pay it. Reported, not averaged away.
    assert set(verdicts["neither"]) == {"mundy-pond-5000", "harbour-front-10000"}


def test_the_two_misses_are_the_rolling_courses_with_no_net_drop() -> None:
    """The exceptions are reported, not rounded away, and this is how far off they are.

    Mundy Pond and Harbour Front climb almost exactly what they descend, +3 m over 5 km and
    +7 m over 10 km, so the grade model charges them for the undulation: a metre climbed
    takes more than the same metre descended gives back. Both measure faster than that
    against the other courses of their length, one by a tenth of a point and one by nine.
    """
    for course_id, steepest, peers_high, margin in (
        ("mundy-pond-5000", 0.016, 0.0045, 0.002),
        ("harbour-front-10000", 0.023, -0.0026, 0.010),
    ):
        low, _high = _physics(course_id, steepest)
        assert low > 0, f"{course_id}: a rolling course with no net drop costs time"
        assert 0 < low - peers_high < margin, f"{course_id}: {low:.4f} against {peers_high:.4f}"


def test_mews_is_faster_than_its_net_descent_can_explain() -> None:
    """The strongest form of the check, because it needs no reading of the chart at all.

    The profile labels 88 m at the start and 14 m at the finish. A course that shed those
    74 m with no climb anywhere, spread as gently as 8 km allows, is the fastest a course of
    this shape can be, and 4,893 finishes say this one is faster than that.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["mews-memorial-8000"]
    net = record["drop_m"] - record["climb_m"]
    assert net == pytest.approx(74, abs=1), "the labelled start and finish, 88 m and 14 m"
    fastest_possible = grade.penalty(
        distance_m=record["distance_m"],
        climb_m=0.0,
        drop_m=net,
        grade=net / record["distance_m"],
    )
    assert fastest_possible == pytest.approx(-0.049, abs=0.001)
    assert fastest_possible > -0.0512, "the whole measured interval is past the bound"


def test_the_marathon_is_flat_and_measures_nine_points_hard() -> None:
    """The clearest case in the archive that the flat-reference factor is not the road.

    273 m up and 270 m down over 42 km, in a 59 m band, with no 2.6 km window steeper than
    1.5 percent. The course reads +9.6 percent against Daniels' reference at the marathon
    and +1.3 percent against the four other marathons.
    """
    low, high = _physics("huffin-puffin-42195", 0.015)
    assert high < 0.004, f"{high:.4f}: these hills are worth a quarter of a point"
    assert _overlaps((low, high), (0.0133, -0.0045, 0.0308)), "the own-length figure holds it"
    assert not _overlaps((low, high), (0.0962, 0.0831, 0.1078)), "the flat one misses by nine"


def test_the_telys_hills_say_it_is_fast_and_the_flat_reference_says_it_is_not() -> None:
    """The widest gap here between the two ways of measuring one course, on the archive's
    best-measured course: 25,664 finishes over 11 editions.

    A course that drops 124 m in 16 km does not cost a runner time. The factor against the
    flat reference says +0.2 percent, and the factor against the other 10 mile course says
    -4.1 percent. The hills, read off the profile, say between -3.0 and -3.7.
    """
    low, high = _physics("tely-10-16093", 0.046)
    assert high < 0, "the hills cannot make this course slow"
    assert _overlaps((low, high), (-0.0414, -0.0498, -0.0342))
    assert not _overlaps((low, high), (0.0024, 0.0011, 0.0037))


def test_cape_to_cabot_needs_a_steeper_grade_than_any_kilometre_of_it_has() -> None:
    """The check that passed on the published totals is weaker on the measured grades.

    The published 550 m against 450 m solve at a 10.3 percent average, and the race's page
    says "more than 10 per cent in some parts", which is how the two were reconciled. The
    profile's own 508 m and 400 m need 11.1 percent, and no 1.3 km of the course is steeper
    than 8.7. Both can be true, because a 1.3 km window is a smoothing; what cannot be said
    any more is that the physics and the results land on the same number.
    """
    record = tomllib.loads(COURSES.read_text(encoding="utf-8"))["cape-to-cabot-20000"]
    solved = grade.implied_grade(
        distance_m=record["distance_m"],
        climb_m=record["independent_climb_m"],
        drop_m=record["independent_drop_m"],
        factor=0.0924,
    )
    assert solved is not None
    assert solved == pytest.approx(0.111, abs=0.003)
    assert solved > 0.087, "steeper than the steepest 1.3 km the profile labels"


def test_every_profiled_course_states_where_its_totals_came_from() -> None:
    """A second figure is only worth keeping if the file says what produced it."""
    loaded = tomllib.loads(COURSES.read_text(encoding="utf-8"))
    for course_id, _steepest, _flat, _peers in PROFILED:
        record = loaded[course_id]
        assert record["climb_m"] and record["drop_m"], course_id
        assert record.get("source"), course_id
        if "independent_climb_m" in record:
            assert record.get("independent_source"), course_id
            assert "independent_drop_m" in record, (
                f"{course_id}: an ascent total with no drop beside it cannot be read "
                "through the grade model"
            )


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
