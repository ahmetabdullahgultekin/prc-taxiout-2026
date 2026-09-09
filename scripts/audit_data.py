"""Data-quality audit of the categorical fields, training against ranking.

The BTK playbook's largest easy win was lowercase-and-trim on the text categories: train
and test arrived in different formats, so a raw category became noise on the test side.
That check was never run here, and the categorical fields are exactly where this
competition lives, 1,899 stands and a hashed operator among them.

Looks for, in order of how quietly each one hurts:

  1. case and whitespace variants of the same value
  2. values present on one side and not the other
  3. values so rare they cannot be learned
  4. the same value written differently across the two sets
"""

import argparse
import glob

import polars as pl

from taxiout import config

pl.Config.set_tbl_rows(25)
pl.Config.set_fmt_str_lengths(40)

_ap = argparse.ArgumentParser(description="data quality audit of the categorical fields")
_ap.add_argument("--data-dir", default=str(config.DATA_DIR))
RAW = config.raw(_ap.parse_args().data_dir)
APT = pl.when(pl.col("PHASE_mvt") == "DEP").then(pl.col("ADEP_mvt")).otherwise(pl.col("ADES_mvt"))

tr = pl.concat([pl.read_parquet(f) for f in sorted(glob.glob(str(RAW / "training_*.parquet")))],
               how="vertical_relaxed").with_columns(apt_mvt=APT)
rk = pl.read_parquet(RAW / "ranking.parquet").with_columns(apt_mvt=APT)
trd = tr.filter(pl.col("PHASE_mvt") == "DEP")
rkd = rk.filter(pl.col("PHASE_mvt") == "DEP")

FIELDS = ["apt_mvt", "STAND_mvt", "RUNWAY_mvt", "AIRCRAFT_TYPE_mvt", "AIRCRAFT_TYPE_flt",
          "WK_TBL_CAT_flt", "MARKET_SEGMENT_flt", "FLIGHT_TYPE_flt", "FLIGHT_RULE_mvt"]
FIELDS = [f for f in FIELDS if f in trd.columns]

print("=" * 96)
print("1. CASE AND WHITESPACE VARIANTS OF THE SAME VALUE")
print("=" * 96)
found_any = False
for c in FIELDS:
    s = trd[c].drop_nulls()
    raw_n = s.n_unique()
    norm_n = s.str.strip_chars().str.to_uppercase().n_unique()
    flag = "  <-- DIRTY" if raw_n != norm_n else ""
    if raw_n != norm_n:
        found_any = True
        variants = (
            trd.select(c).drop_nulls()
            .with_columns(_k=pl.col(c).str.strip_chars().str.to_uppercase())
            .group_by("_k").agg(forms=pl.col(c).unique())
            .filter(pl.col("forms").list.len() > 1)
        )
        print(f"  {c:<24} {raw_n:>6} raw -> {norm_n:>6} normalised{flag}")
        print(f"    examples: {variants['forms'].to_list()[:5]}")
    else:
        print(f"  {c:<24} {raw_n:>6} raw -> {norm_n:>6} normalised   clean")
if not found_any:
    print("\n  No case or whitespace variants anywhere. The feed is already normalised.")

print("\n" + "=" * 96)
print("2. VALUES IN ONE SET AND NOT THE OTHER")
print("=" * 96)
for c in FIELDS:
    a = set(trd[c].drop_nulls().unique().to_list())
    b = set(rkd[c].drop_nulls().unique().to_list())
    only_rank = b - a
    rows = rkd.filter(pl.col(c).is_in(list(only_rank))).height if only_rank else 0
    print(f"  {c:<24} train {len(a):>6}  rank {len(b):>6}  "
          f"unseen in training {len(only_rank):>4} ({rows / max(rkd.height, 1):.4%} of rows)")
    if only_rank and len(only_rank) <= 8:
        print(f"    {sorted(only_rank)}")

print("\n" + "=" * 96)
print("3. VALUES TOO RARE TO LEARN (training departures)")
print("=" * 96)
for c in FIELDS:
    counts = trd[c].drop_nulls().value_counts()
    n = counts.height
    for threshold in (1, 5, 20):
        rare = counts.filter(pl.col("count") <= threshold)
        share = rare["count"].sum() / trd.height
        if threshold == 1:
            print(f"  {c:<24} {n:>6} values | seen once: {rare.height:>5} "
                  f"({share:.4%} of rows)", end="")
        elif threshold == 20:
            print(f" | <=20: {rare.height:>5} ({share:.3%})")

print("\n" + "=" * 96)
print("4. THE TARGET AND THE TIMES: IMPOSSIBLE VALUES")
print("=" * 96)
t = trd["TAXITIME_SEC_mvt"]
print(f"  taxi-out negative or zero : {(t <= 0).sum():,}")
print(f"  above 2 hours             : {(t > 7200).sum():,} ({(t > 7200).sum()/trd.height:.4%})")
print(f"  above 6 hours             : {(t > 21600).sum():,}")
naive = (trd.filter(pl.col("AOBT_3_flt").is_not_null())
            .with_columns(n=(pl.col("MVT_TIME_UTC_mvt") - pl.col("AOBT_3_flt")).dt.total_seconds()))
print(f"  network estimate negative : {(naive['n'] < 0).sum():,} "
      f"({(naive['n'] < 0).sum()/naive.height:.3%})")
print(f"  network estimate > 4 h    : {(naive['n'] > 14400).sum():,}")

print("\n  do the two disagree on the extreme rows?")
big = naive.filter(pl.col("TAXITIME_SEC_mvt") > 7200)
plausible = big.filter(pl.col("n").is_between(0, 7200))
print(f"    {big.height:,} departures above 2 h have a network match")
print(f"    {plausible.height:,} of them ({plausible.height / max(big.height,1):.1%}) have a "
      f"plausible network time, so the airport feed's block time is the wrong one")

print("\n" + "=" * 96)
print("5. THE SAME FLIGHT TWICE?")
print("=" * 96)
for name, d in (("train", trd), ("rank", rkd)):
    dup = (d.group_by(["apt_mvt", "MVT_TIME_UTC_mvt", "STAND_mvt", "RUNWAY_mvt"])
             .agg(n=pl.len()).filter(pl.col("n") > 1))
    print(f"  {name}: {dup.height:,} groups share airport, take-off second, stand and runway"
          f" (largest {dup['n'].max() if dup.height else 0})")
