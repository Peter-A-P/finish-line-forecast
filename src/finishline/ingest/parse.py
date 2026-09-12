"""The NLAA results parser: fixed-width text inside a <pre> block.

WHAT THE PAGES ACTUALLY LOOK LIKE
---------------------------------
Every road result on nlaa.ca is a plain-text table wrapped in one `<pre>` element,
produced by the timing company's software rather than by a web template. Two layouts
appear across 2016 to 2026. The general one, cut short here at the hometown::

    POS   BIB              NAME              TIME     F/M      AGE    CAT   HOMETOWN
    ----- ------ --------------------------- ------- -------- ------- ----- ---------
       1    645   Cormac Whitten (ANER)       32:51   M(1)     30-39     1   Harbourm

and the Tely 10's, which is the only one carrying a chip time, and whose header runs
over two lines::

    O'all                                    Gun      Class       Gender Pace  Chip
    Place  Bib       Name                    Time     Placing     Place  /Mi   Time   City
    ----- ----- -------------------------  ------- ------------- ----- ----- ------- ------
        1  2861 Cormac Whitten              50:28   M25-29    1      1  5:03   50:28 Harbou

Both are in `tests/fixtures/` at their true widths, with invented runners in them.

WHY THE RULER LINE IS THE PARSER
--------------------------------
The obvious approach is to split each row on runs of whitespace. It fails on the first
row it meets: names contain spaces, hometowns contain spaces ("Portugal Cove-St.
Philip's"), the Tely's class placing is two values in one field, and a missing value
leaves a hole that shifts every column after it. Counting from the left in characters is
the only thing that survives, and the pages hand us the character positions directly: the
row of dashes under the header has one run per column, in the right places.

So this module never guesses a column boundary. It finds the ruler, slices the header and
every data row by it, and matches the header text against a table of names it knows. A
layout whose header it does not recognise raises `UnknownColumns` naming the headers,
because a results page silently parsed into the wrong columns is exactly the confident
wrong number this project exists not to publish. The crawl reports those pages and the
map is extended deliberately.

⚠️ **The ruler names the columns; the data decides where they are.** The Tely's dashes
are drawn a few characters right of the values under them: its gender-place column is
declared at 72 to 77 and the numbers actually sit at 71 to 75, with the pace beginning at
76. Slicing by the dashes therefore takes the first digit of the pace into the place and
leaves the pace short, which is a wrong number in both columns and no error anywhere. So
the boundaries are measured instead, from the character positions that are blank in every
row of the table, and each measured field is assigned to the ruler segment it overlaps
most. A segment that ends up with two fields keeps both, which is right: the Tely's
"Class Placing" really is two values in one declared column, and `class_placing` parses
the pair. A segment that ends up with none falls back to its dashes.

This also makes the parser safe on a table too short to measure. With one finisher every
space is blank in every row, so the measurement over-splits the name into two fields, and
the union back onto the segment puts it together again.

⚠️ **A header word is assigned to a column, never sliced by it**, for the same reason.
The header is centred over its dashes and routinely starts before them: on the Tely,
"Gender" begins one character to the left of its own segment, so slicing leaves a "G" on
the end of the previous column and an "ender" at the front of its own.

⚠️ **A page ends with a second ruler under the last row**, which is a rule drawn across
the foot of the table and not the head of another one. A ruler counts as a table only
when the lines above it are a header rather than results; otherwise the last two runners
on the page become its column names, which is how this was found.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from itertools import pairwise

# A ruler is dashes and spaces only, with at least two runs of three or more dashes.
_RULER = re.compile(r"^[- ]*$")
_RUN = re.compile(r"-{3,}")

# How far above the ruler a header may start. The Tely's runs to two lines; nothing
# observed runs to three, and the limit stops a stray title line joining the header.
MAX_HEADER_LINES = 2

# What a tab is worth inside a <pre>. The browser default, which is what the page was
# laid out against.
TAB_STOP = 8

# The trailing "(ANER)" on a name is the runner's club. Clubs are short and upper case
# (ANER, PRCA, SRNL, PGNL); anything longer or mixed-case is left in the name, because a
# parenthetical is not always a club and a name is not ours to edit.
_CLUB = re.compile(r"^(?P<name>.*?)\s*\((?P<club>[A-Z0-9]{2,6})\)\s*$")

# "M(1)" in the general layout's F/M column: sex, and place within it.
_SEX_PLACE = re.compile(r"^(?P<sex>[MFX])\s*\((?P<place>\d+)\)$")

# "LM30-34" in the 2022 Tely's class column: an entry-type letter, then sex and band.
_CLASS_CODE = re.compile(
    r"^[A-Z]*?(?P<sex>[MF])(?P<band>\d{1,2}-\d{1,3}|U\d{1,2}|\d{1,2}\+)$"
)

# "1/106" in the same layout: place within the class, and how many were in it.
_PLACE_OF = re.compile(r"^(?P<place>\d+)\s*/\s*(?P<field>\d+)$")

# "M25-29     1" in the Tely's class placing column: sex, age band, place within it.
_CLASS_PLACING = re.compile(
    r"^(?P<sex>[MFX])(?P<band>\d{1,2}-\d{1,3}|U\d{1,2}|\d{1,2}\+)\s+(?P<place>\d+)$"
)

# What this parser will answer to, by header text once flattened (lower case, runs of
# non-alphanumerics collapsed to one space). Extend this deliberately, with a fixture.
CANONICAL: dict[str, str] = {
    "pos": "place",
    "place": "place",
    "o all place": "place",
    "bib": "bib",
    "name": "name",
    "time": "gun_seconds",
    "gun time": "gun_seconds",
    "chip time": "chip_seconds",
    "f m": "sex_and_place",
    "age": "age_band",
    "cat": "category_place",
    "class placing": "class_placing",
    "class": "class_code",
    "place finishers": "category_place",
    "net time": "chip_seconds",
    "gender place": "sex_place",
    "pace mi": "pace_per_mile",
    "hometown": "hometown",
    "city": "hometown",
}


class ParseError(Exception):
    """A results page this parser will not guess at."""


class UnknownColumns(ParseError):
    """A header this parser does not recognise, named so the map can be extended."""

    def __init__(self, headers: tuple[str, ...]) -> None:
        self.headers = headers
        super().__init__(
            "unrecognised column headers "
            + ", ".join(repr(h) for h in headers)
            + ". Add them to parse.CANONICAL with a fixture that pins the layout, rather "
            "than letting the rows land in the wrong fields."
        )


@dataclass(frozen=True, slots=True)
class Column:
    """One column of a results table, and where it sits on every line."""

    field: str
    header: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Table:
    """One results table: the columns it declared and the rows under them, as text."""

    columns: tuple[Column, ...]
    rows: tuple[dict[str, str], ...]

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(column.field for column in self.columns)


def pre_blocks(page: str) -> list[str]:
    """The text of every `<pre>` element on the page, entities resolved.

    Tags inside a `<pre>` are stripped rather than rendered: some pages bold the winner's
    row, and a `<b>` in the middle of a line would shift every column after it.
    """
    blocks: list[str] = []
    for match in re.finditer(r"<pre[^>]*>(.*?)</pre>", page, re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", "", match.group(1))
        # ⚠️ A tab is eight columns wide to a browser and one character to str.index.
        # One 2022 page has a stray tab in the middle of a row, which slid every column
        # after it and lost the race. Expanding at the same stops the browser uses puts
        # the characters back where the page showed them.
        blocks.append(html.unescape(text).expandtabs(TAB_STOP))
    return blocks


def is_ruler(line: str) -> bool:
    """Whether this line is the row of dashes that declares the column boundaries."""
    return bool(line.strip()) and bool(_RULER.match(line)) and len(_RUN.findall(line)) >= 2


def segments(ruler: str) -> tuple[tuple[int, int], ...]:
    """The (start, end) of each run of dashes, in characters."""
    return tuple((m.start(), m.end()) for m in _RUN.finditer(ruler))


def _cells(line: str, spans: tuple[tuple[int, int], ...]) -> list[str]:
    """Slice a line by column span. A span past the end of a short line gives ''."""
    return [line[start:end].strip() for start, end in spans]


def data_fields(rows: list[str]) -> tuple[tuple[int, int], ...]:
    """Where the values actually sit, from the positions blank in every row.

    The complement of the all-blank positions is the set of fields. See the module note:
    this is measurement, and the ruler is only a claim.
    """
    if not rows:
        return ()
    width = max(len(row) for row in rows)
    filled = [
        column
        for column in range(width)
        if any(len(row) > column and row[column] != " " for row in rows)
    ]
    fields: list[tuple[int, int]] = []
    for column in filled:
        if fields and column == fields[-1][1]:
            fields[-1] = (fields[-1][0], column + 1)
        else:
            fields.append((column, column + 1))
    return tuple(fields)


def column_spans(
    bounds: tuple[tuple[int, int], ...], fields: tuple[tuple[int, int], ...]
) -> tuple[tuple[int, int], ...]:
    """One span per ruler segment, covering the measured fields that belong to it.

    Each measured field goes to the segment it overlaps most, or the nearest by centre
    when it overlaps none. A segment's span runs from the first to the last of its
    fields; a segment that drew no fields keeps its own dashes. The last span is opened
    to the end of the line so a hometown wider than everything measured stays whole.
    """
    owned: list[list[tuple[int, int]]] = [[] for _ in bounds]
    for start, end in fields:
        overlaps = [max(0, min(end, hi) - max(start, lo)) for lo, hi in bounds]
        best = max(range(len(bounds)), key=overlaps.__getitem__)
        if overlaps[best] == 0:
            centre = (start + end) / 2
            best = min(range(len(bounds)), key=lambda i: abs((sum(bounds[i]) / 2) - centre))
        owned[best].append((start, end))

    spans = [
        (mine[0][0], mine[-1][1]) if (mine := owned[index]) else bounds[index]
        for index in range(len(bounds))
    ]
    if spans:
        spans[-1] = (spans[-1][0], 10_000)
    return tuple(spans)


def _assign_spans(
    line: str, bounds: tuple[tuple[int, int], ...]
) -> list[list[tuple[str, int, int]]]:
    """Put each word of a header line in the column it overlaps most, keeping its span.

    A word that overlaps nothing (the header sits entirely in a gap) goes to the nearest
    column by centre distance, which is what a reader does with it.
    """
    buckets: list[list[tuple[str, int, int]]] = [[] for _ in bounds]
    for match in re.finditer(r"\S+", line):
        start, end = match.start(), match.end()
        overlaps = [max(0, min(end, hi) - max(start, lo)) for lo, hi in bounds]
        best = max(range(len(bounds)), key=overlaps.__getitem__)
        if overlaps[best] == 0:
            centre = (start + end) / 2
            best = min(range(len(bounds)), key=lambda i: abs((sum(bounds[i]) / 2) - centre))
        buckets[best].append((match.group(), start, end))
    return buckets


def _assign_words(line: str, bounds: tuple[tuple[int, int], ...]) -> list[list[str]]:
    """The words of a header line, bucketed by column."""
    return [[word for word, _start, _end in bucket] for bucket in _assign_spans(line, bounds)]


def _split_merged(
    fields: tuple[tuple[int, int], ...],
    buckets: list[list[tuple[str, int, int]]],
    rows: list[str],
) -> tuple[tuple[int, int], ...]:
    """Split a measured field that the header says is really two columns.

    ⚠️ **A measured boundary needs one blank column in every row, and the archive does
    not always provide one.** On thirty of these pages a single long name reaches into
    the time column, so name and time measure as one field and their two header words
    land together. Read that way the whole page is refused, which is the right refusal
    and the wrong outcome: the page is perfectly readable and the header says exactly
    where the seam is.

    So where a field collects more than one header word, it is cut between them, at the
    column carrying the fewest characters across the rows. The header says how many
    columns there are; the data says where the join is thinnest. A name clipped by one
    character in the single row that caused it is the cost, and it beats losing the race.
    """
    out: list[tuple[int, int]] = []
    for (low, high), bucket in zip(fields, buckets, strict=True):
        if len(bucket) < 2:
            out.append((low, high))
            continue
        edges = [low]
        for left, right in pairwise(bucket):
            start = max(low + 1, min(left[2], high - 1))
            stop = max(start + 1, min(right[1] + 1, high))
            edges.append(min(range(start, stop), key=lambda c: _filled(rows, c)))
        edges.append(high)
        out.extend(pairwise(edges))
    return tuple(out)


def _header_groups(lines: list[str], header: list[int]) -> list[tuple[int, int]]:
    """The header's words merged into one span per column, across all its header lines.

    Two words belong to the same column when they actually overlap, which is what a word
    stacked above another one does: "Net" over "Time" is one column. Merely touching is
    not enough, and the difference decides the count: on the 2022 Tely, "Finishers" ends
    one character before "Gender" begins, and treating that as one column made eight
    columns out of nine and lost the page.
    """
    spans: list[tuple[int, int]] = []
    for index in header:
        spans += [(m.start(), m.end()) for m in re.finditer(r"\S+", lines[index])]
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _headers_in_order(
    lines: list[str], header: list[int], count: int
) -> list[str] | None:
    """The header cells read left to right, when the header agrees on how many there are.

    ⚠️ **Some pages print their header several characters left of the data under it**,
    far enough that matching a word to the column it overlaps puts every name one column
    out. The 2022 Tely does exactly this: "Class" lands over the gun time and "City"
    lands over the chip time, and the result is a page read with every column mislabelled
    and nothing raised.

    Counting is the check that catches it. Where the header's own columns come to the
    same number as the columns measured in the rows, the two agree about the shape of the
    table and reading them off in order is safe. Where they do not, this returns None and
    the overlap rule takes over, because a count that does not match is not evidence.
    """
    groups = _header_groups(lines, header)
    if len(groups) != count:
        return None
    return [
        " ".join(
            match.group()
            for index in header
            for match in re.finditer(r"\S+", lines[index])
            if start <= match.start() <= end
        )
        for start, end in groups
    ]


def _merged_spans(
    lines: list[str], header: list[int], fields: tuple[tuple[int, int], ...]
) -> list[list[tuple[str, int, int]]]:
    """Every header line's words, bucketed by column and kept in reading order."""
    buckets: list[list[tuple[str, int, int]]] = [[] for _ in fields]
    for index in header:
        for column, words in enumerate(_assign_spans(lines[index], fields)):
            buckets[column].extend(words)
    return buckets


