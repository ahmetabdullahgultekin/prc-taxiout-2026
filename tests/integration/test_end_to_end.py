"""End to end: from synthetic data to a valid submission file.

This test does not check that the individual modules are correct, it checks that **the
chain does not break**. The unit tests verify each part on its own; the risk here is
different: a column gets renamed, a join silently drops rows, and the submission is
rejected. In the competition that costs a submission round.

The fixture is kept small; the point is not speed but that the pipes really do carry
through from one end to the other.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from taxiout.application import pipeline, submission
from taxiout.domain import reference

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Produces a small synthetic data set (12 months of training + ranking + template)."""
    out = tmp_path_factory.mktemp("data") / "00_raw"
    subprocess.run(  # noqa: S603
        [sys.executable, str(REPO / "tests" / "make_fixture.py"),
         "--out", str(out), "--per-day", "40"],
        check=True, cwd=REPO,
    )
    return out


def test_fixture_reproduces_the_ranking_set_shape(raw_dir: Path) -> None:
    """The fixture must imitate the real setup, or the test verifies the wrong thing."""
    rank = pl.read_parquet(raw_dir / "ranking.parquet")
    dep = rank.filter(pl.col("PHASE_mvt") == "DEP")
    arr = rank.filter(pl.col("PHASE_mvt") == "ARR")
    assert dep["BLOCK_TIME_UTC_mvt"].null_count() == dep.height, "DEP block time must be empty"
    assert dep["TAXITIME_SEC_mvt"].null_count() == dep.height, "DEP taxi time must be empty"
    assert arr["TAXITIME_SEC_mvt"].null_count() == 0, "ARR taxi time must be filled"
    assert dep["MVT_TIME_UTC_mvt"].null_count() == 0, "DEP take-off time must be filled"


def test_features_are_producible_on_the_ranking_set(raw_dir: Path) -> None:
    """Every feature produced in training must also be producible on the ranking set.

    A feature that cannot be produced is information the model learns in training and
    loses at prediction time; if that happens silently it hurts the RMSE and the cause
    stays invisible.

    The external data must be handed to **both** sides in the same way. The first version
    of this test did not do that and missed a real bug: `make_submission.py` was not
    passing the daily ATFM table to the ranking side, and 11 features were dropped
    silently.
    """
    inputs = pipeline.load_inputs(raw_dir)
    fit = pipeline.build_features(inputs)
    rank_inputs = replace(inputs, movements=pipeline.prepare_movements(
        pl.read_parquet(raw_dir / "ranking.parquet")))
    rank = pipeline.build_features(rank_inputs)

    missing = set(pipeline.feature_columns(fit)) - set(rank.columns)
    assert missing == set(), f"features not producible on the ranking set: {sorted(missing)}"


def test_holdout_mirrors_the_ranking_set_shape(raw_dir: Path) -> None:
    """The validation split must carry the shape of the ranking set.

    The ranking set is not symmetric: 10 airports in January, only three in July
    (docs/facts.md R03). If the validation does not imitate that, we treat July as more
    important than it is and pick the wrong model. July's other airports are deliberately
    left in training.
    """
    inputs = pipeline.load_inputs(raw_dir)
    split = pipeline.seasonal_split(pipeline.build_features(inputs), inputs.movements)

    month_num = pl.col("MVT_TIME_UTC_mvt").dt.month()
    assert set(split.val.select(month_num.unique()).to_series().to_list()) == {1, 7}

    july_apt = set(
        split.val.filter(month_num == 7)[pipeline.APT].unique().to_list()
    )
    january_apt = set(split.val.filter(month_num == 1)[pipeline.APT].unique().to_list())
    assert july_apt <= set(pipeline.JULY_AIRPORTS), f"extra airports in July: {july_apt}"
    assert len(january_apt) > len(july_apt), "January must be the wider month"

    # the rows must not overlap
    shared = set(split.fit["MVT_ID_mvt"].to_list()) & set(split.val["MVT_ID_mvt"].to_list())
    assert shared == set(), "the same movement cannot be in training and in validation"

    # July airports that are not in validation must stay in training
    july_in_fit = set(split.fit.filter(month_num == 7)[pipeline.APT].unique().to_list())
    assert july_in_fit, "the other July airports must be in training"
    assert not (july_in_fit & july_apt)


