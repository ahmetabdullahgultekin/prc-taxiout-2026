"""Havalimani ve pist referans verisi (OurAirports, kamu mali).

Iki sey icin gerekli:

1. **Kalkis yonu.** Lee, Malik ve Jung (Charlotte, 2016) "departure fix"i anlamli bir
   tahmin edici olarak buluyor: ayni cikis noktasina giden kalkislar birbirinden daha
   fazla ayrilmak zorundadir, dolayisiyla komsulari kendisiyle ayni yone gidiyorsa ucak
   daha uzun bekler. Veride departure fix yok; `ADES_mvt` var. Kalkistan varisa
   **kerteriz** hesaplayip sektore yuvarlayarak vekilliyoruz.

2. **Havalimani yapisi.** Pist sayisi kapasiteyi belirler: EGLL ve EDDM'de 2, LTFM ve
   EHAM'da 6 pist var. Bu, havalimanlarinin neden farkli davrandiginin bir parcasi.

Lisans: "All data is released to the Public Domain" (ourairports.com/data/, 2026-09-01).
Atif zorunlu degil, yine de verilecek. `docs/external_data.md`'de belgeli.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import polars as pl

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"

CHALLENGE_AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]


def _download(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as r, dest.open("wb") as f:  # noqa: S310
            f.write(r.read())
    return dest


def build(raw_dir: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(tum havalimanlarinin koordinatlari, 11 havalimaninin pist ozeti) dondurur.

    Koordinat tablosu **tum** havalimanlarini icerir: varis noktasi dunyanin herhangi
    bir yerinde olabilir, kerteriz icin hepsi gerekli.
    """
    apt_csv = _download(AIRPORTS_URL, raw_dir / "ourairports_airports.csv")
    rwy_csv = _download(RUNWAYS_URL, raw_dir / "ourairports_runways.csv")

    coords = (
        pl.read_csv(apt_csv, infer_schema_length=50_000)
        .filter(pl.col("latitude_deg").is_not_null() & pl.col("longitude_deg").is_not_null())
        .select(
            icao=pl.col("ident"),
            enlem=pl.col("latitude_deg").cast(pl.Float64),
            boylam=pl.col("longitude_deg").cast(pl.Float64),
            yukseklik_ft=pl.col("elevation_ft").cast(pl.Float32, strict=False),
        )
        .unique(subset="icao")
    )

    runways = (
        pl.read_csv(rwy_csv, infer_schema_length=50_000)
        .filter(pl.col("airport_ident").is_in(CHALLENGE_AIRPORTS) & (pl.col("closed") == 0))
        .group_by("airport_ident")
        .agg(
            pist_sayisi=pl.len().cast(pl.Int8),
            en_uzun_pist_ft=pl.col("length_ft").max().cast(pl.Float32),
            ort_pist_ft=pl.col("length_ft").mean().cast(pl.Float32),
        )
        .rename({"airport_ident": "icao"})
    )
    return coords, runways


def main() -> None:
    ap = argparse.ArgumentParser(description="OurAirports referans verisi hazirla")
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    coords, runways = build(raw)
    coords.write_parquet(raw / "airport_coords.parquet")
    runways.write_parquet(raw / "airport_runways.parquet")
    print(f"{coords.height:,} havalimani koordinati, {runways.height} yarisma havalimani pisti")
    print(runways.sort("pist_sayisi", descending=True))


if __name__ == "__main__":
    main()
