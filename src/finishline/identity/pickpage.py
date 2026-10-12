"""The page `finishline review <race>` serves: refused entrants beside who they might be.

One card per entrant the linker refused, with every runner of that name next to it: where
and when they raced, the towns and age bands their results printed, the age those bands allow
on race day, and whether they have run this course. A button gives the entrant to one of
them, or to nobody, and `identity.picks` writes it down. The next prediction file reads it.

⚠️ **It runs on this machine and nowhere else.** The page puts named people's whole racing
histories side by side to decide which of them entered a race, which is more than any results
page says about them. So the server listens on the loopback address only, answers only to
the address it printed (a page on the web cannot be pointed at it by a made-up host name),
and wants the token in that address on every request (a page on the web cannot post to it
either). Nothing here is built into the public site.

⚠️ **A pick whose line is already in a tagged file is locked.** The file said who the entrant
was; changing the pick afterwards would leave a published line standing on a history this
project no longer believes, with nothing in the next file to say so where both candidates
have the same number of results (`publish/daily.py` re-issues on that number alone). A locked
pick that is wrong is corrected by hand, in the picks file, and written up.

An entrant can also have a line from before the linker refused them (PLAN.md 13 item 46: a
listed sex the archive overruled turned a newcomer into one of two runners). That line was
not made by a pick and does not lock one: picking a runner re-issues the line in the next
daily file, marked with the file it supersedes, exactly as that item describes.
"""

from __future__ import annotations

import json
import secrets
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from finishline.identity import link, picks
from finishline.identity.normalise import name_key
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant
from finishline.schema import Race


class Refused(ValueError):
    """A decision the page asked for that cannot be made."""


