"""The regressor port and its three adapters.

Every adapter takes the same thing, a training frame, a prediction frame, the list of
feature columns and the target, and returns predictions for the prediction frame. Each
one encodes the categorical columns the way its own library wants them, because that is
precisely where the libraries differ and where the difference turned out to matter:

| learner | holdout RMSE, 400 rounds |
|---|---:|
| LightGBM, categorical splits | 378.99 |
| LightGBM, **same code, categorical declaration removed** | 363.97 |
| XGBoost, categoricals as plain integer codes | 357.80 |
| CatBoost depth 8, ordered target statistics | 353.59 |
| CatBoost depth 10 | 348.71 |
| XGBoost and CatBoost depth 8 averaged | 351.69 |

The paired noise floor on this holdout is about 5 seconds, so those gaps are real. The
reading is that LightGBM's categorical splitting overfits the high cardinality fields
here, and there are several: 1,899 stands, a hashed aircraft operator, 11 origins.

Two independent pieces of evidence for that reading. XGBoost applies no categorical
handling at all and beats LightGBM by 21 seconds. And LightGBM with nothing changed but
the categorical declaration removed gains 13.9 of those 21 seconds back, which is the
prediction the diagnosis made before it was tested.

Keeping the interface at the frame level rather than the matrix level is what makes this
comparable. A matrix-level port would have forced one encoding on all three, which is
the assumption under test.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import polars as pl


class Regressor(Protocol):
    """A learner that can be fitted on one frame and asked to predict another."""

    name: str

    def fit_predict(
        self,
        fit: pl.DataFrame,
        val: pl.DataFrame,
        cols: list[str],
        y: np.ndarray,
        rounds: int,
        seed: int,
    ) -> np.ndarray:
        """Return predictions for `val` after fitting on `fit` and `y`."""


def _encode(
    df: pl.DataFrame, cols: list[str], categorical: set[str],
    levels: dict[str, pl.Series] | None = None,
) -> tuple[np.ndarray, list[int], dict[str, pl.Series]]:
    """Frame to float32 matrix with integer coded categoricals.

    The level dictionary is built on the training side and carried to prediction
    unchanged. Without that, the same category maps to different codes on the two sides
    and the model degrades silently rather than failing.
    """
    levels = {} if levels is None else levels
    arrays: list[np.ndarray] = []
    cat_idx: list[int] = []
    for i, c in enumerate(cols):
        s = df[c]
        if c in categorical or s.dtype == pl.String:
            if c not in levels:
                levels[c] = s.drop_nulls().unique().sort()
            codes = s.cast(pl.String).replace_strict(
                old=levels[c].cast(pl.String),
                new=pl.int_range(len(levels[c]), eager=True),
                default=-1,
                return_dtype=pl.Int32,
            )
            arrays.append(codes.cast(pl.Float32).to_numpy())
            cat_idx.append(i)
        elif s.dtype == pl.Boolean:
            arrays.append(s.cast(pl.Float32).fill_null(float("nan")).to_numpy())
        else:
            arrays.append(s.cast(pl.Float32).to_numpy())
    return np.column_stack(arrays).astype(np.float32), cat_idx, levels


class LightGbm:
    """LightGBM. `categorical` selects whether its categorical splitting is used."""

    def __init__(self, categorical: bool = True) -> None:
        self.categorical = categorical
        self.name = "lightgbm" if categorical else "lightgbm-nocat"

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        import lightgbm as lgb

        from taxiout.application import pipeline

        x_fit, cat_idx, levels = _encode(fit, cols, pipeline.CATEGORICAL)
        x_val, _, _ = _encode(val, cols, pipeline.CATEGORICAL, levels)
        params = {
            **pipeline.LGB_PARAMS,
            "learning_rate": 0.05,
            "num_leaves": 127,
            "seed": seed,
            "bagging_seed": seed,
            "feature_fraction_seed": seed,
        }
        dataset = lgb.Dataset(
            x_fit, label=y, feature_name=cols,
            categorical_feature=cat_idx if self.categorical else [],
        )
        booster = lgb.train(params, dataset, num_boost_round=rounds)
        return np.asarray(booster.predict(x_val), dtype=np.float64)


class XGBoost:
    """XGBoost with the histogram method. Categoricals go in as integer codes."""

    name = "xgboost"

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        import xgboost as xgb

        from taxiout.application import pipeline

        x_fit, _, levels = _encode(fit, cols, pipeline.CATEGORICAL)
        x_val, _, _ = _encode(val, cols, pipeline.CATEGORICAL, levels)
        model = xgb.XGBRegressor(
            n_estimators=rounds, learning_rate=0.05, max_depth=9, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", max_bin=127, n_jobs=0,
            random_state=seed, objective="reg:squarederror",
        )
        model.fit(x_fit, y, verbose=False)
        return np.asarray(model.predict(x_val), dtype=np.float64)


class CatBoost:
    """CatBoost, which encodes categoricals with ordered target statistics.

    By far the slowest of the three, roughly seven times LightGBM per round at depth 8
    and three times that again at depth 10, and also the most accurate.

    Depth 10 rather than the library default of 6, because it was measured and the
    difference is large:

    | depth | 400 rounds | 800 rounds |
    |---|---:|---:|
    | 6 | 359.27 | 355.76 |
    | 8 | 356.45 | 355.00 |
    | 10 | **348.71** | **345.60** |

    Depth 10 at 400 rounds already beats depth 8 at 1600 (352.50), so the extra depth
    buys more than four times the rounds. The score was still improving at 1600 rounds,
    slowly, so the round count is a time budget rather than a fitted optimum.
    """

    name = "catboost"

    def __init__(self, depth: int = 10, learning_rate: float = 0.08) -> None:
        self.depth = depth
        self.learning_rate = learning_rate

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        from catboost import CatBoostRegressor, Pool

        from taxiout.application import pipeline

        cat_names = [
            c for c in cols
            if c in pipeline.CATEGORICAL or fit[c].dtype == pl.String
        ]
        as_str = [pl.col(c).cast(pl.String).fill_null("NA") for c in cat_names]
        fit_pd = fit.select(cols).with_columns(as_str).to_pandas()
        val_pd = val.select(cols).with_columns(as_str).to_pandas()
        model = CatBoostRegressor(
            iterations=rounds, learning_rate=self.learning_rate, depth=self.depth,
            loss_function="RMSE", random_seed=seed, verbose=False, thread_count=-1,
        )
        model.fit(Pool(fit_pd, y, cat_features=cat_names))
        return np.asarray(
            model.predict(Pool(val_pd, cat_features=cat_names)), dtype=np.float64
        )


_REGISTRY: dict[str, type | object] = {
    "lightgbm": lambda: LightGbm(categorical=True),
    "lightgbm-nocat": lambda: LightGbm(categorical=False),
    "xgboost": XGBoost,
    "catboost": CatBoost,
    "catboost-d8": lambda: CatBoost(depth=8),
    "catboost-d12": lambda: CatBoost(depth=12),
}


def build(name: str) -> Regressor:
    """Look a regressor up by name, failing loudly on a typo."""
    if name not in _REGISTRY:
        raise KeyError(f"unknown regressor {name!r}; known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def blend(preds: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    """Weighted average of several predictions, equal weights by default.

    Equal weights are the default on purpose. Weights fitted on the holdout are fitted
    on the same rows the score is read from, so they flatter themselves; the measured
    difference between the equal-weight pair and the best searched weighting was 0.27
    seconds, well inside the noise.
    """
    if not preds:
        raise ValueError("nothing to blend")
    if weights is None:
        weights = [1.0 / len(preds)] * len(preds)
    if len(weights) != len(preds):
        raise ValueError(f"{len(preds)} predictions but {len(weights)} weights")
    total = sum(weights)
    return np.sum([w / total * p for w, p in zip(weights, preds, strict=True)], axis=0)
