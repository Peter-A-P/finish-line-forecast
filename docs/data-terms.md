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

### What the archive holds, and what it does not

Measured by `finishline catalogue`, 2026-09-12, over the year indexes for 2016 to 2026.

| | |
|---|---|
| Individual road races read | 160 |
| Distinct courses | 45 |
| Index rows deliberately skipped | 39 |
| Years covered | 2016 to 2026, **no 2020** |

The skips, by reason:

| Rows | Reason |
|---:|---|
| 8 | cross-country, a different discipline on grass |
| 7 | team standings, a second view of a race already read |
| 6 | awards, likewise |
| 6 | school races |
| 5 | relays, which are not individual results |
| 4 | trail races, not comparable to a road course |
| 2 | children's races, two distances on one page |
| 1 | results published as a PDF (Run to Remember 2016) |

**Known holes, stated rather than discovered later.**

- **2020 is absent.** The season did not happen.
- **The 2026 Tely 10 is not on the results index**, though every edition from 2018 to
  2025 is. The Tely publishes its own archive at `/tely10/results/`, which is a second
  loader and is not built yet. Until it is, the largest field in the province is missing
  its most recent edition.
- **2016 and 2017 carry no Tely at all** on the main index, for the same reason.
- **One race is a PDF** and is not read. A PDF parser for one page in eleven years is not
  worth the week.
- **A team page is not a hole.** Seven of the skips are team standings for races whose
  individual results are read; counting them as races made nineteen editions of a race
  run seven times.

## Athletics NorthEAST entrant lists

Public pages on the club's store, "up-to-the-minute", no privacy statement:

- Cape to Cabot: `athleticsnortheast.com/cart/index.php?main_page=page&id=4`
- Uniformed Services Run: the same path with `id=1`

Snapshotted daily from 2026-09-12 into `data/entrants/`, gitignored. On 2026-09-12 the
Cape to Cabot list held 453 names with sex and shirt size against a cap of 500, and the
USR list held about 670 adults across five events.

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
