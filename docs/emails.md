# The two courtesy notices, to send before the crawler runs

Written for Peter to send from his personal address. Nothing here is sent by any code in
this repository, and `finishline crawl` refuses until one of them has gone out.

Both say the same three things: what is fetched, how, and what for. Both offer to stop.

---

## 1. Newfoundland and Labrador Athletics Association

**To:** athletics@nlaa.ca
**Subject:** Heads-up: reading the public road results for a running-prediction project

> Hello,
>
> I am a data scientist in St. John's and a road runner, and I am building a personal
> project that predicts finish times for local road races and then publishes how wrong it
> was. It works from the public results on nlaa.ca, so I wanted to tell you before it
> fetches anything rather than after.
>
> What it does: reads the road-running results pages from 2016 onward, once. One request
> per second, never in parallel, each page saved locally and never fetched again. About
> 160 pages in total, so under half an hour, once.
>
> What it publishes: a predicted finish time for runners entered in an upcoming race,
> posted before the race, and the error afterwards. Runners are named only as your
> results pages already name them, first and last name and hometown, and nothing else.
> Nobody's raw results are republished, and anyone who asks to be left out is left out.
>
> The code and the write-up will be public, and the NLAA results are credited as the
> source throughout.
>
> If you would rather I did not, or you would like it run differently, say so and I will
> stop. If it would be useful to you, I am happy to share the predictions for any race
> you like before it happens.
>
> Thanks for keeping the archive up. It is a better record than most provinces have.
>
> Peter Parker

---

## 2. Athletics NorthEAST

**To:** admin@athleticsnortheast.com
**Subject:** Heads-up: using the public Cape to Cabot and USR registration lists

> Hello,
>
> I am building a personal project that predicts finish times for local road races and
> publishes the error afterwards, and Cape to Cabot on 18 October is the first race it
> will predict.
>
> It reads two things from your site: the public registration lists for Cape to Cabot and
> the Uniformed Services Run, so it knows who is entered. Nothing else, and nothing
> behind a login. It takes one copy a day and keeps it locally. The predictions use the
> name and, where your list prints it, the runner's sex; it does not use shirt size or
> anything else on the list.
>
> What gets published is a predicted time and placing per entrant, posted before the gun,
> and the measured error afterwards. Runners are named as the NLAA results pages already
> name them. Anyone who asks to be left out is left out.
>
> If you would rather I did not use the lists, say so and I will predict from past results
> alone instead, which works and is simply less complete.
>
> Happy to share the Cape to Cabot predictions with you before race day if that is of any
> use for corral or timing planning.
>
> Peter Parker

---

## After they have gone

```
finishline crawl --notices-sent
```

or set `FINISHLINE_NOTICES_SENT=1`. Record the date they were sent in
[data-terms.md](data-terms.md).

---

## 3. NLAA, for the 2026 Tely 10 results file

**To:** athletics@nlaa.ca
**Subject:** Would you be able to send the 2026 Tely 10 results file?

> Hello again,
>
> Following on from my note about the road-results project: I have everything from the
> site now, 2016 through 2026, and it is working well.
>
> The one gap is this year's Tely 10. Every edition from 2018 to 2025 is on nlaa.ca, but
> the 2026 results are on Race Roster and the Tely page links out to them. I would rather
> not pull them off Race Roster, because their terms do not really allow for it and it is
> your race and your data either way.
>
> Would you be able to export the 2026 finisher list from Race Roster and send it as a
> CSV? As the event organiser it should be a couple of clicks in the results dashboard.
> Names, times, categories and hometowns are all I need, exactly what the results pages
> already show; I have no use for email addresses or anything else on the registration
> side, and would rather not receive them.
>
> It matters more than one race normally would: about seven in ten of the people entered
> for Cape to Cabot next month have run a Tely at some point, so this June's race is the
> most recent form most of them have.
>
> If it is easier, posting it on nlaa.ca where the other years live would work just as
> well, and would be useful to more people than me.
>
> No rush and no problem if not.
>
> Peter Parker
