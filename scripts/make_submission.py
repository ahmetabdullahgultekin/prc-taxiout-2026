"""Produces predictions for the ranking set and writes a valid submission file.

One design point matters: **the congestion features are built from each data set's own
movement stream.** The ranking set contains every movement of January + July 2026 (arrivals
included, none of them blanked out), so the traffic intensity of those months is computed
from there, not from the 2025 data. The reference table is the opposite case, it comes from
2025, because the ranking set has no taxi times for departures.

Flow:

    1. Train on all of 2025 (seasonal validation is a separate run, `train_baseline.py`)
    2. Build features on ranking.parquet, apply the 2025 reference
    3. Predict, clip, validate, write

    python scripts/make_submission.py --data-dir D:/prc-taxiout-2026 --team keen-hamburger
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import polars as pl

from taxiout import config
from taxiout.application import cache, pipeline, submission
from taxiout.domain import reference
from taxiout.features import groups

TARGET = pipeline.TARGET


def main() -> None:
    ap = argparse.ArgumentParser(description="produce a ranking set submission")
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--team", required=True, help="assigned team name, e.g. keen-hamburger")
    ap.add_argument("--rounds", type=int, default=1500)
    ap.add_argument("--seeds", type=int, default=5,
                    help="seed averaging; the method of the 2024 winner")
    ap.add_argument("--learners", default="lightgbm",
                    help="comma separated, from taxiout.models: lightgbm, "
                         "lightgbm-nocat, xgboost, catboost")
    ap.add_argument("--raw-target", action="store_true")
    ap.add_argument("--drop-groups", nargs="*", default=[],
                    help="feature families to drop, for ablation")
    ap.add_argument("--version", type=int, default=None,
                    help="explicit version; defaults to the next one")
    ap.add_argument("--use-cache", action="store_true",
                    help="load features from scripts/cache_features.py --ranking "
                         "instead of rebuilding them, which is most of the run time")
    ap.add_argument("--force-cache", action="store_true",
                    help="use the cache even when its fingerprint says the feature code "
                         "has changed since it was built")
    args = ap.parse_args()

    t0 = time.time()
    raw = Path(args.data_dir) / "00_raw"
    out_dir = Path(args.data_dir) / "04_submissions"
    rank_path, template_path = raw / "ranking.parquet", raw / "submitting.parquet"
    for p in (rank_path, template_path):
        if not p.exists():
            raise SystemExit(f"not found: {p}")

    if args.use_cache:
        # Both sides come from scripts/cache_features.py --ranking. The cache carries a
        # fingerprint of the code that built it and refuses to load when that has moved,
        # so this cannot quietly submit a model built from features that no longer exist.
        cached = cache.read(config.cache(args.data_dir), want_rank=True,
                            force=args.force_cache)
        fit = cached.fit_full
        rank_feats = cached.rank
        print(f"cached features: fit {fit.height:,}, ranking {rank_feats.height:,}")
    else:
        # --- training side
        inputs = pipeline.load_inputs(raw)
        print(f"training movements: {inputs.movements.height:,}")
        fit_feats = pipeline.build_features(inputs).filter(pl.col(TARGET).is_not_null())

        # reference from ALL of 2025: there is no month_num to hold out for the ranking set
        tables = reference.fit_reference(inputs.movements)
        fit = reference.apply_reference(fit_feats, tables)

        # --- ranking side: features come from its own movement stream
        # the external data must be the SAME as on the training side; passed by field
        # name because a positional call silently drops a field whenever a new one is
        # added to Inputs (this happened once)
        rank_inputs = pipeline.Inputs(
            movements=pipeline.prepare_movements(pl.read_parquet(rank_path)),
            metar=inputs.metar,
            coords=inputs.coords,
            runways=inputs.runways,
            atfm_daily=inputs.atfm_daily,
        )
        print(f"ranking movements: {rank_inputs.movements.height:,}")
        rank_feats = reference.apply_reference(pipeline.build_features(rank_inputs), tables)

    cols = [c for c in pipeline.feature_columns(fit) if c in rank_feats.columns]
    missing = set(pipeline.feature_columns(fit)) - set(cols)
    if missing:
        # say so instead of dropping them silently: a feature that cannot be produced on
        # the ranking set means we have learned something about the setup
        print(
            f"WARNING: skipped {len(missing)} features that cannot be produced on the "
            f"ranking set: {sorted(missing)}"
        )
        print("  this is nearly always a bug: it is information the model learns during")
        print("  training and loses at prediction time. Look at it before going on.")
    cols = groups.select(cols, set(args.drop_groups))
    print(f"using {len(cols)} features")

    split = pipeline.Split(fit=fit, val=rank_feats, columns=cols)
    learners = tuple(s.strip() for s in args.learners.split(",") if s.strip())
    print(f"learners: {', '.join(learners)}  rounds: {args.rounds}  seeds: {args.seeds}")
    pred = pipeline.train_predict(
        split, cols, args.rounds,
        residual=not args.raw_target,
        seeds=tuple(range(1, args.seeds + 1)),
        learners=learners,
    )

    # --- submission file
    template = pl.read_parquet(template_path)
    pred_df = rank_feats.select("MVT_ID_mvt").with_columns(
        pl.Series(TARGET, np.asarray(pred, dtype=np.float64))
    )
    # if a row is in the template but not in the feature table, fill it with the median:
    # a file with missing rows is rejected and a submission is wasted
    missing_rows = template.join(pred_df, on="MVT_ID_mvt", how="anti")
    if missing_rows.height:
        filler = float(np.median(pred))
        print(
            f"WARNING: {missing_rows.height:,} template rows could not be predicted, "
            f"filled with the median ({filler:,.0f} s)"
        )
        pred_df = pl.concat([
            pred_df,
            missing_rows.select("MVT_ID_mvt").with_columns(pl.lit(filler).alias(TARGET)),
        ])
    pred_df = pred_df.join(template.select("MVT_ID_mvt"), on="MVT_ID_mvt", how="semi")

    out_dir.mkdir(parents=True, exist_ok=True)
    version = args.version or submission.next_version(out_dir, args.team)
    out_path = out_dir / f"{args.team}_v{version}.parquet"
    warnings = submission.write(pred_df, template, out_path)

    print(f"\nprediction summary: mean={np.mean(pred):,.0f} s  median={np.median(pred):,.0f}  "
          f"p99={np.percentile(pred, 99):,.0f}  min={np.min(pred):,.0f}")
    for w in warnings:
        print(f"  warning: {w}")
    print(f"\nwritten: {out_path}   ({time.time() - t0:,.0f} s)")
    # Not a bare mc command: the alias is `prc`, and mc silently turns an unknown alias
    # into a local directory copy that reports success. scripts/submit.py checks.
    print(f"upload:  python scripts/submit.py --team {args.team} --version {version}")


if __name__ == "__main__":
    main()