def _joined_headers(
    lines: list[str], header: list[int], fields: tuple[tuple[int, int], ...]
) -> list[str]:
    """One header string per column, read down the header lines then across."""
    return [
        " ".join(word for word, _start, _end in bucket)
        for bucket in _merged_spans(lines, header, fields)
    ]


def _filled(rows: list[str], column: int) -> int:
    """How many of these rows carry a character at this column."""
    return sum(1 for row in rows if len(row) > column and row[column] != " ")


def flatten_header(text: str) -> str:
    """Header text as CANONICAL keys it: lower case, punctuation to single spaces.

    `#` is spelled out first, because the 2016 and 2017 pages head the bib column with it
    and nothing else. Repeated words are collapsed so that `BIB #` and `#` land on the
    same key rather than on `bib bib` and `bib`.
    """
    spelled = text.lower().replace("#", " bib ")
    words: list[str] = []
    for word in re.sub(r"[^a-z0-9]+", " ", spelled).split():
        if not words or words[-1] != word:
            words.append(word)
    return " ".join(words)


def header_lines(lines: list[str], ruler: int) -> list[int]:
    """The indices of the header lines above this ruler, in reading order.

    Empty when the ruler is a rule drawn under the last row rather than over the first:
    the walk upward stops at a blank line, at another ruler, and at anything that reads
    as a result row. See the module note.
    """
    bounds = segments(lines[ruler])
    first = Column(field="", header="", start=bounds[0][0], end=bounds[0][1])
    found: list[int] = []
    for offset in range(1, MAX_HEADER_LINES + 1):
        index = ruler - offset
        if index < 0 or not lines[index].strip():
            break
        if is_ruler(lines[index]) or _is_data(lines[index], first):
            break
        found.append(index)
    return sorted(found)


