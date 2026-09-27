"""Git must never convert a prediction file's line endings: its hash is published."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
@pytest.mark.parametrize(
    "path",
    ["predictions/tt-2026/daily-2026-09-27.json", "predictions/c2c-2026/final.json"],
)
def test_prediction_files_are_never_converted(path: str) -> None:
    # `predictions/*.json` matched nothing: the files live one folder down, per race.
    out = subprocess.run(
        ["git", "check-attr", "text", "--", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.strip().endswith("text: unset"), out
