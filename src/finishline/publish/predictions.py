"""The prediction file: what was predicted, written once, hashed, and never edited (PLAN.md 2.2).

WHY THE BYTES MATTER
--------------------
A prediction counts only if it provably existed before the gun. The proof is a git tag whose
timestamp predates the race, on a commit holding this file, with the file's SHA-256 in the
README and the tag message. That proof is only as good as the hash is stable, so the file is
written in one canonical form: JSON with sorted keys, two-space indentation, times rounded to
a tenth of a second, UTF-8, LF line endings, and a final newline. The same prediction always
produces the same bytes, on any machine, and so the same hash.

WHAT IS IN IT, AND WHAT IS NOT
------------------------------
Per runner: the name as the start list printed it, the hometown as the results last printed
it (none for a newcomer, because the list prints none), how many prior results the prediction
had, the predicted time, the 80 and 90 percent intervals, and the place range. Nothing else
about anyone: no age band, no archive identifier, and never the shirt size the list also
shows (PLAN.md 2.8). Entrants the linker refused are not in the runner list at all; they are
counted in `entrants`.

⚠️ **`freeze` refuses inside 24 hours of the gun, and there is no flag to override it.** A
rule with an override is a rule for whoever is not in a hurry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# How long before the gun a prediction file must exist. CLAUDE.md, PLAN.md 2.2.
MINIMUM_NOTICE = timedelta(hours=24)

LEVELS: tuple[str, ...] = ("80", "90")


class FreezeRefused(RuntimeError):
    """The gun is too close, or already gone, for a prediction to count."""


class SchemaError(ValueError):
    """A prediction file that does not say what a prediction file has to say."""


def check_gun(gun: datetime, now: datetime) -> None:
    """Refuse unless the gun is at least `MINIMUM_NOTICE` away. Both times must be aware.

    Naive datetimes are refused outright: a gun time with no zone is a gun time that is
    right in St. John's and wrong by three and a half hours on a UTC build server, and this
    check would pass in exactly the direction that matters.
    """
    if gun.tzinfo is None or now.tzinfo is None:
        raise FreezeRefused("gun and current time must both carry a time zone")
    if gun - now < MINIMUM_NOTICE:
        remaining = gun - now
        raise FreezeRefused(
            f"the gun is {remaining} away; a prediction must be frozen at least "
            f"{MINIMUM_NOTICE} before it, and this one would not count"
        )


@dataclass(frozen=True, slots=True)
class RunnerPrediction:
    """One published line."""

    name: str
    hometown: str | None
    prior_results: int
    seconds: float
    interval_80: tuple[float, float]
    interval_90: tuple[float, float]
    place: float
    place_low: float
    place_high: float

    def as_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hometown": self.hometown,
            "prior_results": self.prior_results,
            "seconds": _time(self.seconds),
            "interval_80": [_time(self.interval_80[0]), _time(self.interval_80[1])],
            "interval_90": [_time(self.interval_90[0]), _time(self.interval_90[1])],
            "place": {
                "median": round(self.place, 1),
                "low": round(self.place_low, 1),
                "high": round(self.place_high, 1),
            },
        }


def _time(seconds: float) -> float:
    return round(float(seconds), 1)


def document(
    *,
    race: dict[str, Any],
    gun: datetime,
    frozen_at: datetime,
    snapshot: dict[str, Any],
    model: dict[str, Any],
    conditions: dict[str, Any] | None,
    entrants: dict[str, int],
    runners: list[RunnerPrediction],
) -> dict[str, Any]:
    """The whole file as a plain structure, runners ordered by predicted time then name."""
    ordered = sorted(runners, key=lambda runner: (runner.seconds, runner.name))
    return {
        "schema_version": SCHEMA_VERSION,
        "race": race,
        "gun": gun.isoformat(),
        "frozen_at": frozen_at.isoformat(),
        "entrant_snapshot": snapshot,
        "model": model,
        "conditions": conditions,
        "entrants": entrants,
        "runners": [runner.as_record() for runner in ordered],
    }


def to_bytes(doc: dict[str, Any]) -> bytes:
    """The canonical bytes. The hash is of these, and only these."""
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, doc: dict[str, Any]) -> str:
    """Validate, write the canonical bytes, and return their SHA-256.

    ⚠️ **Refuses to overwrite.** A prediction file that exists has possibly been tagged, and
    replacing it is exactly the edit the whole design forbids. A second prediction for the
    same race is a new file name and an explanation, never a replacement.
    """
    problems = validate(doc)
    if problems:
        raise SchemaError("; ".join(problems))
    if path.exists():
        raise FileExistsError(f"{path} exists; a prediction file is never replaced")
    data = to_bytes(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
    return sha256(data)


def verify(path: Path, expected: str) -> bool:
    """Whether the file on disk is byte for byte the one that was hashed."""
    return sha256(path.read_bytes()) == expected


def validate(doc: dict[str, Any]) -> list[str]:
    """Everything wrong with a prediction file, or an empty list.

    A hand-written check rather than a JSON Schema library: the rules that matter here (an
    interval contains its prediction, the 90 contains the 80, a place range is inside the
    field) are relations between fields, which is where schema languages are weakest.
    """
    problems: list[str] = []
    required = {
        "schema_version": int,
        "race": dict,
        "gun": str,
        "frozen_at": str,
        "entrant_snapshot": dict,
        "model": dict,
        "entrants": dict,
        "runners": list,
    }
    for key, kind in required.items():
        if not isinstance(doc.get(key), kind):
            problems.append(f"{key} missing or not a {kind.__name__}")
    if "conditions" not in doc:
        problems.append("conditions missing (null is allowed, absent is not)")
    if problems:
        return problems

    if doc["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version {doc['schema_version']} is not {SCHEMA_VERSION}")
    for key in ("race_id", "name", "date", "distance_m", "course_id"):
        if key not in doc["race"]:
            problems.append(f"race.{key} missing")
    for key in ("name", "commit"):
        if key not in doc["model"]:
            problems.append(f"model.{key} missing")
    try:
        gun = datetime.fromisoformat(doc["gun"])
        frozen = datetime.fromisoformat(doc["frozen_at"])
        if gun.tzinfo is None or frozen.tzinfo is None:
            problems.append("gun and frozen_at must carry a time zone")
        elif gun - frozen < MINIMUM_NOTICE:
            problems.append("frozen less than 24 hours before the gun")
    except ValueError as error:
        problems.append(f"unreadable time: {error}")

    runners = doc["runners"]
    field = len(runners)
    if doc["entrants"].get("predicted") != field:
        problems.append(f"entrants.predicted is not the {field} runners in the file")
    allowed = {
        "name", "hometown", "prior_results", "seconds", "interval_80", "interval_90", "place",
    }
    for position, runner in enumerate(runners):
        where = f"runners[{position}]"
        if not isinstance(runner, dict):
            problems.append(f"{where} is not an object")
            continue
        extra = set(runner) - allowed
        if extra:
            problems.append(f"{where} publishes more than the results do: {sorted(extra)}")
        try:
            seconds = float(runner["seconds"])
            low80, high80 = (float(v) for v in runner["interval_80"])
            low90, high90 = (float(v) for v in runner["interval_90"])
            place = runner["place"]
            median, low, high = (float(place[k]) for k in ("median", "low", "high"))
        except (KeyError, TypeError, ValueError) as error:
            problems.append(f"{where} incomplete: {error}")
            continue
        if not str(runner.get("name", "")).strip():
            problems.append(f"{where} has no name")
        if not low80 <= seconds <= high80:
            problems.append(f"{where} 80% interval does not contain the prediction")
        if not (low90 <= low80 and high80 <= high90):
            problems.append(f"{where} 90% interval does not contain the 80%")
        if not 1 <= low <= median <= high <= field:
            problems.append(f"{where} place range is not inside a field of {field}")
        if not isinstance(runner.get("prior_results"), int) or runner["prior_results"] < 0:
            problems.append(f"{where} prior_results is not a count")
    return problems
