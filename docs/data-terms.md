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
and not on evidence. Rule C is about an approach that was tried and measured.

## NLAA road results: the archive this project runs on

Public pages at `https://www.nlaa.ca/results/`, one per race, results as fixed-width text
in a `<pre>` block. Footer reads "Copyright NLAA". There is no terms-of-use page and no
`robots.txt`. Results go back to 1978; this project reads 2016 onward.

**How it is read.** One request a second, never concurrent. Every page is written to
`data/cache/` on arrival and read from disk forever after, so a full rerun of the
pipeline costs zero requests. The SHA-256 and fetch time of every page are recorded in
`data/cache/nlaa/manifest.jsonl`. The user agent names the project and carries an address.

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
| Individual road races read | 287 |
| Distinct courses | 80 |
| Deepest course histories | 17 editions (Mews Memorial 8 km, Mundy Pond 5 km), 16 (Cape to Cabot 20 km) |
| Index rows skipped, each with its own reason | 46 |
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

## Athletics NorthEAST entrant lists

Public pages on the club's store, "up-to-the-minute", no privacy statement:

- Cape to Cabot: `athleticsnortheast.com/cart/index.php?main_page=page&id=4`
- Uniformed Services Run: the same path with `id=1`

Snapshotted daily from 2026-09-12 into `data/entrants/`, gitignored, by `finishline
snapshot`. It fetches at the same one request a second as the results crawler, sends the
same identifying user agent, and refuses to run until the courtesy notes have gone out
exactly as `crawl` does; CI asserts both refusals. It writes a file only when the page has
changed and a manifest row on every look, so a day with no new entries is recorded without
a second copy of the names.

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

## Weather

| Source | Use | Terms |
|---|---|---|
| Environment and Climate Change Canada, station 50089 (St. John's Intl A, climate ID 8403505) | Observed temperature, humidity, wind speed and direction for every past race morning, as a monthly CSV | Open Government Licence Canada |
| Open-Meteo forecast API | The forecast pulled before a race, recorded with the prediction | Free for non-commercial use, no key |
| Open-Meteo archive API | The comparison against the observations, so the gap between modelled and measured is itself reported | Same |

The observations are the backtest's basis because Overload measured Open-Meteo's modelled
temperature about 6 degrees Celsius off at this coast. There is no observation of the
future, so the live prediction uses the forecast and says so.

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
