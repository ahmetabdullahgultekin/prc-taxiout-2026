"""Building and validating the submission file.

The competition's validation rules (dc2026/ranking.html):

- the filename must be ``<team-name>_v<increasing integer>.parquet``
- **every** `MVT_ID_mvt` in the ``submitting.parquet`` template must be matched
- no missing rows, no extra rows

These checks run here, **before** upload. A malformed file costs a submission round and
the wait that goes with it, while checking costs nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

MVT_ID = "MVT_ID_mvt"
TARGET = "TAXITIME_SEC_mvt"

FILENAME_RE = re.compile(r"^[a-z0-9-]+_v\d+\.parquet$")

# ATXOT's official upper filter. Predictions above it are not forbidden, but they are
# almost certainly a mistake, so they should not pass unremarked.
SANITY_MAX_SEC = 120 * 60


class SubmissionError(ValueError):
    """One of the submission validity rules was not met."""


def validate(pred: pl.DataFrame, template: pl.DataFrame) -> list[str]:
    """Enforce the hard rules, raising on violation. Returns warnings as a list."""
    missing = {MVT_ID, TARGET} - set(pred.columns)
    if missing:
        raise SubmissionError(f"prediction table is missing columns: {sorted(missing)}")

    if pred.height != template.height:
        raise SubmissionError(
            f"row count mismatch: prediction {pred.height:,}, template {template.height:,}"
        )

    dup = pred.height - pred[MVT_ID].n_unique()
    if dup:
        raise SubmissionError(f"{dup:,} duplicate {MVT_ID} values")

    pred_ids = set(pred[MVT_ID].to_list())
    tmpl_ids = set(template[MVT_ID].to_list())
    if absent := tmpl_ids - pred_ids:
        raise SubmissionError(
            f"{len(absent):,} template rows are not in the prediction, e.g. {list(absent)[:5]}"
        )
    if extra := pred_ids - tmpl_ids:
        raise SubmissionError(f"{len(extra):,} extra rows, e.g. {list(extra)[:5]}")

    target = pred[TARGET]
    if n := target.is_null().sum():
        raise SubmissionError(f"{n:,} null predictions")
    if n := target.is_nan().sum():
        raise SubmissionError(f"{n:,} NaN predictions")
    if n := target.is_infinite().sum():
        raise SubmissionError(f"{n:,} infinite predictions")
    if n := (target < 0).sum():
        raise SubmissionError(f"{n:,} negative predictions; a taxi time cannot be negative")

    warnings: list[str] = []
    if n := (target > SANITY_MAX_SEC).sum():
        warnings.append(f"{n:,} predictions exceed 120 minutes (ATXOT upper filter)")
    if n := (target < 60).sum():
        warnings.append(f"{n:,} predictions below 60 seconds, physically doubtful")
    mean = target.mean()
    if mean is not None and not 300 <= mean <= 1800:
        warnings.append(
            f"mean prediction {mean:,.0f} s, outside the expected 5 to 30 minute range"
        )
    return warnings


def write(pred: pl.DataFrame, template: pl.DataFrame, out_path: Path) -> list[str]:
    """Validate, preserve the template row order, and write the parquet file."""
    if not FILENAME_RE.match(out_path.name):
        raise SubmissionError(
            f"filename does not follow the convention: {out_path.name} "
            "(expected '<team-name>_v<N>.parquet', e.g. 'keen-hamburger_v1.parquet')"
        )
    warnings = validate(pred, template)
    ordered = template.select(MVT_ID).join(
        pred.select(MVT_ID, TARGET), on=MVT_ID, how="left"
    )
    # Should be impossible after validate; guards against a silent corruption.
    if ordered[TARGET].is_null().any():
        raise SubmissionError("nulls appeared after the join")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.write_parquet(out_path)
    return warnings


def next_version(directory: Path, team: str) -> int:
    """One past the highest version present. Submissions must use increasing integers."""
    pattern = re.compile(rf"^{re.escape(team)}_v(\d+)\.parquet$")
    versions = [
        int(m.group(1))
        for f in directory.glob("*.parquet")
        if (m := pattern.match(f.name))
    ]
    return max(versions, default=0) + 1