def _looks_like_data(line: str) -> bool:
    """Whether a line opens with a finishing place, wherever its column starts.

    Used only where there is no ruler to say where the first column is. Deliberately
    narrow: a place, then whitespace. A title, a date and a note all fail it.
    """
    return bool(re.match(r"\s{0,8}\d{1,5}\s", line))


def _runs_of_data(lines: list[str]) -> list[list[int]]:
    """Contiguous blocks of result rows, tolerating a repeated header inside one.

    A gap of up to three lines keeps a run together, because several pages repeat their
    column header and a blank line every hundred finishers where the printout broke.
    """
    marked = [index for index, line in enumerate(lines) if _looks_like_data(line)]
    runs: list[list[int]] = []
    for index in marked:
        if runs and index - runs[-1][-1] <= 3:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


def _header_above(lines: list[str], first_row: int) -> list[int]:
    """The header lines above this run, in reading order.

    Walks up past a ruler and past blank lines, and stops at the first result row, so it
    works whether or not the page drew a rule and whether the header runs to one line or
    two.
    """
    found: list[int] = []
    for index in range(first_row - 1, max(-1, first_row - 5), -1):
        if not lines[index].strip() or is_ruler(lines[index]):
            continue
        if _looks_like_data(lines[index]):
            break
        found.append(index)
        if len(found) == MAX_HEADER_LINES:
            break
    return sorted(found)


