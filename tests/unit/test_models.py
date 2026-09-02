"""The regressor port, its registry, its blending and its encoding.

The encoding tests are the ones that earn their place. A learner given inconsistently
coded categories does not fail, it fits happily and predicts badly, and the only symptom
is a score that is worse than it should be for no visible reason. That is exactly the
class of defect this project has already been bitten by twice, so it gets a guard.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from taxiout import models
from taxiout.models.base import _encode


def test_build_returns_each_registered_learner_under_its_own_name() -> None:
    for name in ("lightgbm", "lightgbm-nocat", "xgboost", "catboost"):
        assert models.build(name).name == name


def test_build_rejects_an_unknown_name_instead_of_falling_back() -> None:
    # A typo in --learners must stop the run. Silently defaulting to LightGBM would
    # produce a submission that is not the one asked for.
    with pytest.raises(KeyError, match="unknown regressor"):
        models.build("lightbgm")


def test_blend_averages_equally_by_default() -> None:
    out = models.blend([np.array([0.0, 10.0]), np.array([2.0, 20.0])])
    assert out.tolist() == [1.0, 15.0]


def test_blend_normalises_the_weights_it_is_given() -> None:
    # Weights of 3 and 1 mean the same thing as 0.75 and 0.25.
    out = models.blend([np.array([0.0]), np.array([4.0])], [3.0, 1.0])
    assert out.tolist() == [1.0]


def test_blend_refuses_a_weight_count_that_does_not_match() -> None:
    with pytest.raises(ValueError, match="2 predictions but 3 weights"):
        models.blend([np.array([1.0]), np.array([2.0])], [1.0, 1.0, 1.0])


def test_blend_refuses_an_empty_list() -> None:
    with pytest.raises(ValueError, match="nothing to blend"):
        models.blend([])


# --------------------------------------------------------------------------- encoding


def _frames() -> tuple[pl.DataFrame, pl.DataFrame]:
    fit = pl.DataFrame({"stand": ["A1", "B2", "C3", "A1"], "n": [1.0, 2.0, 3.0, 4.0]})
    val = pl.DataFrame({"stand": ["C3", "A1", "Z9"], "n": [5.0, 6.0, 7.0]})
    return fit, val


def test_the_same_category_gets_the_same_code_on_both_sides() -> None:
    """The failure this prevents is silent: codes drift, the model degrades, nothing raises."""
    fit, val = _frames()
    cols, cat = ["stand", "n"], {"stand"}
    x_fit, cat_idx, levels = _encode(fit, cols, cat)
    x_val, _, _ = _encode(val, cols, cat, levels)

    assert cat_idx == [0]
    # A1 is row 0 of fit and row 1 of val; C3 is row 2 of fit and row 0 of val.
    assert x_val[1, 0] == x_fit[0, 0]
    assert x_val[0, 0] == x_fit[2, 0]


def test_encoding_the_prediction_side_alone_would_give_different_codes() -> None:
    """The negative control: without the carried levels the codes really do differ.

    Without this case the test above could pass on a data set where the two encodings
    happen to agree, and would then be proving nothing.
    """
    fit, val = _frames()
    cols, cat = ["stand", "n"], {"stand"}
    x_fit, _, _ = _encode(fit, cols, cat)
    x_val_alone, _, _ = _encode(val, cols, cat)  # levels rebuilt from val

    # C3 is the third of three stands in fit and the second of three in val, so rebuilding
    # the levels moves it. A1 is first in both and would not have shown the defect, which
    # is the point of naming the category explicitly rather than trusting any row.
    assert x_fit[2, 0] == 2.0
    assert x_val_alone[0, 0] == 1.0


def test_a_category_unseen_in_training_is_coded_as_minus_one() -> None:
    # 24 stand combinations in the ranking set were never seen in training. They have to
    # land somewhere defined rather than raising or silently becoming a known stand.
    fit, val = _frames()
    _, _, levels = _encode(fit, ["stand", "n"], {"stand"})
    x_val, _, _ = _encode(val, ["stand", "n"], {"stand"}, levels)
    assert x_val[2, 0] == -1.0


def test_numeric_columns_pass_through_untouched() -> None:
    fit, _ = _frames()
    x_fit, cat_idx, _ = _encode(fit, ["stand", "n"], {"stand"})
    assert cat_idx == [0]
    assert x_fit[:, 1].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_booleans_become_numbers_and_keep_their_nulls() -> None:
    df = pl.DataFrame({"flag": [True, False, None]})
    x, cat_idx, _ = _encode(df, ["flag"], set())
    assert cat_idx == []
    assert x[0, 0] == 1.0
    assert x[1, 0] == 0.0
    assert np.isnan(x[2, 0])


# --------------------------------------------------------------------------- learners


@pytest.mark.parametrize("name", ["lightgbm", "lightgbm-nocat", "xgboost", "catboost"])
def test_every_learner_fits_a_signal_it_can_see(name: str) -> None:
    """Each adapter must actually learn, not merely return an array of the right length.

    The target is built from the features, so a working learner beats predicting the
    mean by a wide margin. A broken adapter that returns constants passes a shape check
    and fails this one.
    """
    rng = np.random.default_rng(0)
    n = 600
    group = rng.integers(0, 4, n)
    noise = rng.normal(0.0, 1.0, n)
    y = 100.0 * group + 10.0 * noise

    df = pl.DataFrame({
        "stand": [f"S{g}" for g in group],
        "n": noise.astype(np.float32),
    })
    fit, val = df.head(450), df.tail(150)
    y_fit, y_val = y[:450], y[450:]

    pred = models.build(name).fit_predict(fit, val, ["stand", "n"], y_fit, rounds=60, seed=1)

    assert pred.shape == (150,)
    assert np.isfinite(pred).all()
    learned = float(np.sqrt(np.mean((pred - y_val) ** 2)))
    baseline = float(np.sqrt(np.mean((y_fit.mean() - y_val) ** 2)))
    assert learned < baseline / 2, f"{name}: {learned:.1f} against a baseline of {baseline:.1f}"
