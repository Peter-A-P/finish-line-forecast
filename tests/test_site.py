"""The website build: what the race card says about its field."""

from __future__ import annotations

from finishline.publish import site


def test_the_card_counts_entrants_from_the_newest_file() -> None:
    def daily_file(name: str, priors: list[int], listed: int, ambiguous: int) -> site.Published:
        doc = {
            "kind": "daily",
            "frozen_at": f"{name[6:16]}T08:45:00+00:00",
            "entrants": {"listed": listed, "ambiguous": ambiguous},
            "runners": [{"prior_results": prior} for prior in priors],
        }
        return site.Published(name, doc, "")

    files = [
        daily_file("daily-2026-09-27.json", [0, 1, 5, 7], 5, 1),
        daily_file("daily-2026-09-28.json", [2], 6, 1),
    ]
    counted = site.entrants_from_files(files)
    assert counted is not None
    assert counted["as_of"] == "2026-09-28"
    assert counted["listed"] == 6
    assert counted["refused"] == 1
    assert sum(counted["depth"].values()) + counted["refused"] == counted["listed"]
    assert site.entrants_from_files([]) is None


def test_a_scored_race_shows_each_finish_beside_its_prediction() -> None:
    line = {"name": "Ann Poe", "hometown": "Torbay", "prior_results": 3, "seconds": 3000.0,
            "interval_80": [2800.0, 3200.0], "interval_90": [2700.0, 3300.0]}
    other = {**line, "name": "Bea Roe", "seconds": 3100.0}
    files = [site.Published("daily-2026-10-01.json", {"kind": "daily", "runners": [line, other]},
                            "")]
    card = {"finishers": [{"name": "Ann Poe", "actual": 3050.0, "place": 7}]}
    rows = {row["name"]: row for row in site.race_predictions(files, card)["runners"]}
    assert rows["Ann Poe"]["actual"] == 3050.0 and rows["Ann Poe"]["actual_place"] == 7
    assert "actual" not in rows["Bea Roe"]  # no show, or not found: no result to show