def columns_at(lines: list[str], ruler: int) -> tuple[Column, ...]:
    """The columns declared by the ruler on line `ruler`, named from the lines above it.

    A header cell is every word assigned to that column, from each header line in reading
    order, so the Tely's "Gun" over "Time" resolves to "gun time".
    """
    bounds = segments(lines[ruler])
    per_line = [_assign_words(lines[index], bounds) for index in header_lines(lines, ruler)]
    joined = [
        " ".join(word for line_words in per_line for word in line_words[column])
        for column in range(len(bounds))
    ]

    unknown = tuple(h for h in joined if flatten_header(h) not in CANONICAL)
    if unknown:
        raise UnknownColumns(unknown)

    return tuple(
        Column(field=CANONICAL[flatten_header(header)], header=header, start=start, end=end)
        for header, (start, end) in zip(joined, bounds, strict=True)
    )


def _is_data(line: str, first: Column) -> bool:
    """Whether this line is a result row rather than a heading or a spacer.

    Every layout opens with a numeric place, so a row whose first column does not start
    with a digit is a section title, a note, or the blank line before one. The rule is
    deliberately strict: a row that cannot be placed is a row that will not be published.
    """
    if not line.strip():
        return False
    return line[first.start : first.end + 1].strip()[:1].isdigit()


