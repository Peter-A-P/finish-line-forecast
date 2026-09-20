"""The public website: what this is, every live race and its predictions, and how it works.

Built by `finishline site` into `site/` and deployed to Azure Static Web Apps by the Website
workflow on every push (docs/deploy.md), so a daily prediction file that the morning task
commits is on the website minutes later. It is built from committed files only:

- `web/`, the page itself: `index.html` with `{{tokens}}`, `style.css`, `app.js` and the fonts,
  in the same style as the other project pages on peterparker.ca;
- `data/site/results.json`, the measured numbers, written by `finishline report` from the same
  objects as the README's tables (`publish/showcase.py`);
- `data/live.toml` and the prediction files under `predictions/`.

The page's headline numbers are filled in here, as text, so that they are in the page a
search engine or a reader without JavaScript sees; the race picker and the charts are drawn by
`app.js` from the JSON files written beside it.

⚠️ **Nothing inline.** The host sends a content security policy (`HOST_CONFIG`, written into
the site as `staticwebapp.config.json`) that allows scripts and styles from the site's own
files only, so an inline `<style>` or `<script>` would be refused on the live site while
looking fine from a plain file server. `finishline serve` sends the same headers locally.

⚠️ **The names are kept out of search engines.** Runners' predictions are only ever in
`data/predictions/*.json`, which `robots.txt` disallows and the host serves with
`X-Robots-Tag: noindex`, so a crawler rendering the page cannot fetch them. The page itself,
which names nobody, is indexed. `app.js` puts names into the page with `textContent` only.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from finishline.metrics import daniels
from finishline.models import blend
from finishline.publish import daily, predictions, showcase
from finishline.schema import HALF_MARATHON_M

REPOSITORY = "https://github.com/Peter-A-P/finish-line-forecast"
PREDICTION_DATA = "data/predictions"

# What Azure Static Web Apps sends with every file (docs/deploy.md), as project 08 does.
HOST_CONFIG: dict[str, Any] = {
    "$schema": "https://json.schemastore.org/staticwebapp.config.json",
    "globalHeaders": {
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=(), interest-cohort=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    },
    "mimeTypes": {
        ".json": "application/json",
        ".js": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".woff2": "font/woff2",
        ".txt": "text/plain",
    },
    "routes": [
        {
            "route": f"/{PREDICTION_DATA}/*",
            "headers": {
                "X-Robots-Tag": "noindex",
                "Cache-Control": "public, max-age=300, must-revalidate",
            },
        },
        {"route": "/data/*", "headers": {"Cache-Control": "public, max-age=300, must-revalidate"}},
        {"route": "/index.html", "headers": {"Cache-Control": "public, max-age=300"}},
    ],
}

ROBOTS = f"User-agent: *\nDisallow: /{PREDICTION_DATA}/\n"

# The invented runner in the "one scale" section: three races, one fitness.
EXAMPLE_RACES: tuple[tuple[str, float, float], ...] = (
    ("5 km in the spring", 5_000.0, 24 * 60.0),
    ("10 km in the summer", 10_000.0, 49 * 60.0 + 30.0),
    ("Half marathon in the autumn", HALF_MARATHON_M, 110 * 60.0),
)


@dataclass(frozen=True, slots=True)
class Published:
    """One prediction file as the website reads it."""

    name: str
    doc: dict[str, Any]
    sha256: str


def files_for(directory: Path, race_id: str) -> list[Published]:
    """The race's daily files in date order, then its final file."""
    paths = sorted((directory / race_id).glob(f"{daily.DAILY_PREFIX}*.json"))
    final = directory / f"{race_id}.json"
    if final.exists():
        paths.append(final)
    return [
        Published(
            path.name,
            json.loads(path.read_text(encoding="utf-8")),
            predictions.sha256(path.read_bytes()),
        )
        for path in paths
    ]


