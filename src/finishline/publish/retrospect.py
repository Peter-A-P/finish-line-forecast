"""A race that ran while this project was watching, but before it published anything.

WHY
---
The Uniformed Services Run went on 2026-09-13, a day after the first entrant-list snapshot
and three weeks before the first race this project freezes a prediction for. There is a
start list saved from before its gun and an official finish list from after it, and in
between there is what the model would have said. That is the only end-to-end demonstration
this project has until the Turkey Tea on 2026-10-04, and leaving it off the website because
no tag was cut would be hiding the most informative thing here.

⚠️ **This is not a prediction and the page must never call it one.** Nothing was frozen,
hashed or tagged before the gun, so it does not enter the public record and it is not
scored in `scores/`. What it is, exactly: the rows the rolling-origin backtest already
produced for this race, which are held out by construction. The model that made them was
fitted on the history strictly before the quarter the race falls in
(`hierarchical.block_start`, three months), so for 2026-09-13 it had seen nothing after
2026-06-30. `backtest.run.check_no_leakage` asserts it at every origin.

⚠️ **Only an event whose road this project had already seen is scored.** The 2026 USR
introduced new marathon and half-marathon routes and its 5 km had never been run before, so
for three of its four events the model was predicting a road with no course factor at all
(`nlaa.SAME_ROUTE`). Publishing a held-out error for those would be reporting the cost of a
missing course as if it were the model's accuracy. They are listed, with the reason, and
not scored. The rule is mechanical rather than a judgement made race by race: an event is
scored when its course has an edition before it, and is not when it does not.

⚠️ **Every finisher is in the table, and the only place printed is the place in the race
that was run.** A finisher the archive cannot tell apart from another runner of the same name
has no prediction, and is listed with the resolver's reason where the prediction would be
rather than dropped. An earlier version dropped them and ranked the rest among themselves,
which printed the man who finished second as "actual place 1" because the winner was one of
the ones it had dropped: a second, invented race beside the real one (PLAN.md 13 item 38).

⚠️ **Showing them and scoring them are different jobs, and one column may not do both.** The
place error is measured over the field the model was actually given, the predicted runners
ranked among themselves by prediction against the same runners ranked among themselves by
result, so nothing about the unidentified ten reaches it. Mapping those ranks back onto real
places was tried and is wrong: the real places of the predicted runners have gaps in them
where the others finished, so the same ordering scores worse the more people the resolver had
to refuse. That charged the model 1.1 places for a fault it has no part in. What the table
prints per runner is therefore the difference and never an absolute predicted place, because
an absolute place on that scale would be a claim about the race.

⚠️ **The ordering here is a rank, not a simulation.** For a live race the published place
comes from drawing the whole field thousands of times (`placing/simulate.py`), which needs a
posterior; the backtest saved scored rows and let its posteriors go. So the order behind
the place error is the order of the predicted times, with no range on it, and the page says
so rather than letting it look like the same object.

⚠️ **`out_by` is the finish minus the prediction, which is the opposite sign to everything
else in this repository.** `score.Scored.error` and the bias tables are predicted minus
actual, because a model's bias is naturally read on the model. A reader looking at one
runner's row is not reading a bias; they are reading a runner who took two minutes longer
than they were told, and they expect +2:00. The flip lives here, at the last step before the
page, so nothing measured is touched by it.

⚠️ **The gender and age group are from another race's page, and are dated.** The club's
finish list for this race prints neither, nor a hometown (`ingest/ane.py`): a name, a place
and a time is all of it. So the two columns carry what the association's own results last
printed for that runner before this race, which is public on nlaa.ca under that runner's
name, and they carry the race and date they were printed at. `printed_category` refuses a
band the runner has certainly grown out of since, and prints nothing rather than a guess for
a finisher the resolver could not identify, because an age band is a claim about a person and
a row with no prediction is a row where this project does not know which person it is.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from finishline.backtest import score
from finishline.conformal import split
from finishline.identity.normalise import name_key
from finishline.identity.resolve import Runner, age_range, birth_window
from finishline.ingest import nlaa
from finishline.ingest.entrants import Entrant
from finishline.publish import showcase
from finishline.schema import Race, Result
from finishline.store import Dataset


@dataclass(frozen=True, slots=True)
class Attendance:
    """The start list against the finish list, for one event of one race."""

    listed: int
    finished: int
    found: int
    not_listed: int
    switched: int

    @property
    def not_found(self) -> float | None:
        """The share of listed entrants who did not finish under a name on their list.

        ⚠️ **An upper bound on the no-show rate, not the no-show rate.** It also holds
        everyone who started and did not finish, and everyone whose name the list and the
        results page printed two different ways. Said here because the number is quoted.
        """
        return None if not self.listed else 1.0 - self.found / self.listed


def snapshot_before(directory: Path, prefix: str, when: datetime) -> Path | None:
    """The last snapshot of a list taken before a moment, by the stamp in its filename.

    ⚠️ **Not `entrants.latest_snapshot`.** The scheduled task kept looking at the USR list
    for days after the race, so the latest snapshot of it is a list nobody could have
    predicted from. What a retrospective may use is what was knowable before the gun.
    """
    best: tuple[datetime, Path] | None = None
    for path in sorted(directory.glob(f"{prefix}_*.html")):
        stamp = path.stem.rsplit("_", 1)[-1]
        try:
            taken = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")
        except ValueError:
            try:
                taken = datetime.strptime(stamp, "%Y%m%dT%H%MZ")
            except ValueError:
                continue
        taken = taken.replace(tzinfo=when.tzinfo)
        if taken <= when and (best is None or taken > best[0]):
            best = (taken, path)
    return None if best is None else best[1]


def entered(people: Sequence[Entrant], race: Race) -> list[Entrant]:
    """The entrants on a list who are in this race, by the distance their event names.

    ⚠️ **The list groups a day's entrants by event and the archive files them by distance**,
    and no identifier joins the two. The USR list says "Quidi Vidi Brewery 10k", "Half
    Marathon", "1k Kids Run"; the archive says 10,000 m and 21,097.5 m. So an event label is
    read for its distance with the same parser the results index is read with, and dropped
    by the same rules: the kids' run, the family walk and the marathon relay are not
    individual road races and never join a field here.
    """
    picked = []
    for person in people:
        label = person.event
        if not label or nlaa.why_not_read(label, "") is not None:
            continue
        metres = nlaa.distance_m(label)
        if metres is not None and abs(metres - race.distance_m) < 1.0:
            picked.append(person)
    return picked


def attendance(people: Sequence[Entrant], results: Sequence[Result], race: Race) -> Attendance:
    """Who was listed, who finished, and how far apart the two lists are.

    Matched on the normalised name key within the event, which is all there is: the club's
    finish lists print no sex, no age and no hometown, so there is nothing else to agree on.
    A switch is a finisher who was on another event's list that day, which is a runner who
    changed distance rather than a late entry, and the two are counted apart.
    """
    mine = {name_key(person.name) for person in entered(people, race)}
    everyone = {name_key(person.name) for person in people if person.event}
    finished = {name_key(result.name) for result in results if result.finished}
    not_listed = finished - mine
    return Attendance(
        listed=len(mine),
        finished=len(finished),
        found=len(mine & finished),
        not_listed=len(not_listed),
        switched=len(not_listed & everyone),
    )


def still_possible(band: str, printed_on: date, when: date) -> bool:
    """Whether a runner printed under this band then could still be in it now.

    The band fixes a window of birth years (`resolve.birth_window`, which is the same
    function the resolver uses to decide whether two results can be one person). Carry that
    window forward to this race and it gives the ages the runner can be on the day; the band
    is still printable if those ages overlap it. A 20-29 printed in 2016 puts the runner at
    30 to 40 in 2026 and is refused. A 45-49 printed three months ago is kept, because a
    runner who has just turned 50 is still inside the window that band allowed.
    """
    ages = age_range(band)
    window = birth_window(band, printed_on)
    if ages is None or window is None:
        return False
    return when.year - window[1] <= ages[1] and ages[0] <= when.year - window[0]


def printed_category(data: Dataset, runner: Runner | None, when: date) -> dict[str, Any]:
    """The gender and age group the association's results printed for this runner.

    ⚠️ **Nothing here is inferred and nothing here is from this race.** The club's list for
    this race prints no sex and no age at all, so these come from that runner's other results
    on nlaa.ca, where they are public under the same name. Only results before this race
    count: a description taken from a later page would be true and still wrong to put beside
    a held-out prediction, because the whole claim of this page is that nothing after the
    race was used. The band is the one printed most recently, with the race it was printed
    at, and it is dropped rather than aged forward when `still_possible` refuses it.

    A runner the resolver would not commit to gets nothing. Their row has no prediction
    precisely because the archive holds more than one person it could be, and printing one of
    those people's age beside the other's finish would be inventing the thing the row is
    there to say is unknown.
    """
    blank: dict[str, Any] = {"sex": None, "age": None, "age_from": None}
    if runner is None or runner.ambiguous:
        return blank
    dated = [
        (data.races[result.race_id].date, result)
        for result in runner.results
        if result.age_band
        and result.race_id in data.races
        and data.races[result.race_id].date < when
    ]
    found = {"sex": runner.sex, "age": None, "age_from": None}
    if not dated:
        return found
    printed_on, latest = max(dated, key=lambda pair: pair[0])
    band = latest.age_band or ""
    if not still_possible(band, printed_on, when):
        return found
    source = data.races[latest.race_id]
    found["age"] = band
    found["age_from"] = f"{source.name}, {printed_on.isoformat()}"
    return found


def scorable(data: Dataset, race_id: str) -> bool:
    """Whether this race's course had been run before, so the model knew the road.

    The bar the module docstring sets, in one line. A course with no earlier edition has no
    course factor, and an error measured on it is mostly the cost of that.
    """
    race = data.races[race_id]
    return any(
        other.course_id == race.course_id and other.date < race.date
        for other in data.races.values()
    )


def _bands(
    rows: Sequence[tuple[float, float, int]], field: Sequence[float]
) -> list[dict[str, Any]]:
    """The error split by where a runner finished in their own field.

    The same three bands the rest of the site uses (`showcase.SPEED_GROUPS`), so a reader
    moving between this race and the archive-wide table is not changing subject. Reported in
    minutes and as a share of a finish time, because a five-minute miss is not the same claim
    for somebody racing the front as for somebody out there twice as long.
    """
    out = []
    for key, label, note, low, high in showcase.SPEED_GROUPS:
        picked = [
            (error, actual, places)
            for error, actual, places in rows
            if low <= showcase._share_of_field(actual, field) < high
        ]
        if not picked:
            continue
        out.append({
            "key": key,
            "label": label,
            "note": note,
            "runners": len(picked),
            "mae_min": round(statistics.mean(error for error, _, _ in picked) / 60, 2),
            "mape": round(statistics.mean(error / actual for error, actual, _ in picked), 4),
            "places_out": round(statistics.mean(places for _, _, places in picked), 1),
        })
    return out


def race(
    data: Dataset,
    scored: Sequence[score.Scored],
    intervals: Sequence[split.Interval],
    race_id: str,
    people: Sequence[Entrant],
    *,
    model: str = showcase.MODEL,
    baseline: str = showcase.BASELINE,
) -> dict[str, Any] | None:
    """Everything the website says about one already-run race, names included.

    The runner rows carry a name because the finish list carries a name; nothing else about
    a person is here that the finish list did not print. They go to a file the host serves
    `noindex` and `robots.txt` disallows, like the prediction files.
    """
    target = data.races.get(race_id)
    if target is None:
        return None
    rows = {
        row.runner_id: row
        for row in scored
        if row.race_id == race_id and row.model == model and row.predicted is not None
    }
    if not rows:
        return None
    others = {
        row.runner_id: row
        for row in scored
        if row.race_id == race_id and row.model == baseline and row.predicted is not None
    }
    bounds = {
        item.row.runner_id: item
        for item in intervals
        if item.row.race_id == race_id and item.adjusted
    }
    finishers = sorted(
        (
            result
            for result in data.results
            if result.race_id == race_id and result.finished and result.seconds
        ),
        key=lambda result: result.place or 0,
    )
    # Every finisher's runner, the ones the resolver refused included, because those are the
    # rows this table has to carry a reason for rather than quietly leave out.
    owner: dict[tuple[str, int | None], Runner] = {
        (result.name, result.place): runner
        for runner in data.runners
        for result in runner.results
        if result.race_id == race_id
    }

    def runner_of(result: Result) -> Runner | None:
        return owner.get((result.name, result.place))

    def prediction_for(result: Result) -> score.Scored | None:
        found = runner_of(result)
        return None if found is None else rows.get(found.runner_id)

    def predicted_seconds(result: Result) -> float:
        row = prediction_for(result)
        return float(row.predicted or 0.0) if row is not None else 0.0

    # ⚠️ **The place shown is the place in the race that was run, and the place error is
    # measured without the runners who have no prediction.** Those are two different jobs and
    # an earlier version tried to make one column do both, which printed the man who finished
    # second as "actual place 1" because the winner could not be identified (PLAN 13 item 38).
    #
    # So: the table prints the real place and nothing else absolute, and "places out" is the
    # model's ordering error over the field it was actually given, the predicted runners
    # ranked among themselves by prediction against the same runners ranked among themselves
    # by result. **Nothing about the ten reaches this number.** Mapping those ranks back onto
    # real places was tried and is wrong: the real places of the predicted runners have gaps
    # in them where the unidentified runners finished, so the same ordering scores worse the
    # more people the resolver had to refuse, and that is not the model's doing. It cost 1.1
    # places of accuracy to a fault the model has no part in.
    predicted_only = [result for result in finishers if prediction_for(result) is not None]
    by_prediction = sorted(predicted_only, key=predicted_seconds)
    by_result = sorted(predicted_only, key=lambda result: float(result.seconds or 0.0))
    predicted_rank = {result.place: i + 1 for i, result in enumerate(by_prediction)}
    actual_rank = {result.place: i + 1 for i, result in enumerate(by_result)}

    runners: list[dict[str, Any]] = []
    ranged: list[tuple[float, int, int]] = []
    for result in finishers:
        actual = float(result.seconds or 0.0)
        row = prediction_for(result)
        if row is None:
            found = runner_of(result)
            runners.append({
                "name": result.name,
                "place": result.place,
                "actual": round(actual, 1),
                "prior": None,
                "seconds": None,
                "out_by": None,
                "i80": None,
                "places_out": None,
                **printed_category(data, found, target.date),
                # Why there is no prediction, in the resolver's own words. It is always the
                # same kind of reason: the archive holds more than one runner this result
                # could belong to, and nothing on the page says which.
                "excluded": (found.reason if found is not None else "not resolved to a runner"),
            })
            continue
        held = bounds.get(row.runner_id)
        predicted = float(row.predicted or 0.0)
        # An open-ended upper edge is no range at all, and rounding `inf` raises. The
        # conformal step can leave one on a stratum with too few earlier races.
        edges: list[int] | None = None
        low = None if held is None else held.low
        high = None if held is None else held.high
        if low is not None and high is not None and math.isfinite(low) and math.isfinite(high):
            edges = [round(low), round(high)]
            ranged.append((actual, edges[0], edges[1]))
        runners.append({
            "name": result.name,
            "place": result.place,
            "prior": row.depth,
            "seconds": round(predicted, 1),
            "actual": round(actual, 1),
            # The finish minus the prediction, in that order: a runner who took two minutes
            # longer than the model called reads +2:00. Written the other way round it read
            # -2:00 for the same race, which is the sign every reader expects on the
            # difference of two times and the opposite of what it meant.
            "out_by": round(actual - predicted, 1),
            "i80": edges,
            # How far out the model had this runner in the order of the field it was given.
            # Positive means it expected them further back than they finished. Not an
            # absolute place, and deliberately so: an absolute place on this scale would be a
            # claim about the race, and the race is the `place` above.
            "places_out": predicted_rank[result.place] - actual_rank[result.place],
            "excluded": None,
            **printed_category(data, runner_of(result), target.date),
        })

    field = showcase.field_times(data).get(race_id, ())
    errors = [
        (
            abs(float(item["seconds"]) - float(item["actual"])),
            float(item["actual"]),
            abs(int(item["places_out"])),
        )
        for item in runners
        if item["excluded"] is None
    ]
    both = [runner_id for runner_id in rows if runner_id in others]
    held_count = sum(1 for actual, low, high in ranged if low <= actual <= high)

    return {
        "race_id": race_id,
        "name": target.name,
        "date": target.date.isoformat(),
        "course_id": target.course_id,
        "distance_m": target.distance_m,
        "model": model,
        "baseline": baseline,
        "finishers": len(finishers),
        "scored": len(rows),
        "ambiguous": len(finishers) - len(rows),
        "mae_min": round(statistics.mean(error for error, _, _ in errors) / 60, 2),
        "median_error_min": round(statistics.median(error for error, _, _ in errors) / 60, 2),
        "places_out": round(statistics.mean(places for _, _, places in errors), 1),
        "median_places_out": round(statistics.median(places for _, _, places in errors), 1),
        "coverage80": None if not ranged else round(held_count / len(ranged), 4),
        # How much of the borrowed description there is, so the page can say it rather than
        # let a column of blanks look like a bug.
        "with_sex": sum(1 for item in runners if item["sex"]),
        "with_age": sum(1 for item in runners if item["age"]),
        "paired": len(both),
        "paired_model_min": None if not both else round(
            statistics.mean(
                abs(float(rows[key].predicted or 0.0) - float(rows[key].actual)) for key in both
            ) / 60, 2
        ),
        "paired_baseline_min": None if not both else round(
            statistics.mean(
                abs(float(others[key].predicted or 0.0) - float(others[key].actual))
                for key in both
            ) / 60, 2
        ),
        "bands": _bands(errors, field),
        "attendance": _attendance_record(people, finishers, target),
        "runners": runners,
    }


def _attendance_record(
    people: Sequence[Entrant], finishers: Sequence[Result], target: Race
) -> dict[str, Any] | None:
    if not people:
        return None
    seen = attendance(people, finishers, target)
    return {
        "listed": seen.listed,
        "finished": seen.finished,
        "found": seen.found,
        "not_found": None if seen.not_found is None else round(seen.not_found, 4),
        "not_listed": seen.not_listed,
        "switched": seen.switched,
    }


def unscored(data: Dataset, race_ids: Sequence[str]) -> list[dict[str, Any]]:
    """The events of the same day that ran on a road this project had never seen.

    Listed rather than dropped. A reader who is told the 10 km was 4.7 minutes out and not
    told that the marathon beside it ran on a road new that year has been told half of it.
    """
    return [
        {
            "race_id": race_id,
            "name": data.races[race_id].name,
            "distance_m": data.races[race_id].distance_m,
            "course_id": data.races[race_id].course_id,
            "finishers": sum(
                1
                for result in data.results
                if result.race_id == race_id and result.finished
            ),
        }
        for race_id in race_ids
        if race_id in data.races
    ]


def events_on(data: Dataset, when: date, family: str) -> list[str]:
    """Every race in the archive that this calendar entry turned into, soonest distance first.

    A calendar entry is a day, not a race (`ingest.calendar`), so this is where one becomes
    several. Matched on the day and on the course family the entry's name gave, which is the
    same alias table the results index is read with, so a sponsor change cannot break it.
    """
    return sorted(
        (
            race_id
            for race_id, race in data.races.items()
            if race.date == when and race.course_id.startswith(f"{family}-")
        ),
        key=lambda race_id: data.races[race_id].distance_m,
    )


def list_prefix(family: str, when: date, known: Iterable[str]) -> str | None:
    """The entrant-list prefix a closed race's snapshots were filed under, if there is one.

    The snapshot prefixes are named by hand in `ingest.entrants.LISTS` and the calendar knows
    only a course family, so the two are joined by the convention the prefixes follow:
    the family and the year. Returns None rather than guessing at a near miss, because
    attaching one race's start list to another race would invent a no-show rate.
    """
    wanted = f"{family}-{when.year}"
    return wanted if wanted in set(known) else None


__all__ = [
    "Attendance",
    "attendance",
    "entered",
    "events_on",
    "list_prefix",
    "printed_category",
    "race",
    "scorable",
    "snapshot_before",
    "still_possible",
    "unscored",
]
