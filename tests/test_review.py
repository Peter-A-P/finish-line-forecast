"""The labelled pairs: drawn by stratum, scored reweighted to the archive."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finishline.identity import review
from finishline.identity.resolve import resolve
from finishline.schema import Race, Result

RACES = {
    f"r{year}": Race(f"r{year}", "Road race", date(year, 6, 1), 10_000.0, "road-10000", "")
    for year in range(2016, 2026)
}


def row(year: int, name: str, town: str | None, band: str | None) -> Result:
    return Result(f"r{year}", 1, None, name, None, "F", None, band, None, town, 3000.0, None)


def test_near_first_names_are_a_prefix_or_one_letter_apart() -> None:
    assert review._near("chris", "christopher")
    assert review._near("jon", "joan")
    assert review._near("sara", "sarah")
    assert not review._near("ann", "ann")
    assert not review._near("mike", "michael")
    assert not review._near("al", "alan")  # too short to mean anything


def test_every_kind_of_decision_is_drawn_and_counted() -> None:
    results = [
        # One runner, one town, over three years.
        *(row(year, "Ann Hynes", "Paradise", "40-49") for year in (2016, 2017, 2018)),
        # One runner who moved.
        row(2016, "Bea Power", "Torbay", "30-39"),
        row(2020, "Bea Power", "Halifax", "30-39"),
        # Two runners of one name, told apart by age.
        row(2016, "Cy Walsh", "Mount Pearl", "20-29"),
        row(2017, "Cy Walsh", "Mount Pearl", "60-69"),
        # A result that could be either of them.
        row(2019, "Cy Walsh", None, None),
        # A near name in one town.
        row(2018, "Chris Keats", "Gander", "40-49"),
        row(2019, "Christopher Keats", "Gander", "40-49"),
    ]
    sample = review.draw(resolve(results, RACES), per_stratum=5)
    kinds = {pair.stratum: pair.resolver for pair in sample.pairs}
    assert kinds == {
        "merged, one town": "same",
        "merged, two towns": "same",
        "split by age": "different",
        "held back": "refused",
        "near names": "different",
    }
    assert all(sample.population[stratum] >= 1 for stratum in review.STRATA)


def test_the_sheet_is_never_replaced(tmp_path: Path) -> None:
    sample = review.Sample([], dict.fromkeys(review.STRATA, 0))
    path = tmp_path / "pairs.csv"
    review.write(path, sample, RACES)
    with pytest.raises(FileExistsError):
        review.write(path, sample, RACES)


def labelled(stratum: str, resolver: str, label: str) -> dict[str, str]:
    return {"pair": "1", "stratum": stratum, "resolver": resolver, "label": label}


def test_precision_is_reweighted_to_how_often_each_decision_happens() -> None:
    rows = [
        # Easy joins: all right. Hard joins: half wrong.
        *(labelled("merged, one town", "same", "same") for _ in range(10)),
        *(labelled("merged, two towns", "same", "same") for _ in range(5)),
        *(labelled("merged, two towns", "same", "different") for _ in range(5)),
        labelled("near names", "different", "unsure"),
        labelled("near names", "different", ""),
    ]
    population = {"merged, one town": 9_000, "merged, two towns": 1_000}
    measured = review.score(rows, population, draws=200)
    assert measured.precision is not None
    # 0.9 * 1.0 + 0.1 * 0.5, not the sheet's own 15 of 20.
    assert measured.precision[0] == pytest.approx(0.95)
    assert measured.unsure == 1 and measured.unlabelled == 1 and measured.labelled == 20


def test_recall_counts_a_refused_pair_as_not_joined() -> None:
    rows = [
        *(labelled("merged, one town", "same", "same") for _ in range(3)),
        *(labelled("held back", "refused", "same") for _ in range(3)),
    ]
    measured = review.score(rows, {"merged, one town": 100, "held back": 100}, draws=50)
    assert measured.recall is not None
    assert measured.recall[0] == pytest.approx(0.5)


def test_a_label_outside_the_three_is_refused() -> None:
    with pytest.raises(ValueError, match="not one of"):
        review.score([labelled("held back", "refused", "yes")], {"held back": 1})
