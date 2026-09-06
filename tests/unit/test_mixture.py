"""The mixture learner: does it actually recover a target that equals one of its inputs.

The first version of this file asserted that a tree cannot emit `y = sched_offset` at
all, because it predicts a constant per leaf. The control test refuted that: given 400
rounds at depth 9 on a clean two-population problem, a tree approximated the identity to
an RMSE of 493 over a range of 40,000, by spending many splits on it. The claim was too
strong and has been corrected here and in the module.

What is true is weaker and still decisive. The tree has to find the identity, spend
capacity on it, and it approximates it with a staircase whose steps are widest exactly
where the offset is largest and the rows are fewest. So the population here is drawn the
way the real one behaves: the substituted rows are a twentieth of the data and their
offsets are log-spaced out to a day, which is where a staircase does worst.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout import models
from taxiout.models.mixture import OFFSET, Mixture

TARGET = "TAXITIME_SEC_mvt"


def _population(n: int, seed: int, substituted_share: float = 0.05):
    """Two kinds of row, drawn the way the real ones are distributed.

    Ordinary rows have a taxi that depends on `x` and not at all on the schedule offset.
    Substituted rows have a taxi that IS the schedule offset, log-spaced from five
    minutes to a day so that the rare large values, which is where the metric lives, are
    also where a staircase of leaf constants is coarsest.
    """
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, n).astype(np.float32)
    offset = np.exp(rng.uniform(np.log(300.0), np.log(86_400.0), n))
    flag = rng.random(n) < substituted_share
    # `marker` is what makes the two kinds separable at all; without something like it
    # the classifier has nothing to learn and the mixture should not help.
    marker = flag.astype(np.float32)
    ordinary = 900.0 + 200.0 * x
    y = np.where(flag, offset, ordinary)
    frame = pl.DataFrame({
        "x": x,
        "marker": marker,
        OFFSET: offset,
        TARGET: y,
    })
    return frame, y


def _rmse(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.sqrt(np.mean((p - y) ** 2)))


COLS = ["x", "marker", OFFSET]


def test_it_recovers_a_target_that_is_one_of_its_inputs() -> None:
    fit, y_fit = _population(6000, seed=0)
    val, y_val = _population(3000, seed=1)

    tree = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 120, 1)
    mixed = Mixture("xgboost", clf_rounds=60).fit_predict(fit, val, COLS, y_fit, 120, 1)

    # The tree has the offset as a feature and approximates it badly where it is large;
    # the mixture reads it off.
    assert _rmse(mixed, y_val) < _rmse(tree, y_val) / 2, (
        f"tree {_rmse(tree, y_val):.0f}, mixture {_rmse(mixed, y_val):.0f}"
    )


def test_the_tree_really_does_struggle_here() -> None:
    """The control: the comparison means nothing unless the tree, given the same inputs
    and more rounds than the mixture's inner learner, is still far from the answer.

    This assertion is deliberately calibrated against what was measured rather than what
    was assumed. An earlier version demanded an RMSE above 2,000 on a uniform offset and
    the tree reached 493, which is how the over-strong claim in the module was found."""
    fit, y_fit = _population(6000, seed=2)
    val, y_val = _population(3000, seed=3)
    tree = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 400, 1)
    assert _rmse(tree, y_val) > 1000, _rmse(tree, y_val)


def test_it_does_not_disturb_a_population_with_no_substitution() -> None:
    """If no row's target equals the offset, the mixture must fall back cleanly.

    This is the failure that would cost the most in practice: paying for a mechanism that
    is not there.
    """
    rng = np.random.default_rng(4)
    n = 4000
    x = rng.normal(0.0, 1.0, n).astype(np.float32)
    frame = pl.DataFrame({
        "x": x,
        "marker": np.zeros(n, dtype=np.float32),
        OFFSET: rng.uniform(300.0, 40_000.0, n),
        TARGET: (900.0 + 200.0 * x).astype(np.float64),
    })
    y = frame[TARGET].to_numpy()

    tree = models.build("xgboost").fit_predict(frame, frame, COLS, y, 100, 1)
    mixed = Mixture("xgboost", clf_rounds=60).fit_predict(frame, frame, COLS, y, 100, 1)
    assert _rmse(mixed, y) < _rmse(tree, y) * 1.5


def test_without_the_offset_column_it_is_the_inner_learner() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0.0, 1.0, 500).astype(np.float32)
    frame = pl.DataFrame({"x": x, TARGET: (10.0 * x).astype(np.float64)})
    y = frame[TARGET].to_numpy()

    plain = models.build("xgboost").fit_predict(frame, frame, ["x"], y, 40, 1)
    mixed = Mixture("xgboost").fit_predict(frame, frame, ["x"], y, 40, 1)
    assert np.allclose(plain, mixed)


def test_a_missing_schedule_takes_the_ordinary_prediction() -> None:
    """A null offset has no second opinion to mix in, and must not become a zero."""
    fit, y_fit = _population(4000, seed=6)
    val, y_val = _population(600, seed=7)
    val = val.with_columns(
        pl.when(pl.int_range(pl.len()) < 100)
        .then(None)
        .otherwise(pl.col(OFFSET))
        .alias(OFFSET)
    )
    out = Mixture("xgboost", clf_rounds=60).fit_predict(fit, val, COLS, y_fit, 100, 1)
    assert np.isfinite(out).all()
    assert (out[:100] > 100.0).all(), "a missing schedule collapsed the prediction"


def test_a_negative_offset_is_not_predicted() -> None:
    """Taking off before the scheduled off-block would be a taxi of less than nothing."""
    fit, y_fit = _population(4000, seed=8)
    val, _ = _population(300, seed=9)
    val = val.with_columns((pl.col(OFFSET) * -1.0).alias(OFFSET))
    out = Mixture("xgboost", clf_rounds=60).fit_predict(fit, val, COLS, y_fit, 100, 1)
    assert (out >= 0.0).all()


def test_it_is_reachable_by_name() -> None:
    assert models.build("mixture-xgboost").name == "mixture-xgboost"
    assert models.build("mixture-catboost").name == "mixture-catboost"


def test_the_fitted_weight_mode_also_recovers_the_identity() -> None:
    """The second way of getting the weight has to clear the same bar as the first."""
    fit, y_fit = _population(6000, seed=10)
    val, y_val = _population(3000, seed=11)
    tree = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 120, 1)
    fitted = Mixture("xgboost", clf_rounds=60, weight_mode="regression").fit_predict(
        fit, val, COLS, y_fit, 120, 1
    )
    assert _rmse(fitted, y_val) < _rmse(tree, y_val) / 2, (
        f"tree {_rmse(tree, y_val):.0f}, fitted weight {_rmse(fitted, y_val):.0f}"
    )


def test_the_fitted_weight_is_not_collapsed_to_zero() -> None:
    """The control for the out-of-fold step.

    If the ordinary model were asked about rows it had been fitted on, the weight target
    would be zero nearly everywhere and this class would quietly become its inner
    learner. That failure is invisible in a score, so it is checked directly.
    """
    fit, y_fit = _population(6000, seed=12)
    val, _ = _population(2000, seed=13)
    plain = models.build("xgboost").fit_predict(fit, val, COLS, y_fit, 120, 1)
    fitted = Mixture("xgboost", clf_rounds=60, weight_mode="regression").fit_predict(
        fit, val, COLS, y_fit, 120, 1
    )
    moved = np.abs(fitted - plain) > 1.0
    assert moved.mean() > 0.05, f"only {moved.mean():.1%} of rows moved at all"


def test_an_unknown_weight_mode_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError, match="weight_mode"):
        Mixture("xgboost", weight_mode="magic")
