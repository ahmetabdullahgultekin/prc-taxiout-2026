"""Raw column names must be spelled out in one place and nowhere else.

Tidying the literals away once is worth little: the next feature that needs
`AOBT_3_flt` will paste the string in again unless something objects. This objects.

The names are unusually easy to confuse. `ADEP_mvt` and `ADEP_flt` differ by three
characters and mean different things; `AOBT_3_flt` sits beside `ARVT_3_flt`;
`MVT_TIME_UTC_mvt` beside `BLOCK_TIME_UTC_mvt`. This project has already grouped every
arrival-derived feature on the wrong airport by reaching for `ADEP_mvt`, and the cost
was weeks of features that looked right and were not.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "taxiout"
SCHEMA = SRC / "domain" / "schema.py"

# The competition's own naming convention: every raw column ends in _mvt or _flt.
RAW_NAME = re.compile(r'"([A-Za-z][A-Za-z0-9_]*_(?:mvt|flt))"')

# Columns this project derives rather than reads. They are not schema's business.
DERIVED = {"apt_mvt"}


def _offenders() -> dict[Path, set[str]]:
    found: dict[Path, set[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        if path == SCHEMA:
            continue
        names = {
            m.group(1) for m in RAW_NAME.finditer(path.read_text(encoding="utf-8"))
        } - DERIVED
        if names:
            found[path] = names
    return found


def test_no_module_outside_schema_spells_a_raw_column_name() -> None:
    offenders = _offenders()
    assert not offenders, "\n".join(
        f"{p.relative_to(SRC.parent.parent)}: {sorted(names)}"
        for p, names in offenders.items()
    ) + "\n\nUse taxiout.domain.schema.Col instead; add the column there if it is missing."


def test_schema_itself_defines_the_names() -> None:
    """Negative control: if the pattern matched nothing, the test above is vacuous."""
    names = {m.group(1) for m in RAW_NAME.finditer(SCHEMA.read_text(encoding="utf-8"))}
    assert len(names) > 15, f"only {len(names)} column names found in schema.py"
    assert {"TAXITIME_SEC_mvt", "AOBT_3_flt", "ADEP_mvt"} <= names
