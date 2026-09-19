"""Assembling a prediction file, against a posterior built by hand."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from finishline.history import History
from finishline.identity import link
from finishline.identity.resolve import Runner
from finishline.ingest.entrants import Entrant
from finishline.models import hierarchical as hm
from finishline.models import weather
from finishline.publish import daily, freeze
from finishline.publish import predictions as pf
from finishline.schema import Race, Result

NEWFOUNDLAND = timezone(timedelta(hours=-2, minutes=-30))
PAST = {
    "a": Race("a", "a", date(2025, 6, 1), 20_000.0, "c2c-20000", "x"),
    "b": Race("b", "b", date(2025, 8, 1), 10_000.0, "flat-10000", "x"),
}
LIVE = freeze.LiveRace(
    race=Race("c2c-2026", "Cape to Cabot", date(2026, 10, 18), 20_000.0, "c2c-20000", ""),
    gun=datetime(2026, 10, 18, 8, 0, tzinfo=NEWFOUNDLAND),
    entrant_list="c2c-2026",
)
NOW = datetime(2026, 10, 16, 9, 0, tzinfo=NEWFOUNDLAND)


def result(race_id: str, seconds: float) -> Result:
    return Result(race_id, 1, 1, "x", None, "F", 1, "40-49", 1, "Paradise", seconds, None)


def setup(
    sigma_eps: float = 0.03,
) -> tuple[hm.Posterior, list[link.Link], History]:
    archive = [
        Runner(
            "r1", "Ann Hynes", "Paradise", "F", (result("a", 5400.0), result("b", 2500.0)), False
        ),
        Runner("r2", "Bea Power", "Torbay", "F", (result("a", 6600.0),), False),
        Runner("r3", "Cy Walsh", None, "M", (result("b", 2400.0),), True),
    ]
    history = History.before(LIVE.race.date, PAST, archive)
    data = hm.design(history, min_finishes=1)
    assert data is not None
    draws = 400
    runners, groups, courses = len(data.runner_ids), len(data.groups), len(data.courses)
    posterior = hm.Posterior(
        design=data,
        alpha=np.tile(np.array([0.05, 0.30][:runners], dtype=np.float32), (draws, 1)),
        beta=np.zeros((draws, runners), dtype=np.float32),
        form=np.zeros((draws, runners), dtype=np.float32),
        mu_group=np.full((draws, groups), 0.35),
        mu_trend=np.zeros((draws, groups)),
        sigma_alpha=np.full(draws, 0.15),
        sigma_beta=np.zeros(draws),
        sigma_walk=np.full(draws, 0.03),
        course=np.full((draws, courses), 0.09),
        sigma_course=np.full(draws, 0.06),
        sigma_edition=np.full(draws, 0.04),
        latest_year=np.full(draws, 0.02),
        sigma_year=np.full(draws, 0.02),
        weather=np.zeros((draws, hm.WEATHER_TERMS)),
        nu=np.full(draws, 3.0),
        sigma_eps=np.full(draws, sigma_eps),
        newcomer_share=hm.newcomer_shares(data),
        diagnostics={"max_rhat": 1.02},
    )
    entrants = [
        Entrant("ANN HYNES", "F"),
        Entrant("Bea Power", "F"),
        Entrant("Cy Walsh", "M"),
        Entrant("Dee Newcomer", "F"),
    ]
    return posterior, link.link(entrants, archive), history


def assemble(**calibration: dict[str, float | None]) -> dict[str, Any]:
    posterior, links, history = setup()
    return freeze.assemble(
        posterior=posterior,
        links=links,
        history=history,
        live=LIVE,
        now=NOW,
        snapshot={"file": "c2c-2026_ane-list_20261016T1100Z.html", "sha256": "ab"},
        model={"name": "hierarchical", "commit": "0" * 40},
        calibration={
            0.80: calibration.get("eighty", {}),
            0.90: calibration.get("ninety", {}),
        },
        seed=7,
    )


def test_the_assembled_file_is_valid_and_excludes_the_refused() -> None:
    doc = assemble()
    assert pf.validate(doc) == []
    names = {runner["name"] for runner in doc["runners"]}
    assert names == {"ANN HYNES", "Bea Power", "Dee Newcomer"}
    assert doc["entrants"] == {"listed": 4, "linked": 2, "new": 1, "ambiguous": 1, "predicted": 3}


def test_a_linked_runner_carries_the_archive_hometown_and_a_newcomer_carries_none() -> None:
    doc = assemble()
    by_name = {runner["name"]: runner for runner in doc["runners"]}
    assert by_name["ANN HYNES"]["hometown"] == "Paradise"
    assert by_name["ANN HYNES"]["prior_results"] == 2
    assert by_name["Dee Newcomer"]["hometown"] is None
    assert by_name["Dee Newcomer"]["prior_results"] == 0


def test_the_conformal_shift_widens_only_its_own_stratum() -> None:
    plain = assemble()
    shifted = assemble(eighty={"0": 0.10}, ninety={"0": 0.10})

    def width(doc: dict[str, Any], name: str) -> float:
        runner = next(r for r in doc["runners"] if r["name"] == name)
        low, high = runner["interval_80"]
        return float(high - low)

    assert width(shifted, "Dee Newcomer") > 1.15 * width(plain, "Dee Newcomer")
    assert width(shifted, "ANN HYNES") == pytest.approx(width(plain, "ANN HYNES"))
    assert shifted["model"]["calibration"]["80"] == {"0": 0.10}


def test_a_large_negative_shift_cannot_publish_an_interval_that_misses_its_own_median() -> None:
    doc = assemble(eighty={"2 to 3": -2.0, "1": -2.0, "0": -2.0}, ninety={"0": -3.0})
    assert pf.validate(doc) == []


def test_freeze_refuses_inside_a_day() -> None:
    posterior, links, history = setup()
    with pytest.raises(pf.FreezeRefused):
        freeze.assemble(
            posterior=posterior,
            links=links,
            history=history,
            live=LIVE,
            now=LIVE.gun - timedelta(hours=10),
            snapshot={},
            model={"name": "hierarchical", "commit": "0" * 40},
            calibration={},
            seed=1,
        )


def test_the_same_inputs_freeze_to_the_same_bytes() -> None:
    assert pf.to_bytes(assemble()) == pf.to_bytes(assemble())


def test_a_live_race_without_a_confirmed_gun_time_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "live.toml"
    path.write_text(
        '[c2c-2026]\nname = "Cape to Cabot"\ndate = "2026-10-18"\ndistance_m = 20000\n'
        'course_id = "cape-to-cabot-20000"\nentrant_list = "c2c-2026"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no gun time"):
        freeze.load_live(path, "c2c-2026")
    path.write_text(
        path.read_text(encoding="utf-8") + 'gun = "2026-10-18T08:00:00"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no time zone"):
        freeze.load_live(path, "c2c-2026")


def test_the_weekly_crawl_stands_down_around_every_live_race(tmp_path: Path) -> None:
    path = tmp_path / "live.toml"
    path.write_text(
        '[c2c-2026]\ndate = "2026-10-18"\n\n[r2r-2026]\ndate = "2026-11-11"\n', encoding="utf-8"
    )
    assert freeze.crawl_paused(path, date(2026, 10, 7)) is None
    assert freeze.crawl_paused(path, date(2026, 10, 8)) is not None, "ten days before"
    assert freeze.crawl_paused(path, date(2026, 10, 19)) is not None, "the day after"
    assert freeze.crawl_paused(path, date(2026, 10, 20)) is None, "back for the results"
    reason = freeze.crawl_paused(path, date(2026, 11, 5))
    assert reason is not None and "r2r-2026" in reason, "no gun time needed to pause"
    assert freeze.crawl_paused(tmp_path / "missing.toml", date(2026, 10, 18)) is None


def test_the_forecast_used_is_recorded_and_moves_the_prediction() -> None:
    posterior, links, history = setup()
    hot = hm.Posterior(
        **{
            **{name: getattr(posterior, name) for name in hm.Posterior.__slots__},
            "weather": np.tile(np.array([0.01, 0.0, 0.0, 0.0, 0.0]), (posterior.draws, 1)),
        }
    )
    record = {"used": True, "source": "test", "conditions_mean": {"temp_c": 22.0}}

    def freeze_with(conditions: np.ndarray | None) -> dict[str, Any]:
        return freeze.assemble(
            posterior=hot,
            links=links,
            history=history,
            live=LIVE,
            now=NOW,
            snapshot={},
            model={"name": "hierarchical", "commit": "0" * 40},
            calibration={},
            seed=3,
            conditions=conditions,
            conditions_record=record if conditions is not None else None,
        )

    neutral = freeze_with(None)
    warm = freeze_with(
        np.tile(np.array([1.0, 22.0, 0.0, 0.0, 0.0, 0.0]), (posterior.draws, 1))
    )
    assert neutral["conditions"] is None
    assert warm["conditions"] == record
    assert pf.validate(warm) == []
    by_name = {runner["name"]: runner["seconds"] for runner in neutral["runners"]}
    for runner in warm["runners"]:
        assert runner["seconds"] > by_name[runner["name"]], "ten degrees warm is slower"


# --- the prediction week (publish/daily.py) ----------------------------------------


def build(
    entrants: list[Entrant], already: daily.Published | None = None, only_new: bool = False
) -> dict[str, Any]:
    posterior, _links, history = setup()
    archive = [
        runner
        for runner in (
            history.runners.get("r1"),
            history.runners.get("r2"),
            history.runners.get("r3"),
        )
        if runner is not None
    ]
    return freeze.assemble(
        posterior=posterior,
        links=link.link(entrants, archive),
        history=history,
        live=LIVE,
        now=NOW,
        snapshot={"file": "x.html", "sha256": "ab"},
        model={"name": "hierarchical", "commit": "0" * 40},
        calibration={0.80: {}, 0.90: {}},
        seed=7,
        already=already,
        only_new=only_new,
    )


def publish(tmp_path: Path, name: str, doc: dict[str, Any]) -> None:
    path = tmp_path / "c2c-2026" / name
    pf.write(path, doc)


def test_repeated_names_are_told_apart_by_order() -> None:
    already: daily.Published = {"ann hynes": [("daily-1.json", {"seconds": 1.0})]}
    new, carried, streams = daily.split(["ann hynes", "bea power", "ann hynes"], already)
    assert new == [1, 2], "the second Ann Hynes was not published before"
    assert carried[0][0] == "daily-1.json"
    assert streams == ["ann hynes#0", "bea power#0", "ann hynes#1"]


def test_a_daily_file_holds_only_the_new_and_no_places(tmp_path: Path) -> None:
    first = build([Entrant("Ann Hynes", "F"), Entrant("Dee Newcomer", "F")], only_new=True)
    assert pf.validate(first) == []
    assert first["kind"] == "daily"
    assert all("place" not in runner for runner in first["runners"])
    publish(tmp_path, "daily-2026-10-11.json", first)

    already = daily.published(tmp_path, "c2c-2026")
    second = build(
        [Entrant("Ann Hynes", "F"), Entrant("Bea Power", "F"), Entrant("Dee Newcomer", "F")],
        already,
        only_new=True,
    )
    assert [runner["name"] for runner in second["runners"]] == ["Bea Power"]
    assert second["entrants"]["published_before"] == 2


def test_a_runners_time_does_not_depend_on_who_else_is_on_the_list() -> None:
    alone = build([Entrant("Dee Newcomer", "F")], only_new=True)
    crowded = build(
        [Entrant("Ann Hynes", "F"), Entrant("Bea Power", "F"), Entrant("Dee Newcomer", "F")],
        only_new=True,
    )

    def dee(doc: dict[str, Any]) -> dict[str, Any]:
        return next(r for r in doc["runners"] if r["name"] == "Dee Newcomer")

    assert dee(alone) == dee(crowded)


def test_the_final_file_recomputes_everyone_and_names_where_they_first_appeared(
    tmp_path: Path,
) -> None:
    """Same fit, same random numbers: with the same morning, the same time as the daily line."""
    first = build([Entrant("Ann Hynes", "F")], only_new=True)
    publish(tmp_path, "daily-2026-10-11.json", first)
    final = build(
        [Entrant("Ann Hynes", "F"), Entrant("Bea Power", "F")],
        daily.published(tmp_path, "c2c-2026"),
    )
    assert pf.validate(final) == []
    by_name = {runner["name"]: runner for runner in final["runners"]}
    ann = by_name["Ann Hynes"]
    assert ann["first_published"] == "daily-2026-10-11.json"
    assert ann["seconds"] == first["runners"][0]["seconds"]
    assert ann["interval_80"] == first["runners"][0]["interval_80"]
    assert "first_published" not in by_name["Bea Power"]
    assert all("place" in runner for runner in final["runners"])


def test_a_daily_file_may_not_carry_places() -> None:
    doc = build([Entrant("Ann Hynes", "F")], only_new=True)
    doc["runners"][0]["place"] = {"median": 1, "low": 1, "high": 1}
    assert any("no places" in problem for problem in pf.validate(doc))


def test_the_saved_fit_is_refused_once_the_archive_moves(tmp_path: Path) -> None:
    posterior, _links, _history = setup()
    path = daily.posterior_path(tmp_path, "c2c-2026")
    daily.save_posterior(path, posterior, {"race_id": "c2c-2026", "key": "a"})
    assert daily.load_posterior(path, {"race_id": "c2c-2026", "key": "a"}) is not None
    with pytest.raises(ValueError, match="archive changed"):
        daily.load_posterior(path, {"race_id": "c2c-2026", "key": "b"})
    assert daily.load_posterior(tmp_path / "none.pkl", {}) is None


def test_the_forecast_error_is_taken_at_the_lead_and_never_a_shorter_one(tmp_path: Path) -> None:
    def table(lead: int, sd: float) -> list[str]:
        record = {
            "mornings": 30, "temp_bias": 0.0, "temp_sd": sd, "wind_bias": 0.0, "wind_sd": 1.0,
            "east_bias": 0.0, "east_sd": 1.0, "north_bias": 0.0, "north_sd": 1.0,
        }
        return [f'["{lead}"]', *(f"{k} = {v!r}" for k, v in record.items()), ""]

    path = tmp_path / "by_lead.toml"
    path.write_text("\n".join(table(1, 2.0) + table(3, 3.0) + table(7, 4.0)), encoding="utf-8")
    fallback = tmp_path / "missing.toml"
    assert daily.forecast_error_for(path, fallback, 1).temp_sd == 2.0
    assert daily.forecast_error_for(path, fallback, 5).temp_sd == 3.0
    assert daily.forecast_error_for(path, fallback, 9).temp_sd == 4.0
    assert isinstance(daily.forecast_error_for(path, fallback, 2), weather.ForecastError)


def test_published_reads_names_back_from_the_files(tmp_path: Path) -> None:
    doc = build([Entrant("ANN HYNES", "F")], only_new=True)
    publish(tmp_path, "daily-2026-10-11.json", doc)
    found = daily.published(tmp_path, "c2c-2026")
    assert list(found) == [daily.entrant_key(Entrant("Ann Hynes", None))]
    assert json.loads((tmp_path / "c2c-2026" / "daily-2026-10-11.json").read_text())["kind"] == (
        "daily"
    )


def test_the_race_page_shows_every_published_runner_once_and_the_top_places(
    tmp_path: Path,
) -> None:
    from finishline.publish import racepage

    first = build([Entrant("Ann Hynes", "F")], only_new=True)
    publish(tmp_path, "daily-2026-10-11.json", first)
    final = build(
        [Entrant("Ann Hynes", "F"), Entrant("Bea Power", "F")],
        daily.published(tmp_path, "c2c-2026"),
    )
    page = racepage.before_the_gun(
        [("daily-2026-10-11.json", first, "aa"), ("c2c-2026.json", final, "bb")]
    )
    assert page.count("| Ann Hynes |") == 2, "once in the top places, once in the full list"
    assert "Predicted top 20" in page and "`bb`" in page
    assert "| Bea Power |" in page
    assert racepage.clock(3725.4) == "1:02:05" and racepage.clock(1500) == "25:00"


def test_at_a_big_race_the_final_file_says_how_many_top_places_newcomers_take() -> None:
    from finishline.placing import unseen

    posterior, links, history = setup()
    source = unseen.Pool("c2c-20000", {}, np.array([-0.5, -0.3, 0.0, 0.2]), 5)
    doc = freeze.assemble(
        posterior=posterior,
        links=links,
        history=history,
        live=LIVE,
        now=NOW,
        snapshot={"file": "x.html", "sha256": "ab"},
        model={"name": "hierarchical", "commit": "0" * 40},
        calibration={0.80: {"0": 0.5}, 0.90: {"0": 0.5}},
        seed=7,
        pool=source,
    )
    assert pf.validate(doc) == []
    block = doc["newcomers"]
    assert block["pool_editions"] == 5 and block["pool_first_timers"] == 4
    assert 0 <= block["expected_in_top_10"]["mean"] <= 1, "one newcomer on the list"
    dee = next(r for r in doc["runners"] if r["name"] == "Dee Newcomer")
    low, high = dee["interval_80"]
    assert high / low < np.exp(0.8), "the pool's own spread, with no conformal shift on top"


def test_the_race_page_holds_places_for_runners_with_no_results_here() -> None:
    from finishline.publish import racepage

    doc = build([Entrant("Ann Hynes", "F"), Entrant("Bea Power", "F")])
    doc["newcomers"] = {
        "pool_editions": 9,
        "likely_places_top_20": [1],
        "expected_in_top_10": {"mean": 1.2, "low": 0, "high": 2},
        "expected_in_top_20": {"mean": 1.9, "low": 1, "high": 3},
    }
    page = "\n".join(racepage.top_table(doc))
    assert f"| 1 | {racepage.UNSEEN} |" in page
    assert "| 2 | Ann Hynes |" in page or "| 2 | Bea Power |" in page
    assert "1.2 of the top 10" in page


def test_the_website_is_built_from_the_committed_files_alone(tmp_path: Path) -> None:
    from finishline.publish import site

    doc = build([Entrant("Ann <Hynes>", "F")], only_new=True)
    publish(tmp_path / "predictions", "daily-2026-10-11.json", doc)
    live = tmp_path / "live.toml"
    live.write_text(
        '[c2c-2026]\nname = "Cape to Cabot"\ndate = "2026-10-18"\n'
        'gun = "2026-10-18T08:00:00-02:30"\n'
        '[r2r-2026]\nname = "Run to Remember"\ndate = "2026-11-11"\n',
        encoding="utf-8",
    )
    pages = site.build(
        tmp_path / "site", live, tmp_path / "predictions", tmp_path / "scores", date(2026, 10, 12)
    )
    assert {page.name for page in pages} == {"index.html", "c2c-2026.html", "r2r-2026.html"}
    race = (tmp_path / "site" / "c2c-2026.html").read_text(encoding="utf-8")
    assert "Ann &lt;Hynes&gt;" in race and "<Hynes>" not in race, "names are escaped"
    assert 'id="find"' in race and "daily-2026-10-11.json" in race
    assert "http" not in race.replace(site.REPOSITORY, ""), "no third-party request"
    front = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Prediction week: 1 daily file(s)" in front
    assert "Daily predictions start" in front, "Run to Remember is weeks away"
