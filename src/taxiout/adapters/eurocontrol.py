"""EUROCONTROL'un yayimladigi resmi gostergeleri indirir.

Aviation Intelligence Portal (ansperformance.eu/data) uzerinden acik indirilebilen
havalimani serilerinden bizi ilgilendiren: **Taxi-Out Additional Time**. Bu, yarismayi
duzenleyen kurumun kendi gostergesinin yayimlanmis degerleridir; iki isi gorur:

1. **Dogrulama.** `domain/reference.py` ATXOT'u yeniden uyguluyor. Yeniden uygulamanin
   dogru oldugunu iddia etmek yerine, havalimani-ay bazinda yayimlanmis referans
   suresiyle karsilastirip gosterebiliriz.
2. **Bagimsiz olcum.** Gostergenin "gecerli referansi olmayan ucus orani" alani, kis
   aylarinda de-icing nedeniyle hesaptan dusen ucuslari tasir (ATXOT s.13 adim 1).
   METAR'dan turettigimiz de-icing vekilini buna karsi dogrulayabiliriz.

**Ozellik olarak kullanilamaz:** seri aylik ve yayimi ~2 ay gecikmeli; siralama
aylarindan Temmuz 2026 henuz yayimlanmamis. Yalnizca dogrulama icin.

Lisans/kullanim: EUROCONTROL kamuya acik yayin. `docs/external_data.md`'de belgeli.

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
# Portal tarayici disi istekleri reddedebiliyor
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

CHALLENGE_AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]


def download(url: str, dest: Path) -> Path:
    """Bir kez indirir; dosya varsa dokunmaz (setler 100 MB mertebesinde)."""
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=900) as r, dest.open("wb") as f:  # noqa: S310
            f.write(r.read())
    return dest


def _read_data_sheet(path: Path) -> pl.DataFrame:
    """DATA sayfasini okur; YEAR/MONTH kolonlari bazen string geliyor."""
    return pl.read_excel(path, sheet_name="DATA").with_columns(
        pl.col("YEAR").cast(pl.Int32, strict=False),
        pl.col("MONTH_NUM").cast(pl.Int32, strict=False),
    )


def official_taxiout(raw_dir: Path) -> pl.DataFrame:
    """Havalimani-ay bazinda resmi referans ve ek taxi-out suresi (dakika/kalkis).

    `TF` toplam ucus, `VALID_FL` gecerli ek suresi hesaplanabilen ucus sayisidir;
    ikisinin farki agirlikli olarak de-icing ve eksik veri nedeniyle dusen ucuslardir.
    """
    path = download(TAXIOUT_URL, raw_dir / "eurocontrol_taxiout_additional.xlsx")
    df = pl.read_excel(path, sheet_name="DATA")
    return (
        df.filter(pl.col("APT_ICAO").is_in(CHALLENGE_AIRPORTS) & (pl.col("TF") > 0))
        .select(
            apt=pl.col("APT_ICAO"),
            yil=pl.col("YEAR"),
            ay=pl.col("MONTH_NUM"),
            ucus=pl.col("TF"),
            gecerli_ucus=pl.col("VALID_FL"),
            referans_dk=pl.col("TOTAL_REF_TIME_MIN") / pl.col("TOTAL_REF_NB_FL"),
            ek_sure_dk=pl.col("TOTAL_ADD_TIME_MIN") / pl.col("TOTAL_REF_NB_FL"),
            referanssiz_oran=1 - pl.col("VALID_FL") / pl.col("TF"),
        )
        .sort("apt", "yil", "ay")
    )


# --------------------------------------------------------------------------- gunluk ATFM

# EUROCONTROL/CFMU gecikme neden kodlari. Yalnizca dolu olanlari aliyoruz.
# Not: 'D' (de-icing) kolonu **tamamen bos** — de-icing bir VARIS ATFM nedeni olarak
# kodlanmiyor, ki mantikli: kalkis tarafi bir sorun. De-icing sinyalimiz METAR'dan
# geliyor ve resmi gostergeye karsi ayrica dogrulandi (docs/deicing_analysis.md).
DELAY_CAUSES = {
    "W": "hava",
    "C": "atc_kapasite",
    "G": "meydan_kapasite",
    "S": "atc_personel",
    "T": "atc_ekipman",
}


def daily_atfm(raw_dir: Path) -> pl.DataFrame:
    """Havalimani-gun bazinda ATFM durumu.

    Iki kaynagi birlestirir; ikisi de **her iki siralama ayini** (Ocak ve Temmuz 2026)
    kapsiyor ve 11 havalimaninin tamamini iceriyor:

    - **ATFM Slot Adherence**: gunun kalkislarindan kaci ATFM slotu altindaydi. Idris ve
      ark.'nin (2002) dort ana faktorunden "asagi-akis kisitlari"nin dogrudan olcumu;
      su ana kadar yalnizca IOBT/LOBT suruklenmesiyle vekilliyorduk.
    - **Airport Arrival ATFM Delay**: gunluk varis ATFM gecikmesi, neden koduna gore.

    **Nedensellik uyarisi:** bunlar gun boyunun toplamidir, yani bir kalkis anindan
    sonraki saatleri de icerir; ayrica yayimlari aylarca gecikmelidir. Retrospektif
    model icin mesru, **nedensel model icin degil** — `groups.py` bu aileyi ayri
    tutuyor ve nedensel kosuda cikariliyor.
    """
    slot = _read_data_sheet(download(SLOT_URL, raw_dir / "eurocontrol_slot_adherence.xlsx"))
    arr = _read_data_sheet(download(ARR_DELAY_URL, raw_dir / "eurocontrol_arr_atfm_delay.xlsx"))

    num = lambda c: pl.col(c).cast(pl.Float64, strict=False)  # noqa: E731

    slot = (
        slot.filter(pl.col("APT_ICAO").is_in(CHALLENGE_AIRPORTS))
        .select(
            apt=pl.col("APT_ICAO"),
            gun=pl.col("FLT_DATE").cast(pl.Date, strict=False),
            _dep=num("FLT_DEP_1"),
            _reg=num("FLT_DEP_REG_1"),
            _gec=num("FLT_DEP_OUT_LATE_1"),
            _erken=num("FLT_DEP_OUT_EARLY_1"),
        )
        .with_columns(
            atfm_duzenlenen_oran=(pl.col("_reg") / pl.col("_dep").replace(0, None))
            .cast(pl.Float32),
            atfm_slot_gec_oran=(pl.col("_gec") / pl.col("_reg").replace(0, None))
            .cast(pl.Float32),
            atfm_slot_erken_oran=(pl.col("_erken") / pl.col("_reg").replace(0, None))
            .cast(pl.Float32),
            gunluk_kalkis=pl.col("_dep").cast(pl.Float32),
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
            pl.col("FLT_DATE").cast(pl.Date, strict=False).alias("gun"),
            (num("DLY_APT_ARR_1") / num("FLT_ARR_1").replace(0, None))
            .cast(pl.Float32).alias("varis_atfm_gecikme_dk"),
            num("FLT_ARR_1").cast(pl.Float32).alias("gunluk_inis"),
            *cause_exprs,
        )
    )
    return slot.join(arr, on=["apt", "gun"], how="full", coalesce=True).sort("apt", "gun")


def main() -> None:
    ap = argparse.ArgumentParser(description="EUROCONTROL acik gostergeleri")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--skip-daily", action="store_true",
                    help="gunluk ATFM setlerini indirme (yaklasik 215 MB)")
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    df = official_taxiout(raw)
    out = raw / "eurocontrol_taxiout.parquet"
    df.write_parquet(out)
    print(f"{df.height:,} havalimani-ay -> {out}")

    if not args.skip_daily:
        daily = daily_atfm(raw)
        dout = raw / "eurocontrol_atfm_daily.parquet"
        daily.write_parquet(dout)
        kapsam = daily.filter(pl.col("gun").is_not_null())
        print(f"{daily.height:,} havalimani-gun -> {dout}")
        print(f"  tarih araligi: {kapsam['gun'].min()} .. {kapsam['gun'].max()}")
    print(f"kapsanan havalimani: {sorted(df['apt'].unique().to_list())}")
    eksik = set(CHALLENGE_AIRPORTS) - set(df["apt"].unique().to_list())
    if eksik:
        print(f"resmi gostergede HIC verisi olmayan: {sorted(eksik)}")

if __name__ == "__main__":
    main()
