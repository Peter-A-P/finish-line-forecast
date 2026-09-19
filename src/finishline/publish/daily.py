"""A prediction a day for the last week, each runner published once (Peter, 2026-09-19).

HOW IT RUNS
-----------
From seven days before the gun, `finishline freeze <race> --daily` publishes a file a day,
`predictions/<race>/daily-<date>.json`, holding only the entrants who were on that morning's
list and in no earlier daily file. The day before, `finishline freeze <race>` writes the final
file with the whole field and its places. Each file is committed and tagged the day it is
written, so each runner's prediction provably existed from the day it was first published.

WHY A RUNNER'S TIME NEVER CHANGES ONCE PUBLISHED
------------------------------------------------
Three things are held fixed, so the same entrant gets the same numbers on any day:

- **One fit.** The model is sampled on the first day and saved (`save_posterior`); every later
  day, and the final file, loads it and refuses if the archive has changed underneath it.
- **One stream of random numbers per runner**, seeded by the race and the entrant
  (`runner_rng`), not by their position on a list that grows.
What does change from day to day is the weather forecast. A daily line is predicted with the
forecast of the morning it was published, at that lead, with the error measured for that
lead (`forecast_error_for`), which a week out is large. **The final file recomputes everyone
with the day-before forecast** (Peter, 2026-09-19: a week-old forecast is of poor value by
then) and names the daily file each runner first appeared in (`first_published`). Since the
fit and the random numbers are the same, the weather is the only thing that moves a runner's
time between their daily line and their final one, and both are tagged.
"""

from __future__ import annotations

import json
import pickle
import tomllib
import zlib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from finishline.identity.normalise import name_key
from finishline.ingest.entrants import Entrant
from finishline.models import weather
from finishline.models.hierarchical import Posterior

# How far ahead the daily files start.
FIRST_LEAD_DAYS = 7

DAILY_PREFIX = "daily-"


def entrant_key(entrant: Entrant) -> str:
    """Who an entrant is across days: their name as a key.

    Not their position on the list, which moves as people enter, and not an archive id,
    which a newcomer does not have. Not their sex either, which the published file does not
    print. Two entrants of one name are told apart by order (`split`).
    """
    return name_key(entrant.name)


def runner_rng(seed: int, key: str) -> np.random.Generator:
    """The random numbers for one entrant at one race, the same on every day."""
    return np.random.default_rng([seed, zlib.crc32(key.encode("utf-8"))])


def daily_path(directory: Path, race_id: str, day: date) -> Path:
    return directory / race_id / f"{DAILY_PREFIX}{day.isoformat()}.json"


Published = dict[str, list[tuple[str, dict[str, Any]]]]


def published(directory: Path, race_id: str) -> Published:
    """Every line already in a daily file for this race, by name key, earliest file first."""
    found: Published = {}
    for path in sorted((directory / race_id).glob(f"{DAILY_PREFIX}*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for line in doc.get("runners", []):
            found.setdefault(name_key(str(line["name"])), []).append((path.name, line))
    return found


def split(
    keys: list[str], already: Published
) -> tuple[list[int], dict[int, tuple[str, dict[str, Any]]], list[str]]:
    """Which of today's entrants are new, and which carry an earlier line.

    `keys` are today's entrants' name keys in list order. Of k entrants sharing a name, the
    first as many as were published before are carried and the rest are new. Returns the
    positions that are new, the carried line for each other position, and a stream key per
    position (the name key and which of its name it is), for `runner_rng`.
    """
    seen: dict[str, int] = {}
    new: list[int] = []
    carried: dict[int, tuple[str, dict[str, Any]]] = {}
    streams: list[str] = []
    for position, key in enumerate(keys):
        index = seen.get(key, 0)
        seen[key] = index + 1
        streams.append(f"{key}#{index}")
        earlier = already.get(key, [])
        if index < len(earlier):
            carried[position] = earlier[index]
        else:
            new.append(position)
    return new, carried, streams


def posterior_path(cache: Path, race_id: str) -> Path:
    return cache / race_id / "posterior.pkl"


def save_posterior(path: Path, posterior: Posterior, meta: Mapping[str, Any]) -> None:
    """Keep the fit for the rest of the week. Local and gitignored: it is every runner's draws."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump({"meta": dict(meta), "posterior": posterior}, handle)


def load_posterior(path: Path, expected: Mapping[str, Any]) -> Posterior | None:
    """The saved fit, or None when there is none.

    ⚠️ **Refuses a fit made on a different archive.** If a crawl has added a race since the
    first daily file, the saved fit no longer describes what the model would say, and the
    week's files would stop being one prediction. That is raised rather than refitted.
    """
    if not path.exists():
        return None
    with path.open("rb") as handle:
        record = pickle.load(handle)  # our own file, written by save_posterior
    meta = record["meta"]
    for key, value in expected.items():
        if meta.get(key) != value:
            raise ValueError(
                f"the saved fit for this race has {key} = {meta.get(key)!r}, not {value!r}; "
                "the archive changed during the prediction week"
            )
    posterior: Posterior = record["posterior"]
    return posterior


def forecast_error_for(path: Path, fallback: Path, lead_days: int) -> weather.ForecastError:
    """The forecast error measured at this lead, or the day-ahead one where none was.

    `path` holds one table per lead, `[1]` to `[7]`, written by `finishline forecast-error`.
    A lead beyond the longest measured takes the longest, never a shorter one: a forecast
    does not get better for being further away.
    """
    if path.exists():
        tables = tomllib.loads(path.read_text(encoding="utf-8"))
        leads = sorted(int(lead) for lead in tables)
        if leads:
            chosen = max((lead for lead in leads if lead <= max(lead_days, 1)), default=leads[0])
            if lead_days > leads[-1]:
                chosen = leads[-1]
            return weather.ForecastError(**tables[str(chosen)])
    return weather.load(fallback)
