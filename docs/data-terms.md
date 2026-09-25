# Where the data comes from, what its terms say, and what is deliberately missing

Checked 2026-09-12. Nothing is fetched until its terms have been read and recorded here
with the date. If you are adding a source, add its row first.

## Strava: not usable, and this is the decision that shaped the project

The original idea was to read each registered runner's public Strava activity. It cannot
be done, by the API or otherwise.

| Clause | Where | What it says |
|---|---|---|
| Other users' data | API Agreement effective 2026-06-01, section 2.3 | "Strava Data related to other users, even if such data is publicly viewable on the Strava Platform, may not be displayed or disclosed." |
| Sharing | Section 5.1 | A developer must not share a user's data with other users or third parties without explicit consent. |
| Model training | November 2024 revision, restated in the 2026 developer programme | Data obtained through the API may not be used to train artificial-intelligence or machine-learning models. |
| Scraping | Acceptable Use Policy | Forbids collecting or harvesting information about identifiable individuals, and any automated scraping. |
| Access | 2026 developer programme | Standard-tier access requires a paid Strava subscription; public profile pages are moving behind login. |

**Consequence.** The public model uses no training data for anyone. An opt-in channel,
where a runner authorises the app, sees a prediction built from their own activity, and
nobody else does, is the only compliant use and is deferred to Part B. Nothing published
by this repository will ever contain Strava data.

This is recorded here rather than in `docs/rejected.md` because it was rejected on terms
and not on evidence. `docs/rejected.md` is for an approach that was tried and measured.

## NLAA road results: the archive this project runs on

Public pages at `https://www.nlaa.ca/results/`, one per race, results as fixed-width text
in a `<pre>` block. Footer reads "Copyright NLAA". There is no terms-of-use page and no
`robots.txt`. Results go back to 1978; this project reads 2016 onward.

**How it is read.** One request a second, never concurrent. Every page is written to
`data/cache/` on arrival and read from disk forever after, so a full rerun of the
pipeline costs zero requests. The SHA-256 and fetch time of every page are recorded in
`data/cache/nlaa/manifest.jsonl`. The user agent names the project and carries an address.

⚠️ **The one page read more than once is the current year's index, and only when asked.** A
results page never changes, but the current year's index grows as races are posted, and the
cached copy cannot show a race that was posted after it was fetched. `finishline crawl
--refresh-index` reads that one index again before crawling, and `finishline score` does the
same when it cannot find the race it is scoring. New results pages are then fetched once like
any other.

**Weekly, on a schedule.** `scripts/weekly-crawl.ps1`, registered with Task Scheduler by
`scripts/register-crawl-task.ps1`, runs `finishline crawl --refresh-index --scheduled` on Sunday
mornings: one index request plus one per newly posted results page. It stands down from ten
days before each race in `data/live.toml` to the day after, because a new race makes the saved
model backtest stale and `freeze` refuses without a matching one. It then fetches this year's
airport observations the same way (`finishline weather --scheduled`); a month fetched before
it ended is fetched again, so a race late in a month is not left without weather. Every run
appends to `data/cache/nlaa/crawl.log`.

**What is published.** Only what the results already publish about a runner: their name
and hometown as the page printed them, and the prediction. Never the age, beyond the
category the page prints. Never anything from an entrant list beyond who is running.

**Nothing from the cache is committed.** It is thousands of identifiable people.
`.gitignore` enforces it.

**The courtesy notice.** Reading a small volunteer association's whole archive without
telling them is not something to do quietly, so `finishline crawl` refuses until the
notices in [emails.md](emails.md) have gone out. The rail is in code because the person
the command is convenient for is not the person who decided to be polite.

**Sent 2026-09-12**, to the Newfoundland and Labrador Athletics Association and to
Athletics NorthEAST. The crawl ran the same day. If either organisation asks for it to
stop, it stops: the cache is local, nothing is committed, and no prediction has been
published yet.

### What the archive holds, and what it does not

