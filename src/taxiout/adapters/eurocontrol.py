"""Downloads the indicators EUROCONTROL publishes openly.

Of the airport series available through the Aviation Intelligence Portal
(ansperformance.eu/data), the one that concerns us is **Taxi-Out Additional Time**.
These are the published values of the organiser's own indicator, and they serve two
purposes:

1. **Validation.** `domain/reference.py` reimplements ATXOT. Rather than assert that
   the reimplementation is right, we can compare it against the published reference
   times per airport and month.
2. **An independent measurement.** The indicator's share of flights without a valid
   reference carries, in winter, the flights dropped because of de-icing (ATXOT p.13
   step 1). That gives the METAR de-icing proxy something external to be checked
   against.

**Not usable as a feature:** the series is monthly and published about two months in
arrears, so July 2026, one of the two ranking months, is not covered. Validation only.

Licence and use: EUROCONTROL public release. See `docs/external_data.md`.

    python -m taxiout.adapters.eurocontrol --raw-dir D:/prc-taxiout-2026/00_raw
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import polars as pl

BASE = "https://www.eurocontrol.int/performance/data/download/xls/"
TAXIOUT_URL = BASE + "Taxi-Out_Additional_Time.xlsx"
SLOT_URL = BASE + "ATFM_Slot_Adherence.xlsx"
ARR_DELAY_URL = BASE + "Airport_Arrival_ATFM_Delay.xlsx"
# The portal can refuse requests that do not look like a browser.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

CHALLENGE_AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]


def download(url: str, dest: Path) -> Path:
    """Download once; leaves an existing file alone (these sets run to 100 MB)."""
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=900) as r, dest.open("wb") as f:  # noqa: S310
            f.write(r.read())
    return dest


def _read_data_sheet(path: Path) -> pl.DataFrame:
    """Read the DATA sheet; the YEAR and MONTH columns sometimes arrive as strings."""
    return pl.read_excel(path, sheet_name="DATA").with_columns(
        pl.col("YEAR").cast(pl.Int32, strict=False),
        pl.col("MONTH_NUM").cast(pl.Int32, strict=False),
    )


def official_taxiout(raw_dir: Path) -> pl.DataFrame:
    """Official reference and additional taxi-out time per airport and month (min/departure).

    `TF` is total flights and `VALID_FL` those with a computable additional time; the
    difference is mostly flights dropped for de-icing or missing data.
    """
    path = download(TAXIOUT_URL, raw_dir / "eurocontrol_taxiout_additional.xlsx")
    df = pl.read_excel(path, sheet_name="DATA")
    return (
        df.filter(pl.col("APT_ICAO").is_in(CHALLENGE_AIRPORTS) & (pl.col("TF") > 0))
        .select(
            apt=pl.col("APT_ICAO"),
            year=pl.col("YEAR"),
            month_num=pl.col("MONTH_NUM"),
            flights=pl.col("TF"),
            valid_flights=pl.col("VALID_FL"),
            reference_min=pl.col("TOTAL_REF_TIME_MIN") / pl.col("TOTAL_REF_NB_FL"),
            additional_min=pl.col("TOTAL_ADD_TIME_MIN") / pl.col("TOTAL_REF_NB_FL"),
            no_reference_share=1 - pl.col("VALID_FL") / pl.col("TF"),
        )
        .sort("apt", "year", "month_num")
    )


# --------------------------------------------------------------------------- daily ATFM

# EUROCONTROL/CFMU delay cause codes; only the populated ones are taken.
# Note: the 'D' (de-icing) column is **entirely empty**. De-icing is not coded as
# an ARRIVAL ATFM cause, which makes sense since it constrains departures. Our
# de-icing signal comes from METAR and is validated separately against this very
# indicator (docs/deicing_analysis.md).
DELAY_CAUSES = {
    "W": "weather",
    "C": "atc_kapasite",
    "G": "meydan_kapasite",
    "S": "atc_personel",
    "T": "atc_ekipman",
}


def daily_atfm(raw_dir: Path) -> pl.DataFrame:
    """ATFM state per airport and day.

    Combines two sources, both covering **both ranking months** (January and July
    2026) and every airport:

    - **ATFM Slot Adherence**: how many of the day's departures sat under an ATFM
      slot. This is the direct measurement of the downstream restrictions that
      Idris et al. (2002) name among their four factors; until now we proxied it
      only through the IOBT to LOBT drift.
    - **Airport Arrival ATFM Delay**: daily arrival ATFM delay, broken down by cause.

    **Causality caveat:** these are whole-day totals, so they include hours after
    a given departure, and they are published months in arrears. Legitimate for
    the retrospective model, **not for the causal one**; `groups.py` keeps them in
    their own family and the causal path never attaches them.
    """
    slot = _read_data_sheet(download(SLOT_URL, raw_dir / "eurocontrol_slot_adherence.xlsx"))
    arr = _read_data_sheet(download(ARR_DELAY_URL, raw_dir / "eurocontrol_arr_atfm_delay.xlsx"))

    num = lambda c: pl.col(c).cast(pl.Float64, strict=False)  # noqa: E731

    slot = (
        slot.filter(pl.col("APT_ICAO").is_in(CHALLENGE_AIRPORTS))
        .select(
            apt=pl.col("APT_ICAO"),
            day=pl.col("FLT_DATE").cast(pl.Date, strict=False),
            _dep=num("FLT_DEP_1"),
            _reg=num("FLT_DEP_REG_1"),
            _gec=num("FLT_DEP_OUT_LATE_1"),
            _erken=num("FLT_DEP_OUT_EARLY_1"),
        )
        .with_columns(
            atfm_regulated_share=(pl.col("_reg") / pl.col("_dep").replace(0, None))
            .cast(pl.Float32),
            atfm_slot_late_share=(pl.col("_gec") / pl.col("_reg").replace(0, None))
            .cast(pl.Float32),
            atfm_slot_early_share=(pl.col("_erken") / pl.col("_reg").replace(0, None))
            .cast(pl.Float32),
            daily_departures=pl.col("_dep").cast(pl.Float32),
        )
        .drop("_dep", "_reg", "_gec", "_erken")
    )

    cause_exprs = [
        (num(f"DLY_APT_ARR_{code}_1") / num("FLT_ARR_1").replace(0, None))
        .cast(pl.Float32)
        .alias(f"varis_gecikme_{name}_dk")
        for code, name in DELAY_CAUSES.items()
    ]
    arr = (
        arr.filter(pl.col("APT_ICAO").is_in(CHALLENGE_AIRPORTS))
        .select(
            pl.col("APT_ICAO").alias("apt"),
            pl.col("FLT_DATE").cast(pl.Date, strict=False).alias("day"),
            (num("DLY_APT_ARR_1") / num("FLT_ARR_1").replace(0, None))
            .cast(pl.Float32).alias("arr_atfm_delay_min"),
            num("FLT_ARR_1").cast(pl.Float32).alias("daily_arrivals"),
            *cause_exprs,
        )
    )
    return slot.join(arr, on=["apt", "day"], how="full", coalesce=True).sort("apt", "day")


def main() -> None:
    ap = argparse.ArgumentParser(description="EUROCONTROL open indicators")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--skip-daily", action="store_true",
                    help="skip the daily ATFM downloads (about 215 MB)")
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    df = official_taxiout(raw)
    out = raw / "eurocontrol_taxiout.parquet"
    df.write_parquet(out)
    print(f"{df.height:,} airport-months -> {out}")

    if not args.skip_daily:
        daily = daily_atfm(raw)
        dout = raw / "eurocontrol_atfm_daily.parquet"
        daily.write_parquet(dout)
        covered = daily.filter(pl.col("day").is_not_null())
        print(f"{daily.height:,} airport-days -> {dout}")
        print(f"  date range: {covered['day'].min()} .. {covered['day'].max()}")
    print(f"airports covered: {sorted(df['apt'].unique().to_list())}")
    eksik = set(CHALLENGE_AIRPORTS) - set(df["apt"].unique().to_list())
    if eksik:
        print(f"absent from the official indicator: {sorted(eksik)}")

if __name__ == "__main__":
    main()
