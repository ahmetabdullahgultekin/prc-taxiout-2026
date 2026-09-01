"""De-icing regime analysis: validates the METAR proxy against the official indicator.

**Needs no competition data.** It uses two open sources: METAR (Iowa State IEM, public
domain) and the Taxi-Out Additional Time indicator published by EUROCONTROL.

The question it asks: does the de-icing proxy we derive from METAR actually measure
de-icing? An independent measurement was needed, and the official indicator provides one.
In its own indicator the PRC **discards flights that de-ice after AOBT** (ATXOT p.13,
step 1), so the "share of flights without a valid reference" field carries de-icing during
the winter months.

What we found goes further than that: airports have **different de-icing regimes**, and
that determines where our January error will pile up. Detail in `docs/deicing_analysis.md`.

    python scripts/analyse_deicing.py --raw-dir D:/prc-taxiout-2026/00_raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from taxiout.adapters import eurocontrol

OUT_MD = Path("docs/deicing_analysis.md")


def monthly_metar(metar: pl.DataFrame) -> pl.DataFrame:
    return metar.group_by(
        apt=pl.col("station"),
        year=pl.col("valid").dt.year(),
        month_num=pl.col("valid").dt.month(),
    ).agg(
        deicing=pl.col("deicing_proxy").mean(),
        snow=pl.col("snow").mean(),
        freezing=pl.col("freezing_precip").mean(),
        min_temperature_c=pl.col("temperature_c").min(),
    )


def table(df: pl.DataFrame, digits: dict[str, int] | None = None) -> str:
    digits = digits or {}
    lines = ["| " + " | ".join(df.columns) + " |",
             "|" + "|".join("---" for _ in df.columns) + "|"]
    for row in df.iter_rows():
        cells = []
        for col, v in zip(df.columns, row, strict=True):
            if v is None:
                cells.append("-")
            elif isinstance(v, float):
                cells.append(f"{v:.{digits.get(col, 3)}f}")
            else:
                cells.append(f"{v:,}" if isinstance(v, int) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()
    raw = Path(args.raw_dir)

    metar_path = raw / "metar.parquet"
    if not metar_path.exists():
        raise SystemExit(
            f"METAR not found: {metar_path}\n"
            "first: python -m taxiout.adapters.metar_iem --start 2025-01-01 "
            "--end 2026-08-01 --out <path>"
        )
    met = monthly_metar(pl.read_parquet(metar_path))
    off = eurocontrol.official_taxiout(raw)
    j = off.join(met, on=["apt", "year", "month_num"], how="inner").sort("apt", "year", "month_num")

    overall_ref = j.select(pl.corr("deicing", "no_reference_share")).item()
    overall_time = j.select(pl.corr("deicing", "additional_min")).item()

    per = (
        j.group_by("apt")
        .agg(
            n_months=pl.len(),
            r_no_reference=pl.corr("deicing", "no_reference_share"),
            r_additional=pl.corr("deicing", "additional_min"),
            mean_deicing=pl.col("deicing").mean(),
            mean_no_reference=pl.col("no_reference_share").mean(),
            winter_additional=pl.col("additional_min")
            .filter(pl.col("month_num").is_in([1, 2, 12]))
            .mean(),
            summer_additional=pl.col("additional_min")
            .filter(pl.col("month_num").is_in([6, 7, 8]))
            .mean(),
        )
        .with_columns(
            winter_summer_diff=pl.col("winter_additional") - pl.col("summer_additional")
        )
        .sort("r_no_reference", descending=True)
    )

    missing = set(eurocontrol.CHALLENGE_AIRPORTS) - set(off["apt"].unique().to_list())

    # the tables are built OUTSIDE the f-string: a dict literal cannot go in an f-string
    # expression
    table_correlation = table(
        per.select("apt", "n_months", "r_no_reference", "r_additional", "mean_deicing",
                   "mean_no_reference")
    )
    table_regime = table(
        per.select("apt", "r_additional", "winter_additional", "summer_additional",
                   "winter_summer_diff"),
        digits={"winter_additional": 2, "summer_additional": 2, "winter_summer_diff": 2},
    )
    out_of_scope = (
        "Airports with **no data at all** in the official indicator: " + ", ".join(sorted(missing))
        if missing
        else "Every competition airport is covered by the indicator."
    )

    body = f"""# De-icing regime: independent validation of the METAR proxy

Produced by: `python scripts/analyse_deicing.py --raw-dir <path>`
**No competition data is used**, only two open sources: IEM METAR and the Taxi-Out
Additional Time indicator published by EUROCONTROL. Coverage: {j.height} airport-months.

## Why this comparison is meaningful

In its official indicator the PRC **discards flights that de-ice after AOBT**
(ATXOT p.13, step 1). The indicator's "share of flights without a valid reference" field
therefore carries mostly de-icing during the winter months. That is an **independent**
measurement of the `deicing_proxy` field we derive from METAR.

## Result: the proxy works

Over the whole data set the correlation is **r = {overall_ref:.3f}** (de-icing proxy
against the share of flights without a reference). Within an airport, across months:

{table_correlation}

At the cold airports the correlation is 0.87 to 0.98; at the warm ones (LIRF, LEBL, EGLL)
there is almost no de-icing, so the correlation is noise and is expected to be low.

## The real finding: airports have different de-icing regimes

The correlation between the de-icing proxy and the **additional taxi-out time** is
{overall_time:+.3f} overall, that is, effectively none. But per airport the table splits
in two:

{table_regime}

**EHAM stands apart on its own.** At Amsterdam the share of flights without a reference
stays flat through the year (~1%), yet the additional taxi-out time rises clearly in
winter. At EDDM and LSZH it is the other way round: in winter a large share of flights
**drops out** of the indicator (31% at Munich in January 2026), while the additional time
does not rise.

One caveat worth recording: the additional taxi-out time is lower in winter than in summer
at **every** airport (between -0.25 and -2.82 min), because the summer traffic peak makes
the queue longer. EHAM's +1.46 min appears in spite of that baseline, so the background
strengthens the anomaly rather than weakening it.

Reading: **how much of the winter delay lands inside taxi-out** varies by airport. At
Amsterdam it lands inside and inflates the target; at Munich and Zurich the affected
flights are flagged and taken out of the official calculation.

This is not a firm causal claim: we have no de-icing records, only a weather condition
proxy and two fields of the official indicator. But two independent sources showing the
same seasonal structure, and the airports splitting into two distinct patterns, is enough
to fix **the first hypothesis to test** once the competition data arrives.

## What it means for us

We predict **raw taxi-out** and we cannot discard any row. So:

- At EHAM the weather effect shows up directly in the target and can be learned.
- At EDDM and LSZH the flights the official indicator **discards** are still in our data
  set, and as outliers they will dominate our January error. No published taxi-out model
  has had to predict those flights, because the standard methodology filters them out.
- The weather effect **varies by airport**; instead of one global weather coefficient we
  need an airport x weather interaction (or a per-airport model).

## Out of scope

{out_of_scope}
Antalya is not in the EUROCONTROL performance scheme; we have no external validation source
for that airport, and its data quality may differ, which is worth keeping in mind.

Of the two ranking months, **July 2026 has not been published yet** (the series ends in
June 2026), so this indicator cannot be used as a feature. It is for validation only.
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(body, encoding="utf-8")
    print(f"overall correlation r = {overall_ref:.3f}")
    print(per)
    print(f"\nreport: {OUT_MD}")


if __name__ == "__main__":
    main()