Measured by `finishline catalogue`, 2026-09-12, over the year indexes for 2008 to 2026.

| | |
|---|---|
| Individual road races read | 286 |
| Distinct courses | 52 |
| Deepest course histories | 17 editions (Mews Memorial 8 km, Mundy Pond 5 km), 16 (Cape to Cabot 20 km) |
| Index rows skipped, each with its own reason | 47 |
| Years covered | 2008 to 2026, **no 2020** |

**Why 2008 and not 2016.** The first crawl stopped at 2016, on the reasoning that ten
years was enough and the older pages were a different era. Then the Cape to Cabot start
list showed 67 of its 453 entrants with an earliest result in 2016 exactly, which is the
shape a history makes when it has been cut off rather than when it began. Eighteen years
covers a masters career from one age band into the next and takes the deepest courses from
9 editions to 16 or 17. Before 2008 the returns fall away: the recent-form window is
eighteen months whatever the archive holds, so an older result speaks to a career arc and
not to next month's race.

⚠️ **The heading changed name and eight years went missing without a sound.** Every index
from 2008 to 2015 calls its road section "Road Race Series"; 2016 onward calls it "Road
Running". The parser matched the current wording, found nothing, and reported nothing,
which is the same failure as a parser keyed on a ruler that most pages do not draw. It now
matches on "Road" and leaves the rest of the phrase alone, and a test pins both spellings.

**Known holes, stated rather than discovered later.**

- **2020 is absent.** The season did not happen.
- **Five pages will not parse**, out of 288 read:
  - The 2008 Cape to Cabot and the 2008 HBC Run for Canada are stubs that link out to a
    third-party timing site rather than carrying results themselves.
  - The 2011 Mews Memorial 8 km carries no results table.
  - **The 2013 Tely 10 prints its rows with no column header at all**, only the race title
    above them. The layout is recognisable and this parser still refuses it, because
    supplying column names it was not given is exactly the guess that everything else here
    is built to avoid.
  - The 2017 Turkey Tea is an HTML table rather than fixed-width text, the only page in
    eighteen years in that shape.
- **A few races are published as PDFs** and are not read, including one Cape to Cabot
  edition and one Huffin' Puffin marathon. A PDF parser for a handful of pages in eighteen
  years is not worth the week, and the skip list names each one.
- **A team page is not a hole.** Many of the skips are team standings and awards pages for
  races whose individual results are read.

## NLAA race calendar, added 2026-09-20

`https://www.nlaa.ca/calendar.php`, the association's own list of the year's events: a
date, an event name and a place per entry, in a plain unordered list. Same site, same
footer ("Copyright NLAA 2026"), no terms-of-use page and no `robots.txt`, which is the
same standing the results pages were read under. Peter told the association on 2026-09-19
that this project reads its site to predict races, and it raised no objection.

**Why it is read at all.** Without it the website's list of races is whatever a person last
typed into `data/live.toml`, which goes stale the moment a race is added or cancelled and
says nothing about the races this project is not predicting. The calendar is the only public
statement of what is actually being run this year.

⚠️ **This page is alive, like an entrant list and unlike a results page.** Races are added,
moved and cancelled all year, so the cached copy is not the truth and a fetch-once-keep-forever
rule would publish last month's calendar. It is re-fetched on each run of `finishline calendar`,
at the crawler's one-a-second pace and under its user agent, and the copy on disk is replaced.
It holds no personal data at all, so unlike the entrant snapshots it is not kept as a series
and the file it writes, `data/calendar.json`, is committed.

**What is taken.** The date, the event name and the place, for road races only. Track meets,
cross-country, road relays and the kids' events are dropped by the same rules that decide
what `finishline catalogue` reads (`nlaa.why_not_read`), and the count of what was dropped
is printed rather than hidden. A calendar entry carries no distance and no course, so it is
matched to a course in the archive by the same sponsor-proof aliases the results index is
matched by (`nlaa.COURSE_ALIASES`); an entry that matches nothing is listed as an
unrecognised road race rather than guessed at.

