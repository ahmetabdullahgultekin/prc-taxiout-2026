"""OPDI yer olaylarinin 11 havalimanindaki kapsamasini olcer.

**Neden bakildi.** OPDI (Open Performance Data Initiative, PRC'nin kendi girisimi,
OpenSky Network ile) ADS-B'den turetilmis flights olaylari yayimliyor ve v0.0.2 ile
**park pozisyonu giris/cikis** olaylari eklendi. `exit-parking_position`, siralama
setinde bosaltilmis olan blok cozulme aninin **bagimsiz bir olcumu** olurdu. Kapsam
Ocak 2022 - Agustos 2026, yani her iki siralama ayi da iceride.

Ayrica yarismanin belirtilen amaci tam olarak bu: taxi-out "elde etmesi zor bir
buyukluk" ve model, A-CDM verisi paylasmayan havalimanlarindaki bosluk icin. Acik
ADS-B olaylariyla o boslugu doldurabilmek dogrudan konuyla ilgili bir sonuc olurdu.

**Sonuc: kullanilamaz.** Olculen kapsama asagida; ozet `docs/opdi_negative_result.md`.

    python scripts/probe_opdi_coverage.py --events <flight_events_*.parquet>
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import polars as pl

# ICAO -> (latitude, longitude). OurAirports.
AIRPORTS = {
    "EDDF": (50.026706, 8.55835), "EDDM": (48.353802, 11.7861),
    "EGLL": (51.470748, -0.459909), "EHAM": (52.308601, 4.76389),
    "LEBL": (41.2971, 2.07846), "LEMD": (40.471926, -3.562664),
    "LFPG": (49.00896, 2.554117), "LIRF": (41.804532, 12.251998),
    "LTAI": (36.898701, 30.800501), "LTFM": (41.274874, 28.732136),
    "LSZH": (47.458056, 8.548056),
}

GROUND_EVENTS = [
    "exit-parking_position", "entry-parking_position", "take-off",
    "entry-runway", "exit-runway", "entry-taxiway",
]

RADIUS_KM = 10.0


def near(lat: float, lon: float) -> pl.Expr:
    """Havalimani cevresinde kaba bir kutu. Enlem-longitude olcegi enleme gore duzeltilir."""
    dlat = RADIUS_KM / 111.0
    dlon = RADIUS_KM / (111.0 * max(0.1, math.cos(math.radians(lat))))
    return ((pl.col("latitude") - lat).abs() < dlat) & (
        (pl.col("longitude") - lon).abs() < dlon
    )


def coverage(event_files: list[Path]) -> pl.DataFrame:
    ev = (
        pl.scan_parquet([str(p) for p in event_files])
        .filter(pl.col("type").is_in(GROUND_EVENTS))
        .select("type", "latitude", "longitude")
        .collect()
    )
    rows = []
    for icao, (la, lo) in AIRPORTS.items():
        sub = ev.filter(near(la, lo))
        counts = dict(sub.group_by("type").agg(n=pl.len()).iter_rows())
        rows.append({"apt": icao, **{e: counts.get(e, 0) for e in GROUND_EVENTS}})
    return pl.DataFrame(rows).sort("exit-parking_position", descending=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", nargs="+", required=True,
                    help="OPDI flight_events_*.parquet dosyalari")
    args = ap.parse_args()
    files = [Path(p) for p in args.events]
    df = coverage(files)
    print(f"dosya: {len(files)}")
    print(df)
    sifir = df.filter(pl.col("exit-parking_position") == 0)["apt"].to_list()
    print(f"\npark pozisyonu cikis olayi HIC olmayan havalimani: {sorted(sifir)}")


if __name__ == "__main__":
    main()