class Desk:
    """One race's refused entrants, and the picks file they are decided into."""

    def __init__(
        self,
        race: Race,
        entered: Sequence[Entrant],
        runners: Sequence[Runner],
        races: Mapping[str, Race],
        path: Path,
        published: Mapping[str, tuple[str, bool]],
        today: date,
    ) -> None:
        self.race = race
        self.entered = list(entered)
        self.runners = list(runners)
        self.races = races
        self.path = path
        # Name key to the daily file that entrant's standing line is in, and whether a pick
        # made that line. Only a line a pick made locks the pick.
        self.earlier = {key: name for key, (name, _) in published.items()}
        self.published = {key: name for key, (name, by_hand) in published.items() if by_hand}
        self.today = today
        self.archive = link.index(self.runners)
        self.shared = Counter(name_key(entrant.name) for entrant in self.entered)
        # What the rules alone say: the cards are the entrants refused here, picked or not.
        self.refused = [
            item
            for item in link.link(self.entered, self.runners)
            if item.status is link.Status.AMBIGUOUS
        ]

    def cases(self) -> dict[str, Any]:
        """Everything the page draws."""
        made = {pick.key: pick for pick in picks.load(self.path)}
        cards = []
        drawn: set[str] = set()
        for item in self.refused:
            entrant = item.entrant
            key = name_key(entrant.name)
            # A name the list prints twice is one card that says so, not two identical ones.
            if key in drawn:
                continue
            drawn.add(key)
            everyone = link.candidates_for(entrant, self.archive)
            committed = [runner for runner in everyone if not runner.ambiguous]
            unplaced = [runner for runner in everyone if runner.ambiguous]
            pick = made.get(key)
            chosen = None if pick is None else pick.among(committed)
            cards.append({
                "entrant": entrant.name,
                "sex": entrant.sex or "",
                "town": entrant.hometown or "",
                "reason": item.reason,
                "listed": self.shared[key],
                "decidable": self.shared[key] == 1,
                "published": self.published.get(key),
                "earlier": None if key in self.published else self.earlier.get(key),
                "candidates": [
                    picks.candidate(runner, self.races, self.race) for runner in committed
                ],
                "unplaced": sorted(
                    (
                        row
                        for runner in unplaced
                        for row in picks.candidate(runner, self.races, self.race)["results"]
                    ),
                    key=lambda row: str(row["date"]),
                    reverse=True,
                ),
                "pick": None
                if pick is None
                else {
                    "choice": pick.choice,
                    "candidate": None if chosen is None else chosen.runner_id,
                    "evidence": pick.evidence,
                    "note": pick.note,
                    "picked_on": pick.picked_on,
                    # A pick of a runner the archive no longer holds together decides nothing.
                    "stands": pick.choice == picks.NEWCOMER or chosen is not None,
                },
            })
        return {
            "race": {"name": self.race.name, "date": self.race.date.isoformat()},
            "evidence": picks.EVIDENCE,
            "cards": cards,
        }

    def decide(self, body: Mapping[str, Any]) -> None:
        """Make, change or clear one pick."""
        name = str(body.get("entrant", ""))
        key = name_key(name)
        item = next((x for x in self.refused if name_key(x.entrant.name) == key), None)
        if item is None:
            raise Refused("that entrant is not one the linker refused")
        if self.shared[key] != 1:
            raise Refused("two entrants on the list share this name; a pick cannot say which")
        if key in self.published:
            raise Refused(
                f"this entrant's line is already published in {self.published[key]}; "
                "the pick is locked"
            )
        made = picks.load(self.path)
        action = body.get("action")
        if action == "clear":
            picks.save(self.path, picks.drop(made, name))
            return
        evidence, note = str(body.get("evidence", "")), str(body.get("note", ""))
        try:
            if action == picks.NEWCOMER:
                pick = picks.newcomer(item.entrant.name, evidence, note, self.today)
            elif action == picks.RUNNER:
                runner = next(
                    (
                        runner
                        for runner in link.candidates_for(item.entrant, self.archive)
                        if runner.runner_id == body.get("candidate")
                    ),
                    None,
                )
                if runner is None:
                    raise Refused("that runner is not one of this entrant's candidates")
                pick = picks.for_runner(
                    item.entrant.name, runner, self.races, evidence, note, self.today
                )
            else:
                raise Refused(f"{action!r} is not something this page does")
        except ValueError as problem:
            raise Refused(str(problem)) from problem
        if evidence == "other" and not pick.note:
            raise Refused("say in the note what the pick was made on")
        picks.save(self.path, picks.put(made, pick))


