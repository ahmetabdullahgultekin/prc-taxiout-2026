"""METAR gozlemlerini hareket kayitlarina baglar.

Birlestirme **asof/backward**: her kalkis, kalkis anindan onceki en son gecerli
gozlemi alir. Ileriye bakmak burada anlamsiz olurdu; hava durumu kalkis anindaki
kosulu tarif eder.

`gozlem_yasi_dk` bilerek disari verilir: yarim saatlik yayin arasinda kosullar
degisebilir, model gozlemin ne kadar bayat oldugunu bilmelidir.
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
# Hareketin gerceklestigi havalimani; `pipeline.prepare_movements` ekler.
# `ADEP_mvt` DEGIL: o, ucusun kalkis havalimani (varislarda gelinen yer).
APT = "apt_mvt"

WEATHER_COLS = [
    "sicaklik_c", "cig_noktasi_c", "gorus_km", "ruzgar_ms", "yagis_mm", "tavan_m",
    "donma_yagisi", "kar", "sis", "gok_gurultusu", "deicing_vekili", "dusuk_gorus",
]


def attach(dep: pl.DataFrame, metar: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """`dep` satirlarina en son METAR gozlemini ekler.

    Nedensel modda `anchor` blok cozulme anidir: kalkis anindaki havayi bilmek
    gercek zamanli bir modelin elinde olmazdi.
    """
    # Yarisma verisinin zaman damgalari UTC-farkindalikli (datetime[us, UTC]);
    # IEM arsivi naif UTC donuyor. Birlestirme oncesi hizalanmazsa polars
    # dogrudan hata veriyor. Ayni anin iki gosterimi, kayma yok.
    tz = dep.schema[anchor].time_zone
    gozlem = pl.col("valid")
    if tz is not None:
        gozlem = gozlem.dt.replace_time_zone(tz)
    obs = (
        metar.select("station", _gozlem_ani=gozlem, **{c: pl.col(c) for c in WEATHER_COLS})
        .sort("_gozlem_ani")
    )
    joined = (
        dep.sort(anchor)
        .join_asof(
            obs,
            left_on=anchor,
            right_on="_gozlem_ani",
            by_left=APT,
            by_right="station",
            strategy="backward",
        )
    )
    return joined.with_columns(
        gozlem_yasi_dk=((pl.col(anchor) - pl.col("_gozlem_ani")).dt.total_seconds() / 60.0)
        .cast(pl.Float32),
        # cig noktasi farki: sifira yaklastikca sis/kirlanma riski artar
        cig_farki_c=(pl.col("sicaklik_c") - pl.col("cig_noktasi_c")).cast(pl.Float32),
    ).drop("_gozlem_ani", "station", strict=False)
