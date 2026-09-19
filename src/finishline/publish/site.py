"""The public website: every live race, its predictions, and a runner looking themselves up.

Built by `finishline site` into `site/` and deployed to Azure Static Web Apps by the Website
workflow on every push (docs/deploy.md), so a daily prediction file that the morning task
commits is on the website minutes later. Like the
race page, it is rendered from the committed prediction files and `data/live.toml` and nothing
else: the website cannot show a prediction that is not in a tagged file, and each file's
SHA-256 is printed so anyone can check the one they are reading.

Static HTML, one stylesheet and one small script for the name search, all served from the
site itself. No framework, no tracking, no third-party request of any kind: the pages name
real people, and a reader looking up their own prediction should not be announcing it to
anybody.

⚠️ **Nothing inline.** The host sends a content security policy (`HOST_CONFIG`, written into
the site as `staticwebapp.config.json`) that allows scripts and styles from the site's own
files only, so an inline `<style>` or `<script>` would be refused on the live site while
looking fine from a plain file server. `finishline serve` sends the same headers locally.

⚠️ **Race pages ask search engines not to index them.** They list real people by name; the
results pages already do, but a prediction about a named person turning up in a web search is
a step further than the results go. The front page, which names nobody, may be indexed.
"""

from __future__ import annotations

import html
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from finishline.publish import daily, predictions
from finishline.publish.racepage import TOP, UNSEEN, clock

REPOSITORY = "https://github.com/Peter-A-P/finish-line-forecast"

STYLE = """
:root { --bg: #fbfaf7; --fg: #1d1f21; --muted: #5d6166; --line: #dcdad4; --accent: #1f5f8b;
  --band: #f1efe9; --mark: #fff2b3; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #16181b; --fg: #e8e6e1; --muted: #a2a6ab; --line: #34373c; --accent: #7fb6dd;
    --band: #1f2226; --mark: #5a4d12; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 64rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
h1 { font-size: 1.75rem; margin: 0 0 .25rem; }
h2 { font-size: 1.2rem; margin: 2rem 0 .5rem; }
p { max-width: 44rem; }
a { color: var(--accent); }
.muted { color: var(--muted); font-size: .9rem; }
.wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: .4rem .6rem; text-align: left; border-bottom: 1px solid var(--line);
  white-space: nowrap; }
th { background: var(--band); font-weight: 600; font-size: .85rem; }
td.num, th.num { text-align: right; }
tr.unseen td { color: var(--muted); font-style: italic; }
input[type=search] { width: 100%; max-width: 24rem; padding: .5rem .6rem; font: inherit;
  border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--fg);
  margin: .25rem 0 .75rem; }
.cards { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); }
.card { border: 1px solid var(--line); border-radius: 8px; padding: .9rem 1rem; }
.card h3 { margin: 0 0 .25rem; font-size: 1.05rem; }
code { font-size: .8rem; word-break: break-all; }
footer { margin-top: 3rem; }
"""

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
    "mimeTypes": {".html": "text/html", ".css": "text/css", ".js": "text/javascript"},
    "routes": [
        {"route": "/index.html", "headers": {"Cache-Control": "public, max-age=300"}},
        {
            "route": "/*.html",
            "headers": {"X-Robots-Tag": "noindex", "Cache-Control": "public, max-age=300"},
        },
    ],
}

SEARCH = """
const box = document.getElementById('find');
if (box) {
  const rows = Array.from(document.querySelectorAll('#everyone tbody tr'));
  box.addEventListener('input', () => {
    const q = box.value.trim().toLowerCase();
    for (const row of rows) row.hidden = q !== '' && !row.dataset.key.includes(q);
  });
}
"""


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


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _page(title: str, body: str, script: bool = False, index: bool = False) -> str:
    tail = "<script src=\"search.js\" defer></script>" if script else ""
    robots = "" if index else "<meta name=\"robots\" content=\"noindex\">"
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"{robots}<title>{_e(title)}</title><link rel=\"stylesheet\" href=\"site.css\">"
        "</head>"
        f"<body><main>{body}<footer class=\"muted\"><p>Finish Line Forecast predicts finish "
        "times and places from public race results only, publishes each prediction before the "
        "gun and the error after it. Names and hometowns are shown only as the results print "
        f"them; to be removed, see <a href=\"{REPOSITORY}/blob/main/docs/data-terms.md\">the "
        f"data terms</a>. <a href=\"{REPOSITORY}\">Source, methods and backtest</a>.</p>"
        f"</footer></main>{tail}</body></html>\n"
    )


