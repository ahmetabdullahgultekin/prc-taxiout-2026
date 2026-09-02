"""Builds the feature tables once and keeps them on disk for later runs.

Every experiment and every submission rebuilds the same features from the same raw
files, which is minutes of wasted work each time and, in a competition decided on the
leaderboard, the thing that limits how many questions get answered per evening.

`--ranking` also builds the ranking-set features and the reference table applied to
both, which is what turns a submission from a three-hour job into a training run.

The cache carries a fingerprint of the code that produced it and refuses to load when
that code has moved; see `taxiout.application.cache`. A cache that is merely old is
harmless, one that is stale answers plausibly for a model that no longer exists.

    python scripts/cache_features.py --ranking
    python scripts/cache_features.py --check
"""

from __future__ import annotations

import argparse
import time

import polars as pl

from taxiout import config
from taxiout.application import cache, pipeline
from taxiout.domain import reference


def main() -> None:
    ap = argparse.ArgumentParser(description="build and cache the feature tables")
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--causal", action="store_true", help="build the causal variant")
    ap.add_argument("--ranking", action="store_true",
                    help="also build the ranking set features, for submissions")
    ap.add_argument("--check", action="store_true", help="report on the cache and exit")
    args = ap.parse_args()

    directory = config.cache(args.data_dir)
    if args.check:
        if not (directory / "columns.parquet").exists():
            raise SystemExit(f"no cache in {directory}")
        cols = pl.read_parquet(directory / "columns.parquet")["column"].to_list()
        for name in ("fit", "val", "fit_full", "rank"):
            path = directory / f"{name}.parquet"
            if path.exists():
                rows = pl.scan_parquet(path).select(pl.len()).collect().item()
                print(f"  {name}: {rows:,} rows")
            else:
                print(f"  {name}: absent")
        print(f"  {len(cols)} feature columns")
        changed = cache.stale(directory)
        print("  fingerprint: matches the current code" if not changed
              else f"  STALE, {len(changed)} source files differ: {changed[:5]}")
        return

    t0 = time.time()
    raw = config.raw(args.data_dir)
    inputs = pipeline.load_inputs(raw)
    feats = pipeline.build_features(inputs, causal=args.causal)
    split = pipeline.seasonal_split(feats, inputs.movements)

    rank = fit_full = None
    if args.ranking:
        # The reference comes from ALL of 2025: the ranking set has no taxi times of its
        # own to fit one from. The congestion features are the opposite case, computed
        # from the ranking set's own movement stream, because January and July 2026 have
        # their own traffic.
        tables = reference.fit_reference(inputs.movements)
        rank_inputs = pipeline.Inputs(
            movements=pipeline.prepare_movements(pl.read_parquet(raw / "ranking.parquet")),
            metar=inputs.metar,
            coords=inputs.coords,
            runways=inputs.runways,
            atfm_daily=inputs.atfm_daily,
        )
        rank = reference.apply_reference(
            pipeline.build_features(rank_inputs, causal=args.causal), tables
        )
        # The training side of a submission uses the SAME all-2025 reference, which is
        # not the one in `split.fit`: that one is fitted without the holdout months so
        # that validation is honest. Mixing the two would shift every prediction by the
        # difference between the two baselines and nothing would say so.
        fit_full = reference.apply_reference(
            feats.filter(pl.col(pipeline.TARGET).is_not_null()), tables
        )
        del rank_inputs
    del feats, inputs

    cache.write(directory, split.fit, split.val, split.columns, rank, fit_full)
    extra = f", rank {rank.height:,}" if rank is not None else ""
    print(f"cached {len(split.columns)} features, fit {split.fit.height:,} / "
          f"val {split.val.height:,}{extra}, to {directory}  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
