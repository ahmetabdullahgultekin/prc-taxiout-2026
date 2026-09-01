"""Gunluk havalimani durumu: ATFM duzenlemesi ve varis gecikmesi.

Idris ve ark. (Logan, 2002) taxi-out'u belirleyen dort ana faktorden birini
**asagi-akis kisitlari** (downstream restrictions) olarak sayiyor. Simdiye kadar bunu
yalnizca IOBT/LOBT suruklenmesiyle vekilliyorduk; EUROCONTROL'un acik gunluk serileri
dogrudan olcumu veriyor:

- gunun kalkislarindan kaci **ATFM slotu** altindaydi
- slot uyumu (erken/gec cikanlarin orani)
- gunluk **varis ATFM gecikmesi**, neden koduna gore (hava, ATC kapasitesi, meydan
  kapasitesi, personel, ekipman)

Iki seri de Ocak ve Temmuz 2026'yi, yani her iki siralama ayini da kapsiyor.

**Nedensellik uyarisi.** Bunlar gun boyunun toplamidir: bir kalkisin anindan sonraki
saatleri de icerirler, ve yayimlari aylarca gecikmelidir. Retrospektif model icin
mesru, gercek zamanli bir model icin degil. `groups.py` bunlari `atfm_gunluk` ailesinde
ayri tutuyor; `pipeline.build_features` nedensel kosuda hic eklemiyor.
"""

from __future__ import annotations

import polars as pl

APT = "ADEP_mvt"

STATE_COLS = [
    "atfm_duzenlenen_oran", "atfm_slot_gec_oran", "atfm_slot_erken_oran",
    "gunluk_kalkis", "gunluk_inis", "varis_atfm_gecikme_dk",
    "varis_gecikme_hava_dk", "varis_gecikme_atc_kapasite_dk",
    "varis_gecikme_meydan_kapasite_dk", "varis_gecikme_atc_personel_dk",
    "varis_gecikme_atc_ekipman_dk",
]


def attach(dep: pl.DataFrame, daily: pl.DataFrame, anchor: str) -> pl.DataFrame:
    """Kalkis satirlarina o gunun havalimani durumunu ekler."""
    have = [c for c in STATE_COLS if c in daily.columns]
    state = daily.select("apt", "gun", *have).rename({"apt": APT, "gun": "_gun"})
    return (
        dep.with_columns(_gun=pl.col(anchor).dt.date())
        .join(state, on=[APT, "_gun"], how="left")
        .drop("_gun")
    )
