"""When the feed had no off-block time it wrote down the scheduled one.

On 4.86 percent of training rows the taxi time equals ATOT minus the scheduled time to
within ten seconds. Since the target is ATOT minus AOBT, that says the airport feed's
off-block time IS the scheduled time on those rows, to the second. It is not spread
evenly: 18.4 percent at Rome against 1.1 percent at Zurich, and 53.8 percent at Rome
among flights the Network Manager never matched, where the median taxi is 7,436 seconds.

Two facts make this the largest thing in the project.

**It is where the metric lives.** 333 of the 435 training rows with a taxi above two
hours are rows of this kind, and 97 of the holdout's 149. Those rows carry roughly two
thirds of the squared error. Their target is not noise: it is a column the ranking set
publishes.

**A tree reaches it badly.** The first version of this file claimed a tree cannot emit
`y = sched_offset` at all, since it predicts a constant per leaf. The control test in
`test_mixture.py` refuted that: on a clean two-population problem a tree at 400 rounds
approximated the identity to an RMSE of 493 over a range of 40,000, by spending a great
many splits on it. The claim was wrong and this is the corrected one.

What survives is enough. The tree has to find the identity, spend capacity on it against
everything else it is fitting, and it can only approximate it with a staircase whose
steps are widest where the offset is largest. Here the substituted rows are one row in
twenty and their offsets run from minutes to more than a day, so the staircase is
coarsest exactly where the squared metric is most expensive.

So the estimator is a mixture, which is also the form a squared metric asks for:

    E[y|x] = P(substituted|x) * sched_offset + (1 - P(substituted|x)) * E[y | x, not]

**Why this should survive 2026, checked rather than assumed.** The rule cannot be tested
on the ranking set's departures, whose block times are blanked. It can be tested on its
arrivals, which keep everything. The same substitution on the arrival side runs at 2.31
percent in January and July 2025 and 2.42 percent in the same months of 2026, and the
per-airport pattern is the same in both: Rome 8.81 then 9.74 percent, Frankfurt 0.88 then
0.79. The behaviour belongs to the feed, not to the year.

The honest failure mode: if the probability is badly calibrated, an ordinary flight with
a schedule offset of fifty thousand seconds and a five percent probability collects two
and a half thousand seconds of error it did not have. `scale` exists so that the
sensitivity to this is measurable rather than assumed, and the default is a plain
expectation with no thumb on the scale.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout.models.base import _encode, build

# The feature holding ATOT minus the scheduled time. Named here rather than imported
# from the pipeline because this class is about that one quantity.
OFFSET = "sched_offset_sec"

# Ten seconds. The spike in the difference is about five times the local background and
# essentially all of it sits inside this window; widening it collects ordinary flights
# that happened to leave near their scheduled time.
TOLERANCE_SEC = 10.0


class Mixture:
    """`inner` for the ordinary flights, the schedule offset for the substituted ones."""

    def __init__(
        self,
        inner: str = "xgboost",
        tolerance_sec: float = TOLERANCE_SEC,
        clf_rounds: int = 300,
        scale: float = 1.0,
    ) -> None:
        self.inner = inner
        self.tolerance_sec = tolerance_sec
        self.clf_rounds = clf_rounds
        self.scale = scale
        self.name = f"mixture-{inner}"

    def _probability(
        self, fit: pl.DataFrame, val: pl.DataFrame, cols: list[str],
        label: np.ndarray, seed: int,
    ) -> np.ndarray:
        import xgboost as xgb

        from taxiout.application import pipeline

        x_fit, _, levels = _encode(fit, cols, pipeline.CATEGORICAL)
        x_val, _, _ = _encode(val, cols, pipeline.CATEGORICAL, levels)
        clf = xgb.XGBClassifier(
            n_estimators=self.clf_rounds, learning_rate=0.08, max_depth=8, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", max_bin=127, n_jobs=0,
            random_state=seed, objective="binary:logistic", eval_metric="logloss",
        )
        clf.fit(x_fit, label.astype(int), verbose=False)
        return np.asarray(clf.predict_proba(x_val)[:, 1], dtype=np.float64)

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        if OFFSET not in fit.columns or OFFSET not in val.columns:
            return build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        off_fit = fit[OFFSET].cast(pl.Float64).to_numpy()
        off_val = val[OFFSET].cast(pl.Float64).to_numpy()
        substituted = np.isfinite(off_fit) & (np.abs(y - off_fit) <= self.tolerance_sec)

        # Both segments have to be worth fitting. Below that this degrades to the inner
        # learner rather than fitting a classifier on a handful of positives.
        ordinary = ~substituted
        if substituted.sum() < 100 or ordinary.sum() < 100:
            return build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        rest = build(self.inner).fit_predict(
            fit.filter(pl.Series(ordinary)), val, cols, y[ordinary], rounds, seed
        )
        probability = self._probability(fit, val, cols, substituted, seed)
        weight = np.clip(probability * self.scale, 0.0, 1.0)

        # A negative offset would mean taking off before the scheduled off-block, which
        # is a taxi of less than nothing. Where the schedule is missing there is no
        # second opinion to mix in, so the weight goes to zero.
        offset = np.clip(off_val, 0.0, None)
        known = np.isfinite(off_val)
        weight = np.where(known, weight, 0.0)
        offset = np.where(known, offset, 0.0)

        return (1.0 - weight) * rest + weight * offset