**Nothing about a person is on this page**, so nothing about a person comes off it.

## Athletics NorthEAST entrant lists

Public pages on the club's store, "up-to-the-minute", no privacy statement:

- Cape to Cabot: `athleticsnortheast.com/cart/index.php?main_page=page&id=4`
- Uniformed Services Run: the same path with `id=1`

Snapshotted daily from 2026-09-12 into `data/entrants/`, gitignored, by `finishline
snapshot`. It fetches at the same one request a second as the results crawler, sends the
same identifying user agent, and refuses to run until the courtesy notes have gone out
exactly as `crawl` does; CI asserts both refusals. It writes a file only when the start
list has changed and a manifest row on every look, so a day with no new entries is
recorded without a second copy of the names.

⚠️ **"Changed" means the entrants changed, not the bytes.** The store puts a fresh
`securityToken` in every response, so no two fetches are ever byte equal and the first
version of this called every look a change. The comparison is over the parsed start list,
sorted; the manifest keeps both hashes, `page_sha256` for the provenance of the file on
disk and `listing_sha256` for whether anything actually happened.

Run daily by `scripts/daily-snapshot.ps1` under Windows Task Scheduler; register it with
`scripts/register-snapshot-task.ps1`, which also prints how to remove it. Every run appends
a line to `data/entrants/snapshot.log` whether it worked or not, because a scheduled task
that has been failing quietly for a fortnight is worse than no scheduled task.

**These pages are the opposite of a results page and are treated that way.** A results page
is written once and never changes, so it is fetched once and kept forever. An entrant list
changes every day until the gun and is archived nowhere, not even by the Wayback Machine,
so the only chance to see it on a given day is that day. Snapshots are never overwritten.

| Look | Cape to Cabot | USR |
|---|---:|---:|
| 2026-09-12T16:03Z | 453 | 895 |
| 2026-09-13T00:14Z, the last before the USR gun | 458 | 896 |

Of the 896 on the USR list, 629 are in the four individual road events that produce
results: 277 half marathon, 198 10 km, 79 marathon, 75 5 km. The remainder are the kids'
1 km, the family 3 km and the marathon relay, none of which this project predicts.

**Sex is used. Shirt size is not**, by decision. A body-size proxy would probably help the
model a little, and a public finish-time prediction that leaned on somebody's T-shirt size
is not one anyone would thank us for. The rule the project holds to is that it publishes
only what the results publish, and a results page has never printed a shirt size.

## Athletics NorthEAST finish lists, added 2026-09-19

The club timed the 2026 Uniformed Services Run and posted its overall finish lists on its own
site (`athleticsnortheast.com`, "USR Marathon Overall", "USR Half Overall", "USR 10k Overall",
"USR 5k Overall") the week of the race; the association republishes them later. Peter
pointed to them and wrote to the club before they were read. Four pages, fetched once each
on 2026-09-19 at one a second under the crawler's user agent, kept in `data/cache/ane/` with
a manifest, gitignored (`ingest/ane.py`).

**They print a place, a name, a service affiliation, a bib and the times, and nothing else.**
No sex, no age band and no hometown, so these results join a runner's history on the name
alone where nothing contradicts it. The affiliation ("Eastern Health", "Canadian Forces") is
not a hometown and is not read. **When nlaa.ca carries the same race**, the same date on the
same course, the club's copy is dropped (`store.build`), so no edition is counted twice.

## Trackie entry lists, added 2026-09-19

The Turkey Tea 10k, this project's dress rehearsal on 2026-10-04, registers through Trackie,
whose public entry list for it (event 1038734, pointed to by Peter) prints each entrant's
name, sex, hometown, club and whether they bought a medal: 306 entrants on 2026-09-19.

