"""The race page before the gun: every prediction published so far, from the files themselves.

Written by `finishline page <race>` into docs/predictions/<race>.md after each daily file and
the final one, and replaced by `finishline score` once the results are in. It is rendered
from the committed prediction files and nothing else, so the page can never say more than
the tagged files do, and each file's hash is printed beside it for anyone who wants to check.

Only what the files publish is shown: the name as the start list printed it, the hometown as
the results last printed it, how many results the prediction had, the time and its intervals,
and, once the final file exists, the place. The final file recomputes every runner with the
day-before forecast, so once it exists its times are the ones shown here; each daily file
keeps its own, and every file is listed with its hash.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

TOP = 20


def clock(seconds: float) -> str:
    """A finish time the way a results page prints one."""
    whole = round(float(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _cell(text: object) -> str:
    return str(text).replace("|", "/")


def before_the_gun(files: Sequence[tuple[str, dict[str, Any], str]]) -> str:
    """The page, from (file name, document, sha256) in the order they were published."""
    if not files:
        raise ValueError("no prediction file to render")
    first = files[0][1]
    race = first["race"]
    final = next((doc for name, doc, _ in files if doc.get("kind") != "daily"), None)
    lines = [
        f"# {race['name']}, {race['date']}",
        "",
        f"Gun {first['gun']}. Every prediction below was committed and tagged in this "
        "repository before the gun, in the file named beside it, and none is ever edited. "
        "The errors are published here after the race.",
        "",
        "| File | Frozen at | Runners | SHA-256 |",
        "|---|---|---:|---|",
    ]
    lines += [
        f"| `{name}` | {doc['frozen_at']} | {len(doc['runners'])} | `{digest}` |"
        for name, doc, digest in files
    ]

    if final is not None:
        lines += top_table(final)

    # Before the final file, every daily line; after it, the final file's lines, which
    # recompute everyone with the day-before forecast, beside the file each first appeared in.
    if final is not None:
        final_name = next(name for name, doc, _ in files if doc is final)
        everyone = [
            (str(runner.get("first_published", final_name)), runner) for runner in final["runners"]
        ]
        heading = "Every runner, as the final file predicts them"
    else:
        everyone = [
            (name, runner)
            for name, doc, _ in files
            if doc.get("kind") == "daily"
            for runner in doc["runners"]
        ]
        heading = "Every runner predicted so far"
    everyone.sort(key=lambda item: (item[1]["seconds"], item[1]["name"]))
    lines += [
        "",
        f"## {heading}, {len(everyone)}",
        "",
        "| Name | Hometown | Prior results | Predicted | 80% interval | First published |",
        "|---|---|---:|---:|---|---|",
    ]
    for name, runner in everyone:
        low, high = runner["interval_80"]
        lines.append(
            f"| {_cell(runner['name'])} | {_cell(runner['hometown'] or '')} "
            f"| {runner['prior_results']} | {clock(runner['seconds'])} "
            f"| {clock(low)} to {clock(high)} | `{name}` |"
        )
    return "\n".join(lines) + "\n"


UNSEEN = "_a runner with no results here_"


def top_table(final: dict[str, Any]) -> list[str]:
    """The predicted top of the field, with the places newcomers are expected to take.

    At the biggest races (`placing.unseen`) the file says how many top places are expected to
    go to runners with no results here, and where. Those rows are shown as placeholders rather
    than given to a named newcomer, because nothing on the list says which newcomer it will be;
    the named runners fill the other rows in order of their median simulated place.
    """
    block = final.get("newcomers") or {}
    likely = set(block.get("likely_places_top_20", []))
    runners = final["runners"]
    named = runners if not block else [r for r in runners if r["prior_results"] > 0]
    named = sorted(named, key=lambda runner: runner["place"]["median"])
    lines = [
        "",
        f"## Predicted top {TOP}",
        "",
        "Places are simulated from the whole field with one shared morning; the range is the "
        "middle 80% of the simulated places.",
    ]
    if block:
        ten, twenty = block["expected_in_top_10"], block["expected_in_top_20"]
        lines += [
            "",
            f"Runners with no results here are expected to take {ten['mean']:.1f} of the top "
            f"10 places (80% range {ten['low']} to {ten['high']}) and {twenty['mean']:.1f} of "
            f"the top 20 ({twenty['low']} to {twenty['high']}), judged from how first-timers "
            f"finished at {block['pool_editions']} earlier editions of this course. Which of "
            "the newcomers on the list they will be, the list does not say, so those places "
            "are shown as placeholders.",
        ]
    lines += [
        "",
        "| Rank | Name | Hometown | Median place | Range | Predicted | 80% interval |",
        "|---:|---|---|---:|---|---:|---|",
    ]
    queue = iter(named)
    for rank in range(1, TOP + 1):
        if rank in likely:
            lines.append(f"| {rank} | {UNSEEN} | | | | | |")
            continue
        runner = next(queue, None)
        if runner is None:
            break
        place = runner["place"]
        low, high = runner["interval_80"]
        lines.append(
            f"| {rank} | {_cell(runner['name'])} | {_cell(runner['hometown'] or '')} "
            f"| {place['median']:.0f} | {place['low']:.0f} to {place['high']:.0f} "
            f"| {clock(runner['seconds'])} | {clock(low)} to {clock(high)} |"
        )
    return lines
