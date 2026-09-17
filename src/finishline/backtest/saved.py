"""Scored backtest rows kept on disk, so the tables do not wait on a sampler.

The baselines score every origin in seconds. The hierarchical model takes a sampling run per
block, which is hours for the whole backtest, and `finishline report` should not repeat that
to rewrite a table. So the model's scored rows are saved once and read back.

⚠️ **A saved row is only reused when nothing that produced it has changed.** The key hashes
the model's settings, the dataset (every race id and every finish time), and the source of
the model module itself. Editing the model, re-reading a page, or changing the draws all
change the key, and a stale file is then ignored rather than published. A cache that could
serve last week's model under this week's name is how a table ends up describing code that
no longer exists.

The files live under `data/cache/`, which is gitignored: each row names a runner id and a
race, which is derived personal data like everything else in the cache.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from finishline.backtest.score import Scored
from finishline.schema import Race, Result


def dataset_fingerprint(races: Mapping[str, Race], results: Iterable[Result]) -> str:
    """A hash that moves if any race or any finish time moves."""
    digest = hashlib.sha256()
    for race_id in sorted(races):
        race = races[race_id]
        digest.update(f"{race_id}|{race.date}|{race.distance_m}|{race.course_id}\n".encode())
    for line in sorted(
        f"{result.race_id}|{result.name}|{result.seconds}" for result in results
    ):
        digest.update(line.encode())
    return digest.hexdigest()


def key(parts: Mapping[str, object], sources: Sequence[Path]) -> str:
    """The identity of a backtest run: its settings, and the code that ran it.

    ⚠️ **Line endings are normalised before hashing.** On Windows git checks sources out with
    CRLF and an editor may save them with LF; the code is the same either way, and an hours-long
    saved run should not go stale because a checkout touched the file.
    """
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode())
    for source in sources:
        digest.update(source.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def save(path: Path, run_key: str, rows: Sequence[Scored]) -> None:
    """Write the rows with the key as the first line, replacing whatever was there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"key": run_key, "rows": len(rows)}) + "\n")
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "model": row.model,
                        "race_id": row.race_id,
                        "runner_id": row.runner_id,
                        "predicted": row.predicted,
                        "actual": row.actual,
                        "depth": row.depth,
                        "quantiles": list(row.quantiles),
                    }
                )
                + "\n"
            )
    # Written aside and moved into place, so a run killed halfway leaves no file that
    # looks complete.
    temporary.replace(path)


def load(path: Path, run_key: str) -> list[Scored] | None:
    """The saved rows, or None when there are none or they belong to a different run."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if header.get("key") != run_key:
            return None
        rows = [
            Scored(
                model=record["model"],
                race_id=record["race_id"],
                runner_id=record["runner_id"],
                predicted=record["predicted"],
                actual=record["actual"],
                depth=record["depth"],
                quantiles=tuple(record["quantiles"]),
            )
            for record in map(json.loads, handle)
        ]
    if len(rows) != header.get("rows"):
        return None
    return rows
