"""The README's charts: drawn from the published numbers, and drawn inside their frames.

A chart in a commit has two failure modes a test can catch. It can disagree with the table
under it, which is caught by drawing from the same published JSON and asserting the numbers
appear. And it can be laid out wrong, which nobody notices until a reader sees a clipped
label, because SVG text neither wraps nor complains. So the layout is measured here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from finishline.publish import charts

TEXT = re.compile(
    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)" font-size="([\d.]+)" fill="[^"]*" '
    r'text-anchor="(\w+)"[^>]*>([^<]*)</text>'
)
VIEWBOX = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')


def _measured() -> dict[str, Any]:
    """A backtest shaped like the published one, small enough to read."""
    models = {
        "carry-forward": {"mae_min": 7.4, "low_min": 7.2, "high_min": 7.6, "answered": 1.0},
        "best-equal-vdot": {"mae_min": 7.2, "low_min": 7.0, "high_min": 7.4, "answered": 0.87},
        "category-median": {"mae_min": 14.0, "low_min": 13.7, "high_min": 14.4, "answered": 0.95},
        "hierarchical": {"mae_min": 5.4, "low_min": 5.2, "high_min": 5.6, "answered": 1.0},
        "lightgbm": {"mae_min": 5.2, "low_min": 5.0, "high_min": 5.3, "answered": 1.0},
        "blend": {"mae_min": 5.0, "low_min": 4.8, "high_min": 5.2, "answered": 1.0},
    }
    nothing = {"mae_min": None, "low_min": None, "high_min": None, "answered": 0.0}
    return {
        "backtest": {
            "strata": [
                {
                    "label": "0",
                    "runners": 5711,
                    "models": {**models, "carry-forward": nothing, "best-equal-vdot": nothing},
                },
                {"label": "1", "runners": 2713, "models": models},
                {"label": "2 to 3", "runners": 2910, "models": models},
                {"label": "4 or more", "runners": 7490, "models": models},
            ],
            "coverage": [
                {
                    "stratum": stratum,
                    "level": level,
                    "conformal": 0.78,
                    "conformal_low": 0.74,
                    "conformal_high": 0.82,
                    "checked": 1000,
                }
                for stratum in ("0", "1", "2 to 3", "4 or more")
                for level in (0.8, 0.9)
            ],
        },
        "distances": [
            {
                "label": "5 km",
                "runners": 2491,
                "mae_min": 3.49,
                "mape": 0.1041,
                "deep_mae_min": 1.42,
                "deep_mape": 0.0534,
                "median_error_min": 1.6,
                "p90_error_min": 8.67,
            },
            {
                "label": "Marathon",
                "runners": 323,
                "mae_min": 26.0,
                "mape": 0.0998,
                "deep_mae_min": None,
                "deep_mape": None,
                "median_error_min": 20.2,
                "p90_error_min": 58.1,
            },
        ],
    }


def _labels(svg: str) -> list[tuple[float, float, float, str, str]]:
    return [
        (float(x), float(y), float(size), anchor, body)
        for x, y, size, anchor, body in TEXT.findall(svg)
    ]


def test_no_label_is_drawn_outside_its_frame() -> None:
    """The failure this catches is a sentence running off the right edge of the picture.

    SVG text does not wrap, so a note that grew by ten words is simply cut, and a reader sees
    half a sentence. Widths are estimated generously on purpose: complain early.
    """
    measured = _measured()
    for svg in (
        charts.error_by_depth(measured["backtest"]["strata"]),
        charts.error_by_distance(measured["distances"]),
        charts.coverage(measured["backtest"]["coverage"]),
    ):
        box = VIEWBOX.search(svg)
        assert box is not None
        width, height = float(box.group(1)), float(box.group(2))
        for x, y, size, anchor, body in _labels(svg):
            span = charts.width_of(body, size)
            left = x if anchor == "start" else x - span / 2 if anchor == "middle" else x - span
            assert left >= 0, f"{body!r} starts off the left edge"
            assert left + span <= width, f"{body!r} runs off the right edge"
            assert 0 <= y <= height, f"{body!r} sits outside the frame"


def test_the_published_model_is_the_one_labelled_with_its_number() -> None:
    """One number is printed on the chart, and it is the one the page leads with."""
    svg = charts.error_by_depth(_measured()["backtest"]["strata"])
    printed = [body for *_rest, body in _labels(svg)]
    assert printed.count("5.0") == 4, "the published model's bar carries its value in every group"
    assert "7.4" not in printed, "no other method's bar does, or the chart becomes a table"
    assert "Published: the average" in printed


def test_a_method_with_nothing_to_say_is_drawn_as_nothing() -> None:
    """A rule of thumb that cannot answer for first-timers gets no bar, and says so.

    Drawing a zero-height bar would read as zero error, which is the opposite of the truth.
    """
    svg = charts.error_by_depth(_measured()["backtest"]["strata"])
    printed = [body for *_rest, body in _labels(svg)]
    assert printed.count("n/a") == 2, "last time and the race calculator, at no past races"


def test_a_bigger_error_draws_a_taller_bar() -> None:
    """The one property a bar chart has to have."""
    strata = _measured()["backtest"]["strata"]
    svg = charts.error_by_depth(strata)
    heights = {
        (float(match.group(1)), float(match.group(2))): float(match.group(3))
        for match in re.finditer(
            r'<rect x="([\d.]+)" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"', svg
        )
    }
    tall = max(heights.values())
    # category-median is 14.0 minutes against blend's 5.0, so its bar is the taller one by
    # about the same ratio; the legend swatches are 10px and are excluded by the ratio test.
    assert tall / min(h for h in heights.values() if h > 20) > 2.0


def test_the_same_numbers_draw_the_same_bytes(tmp_path: Path) -> None:
    """A chart lives in a commit, so an unchanged measurement must not rewrite the diff."""
    first = charts.write(_measured(), tmp_path / "a")
    second = charts.write(_measured(), tmp_path / "b")
    assert [path.name for path in first] == list(charts.FILES)
    for left, right in zip(first, second, strict=True):
        assert left.read_bytes() == right.read_bytes()


def test_a_chart_carries_no_script_and_paints_its_own_background() -> None:
    """GitHub sanitises an SVG, and a chart has nothing that needs sanitising.

    The background is the part that matters for a reader: an image gets no page CSS, so a
    chart with a transparent background is unreadable in dark mode.
    """
    for svg in (
        charts.error_by_depth(_measured()["backtest"]["strata"]),
        charts.error_by_distance(_measured()["distances"]),
        charts.coverage(_measured()["backtest"]["coverage"]),
    ):
        assert "<script" not in svg and "onload" not in svg
        assert f'<rect width="{charts.WIDTH}"' in svg and charts.PAPER in svg


def test_a_chart_with_no_measurement_says_so_rather_than_drawing_axes() -> None:
    assert "Not measured yet" in charts.error_by_distance([])
    assert "Not measured yet" in charts.coverage([])


def test_no_two_labels_are_drawn_on_top_of_each_other() -> None:
    """The failure this catches is two sentences printed through one another.

    It happened: the note under the first chart was placed by counting up from the bottom
    edge while the runner counts were placed by counting down from the plot, and at one
    height the two met and the chart said "Bars are the mean abso5,711 runnerse error".
    Nothing in the drawing complains, because SVG text is just a baseline and a string.
    """
    measured = _measured()
    for name, svg in (
        ("depth", charts.error_by_depth(measured["backtest"]["strata"])),
        ("distance", charts.error_by_distance(measured["distances"])),
        ("coverage", charts.coverage(measured["backtest"]["coverage"])),
    ):
        drawn = []
        for x, y, size, anchor, body in _labels(svg):
            if not body.strip():
                continue
            span = charts.width_of(body, size)
            left = x if anchor == "start" else x - span / 2 if anchor == "middle" else x - span
            drawn.append((left, left + span, y, size, body))
        for index, first in enumerate(drawn):
            for second in drawn[index + 1 :]:
                overlaps_across = first[0] < second[1] - 1 and second[0] < first[1] - 1
                apart = abs(first[2] - second[2])
                if overlaps_across and apart < max(first[3], second[3]) * 0.9:
                    raise AssertionError(
                        f"{name}: {first[4]!r} and {second[4]!r} are drawn over each other "
                        f"(baselines {first[2]} and {second[2]})"
                    )
