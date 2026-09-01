"""Seasonal validation run: baseline model and target parameterisation comparison.

January and July are removed from 2025, the model is trained on the remaining 10 months and
evaluated on those two months **separately**. Random K-fold would lie here: the ranking set
is January + July 2026, that is two seasonal extremes plus a one-year shift.

The same run compares two target parameterisations:

  raw       -> TAXITIME_SEC_mvt directly
  residual  -> TAXITIME_SEC_mvt - reference_sec (ATXOT P10), added back at prediction time

The single largest gain of the 2025 winner was exactly this kind of reparameterisation:
fuel flow instead of fuel burn (RMSE 220.56 -> 201.04), a larger effect than any of the
feature groups (P05). So it is measured in the first run.

    python scripts/train_baseline.py --data-dir D:/prc-taxiout-2026
    python scripts/train_baseline.py --data-dir D:/prc-taxiout-2026 --causal
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np

from taxiout.application import pipeline
from taxiout.domain import reference


def report(name: str, split: pipeline.Split, pred: np.ndarray) -> None:
    scores = pipeline.evaluate(split, pred)
    print(f"\n=== {name} ===")
    print(f"  total RMSE: {scores['total']:8.2f} s   (n={split.val.height:,})")
    print("  -- by month_num --")
    for m in pipeline.HOLDOUT_MONTHS:
        if f"month_{m}" in scores:
            print(f"     {m:<8} RMSE={scores[f'month_{m}']:8.2f}")
    print("  -- by airport (worst to best) --")
    per_apt = sorted(
        ((k.removeprefix("apt_"), v) for k, v in scores.items() if k.startswith("apt_")),
        key=lambda kv: -kv[1],
    )
    for apt, r in per_apt:
        print(f"     {apt:<8} RMSE={r:8.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="seasonal validation baseline run")
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--rounds", type=int, default=1500)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--causal", action="store_true",
                    help="causal mode: features are anchored to the off-block instant, "
                         "no forward-looking window (for the paper only)")
    ap.add_argument("--max-train-sec", type=float, default=None,
                    help="drop rows whose target exceeds this threshold FROM TRAINING "
                         "(validation stays complete); a label error filter")
    ap.add_argument("--no-aobt3", action="store_true",
                    help="drop the feature derived from the NM block time (ablation)")
    args = ap.parse_args()

    t0 = time.time()
    inputs = pipeline.load_inputs(Path(args.data_dir) / "00_raw")
    mode = "CAUSAL (block-anchored)" if args.causal else "retrospective (departure-anchored)"
    print(f"movements: {inputs.movements.height:,} rows")
    print(f"METAR: {'none' if inputs.metar is None else f'{inputs.metar.height:,} observations'}")
    print(f"mode: {mode}")

    feats = pipeline.build_features(inputs, causal=args.causal, aobt3=not args.no_aobt3)
    split = pipeline.seasonal_split(feats, inputs.movements, args.max_train_sec)
    print(f"training {split.fit.height:,} / validation {split.val.height:,} departures, "
          f"{len(split.columns)} features")
    if args.max_train_sec:
        print(f"training target threshold: {args.max_train_sec:,.0f} s")
    print("\nfeature family sizes:")
    print(pipeline.group_report(split.columns))

    print("\nreference coverage (official ATXOT level vs fallback):")
    print(reference.official_coverage(split.val))

    seeds = tuple(range(1, args.seeds + 1))
    for name, residual in (
        ("raw target", False),
        ("residual target (taxi - ATXOT P10)", True),
    ):
        pred = pipeline.train_predict(split, split.columns, args.rounds, residual, seeds)
        report(name, split, pred)

    print(f"\ntotal time: {time.time() - t0:,.0f} s")


if __name__ == "__main__":
    main()
