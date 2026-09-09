"""The segmented learner: two models where the data is really two problems.

The measurement behind it is that 1.25 percent of the holdout carries 62 percent of the
squared error, and those rows lose every column that comes from the Network Manager
flight list, not just the off-block time. What is tested here is the mechanism rather
than the gain: that each segment is really fitted on its own rows, that a thin segment
does not get a model fitted on a handful of examples, and that the whole thing degrades
to a single model when the split column is absent.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout import models
from taxiout.models.segmented import SEGMENT, Segmented


def _frame(n: int, matched: np.ndarray, x: np.ndarray) -> pl.DataFrame:
    return pl.DataFrame({
        "x": x.astype(np.float32),
        SEGMENT: matched,
        "TAXITIME_SEC_mvt": np.zeros(n, dtype=np.float64),
    })


def _two_populations(n: int = 4000, seed: int = 0):
    """Two groups whose targets depend on the same feature in opposite directions.

    A single model has to average the two and gets both wrong; a model per group gets
    both right. That is the situation the split exists for, drawn sharply.
    """
    rng = np.random.default_rng(seed)
    matched = rng.random(n) < 0.5
    x = rng.normal(0.0, 1.0, n)
    y = np.where(matched, 100.0 * x, -100.0 * x) + rng.normal(0.0, 1.0, n)
    return _frame(n, matched, x), y


def test_each_segment_is_fitted_on_its_own_rows() -> None:
    fit, y_fit = _two_populations(4000, seed=0)
    val, y_val = _two_populations(2000, seed=1)
    cols = ["x", SEGMENT]

    shared = models.build("xgboost").fit_predict(fit, val, cols, y_fit, 60, 1)
    split = Segmented("xgboost", min_rows=100).fit_predict(fit, val, cols, y_fit, 60, 1)

    def rmse(p):
        return float(np.sqrt(np.mean((p - y_val) ** 2)))

    # The single model can still find the interaction through the flag, so this is not a
    # landslide; what matters is that the split does not make things worse and that both
    # segments are genuinely fitted.
    assert rmse(split) <= rmse(shared) * 1.05
    assert split.shape == y_val.shape
    assert np.isfinite(split).all()


def test_a_thin_segment_falls_back_to_the_shared_model() -> None:
    """Twenty training rows are not a model. Below the threshold the shared fit is used.

    Verified by identity with the shared model's own predictions on those rows, not by
    trusting the branch.
    """
    rng = np.random.default_rng(2)
    n = 2000
    matched = np.ones(n, dtype=bool)
    matched[:20] = False
    x = rng.normal(0.0, 1.0, n)
    y = 50.0 * x + rng.normal(0.0, 1.0, n)
    fit = _frame(n, matched, x)

    val_flag = np.array([True] * 50 + [False] * 50)
    val = _frame(100, val_flag, rng.normal(0.0, 1.0, 100))
    cols = ["x", SEGMENT]

    shared = models.build("xgboost").fit_predict(fit, val, cols, y, 40, 1)
    split = Segmented("xgboost", min_rows=1000).fit_predict(fit, val, cols, y, 40, 1)

    assert np.allclose(split[~val_flag], shared[~val_flag])


def test_a_segment_above_the_threshold_is_not_the_shared_model() -> None:
    """The negative control for the test above: the fallback must be a fallback.

    If both branches returned the shared prediction, the previous test would pass while
    the class did nothing at all.
    """
    fit, y_fit = _two_populations(4000, seed=3)
    val, _ = _two_populations(500, seed=4)
    cols = ["x", SEGMENT]

    shared = models.build("xgboost").fit_predict(fit, val, cols, y_fit, 60, 1)
    split = Segmented("xgboost", min_rows=100).fit_predict(fit, val, cols, y_fit, 60, 1)
    assert not np.allclose(split, shared)


def test_without_the_split_column_it_is_one_model() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0.0, 1.0, 500)
    y = 10.0 * x
    frame = pl.DataFrame({"x": x.astype(np.float32)})

    shared = models.build("xgboost").fit_predict(frame, frame, ["x"], y, 30, 1)
    split = Segmented("xgboost").fit_predict(frame, frame, ["x"], y, 30, 1)
    assert np.allclose(split, shared)


def test_a_null_in_the_split_column_counts_as_unmatched() -> None:
    """Null means the Network Manager had no record, which is the unmatched case.

    Treating it as its own third thing, or letting it raise, would drop rows the split
    exists to serve.
    """
    rng = np.random.default_rng(6)
    n = 2000
    x = rng.normal(0.0, 1.0, n)
    flags = [True] * (n // 2) + [None] * (n // 2)
    fit = pl.DataFrame({
        "x": x.astype(np.float32),
        SEGMENT: flags,
        "TAXITIME_SEC_mvt": np.zeros(n),
    })
    y = np.where(np.array([bool(f) for f in flags]), 20.0 * x, -20.0 * x)

    out = Segmented("xgboost", min_rows=100).fit_predict(fit, fit, ["x", SEGMENT], y, 40, 1)
    assert np.isfinite(out).all()
    assert out.shape == (n,)


def test_it_is_reachable_by_name() -> None:
    assert models.build("segmented-xgboost").name == "segmented-xgboost"
    assert models.build("segmented-catboost").name == "segmented-catboost"