def status(files: Sequence[Published], scored: bool, today: date, race_date: date) -> str:
    """One line saying where this race is in its week."""
    if scored:
        return "Scored against the results."
    if any(item.doc.get("kind") != "daily" for item in files):
        return "Final prediction frozen and tagged."
    if files:
        runners = sum(len(item.doc["runners"]) for item in files)
        return f"Prediction week: {len(files)} daily file(s), {runners} runners so far."
    # A date, not a countdown: the site is rebuilt only when something is pushed, so "in 8
    # days" would go stale on every morning nothing is.
    days = (race_date - today).days
    if days > daily.FIRST_LEAD_DAYS:
        start = race_date - timedelta(days=daily.FIRST_LEAD_DAYS)
        return f"Daily predictions start {start.isoformat()}."
    return "Race over; results awaited." if days < 0 else "No prediction yet."


def race_page(race_id: str, record: Mapping[str, Any], files: Sequence[Published],
              scored: bool, today: date) -> str:
    name = str(record.get("name", race_id))
    when = date.fromisoformat(str(record["date"]))
    parts = [
        "<p class=\"muted\"><a href=\"index.html\">All races</a></p>",
        f"<h1>{_e(name)}</h1>",
        f"<p class=\"muted\">{_e(when.strftime('%A %d %B %Y'))}"
        + (f", gun {_e(record['gun'])}" if record.get("gun") else "")
        + f". {_e(status(files, scored, today, when))}</p>",
    ]
    if scored:
        parts.append(
            f"<p><a href=\"{REPOSITORY}/blob/main/docs/predictions/{_e(race_id)}.md\">"
            "The predictions against the results</a>.</p>"
        )
    if not files:
        parts.append("<p>No prediction file has been published for this race yet.</p>")
        return _page(name, "".join(parts))

    final = next((item.doc for item in files if item.doc.get("kind") != "daily"), None)
    if final is not None:
        parts.append(_top(final))

    if final is not None:
        everyone = [(str(r.get("first_published", files[-1].name)), r) for r in final["runners"]]
        heading = "Every runner, as the final file predicts them"
        note = ("The final file recomputes every runner with the day-before forecast; each "
                "daily file keeps the prediction it made.")
    else:
        everyone = [(item.name, r) for item in files for r in item.doc["runners"]]
        heading = "Every runner predicted so far"
        note = ("Each runner is predicted the first morning they are on the entrant list, "
                "with that morning's forecast. The day before the race every runner is "
                "predicted again with the latest forecast, and places are added.")
    everyone.sort(key=lambda item: (item[1]["seconds"], item[1]["name"]))
    rows = []
    for source, runner in everyone:
        low, high = runner["interval_80"]
        key = f"{runner['name']} {runner['hometown'] or ''}".lower()
        rows.append(
            f"<tr data-key=\"{_e(key)}\"><td>{_e(runner['name'])}</td>"
            f"<td>{_e(runner['hometown'] or '')}</td>"
            f"<td class=\"num\">{runner['prior_results']}</td>"
            f"<td class=\"num\">{clock(runner['seconds'])}</td>"
            f"<td>{clock(low)} to {clock(high)}</td><td class=\"muted\">{_e(source)}</td></tr>"
        )
    parts += [
        f"<h2>{_e(heading)}, {len(everyone)}</h2>",
        f"<p class=\"muted\">{_e(note)} The 80% interval is calibrated on past races to "
        "hold the finish four times in five.</p>",
        "<input id=\"find\" type=\"search\" placeholder=\"Find a name or a town\" "
        "aria-label=\"Find a name or a town\">",
        "<div class=\"wrap\"><table id=\"everyone\"><thead><tr><th>Name</th><th>Hometown</th>"
        "<th class=\"num\">Prior results</th><th class=\"num\">Predicted</th>"
        "<th>80% interval</th><th>First published</th></tr></thead><tbody>",
        *rows,
        "</tbody></table></div>",
        "<h2>The files</h2>",
        "<p class=\"muted\">Every prediction above is in one of these files, committed and "
        "tagged in the repository before the gun, and never edited.</p>",
        "<div class=\"wrap\"><table><thead><tr><th>File</th><th>Frozen at</th>"
        "<th class=\"num\">Runners</th><th>SHA-256</th></tr></thead><tbody>",
        *(
            f"<tr><td><a href=\"{REPOSITORY}/blob/main/predictions/"
            f"{_e(race_id + '/' if item.doc.get('kind') == 'daily' else '')}{_e(item.name)}\">"
            f"{_e(item.name)}</a></td><td>{_e(item.doc['frozen_at'])}</td>"
            f"<td class=\"num\">{len(item.doc['runners'])}</td>"
            f"<td><code>{_e(item.sha256)}</code></td></tr>"
            for item in files
        ),
        "</tbody></table></div>",
    ]
    return _page(name, "".join(parts), script=True)


