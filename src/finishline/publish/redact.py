"""Runners who asked not to be named: every published table shows them as a redacted row.

A runner who writes to ask is added with `finishline redact "<name>"`, and from then on every
name this project publishes passes through `Redactions.rows`: the prediction file `freeze`
writes, the race page, the scorecard, the retrospective, and the website. The row stays,
because the runner is still in the field and still moves everyone else's place; the name,
the hometown and any printed gender and age become `Redacted name 1`, `Redacted name 2` and
blanks, numbered down the table.

WHY THE LIST HOLDS NO NAMES
---------------------------
A public list of the people who asked not to be named would name them. `data/redactions.toml`
holds a keyed hash (HMAC-SHA256) of each name's matching key (`normalise.name_key`), so
`Jane O'Brien` and `JANE OBRIEN` are one entry, and nobody without the key can test a name
against it. The key is in `.env.redaction` on Peter's machine (gitignored with every `.env.*`)
and in the repository secret `FINISHLINE_REDACTION_KEY` for the website build. It is never
committed.

⚠️ **Fails closed.** With entries in the list and no key, `load` raises rather than publishing
every name, and the daily task and the website build stop with it.

⚠️ **The match is on the name alone.** Two runners of one name are both redacted: hiding a
stranger's name by mistake costs nothing, and showing the name of someone who asked not to be
shown is the failure this module exists to prevent.

⚠️ **A file tagged before the request keeps the name.** A prediction is only a prediction if it
cannot be edited after its tag, so the repository's copy is left as it is, and every page this
project renders from it, the website included, shows the redacted row instead. docs/data-terms.md
"Removal" says so to the runner.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from finishline.identity.normalise import name_key

ROOT = Path(__file__).resolve().parents[3]
LIST = ROOT / "data" / "redactions.toml"
KEY_FILE = ROOT / ".env.redaction"
KEY_ENV = "FINISHLINE_REDACTION_KEY"
LABEL = "Redacted name"

# Everything a row may carry that says who it is, beside the name.
_IDENTIFYING = ("hometown", "sex", "age", "age_from")


@dataclass(frozen=True)
class Redactions:
    """The keyed hashes of the names not to publish, and the key that tests a name."""

    digests: frozenset[str]
    key: bytes | None

    def hides(self, name: str) -> bool:
        if not self.digests or self.key is None:
            return False
        return digest(self.key, name) in self.digests

    def rows(self, rows: Iterable[Mapping[str, Any]], field: str = "name") -> list[dict[str, Any]]:
        """The rows in their order, each redacted one renamed and numbered down the table."""
        out: list[dict[str, Any]] = []
        count = 0
        for row in rows:
            copy = dict(row)
            name = str(copy.get(field) or "")
            # A line a file already published redacted is renumbered with the rest.
            if self.hides(name) or name.startswith(f"{LABEL} "):
                count += 1
                copy[field] = f"{LABEL} {count}"
                for other in _IDENTIFYING:
                    if other in copy:
                        copy[other] = None
            out.append(copy)
        return out


def digest(key: bytes, name: str) -> str:
    return hmac.new(key, name_key(name).encode("utf-8"), hashlib.sha256).hexdigest()


def read_key(env: Mapping[str, str] | None = None, key_file: Path | None = None) -> bytes | None:
    value = (os.environ if env is None else env).get(KEY_ENV, "").strip()
    key_file = KEY_FILE if key_file is None else key_file
    if not value and key_file.exists():
        value = key_file.read_text(encoding="utf-8").strip()
    return bytes.fromhex(value) if value else None


def load(path: Path = LIST, key: bytes | None = None) -> Redactions:
    """The list, ready to test names; raises if it has entries and there is no key."""
    entries: list[dict[str, Any]] = []
    if path.exists():
        entries = list(tomllib.loads(path.read_text(encoding="utf-8")).get("runner", []))
    digests = frozenset(str(entry["digest"]) for entry in entries)
    if key is None:
        key = read_key()
    if digests and key is None:
        raise RuntimeError(
            f"{len(digests)} runner(s) asked not to be named and there is no redaction key "
            f"(set {KEY_ENV} or write {KEY_FILE.name}); refusing to publish names"
        )
    return Redactions(digests, key)


@cache
def default() -> Redactions:
    """The repository's list, loaded once per run."""
    return load()


def add(name: str, today: str, path: Path = LIST, key_file: Path | None = None) -> bool:
    """Add a runner to the list by hash, making the key on first use; False if already there."""
    key_file = KEY_FILE if key_file is None else key_file
    key = read_key(key_file=key_file)
    if key is None:
        key = secrets.token_bytes(32)
        key_file.write_text(key.hex() + "\n", encoding="utf-8")
    entry = digest(key, name)
    if entry in load(path, key).digests:
        return False
    text = path.read_text(encoding="utf-8") if path.exists() else HEADER
    block = f'[[runner]]\ndigest = "{entry}"\nadded = "{today}"\n'
    path.write_text(text.rstrip("\n") + "\n\n" + block, encoding="utf-8", newline="\n")
    return True


HEADER = """# Runners who asked not to be named (publish/redact.py). Each entry is a keyed hash of
# the name, never the name: the list would otherwise name the people who asked not to be named.
# Add one with `finishline redact "<name as printed>"`; the date is the day of the request.
"""
