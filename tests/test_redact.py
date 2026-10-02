"""A runner who asked not to be named is never named, and the list never names them either."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from finishline.publish import daily, redact, scorecard
from finishline.schema import Result

KEY = bytes(range(32))


def _list(tmp_path: Path, *names: str) -> Path:
    path = tmp_path / "redactions.toml"
    entries = "".join(
        f'[[runner]]\ndigest = "{redact.digest(KEY, name)}"\nadded = "2026-10-02"\n\n'
        for name in names
    )
    path.write_text(entries, encoding="utf-8")
    return path


def test_the_list_holds_no_name_and_matches_any_spelling(tmp_path: Path) -> None:
    path = _list(tmp_path, "Jane O'Brien")
    assert "brien" not in path.read_text(encoding="utf-8").lower()
    hidden = redact.load(path, KEY)
    assert hidden.hides("JANE OBRIEN")
    assert hidden.hides("Jane O" + chr(0x2019) + "Brien")  # a curly apostrophe
    assert not hidden.hides("Jane Brien")


def test_without_the_key_it_refuses_rather_than_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(redact.KEY_ENV, raising=False)
    monkeypatch.setattr(redact, "KEY_FILE", tmp_path / "missing")
    with pytest.raises(RuntimeError, match="refusing to publish names"):
        redact.load(_list(tmp_path, "Jane Doe"), None)


def test_an_empty_list_needs_no_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(redact.KEY_ENV, raising=False)
    monkeypatch.setattr(redact, "KEY_FILE", tmp_path / "missing")
    assert redact.load(tmp_path / "none.toml", None).rows([{"name": "A B"}]) == [{"name": "A B"}]


def test_rows_keep_the_row_and_drop_who_it_is(tmp_path: Path) -> None:
    hidden = redact.load(_list(tmp_path, "Jane Doe", "John Roe"), KEY)
    rows: list[dict[str, object]] = [
        {"name": "John Roe", "hometown": "Paradise", "sex": "M", "age": "40-44", "seconds": 1.0},
        {"name": "Ann Poe", "hometown": "Torbay", "seconds": 2.0},
        {"name": f"{redact.LABEL} 1", "hometown": None, "seconds": 3.0},
        {"name": "Jane Doe", "hometown": "St. John's", "seconds": 4.0},
    ]
    shown = hidden.rows(rows)
    assert [row["name"] for row in shown] == [
        f"{redact.LABEL} 1", "Ann Poe", f"{redact.LABEL} 2", f"{redact.LABEL} 3"
    ]
    assert shown[0] == {"name": f"{redact.LABEL} 1", "hometown": None, "sex": None, "age": None,
                        "seconds": 1.0}
    assert shown[1]["hometown"] == "Torbay"
    assert rows[0]["name"] == "John Roe"  # the input is not changed


def test_add_makes_a_key_once_and_writes_only_a_hash(tmp_path: Path) -> None:
    path, key_file = tmp_path / "redactions.toml", tmp_path / ".env.redaction"
    assert redact.add("Jane Doe", "2026-10-02", path, key_file)
    assert not redact.add("JANE DOE", "2026-10-03", path, key_file)
    text = path.read_text(encoding="utf-8")
    assert "doe" not in text.lower()
    key = bytes.fromhex(key_file.read_text(encoding="utf-8").strip())
    assert redact.load(path, key).hides("Jane Doe")


def test_a_redacted_daily_line_is_found_again_by_its_hash(tmp_path: Path) -> None:
    folder = tmp_path / "tt-2026"
    folder.mkdir()
    line = {"name": f"{redact.LABEL} 1", "hometown": None, "redacted": "ab12"}
    (folder / f"{daily.DAILY_PREFIX}2026-09-27.json").write_text(
        json.dumps({"runners": [line, {"name": "Ann Poe"}]}), encoding="utf-8"
    )
    found = daily.published(tmp_path, "tt-2026")
    assert set(found) == {f"{daily.REDACTED}ab12", "annpoe"}


def test_the_score_finds_a_redacted_runner_by_hash(tmp_path: Path) -> None:
    hidden = redact.load(_list(tmp_path, "Jane Doe"), KEY)
    record = {
        "name": f"{redact.LABEL} 1", "hometown": None, "prior_results": 3, "seconds": 3000.0,
        "interval_80": [2800.0, 3200.0], "interval_90": [2700.0, 3300.0],
        "place": {"median": 5.0, "low": 2.0, "high": 9.0},
        "redacted": redact.digest(KEY, "Jane Doe"),
    }
    lines = scorecard.published({"runners": [record]})
    result = Result(
        race_id="tt-2026", place=4, bib=None, name="JANE DOE", club=None, sex="F",
        sex_place=None, age_band=None, category_place=None, hometown=None,
        gun_seconds=3050.0, chip_seconds=None,
    )
    matching = scorecard.match(lines, [result], hidden)
    assert matching.matches[0].outcome is scorecard.Outcome.FINISHED
