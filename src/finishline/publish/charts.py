"""The README's charts, drawn as SVG from the numbers the report just published.

WHY SVG WRITTEN BY HAND, AND WHY IN THE REPOSITORY
--------------------------------------------------
A README's tables are the checkable record and they stay, but a table of twenty-four
numbers is not how anybody reads a headline. These charts sit above three of those tables
so a reader sees the shape first and can still audit the digits underneath.

Two constraints decide the format. GitHub renders an image from the repository and
peterparker.ca renders the same README through markdown-it with raw HTML escaped, so the
picture has to arrive as a plain Markdown image, not as inline HTML and not as a Mermaid
fence, which one of the two would show as a code block. And the drawing has to be
deterministic: it goes in a commit, so the same numbers must produce the same bytes or
every report rewrites the diff. That rules out a plotting library rasterising fonts and
rules in a few hundred lines of SVG.

⚠️ **A viewer's colour scheme is not ours to guess.** An SVG served as an image gets no
page CSS, and GitHub in dark mode would otherwise put dark text on a dark page, so every
chart paints its own light background and inks itself against that. It is the one place in
this project where a colour is hard-coded rather than themed.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

WIDTH = 880
"""Wide enough for four grouped bars and narrow enough that GitHub does not shrink it much."""

PAPER = "#fdfdfb"
INK = "#1f2328"
FAINT = "#6b7280"
GRID = "#e3e5e8"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

# The published model last, so it is the rightmost bar in every group and the eye ends on
# it. The three rules of thumb are greys and sands, the two models and their average carry
# the colour, and the average is the strongest of them: the chart's subject.
METHODS: tuple[tuple[str, str, str], ...] = (
    ("carry-forward", "Last time", "#a8adb4"),
    ("best-equal-vdot", "Race calculator", "#8fb3cc"),
    ("category-median", "Your category", "#cbb389"),
    ("hierarchical", "Bayesian model", "#5f9fae"),
    ("lightgbm", "Boosted trees", "#9184bd"),
    ("blend", "Published: the average", "#2f6f4f"),
)

DEPTHS: tuple[tuple[str, str], ...] = (
    ("0", "No past races"),
    ("1", "One past race"),
    ("2 to 3", "Two or three"),
    ("4 or more", "Four or more"),
)


def _text(
    x: float,
    y: float,
    body: str,
    *,
    size: float = 12,
    fill: str = INK,
    anchor: str = "start",
    weight: str = "normal",
) -> str:
    return (
        f'<text x="{_n(x)}" y="{_n(y)}" font-size="{_n(size)}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{html.escape(body)}</text>'
    )


def _rect(x: float, y: float, width: float, height: float, fill: str, *, radius: float = 2) -> str:
    return (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(max(width, 0))}" '
        f'height="{_n(max(height, 0))}" rx="{_n(radius)}" fill="{fill}"/>'
    )


def _line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    stroke: str = GRID,
    dash: str = "",
    width: float = 1,
) -> str:
    attrs = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
        f'stroke="{stroke}" stroke-width="{_n(width)}"{attrs}/>'
    )


def _n(value: float) -> str:
    """One decimal place, and no trailing .0, so the same numbers give the same bytes."""
    rounded = round(float(value), 1)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


NOTE_SIZE = 10.5
"""SVG text does not wrap, so a note is written as lines and this is what they are set in."""


def width_of(body: str, size: float) -> float:
    """A rough width for a string, wide enough to catch a label that would be clipped.

    0.52 of the font size per character is a little generous for this stack, which is the
    safe direction: the test that uses it should complain before a reader sees a cut label.
    """
    return len(body) * 0.52 * size


def _frame(
    height: float,
    title: str,
    subtitle: str,
    body: str,
    notes: Sequence[str] = (),
) -> str:
    """The shell every chart shares: its own background, a title, the drawing, its notes."""
    foot = height - 12 - NOTE_SIZE * 1.3 * (len(notes) - 1 if notes else 0)
    written = "".join(
        _text(16, foot + NOTE_SIZE * 1.3 * index, line, size=NOTE_SIZE, fill=FAINT)
        for index, line in enumerate(notes)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {_n(height)}" '
        f'width="{WIDTH}" height="{_n(height)}" role="img" '
        f'aria-label="{html.escape(title)}" font-family="{FONT}">'
        f'<rect width="{WIDTH}" height="{_n(height)}" fill="{PAPER}"/>'
        + _text(16, 24, title, size=15, weight="600")
        + (_text(16, 42, subtitle, size=11.5, fill=FAINT) if subtitle else "")
        + body
        + written
        + "</svg>"
    )


def _legend(entries: Sequence[tuple[str, str]], x: float, y: float, step: float) -> str:
    """Swatch and label, left to right, one row."""
    out = []
    for index, (label, colour) in enumerate(entries):
        at = x + index * step
        out.append(_rect(at, y - 8, 10, 10, colour, radius=2))
        out.append(_text(at + 15, y, label, size=11, fill=FAINT))
    return "".join(out)


def error_by_depth(strata: Sequence[Mapping[str, Any]]) -> str:
    """Average error in minutes, per history depth, for every method beside the model.

    The whole argument of the project is in one picture here: the three rules of thumb, the
    two models, the average that publishes, and the empty space where a rule of thumb has
    nothing to say about a runner with no past races.
    """
    rows = {str(row["label"]): row for row in strata}
    top = 5.0
    for row in strata:
        for method, _label, _colour in METHODS:
            high = (row["models"].get(method) or {}).get("high_min")
            if isinstance(high, int | float):
                top = max(top, float(high))
    top = 5 * (int(top / 5) + 1)

    # The foot of the plot, the group labels, the runner counts and then the notes, each
    # with room of its own: the note used to be placed by counting up from the bottom edge
    # while the runner counts were placed by counting down from the plot, and they met.
    height, left, right, head, foot = 452.0, 56.0, WIDTH - 16.0, 104.0, 360.0
    body = [_legend([(label, colour) for _m, label, colour in METHODS], 16, 66, 142)]
    for tick in range(0, int(top) + 1, 5):
        y = foot - (foot - head) * tick / top
        body.append(_line(left, y, right, y))
        body.append(_text(left - 8, y + 4, f"{tick}", size=11, fill=FAINT, anchor="end"))
    body.append(_text(16, head - 14, "minutes", size=11, fill=FAINT))

    group = (right - left) / len(DEPTHS)
    for index, (key, label) in enumerate(DEPTHS):
        found = rows.get(key)
        x0 = left + group * index
        if index:
            body.append(_line(x0, head - 6, x0, foot + 26, stroke=GRID, dash="3 3"))
        body.append(_text(x0 + group / 2, foot + 22, label, size=12, anchor="middle"))
        if found is None:
            continue
        row = found
        body.append(
            _text(
                x0 + group / 2,
                foot + 38,
                f"{int(row['runners']):,} runners",
                size=10.5,
                fill=FAINT,
                anchor="middle",
            )
        )
        span = group * 0.84 / len(METHODS)
        for slot, (method, _label, colour) in enumerate(METHODS):
            measured = row["models"].get(method) or {}
            value = measured.get("mae_min")
            x = x0 + group * 0.08 + span * slot
            if not isinstance(value, int | float):
                body.append(
                    _text(x + span / 2, foot - 6, "n/a", size=10, fill=FAINT, anchor="middle")
                )
                continue
            y = foot - (foot - head) * float(value) / top
            body.append(_rect(x + 1.5, y, span - 3, foot - y, colour))
            low, high = measured.get("low_min"), measured.get("high_min")
            if isinstance(low, int | float) and isinstance(high, int | float):
                y_low = foot - (foot - head) * float(low) / top
                y_high = foot - (foot - head) * float(high) / top
                body.append(_line(x + span / 2, y_low, x + span / 2, y_high, stroke=INK, width=1))
            if method == "blend":
                body.append(
                    _text(
                        x + span / 2,
                        y - 6,
                        f"{float(value):.1f}",
                        size=11,
                        weight="600",
                        anchor="middle",
                    )
                )
    return _frame(
        height,
        "Average error by how many past races a runner has",
        "53 races from 2024 on, each prediction made only from results dated before its race",
        "".join(body),
        (
            "Bars are the mean absolute error and the line through each is its 95% interval.",
            "n/a is a method with nothing at all to say about that runner.",
        ),
    )


def error_by_distance(distances: Sequence[Mapping[str, Any]]) -> str:
    """The published model's average miss per race length, whole field and deep histories.

    Two bars a row rather than one, because the useful comparison is not between distances,
    which run for different lengths of time, but between a field and the part of it the
    model knows something about.
    """
    rows = [row for row in distances if isinstance(row.get("mae_min"), int | float)]
    if not rows:
        return _frame(120, "Average miss by race length", "Not measured yet", "")
    top = max(float(row["mae_min"]) for row in rows)
    top = 5 * (int(top / 5) + 1)

    head, foot = 78.0, 78.0 + 46.0 * len(rows)
    # Room under the axis for its ticks, its unit and two lines of note, in that order.
    height = foot + 96
    left, right = 176.0, WIDTH - 60.0
    body = [
        _legend(
            [("Whole field", "#8fb3cc"), ("Runners with four or more past races", "#2f6f4f")],
            16,
            66,
            120,
        )
    ]
    for tick in range(0, int(top) + 1, 5):
        x = left + (right - left) * tick / top
        body.append(_line(x, head - 8, x, foot + 4))
        body.append(_text(x, foot + 20, f"{tick}", size=11, fill=FAINT, anchor="middle"))
    body.append(_text(right, foot + 36, "minutes", size=11, fill=FAINT, anchor="end"))

    for index, row in enumerate(rows):
        y = head + 46 * index
        body.append(_text(left - 12, y + 12, str(row["label"]), size=12, anchor="end"))
        body.append(
            _text(
                left - 12,
                y + 27,
                f"{int(row['runners']):,} runners",
                size=10,
                fill=FAINT,
                anchor="end",
            )
        )
        for slot, (value, share, colour) in enumerate(
            (
                (row.get("mae_min"), row.get("mape"), "#8fb3cc"),
                (row.get("deep_mae_min"), row.get("deep_mape"), "#2f6f4f"),
            )
        ):
            bar_y = y + slot * 15
            if not isinstance(value, int | float):
                body.append(_text(left + 4, bar_y + 11, "not measured", size=10, fill=FAINT))
                continue
            width = (right - left) * float(value) / top
            body.append(_rect(left, bar_y, width, 13, colour))
            shown = f"{float(value):.1f} min"
            if isinstance(share, int | float):
                shown += f", {float(share) * 100:.0f}%"
            body.append(_text(left + width + 6, bar_y + 11, shown, size=10.5, fill=INK))
    return _frame(
        height,
        "How far out the published prediction is, by race length",
        "The same 53 races, every runner on every start list",
        "".join(body),
        (
            "Mean absolute error in minutes, with the same error as a share of the runner's own "
            "finish time beside it.",
            "Half of the misses are smaller than the average and a few are much larger: the "
            "table below has the middle and the ninth decile.",
        ),
    )


def coverage(rows: Sequence[Mapping[str, Any]]) -> str:
    """Did the ranges hold? Conformal coverage per depth, against what it promises."""
    measured = {(str(row["stratum"]), float(row["level"])): row for row in rows}
    if not measured:
        return _frame(120, "How often the ranges held", "Not measured yet", "")
    height, head, foot = 350.0, 96.0, 250.0
    panels = ((0.8, 66.0, 430.0), (0.9, 470.0, WIDTH - 16.0))
    lo, hi = 0.6, 1.0
    body = [
        _legend([("Where the finishes actually fell", "#2f6f4f")], 16, 66, 160),
        _text(360, 66, "dashed: what the range promises", size=11, fill=FAINT),
    ]
    for tick in (0.6, 0.7, 0.8, 0.9, 1.0):
        y = foot - (foot - head) * (tick - lo) / (hi - lo)
        body.append(_line(66, y, WIDTH - 16, y))
        body.append(_text(58, y + 4, f"{tick * 100:.0f}%", size=11, fill=FAINT, anchor="end"))

    for level, left, right in panels:
        body.append(
            _text(
                (left + right) / 2,
                foot + 44,
                f"the {level * 100:.0f}% range",
                size=12,
                anchor="middle",
            )
        )
        promised = foot - (foot - head) * (level - lo) / (hi - lo)
        body.append(_line(left, promised, right, promised, stroke=FAINT, dash="5 4"))
        step = (right - left) / len(DEPTHS)
        for index, (key, label) in enumerate(DEPTHS):
            row = measured.get((key, level))
            x = left + step * (index + 0.5)
            body.append(
                _text(x, foot + 22, label.replace(" past races", "").replace(" past race", ""),
                      size=10.5, fill=FAINT, anchor="middle")
            )
            if row is None:
                continue
            value = float(row["conformal"])
            y = foot - (foot - head) * (value - lo) / (hi - lo)
            y_low = foot - (foot - head) * (float(row["conformal_low"]) - lo) / (hi - lo)
            y_high = foot - (foot - head) * (float(row["conformal_high"]) - lo) / (hi - lo)
            body.append(_line(x, y_low, x, y_high, stroke=INK, width=1))
            body.append(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="5.5" fill="#2f6f4f"/>')
            body.append(
                _text(x, y - 11, f"{value * 100:.0f}%", size=10.5, weight="600", anchor="middle")
            )
    return _frame(
        height,
        "How often the ranges held, by how much history a runner has",
        "A range that holds less often than it promises is a range that is too narrow",
        "".join(body),
        (
            "Share of runners whose finish fell inside their own range, after calibration on the "
            "races before theirs.",
            "The line through each dot is its 95% interval, which resamples races rather than "
            "runners.",
        ),
    )


FILES = ("error-by-depth.svg", "error-by-distance.svg", "coverage.svg")


def write(results: Mapping[str, Any], out: Path) -> list[Path]:
    """Draw all three charts into `out`, and say which files were written."""
    backtest = results.get("backtest") or {}
    drawings = (
        error_by_depth(backtest.get("strata") or []),
        error_by_distance(results.get("distances") or []),
        coverage(backtest.get("coverage") or []),
    )
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, drawing in zip(FILES, drawings, strict=True):
        path = out / name
        path.write_text(drawing + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written
