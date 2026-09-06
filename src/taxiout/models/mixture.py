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

**Why there are two ways of getting the weight.** Under a squared loss the optimal weight
on the candidate is exactly the probability that the candidate is the answer, so scaling
it above one should not help. It does: on the holdout, 393.99 at scale 1.0 against 368.52
at 2.0, and widening the tolerance instead makes things worse at every scale, so the
scale is not standing in for a wider definition.

The explanation is that "the offset is the answer" is narrower than "the offset is worth
listening to". A flight whose taxi is within a few minutes of its schedule offset is not
an exact match and the offset is still a better prediction for it than a leaf constant.
The classifier is answering the wrong question by a small margin, and the scale is a
crude correction for it.

`weight_mode="regression"` asks the right question instead. For every training row the
weight that would have minimised the squared error is

    w* = (y - rest) / (offset - rest),  clipped to [0, 1]

so that quantity can simply be fitted, with the rows weighted by (offset - rest)^2, which
is how much getting the weight wrong actually costs there. Where the two candidates are
close the target is noise and the weighting correctly ignores it.
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
        weight_mode: str = "classifier",
        folds: int = 3,
        weight_clip: tuple[float, float] = (0.0, 1.0),
    ) -> None:
        if weight_mode not in ("classifier", "regression"):
            raise ValueError(f"unknown weight_mode {weight_mode!r}")
        self.inner = inner
        self.tolerance_sec = tolerance_sec
        self.clf_rounds = clf_rounds
        self.scale = scale
        self.weight_mode = weight_mode
        self.folds = folds
        self.weight_clip = weight_clip
        self.name = f"mixture-{inner}" + ("" if weight_mode == "classifier" else "-w")

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

    def _out_of_fold(
        self, fit: pl.DataFrame, cols: list[str], y: np.ndarray,
        ordinary: np.ndarray, rounds: int, seed: int,
    ) -> np.ndarray:
        """The ordinary model's opinion of the training rows, without having seen them.

        This is the part that has to be right. Asking a model about rows it was fitted on
        would make the weight target look like zero everywhere, since the model already
        matches those rows, and the class would learn to never use the candidate. That is
        exactly the population it exists to serve, so the predictions are made out of
        fold. The substituted rows were never in the ordinary model's training set, so a
        model fitted on all the ordinary rows is already out of sample for them.
        """
        out = np.zeros(len(y))
        index = np.arange(len(y))
        ordinary_index = index[ordinary]
        rng = np.random.default_rng(seed)
        fold = rng.integers(0, self.folds, len(ordinary_index))
        for k in range(self.folds):
            train = ordinary_index[fold != k]
            score = ordinary_index[fold == k]
            if len(train) < 100 or len(score) == 0:
                continue
            out[score] = build(self.inner).fit_predict(
                fit[train], fit[score], cols, y[train], rounds, seed
            )
        if (~ordinary).any():
            out[index[~ordinary]] = build(self.inner).fit_predict(
                fit.filter(pl.Series(ordinary)), fit[index[~ordinary]], cols,
                y[ordinary], rounds, seed,
            )
        return out

    def _fitted_weight(
        self, fit: pl.DataFrame, val: pl.DataFrame, cols: list[str],
        y: np.ndarray, rest_fit: np.ndarray, off_fit: np.ndarray, seed: int,
    ) -> np.ndarray:
        """Fit the weight that would have been right, rather than a proxy for it.

        The rows are weighted by the squared distance between the two candidates, which
        is exactly what a wrong weight costs on that row, so rows where they agree
        contribute nothing and cannot inject noise.
        """
        import xgboost as xgb

        from taxiout.application import pipeline

        gap = off_fit - rest_fit
        usable = np.isfinite(gap) & (np.abs(gap) > 1.0)
        target = np.zeros(len(y))
        low, high = self.weight_clip
        target[usable] = np.clip((y[usable] - rest_fit[usable]) / gap[usable], low, high)
        sample_weight = np.where(usable, np.minimum(gap ** 2, 1e10), 0.0)

        x_fit, _, levels = _encode(fit, cols, pipeline.CATEGORICAL)
        x_val, _, _ = _encode(val, cols, pipeline.CATEGORICAL, levels)
        model = xgb.XGBRegressor(
            n_estimators=self.clf_rounds, learning_rate=0.08, max_depth=8, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", max_bin=127, n_jobs=0,
            random_state=seed, objective="reg:squarederror",
        )
        model.fit(x_fit, target, sample_weight=sample_weight, verbose=False)
        return np.clip(np.asarray(model.predict(x_val), dtype=np.float64), 0.0, 1.0)

    # The weight the model emits is always clipped to [0, 1], whatever the target was
    # clipped to: a weight outside that range extrapolates past both candidates, which is
    # not something either of them supports. `weight_clip` widens only the TARGET, so that
    # a row whose truth overshoots the candidate is not recorded as if it had landed
    # exactly on it. The fitted mean prediction sits about five percent above the truth's
    # mean, which is the shape that a one-sided clip would produce.

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
        if self.weight_mode == "regression":
            rest_fit = self._out_of_fold(fit, cols, y, ordinary, rounds, seed)
            weight = self._fitted_weight(fit, val, cols, y, rest_fit, off_fit, seed)
        else:
            probability = self._probability(fit, val, cols, substituted, seed)
            weight = probability
        weight = np.clip(weight * self.scale, 0.0, 1.0)

        # A negative offset would mean taking off before the scheduled off-block, which
        # is a taxi of less than nothing. Where the schedule is missing there is no
        # second opinion to mix in, so the weight goes to zero.
        offset = np.clip(off_val, 0.0, None)
        known = np.isfinite(off_val)
        weight = np.where(known, weight, 0.0)
        offset = np.where(known, offset, 0.0)

        return (1.0 - weight) * rest + weight * offset
