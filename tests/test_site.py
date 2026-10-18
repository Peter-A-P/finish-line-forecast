"""The website build: what the race card says about its field."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

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


def test_the_architecture_page_shows_every_diagram_as_committed(tmp_path: Path) -> None:
    """Rendered from docs/architecture.md, so every diagram in docs/ is on it, copied as is."""
    written = site.write_architecture(tmp_path)
    page = (tmp_path / "architecture.html").read_text(encoding="utf-8")
    docs = Path("docs") / "architecture"
    shown = set(re.findall(r'<img src="architecture/([^"]+)"', page))
    assert shown == {p.name for p in docs.glob("*.svg")}
    assert len(shown) >= 3
    for name in shown:
        assert (tmp_path / "architecture" / name).read_bytes() == (docs / name).read_bytes()
    assert tmp_path / "architecture.html" in written
    assert "{{" not in page and 'aria-current="page">How it' in page
    # A way back at the bottom, for a reader who has scrolled past every diagram.
    assert page.rindex('<p class="arch-back"><a href="index.html">') > page.rindex("<img ")
    assert not re.search(r"<script|<style|\sstyle=", page)


def test_the_front_page_carries_the_menu_and_an_early_link_to_it() -> None:
    page = Path("web/index.html").read_text(encoding="utf-8")
    menu = page.partition('<nav class="tabs"')[2].partition("</nav>")[0]
    assert 'href="architecture.html"' in menu
    for anchor in re.findall(r'href="#([^"]+)"', menu):
        assert f'id="{anchor}"' in page, anchor
    hero = page.partition('<header class="hero"')[2].partition("</header>")[0]
    assert 'href="architecture.html"' in hero


def test_a_scored_race_is_run_and_an_opened_registration_is_open() -> None:
    today = date(2026, 10, 18)
    assert site.group_of({"date": "2026-10-18", "stage": "scored"}, 503, today) == "run"
    assert site.group_of({"date": "2026-10-18", "stage": "final"}, 503, today) == "open"
    assert site.group_of({"date": "2026-11-11", "stage": "before"}, None, today) == "announced"
    assert site.group_of(
        {"date": "2026-11-11", "stage": "before"}, None, today, date(2026, 10, 16)
    ) == "open"
    assert site.group_of(
        {"date": "2026-11-11", "stage": "before"}, None, today, date(2026, 10, 20)
    ) == "announced"