**What the terms say.** Trackie's Terms and Conditions (the popup linked from every page,
"Last updated: August 21st 2025") contain no clause on automated access, and the site
serves no robots.txt. The clauses that bear on this use: "You may not link to this Site or
display this Site in such a manner as to make it 'framed' within another website without
our explicit permission", and a user may not "use or gain access to the identities,
information or computers of others, through this Site". The first is why this repository
names the page and does not link to it from anything it publishes, and never displays or
frames it. The second is read as it is meant, against accessing what is not offered: the
list is published by the organiser for anyone to read, and this project uses it exactly as
it uses the club's own lists, for the names of a field that has chosen to be listed.

**How it is read.** The list page is a shell and its names come from one data request the
page itself makes, so a look is those two requests, a second apart, under the same
identifying user agent, once a day by the same scheduled `finishline snapshot` as the
Athletics NorthEAST lists, and with the same refusal to run before the courtesy notes.
Snapshots go to `data/entrants/`, gitignored, and are never overwritten.

**Name, sex and hometown are read. The medal choice is not**, for the reason the shirt size
is not: no results page prints it. The hometown is printed by the results too, and the
linker uses it for one thing only: to break a tie between runners of one name when exactly
one of them was ever printed under that town (on the 2026-09-19 list, 2 of 7 such ties). The
prediction file publishes the hometown the results printed, never the list's. The club is not
used.

## Course elevation

⚠️ **Nothing is fetched for this, and nothing needs to be.** The course factor this project
uses is measured from the results, where Cape to Cabot's 5,310 finishes give +9.3 percent
[+9.0, +9.5]. No survey, DEM or GPX can beat that interval, so the elevation figures exist
to check the measurement rather than to feed it.