def clock(seconds: float) -> str:
    """A finish time the way a results page prints one."""
    whole = round(float(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def stage(files: Sequence[Published], scored: bool, today: date, race_date: date) -> str:
    """Where a race is: before its week, in it, frozen, run, or scored."""
    if scored:
        return "scored"
    if today > race_date:
        return "run"
    if any(item.doc.get("kind") != "daily" for item in files):
        return "final"
    return "week" if files else "before"


def status(files: Sequence[Published], scored: bool, today: date, race_date: date) -> str:
    """One line saying where this race is in its week."""
    now = stage(files, scored, today, race_date)
    if now == "scored":
        return "Scored against the official results."
    if now == "final":
        return "Final prediction frozen and published. Nothing changes now."
    if now == "week":
        runners = sum(len(item.doc["runners"]) for item in files)
        return f"Prediction week: {len(files)} daily file(s) so far, {runners} runners predicted."
    if now == "run":
        return "Race run; waiting for the official results."
    # A date, not a countdown: the site is rebuilt only when something is pushed, so "in 8
    # days" would go stale on every morning nothing is.
    start = race_date - timedelta(days=daily.FIRST_LEAD_DAYS)
    if today >= start:
        return "The first daily prediction is due; none is published yet."
    return f"Daily predictions start {start.isoformat()}."


def _file_url(race_id: str, item: Published) -> str:
    folder = f"{race_id}/" if item.doc.get("kind") == "daily" else ""
    return f"{REPOSITORY}/blob/main/predictions/{folder}{item.name}"


def race_record(
    race_id: str, record: Mapping[str, Any], files: Sequence[Published], scored: bool, today: date
) -> dict[str, Any]:
    """What the page says about one race, naming nobody."""
    when = date.fromisoformat(str(record["date"]))
    final = next((item for item in files if item.doc.get("kind") != "daily"), None)
    source = final or (files[-1] if files else None)
    forecast = None
    if source is not None and source.doc.get("conditions"):
        forecast = source.doc["conditions"].get("forecast")
    return {
        "id": race_id,
        "name": str(record.get("name", race_id)),
        "date": when.isoformat(),
        "gun": record.get("gun"),
        "distance_m": record.get("distance_m"),
        "course_id": record.get("course_id"),
        "entrant_list": record.get("entrant_list") is not None,
        "newcomer_pool": record.get("newcomers") == "course",
        "stage": stage(files, scored, today, when),
        "status": status(files, scored, today, when),
        "week_start": (when - timedelta(days=daily.FIRST_LEAD_DAYS)).isoformat(),
        "final_by": (when - timedelta(days=1)).isoformat(),
        "forecast": forecast,
        "files": [
            {
                "name": item.name,
                "url": _file_url(race_id, item),
                "frozen_at": item.doc["frozen_at"],
                "sha256": item.sha256,
                "kind": item.doc.get("kind", "final"),
                "runners": len(item.doc["runners"]),
            }
            for item in files
        ],
        "scorecard": f"{REPOSITORY}/blob/main/docs/predictions/{race_id}.md" if scored else None,
        "predictions": f"{PREDICTION_DATA}/{race_id}.json" if files else None,
    }


def race_predictions(files: Sequence[Published]) -> dict[str, Any]:
    """Every published runner line for one race: the final file's once it exists."""
    final = next((item for item in files if item.doc.get("kind") != "daily"), None)
    if final is not None:
        lines = [
            (str(runner.get("first_published", final.name)), runner)
            for runner in final.doc["runners"]
        ]
    else:
        lines = [(item.name, runner) for item in files for runner in item.doc["runners"]]
    lines.sort(key=lambda item: (item[1]["seconds"], item[1]["name"]))
    runners = []
    for source, runner in lines:
        row: dict[str, Any] = {
            "name": runner["name"],
            "hometown": runner.get("hometown"),
            "prior": runner["prior_results"],
            "seconds": runner["seconds"],
            "i80": runner["interval_80"],
            "i90": runner["interval_90"],
            "file": source,
        }
        if "place" in runner:
            row["place"] = runner["place"]
        runners.append(row)
    return {
        "final": final is not None,
        "newcomers": None if final is None else final.doc.get("newcomers"),
        "runners": runners,
    }


def plan_entries(plan: Path) -> int:
    """How many designs PLAN.md section 13 records the data refuting."""
    text = plan.read_text(encoding="utf-8")
    section = text.split("\n## 13.", 1)[1].split("\n## ", 1)[0]
    return len(re.findall(r"^ {0,3}\d+\. \*\*", section, flags=re.MULTILINE))


def count_tests(tests: Path) -> int:
    """Test functions in the suite, before parametrisation multiplies them."""
    return sum(
        len(re.findall(r"^def test_", path.read_text(encoding="utf-8"), flags=re.MULTILINE))
        for path in tests.glob("test_*.py")
    )


def count_lines(source: Path) -> int:
    return sum(len(path.read_text(encoding="utf-8").splitlines()) for path in source.rglob("*.py"))


def vdot_rows() -> str:
    """The invented runner's races, on one scale, from this project's own Daniels code."""
    rows = []
    for label, metres, seconds in EXAMPLE_RACES:
        value = daniels.vdot(metres, seconds)
        tenk = daniels.race_time(value, 10_000.0)
        if value is None or tenk is None:
            raise ValueError(f"{label} is outside the range Daniels' tables are fitted for")
        rows.append(
            f"<tr><td>{html.escape(label)}</td><td class=\"num\">{clock(seconds)}</td>"
            f"<td class=\"num\">{value:.1f}</td><td class=\"num\">{clock(tenk)}</td></tr>"
        )
    return "".join(rows)


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _number(value: float | None, places: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{places}f}"


def tokens(
    results: Mapping[str, Any],
    races: Sequence[Mapping[str, Any]],
    *,
    refuted: int,
    tests: int,
    code_lines: int,
    today: date,
) -> dict[str, str]:
    """Every `{{token}}` in web/index.html, as the text that replaces it."""
    archive = results["archive"]
    backtest = results["backtest"]
    strata = {row["label"]: row["models"] for row in backtest["strata"]}
    deep = strata.get("4 or more", {})
    model = deep.get(showcase.MODEL, {})
    baseline = deep.get(showcase.BASELINE, {})
    newcomer = strata.get("0", {}).get(showcase.MODEL, {})
    # What share of a whole field each method can answer for at all. "Last time" has nothing to
    # say about a runner with no past result, and about three entrants in ten are that runner, so
    # the comparison of errors is only half the story and the page says the other half.
    def answered(name: str) -> float | None:
        counted = [(row["runners"], row["models"].get(name, {})) for row in backtest["strata"]]
        total = sum(runners for runners, _model in counted)
        known = [
            (runners, model) for runners, model in counted if model.get("answered") is not None
        ]
        if not total or not known:
            return None
        share = sum(runners * float(model["answered"]) for runners, model in known) / total
        return float(share)

    newcomers = next(
        (row["runners"] for row in backtest["strata"] if row["label"] == "0"), 0
    )
    field = sum(row["runners"] for row in backtest["strata"]) or 1
    coverage = {(row["stratum"], row["level"]): row for row in backtest["coverage"]}
    cov_deep = coverage.get(("4 or more", 0.8), {})
    cov_new = coverage.get(("0", 0.8), {})
    course = {row["course_id"]: row for row in results["courses"]}
    c2c = course.get("cape-to-cabot-20000")
    options = "".join(
        f"<option value=\"{html.escape(str(race['id']))}\">{html.escape(str(race['name']))}, "
        f"{date.fromisoformat(str(race['date'])).day} "
        f"{date.fromisoformat(str(race['date'])).strftime('%B %Y')}</option>"
        for race in races
    )
    gbm_verdict, gbm_ranges = challenger_text(results)
    return {
        "repository": REPOSITORY,
        "gbm_verdict": gbm_verdict,
        "gbm_ranges": gbm_ranges,
        # From the constant the predictions are made with, so the page cannot state a weight
        # the model does not use.
        "blend_weight": f"{blend.WEIGHT:.2f}",
        "blend_parent_weight": f"{1 - blend.WEIGHT:.2f}",
        "mae_model": _number(model.get("mae_min")),
        # The same error as a share of each runner's own finish time. Minutes mean different
        # things over 5 km and over a marathon, and this field is mostly 10 to 16 km races, so
        # the page says both and the reader can judge which one they care about.
        "mae_model_pct": _percent(model.get("mape")),
        "mae_cf": _number(baseline.get("mae_min")),
        "model_answered": _percent(answered(showcase.MODEL)),
        "cf_answered": _percent(answered(showcase.BASELINE)),
        "vdot_answered": _percent(answered("best-equal-vdot")),
        "newcomer_share": _percent(newcomers / field),
        "mae_new": _number(newcomer.get("mae_min"), 0),
        "skill": _percent(model.get("skill")),
        "cov80_deep": _percent(cov_deep.get("conformal")),
        "width_new": _number(cov_new.get("conformal_width_min"), 0),
        "width_deep": _number(cov_deep.get("conformal_width_min"), 0),
        "bt_predictions": f"{backtest['predictions']:,}",
        "bt_races": str(backtest["races"]),
        "bt_first_year": str(backtest["first_race"])[:4],
        "finishes": f"{archive['finishes']:,}",
        "runners": f"{archive['runners']:,}",
        "races": str(archive["races"]),
        "courses": str(archive["courses"]),
        "ambiguous": f"{archive['ambiguous']:,}",
        "unparsed": str(archive["unparsed"]),
        "first_year": str(archive["first_year"]),
        "last_year": str(archive["last_year"]),
        "c2c_factor": "n/a" if c2c is None else f"{c2c['factor'] * 100:.0f}%",
        "race_options": options,
        "vdot_rows": vdot_rows(),
        "distance_rows": distance_rows(results),
        "hero_distances": hero_distances(results),
        "speed_options": speed_options(),
        "refuted": str(refuted),
        "tests": f"{tests:,}",
        "code_lines": f"{code_lines:,}",
        "built": today.isoformat(),
    }


_DEPTHS = {
    "0": "first-timers",
    "1": "runners with one past race",
    "2 to 3": "runners with two or three past races",
    "4 or more": "runners with four or more past races",
}


def _blend_sentences(backtest: Mapping[str, Any]) -> list[str]:
    """What the page says about publishing the average of the two models.

    Silent until both comparisons are in the file, because the claim the page makes is that the
    average beats both parents, and a page cannot make that claim from one of them.
    """
    blend = backtest.get("blend_paired") or {}
    against_model = blend.get("hierarchical") or []
    against_trees = blend.get("lightgbm") or []
    if not against_model or not against_trees:
        return []
    said = [
        "<strong>So what this site publishes is neither model on its own: it is the two "
        "averaged.</strong> The average is taken on the log scale, leaning about two thirds on "
        "the trees, and how far to lean was read off the 2022 and 2023 races alone, so nothing "
        "in the tables on this page helped choose it."
    ]
    for name, rows in (("Bayesian model", against_model), ("trees", against_trees)):
        ahead, level, behind = _phrases(rows)
        parts = []
        if ahead:
            parts.append("better for " + "; ".join(ahead))
        if level:
            parts.append("level for " + "; ".join(level))
        if behind:
            parts.append("behind for " + "; ".join(behind))
        if parts:
            body = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", and " + parts[-1]
            said.append(f"Against the {name}, the average is {body}.")
    said.append(
        "Averaging two models that make different mistakes is the oldest trick in forecasting, "
        "and the gain here is real but small: a few tenths of a percent of a finish time, which "
        "is seconds rather than minutes. It is published because it is measured, at the size it "
        "was measured."
    )
    return said


def _phrases(paired: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    """Each depth sorted into ahead, level and behind, as the page says them.

    Ahead means the first model named in the comparison is more accurate and the interval is
    clear of zero. An interval that crosses zero is called level, whichever way it leans.
    """
    ahead: list[str] = []
    level: list[str] = []
    behind: list[str] = []
    for row in paired:
        _point, low, high = row["difference"]
        who = _DEPTHS.get(row["label"], f"runners with {row['label']} past races")
        times = f"{row['model_min']:.1f} against {row['other_min']:.1f} minutes"
        gap = sorted((abs(low), abs(high)))
        detail = f"{who} ({times}, {gap[0]:.1f} to {gap[1]:.1f} points of a finish time)"
        if high < 0:
            ahead.append(detail)
        elif low > 0:
            behind.append(detail)
        else:
            level.append(f"{who} ({times})")
    return ahead, level, behind


DEFAULT_SPEED = "front"


def speed_options(selected: str = DEFAULT_SPEED) -> str:
    """The three parts of a field, as options for the strip's picker.

    The words come from `showcase.SPEED_GROUPS`, so the page, the JSON and any future table
    say the same thing about the same runners.
    """
    return "".join(
        f'<option value="{html.escape(key)}"{" selected" if key == selected else ""}>'
        f"{html.escape(label)}, the {html.escape(note)}"
        "</option>"
        for key, label, note, _low, _high in showcase.SPEED_GROUPS
    )


def hero_distances(results: Mapping[str, Any], group: str = DEFAULT_SPEED) -> str:
    """The typical error at each race length, for one part of the field, as the hero strip.

    The population is runners with four or more past races, the same as the headline figure, so
    a reader comparing the two is not quietly changed subject on. Rendered here for the group
    the page opens on, so a reader without JavaScript still gets numbers; `app.js` redraws the
    strip from the same JSON when the picker changes.
    """
    groups = results.get("distance_groups") or {}
    rows = (groups.get("rows") or {}).get(group) or []
    if not rows:
        return ""
    return "".join(
        "<span class=\"hero-distance\">"
        f"<span class=\"hd-race\">{html.escape(str(row['label']))}</span>"
        f"<span class=\"hd-min\">{row['mae_min']:.1f} min</span>"
        f"<span class=\"hd-pct\">{row['mape'] * 100:.1f}% of the time</span>"
        "</span>"
        for row in rows
    )


def distance_rows(results: Mapping[str, Any]) -> str:
    """The error by race length, as table rows, in minutes and as a share of a finish time.

    Both units, because "five minutes out" is a different claim over 5 km and over a marathon,
    and the share is the one that compares them. Written here rather than drawn in the browser:
    it is six rows, and a table a reader can copy beats a chart they cannot.
    """
    rows = results.get("distances") or []
    if not rows:
        return (
            '<tr><td colspan="5">Not measured yet; run the backtest.</td></tr>'
        )
    out = []
    for row in rows:
        deep = "-" if row.get("deep_mae_min") is None else (
            f"{row['deep_mae_min']:.1f} min, {_percent(row['deep_mape'])}"
        )
        out.append(
            "<tr>"
            f"<td>{html.escape(str(row['label']))}</td>"
            f"<td class=\"num\">{row['runners']:,}</td>"
            f"<td class=\"num\">{row['median_min']:.0f} min</td>"
            f"<td class=\"num\">{row['mae_min']:.1f} min, {_percent(row['mape'])}</td>"
            f"<td class=\"num\">{deep}</td>"
            "</tr>"
        )
    return "".join(out)


def challenger_text(results: Mapping[str, Any]) -> tuple[str, str]:
    """What the page says about the challenger and the blend, from their numbers.

    Worded from the paired comparisons on the same runners with a race-level interval
    (`score.paired_error`), not from two marginal MAE intervals, which overlap even when one
    model is consistently ahead. A difference whose interval crosses zero is called level.
    """
    backtest = results["backtest"]
    paired = backtest.get("challenger_paired") or []
    if not paired:
        owed = "The LightGBM challenger's backtest is not published yet."
        return owed, owed

    ahead, level, behind = _phrases(paired)
    sentences = []
    if ahead:
        sentences.append(
            "<strong>On the same runners, the LightGBM challenger is more accurate than the "
            "Bayesian model</strong> for " + "; ".join(ahead) + "."
        )
    if behind:
        sentences.append("The Bayesian model is more accurate for " + "; ".join(behind) + ".")
    if level:
        sentences.append("The two are level for " + "; ".join(level) + ".")
    challenger_places = backtest.get("challenger_placing")
    parent_places = backtest.get("parent_placing")
    if challenger_places and parent_places:
        mine = -challenger_places["difference"][0]
        theirs = -parent_places["difference"][0]
        sentences.append(
            f"On the order of a field, it is {mine:.1f} places closer than \"last time\" on the "
            f"same runners, against the Bayesian model's {theirs:.1f}."
        )
    sentences.extend(_blend_sentences(backtest))
    verdict = " ".join(sentence for sentence in sentences if sentence)

    held = {
        (row["stratum"], row["level"]): row for row in backtest.get("challenger_coverage", [])
    }

    def rate(stratum: str, key: str) -> str:
        row = held.get((stratum, 0.8), {})
        return _percent(row.get(key))

    ranges = (
        f"<strong>Its own 80% ranges held {rate('1', 'raw')} of the time for runners with one "
        f"past race and {rate('4 or more', 'raw')} for runners with four or more; after "
        f"calibration, {rate('1', 'conformal')} and {rate('4 or more', 'conformal')}.</strong> "
        "Quantile trees fit each edge of the range on its own and nothing ties the edges to "
        "how often they hold, which is why no range this project publishes goes out without "
        "the calibration step."
    )
    return verdict, ranges


def fill(template: str, values: Mapping[str, str]) -> str:
    """Replace every `{{token}}`, refusing a token with no value or a value with no token."""
    used = set(re.findall(r"\{\{(\w+)\}\}", template))
    missing = used - set(values)
    if missing:
        raise KeyError(f"web/index.html asks for {sorted(missing)}, which nothing supplies")
    unused = set(values) - used
    if unused:
        raise KeyError(f"{sorted(unused)} are supplied and web/index.html never uses them")
    return re.sub(r"\{\{(\w+)\}\}", lambda match: values[match.group(1)], template)


def _json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(
    out: Path,
    live: Path,
    directory: Path,
    scores: Path,
    today: date,
    *,
    web: Path = Path("web"),
    results: Path = Path("data/site/results.json"),
    plan: Path = Path("PLAN.md"),
    tests: Path = Path("tests"),
    source: Path = Path("src"),
) -> list[Path]:
    """Write the whole site; returns the files written."""
    records: dict[str, Any] = tomllib.loads(live.read_text(encoding="utf-8"))
    measured: dict[str, Any] = json.loads(results.read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(web, out, ignore=shutil.ignore_patterns("index.html"))
    written: list[Path] = []

    races = []
    for race_id in records:
        files = files_for(directory, race_id)
        scored = (scores / f"{race_id}.json").exists()
        races.append(race_record(race_id, records[race_id], files, scored, today))
        if files:
            path = out / PREDICTION_DATA / f"{race_id}.json"
            _json(path, race_predictions(files))
            written.append(path)
    # The races still to come first, soonest first, then the ones already run, latest first.
    upcoming = sorted(
        (race for race in races if race["stage"] not in ("run", "scored")),
        key=lambda race: str(race["date"]),
    )
    past = sorted(
        (race for race in races if race["stage"] in ("run", "scored")),
        key=lambda race: str(race["date"]),
        reverse=True,
    )
    ordered = upcoming + past

    for name, payload in (("results.json", measured), ("races.json", ordered)):
        path = out / "data" / name
        _json(path, payload)
        written.append(path)

    page = out / "index.html"
    page.write_text(
        fill(
            (web / "index.html").read_text(encoding="utf-8"),
            tokens(
                measured,
                ordered,
                refuted=plan_entries(plan),
                tests=count_tests(tests),
                code_lines=count_lines(source),
                today=today,
            ),
        ),
        encoding="utf-8",
        newline="\n",
    )
    # Each race had a page of its own before the site became one page; those addresses
    # still work, and land on the race in the picker.
    moved = [
        {"route": f"/{race['id']}.html", "redirect": f"/#{race['id']}", "statusCode": 301}
        for race in ordered
    ]
    host = {**HOST_CONFIG, "routes": [*moved, *HOST_CONFIG["routes"]]}
    config = out / "staticwebapp.config.json"
    config.write_text(json.dumps(host, indent=2) + "\n", encoding="utf-8", newline="\n")
    robots = out / "robots.txt"
    robots.write_text(ROBOTS, encoding="utf-8", newline="\n")
    return [page, config, robots, *written]
