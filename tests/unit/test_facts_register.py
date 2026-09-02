"""Structural checks on the verified-facts register.

`docs/facts.md` exists so that any claim in this project can be traced to a source and a
date. That only works if a reference resolves to one row, and twice now a batch of new
rows has been filed under identifiers already in use: M10 to M12 collided with the domain
knowledge table, then Q01 to Q04 with the open questions. Both times the register still
read perfectly well and the collision was invisible until someone went looking.

Twice is a pattern, so it gets a check rather than more care.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

FACTS = Path(__file__).resolve().parents[2] / "docs" / "facts.md"
ROW = re.compile(r"^\|\s*([A-Z]{1,3}\d{2})\s*\|")
HEADING = re.compile(r"^##\s+(.*)$")


def _rows() -> list[tuple[str, str]]:
    """(identifier, the heading it sits under) for every row in the register."""
    out, heading = [], "(no heading)"
    for line in FACTS.read_text(encoding="utf-8").split("\n"):
        if m := HEADING.match(line):
            heading = m.group(1)
        elif m := ROW.match(line):
            out.append((m.group(1), heading))
    return out


def test_every_identifier_appears_once() -> None:
    counts = Counter(ident for ident, _ in _rows())
    repeated = {i: n for i, n in counts.items() if n > 1}
    assert not repeated, (
        f"identifiers used more than once: {repeated}. A reference to one of these "
        "resolves to two different facts."
    )


def test_a_prefix_belongs_to_one_table() -> None:
    """F01 and F02 under different headings means a row is filed in the wrong table.

    That happened too: three rows about external data sources sat in the scale and
    performance table, and three about previous editions in the board results table.
    """
    homes: dict[str, set[str]] = {}
    for ident, heading in _rows():
        prefix = re.match(r"^([A-Z]{1,3})", ident).group(1)
        homes.setdefault(prefix, set()).add(heading)
    scattered = {p: sorted(h) for p, h in homes.items() if len(h) > 1}
    assert not scattered, f"prefixes spread across several tables: {scattered}"


def test_every_row_cites_a_source_and_a_date() -> None:
    """The register's one rule: a claim without a source is not a fact.

    Applied only to tables that promise a source. The open questions table has a
    different shape on purpose, since an open question has no source yet, and the header
    row is what tells the two apart rather than the heading text.
    """
    missing, checked = [], False
    for line in FACTS.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| # |"):
            checked = "Source" in line and "Checked" in line
            continue
        if not checked or not ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[2] or not re.search(r"\d{4}-\d{2}-\d{2}", cells[3]):
            missing.append(cells[0] if cells else line[:40])
    assert not missing, f"rows without a source or a dated check: {missing}"


def test_the_register_is_actually_being_read() -> None:
    """Negative control: if the row pattern matched nothing the tests above pass empty."""
    rows = _rows()
    assert len(rows) > 60, f"only {len(rows)} rows parsed out of the register"