| Figure | Source | Terms |
|---|---|---|
| Cape to Cabot, 550 m of climb against 450 m of drop over 20 km | `capetocabot.com/course.html`, and the same figures in the race's press coverage | A fact about a public road, published by the race about itself. Read once by hand, not crawled. |
| Cape to Cabot, 519 m of climb | Strava's own total for Peter Parker's recording of the **2024** edition | His own data about his own run. **Corrected 2026-09-25**: this row said the 2025 edition, and there is no 2025 recording. Superseded as the second reading by the smoothed series of the same recording (513.7 m up, 403.8 m down, the row for the profiles below); 519 is the raw total of that same run, 6 percent under the published figure, which is the usual disagreement between a barometric ascent total and a surveyed one. |
| Cape to Cabot, the heights of the named climbs, and a second profile | The race's own 2006 chart on `capetocabot.com/course.html`, heights labelled at about 500 m spacing, and a profile image of the certified 20 km that Peter supplied on 2026-09-21, both read off by eye | The first is the race's page again, read by hand. The second is kept as a bracket only (about 495 m up), and **where it was made is still not recorded**: project 11 drew its first profile on 2026-09-25, so it was not the source, and the image finishes about 10 m lower on Signal Hill than project 11's series does. |
| Turkey Tea 10 km, 38 m up and 123 m down, and a bearing of 79 degrees | The summary of the public Strava segment "Turkey Day 10K" (segment 10652676), from a screenshot Peter supplied on 2026-09-19 | Recorded here on 2026-09-21; it went into `data/courses.toml` without a row, which this document says should come first. A segment is a line along public roads, drawn by a Strava user; its printed distance, gain and high and low points describe the road, not anyone's run. No activity and no leaderboard was read, nothing was fetched, and the numbers can be replaced by any other published figure for the same road. It is the one place a number in this repository came off a Strava page, and it is written down so that can be judged. **Extended 2026-09-25**: Overload redrew this course's profile from Strava's own segment stream rather than from a screenshot of the summary, giving 39 m up and 123 m down (a metre from the printed 38) and, for the first time, the grade of the steepest and fastest 600 m. A segment stream is more of Strava than had been taken before. What crosses into the repository is unchanged in kind: two totals and two grade windows about a line of public road, with no stream, no coordinates, no effort, no athlete and no leaderboard stored. Drawing the segment's profile on the website was a further step, and Peter took it on 2026-09-25: the segment is public and describes no person. |
| Harbour Front 10 km, 71.5 m up and 65.5 m down, and the grade of the steepest 600 m | Overload's profile of 2026-09-25, drawn from Strava's own segment stream for the course, as Turkey Tea's and Run to Remember's were | Same terms and same line as the Turkey Tea row below. This course had no elevation figure of any kind before. |
| Run to Remember 11 km, 92.5 m up and 92.0 m down, and the grade of the steepest 700 m | Overload's profile of 2026-09-25, drawn from Strava's own segment stream for the course, as Turkey Tea's was | Same terms and same line as the Turkey Tea row below: a segment is a line along public roads, the stream carries no clock, no athlete and no effort, and what is stored is two totals and two grade windows. It replaced the organisers' 56 m; the difference is smoothing scale, since on a steady out-and-back the cumulative climb a coarse chart prints is the range, about 51 m in both sources. The page as served on 2026-09-25 no longer carries the chart. |
| Run to Remember 11 km, 56 m up and 56 m down, kept as the second reading | The course profile on the organisers' page, `striderunningnl.ca/run-to-remember/` (Stride Running NL), as Peter read it on 2026-09-21; the route and the 2025 switch of start and turnaround from the same page, read once by hand | A race describing its own course, as Cape to Cabot's page is. Two figures and a route description are taken; the page ("Copyright 2021-2026 Stride Running NL") is not reproduced. The 2026-09-25 stream profile disagrees with these two figures and confirms the switch of the ends, which had been the page's word alone. |
| Eight courses' climb and descent, and the grade windows that go with them: Five and Dime 5 km and 10 km, Mundy Pond, Flat Out, Mews Memorial, the Tely, Cape to Cabot and the Huffin Puffin marathon | Elevation profiles built by project 11 (Overload) from Peter Parker's own recordings of each route, supplied as chart images on 2026-09-25 | His own data about his own runs, and only the road is taken from them: the climb and descent of the smoothed series, the start, finish, high and low heights, and the steepest and fastest windows. **The distance, the moving time, the average pace and, on one chart, the heart rate are recorded nowhere in this repository**; no track, split or stream is; no start or finish position was taken, which is why several of these courses still have no bearing; and the images themselves are not committed. A height above sea level along a public road is the same kind of fact as the ascent total Cape to Cabot's own page prints. A pace or a heart rate is not, and that is where the line is. Overload is Peter's own project and has no terms of its own to read; the recordings behind it are his. |
| The height series of all eleven courses, committed at `data/profiles/<course_id>.json`, and drawn on the website's race cards | Project 11's `metrics/elevation.py`, from the same eight recordings, delivered 2026-09-25 to the written specification in that project's `courses-instructions.md` | Heights above sea level on a 20 m distance grid, smoothed, with their totals, end heights, high and low, the steepest and fastest windows, the grid and smoothing widths, and the race edition's date. **No time, pace, speed, heart rate, cadence, power, temperature, activity id, athlete id or coordinate array**, and `tests/test_grade.py` refuses a profile file carrying any key that names one. The test for what may cross is whether the number would be the same if somebody else had walked the route with a barometer. The three segment series (Turkey Tea, Run to Remember, Harbour Front) are Strava's own segment streams: Peter decided on 2026-09-25 that a public Strava segment's profile may be stored and drawn: it is a line along public roads and describes no person. The card that draws one names the segment and links to it. |
| Start and finish points of Mews Memorial, the Five and Dime 5 km and 10 km, and Harbour Front, in `data/courses.toml` | Project 11's manifest of 2026-09-25: the first and last point of the race as recorded, or a segment's own two ends, rounded to four decimal places | Two points per course, about ten metres of precision, on public start and finish lines; never a trace. They exist to compute a bearing, and none has been set yet (docs/todo.md item 2). |
| Flat Out 5 km, 39 m up and 52 m down | An elevation profile image of the course Peter supplied on 2026-09-21, with no figures printed on it; the totals are read off the chart by eye. The route is from the race's page, `athleticsnortheast.com/FlatOut5k/course.html`, read once by hand, and nine waypoints Peter placed on a map along it | The race's page is a race describing its own public road, as Cape to Cabot's is. The waypoints are coordinates typed onto a public road. **Where that image was made is still not recorded.** Project 11 did not draw it (its first profile is from 2026-09-25). Its by-eye totals agree with project 11's series (38.4 m up, 49.3 m down) to within 3 m on the totals, the net and both ends, which is two independent readings agreeing rather than one read twice. Nothing was taken from Google Maps beyond the nine points Peter typed: its terms bar extracting content, and its elevation service may not be stored or shown away from its own map, so no profile or elevation from it is used. |

