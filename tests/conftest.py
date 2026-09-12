"""Fixture plumbing.

Two kinds of fixture live here, and the difference is the point.

`tests/fixtures/` holds **committed golden pages**: the real column geometry of each
layout, down to the character, with invented runners in it. They pin what the parser must
keep doing and they run everywhere, including in CI on a machine that has never fetched
anything.

`data/cache/` holds **the real pages**, which are thousands of identifiable people and
are never committed. Tests that need them are skipped when the cache is empty. They check
the things only volume can check: that the row counts come out right on a four-thousand
runner field, and that every page in the archive parses at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CACHE = ROOT / "data" / "cache" / "nlaa"


def fixture(name: str) -> str:
    """A committed golden page."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def cached(name: str) -> str:
    """A real page from the local cache, or skip: CI has no cache and must not fetch."""
    path = CACHE / "pages" / name
    if not path.exists():
        pytest.skip(f"no cached page {name}; run 'finishline crawl' locally to fill the cache")
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture
def general_page() -> str:
    """The layout most NLAA road results use: gun time only, sex and place in one column."""
    return fixture("results_general.html")


@pytest.fixture
def tely_page() -> str:
    """The Tely 10's layout: two header lines, a chip time, and a misaligned ruler."""
    return fixture("results_tely.html")


@pytest.fixture
def index_page() -> str:
    """A year index, trimmed to the rows that exercise every decision the catalogue makes."""
    return fixture("results_index.html")