def _top(final: Mapping[str, Any]) -> str:
    """The predicted top of the field, with placeholders where newcomers are expected."""
    block = final.get("newcomers") or {}
    likely = set(block.get("likely_places_top_20", []))
    runners = final["runners"]
    named = runners if not block else [r for r in runners if r["prior_results"] > 0]
    queue = iter(sorted(named, key=lambda runner: runner["place"]["median"]))
    rows = []
    for rank in range(1, TOP + 1):
        if rank in likely:
            rows.append(f"<tr class=\"unseen\"><td class=\"num\">{rank}</td>"
                        f"<td colspan=\"5\">{_e(UNSEEN.strip('_'))}</td></tr>")
            continue
        runner = next(queue, None)
        if runner is None:
            break
        place = runner["place"]
        low, high = runner["interval_80"]
        rows.append(
            f"<tr><td class=\"num\">{rank}</td><td>{_e(runner['name'])}</td>"
            f"<td>{_e(runner['hometown'] or '')}</td>"
            f"<td class=\"num\">{place['median']:.0f} ({place['low']:.0f} to "
            f"{place['high']:.0f})</td><td class=\"num\">{clock(runner['seconds'])}</td>"
            f"<td>{clock(low)} to {clock(high)}</td></tr>"
        )
    note = ""
    if block:
        ten, twenty = block["expected_in_top_10"], block["expected_in_top_20"]
        note = (
            f"<p class=\"muted\">Runners with no results here are expected to take "
            f"{ten['mean']:.1f} of the top 10 places (80% range {ten['low']} to {ten['high']}) "
            f"and {twenty['mean']:.1f} of the top 20, judged from how first-timers finished at "
            f"{block['pool_editions']} earlier editions. The entrant list cannot say which "
            "newcomers they will be, so those places are shown as placeholders.</p>"
        )
    return (
        f"<h2>Predicted top {TOP}</h2><p class=\"muted\">Places are simulated from the whole "
        "field sharing one morning; the range is the middle 80% of the simulated places.</p>"
        + note
        + "<div class=\"wrap\"><table><thead><tr><th class=\"num\">Rank</th><th>Name</th>"
        "<th>Hometown</th><th class=\"num\">Place (range)</th><th class=\"num\">Predicted</th>"
        "<th>80% interval</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def index(races: Sequence[tuple[str, Mapping[str, Any], str]]) -> str:
    """Every live race, soonest first, with where it stands."""
    cards = [
        f"<div class=\"card\"><h3><a href=\"{_e(race_id)}.html\">{_e(record.get('name', race_id))}"
        f"</a></h3><div class=\"muted\">{_e(record['date'])}</div><p>{_e(line)}</p></div>"
        for race_id, record, line in races
    ]
    body = (
        "<h1>Finish Line Forecast</h1>"
        "<p>Before the gun, a predicted finish time and place for every registered runner at "
        "Newfoundland road races, from their public race history, each with an honest "
        "interval. After the race, the error, published beside the prediction.</p>"
        "<h2>Races</h2><div class=\"cards\">" + "".join(cards) + "</div>"
    )
    return _page("Finish Line Forecast", body, index=True)


def build(out: Path, live: Path, directory: Path, scores: Path, today: date) -> list[Path]:
    """Write the whole site; returns the pages written."""
    records: dict[str, Any] = tomllib.loads(live.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    listed: list[tuple[str, Mapping[str, Any], str]] = []
    for race_id in sorted(records, key=lambda rid: str(records[rid]["date"])):
        record = records[race_id]
        files = files_for(directory, race_id)
        scored = (scores / f"{race_id}.json").exists()
        when = date.fromisoformat(str(record["date"]))
        page = out / f"{race_id}.html"
        page.write_text(race_page(race_id, record, files, scored, today), encoding="utf-8",
                        newline="\n")
        written.append(page)
        listed.append((race_id, record, status(files, scored, today, when)))
    front = out / "index.html"
    front.write_text(index(listed), encoding="utf-8", newline="\n")
    (out / "site.css").write_text(STYLE.lstrip(), encoding="utf-8", newline="\n")
    (out / "search.js").write_text(SEARCH.lstrip(), encoding="utf-8", newline="\n")
    (out / "staticwebapp.config.json").write_text(
        json.dumps(HOST_CONFIG, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return [front, *written]
