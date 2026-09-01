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

TAXIOUT_URL = (
    "https://www.eurocontrol.int/performance/data/download/xls/"
    "Taxi-Out_Additional_Time.xlsx"
)
# Portal tarayici disi istekleri reddedebiliyor
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

CHALLENGE_AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]


def download(dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(TAXIOUT_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as f:  # noqa: S310
            f.write(r.read())
    return dest


def official_taxiout(raw_dir: Path) -> pl.DataFrame:
    """Havalimani-ay bazinda resmi referans ve ek taxi-out suresi (dakika/kalkis).

    `TF` toplam ucus, `VALID_FL` gecerli ek suresi hesaplanabilen ucus sayisidir;
    ikisinin farki agirlikli olarak de-icing ve eksik veri nedeniyle dusen ucuslardir.
    """
    path = download(raw_dir / "eurocontrol_taxiout_additional.xlsx")
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


def main() -> None:
    ap = argparse.ArgumentParser(description="EUROCONTROL resmi taxi-out gostergesi")
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    df = official_taxiout(raw)
    out = raw / "eurocontrol_taxiout.parquet"
    df.write_parquet(out)
    print(f"{df.height:,} havalimani-ay -> {out}")
    print(f"kapsanan havalimani: {sorted(df['apt'].unique().to_list())}")
    eksik = set(CHALLENGE_AIRPORTS) - set(df["apt"].unique().to_list())
    if eksik:
        print(f"resmi gostergede HIC verisi olmayan: {sorted(eksik)}")


if __name__ == "__main__":
    main()