def test_reference_is_fitted_without_the_validation_months(raw_dir: Path) -> None:
    """Leakage check: the reference must not see the validation months.

    If it did, the OOF numbers would improve dishonestly and the board would not give
    that back.
    """
    inputs = pipeline.load_inputs(raw_dir)
    month_num = pl.col("MVT_TIME_UTC_mvt").dt.month()
    holdout_only = inputs.movements.filter(month_num.is_in(pipeline.HOLDOUT_MONTHS))
    rest = inputs.movements.filter(~month_num.is_in(pipeline.HOLDOUT_MONTHS))

    t_rest = reference.fit_reference(rest)["apt"]
    t_all = reference.fit_reference(inputs.movements)["apt"]
    assert holdout_only.height > 0
    # taking the months out must lower the sample count: the table really is built from
    # different data
    assert t_rest["n_apt"].sum() < t_all["n_apt"].sum()


def test_full_run_produces_a_valid_submission(raw_dir: Path, tmp_path: Path) -> None:
    inputs = pipeline.load_inputs(raw_dir)
    tables = reference.fit_reference(inputs.movements)
    fit = reference.apply_reference(
        pipeline.build_features(inputs).filter(pl.col(pipeline.TARGET).is_not_null()), tables
    )
    rank_inputs = replace(inputs, movements=pipeline.prepare_movements(
        pl.read_parquet(raw_dir / "ranking.parquet")))
    rank = reference.apply_reference(pipeline.build_features(rank_inputs), tables)

    cols = [c for c in pipeline.feature_columns(fit) if c in rank.columns]
    split = pipeline.Split(fit=fit, val=rank, columns=cols)
    pred = pipeline.train_predict(split, cols, rounds=30)

    assert np.isfinite(pred).all(), "predictions must hold no NaN or infinity"
    assert (pred >= 0).all(), "a negative taxi time is physically impossible"

    template = pl.read_parquet(raw_dir / "submitting.parquet")
    pred_df = rank.select("MVT_ID_mvt").with_columns(
        pl.Series(pipeline.TARGET, pred.astype(np.float64))
    ).join(template.select("MVT_ID_mvt"), on="MVT_ID_mvt", how="semi")

    out = tmp_path / "keen-hamburger_v1.parquet"
    submission.write(pred_df, template, out)

    written = pl.read_parquet(out)
    assert written.columns == ["MVT_ID_mvt", pipeline.TARGET]
    assert written["MVT_ID_mvt"].to_list() == template["MVT_ID_mvt"].to_list()
    assert written[pipeline.TARGET].null_count() == 0


def test_causal_run_also_completes(raw_dir: Path) -> None:
    """The causal variant is needed for the paper; do not let it break unnoticed."""
    inputs = pipeline.load_inputs(raw_dir)
    feats = pipeline.build_features(inputs, causal=True)
    split = pipeline.seasonal_split(feats, inputs.movements)
    pred = pipeline.train_predict(split, split.columns, rounds=30)
    scores = pipeline.evaluate(split, pred)
    assert scores["total"] > 0
    assert not [c for c in split.columns if "_next_" in c]


def test_submission_script_drops_no_features(raw_dir: Path, tmp_path: Path) -> None:
    """Actually runs the production script and verifies that no feature is dropped.

    This test exists for a concrete reason: `make_submission.py` was constructing `Inputs`
    with positional arguments, and when the daily ATFM field was added to `Inputs` the
    ranking side silently ended up without it and 11 features were dropped. Testing the
    pipeline functions does not catch that, because the bug was in the script's own setup.
    That is why the script is run as a subprocess.
    """
    data_dir = tmp_path / "data"
    (data_dir / "00_raw").mkdir(parents=True)
    for f in raw_dir.iterdir():
        (data_dir / "00_raw" / f.name).write_bytes(f.read_bytes())

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(REPO / "scripts" / "make_submission.py"),
         "--data-dir", str(data_dir), "--team", "keen-hamburger",
         "--rounds", "20", "--seeds", "1"],
        check=True, cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert "features that cannot be produced on the ranking set" not in result.stdout, (
        "features are being dropped on the submission path:\n" + result.stdout
    )
    written = list((data_dir / "04_submissions").glob("keen-hamburger_v*.parquet"))
    assert len(written) == 1, f"expected exactly one submission file, found: {written}"
    template = pl.read_parquet(raw_dir / "submitting.parquet")
    assert pl.read_parquet(written[0]).height == template.height