All of these are in `data/courses.toml` with the source beside the number, and a test
refuses a course that states a climb without one. Cape to Cabot publishes an elevation
profile image for its 2006 test run only, and no GPX or KML; the street-by-street route
description is on the same page. **No third-party elevation service is used**, and none is needed: what the
physics wants is the grade distribution, which nobody publishes, and the results already
answer the question the profile would have been used to answer.

⚠️ **Do not add a runner's own GPS trace to this.** A watch file is training data about an
identifiable person, which is the line drawn for Strava at the top of this document and it
does not move because the file arrived by a different route. Peter's own ascent figures are
here as numbers about a public road, not as tracks.

⚠️ **The line, now that eight courses have been read off one person's recordings.** What
crosses into this repository is the shape of the road: heights above sea level, a climb and
a descent total, the grade of the steepest and the fastest stretch. What does not cross is
anything about the running: no time, no pace, no heart rate, no stream, no per-kilometre
split, not even for Peter himself, who is as identifiable as anyone else the results name.
The test is whether the number would be the same if somebody else had walked the route with
a barometer. If it would not, it does not belong here. That also rules out publishing the
chart images: their headers carry a pace and a moving time, so the website draws its own
profile from the heights alone (`web/app.js`, `drawProfile`), and its caption says whether the
heights are a recording or a public segment and never whose recording.

## Weather