def serve(desk: Desk, port: int) -> None:
    """Serve the page until interrupted, printing the one address that opens it."""
    token = secrets.token_urlsafe(24)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, kind: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "connect-src 'self'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, value: object) -> None:
            self._send(status, "application/json", json.dumps(value).encode("utf-8"))

        def _allowed(self) -> bool:
            return (
                self.headers.get("Host") in hosts
                and secrets.compare_digest(self.headers.get("X-Token", ""), token)
            )

        def do_GET(self) -> None:
            if self.headers.get("Host") not in hosts:
                self._json(403, {"error": "not this address"})
            elif self.path.split("?", 1)[0] == "/":
                # The page itself holds no names; it asks for them with the token.
                self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
            elif self.path == "/cases" and self._allowed():
                self._json(200, desk.cases())
            else:
                self._json(403, {"error": "no"})

        def do_POST(self) -> None:
            if self.path != "/pick" or not self._allowed():
                self._json(403, {"error": "no"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                desk.decide(body)
            except Refused as refusal:
                self._json(409, {"error": str(refusal)})
                return
            except (ValueError, AttributeError):
                self._json(400, {"error": "unreadable request"})
                return
            self._json(200, desk.cases())

        def log_message(self, format: str, *args: Any) -> None:
            """Quiet: the access log would print nothing useful and the token with it."""

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as http:
        print(f"open http://127.0.0.1:{port}/#{token}")
        print("picks are saved as you make them; Ctrl+C stops the page")
        try:
            http.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Review refused entrants</title>
<style>
:root {
  --paper: #faf8f4; --card: #ffffff; --ink: #1d2126; --soft: #4a525c; --faint: #7a828c;
  --line: #e2ddd3; --accent: #0b6b62; --accent-soft: #e2f1ee; --warn: #9a5b00;
  --warn-soft: #fbf0db; --here: #eef6f4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #15181c; --card: #1d2126; --ink: #e9e6df; --soft: #b9bec5; --faint: #8a919a;
    --line: #333941; --accent: #5cc4b8; --accent-soft: #17322f; --warn: #e2b062;
    --warn-soft: #33290f; --here: #1a2a28;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
header, main { max-width: 78rem; margin: 0 auto; padding: 1rem; }
h1 { font-size: 1.5rem; margin: 0.5rem 0 0.25rem; }
h2 { font-size: 1.15rem; margin: 0; }
p { margin: 0.35rem 0; }
.lede { color: var(--soft); max-width: 60rem; }
.bar {
  display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; align-items: center;
  margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid var(--line);
}
.count { font-weight: 600; font-variant-numeric: tabular-nums; }
label { color: var(--soft); }
select, input[type=text], button {
  font: inherit; color: var(--ink); background: var(--card);
  border: 1px solid var(--line); border-radius: 6px; padding: 0.35rem 0.6rem;
}
input[type=text] { width: min(26rem, 100%); }
button { cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: 0.5; cursor: default; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--paper); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem; margin: 0 0 1rem;
}
.card.done { border-left: 4px solid var(--accent); }
.top { display: flex; flex-wrap: wrap; gap: 0.4rem 1rem; align-items: baseline; }
.listed { color: var(--soft); }
.chip {
  font-size: 0.8rem; border-radius: 999px; padding: 0.1rem 0.6rem;
  background: var(--warn-soft); color: var(--warn); white-space: nowrap;
}
.chip.ok { background: var(--accent-soft); color: var(--accent); }
.reason { color: var(--faint); font-size: 0.88rem; }
.controls { display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; align-items: center; margin: 0.75rem 0; }
.people { display: flex; gap: 0.75rem; overflow-x: auto; padding-bottom: 0.25rem; }
.person {
  flex: 1 0 21rem; max-width: 34rem; min-width: 0; border: 1px solid var(--line);
  border-radius: 8px; padding: 0.75rem;
}
.person.chosen { border-color: var(--accent); background: var(--accent-soft); }
.person.unplaced { border-style: dashed; }
.facts { display: grid; grid-template-columns: auto 1fr; gap: 0.1rem 0.75rem; margin: 0.5rem 0; }
.facts dt { color: var(--faint); }
.facts dd { margin: 0; }
.scroll { max-height: 17rem; overflow: auto; border-top: 1px solid var(--line); }
table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
th, td { text-align: left; padding: 0.2rem 0.5rem 0.2rem 0; white-space: nowrap; }
th { color: var(--faint); font-weight: 600; position: sticky; top: 0; background: var(--card); }
.person.chosen th { background: var(--accent-soft); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.here td { background: var(--here); }
.error { color: var(--warn); font-weight: 600; }
.saved { color: var(--accent); }
.hidden { display: none; }
</style>
</head>
<body>
<header>
  <h1 id="title">Review refused entrants</h1>
  <p class="lede">Each entrant below shares a name with more than one runner in the archive, and
  the start list prints no age to tell them apart, so the linker gave them no prediction. Where
  the histories make it plain who entered, pick that runner. The pick is read by the next
  prediction file, the runner's line is marked as resolved by hand, and it cannot be changed
  from here once that file is published. Leave anything doubtful alone: an entrant with no
  pick stays out of the predictions, as now.</p>
  <div class="bar">
    <span class="count" id="count"></span>
    <label><input type="checkbox" id="open-only"> Only entrants with no pick</label>
    <span class="saved" id="saved" role="status">Picks are saved as you make them; there is nothing else to press.</span>
    <span class="error" id="error" role="alert"></span>
  </div>
</header>
<main id="cards"></main>
<script>
(function () {
  "use strict";
  var token = location.hash.slice(1);
  var state = null;

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined && text !== null) { node.textContent = text; }
    return node;
  }
  function add(parent, children) {
    children.forEach(function (child) { if (child) { parent.appendChild(child); } });
    return parent;
  }
  function fail(message) { document.getElementById("error").textContent = message || ""; }

  function call(path, body) {
    var options = { headers: { "X-Token": token } };
    if (body) {
      options.method = "POST";
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    return fetch(path, options).then(function (response) {
      return response.json().then(function (value) {
        if (!response.ok) { throw new Error(value.error || "the request failed"); }
        return value;
      });
    });
  }

  function results(rows) {
    var table = el("table");
    var head = el("tr");
    [["Date", ""], ["Race", ""], ["km", "num"], ["Town", ""], ["Age", ""], ["Time", "num"]]
      .forEach(function (c) { head.appendChild(el("th", { "class": c[1] }, c[0])); });
    table.appendChild(add(el("thead"), [head]));
    var body = el("tbody");
    rows.forEach(function (r) {
      var row = el("tr", r.here ? { "class": "here", title: "This course" } : {});
      add(row, [
        el("td", null, r.date), el("td", null, r.race), el("td", { "class": "num" }, String(r.km)),
        el("td", null, r.town), el("td", null, (r.sex + " " + r.age).trim()),
        el("td", { "class": "num" }, r.time)
      ]);
      body.appendChild(row);
    });
    table.appendChild(body);
    return add(el("div", { "class": "scroll", tabindex: "0" }), [table]);
  }

  function fact(list, label, value) {
    add(list, [el("dt", null, label), el("dd", null, value)]);
  }

  function person(card, who, index, controls) {
    var chosen = card.pick && card.pick.choice === "runner" && card.pick.candidate === who.id;
    var box = el("section", { "class": "person" + (chosen ? " chosen" : "") });
    box.appendChild(el("h3", { style: "margin:0;font-size:1rem" },
      "Runner " + String.fromCharCode(65 + index) + (chosen ? " (picked)" : "")));
    var list = el("dl", { "class": "facts" });
    fact(list, "Finishes", who.finishes + ", " + (who.first === who.last ? who.last : who.first + " to " + who.last));
    fact(list, "This course", who.here ? who.here + (who.here === 1 ? " time" : " times") : "never");
    fact(list, "Age on race day", who.age);
    fact(list, "Sex", who.sex || "not printed");
    fact(list, "Towns", who.towns.length ? who.towns.join("; ") : "none printed");
    box.appendChild(list);
    var button = el("button", { "class": "primary", type: "button" }, chosen ? "Picked" : "Pick this runner");
    button.disabled = chosen || !who.pickable || controls.locked;
    button.addEventListener("click", function () { controls.send("runner", who.id); });
    box.appendChild(button);
    box.appendChild(results(who.results));
    return box;
  }

  function draw() {
    var target = document.getElementById("cards");
    var onlyOpen = document.getElementById("open-only").checked;
    target.textContent = "";
    var decided = state.cards.filter(function (c) { return c.pick && c.pick.stands; }).length;
    document.getElementById("title").textContent =
      state.race.name + ", " + state.race.date + ": refused entrants";
    document.getElementById("count").textContent =
      decided + " of " + state.cards.length + " picked";
    document.title = decided + " of " + state.cards.length + " picked";
    state.cards.forEach(function (card) {
      var stands = card.pick && card.pick.stands;
      if (onlyOpen && stands) { return; }
      var box = el("article", { "class": "card" + (stands ? " done" : "") });
      var top = el("div", { "class": "top" });
      add(top, [
        el("h2", null, card.entrant),
        el("span", { "class": "listed" }, "listed as " + (card.sex || "no sex") + (card.town ? ", " + card.town : "") + (card.listed > 1 ? ", " + card.listed + " times" : "")),
        el("span", { "class": "chip" + (stands ? " ok" : "") },
          !card.pick ? "no pick" :
          !card.pick.stands ? "pick no longer matches the archive" :
          card.pick.choice === "new" ? "picked: a newcomer" : "picked on " + card.pick.picked_on),
        card.published ? el("span", { "class": "chip ok" }, "published in " + card.published + ", locked") : null
      ]);
      box.appendChild(top);
      if (card.earlier) {
        box.appendChild(el("p", { "class": "reason" }, "This entrant has a line in " + card.earlier + " from before the linker refused them. Picking a runner publishes the line again in the next daily file, marked as replacing that one."));
      }
      box.appendChild(el("p", { "class": "reason" }, "The linker: " + card.reason + "."));
      if (!card.decidable) {
        box.appendChild(el("p", { "class": "reason" }, "The entrant list prints this name " + card.listed + " times. It does not say whether that is one person entered twice or different people, so a pick could not say which entry it means, and the buttons are off. These entries stay out of the predictions."));
      }

      var locked = !card.decidable || Boolean(card.published);
      var evidence = el("select", { "aria-label": "What the pick is made on" });
      Object.keys(state.evidence).forEach(function (key) {
        evidence.appendChild(el("option", { value: key }, state.evidence[key]));
      });
      var note = el("input", { type: "text", placeholder: "Note (optional)", "aria-label": "Note" });
      if (card.pick) { evidence.value = card.pick.evidence; note.value = card.pick.note; }
      var controls = {
        locked: locked,
        send: function (action, candidate) {
          fail("");
          call("/pick", {
            entrant: card.entrant, action: action, candidate: candidate,
            evidence: evidence.value, note: note.value
          }).then(function (value) {
            state = value;
            draw();
            document.getElementById("saved").textContent =
              (action === "clear" ? "Cleared and saved: " : "Saved: ") + card.entrant + ".";
          }).catch(function (problem) { fail(card.entrant + ": " + problem.message); });
        }
      };
      var none = el("button", { type: "button" }, "None of these: a newcomer");
      none.disabled = locked;
      none.addEventListener("click", function () { controls.send("new"); });
      var clear = el("button", { type: "button" }, "Clear the pick");
      clear.disabled = locked || !card.pick;
      clear.addEventListener("click", function () { controls.send("clear"); });
      box.appendChild(add(el("div", { "class": "controls" }), [evidence, note, none, clear]));

      var people = el("div", { "class": "people" });
      card.candidates.forEach(function (who, index) {
        people.appendChild(person(card, who, index, controls));
      });
      if (card.unplaced.length) {
        var loose = el("section", { "class": "person unplaced" });
        loose.appendChild(el("h3", { style: "margin:0;font-size:1rem" },
          card.unplaced.length + (card.unplaced.length === 1 ? " result" : " results") + " the archive could not place"));
        loose.appendChild(el("p", { "class": "reason" }, "Results under this name that the resolver would not give to any one runner. They are in no model fit, so they cannot be picked; they are here as evidence."));
        loose.appendChild(results(card.unplaced));
        people.appendChild(loose);
      }
      if (!card.candidates.length) {
        box.appendChild(el("p", { "class": "reason" }, "Nobody of this name is a runner the archive commits to, so there is nobody to pick."));
      }
      box.appendChild(people);
      target.appendChild(box);
    });
  }

  document.getElementById("open-only").addEventListener("change", function () { if (state) { draw(); } });
  if (!token) { fail("Open the address the command printed: it carries the key to this page."); return; }
  call("/cases").then(function (value) { state = value; draw(); })
    .catch(function (problem) { fail(problem.message); });
}());
</script>
</body>
</html>
"""
