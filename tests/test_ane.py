"""Athletics NorthEAST's own finish lists: read the times from the end, never a badge as a town."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from finishline import store
from finishline.ingest import ane, nlaa, raceroster
from finishline.schema import Race

# The layout of the 2026 half marathon list, names invented: splits and a division before
# the chip and gun times.
PAGE = """
<table class="racetable">
  <tr><td class=h21 colspan="5">&nbsp;</td><td class=h21 colspan="2">--- 1st Loop ---</td>
      <td class=h21>Chip</td><td class=h21>Gun</td></tr>
  <tr><td class=h11>Place</td><td class=h12>Name</td><td class=h12>Badge</td>
      <td class=h11>Bib No</td><td class=h11>Div</td><td class=h11>Rnk</td>
      <td class=h11>Time</td><td class=h11>Time</td><td class=h11>Time</td></tr>
  <tr><td class=d01>1</td><td class=d02>Perpetua Sled</td><td class=d02>Eastern Health</td>
      <td class=d01>347</td><td class=d01>HM</td><td class=d01>1</td><td class=d01>37:55</td>
      <td class=d01>    1:15:08</td><td class=d01>1:15:10</td></tr>
  <tr><td class=d01>2</td><td class=d02>Tobias Hale-Ford</td><td class=d02>Fish &amp; Wildlife</td>
      <td class=d01>336</td><td class=d01>EH</td><td class=d01>2</td><td class=d01>38:03</td>
      <td class=d01>1:16:26</td><td class=d01>1:36:26</td></tr>
</table>
"""


def test_the_times_are_read_from_the_end_and_the_badge_is_not_a_town() -> None:
    first, second = ane.to_results(PAGE, "r")
    assert (first.place, first.name, first.bib) == (1, "Perpetua Sled", 347)
    assert (first.chip_seconds, first.gun_seconds) == (4508.0, 4510.0)
    assert second.chip_seconds == 4586.0, "an early starter's chip time is their run"
    assert all(r.hometown is None and r.club is None for r in (first, second))
    assert all(r.sex is None and r.age_band is None for r in (first, second))


class _Cache:
    """An NLAA cache that holds nothing, so only the external source can supply results."""

    def cached(self, url: str) -> bool:
        return False

    def get(self, url: str) -> str:
        raise AssertionError(url)


def test_a_posted_list_gives_way_once_the_association_carries_the_race(tmp_path: Path) -> None:
    listed = ane.REGISTER[1]
    (tmp_path / listed.cache_name).write_text(PAGE, encoding="utf-8")
    alone = store.build(_Cache(), [], ane_dir=tmp_path)  # type: ignore[arg-type]
    assert listed.race_id in alone.races

    same = Race("20260913-usr-half-marathon", "USR Half", listed.date, listed.distance_m,
                listed.course_id, nlaa.BASE + "x")
    both = store.build(_Cache(), [same], ane_dir=tmp_path)  # type: ignore[arg-type]
    assert listed.race_id not in both.races, "one race, counted once"
    assert same.race_id in both.races
    assert date(2026, 9, 13) == listed.date


def test_the_swap_is_visible_and_not_only_silent() -> None:
    """`store.build` has always dropped the outside copy. Nothing ever said that it had.

    A race changing hands changes what may be published about the runners in it: the club's
    lists print no sex, no age and no hometown, and the association's pages print all three.
    `finishline dataset` prints this list every time, so the day the USR moves is a line of
    output rather than something noticed later from a column that filled itself in.
    """
    listed = ane.REGISTER[1]
    before = {row.race_id: row for row in store.borrowed([])}
    assert before[listed.race_id].still_read
    assert before[listed.race_id].superseded_by is None
    assert before[listed.race_id].source == "Athletics NorthEAST"

    same = Race("20260913-usr-half-marathon", "USR Half", listed.date, listed.distance_m,
                listed.course_id, nlaa.BASE + "x")
    after = {row.race_id: row for row in store.borrowed([same])}
    assert not after[listed.race_id].still_read
    assert after[listed.race_id].superseded_by == same.race_id
    # The other events of the same day are on their own courses and are untouched by it.
    assert all(row.still_read for key, row in after.items() if key != listed.race_id)


def test_every_outside_race_is_in_that_list_and_says_where_it_came_from() -> None:
    rows = store.borrowed([])
    assert len(rows) == len(ane.REGISTER) + len(raceroster.REGISTER)
    assert {row.source for row in rows} == {"Athletics NorthEAST", "Race Roster"}
    assert all(row.name for row in rows)
