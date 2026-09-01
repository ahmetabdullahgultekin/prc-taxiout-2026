"""Builds the feature tables once and keeps them on disk for later runs.

Every experiment rebuilds the same features from the same raw files, which is wasted
work as soon as more than one question is being asked in an evening. The cache holds the
fitted and holdout frames and the column list, so a sweep over learners or feature
families starts in seconds.

The cache is derived data and therefore disposable. Delete the directory to force a
rebuild, and do delete it whenever a feature changes: a stale cache is the kind of thing
that produces a plausible number for the wrong model. `--check` reports what is there.

    python scripts/cache_features.py
    python scripts/cache_features.py --check
"""

from __future__ import annotations

import argparse
import time

import polars as pl

from taxiout import config
from taxiout.application import pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="build and cache the feature tables")
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--causal", action="store_true", help="build the causal variant")
    ap.add_argument("--check", action="store_true", help="report on the cache and exit")
    args = ap.parse_args()

    cache = config.cache(args.data_dir)
    if args.check:
        if not (cache / "columns.parquet").exists():
            raise SystemExit(f"no cache in {cache}")
        cols = pl.read_parquet(cache / "columns.parquet")["column"].to_list()
        for name in ("fit", "val"):
            frame = pl.scan_parquet(cache / f"{name}.parquet")
            print(f"  {name}: {frame.select(pl.len()).collect().item():,} rows")
        print(f"  {len(cols)} feature columns")
        print(f"  built {time.ctime((cache / 'columns.parquet').stat().st_mtime)}")
        return

    t0 = time.time()
    inputs = pipeline.load_inputs(config.raw(args.data_dir))
    feats = pipeline.build_features(inputs, causal=args.causal)
    split = pipeline.seasonal_split(feats, inputs.movements)
    del feats

    cache.mkdir(parents=True, exist_ok=True)
    split.fit.write_parquet(cache / "fit.parquet")
    split.val.write_parquet(cache / "val.parquet")
    pl.DataFrame({"column": split.columns}).write_parquet(cache / "columns.parquet")
    print(f"cached {len(split.columns)} features, fit {split.fit.height:,} / "
          f"val {split.val.height:,}, to {cache}  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
