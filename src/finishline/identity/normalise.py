"""Making two spellings of one person into one string.

WHY THIS IS NOT COSMETIC
------------------------
There is no runner identifier anywhere in the NLAA archive. Bib numbers are per race and
reissued every year, so the only thing linking a 2024 result to a 2025 one is the text of
a name and a town. That makes every difference in spelling a fork in the history, and a
runner whose four results land in two piles of two gets a thinner history, a wider
interval and a worse prediction than the archive can actually support.

The differences are real and they are everywhere in this archive:

- **Curly and straight apostrophes.** The index prints `Kid&#8217;s`, the results pages
  print `St. John's`. Spelled either way it is the same apostrophe, and `O'Brien` sorts
  into two piles without this.
- **Accents.** `Belanger` and `Bel` + e-acute + `nger`.
- **Case and spacing.** `MacDonald`, `Macdonald`, `Mac Donald`.
- **Punctuation in towns.** `St. John's`, `St Johns`, `Saint John's` are one place, and
  `Portugal Cove-St. Philip's` is printed with and without the hyphen.

WHAT IS DELIBERATELY NOT DONE
-----------------------------
⚠️ **Nicknames are not resolved.** `Mike Power` and `Michael Power` stay apart. A
nickname table would merge two runners who really are different far more often than it
would join one who is the same, and this project would rather publish two thin histories
than one prediction for the wrong person.

⚠️ **The key is for matching only; the published name is the one the page printed.** A
prediction names a runner exactly as the results name them (PLAN.md 2.8), so `clean` is
applied to what is published and the aggressive `name_key` never is.
"""

from __future__ import annotations

import re
import unicodedata

# Typographic characters that mean the same thing as their plain equivalents. Two
# spellings of one apostrophe are not two apostrophes.
#
# Written as code points rather than as the characters themselves, so this file stays
# pure ASCII. A reader cannot tell a straight apostrophe from a curly one in a diff, and
# a table of look-alikes written in look-alikes is unreviewable.
_PUNCTUATION = str.maketrans(
    {
        0x2018: "'",  # left single quotation mark
        0x2019: "'",  # right single quotation mark, which is what most software emits
        0x201A: "'",  # single low-9 quotation mark
        0x201B: "'",  # single high-reversed-9 quotation mark
        0x201C: '"',  # left double quotation mark
        0x201D: '"',  # right double quotation mark
        0x201E: '"',  # double low-9 quotation mark
        0x2010: "-",  # hyphen
        0x2011: "-",  # non-breaking hyphen
        0x2012: "-",  # figure dash
        0x2013: "-",  # en dash
        0x2014: "-",  # em dash
        0x2015: "-",  # horizontal bar
        0x2212: "-",  # minus sign
        0x00A0: " ",  # no-break space
    }
)

# Town spellings that are one place. Kept short and obvious on purpose: every entry is a
# claim that two strings are the same town, and a wrong one merges two runners.
_TOWN_PREFIX = re.compile(r"^(st|ste|saint|sainte)\b\.?\s+")


def clean(text: str) -> str:
    """A string as it should be stored: one kind of quote, one kind of space.

    This is what gets published, so it changes punctuation and nothing else. The name
    keeps its case, its accents and its hyphens, because that is the runner's name.
    """
    out = unicodedata.normalize("NFC", text).translate(_PUNCTUATION)
    return re.sub(r"\s+", " ", out).strip()


def _fold(text: str) -> str:
    """Lower case with the accents taken off, for comparison only."""
    stripped = unicodedata.normalize("NFD", clean(text).lower())
    return "".join(char for char in stripped if not unicodedata.combining(char))


def _words(text: str) -> list[str]:
    """The alphanumeric runs of a folded string."""
    return re.findall(r"[a-z0-9]+", _fold(text))


def name_key(name: str) -> str:
    """A name reduced to what two spellings of it have in common.

    ⚠️ **Punctuation and spacing are removed rather than replaced by a space**, and the
    difference is the whole value of the key. Replacing them turns `O'Brien` into
    `o brien` and leaves `OBrien` as `obrien`, which are two runners again; and it can
    never join `MacDonald` to `Mac Donald`, which the archive spells both ways. Removing
    them lands each pair on one key, `obrien` and `macdonald`.

    Letters and their order stay, so `Ann` and `Anne` remain two people, and `Mike` and
    `Michael` deliberately do too.
    """
    return "".join(_words(name))


def town_key(town: str | None) -> str:
    """A hometown reduced for comparison, with the saints spelled one way.

    `St. John's`, `St Johns` and `Saint John's` are one town. An unprinted hometown is
    the empty string rather than None so it compares as a value: a runner who gave no
    town in one race and `Paradise` in another is not evidence of two runners, and the
    resolver treats a blank as "no information" rather than as a mismatch.
    """
    if not town:
        return ""
    return "".join(_words(_TOWN_PREFIX.sub("st ", _fold(town))))


def initial_key(name: str) -> str:
    """A looser key: first initial and surname, for finding candidate duplicates.

    `Jane Doe-Smith` and `J Doe-Smith` are almost certainly one person,
    but "almost certainly" is not the same as "yes", so this key only ever nominates a
    pair for review (`identity/resolve.py`); it never merges one on its own.
    """
    parts = _words(name)
    if len(parts) < 2:
        return name_key(name)
    return f"{parts[0][:1]}{parts[-1]}"
