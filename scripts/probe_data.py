"""Day-zero data diagnosis.

Run this as soon as the data lands. The questions it answers (see docs/facts.md):

  Q02 / D06  Is AOBT_3_flt present in the ranking set, and if so, how good a predictor is it?
  D13        Does the identity MVT_TIME - BLOCK_TIME == TAXITIME hold in 2025?
  M14        Are the timestamps second-precision, or only HH:MM?
  D10        What is the NM flights match rate?
  --         Cold start: do the ranking set (stand, runway) combinations occur in training?
  --         What RMSE floor do the trivial baselines set?
  --         How wide is the departure delay distribution (irreducible uncertainty)?

Usage:
    python scripts/probe_data.py [--data-dir D:/prc-taxiout-2026]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import polars as pl

RAW_SUBDIR = "00_raw"
REPORT_PATH = Path("docs/data_probe_report.md")

TIME_COLS = ["MVT_TIME_UTC_mvt", "BLOCK_TIME_UTC_mvt", "SCHED_TIME_UTC_mvt"]
FLT_TIME_COLS = ["LOBT_flt", "IOBT_flt", "EOBT_1_flt", "ARVT_1_flt", "AOBT_3_flt", "ARVT_3_flt"]

_lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    _lines.append(text)


def section(title: str) -> None:
    say()
    say("## " + title)
    say()


def resolve_data_dir(cli_value: str | None) -> Path:
    for candidate in (cli_value, os.environ.get("TAXIOUT_DATA_DIR"), "D:/prc-taxiout-2026"):
        if candidate:
            return Path(candidate)
    raise SystemExit("could not determine the data directory")


def as_datetime(expr: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    """Cast a column to datetime if it came in as a string; leave it if already datetime."""
    if dtype == pl.String:
        return expr.str.to_datetime(strict=False)
    return expr


def load(paths: list[Path]) -> pl.LazyFrame:
    lf = pl.scan_parquet([str(p) for p in paths])
    schema = lf.collect_schema()
    names = schema.names()
    casts = [
        as_datetime(pl.col(c), schema[c]).alias(c)
        for c in TIME_COLS + FLT_TIME_COLS
        if c in names
    ]
    return lf.with_columns(casts) if casts else lf


def secs(a: str, b: str) -> pl.Expr:
    """a - b, in seconds."""
    return (pl.col(a) - pl.col(b)).dt.total_seconds()


def rmse(pred: pl.Expr, truth: pl.Expr) -> pl.Expr:
    return ((pred - truth) ** 2).mean().sqrt()


def fmt(value: object, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        # 4 places for shares (0..1), 1 place for magnitudes in seconds
        places = 4 if -1.0 <= value <= 1.0 else digits
        return format(value, ",." + str(places) + "f")
    if isinstance(value, int):
        return format(value, ",")
    return str(value)


def table(df: pl.DataFrame) -> None:
    if df.height == 0:
        say("_(empty)_")
        return
    cols = df.columns
    say("| " + " | ".join(cols) + " |")
    say("|" + "|".join("---" for _ in cols) + "|")
    for row in df.iter_rows():
        say("| " + " | ".join(fmt(v) for v in row) + " |")


# --------------------------------------------------------------------------- checks


def check_schema(train: pl.LazyFrame, rank: pl.LazyFrame, submit: pl.LazyFrame | None) -> None:
    section("1. Schema comparison (D05 / D06)")
    tcols = train.collect_schema().names()
    rcols = rank.collect_schema().names()
    missing = [c for c in tcols if c not in rcols]
    extra = [c for c in rcols if c not in tcols]
    say(
        "- training column count: **" + str(len(tcols)) + "**, ranking: **" + str(len(rcols)) + "**"
    )
    say("- columns absent from ranking: " + str(missing or "none"))
    say("- columns present only in ranking: " + str(extra or "none"))
    if submit is not None:
        say("- submitting.parquet columns: " + str(submit.collect_schema().names()))

    say()
    say("**Fill rate on the DEP rows of the ranking set** (0.0 = blanked out entirely):")
    dep = rank.filter(pl.col("PHASE_mvt") == "DEP")
    watch = set(TIME_COLS + FLT_TIME_COLS) | {
        "TAXITIME_SEC_mvt", "RUNWAY_mvt", "STAND_mvt", "FLIGHT_ID_mvt",
    }
    interesting = [c for c in rcols if c in watch]
    filled = dep.select(
        [pl.len().alias("n_dep")]
        + [pl.col(c).is_not_null().mean().alias(c) for c in interesting]
    ).collect()
    say()
    for name, value in zip(filled.columns, filled.row(0), strict=True):
        if name == "n_dep":
            say("- DEP row count: **" + fmt(value) + "**")
            continue
        note = ""
        if value == 0:
            note = "  <-- BLANKED"
        elif name == "AOBT_3_flt":
            note = "  <-- **FILLED, critical finding**"
        say("- `" + name + "`: " + format(value, ".4f") + note)


def check_identity(train: pl.LazyFrame) -> None:
    section("2. Taxi-out identity: MVT_TIME - BLOCK_TIME == TAXITIME ? (D13)")
    dep = train.filter(pl.col("PHASE_mvt") == "DEP")
    diff = secs("MVT_TIME_UTC_mvt", "BLOCK_TIME_UTC_mvt") - pl.col("TAXITIME_SEC_mvt")
    res = dep.select(
        n=pl.len(),
        n_complete=(
            pl.col("MVT_TIME_UTC_mvt").is_not_null()
            & pl.col("BLOCK_TIME_UTC_mvt").is_not_null()
            & pl.col("TAXITIME_SEC_mvt").is_not_null()
        ).sum(),
        exact_match=(diff.abs() < 1).mean(),
        max_abs_diff=diff.abs().max(),
    ).collect()
    n, n_complete, match, maxdiff = res.row(0)
    say("- DEP rows: **" + fmt(n) + "**, rows with all three filled: **" + fmt(n_complete) + "**")
    say("- share where the identity holds within 1 s: **" + fmt(match, 6) + "**")
    say("- largest absolute deviation: **" + fmt(maxdiff) + " s**")
    say()
    say("Reading: a share of 1.0 means TAXITIME is derived and the timestamps are internally "
        "consistent; anything below 1.0 means the difference is an independent measurement "
        "error, and it sets the noise floor for the queue features.")


def check_precision(train: pl.LazyFrame) -> None:
    section("3. Timestamp precision (M14)")
    dep = train.filter(pl.col("PHASE_mvt") == "DEP")
    df = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            mvt_second_is_zero=(pl.col("MVT_TIME_UTC_mvt").dt.second() == 0).mean(),
            block_second_is_zero=(pl.col("BLOCK_TIME_UTC_mvt").dt.second() == 0).mean(),
        )
        .sort("ADEP_mvt")
        .collect()
    )
    table(df)
    say()
    say("An airport whose share is near 1.0 has data at **HH:MM** precision: taxi-out there "
        "carries +-60 s of floor noise, so the reachable RMSE lower bound for that airport is "
        "higher.")


def check_nm_match(train: pl.LazyFrame, rank: pl.LazyFrame) -> None:
    section("4. Network Manager match rate (D10)")
    for label, lf in (("training 2025", train), ("ranking 2026", rank)):
        cols = lf.collect_schema().names()
        aggs = {"n": pl.len()}
        if "FLIGHT_ID_mvt" in cols:
            aggs["flight_id_filled"] = pl.col("FLIGHT_ID_mvt").is_not_null().mean()
        if "AOBT_3_flt" in cols:
            aggs["aobt3_filled"] = pl.col("AOBT_3_flt").is_not_null().mean()
        df = (
            lf.filter(pl.col("PHASE_mvt") == "DEP")
            .group_by("ADEP_mvt")
            .agg(**aggs)
            .sort("ADEP_mvt")
            .collect()
        )
        say("**" + label + "**")
        say()
        table(df)
        say()


def check_aobt_strength(train: pl.LazyFrame) -> None:
    section("5. CRITICAL: how good a predictor is AOBT_3_flt? (Q02)")
    if "AOBT_3_flt" not in train.collect_schema().names():
        say("`AOBT_3_flt` is not in the training set, check skipped.")
        return
    say("Naive predictor: `taxi_out = MVT_TIME_UTC_mvt - AOBT_3_flt`")
    say()
    dep = train.filter(
        (pl.col("PHASE_mvt") == "DEP")
        & pl.col("TAXITIME_SEC_mvt").is_not_null()
        & pl.col("AOBT_3_flt").is_not_null()
        & pl.col("MVT_TIME_UTC_mvt").is_not_null()
    ).with_columns(naive=secs("MVT_TIME_UTC_mvt", "AOBT_3_flt"))

    err = pl.col("naive") - pl.col("TAXITIME_SEC_mvt")
    overall = dep.select(
        n=pl.len(),
        rmse=rmse(pl.col("naive"), pl.col("TAXITIME_SEC_mvt")),
        mae=err.abs().mean(),
        bias=err.mean(),
        median_abs_error=err.abs().median(),
    ).collect()
    table(overall)
    say()
    per_apt = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            rmse=rmse(pl.col("naive"), pl.col("TAXITIME_SEC_mvt")),
            bias=err.mean(),
        )
        .sort("rmse")
        .collect()
    )
    table(per_apt)
    say()
    say("**How to read this.** If this RMSE is low (say <60 s) the competition is mostly a "
        "'reconcile the NM block time with the APDF block time and fill in the unmatched rows' "
        "problem, and the whole architecture follows from that. If it is high (say >200 s) then "
        "AOBT_3 is only a strong feature, not the solution. The coverage share (n / total DEP) "
        "matters at least as much as the RMSE: the rows it does not cover need a separate "
        "model.")


def check_target(train: pl.LazyFrame) -> None:
    section("6. Target distribution")
    dep = train.filter((pl.col("PHASE_mvt") == "DEP") & pl.col("TAXITIME_SEC_mvt").is_not_null())
    t = pl.col("TAXITIME_SEC_mvt")
    df = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            mean=t.mean(),
            std=t.std(),
            p10=t.quantile(0.10),
            p50=t.median(),
            p99=t.quantile(0.99),
            over_120min_share=(t > 7200).mean(),
            negative_share=(t < 0).mean(),
        )
        .sort("ADEP_mvt")
        .collect()
    )
    table(df)
    say()
    say("`over_120min_share` is the share above the official PRC filter (M08); "
        "`negative_share` marks a data error. Both are the tail that RMSE punishes hardest: "
        "they call for a **modelling** decision, not clipping.")

    monthly = (
        dep.with_columns(month_num=pl.col("MVT_TIME_UTC_mvt").dt.month())
        .group_by("month_num")
        .agg(n=pl.len(), mean=t.mean(), std=t.std())
        .sort("month_num")
        .collect()
    )
    say()
    say("**By month (watch the January and July rows: they are the two ranking months):**")
    say()
    table(monthly)


def check_baselines(train: pl.LazyFrame, rank: pl.LazyFrame) -> None:
    section("7. Baselines and cold start")
    dep = train.filter(
        (pl.col("PHASE_mvt") == "DEP") & pl.col("TAXITIME_SEC_mvt").is_not_null()
    ).select("ADEP_mvt", "STAND_mvt", "RUNWAY_mvt", "TAXITIME_SEC_mvt", "MVT_TIME_UTC_mvt")

    # January and July are held out and the remaining 10 months are used to fit:
    # this imitates the seasonal setup of the ranking set.
    month_num = pl.col("MVT_TIME_UTC_mvt").dt.month()
    fit = dep.filter(~month_num.is_in([1, 7]))
    val = dep.filter(month_num.is_in([1, 7]))

    global_mean = fit.select(pl.col("TAXITIME_SEC_mvt").mean()).collect().item()
    apt_mean = fit.group_by("ADEP_mvt").agg(pl.col("TAXITIME_SEC_mvt").mean().alias("apt_mean"))
    combo = fit.group_by("ADEP_mvt", "STAND_mvt", "RUNWAY_mvt").agg(
        pl.col("TAXITIME_SEC_mvt").mean().alias("combo_mean"),
        pl.col("TAXITIME_SEC_mvt").quantile(0.10).alias("combo_p10"),
        pl.len().alias("combo_n"),
    )

    scored = (
        val.join(apt_mean, on="ADEP_mvt", how="left")
        .join(combo, on=["ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"], how="left")
        .with_columns(
            global_pred=pl.lit(global_mean),
            combo_filled=pl.col("combo_mean").fill_null(pl.col("apt_mean")),
        )
    )
    out = scored.select(
        n_validation=pl.len(),
        combo_coverage=pl.col("combo_mean").is_not_null().mean(),
        rmse_global_mean=rmse(pl.col("global_pred"), pl.col("TAXITIME_SEC_mvt")),
        rmse_airport_mean=rmse(pl.col("apt_mean"), pl.col("TAXITIME_SEC_mvt")),
        rmse_combo_mean=rmse(pl.col("combo_filled"), pl.col("TAXITIME_SEC_mvt")),
    ).collect()
    table(out)
    say()
    say("`rmse_combo_mean` is the expected level of our first real submission. Everything we "
        "put on top of it is the queue / congestion / weather component.")

    rank_dep = rank.filter(pl.col("PHASE_mvt") == "DEP").select(
        "ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"
    )
    cold = (
        rank_dep.join(combo, on=["ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"], how="left")
        .select(
            n=pl.len(),
            seen_combo_share=pl.col("combo_n").is_not_null().mean(),
            stand_null_share=pl.col("STAND_mvt").is_null().mean(),
            runway_null_share=pl.col("RUNWAY_mvt").is_null().mean(),
        )
        .collect()
    )
    say()
    say("**Share of ranking set combinations never seen in training (cold start risk):**")
    say()
    table(cold)


def check_schedule_handle(train: pl.LazyFrame) -> None:
    section("8. Second handle: scheduled block time (SCHED_TIME)")
    say("Identity: `MVT_TIME - SCHED_TIME = taxi_out + departure_delay`.")
    say("`SCHED_TIME_UTC_mvt` is not blanked out in the ranking set (D05), so this is a")
    say("legitimate feature too. What it is worth depends entirely on how predictable the")
    say("**departure delay** is: a narrow delay_sec distribution nearly hands us the target,")
    say("a wide one leaves us only an upper bound.")
    say()
    dep = train.filter(
        (pl.col("PHASE_mvt") == "DEP")
        & pl.col("TAXITIME_SEC_mvt").is_not_null()
        & pl.col("SCHED_TIME_UTC_mvt").is_not_null()
        & pl.col("BLOCK_TIME_UTC_mvt").is_not_null()
    ).with_columns(
        delay_sec=secs("BLOCK_TIME_UTC_mvt", "SCHED_TIME_UTC_mvt"),
        sched_naive=secs("MVT_TIME_UTC_mvt", "SCHED_TIME_UTC_mvt"),
    )
    g = pl.col("delay_sec")
    say("**Departure delay (actual block - scheduled block), seconds:**")
    say()
    table(
        dep.select(
            n=pl.len(),
            mean=g.mean(),
            std=g.std(),
            p10=g.quantile(0.10),
            p50=g.median(),
            p90=g.quantile(0.90),
            early_share=(g < 0).mean(),
        ).collect()
    )
    say()
    say("**The `MVT - SCHED` naive predictor (it treats the delay as zero):**")
    say()
    table(
        dep.select(
            rmse=rmse(pl.col("sched_naive"), pl.col("TAXITIME_SEC_mvt")),
            bias=(pl.col("sched_naive") - pl.col("TAXITIME_SEC_mvt")).mean(),
        ).collect()
    )
    say()
    say("Compare with the AOBT_3 naive predictor in section 5. Which of the two handles is")
    say("narrower, and how much is left once both are used, is the architecture decision. The")
    say("standard deviation of the delay may be **most of the irreducible uncertainty** in")
    say("this problem.")


# --------------------------------------------------------------------------- entry point


def main() -> int:
    ap = argparse.ArgumentParser(description="PRC 2026 taxi-out data diagnosis")
    ap.add_argument("--data-dir", default=None, help="parent directory of the raw parquet files")
    args = ap.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    raw = data_dir / RAW_SUBDIR
    train_files = sorted(raw.glob("training_*.parquet"))
    rank_file = raw / "ranking.parquet"
    submit_file = raw / "submitting.parquet"

    if not train_files or not rank_file.exists():
        print("raw data not found: " + str(raw))
        print("expected: training_2025-*.parquet (12 files), ranking.parquet, submitting.parquet")
        print("download it here once the team is approved and the bucket keys arrive, then re-run.")
        return 1

    say("# Data Diagnosis Report")
    say()
    say("Source: `" + str(raw) + "` - training files: " + str(len(train_files)))

    train = load(train_files)
    rank = load([rank_file])
    submit = load([submit_file]) if submit_file.exists() else None

    check_schema(train, rank, submit)
    check_identity(train)
    check_precision(train)
    check_nm_match(train, rank)
    check_aobt_strength(train)
    check_target(train)
    check_baselines(train, rank)
    check_schedule_handle(train)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print("\nreport written: " + str(REPORT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
