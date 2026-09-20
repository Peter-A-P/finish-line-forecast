/* The page, drawn from three data files and nothing else.
 *
 * data/races.json        the live races and where each one stands; names nobody
 * data/results.json      the measured numbers, written by `finishline report` beside the
 *                        README's tables; counts, errors and intervals, no names
 * data/predictions/*.json  the published predictions, one file per race, which name
 *                        runners; robots.txt keeps crawlers out of them
 *
 * No framework and no charting library, like the other project pages on peterparker.ca:
 * every chart is SVG built with the DOM API, so the content security policy can forbid inline
 * scripts and styles outright. Colours live in style.css and never here.
 *
 * ⚠️ Names from the prediction files only ever reach the page through textContent. Nothing
 * here writes HTML from data.
 *
 * This file computes nothing the pipeline could have computed, with one labelled exception:
 * the "borrowing strength" chart is an illustration of shrinkage on invented numbers, and says
 * so in its caption.
 */
"use strict";

(function () {
  var NS = "http://www.w3.org/2000/svg";
  var WIDTH = 880;

  var state = { results: null, races: [], race: null, predictions: {}, query: "" };

  /* Small DOM helpers ---------------------------------------------------------- */

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    if (attrs) { for (var key in attrs) { node.setAttribute(key, attrs[key]); } }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function svg(tag, attrs, text) {
    var node = document.createElementNS(NS, tag);
    if (attrs) { for (var key in attrs) { node.setAttribute(key, String(attrs[key])); } }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function byId(id) { return document.getElementById(id); }

  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } return node; }

  function append(parent, children) {
    for (var i = 0; i < children.length; i++) { if (children[i]) { parent.appendChild(children[i]); } }
    return parent;
  }

  function isNumber(value) { return typeof value === "number" && isFinite(value); }

  /* Formatting ----------------------------------------------------------------- */

  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];

  function clock(seconds) {
    if (!isNumber(seconds)) { return "n/a"; }
    var whole = Math.round(seconds);
    var h = Math.floor(whole / 3600);
    var m = Math.floor((whole % 3600) / 60);
    var s = whole % 60;
    var mm = (h && m < 10 ? "0" : "") + m;
    return (h ? h + ":" : "") + mm + ":" + (s < 10 ? "0" : "") + s;
  }

  function longDate(iso) {
    var parts = iso.split("-");
    return Number(parts[2]) + " " + MONTHS[Number(parts[1]) - 1] + " " + parts[0];
  }

  function shortDate(iso) {
    var parts = iso.split("-");
    return Number(parts[2]) + " " + MONTHS[Number(parts[1]) - 1].slice(0, 3);
  }

  function percent(value, places) {
    return isNumber(value) ? (value * 100).toFixed(places || 0) + "%" : "n/a";
  }

  function count(value) { return isNumber(value) ? Math.round(value).toLocaleString("en-CA") : "n/a"; }

  function distanceLabel(metres) {
    if (Math.abs(metres - 42195) < 60) { return "Marathon"; }
    if (Math.abs(metres - 21097.5) < 60) { return "Half marathon"; }
    if (Math.abs(metres - 16093) < 60) { return "10 miles"; }
    return (metres / 1000) + " km";
  }

  function plural(n, one, many) { return count(n) + " " + (n === 1 ? one : many); }

  /* An error as a reader says it, matching showcase.error_text: seconds under a minute. */
  function errorText(minutes) {
    return minutes < 1 ? Math.round(minutes * 60) + " sec" : minutes.toFixed(1) + " min";
  }

  /* Scales and axes --------------------------------------------------------------- */

  function linear(domain, range) {
    var d0 = domain[0], d1 = domain[1], r0 = range[0], r1 = range[1];
    var f = function (v) { return r0 + (v - d0) * (r1 - r0) / ((d1 - d0) || 1); };
    f.domain = domain;
    return f;
  }

  function ticks(lo, hi, wanted) {
    var span = hi - lo;
    var step = Math.pow(10, Math.floor(Math.log(span / wanted) / Math.LN10));
    var err = span / wanted / step;
    if (err >= 7.5) { step *= 10; } else if (err >= 3.5) { step *= 5; } else if (err >= 1.5) { step *= 2; }
    var out = [];
    for (var v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) { out.push(Math.round(v * 1e9) / 1e9); }
    return out;
  }

  function frame(height, title) {
    var root = svg("svg", {
      viewBox: "0 0 " + WIDTH + " " + height,
      role: "img",
      "aria-label": title,
      preserveAspectRatio: "xMidYMid meet"
    });
    root.appendChild(svg("title", null, title));
    return root;
  }

  function yAxis(root, y, left, right, format, label) {
    var values = ticks(y.domain[0], y.domain[1], 5);
    for (var i = 0; i < values.length; i++) {
      var at = y(values[i]);
      root.appendChild(svg("line", { x1: left, x2: right, y1: at, y2: at, "class": "gridline" }));
      root.appendChild(svg("text", { x: left - 8, y: at + 4, "text-anchor": "end", "class": "tick" }, format(values[i])));
    }
    if (label) {
      root.appendChild(svg("text", { x: left, y: 12, "class": "axis-title" }, label));
    }
  }

  function legend(target, items) {
    var node = clear(byId(target));
    items.forEach(function (item) {
      var entry = el("span", { "class": "legend-item" });
      entry.appendChild(el("span", { "class": "swatch " + item[0], "aria-hidden": "true" }));
      entry.appendChild(document.createTextNode(item[1]));
      node.appendChild(entry);
    });
  }

  /* A readout that follows the pointer or the keyboard over marks in a chart. */
  function hover(mark, readout, text) {
    var show = function () { byId(readout).textContent = text; };
    mark.setAttribute("tabindex", "0");
    mark.setAttribute("aria-label", text);
    mark.addEventListener("mouseenter", show);
    mark.addEventListener("focus", show);
    mark.addEventListener("click", show);
  }

  /* Loading ------------------------------------------------------------------- */

  function getJSON(path) {
    return fetch(path, { credentials: "omit" }).then(function (response) {
      if (!response.ok) { throw new Error(path + " returned " + response.status); }
      return response.json();
    });
  }

  function fail(error) {
    var node = byId("failure");
    node.hidden = false;
    node.textContent = "Part of this page could not load (" + error.message + "). The same " +
      "numbers are in the repository's README.";
  }

  /* ======================================================================== the races */

  function selectRace(id, chosen) {
    var race = null;
    for (var i = 0; i < state.races.length; i++) { if (state.races[i].id === id) { race = state.races[i]; } }
    if (!race) { race = state.races[0]; }
    state.race = race;
    byId("race").value = race.id;
    if (chosen && window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "#" + race.id);
    }
    drawRaceCard(race);
    drawWeek(race);
    drawPreview(race);
    drawHistory(race);
    var find = byId("find");
    if (race.retrospect) {
      find.disabled = false;
      loadRetrospect(race);
    } else if (race.predictions) {
      find.disabled = false;
      loadPredictions(race);
    } else {
      find.disabled = true;
      find.value = "";
      clear(byId("predictions"));
      byId("predictions").appendChild(el("p", { "class": "note" },
        race.predicted
          ? "No prediction has been published for this race yet. " + race.status +
            " Until then, the model's record on the same course is below."
          : race.status));
    }
  }

  /* The measured block for a race. A race already run keeps its numbers under `closed`
     rather than `races`, because nothing about it is a prediction and the two must not be
     reachable by the same key by accident. Both carry the same course facts. */
  function story(race) {
    if (!state.results) { return null; }
    var live = state.results.races && state.results.races[race.id];
    if (live) { return live; }
    return (state.results.closed && state.results.closed[race.id]) || null;
  }

  function absPct(value) { return Math.abs(value * 100).toFixed(1) + "%"; }

  /* An interval that straddles zero is printed signed, because "0.2% to 0.8%" would hide the
     one thing it says: that the measurement did not settle which side of level this is. */
  function intervalText(low, high) {
    if (!isNumber(low) || !isNumber(high)) { return ""; }
    if (low <= 0 && high >= 0) {
      return " (95% interval " + (low < 0 ? "-" : "+") + absPct(low) + " to +" + absPct(high) + ")";
    }
    var ends = [Math.abs(low), Math.abs(high)].sort(function (a, b) { return a - b; });
    return " (95% interval " + absPct(ends[0]) + " to " + absPct(ends[1]) + ")";
  }

  /* The course fact, in two parts. The headline is the course against the other courses of
     its own length, which is the comparison a reader has in mind; the note carries the figure
     against an equal-VDOT flat time, which is the same fit with the race length still inside
     it. A course alone at its length has only the second, and says so. PLAN.md 13 item 36. */
  function courseFact(info) {
    if (!isNumber(info.factor)) { return ["Not enough history to measure", null]; }
    var length = info.length || distanceLabel(info.distance_m || 0);
    var flat = absPct(info.factor) + (info.factor >= 0 ? " slower" : " faster") +
      " than an equal-VDOT flat time";
    var span = intervalText(info.factor_low, info.factor_high);
    if (!isNumber(info.versus)) {
      return [flat + span, info.peers
        ? "Measured from the results. Its own length is too thinly covered here to compare against."
        : "Measured from the results. The only " + length + " course on the archive, so there is " +
          "nothing of its own length to compare it with."];
    }
    var others = info.peers === 1 ? "the other " + length + " course" : "other " + length + " courses";
    var against = info.peers === 1 ? "the only other course of that length"
      : "the " + info.peers + " other courses of that length";
    var clear = info.versus_low > 0 || info.versus_high < 0;
    var value = clear
      ? absPct(info.versus) + (info.versus < 0 ? " faster" : " slower") + " than " + others
      : "about as hard as " + others;
    return [value, "Measured from the results against " + against +
      intervalText(info.versus_low, info.versus_high) +
      ". Against an equal-VDOT flat time for the distance it is " +
      flat.replace(" than an equal-VDOT flat time", "") + span + "."];
  }

  function fact(label, value, note) {
    var box = el("div", { "class": "fact" });
    box.appendChild(el("span", { "class": "fact-label" }, label));
    box.appendChild(el("span", { "class": "fact-value" }, value));
    if (note) { box.appendChild(el("span", { "class": "fact-note" }, note)); }
    return box;
  }

  /* The one thing a reader must not get wrong about an already-run race: nothing here was
     published before the gun. It is the first element in the card, before the name, and it
     is a block of prose rather than a chip, because a chip is the sort of thing an eye
     learns to skip. */
  function notAPrediction(race, info) {
    var box = el("div", { "class": "race-warning" });
    box.appendChild(el("strong", null, "No prediction was tagged before this gun."));
    box.appendChild(el("p", null,
      "This race was run on " + longDate(race.date) + ", before this project published " +
      "anything, so it is not part of the record below and never will be. What is shown is " +
      "what the model would have said: the rolling-origin backtest's own rows for this race, " +
      "made by a fit that had seen no result from the quarter the race falls in or later."));
    if (info && info.unscored && info.unscored.length) {
      /* Longest first, and named by their distance rather than by the results page's title,
         which prefixes every one of them with the same three letters. */
      var names = info.unscored.slice()
        .sort(function (a, b) { return b.distance_m - a.distance_m; })
        .map(function (u) { return distanceLabel(u.distance_m).toLowerCase(); });
      var listed = names.length > 1
        ? names.slice(0, -1).join(", ") + " and " + names[names.length - 1]
        : names[0];
      box.appendChild(el("p", null,
        "The same morning's " + listed + " ran on roads with no earlier edition in the " +
        "archive, so the model had no course difficulty for them at all. An error measured " +
        "there is mostly the cost of the missing course, so those events are not scored here."));
    }
    return box;
  }

  function drawRaceCard(race) {
    var card = clear(byId("race-card"));
    var info = story(race) || {};
    if (race.stage === "retrospect") { card.appendChild(notAPrediction(race, info)); }
    var head = el("div", { "class": "race-head" });
    head.appendChild(el("h3", null, race.name));
    var gun = race.gun ? race.gun.slice(11, 16) : null;
    head.appendChild(el("p", { "class": "race-when" },
      longDate(race.date) + (gun ? ", gun at " + gun + " local time" : "") +
      (race.place ? ", " + race.place : "")));
    head.appendChild(el("p", { "class": "race-status stage-" + race.stage }, race.status));
    card.appendChild(head);

    if (race.stage === "calendar") {
      var note = el("p", { "class": "note" },
        "This project reads the association's calendar so that the list of races here is the " +
        "season as it is, not the part of it with a prediction attached. It predicts a race " +
        "only where the organisers publish an entrant list, because without one there is no " +
        "field to predict.");
      card.appendChild(note);
      if (race.url) {
        card.appendChild(append(el("p", { "class": "note" }),
          [el("a", { href: race.url, rel: "nofollow noopener" }, "The organisers' own page for this race")]));
      }
      return;
    }

    var facts = el("div", { "class": "facts" });
    facts.appendChild(fact("Distance", distanceLabel(race.distance_m)));
    var course = courseFact(info);
    facts.appendChild(fact("Course", course[0], course[1]));
    if (isNumber(info.climb_m)) {
      facts.appendChild(fact("Climb and drop", info.climb_m + " m up, " + info.drop_m + " m down"));
    }
    var editions = info.editions || [];
    if (editions.length) {
      var fastest = editions.reduce(function (a, b) { return b.fastest_s < a.fastest_s ? b : a; });
      facts.appendChild(fact("Editions read", String(editions.length),
        "since " + editions[0].date.slice(0, 4) + "; fastest finish " + clock(fastest.fastest_s) +
        " in " + fastest.date.slice(0, 4)));
    }
    if (race.forecast && isNumber(race.forecast.temp_c)) {
      facts.appendChild(fact("Forecast used", Math.round(race.forecast.temp_c) + " C" +
        (isNumber(race.forecast.wind_kmh) ? ", wind " + Math.round(race.forecast.wind_kmh) + " km/h" : ""),
        "from the file frozen for this race"));
    }
    card.appendChild(facts);

    if (info.attendance) { card.appendChild(attendanceBlock(info.attendance)); }
    if (info.entrants) { card.appendChild(fieldBar(info.entrants)); }
    else if (!race.entrant_list && race.predicted) {
      card.appendChild(el("p", { "class": "note" },
        "This race publishes no entrant list, so who will run has to be predicted too. That " +
        "participation model is not built yet, and this race's predictions will say so."));
    }
    if (race.newcomer_pool) {
      card.appendChild(el("p", { "class": "note" },
        "One of the biggest races: runners from away with no results here are drawn from how " +
        "this course's past first-timers finished, so they can take their share of the top places."));
    }
  }

  /* The start list against the finish list. This is the number a race director asks for and
     the one a prediction cannot supply on its own: how many of the people who entered
     actually came. It is reported apart from the prediction error on purpose, because
     folding the two together would let a good prediction hide a bad guess at the field. */
  function attendanceBlock(a) {
    var box = el("div", { "class": "field" });
    box.appendChild(el("p", { "class": "field-title" },
      "The start list against the finish list"));
    var facts = el("div", { "class": "facts" });
    append(facts, [
      fact("On the start list", count(a.listed), "the last look before the gun"),
      fact("Finished", count(a.finished), "on the official results page"),
      fact("Listed and finished", count(a.found),
        percent(1 - a.found / a.listed, 1) + " of the list did not finish under a name on it, " +
        "which is an upper bound on no-shows: it also holds anyone who started and stopped, " +
        "and anyone whose name the two pages spelled differently"),
      fact("Finished, not on that list", count(a.not_listed),
        a.switched
          ? count(a.switched) + " of them were on another distance's list that morning, so a " +
            "change of event rather than a late entry"
          : "late entries, or a name printed two ways")
    ]);
    box.appendChild(facts);
    return box;
  }

  var DEPTHS = [
    ["4 or more", "4 or more past races", "d4"],
    ["2 to 3", "2 or 3 past races", "d2"],
    ["1", "1 past race", "d1"],
    ["0", "first race here", "d0"]
  ];

  /* Who is on the list, by how much history they bring: one stacked bar. */
  function fieldBar(entrants) {
    var box = el("div", { "class": "field" });
    var total = entrants.listed;
    box.appendChild(el("p", { "class": "field-title" },
      plural(total, "runner", "runners") + " on the entrant list on " + longDate(entrants.as_of) +
      ", by how much history the archive has for them"));
    var root = frame(46, "Entrants by number of past races");
    var x = 0;
    var parts = DEPTHS.map(function (d) { return [d[1], entrants.depth[d[0]] || 0, d[2]]; });
    parts.push(["cannot be told apart, left out", entrants.refused || 0, "dx"]);
    parts.forEach(function (part) {
      if (!part[1]) { return; }
      var w = WIDTH * part[1] / total;
      root.appendChild(svg("rect", { x: x, y: 4, width: Math.max(w - 1.5, 0.5), height: 38, rx: 3, "class": "seg " + part[2] }));
      if (w > 60) {
        root.appendChild(svg("text", { x: x + 8, y: 28, "class": "seg-label" }, count(part[1])));
      }
      x += w;
    });
    box.appendChild(root);
    var keys = el("div", { "class": "legend" });
    parts.forEach(function (part) {
      var entry = el("span", { "class": "legend-item" });
      entry.appendChild(el("span", { "class": "swatch solid sw-" + part[2], "aria-hidden": "true" }));
      entry.appendChild(document.createTextNode(part[0] + ": " + count(part[1])));
      keys.appendChild(entry);
    });
    box.appendChild(keys);
    return box;
  }

  /* The prediction week, as five steps, with where the race is now. */
  function drawWeek(race) {
    var node = clear(byId("week"));
    /* The prediction week belongs to a race this project predicts. Drawing it for a race
       already run, or for one on the calendar with no entrant list, would promise a
       timetable that is not going to happen. */
    if (!race.predicted) { node.hidden = true; return; }
    node.hidden = false;
    var order = ["before", "week", "final", "run", "scored"];
    var at = order.indexOf(race.stage);
    var steps = [
      ["Daily predictions", "from " + shortDate(race.week_start), 1],
      ["Final file with places", "by " + shortDate(race.final_by), 2],
      ["Race day", shortDate(race.date), 3],
      ["Scored", "when results are posted", 4]
    ];
    var list = el("ol", { "class": "week-steps" });
    steps.forEach(function (step) {
      var cls = step[2] < at ? "done" : step[2] === at ? "now" : "next";
      if (step[2] === 1 && at === 0) { cls = "next"; }
      var item = el("li", { "class": cls });
      item.appendChild(el("strong", null, step[0]));
      item.appendChild(el("span", null, step[1]));
      list.appendChild(item);
    });
    node.appendChild(list);
  }

  /* Published predictions ---------------------------------------------------------- */

  function loadPredictions(race) {
    var target = clear(byId("predictions"));
    target.appendChild(el("p", { "class": "note" }, "Loading the published predictions..."));
    if (state.predictions[race.id]) { drawPredictions(race, state.predictions[race.id]); return; }
    getJSON(race.predictions).then(function (data) {
      state.predictions[race.id] = data;
      if (state.race && state.race.id === race.id) { drawPredictions(race, data); }
    }).catch(fail);
  }

  function drawPredictions(race, data) {
    var target = clear(byId("predictions"));
    var runners = data.runners;
    var stats = el("div", { "class": "headline" });
    var known = runners.filter(function (r) { return r.prior > 0; }).length;
    var times = runners.map(function (r) { return r.seconds; }).sort(function (a, b) { return a - b; });
    append(stats, [
      stat(count(runners.length), data.final ? "runners in the final prediction" : "runners predicted so far"),
      stat(clock(times[Math.floor(times.length / 2)]), "the middle of the predicted field"),
      stat(count(known), "have raced here before; " + count(runners.length - known) + " are predicted from their age group alone")
    ]);
    target.appendChild(stats);

    target.appendChild(el("h3", null, "The predicted field"));
    var fig = el("figure", { "class": "chart-figure" });
    var chart = el("div", { id: "field-chart", "class": "chart" });
    fig.appendChild(chart);
    fig.appendChild(el("p", { id: "field-readout", "class": "readout" }));
    fig.appendChild(el("figcaption", null, "How many runners are predicted to finish in each minute. Search for a name above to see where that runner sits, with their 80% range."));
    target.appendChild(fig);
    drawField(runners, null);

    if (data.final) { target.appendChild(topTable(data)); }

    target.appendChild(el("h3", null, data.final ? "Every runner, as the final file predicts them" : "Every runner predicted so far"));
    target.appendChild(el("p", { "class": "note" }, data.final ?
      "The final file predicts every runner again with the day-before forecast. The file each runner first appeared in is kept beside them." :
      "Each runner is predicted the first morning they are on the entrant list, with that morning's forecast. The day before the race everyone is predicted again, and given places."));
    var wrap = el("div", { "class": "table-wrap tall" });
    var table = el("table", { id: "everyone", "class": "tight" });
    var head = el("tr");
    ["Name", "Hometown", "Past races", "Predicted", "80% range"].concat(data.final ? ["Place"] : []).concat(["First published"])
      .forEach(function (label, i) { head.appendChild(el("th", { "class": i >= 2 && i <= 3 ? "num" : "" }, label)); });
    table.appendChild(append(el("thead"), [head]));
    var body = el("tbody");
    runners.forEach(function (r) {
      var row = el("tr");
      row.setAttribute("data-key", (r.name + " " + (r.hometown || "")).toLowerCase());
      append(row, [
        el("td", null, r.name), el("td", null, r.hometown || ""),
        el("td", { "class": "num" }, r.prior), el("td", { "class": "num" }, clock(r.seconds)),
        el("td", null, clock(r.i80[0]) + " to " + clock(r.i80[1]))
      ]);
      if (data.final) {
        row.appendChild(el("td", null, r.place ? Math.round(r.place.median) + " (" + Math.round(r.place.low) + " to " + Math.round(r.place.high) + ")" : ""));
      }
      row.appendChild(el("td", { "class": "muted-cell" }, r.file));
      row.addEventListener("click", function () { drawField(runners, r); });
      body.appendChild(row);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    target.appendChild(wrap);
    target.appendChild(el("p", { id: "find-count", "class": "note" }));

    target.appendChild(el("h3", null, "The files"));
    target.appendChild(el("p", { "class": "note" }, "Every prediction above is in one of these files, committed and tagged in the public repository before the gun, and never edited. The SHA-256 is the file's fingerprint."));
    var files = el("div", { "class": "table-wrap" });
    var ft = el("table", { "class": "tight" });
    var fh = el("tr");
    ["File", "Frozen at", "Runners", "SHA-256"].forEach(function (label, i) { fh.appendChild(el("th", { "class": i === 2 ? "num" : "" }, label)); });
    ft.appendChild(append(el("thead"), [fh]));
    var fb = el("tbody");
    race.files.forEach(function (file) {
      var link = el("a", { href: file.url }, file.name);
      var row = el("tr");
      append(row, [append(el("td"), [link]), el("td", null, file.frozen_at.replace("T", " ").slice(0, 16)),
        el("td", { "class": "num" }, file.runners), el("td", { "class": "hash" }, file.sha256)]);
      fb.appendChild(row);
    });
    ft.appendChild(fb);
    files.appendChild(ft);
    target.appendChild(files);
    if (race.scorecard) {
      target.appendChild(append(el("p"), [el("a", { href: race.scorecard }, "The predictions against the official results")]));
    }
    applySearch();
  }

  /* A race already run, runner by runner --------------------------------------------- */

  function loadRetrospect(race) {
    var target = clear(byId("predictions"));
    target.appendChild(el("p", { "class": "note" }, "Loading this race..."));
    if (state.predictions[race.id]) { drawRetrospect(race, state.predictions[race.id]); return; }
    getJSON(race.retrospect).then(function (data) {
      state.predictions[race.id] = data;
      if (state.race && state.race.id === race.id) { drawRetrospect(race, data); }
    }).catch(fail);
  }

  function signedClock(seconds) {
    if (!isNumber(seconds)) { return ""; }
    return (seconds > 0 ? "+" : seconds < 0 ? "-" : "") + clock(Math.abs(seconds));
  }

  function drawRetrospect(race, data) {
    var target = clear(byId("predictions"));
    var info = story(race) || {};
    var runners = data.runners;

    var stats = el("div", { "class": "headline" });
    append(stats, [
      stat(errorText(info.mae_min), "average miss over " + count(info.scored) + " runners, " +
        "first-timers included"),
      info.paired ? stat(errorText(info.paired_model_min) + " vs " + errorText(info.paired_baseline_min),
        "the model against \"you will run what you ran last time\", on the " + count(info.paired) +
        " runners both could answer for") : null,
      isNumber(info.coverage80) ? stat(percent(info.coverage80, 0),
        "of finishes landed inside the 80% range, which promises 80%") : null,
      stat(info.median_places_out + " places", "the middle miss on where a runner finished in " +
        "the field; the average is " + info.places_out)
    ]);
    target.appendChild(stats);

    if (info.ambiguous) {
      target.appendChild(el("p", { "class": "note" },
        count(info.finishers) + " people finished and " + count(info.scored) + " are below. The " +
        count(info.ambiguous) + " missing are finishers the archive cannot tell apart from " +
        "another runner of the same name, which is the same rule that keeps them out of every " +
        "other number on this page."));
    }

    if (info.bands && info.bands.length) { target.appendChild(bandTable(info.bands)); }

    target.appendChild(el("h3", null, "Every runner, against what the model would have said"));
    target.appendChild(el("p", { "class": "note" },
      "Sorted by finishing time. \"Out by\" is the prediction minus the finish, so a minus " +
      "sign means the model called that runner faster than they ran. The 80% range is green " +
      "where the finish landed inside it, which is the one promise made about a single " +
      "runner; " + percent(info.coverage80, 0) + " of them did, against the 80% promised."));
    target.appendChild(el("p", { "class": "note" },
      "\"Finished\" is the place the results page printed, in the race everybody ran. The two " +
      "place columns after it count only the " + count(info.scored) + " runners in this " +
      "table, because a finisher with no prediction cannot be out by any number of places. " +
      "That is why somebody can finish second and be predicted first and nought places out: " +
      "the runner who beat them is one of the " + count(info.ambiguous) + " the archive " +
      "cannot identify. The predicted place has no range either, because a published place is " +
      "drawn from thousands of simulated races and the backtest kept its scored rows rather " +
      "than the fits that would let that be redone here."));

    var wrap = el("div", { "class": "table-wrap tall" });
    var table = el("table", { id: "everyone", "class": "tight" });
    var head = el("tr");
    /* Two place scales sit in this table and they are not the same scale. "Finished" is the
       race everybody ran; the last three columns count only the runners with a prediction.
       The actual place is a column rather than a number to be inferred, because without it
       "finished second, predicted first, nought places out" reads as an off-by-one, which is
       how it read to the person who built it. The note under the table says which is which. */
    var NUMERIC = { 0: 1, 2: 1, 3: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1 };
    ["Finished", "Name", "Past races", "Predicted", "80% range", "Actual", "Out by",
      "Predicted place", "Actual place", "Places out"]
      .forEach(function (label, i) { head.appendChild(el("th", { "class": NUMERIC[i] ? "num" : "" }, label)); });
    table.appendChild(append(el("thead"), [head]));
    var body = el("tbody");
    runners.forEach(function (r) {
      var row = el("tr");
      row.setAttribute("data-key", r.name.toLowerCase());
      /* Green marks the one promise this project makes about a single runner: that the
         finish would land inside the published range. It used to mark a miss under a
         minute, which is a threshold nobody declared and which this project does not
         measure, so a runner whose finish was inside their range could read as a failure. */
      var held = r.i80 && r.i80[0] <= r.actual && r.actual <= r.i80[1];
      append(row, [
        el("td", { "class": "num" }, isNumber(r.finish_place) ? String(r.finish_place) : ""),
        el("td", null, r.name),
        el("td", { "class": "num" }, String(r.prior)),
        el("td", { "class": "num" }, clock(r.seconds)),
        el("td", { "class": held ? "close" : "" },
          r.i80 ? clock(r.i80[0]) + " to " + clock(r.i80[1]) : ""),
        el("td", { "class": "num" }, clock(r.actual)),
        el("td", { "class": "num" }, signedClock(r.out_by)),
        el("td", { "class": "num" }, String(r.place)),
        el("td", { "class": "num" }, String(r.actual_place)),
        el("td", { "class": "num" }, (r.places_out > 0 ? "+" : "") + r.places_out)
      ]);
      row.addEventListener("click", function () { drawField(runners, r); });
      body.appendChild(row);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    target.appendChild(wrap);
    target.appendChild(el("p", { id: "find-count", "class": "note" }));
    applySearch();
  }

  /* The error by where a runner finished in their own field: the same three bands the rest
     of the page uses, so moving between this race and the archive-wide figures is not a
     change of subject. Both units are shown, because the minutes grow down the field and the
     share of a finish time need not. */
  function bandTable(bands) {
    var box = el("div");
    box.appendChild(el("h3", null, "Where the misses were"));
    box.appendChild(el("p", { "class": "note" },
      "A five-minute miss is not the same claim for somebody racing the front of the field as " +
      "for somebody out on the road twice as long, so the same error is given in minutes and " +
      "as a share of that runner's own finish time."));
    var wrap = el("div", { "class": "table-wrap" });
    var table = el("table", { "class": "tight" });
    var head = el("tr");
    ["Part of the field", "Runners", "Average miss", "As a share of their time", "Places out"]
      .forEach(function (label, i) { head.appendChild(el("th", { "class": i ? "num" : "" }, label)); });
    table.appendChild(append(el("thead"), [head]));
    var body = el("tbody");
    bands.forEach(function (b) {
      var row = el("tr");
      append(row, [
        el("td", null, b.label + " (" + b.note + ")"),
        el("td", { "class": "num" }, count(b.runners)),
        el("td", { "class": "num" }, errorText(b.mae_min)),
        el("td", { "class": "num" }, percent(b.mape, 1)),
        el("td", { "class": "num" }, b.places_out.toFixed(1))
      ]);
      body.appendChild(row);
    });
    table.appendChild(body);
    wrap.appendChild(table);
    box.appendChild(wrap);
    return box;
  }

  function stat(figure, caption) {
    var box = el("div", { "class": "stat" });
    box.appendChild(el("span", { "class": "figure" }, figure));
    box.appendChild(el("span", { "class": "caption" }, caption));
    return box;
  }

  function topTable(data) {
    var box = el("div");
    box.appendChild(el("h3", null, "Predicted top 20"));
    var block = data.newcomers;
    box.appendChild(el("p", { "class": "note" }, "Places are simulated from the whole field sharing one morning; the range is the middle 80% of the simulated places." +
      (block ? " Runners with no results here are expected to take " + block.expected_in_top_10.mean.toFixed(1) +
        " of the top 10 and " + block.expected_in_top_20.mean.toFixed(1) + " of the top 20, judged from " +
        block.pool_editions + " earlier editions. Nothing on the entrant list says which newcomers they will be, so those places are placeholders." : "")));
    var likely = {};
    ((block && block.likely_places_top_20) || []).forEach(function (p) { likely[p] = true; });
    var named = data.runners.filter(function (r) { return r.place && (!block || r.prior > 0); })
      .sort(function (a, b) { return a.place.median - b.place.median; });
    var wrap = el("div", { "class": "table-wrap" });
    var table = el("table", { "class": "tight" });
    var head = el("tr");
    ["Rank", "Name", "Hometown", "Place range", "Predicted", "80% range"].forEach(function (label, i) { head.appendChild(el("th", { "class": i === 0 || i === 4 ? "num" : "" }, label)); });
    table.appendChild(append(el("thead"), [head]));
    var body = el("tbody");
    var next = 0;
    for (var rank = 1; rank <= 20; rank++) {
      var row = el("tr");
      if (likely[rank]) {
        row.setAttribute("class", "unseen");
        append(row, [el("td", { "class": "num" }, rank), el("td", { colspan: "5" }, "a runner with no results here")]);
      } else {
        var r = named[next++];
        if (!r) { break; }
        append(row, [el("td", { "class": "num" }, rank), el("td", null, r.name), el("td", null, r.hometown || ""),
          el("td", null, Math.round(r.place.low) + " to " + Math.round(r.place.high)),
          el("td", { "class": "num" }, clock(r.seconds)), el("td", null, clock(r.i80[0]) + " to " + clock(r.i80[1]))]);
      }
      body.appendChild(row);
    }
    table.appendChild(body);
    wrap.appendChild(table);
    box.appendChild(wrap);
    return box;
  }

  /* The field as a histogram of predicted minutes, with one runner marked if chosen. */
  function drawField(runners, chosen) {
    var node = byId("field-chart");
    if (!node) { return; }
    clear(node);
    var minutes = runners.map(function (r) { return r.seconds / 60; });
    var lo = Math.floor(Math.min.apply(null, minutes));
    var hi = Math.ceil(Math.max.apply(null, minutes));
    var width = Math.max(1, Math.ceil((hi - lo) / 60));
    var bins = {};
    minutes.forEach(function (m) { var b = Math.floor((m - lo) / width); bins[b] = (bins[b] || 0) + 1; });
    var top = 0;
    for (var k in bins) { top = Math.max(top, bins[k]); }
    var H = 240, L = 48, R = WIDTH - 12, T = 16, B = H - 30;
    var root = frame(H, "How many runners are predicted to finish in each minute");
    var x = linear([lo, hi + width], [L, R]);
    var y = linear([0, top], [B, T]);
    yAxis(root, y, L, R, function (v) { return v; }, "runners");
    for (var b in bins) {
      var start = lo + Number(b) * width;
      var bar = svg("rect", { x: x(start) + 0.5, y: y(bins[b]), width: Math.max(x(start + width) - x(start) - 1, 1), height: B - y(bins[b]), "class": "bar lv1" });
      hover(bar, "field-readout", count(bins[b]) + " predicted between " + clock(start * 60) + " and " + clock((start + width) * 60));
      root.appendChild(bar);
    }
    ticks(lo, hi, 8).forEach(function (m) {
      root.appendChild(svg("text", { x: x(m), y: H - 10, "text-anchor": "middle", "class": "tick" }, clock(m * 60)));
    });
    if (chosen) {
      root.appendChild(svg("rect", { x: x(chosen.i80[0] / 60), y: T, width: x(chosen.i80[1] / 60) - x(chosen.i80[0] / 60), height: B - T, "class": "chosen-band" }));
      root.appendChild(svg("line", { x1: x(chosen.seconds / 60), x2: x(chosen.seconds / 60), y1: T, y2: B, "class": "chosen-line" }));
      byId("field-readout").textContent = chosen.name + ": predicted " + clock(chosen.seconds) +
        ", 80% range " + clock(chosen.i80[0]) + " to " + clock(chosen.i80[1]) +
        (chosen.place ? ", place " + Math.round(chosen.place.median) + " (" + Math.round(chosen.place.low) + " to " + Math.round(chosen.place.high) + ")" : "");
    }
    node.appendChild(root);
  }

  function applySearch() {
    var table = byId("everyone");
    if (!table) { return; }
    var q = state.query.trim().toLowerCase();
    var rows = table.tBodies[0].rows;
    var shown = 0, only = null;
    for (var i = 0; i < rows.length; i++) {
      var hit = q === "" || rows[i].getAttribute("data-key").indexOf(q) !== -1;
      rows[i].hidden = !hit;
      if (hit) { shown++; only = i; }
    }
    byId("find-count").textContent = q === "" ? "" : shown + " runner" + (shown === 1 ? "" : "s") + " match. Click a row to mark that runner on the chart.";
    var data = state.predictions[state.race.id];
    if (data && q !== "" && shown === 1) { drawField(data.runners, data.runners[only]); }
    else if (data && q === "") { drawField(data.runners, null); }
  }

  /* How the model did at this course's last backtested edition ---------------------- */

  function drawPreview(race) {
    var info = story(race);
    var bt = info && info.backtest;
    var box = byId("preview");
    box.hidden = !bt;
    if (!bt) { return; }
    var year = bt.date.slice(0, 4);
    var here = race.stage === "retrospect" && bt.date === race.date;
    byId("preview-title").textContent = here
      ? "This race, runner by runner"
      : "How this model did at the " + year + " " + race.name + ", predicted only from races before it";
    byId("preview-lede").textContent = here
      ? "The same rows as the table below, drawn. Each dot is one runner: across is what the model would have said, up is what they actually ran. On the diagonal the two agree. Above it the runner was slower than the model expected, below it faster."
      : "In the backtest, the " + year + " race was predicted as if it were tomorrow, from results dated before it, and then compared with what happened. Each dot is one runner: across is the prediction, up is the actual finish. On the diagonal, the prediction was exact.";
    var stats = clear(byId("preview-stats"));
    append(stats, [
      stat(bt.mae_min.toFixed(1) + " min", "average miss across all " + count(bt.runners) + " finishers, first-timers included"),
      bt.paired ? stat(bt.paired_model_min.toFixed(1) + " vs " + bt.paired_baseline_min.toFixed(1), "minutes, the model against \"last time\", on the " + count(bt.paired) + " runners both could predict") : null,
      isNumber(bt.coverage80) ? stat(percent(bt.coverage80), "of finishes inside their 80% range") : null
    ]);
    var node = clear(byId("preview-chart"));
    var pts = bt.points;
    var all = [];
    pts.forEach(function (p) { all.push(p[0], p[1]); });
    all.sort(function (a, b) { return a - b; });
    var lo = all[Math.floor(all.length * 0.005)] / 60, hi = all[Math.floor(all.length * 0.995) - 1] / 60;
    var pad = (hi - lo) * 0.04;
    lo -= pad; hi += pad;
    var H = 440, L = 58, R = WIDTH - 16, T = 14, B = H - 36;
    var root = frame(H, "Predicted against actual finish times for the " + year + " race");
    var x = linear([lo, hi], [L, R]);
    var y = linear([lo, hi], [B, T]);
    yAxis(root, y, L, R, function (v) { return clock(v * 60); }, "actual finish");
    ticks(lo, hi, 7).forEach(function (m) {
      root.appendChild(svg("text", { x: x(m), y: H - 16, "text-anchor": "middle", "class": "tick" }, clock(m * 60)));
    });
    root.appendChild(svg("text", { x: R, y: H - 2, "text-anchor": "end", "class": "axis-title" }, "predicted finish"));
    root.appendChild(svg("line", { x1: x(lo), y1: y(lo), x2: x(hi), y2: y(hi), "class": "diagonal" }));
    pts.forEach(function (p) {
      var pm = p[0] / 60, am = p[1] / 60;
      if (pm < lo || pm > hi || am < lo || am > hi) { return; }
      var held = isNumber(p[2]) && isNumber(p[3]) ? (p[1] >= p[2] && p[1] <= p[3]) : null;
      var dot = svg("circle", { cx: x(pm), cy: y(am), r: 3.2, "class": "pt " + (held === null ? "pt-none" : held ? "pt-hit" : "pt-miss") });
      var history = p[4] === 0 ? "first race here" : p[4] >= 4 ? "4 or more past races" : p[4] + " past race" + (p[4] === 1 ? "" : "s");
      hover(dot, "preview-readout", "Predicted " + clock(p[0]) + ", ran " + clock(p[1]) + " (" + history + ")" +
        (held === null ? "" : held ? "; inside the 80% range" : "; outside the 80% range"));
      root.appendChild(dot);
    });
    node.appendChild(root);
    legend("preview-legend", [["dot pt-hit-sw", "finish inside its 80% range"], ["dot pt-miss-sw", "outside it"], ["dashed sw-faint", "a perfect prediction"]]);
    byId("preview-caption").textContent = "Every finisher in the " + year + " edition who was in the backtest, shown without names. Most misses above the diagonal are runners who ran slower than their history said: a bad day, an injury, or a friend being paced.";
  }

  /* The race's history, edition by edition ---------------------------------------------- */

  function drawHistory(race) {
    var info = story(race);
    var node = clear(byId("history-chart"));
    var eds = (info && info.editions) || [];
    if (!eds.length) { byId("history-caption").textContent = "No past editions in the archive."; return; }
    /* Tall, and tight around the times. Editions of one race differ by a few percent, which is
       minutes: on a short chart with wide padding those differences flatten into a straight
       line, and the year-to-year swing this chart exists to show disappears. The finisher bars
       get their own band at the bottom so they cannot eat the time axis. */
    var H = 440, L = 58, R = WIDTH - 16, T = 20, B = H - 104, BARS = H - 30;
    var root = frame(H, "Median and fastest finish, and finishers, for each edition of " + race.name);
    var lo = Infinity, hi = 0, most = 0;
    eds.forEach(function (e) { lo = Math.min(lo, e.fastest_s); hi = Math.max(hi, e.median_s); most = Math.max(most, e.finishers); });
    var pad = Math.max((hi - lo) * 0.08, 30) / 60;
    var y = linear([lo / 60 - pad, hi / 60 + pad], [B, T]);
    var step = (R - L) / eds.length;
    var xs = function (i) { return L + step * (i + 0.5); };
    yAxis(root, y, L, R, function (v) { return clock(v * 60); }, "finish time");
    var scale = linear([0, most], [0, 56]);
    var lines = { median_s: [], fastest_s: [] };
    eds.forEach(function (e, i) {
      var h = scale(e.finishers);
      var bar = svg("rect", { x: xs(i) - step * 0.3, y: BARS - h, width: step * 0.6, height: h, "class": "bar lv2" });
      root.appendChild(bar);
      root.appendChild(svg("text", { x: xs(i), y: H - 6, "text-anchor": "middle", "class": "tick" }, "'" + e.date.slice(2, 4)));
      lines.median_s.push([xs(i), y(e.median_s / 60)]);
      lines.fastest_s.push([xs(i), y(e.fastest_s / 60)]);
      var text = e.date.slice(0, 4) + ": " + count(e.finishers) + " finishers, middle of the field " + clock(e.median_s) +
        ", fastest " + clock(e.fastest_s) + (isNumber(e.temp_c) ? ", " + Math.round(e.temp_c) + " C at the airport during the race" : "");
      var hit = svg("rect", { x: xs(i) - step / 2, y: T, width: step, height: BARS - T, "class": "catcher" });
      hover(hit, "history-readout", text);
      root.appendChild(hit);
    });
    [["median_s", "median"], ["fastest_s", "fastest"]].forEach(function (pair) {
      var d = lines[pair[0]].map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
      root.appendChild(svg("path", { d: d, "class": "series " + pair[1] + "-line" }));
      lines[pair[0]].forEach(function (p) { root.appendChild(svg("circle", { cx: p[0], cy: p[1], r: 3.5, "class": "dot " + pair[1] + "-dot" })); });
    });
    root.appendChild(svg("text", { x: L, y: BARS - 38, "class": "axis-title" }, "finishers"));
    node.appendChild(root);
    legend("history-legend", [["sw-median-line", "middle of the field"], ["sw-fastest-line", "fastest finish"], ["solid sw-lv2", "finishers"]]);
    byId("history-caption").textContent = "Every edition of this course in the archive. Point at a year for its finishers, times and morning temperature.";
  }

  /* ================================================================== how it works */

  /* The hero strip: the error at each race length for one part of the field. The page is served
     with one group already in it, so a reader without JavaScript sees numbers; this redraws it
     when the picker changes. Nothing here computes an error: it reads what report measured. */
  function drawHeroDistances(group) {
    var node = byId("hero-distances");
    if (!node || !state.results) { return; }
    var groups = state.results.distance_groups || {};
    var rows = (groups.rows || {})[group] || [];
    clear(node);
    if (!rows.length) {
      node.appendChild(el("span", { "class": "hero-strip-label" }, "Not measured for this part of the field yet."));
      return;
    }
    rows.forEach(function (row) {
      var card = el("span", { "class": "hero-distance" });
      var spread = isNumber(row.median_error_min) && isNumber(row.p90_error_min);
      /* One line each, matching site.hero_distances: a tile is read down, not across. */
      append(card, [
        el("span", { "class": "hd-race" }, row.label),
        el("span", { "class": "hd-min" }, errorText(row.mae_min)),
        el("span", { "class": "hd-pct" }, "avg miss,"),
        el("span", { "class": "hd-pct" }, percent(row.mape, 1) + " of the time"),
        spread ? el("span", { "class": "hd-spread" }, "half within " + errorText(row.median_error_min) + ",") : null,
        spread ? el("span", { "class": "hd-spread" }, "90% within " + errorText(row.p90_error_min)) : null
      ]);
      node.appendChild(card);
    });
  }

  function drawYears(archive) {
    var node = clear(byId("years-chart"));
    var rows = archive.finishes_by_year;
    var first = rows[0][0], last = rows[rows.length - 1][0];
    var map = {};
    var top = 0;
    rows.forEach(function (r) { map[r[0]] = r[1]; top = Math.max(top, r[1]); });
    var H = 250, L = 52, R = WIDTH - 12, T = 16, B = H - 28;
    var root = frame(H, "Finishes read per year, " + first + " to " + last);
    var years = last - first + 1;
    var step = (R - L) / years;
    var y = linear([0, top * 1.08], [B, T]);
    yAxis(root, y, L, R, function (v) { return v >= 1000 ? (v / 1000) + "k" : v; }, "finishes");
    for (var yr = first; yr <= last; yr++) {
      var i = yr - first, value = map[yr] || 0;
      var x = L + step * i;
      if (value) {
        var bar = svg("rect", { x: x + step * 0.15, y: y(value), width: step * 0.7, height: B - y(value), rx: 2, "class": "bar lv1" });
        hover(bar, "years-readout", yr + ": " + count(value) + " finishes");
        root.appendChild(bar);
      } else {
        root.appendChild(svg("text", { x: x + step / 2, y: B - 8, "text-anchor": "middle", "class": "gap-label" }, "no races"));
      }
      if (i % 2 === 0 || yr === last) {
        root.appendChild(svg("text", { x: x + step / 2, y: H - 8, "text-anchor": "middle", "class": "tick" }, yr));
      }
    }
    node.appendChild(root);
  }

  /* Grouped by race length, and it has to be. The factor is measured against Daniels' time
     for VDOT 50 AT THAT DISTANCE, so anything the population does differently from his fade
     over distance lands on the course effects of the long races: read across the whole chart
     and five flat marathons look as hard as Signal Hill. Read down one column and the
     comparison is courses against courses. PLAN.md 13 item 36. */
  function courseText(c) {
    var text = c.name + ", " + (c.length || distanceLabel(c.distance_m)) + ": " +
      (c.factor >= 0 ? "+" : "") + (c.factor * 100).toFixed(1) + "% against an equal-VDOT flat time (95% interval " +
      (c.low * 100).toFixed(1) + " to " + (c.high * 100).toFixed(1) + ")";
    if (isNumber(c.versus)) {
      var others = c.peers === 1 ? "the only other course of this length" :
        "the " + c.peers + " other courses of this length";
      text += ", and " + Math.abs(c.versus * 100).toFixed(1) + "% " + (c.versus < 0 ? "faster" : "slower") +
        " than " + others + " (interval " + Math.abs(c.versus_high * 100).toFixed(1) + " to " +
        Math.abs(c.versus_low * 100).toFixed(1) + ")";
    } else if (c.peers) {
      text += ", and its own length is too thinly covered to compare against";
    } else {
      text += ", the only course of this length on the archive, so there is nothing to compare it with";
    }
    return text + ", from " + count(c.finishes) + " finishes over " + plural(c.editions, "edition", "editions");
  }

  function drawCourses(courses) {
    var node = clear(byId("courses-chart"));
    var H = 430, L = 52, R = WIDTH - 12, T = 26, B = H - 54;
    var root = frame(H, "How much slower than flat each course runs, grouped by race length");
    var lo = 0, hi = 0;
    courses.forEach(function (c) { lo = Math.min(lo, c.low); hi = Math.max(hi, c.high); });
    var y = linear([lo * 100 - 1, hi * 100 + 1], [B, T]);
    yAxis(root, y, L, R, function (v) { return (v > 0 ? "+" : "") + v + "%"; }, "slower than flat");
    root.appendChild(svg("line", { x1: L, x2: R, y1: y(0), y2: y(0), "class": "zero" }));

    var groups = {}, lengths = [];
    courses.forEach(function (c) {
      var key = c.distance_m || 0;
      if (!groups[key]) { groups[key] = []; lengths.push(key); }
      groups[key].push(c);
    });
    lengths.sort(function (a, b) { return a - b; });
    /* A column of one course still needs room for its dot and for its label underneath, and
       eight of the ten lengths hold one or two courses. */
    var weights = lengths.map(function (m) { return Math.max(groups[m].length, 3); });
    var total = weights.reduce(function (a, b) { return a + b; }, 0);
    var labelled = 0, x0 = L;
    lengths.forEach(function (metres, gi) {
      var group = groups[metres].slice().sort(function (a, b) { return b.factor - a.factor; });
      var width = (R - L) * weights[gi] / total;
      if (gi) { root.appendChild(svg("line", { x1: x0, x2: x0, y1: T - 6, y2: B + 6, "class": "divider" })); }
      var mean = group.reduce(function (a, c) { return a + c.factor; }, 0) / group.length;
      root.appendChild(svg("line", {
        x1: x0 + 3, x2: x0 + width - 3, y1: y(mean * 100), y2: y(mean * 100), "class": "nominal"
      }));
      group.forEach(function (c, i) {
        var x = x0 + width * (i + 0.5) / group.length;
        root.appendChild(svg("line", { x1: x, x2: x, y1: y(c.low * 100), y2: y(c.high * 100), "class": "whisker" + (c.live ? " live" : "") }));
        var dot = svg("circle", { cx: x, cy: y(c.factor * 100), r: c.live ? 6 : (c.named ? 5 : 3.8), "class": "course-dot" + (c.live ? " live" : (c.named ? " named" : "")) });
        hover(dot, "courses-readout", courseText(c));
        root.appendChild(dot);
        /* Labelled: the races on this page, and the courses with the deepest history, which
           are the ones a reader goes looking for. Labels alternate above and below the dot,
           and point back into the chart near the right-hand edge. */
        if (c.live || c.named) {
          var end = x > (L + R) / 2;
          var below = labelled % 2 === 1;
          labelled += 1;
          root.appendChild(svg("text", {
            x: x + (end ? -9 : 9),
            y: y(c.factor * 100) + (below ? 20 : -12),
            "text-anchor": end ? "end" : "start",
            "class": "row-label halo" + (c.live ? "" : " faint")
          }, c.name));
        }
      });
      /* Bare numbers, with the unit in the axis title: "16.1 km" does not fit a column of
         two courses, and 16.1 does. */
      var label = metres ? String(Math.round(metres / 100) / 10) : "all";
      root.appendChild(svg("text", { x: x0 + width / 2, y: B + 20, "text-anchor": "middle", "class": "tick" }, label));
      root.appendChild(svg("text", { x: x0 + width / 2, y: B + 34, "text-anchor": "middle", "class": "row-note" }, group.length));
      x0 += width;
    });
    root.appendChild(svg("text", { x: R, y: H - 2, "text-anchor": "end", "class": "axis-title" }, "race length in km, and how many courses"));
    node.appendChild(root);
    legend("courses-legend", [
      ["dot course-sw", "a course"],
      ["dot named-sw", "one of the four busiest, named"],
      ["dot live-sw", "a race on this page"],
      ["dashed sw-faint", "the typical course at that length"]
    ]);
  }

  /* The felt-heat cost per degree above 12 C, by race length: the whole-archive posterior
     medians reported in the README and PLAN.md section 13 item 30. */
  var HEAT = [
    ["5 km", 0.0005, "w0"], ["10 km", 0.0031, "w1"], ["Tely 10 (16 km)", 0.0050, "w2"],
    ["Cape to Cabot 20 km", 0.0058, "w3"], ["Marathon", 0.0087, "w4"]
  ];
  var KNEE = 12;

  function drawWeather() {
    var node = clear(byId("weather-chart"));
    var H = 300, L = 52, R = WIDTH - 150, T = 16, B = H - 34;
    var root = frame(H, "What felt heat costs, by race length");
    var x = linear([0, 30], [L, R]);
    var y = linear([0, 17], [B, T]);
    yAxis(root, y, L, R, function (v) { return v + "%"; }, "slower than a cool morning");
    ticks(0, 30, 6).forEach(function (t) { root.appendChild(svg("text", { x: x(t), y: H - 14, "text-anchor": "middle", "class": "tick" }, t + " C")); });
    root.appendChild(svg("text", { x: R, y: H - 1, "text-anchor": "end", "class": "axis-title" }, "felt temperature"));
    root.appendChild(svg("rect", { x: L, y: T, width: x(KNEE) - L, height: B - T, "class": "cool-zone" }));
    root.appendChild(svg("text", { x: (L + x(KNEE)) / 2, y: T + 16, "text-anchor": "middle", "class": "shift-label" }, "no cost below 12 C"));
    HEAT.forEach(function (h) {
      var end = h[1] * (30 - KNEE) * 100;
      var line = svg("path", { d: "M" + x(0) + " " + y(0) + " L" + x(KNEE) + " " + y(0) + " L" + x(30) + " " + y(end), "class": "series heat " + h[2] });
      root.appendChild(line);
      root.appendChild(svg("text", { x: x(30) + 8, y: y(end) + 4, "class": "row-label heat-label " + h[2] }, h[0]));
      var mark = svg("circle", { cx: x(24), cy: y(h[1] * (24 - KNEE) * 100), r: 5, "class": "dot heat-dot " + h[2] });
      hover(mark, "weather-readout", h[0] + ": about " + (h[1] * 100).toFixed(2) + "% slower per degree of felt heat above 12 C; a 24 C felt morning costs about " + (h[1] * 12 * 100).toFixed(1) + "%");
      root.appendChild(mark);
    });
    node.appendChild(root);
    byId("weather-readout").textContent = "Point at a dot for the cost per degree at that race length.";
  }

  /* The shrinkage illustration: invented results, a normal-normal posterior. */
  var GROUP_SD = 8.0, RACE_SD = 6.0, GROUP_MEAN = 0.0;
  var INVENTED = [
    ["One race", [-9.0]],
    ["Three races", [-7.5, -10.5, -5.5]],
    ["Eight races", [-8.5, -10.0, -7.0, -9.5, -6.5, -11.0, -8.0, -9.0]]
  ];

  function drawShrink() {
    var node = clear(byId("shrink-chart"));
    var H = 260, L = 110, R = WIDTH - 20, T = 30, row = 70;
    var root = frame(H, "Illustration: predictions lean on the group when a runner has few results");
    var x = linear([-22, 16], [L, R]);
    root.appendChild(svg("rect", { x: x(GROUP_MEAN - GROUP_SD), y: T - 18, width: x(GROUP_MEAN + GROUP_SD) - x(GROUP_MEAN - GROUP_SD), height: row * 3 + 6, "class": "group-band" }));
    root.appendChild(svg("line", { x1: x(GROUP_MEAN), x2: x(GROUP_MEAN), y1: T - 18, y2: T + row * 3 - 12, "class": "nominal" }));
    root.appendChild(svg("text", { x: x(GROUP_MEAN), y: T - 22, "text-anchor": "middle", "class": "axis-title" }, "typical for the group"));
    INVENTED.forEach(function (runner, i) {
      var cy = T + 20 + i * row;
      var results = runner[1];
      var n = results.length;
      var mean = results.reduce(function (a, b) { return a + b; }, 0) / n;
      var precision = n / (RACE_SD * RACE_SD) + 1 / (GROUP_SD * GROUP_SD);
      var post = (n * mean / (RACE_SD * RACE_SD) + GROUP_MEAN / (GROUP_SD * GROUP_SD)) / precision;
      var spread = 1.2816 * Math.sqrt(1 / precision + RACE_SD * RACE_SD);
      root.appendChild(svg("text", { x: L - 12, y: cy + 4, "text-anchor": "end", "class": "row-label" }, runner[0]));
      results.forEach(function (r) { root.appendChild(svg("circle", { cx: x(r), cy: cy - 14, r: 4, "class": "past-dot" })); });
      root.appendChild(svg("line", { x1: x(post - spread), x2: x(post + spread), y1: cy + 6, y2: cy + 6, "class": "pred-range" }));
      root.appendChild(svg("circle", { cx: x(post), cy: cy + 6, r: 6, "class": "pred-dot" }));
    });
    ticks(-20, 15, 7).forEach(function (t) {
      root.appendChild(svg("text", { x: x(t), y: H - 6, "text-anchor": "middle", "class": "tick" }, (t > 0 ? "+" : "") + t + "%"));
    });
    root.appendChild(svg("text", { x: L - 12, y: H - 6, "text-anchor": "end", "class": "axis-title" }, "faster"));
    root.appendChild(svg("text", { x: R, y: H - 22, "text-anchor": "end", "class": "axis-title" }, "slower"));
    node.appendChild(root);
    legend("shrink-legend", [["dot past-sw", "a past race"], ["dot pred-sw", "the prediction"], ["sw-range", "its 80% range"], ["block sw-group", "typical for the group"]]);
  }

  var STRATA = [
    ["0", "No past races", "No past races"],
    ["1", "One", "One past race"],
    ["2 to 3", "Two or three", "Two or three past races"],
    ["4 or more", "Four or more", "Four or more past races"]
  ];

  function drawCoverage(rows, prefix) {
    prefix = prefix || "coverage";
    var node = clear(byId(prefix + "-chart"));
    var H = 290, T = 26, B = H - 46;
    var root = frame(H, "How often the 80% and 90% ranges held, by history depth");
    var y = linear([0.6, 1.0], [B, T]);
    var panels = [[0.8, 58, 450], [0.9, 490, WIDTH - 12]];
    yAxis(root, y, 58, WIDTH - 12, function (v) { return Math.round(v * 100) + "%"; }, "share of finishes inside the range");
    panels.forEach(function (panel) {
      var level = panel[0], L = panel[1], R = panel[2];
      root.appendChild(svg("line", { x1: L, x2: R, y1: y(level), y2: y(level), "class": "nominal" }));
      root.appendChild(svg("text", { x: (L + R) / 2, y: H - 4, "text-anchor": "middle", "class": "axis-title" }, Math.round(level * 100) + "% range"));
      var step = (R - L) / STRATA.length;
      STRATA.forEach(function (s, i) {
        var r = rows.filter(function (row) { return row.stratum === s[0] && row.level === level; })[0];
        if (!r) { return; }
        var cx = L + step * (i + 0.5);
        root.appendChild(svg("line", { x1: cx + 7, x2: cx + 7, y1: y(r.conformal_low), y2: y(r.conformal_high), "class": "whisker" }));
        root.appendChild(svg("line", { x1: cx - 7, x2: cx - 7, y1: y(r.raw_low), y2: y(r.raw_high), "class": "whisker faint" }));
        var raw = svg("circle", { cx: cx - 7, cy: y(r.raw), r: 5.5, "class": "cov-raw" });
        var cal = svg("circle", { cx: cx + 7, cy: y(r.conformal), r: 5.5, "class": "cov-cal" });
        var text = s[2] + ", " + Math.round(level * 100) + "% range: the model's own range held " + percent(r.raw) +
          " of the time, after calibration " + percent(r.conformal) + " (95% interval " + percent(r.conformal_low) + " to " +
          percent(r.conformal_high) + "), over " + count(r.checked) + " runners; median width " + r.conformal_width_min.toFixed(0) + " minutes";
        hover(raw, prefix + "-caption", text);
        hover(cal, prefix + "-caption", text);
        root.appendChild(raw);
        root.appendChild(cal);
        root.appendChild(svg("text", { x: cx, y: B + 18, "text-anchor": "middle", "class": "tick" }, s[1]));
      });
    });
    node.appendChild(root);
    legend(prefix + "-legend", [["dot raw-sw", "the model's own range"], ["dot cal-sw", "after calibration"], ["dashed sw-faint", "what the range promises"]]);
  }

  var MODELS = [
    ["carry-forward", "Last time", "m-cf"],
    ["best-equal-vdot", "Race calculator", "m-vdot"],
    ["category-median", "Your category", "m-median"],
    ["hierarchical", "Bayesian model", "m-hier"],
    ["lightgbm", "LightGBM challenger", "m-gbm"],
    ["blend", "What this site publishes", "m-model"]
  ];

  function drawResults(strata) {
    var node = clear(byId("results-chart"));
    var H = 330, L = 52, R = WIDTH - 12, T = 20, B = H - 56;
    var root = frame(H, "Average error in minutes by history depth, for each method");
    var top = 0;
    strata.forEach(function (s) { MODELS.forEach(function (m) { var v = s.models[m[0]]; if (v && isNumber(v.high_min)) { top = Math.max(top, v.high_min); } }); });
    var y = linear([0, Math.ceil(top / 5) * 5], [B, T]);
    yAxis(root, y, L, R, function (v) { return v + " min"; }, "average error");
    var group = (R - L) / strata.length;
    strata.forEach(function (s, gi) {
      var gx = L + group * gi;
      var label = STRATA.filter(function (x) { return x[0] === s.label; })[0];
      root.appendChild(svg("text", { x: gx + group / 2, y: B + 20, "text-anchor": "middle", "class": "row-label" }, (label ? label[2] : s.label)));
      root.appendChild(svg("text", { x: gx + group / 2, y: B + 36, "text-anchor": "middle", "class": "row-note" }, count(s.runners) + " runners"));
      var bw = group * 0.8 / MODELS.length;
      MODELS.forEach(function (m, mi) {
        var v = s.models[m[0]];
        var x = gx + group * 0.1 + bw * mi;
        if (!v || !isNumber(v.mae_min)) {
          root.appendChild(svg("text", { x: x + bw / 2, y: B - 6, "text-anchor": "middle", "class": "row-note" }, "none"));
          return;
        }
        var bar = svg("rect", { x: x + 2, y: y(v.mae_min), width: bw - 4, height: B - y(v.mae_min), rx: 2, "class": "bar " + m[2] });
        hover(bar, "results-readout", m[1] + ", " + (label ? label[2].toLowerCase() : s.label) + ": " + v.mae_min.toFixed(1) +
          " minutes (95% interval " + v.low_min.toFixed(1) + " to " + v.high_min.toFixed(1) + "), answering for " + percent(v.answered) + " of runners" +
          (isNumber(v.skill) ? "; " + (v.skill >= 0 ? percent(v.skill) + " better" : percent(-v.skill) + " worse") + " than last time" : ""));
        root.appendChild(bar);
        root.appendChild(svg("line", { x1: x + bw / 2, x2: x + bw / 2, y1: y(v.low_min), y2: y(v.high_min), "class": "whisker" }));
        if (m[0] === "blend") {
          root.appendChild(svg("text", { x: x + bw / 2, y: y(v.high_min) - 6, "text-anchor": "middle", "class": "bar-value" }, v.mae_min.toFixed(1)));
        }
      });
    });
    node.appendChild(root);
    byId("results-readout").textContent = "Point at a bar for its number, interval and how many runners it could answer for.";
  }

  function drawPlacing(placing) {
    var node = clear(byId("placing-stats"));
    if (!placing) { return; }
    append(node, [
      stat(Math.abs(placing.difference[0]).toFixed(1) + " places", "closer than \"last time\" on average, on the same " + count(placing.runners) +
        " runners in " + placing.races + " races (95% interval " + Math.abs(placing.difference[2]).toFixed(1) + " to " + Math.abs(placing.difference[1]).toFixed(1) + ")"),
      stat(placing.spearman.toFixed(2), "rank correlation between predicted and actual order (1 would be perfect); last time scores " + placing.baseline_spearman.toFixed(2))
    ]);
  }

  /* Start ------------------------------------------------------------------------ */

  function start() {
    Promise.all([getJSON("data/results.json"), getJSON("data/races.json")]).then(function (loaded) {
      state.results = loaded[0];
      state.races = loaded[1];
      drawYears(state.results.archive);
      drawCourses(state.results.courses);
      drawWeather();
      drawShrink();
      drawCoverage(state.results.backtest.coverage);
      var challenger = state.results.backtest.challenger_coverage;
      byId("challenger-ranges").hidden = !(challenger && challenger.length);
      if (challenger && challenger.length) { drawCoverage(challenger, "coverage-gbm"); }
      drawResults(state.results.backtest.strata);
      drawPlacing(state.results.backtest.placing);
      var wanted = (window.location.hash || "").replace("#", "");
      selectRace(state.races.some(function (r) { return r.id === wanted; }) ? wanted : state.races[0].id, false);
      byId("race").addEventListener("change", function (event) { selectRace(event.target.value, true); });
      var speed = byId("speed");
      if (speed) {
        drawHeroDistances(speed.value);
        speed.addEventListener("change", function (event) { drawHeroDistances(event.target.value); });
      }
      byId("find").addEventListener("input", function (event) { state.query = event.target.value; applySearch(); });
    }).catch(fail);
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); } else { start(); }
})();
