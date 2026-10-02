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
