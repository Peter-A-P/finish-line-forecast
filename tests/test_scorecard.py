"""Scoring a tagged prediction: the tag rule, the matching, and the numbers."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from finishline import cli
from finishline.publish import predictions as pf
from finishline.publish import scorecard as sc
from finishline.schema import Result

NEWFOUNDLAND = timezone(timedelta(hours=-2, minutes=-30))
GUN = datetime(2026, 10, 18, 8, 0, tzinfo=NEWFOUNDLAND)


def line(
    name: str, seconds: float, *, hometown: str | None = None, prior: int = 2, spread: float = 300.0
) -> pf.RunnerPrediction:
    return pf.RunnerPrediction(
        name=name,
        hometown=hometown,
        prior_results=prior,
        seconds=seconds,
        interval_80=(seconds - spread, seconds + spread),
        interval_90=(seconds - 1.5 * spread, seconds + 1.5 * spread),
        place=1.0,
        place_low=1.0,
        place_high=3.0,
    )


def doc(runners: list[pf.RunnerPrediction]) -> dict[str, Any]:
    return pf.document(
        race={
            "race_id": "c2c-2026",
            "name": "Cape to Cabot",
            "date": "2026-10-18",
            "distance_m": 20000.0,
            "course_id": "cape-to-cabot-20000",
        },
        gun=GUN,
        frozen_at=GUN - timedelta(days=1, hours=2),
        snapshot={"file": "list.html", "sha256": "ab"},
        model={"name": "hierarchical", "commit": "0" * 40},
        conditions=None,
        entrants={"listed": 6, "linked": 4, "new": 1, "ambiguous": 1, "predicted": len(runners)},
        runners=runners,
    )


def result(
    name: str, seconds: float | None, *, place: int | None = 1, hometown: str | None = None
) -> Result:
    return Result("20261018-c2c", place, None, name, None, "F", None, None, None, hometown,
                  seconds, None)


def test_a_tag_a_day_before_the_gun_counts_and_a_later_one_does_not() -> None:
    sc.check_tag(GUN - timedelta(hours=25), GUN)
    with pytest.raises(sc.NotPreRegistered, match="at least"):
        sc.check_tag(GUN - timedelta(hours=23), GUN)
    with pytest.raises(sc.NotPreRegistered, match="time zone"):
        sc.check_tag(datetime(2026, 10, 16, 8, 0), GUN)


def test_the_tag_message_has_to_publish_the_hash_of_the_tagged_bytes() -> None:
    data = pf.to_bytes(doc([line("Ann Hynes", 6000.0)]))
    digest = sc.check_digest(data, f"sha256 {pf.sha256(data)}\n")
    assert digest == pf.sha256(data)
    with pytest.raises(sc.NotPreRegistered, match="does not publish"):
        sc.check_digest(data + b" ", f"sha256 {digest}\n")


def test_matching_is_by_name_key_and_refuses_to_guess() -> None:
    lines = sc.published(
        doc(
            [
                line("ANN HYNES", 6000.0),
                line("Bea Power", 7000.0, hometown="Torbay"),
                line("Cy Walsh", 6500.0),
                line("Dee Noshow", 8000.0),
                line("Eve Quit", 7500.0),
                line("Fay Twin", 7100.0),
                line("fay twin", 7200.0),
            ]
        )
    )
    results = [
        result("Ann Hynes", 6100.0),
        result("Bea Power", 6900.0, hometown="Torbay"),
        result("Bea Power", 5000.0, hometown="Paradise"),
        result("Cy Walsh", 6400.0, hometown="Torbay"),
        result("Cy Walsh", 6600.0, hometown="Paradise"),
        result("Eve Quit", None, place=None),
        result("Fay Twin", 7150.0),
        result("Gus Late", 5500.0),
    ]
    matching = sc.match(lines, results)
    outcome = {item.line.name: item.outcome for item in matching.matches}
    assert outcome["ANN HYNES"] is sc.Outcome.FINISHED
    assert outcome["Bea Power"] is sc.Outcome.FINISHED, "the published town breaks the tie"
    assert outcome["Cy Walsh"] is sc.Outcome.AMBIGUOUS, "no town was published to break it"
    assert outcome["Dee Noshow"] is sc.Outcome.NOT_FOUND
    assert outcome["Eve Quit"] is sc.Outcome.DID_NOT_FINISH
    assert outcome["Fay Twin"] is sc.Outcome.AMBIGUOUS
    assert outcome["fay twin"] is sc.Outcome.AMBIGUOUS
    bea = next(item for item in matching.matches if item.line.name == "Bea Power")
    assert bea.actual == 6900.0
    assert matching.finishers == 7
    assert matching.unpredicted_finishers == 5  # two Walshes, the other Power, Fay, Gus


def scored() -> tuple[dict[str, Any], sc.Matching]:
    prediction = doc(
        [
            line("Ann Hynes", 6000.0, prior=5),
            line("Bea Power", 7000.0, prior=5),
            line("Cy Walsh", 6500.0, prior=0),
            line("Dee Noshow", 8000.0, prior=1),
        ]
    )
    results = [
        result("Ann Hynes", 6100.0, place=1),  # inside the 80
        result("Bea Power", 7400.0, place=3),  # outside the 80, inside the 90
        result("Cy Walsh", 5000.0, place=2),  # outside both
    ]
    lines = sc.published(prediction)
    matching = sc.match(lines, results)
    positions = {item.line.name: item.line.position for item in matching.matches}
    card = sc.evaluate(
        doc=prediction,
        matching=matching,
        carry_forward={positions["Ann Hynes"]: 6300.0, positions["Bea Power"]: 7000.0},
        prediction={
            "file": "predictions/c2c-2026.json",
            "sha256": "f" * 64,
            "tag": "predictions/c2c-2026",
            "tagged_at": (GUN - timedelta(days=1, hours=1)).isoformat(),
            "model": "hierarchical",
            "commit": "0" * 40,
        },
        results={"race_id": "20261018-c2c", "url": "https://example", "sha256": "e" * 64},
        scored_at=GUN + timedelta(days=3),
    )
    return card, matching


def test_the_card_counts_the_field_and_scores_the_intervals() -> None:
    card, _matching = scored()
    field = card["field"]
    assert (field["predicted"], field["finished"], field["not_found"]) == (4, 3, 1)
    assert card["shares"]["predictions_that_finished"] == pytest.approx(0.75)
    assert card["shares"]["entrants_with_history"] == pytest.approx(4 / 6)

    intervals = card["intervals"]["all"]
    assert intervals["80"]["coverage"][0] == pytest.approx(1 / 3)
    assert intervals["90"]["coverage"][0] == pytest.approx(2 / 3)
    assert intervals["80"]["median_width_minutes"] == pytest.approx(10.0)
    assert card["intervals"]["by_stratum"]["0"]["80"]["coverage"][0] == 0.0
    assert card["intervals"]["by_stratum"]["1"]["runners"] == 0


def test_carry_forward_is_compared_on_the_runners_it_answered_for() -> None:
    card, _matching = scored()
    errors = card["error"]["all"]
    assert errors["runners"] == 3
    assert errors["mae_minutes"][0] == pytest.approx((100 + 400 + 1500) / 3 / 60)
    paired = errors["carry_forward"]
    assert paired["runners"] == 2, "Cy had no history, so carry-forward said nothing"
    # Model |100| and |400| seconds against carry-forward |200| and |400|.
    assert paired["difference_minutes"][0] == pytest.approx((-100 + 0) / 2 / 60)
    low, high = paired["difference_minutes"][1:]
    assert low <= paired["difference_minutes"][0] <= high


def test_the_card_is_canonical_json_with_no_nan() -> None:
    card, _matching = scored()
    assert pf.to_bytes(card) == pf.to_bytes(card)


def test_the_page_names_finishers_and_never_the_runners_who_did_not_appear() -> None:
    card, matching = scored()
    page = sc.race_page(card, matching)
    assert "Ann Hynes" in page and "Cy Walsh" in page
    assert "Dee Noshow" not in page
    assert "One race is one morning" in page
    assert chr(0x2014) not in page and chr(0x2013) not in page


def test_the_readme_row_links_the_race_page_and_says_what_its_intervals_mean() -> None:
    assert "No prediction has been scored yet" in sc.live_table([])
    card, _matching = scored()
    table = sc.live_table([card])
    assert "docs/predictions/c2c-2026.md" in table
    assert "predictions/c2c-2026" in table
    assert "resample runners within each race" in table


def git(root: Path, *args: str, when: datetime | None = None) -> None:
    env = None
    if when is not None:
        import os

        env = {**os.environ, "GIT_COMMITTER_DATE": when.isoformat()}
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example", *args],
        cwd=root,
        check=True,
        capture_output=True,
        env=env,
    )


def test_the_command_refuses_an_untagged_or_late_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    git(tmp_path, "init", "-q")
    path = tmp_path / "predictions" / "c2c-2026.json"
    digest = pf.write(path, doc([line(name, 6000.0) for name in ("Ann", "Bea", "Cy")]))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "Prediction")
    runner = CliRunner()

    untagged = runner.invoke(cli.app, ["score", "c2c-2026"])
    assert untagged.exit_code == 2
    assert "not a prediction" in untagged.output

    late = GUN - timedelta(hours=2)
    git(tmp_path, "tag", "-a", "predictions/c2c-2026", "-m", f"sha256 {digest}", when=late)
    refused = runner.invoke(cli.app, ["score", "c2c-2026"])
    assert refused.exit_code == 2
    assert "at least" in refused.output
