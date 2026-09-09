"""Two identities under one softmax, and the reason it is one softmax and not two.

The interesting failure this class exists to avoid is not statistical. Two independent
probabilities can both say 0.8, and a prediction that puts 0.8 on one candidate and 0.8
on another lands 0.6 of the way outside the range of anything it was built from. A
softmax cannot do that, and the last test here is the one that would catch it if the
implementation drifted back.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout import models
from taxiout.models.identities import Identities

TARGET = "TAXITIME_SEC_mvt"
SCHED = "sched_offset_sec"
NM = "nm_naive_taxi_sec"
COLS = ["x", "kind", SCHED, NM]


def _population(n: int, seed: int):
    """Three kinds of row: one per identity and one that follows neither.

    `kind` is what makes them separable; without a marker the classifier has nothing and
    the class should degrade to its inner learner rather than do harm.
    """
    rng = np.random.default_rng(seed)
    kind = rng.integers(0, 3, n)
    x = rng.normal(0.0, 1.0, n).astype(np.float32)
    sched = np.exp(rng.uniform(np.log(300.0), np.log(86_400.0), n))
    nm = rng.uniform(400.0, 2_500.0, n)
    ordinary = 900.0 + 200.0 * x
    y = np.where(kind == 1, sched, np.where(kind == 2, nm, ordinary))
    frame = pl.DataFrame({
        "x": x, "kind": kind.astype(np.float32),
        SCHED: sched, NM: nm, TARGET: y,
    })
    return frame, y.astype(np.float64)


def _rmse(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.sqrt(np.mean((p - y) ** 2)))


def test_it_beats_a_tree_that_has_the_same_columns() -> None:
    fit, y_fit = _population(9000, seed=0)
    val, y_val = _population(3000, seed=1)
    tree = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 150, 1)
    both = Identities("xgboost", clf_rounds=80).fit_predict(fit, val, COLS, y_fit, 150, 1)
    assert _rmse(both, y_val) < _rmse(tree, y_val) / 2, (
        f"tree {_rmse(tree, y_val):.0f}, identities {_rmse(both, y_val):.0f}"
    )


def test_it_uses_both_identities_and_not_just_the_wider_one() -> None:
    """The control for the test above: check the second identity is really carried.

    The schedule identity spans a far wider range, so a class that only handled it would
    still win the comparison. This measures the rows of the other kind on their own.
    """
    fit, y_fit = _population(9000, seed=2)
    val, y_val = _population(3000, seed=3)
    nm_rows = val["kind"].to_numpy() == 2

    tree = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 150, 1)
    both = Identities("xgboost", clf_rounds=80).fit_predict(fit, val, COLS, y_fit, 150, 1)
    assert _rmse(both[nm_rows], y_val[nm_rows]) < _rmse(tree[nm_rows], y_val[nm_rows])


def test_the_weights_cannot_exceed_one() -> None:
    """A prediction may never land outside everything it was built from.

    Two independent probabilities would allow exactly that; a softmax does not. Built so
    that both candidates look plausible at once, which is the case that would break it.
    """
    rng = np.random.default_rng(4)
    n = 4000
    x = rng.normal(0.0, 1.0, n).astype(np.float32)
    same = rng.uniform(600.0, 1_200.0, n)
    frame = pl.DataFrame({
        "x": x, "kind": np.ones(n, dtype=np.float32),
        SCHED: same, NM: same, TARGET: same,
    })
    y = frame[TARGET].to_numpy()
    out = Identities("xgboost", clf_rounds=60).fit_predict(frame, frame, COLS, y, 80, 1)
    assert out.max() <= same.max() * 1.05, out.max()
    assert out.min() >= 0.0


def test_a_missing_candidate_gives_its_weight_back() -> None:
    """A null candidate must not drag the prediction towards zero."""
    fit, y_fit = _population(6000, seed=5)
    val, _ = _population(600, seed=6)
    val = val.with_columns(
        pl.when(pl.int_range(pl.len()) < 200).then(None).otherwise(pl.col(SCHED)).alias(SCHED),
        pl.when(pl.int_range(pl.len()) < 200).then(None).otherwise(pl.col(NM)).alias(NM),
    )
    out = Identities("xgboost", clf_rounds=60).fit_predict(fit, val, COLS, y_fit, 100, 1)
    assert np.isfinite(out).all()
    assert (out[:200] > 100.0).all(), "a missing candidate collapsed the prediction"


def test_without_the_candidates_it_is_the_inner_learner() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 1.0, 500).astype(np.float32)
    frame = pl.DataFrame({"x": x, TARGET: (10.0 * x).astype(np.float64)})
    y = frame[TARGET].to_numpy()
    plain = models.build("xgboost").fit_predict(frame, frame, ["x"], y, 40, 1)
    both = Identities("xgboost").fit_predict(frame, frame, ["x"], y, 40, 1)
    assert np.allclose(plain, both)


def test_it_is_reachable_by_name() -> None:
    assert models.build("identities-xgboost").name == "identities-xgboost"
    assert models.build("identities-segmented-xgboost").inner == "segmented-xgboost"
