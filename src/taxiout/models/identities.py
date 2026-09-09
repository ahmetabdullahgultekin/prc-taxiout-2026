"""Two columns that are sometimes the answer, and a softmax that says which.

`mixture.py` found one identity: on 4.86 percent of rows the taxi equals ATOT minus the
scheduled time to within ten seconds, because the airport feed wrote the schedule into
the off-block field. Looking for the same shape elsewhere turned up a second one. On 8.28
percent of rows the taxi equals `nm_naive_taxi_sec`, ATOT minus the Network Manager's own
off-block time, to within ten seconds: there the two independent sources agree exactly.

The two are almost disjoint, 7,828 rows of 1.74 million hold both, and together they
cover 12.7 percent of the training set.

They are worth different amounts and for different reasons, which is why this is a
separate class rather than a wider tolerance:

| identity | share | median taxi | rows above two hours |
|---|---:|---:|---:|
| the feed used the schedule | 4.86% | 1,009 | **333 of 435** |
| the feed and the network agree | 8.28% | 898 | **0** |

The schedule identity is where the metric lives; the network identity never produces a
monster and pays off in ordinary accuracy, worth a few seconds rather than a hundred.
Being wrong about the second is also cheap: the network time scores 393 as a predictor
even where it is not exact, so a false positive lands near the truth anyway.

One classifier with three outcomes rather than two independent ones, because the weights
have to sum to at most one. Two separate probabilities can both say 0.8 and leave the
prediction 0.6 of the way outside the range of anything it was built from.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout.models.base import _encode, build

# The columns that are sometimes the target exactly. Order fixes the class labels:
# 0 is neither, then one class per candidate.
CANDIDATES: tuple[str, ...] = ("sched_offset_sec", "nm_naive_taxi_sec")
TOLERANCE_SEC = 10.0


class Identities:
    """A softmax over {neither, each candidate}, mixing the candidates by probability."""

    def __init__(
        self,
        inner: str = "xgboost",
        candidates: tuple[str, ...] = CANDIDATES,
        tolerance_sec: float = TOLERANCE_SEC,
        clf_rounds: int = 300,
    ) -> None:
        self.inner = inner
        self.candidates = candidates
        self.tolerance_sec = tolerance_sec
        self.clf_rounds = clf_rounds
        self.name = f"identities-{inner}"

    def _label(self, frame: pl.DataFrame, y: np.ndarray) -> np.ndarray:
        """0 where no candidate matches, otherwise the index of the first that does.

        First rather than closest: the two overlap on well under one percent of rows, and
        a rule that depends on which is nearer would make the label unstable for a
        difference of a second.
        """
        label = np.zeros(len(y), dtype=np.int64)
        for i, column in enumerate(self.candidates, start=1):
            if column not in frame.columns:
                continue
            value = frame[column].cast(pl.Float64).to_numpy()
            hit = np.isfinite(value) & (np.abs(y - value) <= self.tolerance_sec)
            label = np.where((label == 0) & hit, i, label)
        return label

    def fit_predict(self, fit, val, cols, y, rounds, seed):
        import xgboost as xgb

        from taxiout.application import pipeline

        present = [c for c in self.candidates if c in fit.columns and c in val.columns]
        if not present:
            return build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        label = self._label(fit, y)
        classes = int(label.max()) + 1
        # Every class needs enough rows to be worth a model, and there has to be more
        # than one of them, or this is a plain regression with extra steps.
        counts = np.bincount(label, minlength=classes)
        if classes < 2 or counts.min() < 100:
            return build(self.inner).fit_predict(fit, val, cols, y, rounds, seed)

        rest = build(self.inner).fit_predict(
            fit.filter(pl.Series(label == 0)), val, cols, y[label == 0], rounds, seed
        )

        x_fit, _, levels = _encode(fit, cols, pipeline.CATEGORICAL)
        x_val, _, _ = _encode(val, cols, pipeline.CATEGORICAL, levels)
        clf = xgb.XGBClassifier(
            n_estimators=self.clf_rounds, learning_rate=0.08, max_depth=8, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", max_bin=127, n_jobs=0,
            random_state=seed, objective="multi:softprob", num_class=classes,
            eval_metric="mlogloss",
        )
        clf.fit(x_fit, label, verbose=False)
        probability = np.asarray(clf.predict_proba(x_val), dtype=np.float64)

        out = probability[:, 0] * rest
        spent = probability[:, 0].copy()
        for i, column in enumerate(self.candidates, start=1):
            if i >= probability.shape[1]:
                break
            value = val[column].cast(pl.Float64).to_numpy() if column in val.columns else None
            if value is None:
                continue
            known = np.isfinite(value)
            weight = np.where(known, probability[:, i], 0.0)
            out = out + weight * np.clip(np.where(known, value, 0.0), 0.0, None)
            spent = spent + weight
        # Where a candidate was missing its weight was dropped; give it back to `rest`
        # rather than shrinking the prediction towards zero.
        return out + (1.0 - spent) * rest