def parse_tables(page: str) -> list[Table]:
    """Every results table on the page, in the order they appear.

    A table runs from its ruler to the next ruler or the end of the block; non-data lines
    inside it (a repeated header on a page break, a category heading) are skipped rather
    than ending it, because several pages break the field into sections under one ruler.
    """
    tables: list[Table] = []
    for block in pre_blocks(page):
        lines = block.splitlines()
        starts = [
            (ruler, header)
            for ruler in range(len(lines))
            if is_ruler(lines[ruler]) and (header := header_lines(lines, ruler))
        ]
        if not starts:
            tables.extend(_tables_without_a_ruler(lines))
            continue
        try:
            tables.extend(_tables_with_rulers(lines, starts))
        except UnknownColumns as declared:
            # ⚠️ A ruler can be wrong. The 2022 Tely draws one run of dashes across its
            # place, bib and name columns together, so read by the ruler those three
            # collapse into one column called "O'all Place Bib Name". The dashes are not
            # load-bearing: the boundaries are measured from the rows either way, so the
            # page is read again with the header alone deciding the names. If that
            # fails too, the ruler's own complaint is the more useful one to raise.
            try:
                tables.extend(_tables_without_a_ruler(lines))
            except UnknownColumns:
                raise declared from None
    return tables


def _tables_with_rulers(
    lines: list[str], starts: list[tuple[int, list[int]]]
) -> list[Table]:
    """Read the tables a page's rulers declare."""
    tables: list[Table] = []
    for index, (ruler, _header) in enumerate(starts):
        stop = starts[index + 1][1][0] if index + 1 < len(starts) else len(lines)
        columns = columns_at(lines, ruler)
        bounds = tuple((c.start, c.end) for c in columns)
        body = [line for line in lines[ruler + 1 : stop] if _is_data(line, columns[0])]
        spans = column_spans(bounds, data_fields(body))
        rows = tuple(
            dict(zip((c.field for c in columns), _cells(line, spans), strict=True))
            for line in body
        )
        if rows:
            tables.append(Table(columns=columns, rows=rows))
    return tables


