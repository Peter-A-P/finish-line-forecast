"""The scheduled crawl and weather refresh stand down while a coming race needs the backtest."""

from __future__ import annotations

from pathlib import Path

import pytest

from finishline import cli


def _live(tmp_path: Path, when: str) -> Path:
    path = tmp_path / "live.toml"
    path.write_text(f'[r-race]\nname = "R"\ndate = "{when}"\n', encoding="utf-8")
    return path


def test_with_no_race_to_come_nothing_is_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "LIVE", _live(tmp_path, "2020-01-01"))
    monkeypatch.setattr(cli, "_dataset", lambda *_: pytest.fail("the archive need not be read"))
    assert cli._backtest_guard() is None


def test_a_matching_backtest_before_a_coming_race_pauses_the_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-10-25: a refresh 17 days after the backtest, before the fixed window, broke it."""
    monkeypatch.setattr(cli, "LIVE", _live(tmp_path, "2999-11-11"))
    monkeypatch.setattr(cli, "_dataset", lambda *_: object())
    monkeypatch.setattr(cli, "_edition_weather", lambda _: ({}, 0))
    monkeypatch.setattr(cli, "_blend_rows", lambda *_: ["a saved row"])
    reason = cli._backtest_guard()
    assert reason is not None and "r-race" in reason


def test_a_stale_backtest_guards_nothing_since_a_refresh_is_then_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "LIVE", _live(tmp_path, "2999-11-11"))
    monkeypatch.setattr(cli, "_dataset", lambda *_: object())
    monkeypatch.setattr(cli, "_edition_weather", lambda _: ({}, 0))
    monkeypatch.setattr(cli, "_blend_rows", lambda *_: None)
    assert cli._backtest_guard() is None
