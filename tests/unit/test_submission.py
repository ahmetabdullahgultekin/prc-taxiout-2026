"""Tests for the submission validator.

Every test here stands for a mistake that could really be made and that would waste a
submission round.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from taxiout.application import submission
from taxiout.application.submission import SubmissionError


def _template(n: int = 50) -> pl.DataFrame:
    return pl.DataFrame({"MVT_ID_mvt": list(range(n)), "TAXITIME_SEC_mvt": [None] * n})


def _pred(n: int = 50, value: float = 700.0) -> pl.DataFrame:
    return pl.DataFrame({"MVT_ID_mvt": list(range(n)), "TAXITIME_SEC_mvt": [value] * n})


def test_valid_submission_passes_without_warnings() -> None:
    assert submission.validate(_pred(), _template()) == []


def test_missing_rows_are_rejected() -> None:
    with pytest.raises(SubmissionError, match="row count mismatch"):
        submission.validate(_pred(49), _template(50))


def test_extra_rows_are_rejected() -> None:
    pred = pl.DataFrame({"MVT_ID_mvt": list(range(1, 51)), "TAXITIME_SEC_mvt": [700.0] * 50})
    with pytest.raises(SubmissionError, match="not in the prediction"):
        submission.validate(pred, _template(50))


def test_duplicate_ids_are_rejected() -> None:
    pred = pl.DataFrame({"MVT_ID_mvt": [1] * 50, "TAXITIME_SEC_mvt": [700.0] * 50})
    with pytest.raises(SubmissionError, match="duplicate"):
        submission.validate(pred, _template(50))


def test_nulls_are_rejected() -> None:
    pred = _pred().with_columns(
        pl.when(pl.col("MVT_ID_mvt") == 3).then(None).otherwise(pl.col("TAXITIME_SEC_mvt"))
        .alias("TAXITIME_SEC_mvt")
    )
    with pytest.raises(SubmissionError, match="null predictions"):
        submission.validate(pred, _template())


def test_negative_predictions_are_rejected() -> None:
    with pytest.raises(SubmissionError, match="negative predictions"):
        submission.validate(_pred(value=-1.0), _template())


def test_nan_predictions_are_rejected() -> None:
    with pytest.raises(SubmissionError, match="NaN"):
        submission.validate(_pred(value=float("nan")), _template())


def test_implausible_mean_warns_but_does_not_block() -> None:
    """Not a hard rule: do not block, but do not pass it over in silence either."""
    warnings = submission.validate(_pred(value=50.0), _template())
    assert any("below 60 seconds" in w for w in warnings)


def test_filename_convention_is_enforced(tmp_path: Path) -> None:
    with pytest.raises(SubmissionError, match="filename does not follow"):
        submission.write(_pred(), _template(), tmp_path / "submission.parquet")
    submission.write(_pred(), _template(), tmp_path / "keen-hamburger_v1.parquet")


def test_written_file_preserves_template_row_order(tmp_path: Path) -> None:
    template = _template(20)
    shuffled = _pred(20).sample(fraction=1.0, shuffle=True, seed=1)
    out = tmp_path / "keen-hamburger_v3.parquet"
    submission.write(shuffled, template, out)
    written = pl.read_parquet(out)
    assert written["MVT_ID_mvt"].to_list() == template["MVT_ID_mvt"].to_list()


def test_next_version_increments(tmp_path: Path) -> None:
    assert submission.next_version(tmp_path, "keen-hamburger") == 1
    for v in (1, 2, 7):
        (tmp_path / f"keen-hamburger_v{v}.parquet").touch()
    assert submission.next_version(tmp_path, "keen-hamburger") == 8
    # another team's files do not count
    (tmp_path / "other-team_v99.parquet").touch()
    assert submission.next_version(tmp_path, "keen-hamburger") == 8
