"""One model for the flights the Network Manager matched, another for the rest.

The measurement that forced this:

| rows | share | RMSE | share of the squared error |
|---|---:|---:|---:|
| with a network match | 98.75% | 215.1 | 37.8% |
| without one | **1.25%** | **2455.9** | **62.2%** |

One and a quarter percent of the holdout carries nearly two thirds of the metric. Every
feature this project has built serves the other ninety-nine, which already score 215.

The two groups are not the same problem. A flight the Network Manager never matched
loses more than its off-block time: every `_flt` column comes from that flight list, so
market segment, wake category, filed destination and the estimated off-block time all go
with it. `MARKET_SEGMENT_flt` is null for all 2,723 unmatched rows in the holdout. A
single model fitted across both spends its capacity on the ninety-nine percent, because
that is where the rows are, and then applies whatever it learned about the remainder from
a handful of training examples.

At Rome the result is visible: for unmatched departures the model predicts a median of
4,683 seconds against a median truth of 1,316. It has learned "unmatched at Rome means
enormous" from the few broken block times in that subgroup and applies it to all of them.

Fitting the two separately, measured on the holdout with XGBoost at 400 rounds:

    one model everywhere                     347.74
    a dedicated model for the unmatched      322.39

and on the unmatched rows themselves, 2455.9 down to 2160.9.

**This is a local measurement and the board decides.** A 10.76 second local gain from the
overlap counters became a 7.03 second board loss earlier the same day, so nothing here is
believed until it is submitted.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout.models.base import build

# The column that says whether the Network Manager matched this flight. It is a feature
# in its own right as well as the split, which is fine: the segment models simply find
# it constant.
SEGMENT = "nm_matched"


class Segmented:
    """Fits `inner` once per segment of `SEGMENT` and predicts each row from its own.

    A segment with too few training rows falls back to the model fitted on everything,
    since a model fitted on a handful of flights is worse than a model that at least saw
    the problem. `min_rows` is deliberately generous.
    """

    def __init__(self, inner: str = "xgboost", min_rows: int = 5000) -> None:
        self.inner = inner
        self.min_rows = min_rows
        self.name = f"segmented-{inner}"

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        if SEGMENT not in fit.columns or SEGMENT not in val.columns:
            return build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        fit_flag = fit[SEGMENT].fill_null(False).to_numpy().astype(bool)  # noqa: FBT003
        val_flag = val[SEGMENT].fill_null(False).to_numpy().astype(bool)  # noqa: FBT003

        # The shared model is fitted regardless: it is the fallback for a thin segment,
        # and predicting every row from it costs one fit rather than a special case.
        out = build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        for matched in (True, False):
            fit_rows = fit_flag == matched
            val_rows = val_flag == matched
            if not val_rows.any():
                continue
            if int(fit_rows.sum()) < self.min_rows:
                continue
            part = build(self.inner).fit_predict(
                fit.filter(pl.Series(fit_rows)), val.filter(pl.Series(val_rows)),
                cols, y[fit_rows], rounds, seed,
            )
            out[val_rows] = part

        return np.asarray(out, dtype=np.float64)
