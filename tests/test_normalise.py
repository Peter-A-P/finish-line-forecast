"""Two spellings of one person have to become one string, or the history forks.

Each case here is a difference that really appears in the NLAA archive.
"""

from __future__ import annotations

import pytest

from finishline.identity import normalise

# Look-alike characters as code points. A reader cannot tell a straight apostrophe
# from a curly one in a diff, so the test names the character instead of showing it.
CURLY = chr(0x2019)   # right single quotation mark
EN_DASH = chr(0x2013)
NBSP = chr(0x00A0)
E_ACUTE = chr(0x00E9)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (f"St. John{CURLY}s", "St. John's"),
        (f"Portugal Cove{EN_DASH}St. Philip's", "Portugal Cove-St. Philip's"),
        ("  Cormac   Whitten  ", "Cormac Whitten"),
        (f"Bay{NBSP}Bulls", "Bay Bulls"),
    ],
)
def test_clean_fixes_the_punctuation_and_nothing_else(raw: str, expected: str) -> None:
    """What is published keeps its case, its accents and its hyphens."""
    assert normalise.clean(raw) == expected


def test_clean_leaves_accents_alone() -> None:
    """A published name is the runner's name. Only the matching key folds accents."""
    assert normalise.clean(f"B{E_ACUTE}langer") == f"B{E_ACUTE}langer"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("O'Brien", f"O{CURLY}Brien"),
        ("O'Brien", "OBrien"),
        (f"B{E_ACUTE}langer", "Belanger"),
        ("MacDonald", "Mac Donald"),
        ("Doe-Smith", "doe smith"),
        ("  Cormac   Whitten ", "Cormac Whitten"),
    ],
)
def test_one_runner_spelled_two_ways_gets_one_key(left: str, right: str) -> None:
    assert normalise.name_key(left) == normalise.name_key(right)


@pytest.mark.parametrize(("left", "right"), [("Mike Power", "Michael Power")])
def test_a_nickname_is_not_resolved(left: str, right: str) -> None:
    """Deliberate: a nickname table merges two people far more often than it joins one."""
    assert normalise.name_key(left) != normalise.name_key(right)


def test_two_different_runners_keep_different_keys() -> None:
    assert normalise.name_key("Cormac Whitten") != normalise.name_key("Cormac Witten")
    assert normalise.name_key("Ann Power") != normalise.name_key("Anne Power")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("St. John's", "St Johns"),
        ("St. John's", "Saint John's"),
        ("Portugal Cove-St. Philip's", "Portugal Cove St Philips"),
        ("MOUNT PEARL", "Mount Pearl"),
    ],
)
def test_one_town_spelled_two_ways_gets_one_key(left: str, right: str) -> None:
    assert normalise.town_key(left) == normalise.town_key(right)


def test_two_different_towns_keep_different_keys() -> None:
    assert normalise.town_key("St. John's") != normalise.town_key("Mount Pearl")


def test_a_missing_town_is_a_blank_not_a_mismatch() -> None:
    """A runner who gave no town once and Paradise twice is one runner, not two."""
    assert normalise.town_key(None) == ""
    assert normalise.town_key("") == ""


def test_the_initial_key_nominates_a_pair_without_merging_it() -> None:
    """`J Doe-Smith` and `Jane Doe-Smith` go to review, not to one runner."""
    assert normalise.initial_key("Jane Doe-Smith") == normalise.initial_key(
        "J. Doe-Smith"
    )
    assert normalise.name_key("Jane Doe-Smith") != normalise.name_key(
        "J. Doe-Smith"
    )
    assert normalise.initial_key("Jane Doe-Smith") != normalise.initial_key(
        "Jane Whitten"
    )
