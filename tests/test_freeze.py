"""Assembling a prediction file, against a posterior built by hand."""

from __future__ import annotations

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
from finishline.publish import freeze
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
        gamma=np.zeros((draws, runners), dtype=np.float32),
        mu_group=np.full((draws, groups), 0.35),
        sigma_alpha=np.full(draws, 0.15),
        sigma_beta=np.zeros(draws),
        course=np.full((draws, courses), 0.09),
        sigma_course=np.full(draws, 0.06),
        sigma_edition=np.full(draws, 0.04),
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