def _tables_without_a_ruler(lines: list[str]) -> list[Table]:
    """Read a page that has the columns but not the dashes under them.

    ⚠️ **Two thirds of the archive is this shape and the first version of this parser
    could not read any of it.** Every page from 2016 to mid-2018 prints the header and
    then the rows with no rule between, so a parser that keys on the ruler silently read
    108 of 160 races as empty. Nothing failed; the coverage number was simply wrong.

    It needs no new idea, only the one already here. The boundaries were never really
    coming from the ruler anyway: they are measured from the positions blank in every row
    (see the module note), and that works whether or not anyone drew a line. The ruler
    was only ever naming the columns, and the header line can do that by itself.
    """
    tables: list[Table] = []
    for run in _runs_of_data(lines):
        header = _header_above(lines, run[0])
        if not header:
            continue
        body = [lines[index] for index in run]
        fields = data_fields(body)
        if len(fields) < 3:
            continue
        ordered = _headers_in_order(lines, header, len(fields))
        if ordered is None:
            fields = _split_merged(fields, _merged_spans(lines, header, fields), body)
        joined = ordered or _joined_headers(lines, header, fields)
        unknown = tuple(text for text in joined if flatten_header(text) not in CANONICAL)
        if unknown:
            raise UnknownColumns(unknown)
        columns = tuple(
            Column(field=CANONICAL[flatten_header(text)], header=text, start=lo, end=hi)
            for text, (lo, hi) in zip(joined, fields, strict=True)
        )
        spans = column_spans(fields, fields)
        rows = tuple(
            dict(zip((column.field for column in columns), _cells(line, spans), strict=True))
            for line in body
        )
        if rows:
            tables.append(Table(columns=columns, rows=rows))
    return tables


# ------------------------------------------------------------------ value parsing


def seconds(text: str) -> float | None:
    """A time as seconds. None for a blank, a DNF, or anything that is not a clock.

    Accepts m:ss, h:mm:ss and either with decimals. Returns None rather than a guess for
    "DNF", "DNS", "-" and the handful of other markers the pages carry, because a runner
    who did not finish has no finish time and inventing one would poison the history.
    """
    value = text.strip()
    if not value or not re.fullmatch(r"\d{1,2}(:\d{2}){1,2}(\.\d+)?", value):
        return None
    parts = [float(part) for part in value.split(":")]
    total = 0.0
    for part in parts:
        total = total * 60.0 + part
    return total


def name_and_club(text: str) -> tuple[str, str | None]:
    """Split "Ben Collingwood (ANER)" into the name and the club code."""
    match = _CLUB.match(text.strip())
    if not match:
        return text.strip(), None
    return match.group("name").strip(), match.group("club")


def sex_and_place(text: str) -> tuple[str | None, int | None]:
    """Split the general layout's "M(1)" into sex and place within that sex."""
    match = _SEX_PLACE.match(text.strip())
    if not match:
        return None, None
    return match.group("sex"), int(match.group("place"))


def class_placing(text: str) -> tuple[str | None, str | None, int | None]:
    """Split the Tely's "M25-29     1" into sex, age band and place within the class."""
    match = _CLASS_PLACING.match(" ".join(text.split()))
    if not match:
        return None, None, None
    return match.group("sex"), match.group("band"), int(match.group("place"))


def class_code(text: str) -> tuple[str | None, str | None]:
    """Split the 2022 Tely's "LM30-34" into sex and age band.

    The leading letters are the entry type that year's timing software printed and carry
    nothing this project models, so they are dropped rather than guessed at.
    """
    match = _CLASS_CODE.match(text.strip())
    if not match:
        return None, None
    return match.group("sex"), match.group("band")


def place_of(text: str) -> int | None:
    """The place from a "1/106", which is place within the class out of its size."""
    match = _PLACE_OF.match(" ".join(text.split()))
    return int(match.group("place")) if match else None


def integer(text: str) -> int | None:
    """A whole number, or None. Bibs with letters and blank places land here."""
    value = text.strip()
    return int(value) if value.isdigit() else None