| Source | Use | Terms |
|---|---|---|
| Environment and Climate Change Canada, station 50089 (St. John's Intl A, climate ID 8403505) | Observed temperature, humidity, wind speed and direction for every past race morning, as a monthly CSV | Open Government Licence Canada |
| Open-Meteo forecast API | The forecast pulled before a race, recorded with the prediction | Free for non-commercial use, no key |
| Open-Meteo archive API | Hourly direct (beam) radiation for every past race morning, which the airport does not record and which sets how hot a warm morning feels (`finishline weather`, one request per year); and the comparison against the observations, so the gap between modelled and measured is itself reported | Same |
| Open-Meteo previous-runs API | What the forecast said a day before each past race morning, set beside the observation to measure a day-ahead forecast's bias and spread (`finishline forecast-error`) | Same |

The observations are the backtest's basis because Overload measured Open-Meteo's modelled
temperature about 6 degrees Celsius off at this coast. There is no observation of the
future, so the live prediction uses the forecast and says so.

**Measured 2026-09-16, and it is not the six degrees.** On 32 race mornings near St. John's
since 2024, Open-Meteo's day-ahead forecast at the airport, averaged over the race hours, ran
**1.5 degrees cold** (sd 2.4) and **7.2 km/h calm** (sd 5.0) against the ECCC observation
(remeasured 2026-09-18 over each race's real start time, `data/starts.toml`, rather than an
assumed 9 am; the first measurement was 1.4 and 7.7). The
six degrees Overload found was a different comparison, and the lesson is the one the rest of
this document keeps learning: measure the thing you will use, where you will use it. The wind
bias is the one that matters here, because the airport is reliably windier than the model
thinks. `freeze` corrects a forecast by both biases and carries the spread as uncertainty;
the numbers live in `data/forecast_error.toml` and are regenerated by the command, not typed.

**And at every lead to a week, added 2026-09-19**, for the daily prediction files, which
predict each entrant with the forecast of the morning they are first published. On 36 race
mornings (the 2026 USR added), the spread of the temperature error grows from 2.2 C a day
ahead to about 3 C at five to seven days, and of the wind speed from 4.7 to 9.5 km/h; the
day-ahead biases are now 1.5 degrees cold and 7.1 km/h calm. By lead in
`data/forecast_error_by_lead.toml`.

Fetched by `finishline forecast-error`: one request per year of forecasts and lead, one a
second, with the identifying user agent, kept under `data/cache/openmeteo/`. A live forecast is fetched at
freeze time and never reused, because a forecast is a moment.

**The sun, added 2026-09-18.** The airport records temperature and wind but not the sun, and
the sun raises the heat a runner meets (PLAN.md 13 item 30). Direct radiation comes from the
same archive, reanalysis rather than an observation, one request per year, kept under
`data/cache/openmeteo/`, and is used as a share of a clear noon's 800 W/m2, which is Overload's
measure. A year fetched before the archive has caught up with it is fetched again later, the
same rule the ECCC months follow; the forecast pulled at freeze time asks for the forecast sun
as well. ⚠️ A 9 km reanalysis cell is a poor witness to the sun on one road: Overload's 45 days
of thermometer readings at this coast caught it reporting full cloud while the runner was in
sun for half the run, so what the model learns about the sun is bounded by this input.

**Fetched by `finishline weather`**, under the same rails as the results crawler: one
request a second, an identifying user agent, each station-month written to
`data/cache/eccc/` with its SHA-256 and kept forever, and a refusal until the courtesy
notes have gone out. 120 station-months cover every race in the archive. Not committed: it
is a large cache of somebody else's published file, and `.gitignore` keeps it local.

⚠️ **Two stations, and one of them lies quietly.** "ST JOHN'S A" (6720) carries hourly
observations to the end of 2011 and "ST JOHN'S INTL A" (50089) from 2012. Asked for a month
outside its coverage, a station returns **744 complete-looking rows with every temperature
empty**, not an error. Taken at face value the whole backtest would have run with no weather
for the first four years and nothing would have said so, which is the same silence as a
parser keyed on a ruler most pages do not draw and an index heading that changed wording in
2016. `hourly` raises rather than returning nothing. The boundary was measured by asking
both stations for May and September of 2010 through 2014, not assumed.

⚠️ **The timestamps are Local Standard Time in every month.** ECCC does not shift for
daylight saving, so a race starting at 09:00 on a wall clock in July is at 08:00 in the
file. Every road race here runs inside the daylight-saving period. Read wrong, every race
moves an hour earlier into the cool of the morning, which biases the heat term the same way
every time and looks like a modest effect rather than a mistake.

⚠️ **The airport is not the course.** St. John's Intl is a fair proxy for a race on the
Avalon and says nothing useful about one in Gander, Garnish, Bay Roberts or Labrador City.
Those courses are named in `eccc.AWAY_FROM_ST_JOHNS` and excluded from the conditions fit
rather than quietly averaged in: 55 of the 282 editions.

⚠️ **No results page in this archive prints a start time**, so 09:00 local is an assumption,
and the window runs from there to roughly when the back of the field finishes. It is an
argument rather than a constant so the assumption can be moved and the effect measured.

## Removal

A runner who does not want to be named writes to the address in the crawler's user agent
and is removed from every future prediction file within a day. The removal is logged
without the name. Past prediction files are never edited, because a pre-registered
prediction that can be edited afterwards is not one; the runner is removed going forward
and the file's hash stays what it was.

## What reading all of it actually produced

Measured 2026-09-12 by `finishline dataset`, after the crawl.

| | |
|---|---:|
| Races read | 159 of 160 |
| Finishes parsed | 44,503 |
| Runners resolved | 15,689 |
| Held back as unresolvable | 119 |

**The one page that would not parse** is the 2017 Turkey Tea, which that year was
published as an HTML table by Athletics NorthEAST's timing software rather than as the
fixed-width text every other page uses. One page in eleven years; a second parser for it
is deferred and the gap is here rather than hidden.

**Three layouts, not two.** The plan said the archive had two. It has three: the general
one, the Tely 10's, and a third the Tely used in 2022 with a class code (`LM30-34`), a
place-of-field (`1/106`) and a net time, under a ruler drawn across three columns at once
and a header printed several characters left of its own data. It is read by counting: the
header's own columns come to nine and the rows measure nine, so they agree about the shape
of the table and can be read off in order.

## Race Roster, and the 2026 Tely 10

Checked 2026-09-12, before anything was fetched. This is the one source in this project
that took a judgement rather than a reading, so the judgement is written out.

### What it is

**The 2026 Tely 10 is not on nlaa.ca.** Every edition from 2018 to 2025 is published there
by the association itself, with the same eleven columns. In 2026 it timed the race on Race
Roster and its own Tely page links out instead. The race is 4,147 finishers in June, the
largest field in the province and the most recent big race before Cape to Cabot in October.

### Why it is read

Not because it was reachable. Because of who owns it:

- **The association owns the race and the data.** Race Roster is its timing vendor for one
  year. The results are the same race, the same runners and the same columns the
  association publishes itself in every other year.
- **The association was told.** Peter wrote to them before any of this saying he intended
  to use Tely data for this project. They can say stop at any time, and if they do, it
  stops: the cache is local and nothing from it is committed.
- **The results host invites crawlers.** `results.raceroster.com/robots.txt` allows
  `User-agent: *` and names two AI crawlers it does not. The results are public, no login.
- **One request, not four thousand.** The listing endpoint takes a limit and the site's own
  "show all" control asks for everything in a single call, so that is what this does. The
  payload is written to `data/cache/raceroster/` with its SHA-256 and read from disk
  forever after.

### The argument against, which is real

Race Roster's own terms are broad. Section 7 of its Terms of Service for Event Registrants
(2024-01-01) has a user agree "not to sell, license, rent, modify, distribute, copy,
reproduce, transmit, publicly display, publicly perform, publish, adapt, edit or create
derivative works of any Site Content", and its API License (2020-03-06) issues credentials
and requires "express consent" for access beyond documented parameters. Read on their own,
those say no.

**The first reading of this file said no on exactly that basis, and was overruled.** The
reason is that those clauses protect Race Roster's platform and content, and what is being
read here is the association's race, published by the association everywhere else, with the
association's knowledge. A permissive `robots.txt` is not a licence and did not decide it;
ownership and consent did.

⚠️ **This is Peter's decision rather than the code's, and it is recorded so a reader can
disagree with it.** If the association objects, or Race Roster does, the fix is one command
and one commit: drop the entry from `ingest/raceroster.REGISTER` and the race leaves the
archive. Nothing published depends on it being unavailable to challenge.

### What it changed

Measured on the Cape to Cabot start list, which is the first field this project predicts.

| | Without the 2026 Tely | With it |
|---|---:|---:|
| Entrants resolving to a runner in the archive | 386 of 453 (85%) | 415 (92%) |
| Entrants with a 2026 result, so current-season form | 166 (37%) | 333 (74%) |
| Entrants with no history at all | 67 | 38 |
| Finishes in the archive | 44,503 | 48,650 |
| Runners resolved | 15,689 | 17,099 |

One race doubled the share of the field whose current form the prediction can see.

### Route not taken, kept open

Asking the association to export the file themselves would have worked too and needs no
judgement about a third party's terms at all. The draft is still in [emails.md](emails.md)
and `ingest/resultsfile.py` imports a timing export onto the same rows, refusing a column it
does not recognise and refusing a file with no recorded source and date. If the association
would rather supply it that way, nothing else has to change.
