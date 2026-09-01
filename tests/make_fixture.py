"""Gercek veri setinin YAPISINI taklit eden sentetik veri uretir.

Amac hiz degil sadakat: fixture gercek kurguyu yansitmazsa testler yanlis seyi
dogrular. Bu bir kez pahaliya mal oldu. Ilk surumde `ADEP_mvt` her satirda yarisma
havalimaniydi; gercekte oyle degil ve varis turevli tum oznitelikler yanlis
havalimaninda gruplaniyordu, testler bunu goremedi.

Gercek veriden olculen ve burada birebir yeniden uretilen yapisal ozellikler
(`docs/facts.md` R01-R07):

- **10 havalimani**, 11 degil. LTAI (Antalya) veride yok.
- `ADEP_mvt` **ucusun kalkis havalimani**, hareketin havalimani degil. Varis
  satirlarinda ucagin geldigi (cogu zaman yarisma disi) havalimanini gosterir;
  egitim setinde 1.582 farkli deger aliyor.
- Hareket havalimani = DEP ise `ADEP_mvt`, ARR ise `ADES_mvt`.
- Siralama seti **asimetrik**: Ocak'ta 10 havalimani, Temmuz'da yalnizca EDDF,
  EGLL, EHAM. Ocak satirlarin %71'i.
- `MVT_TIME - BLOCK_TIME == TAXITIME` kimligi tam tutuyor.
- Zaman damgalari saniye hassasiyetinde ve **UTC-farkindalikli** (datetime[us, UTC]);
  dis veri kaynaklari naif donuyor, birlestirmeler hizalama gerektiriyor.

Gercek veri ASLA bu dizine yazilmaz (form sarti F11).

    python tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

# Gercek veri setindeki 10 havalimani. LTAI bilerek yok (R01).
AIRPORTS = ["EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LSZH", "LTFM"]

# Siralama setinde Temmuz yalnizca bu ucunu iceriyor (R03).
JULY_AIRPORTS = ["EDDF", "EGLL", "EHAM"]

# Yarisma disi havalimanlari: varislarin geldigi ve kalkislarin gittigi yerler.
# Gercekte 1.582 tane var; yapiyi tasimak icin bir avuc yeterli.
OUTSIDE = ["LTBA", "EGKK", "LFPO", "EDDL", "LIMC", "LOWW", "EKCH", "ESSA", "KJFK", "OMDB"]

TYPES = ["A320", "A321", "B738", "A20N", "B77W", "E195", "A359"]
WAKE = {"A320": "M", "A321": "M", "B738": "M", "A20N": "M", "B77W": "H", "E195": "M", "A359": "H"}


def build(
    start: datetime, days: int, per_day: int, seed: int, airports: list[str] | None = None
) -> pl.DataFrame:
    """Bir donem icin hareket kayitlari uretir."""
    airports = airports or AIRPORTS
    rng = np.random.default_rng(seed)
    n = days * per_day

    # hareketin GERCEKLESTIGI havalimani
    apt = rng.choice(airports, n)
    phase = rng.choice(["DEP", "ARR"], n)
    other = rng.choice(OUTSIDE + AIRPORTS, n)  # karsi uc

    # gercek kurgu: DEP -> ADEP=hareket apt, ADES=karsi uc; ARR -> tersi
    adep = np.where(phase == "DEP", apt, other)
    ades = np.where(phase == "DEP", other, apt)

    runways = np.array([f"{a[-2:]}L" if r else f"{a[-2:]}R"
                        for a, r in zip(apt, rng.random(n) < 0.5, strict=True)])
    stand = np.array([str(s) for s in rng.integers(1, 21, n)])
    actype = rng.choice(TYPES, n)

    offsets = rng.integers(0, days * 86400, n)
    block = [start + timedelta(seconds=int(s)) for s in offsets]

    # taxi-out: stand/pist tabani + kuyruk kuyrugu; taxi-in daha kisa
    base = 300 + stand.astype(int) * 6 + np.char.endswith(runways, "R") * 120
    taxi = np.where(phase == "DEP", base + rng.gamma(2.0, 90.0, n), 240 + rng.gamma(1.5, 40.0, n))
    taxi = np.round(taxi).astype(int)

    # DEP: kalkis = blok + taxi. ARR: inis = blok - taxi (once iner, sonra bloga girer)
    mvt = [b + timedelta(seconds=int(t)) if p == "DEP" else b - timedelta(seconds=int(t))
           for b, t, p in zip(block, taxi, phase, strict=True)]

    matched = rng.random(n) < 0.985  # gercekte %98,5 (R08)
    aobt3 = [b + timedelta(seconds=float(e)) if m else None
             for b, e, m in zip(block, rng.normal(0, 110, n), matched, strict=True)]
    opt_block = [b if m else None for b, m in zip(block, matched, strict=True)]
    opt_fid = [int(i) if m else None for i, m in enumerate(matched)]

    frame = pl.DataFrame({
        "MVT_ID_mvt": np.arange(seed * 10**7, seed * 10**7 + n),
        "FLIGHT_ID_mvt": opt_fid,
        "FLIGHT_mvt": [f"XX{i % 9000 + 100}" for i in range(n)],
        "FLIGHT_RULE_mvt": ["I"] * n,
        "ADEP_mvt": adep,
        "ADES_mvt": ades,
        "PHASE_mvt": phase,
        "MVT_TIME_UTC_mvt": mvt,
        "BLOCK_TIME_UTC_mvt": block,
        # kalkis gecikmesi degisken; sabit ofset plan_sapmasi_sn'yi hedefin kopyasi yapardi
        "SCHED_TIME_UTC_mvt": [b - timedelta(seconds=int(d)) for b, d in
                               zip(block, rng.normal(600, 900, n).clip(-1800, 7200), strict=True)],
        "AIRCRAFT_TYPE_mvt": actype,
        "RUNWAY_mvt": runways,
        "STAND_mvt": stand,
        "TAXITIME_SEC_mvt": taxi,
        "LOBT_flt": opt_block,
        "CALLSIGN_flt": [f"XXX{i % 9000}" for i in range(n)],
        "ADEP_flt": adep,
        "ADES_flt": ades,
        "ADES_FILED_flt": ades,
        "MARKET_SEGMENT_flt": rng.choice(["Mainline", "Low-Cost", "Regional"], n),
        "IOBT_flt": opt_block,
        "FLIGHT_RULE_flt": ["I"] * n,
        "FLIGHT_TYPE_flt": ["S"] * n,
        "AIRCRAFT_TYPE_flt": actype,
        "WK_TBL_CAT_flt": [WAKE[t] for t in actype],
        "AIRCRAFT_OPERATOR_flt": rng.choice(["AAA", "BBB", "CCC", "DDD"], n),
        "EOBT_1_flt": opt_block,
        "ARVT_1_flt": opt_block,
        "AOBT_3_flt": aobt3,
        "ARVT_3_flt": opt_block,
    })
    # gercek veri gibi UTC-farkindalikli yap
    zaman = [c for c, d in frame.schema.items() if d == pl.Datetime]
    return frame.with_columns(
        [pl.col(c).dt.replace_time_zone("UTC") for c in zaman]
    )


def external_data(out: Path) -> None:
    """Minimal sentetik dis veri: METAR, havalimani referansi, gunluk ATFM.

    Bunlar olmadan entegrasyon testleri **bosuna gecer**: `load_inputs` dis veriyi
    None dondurur, egitim ve siralama taraflari ayni sekilde eksik kalir, dolayisiyla
    "her oznitelik iki tarafta da uretilebiliyor mu" testi hicbir sey dogrulamaz.
    Gercek bir hata tam bu yuzden kacmisti.
    """
    rng = np.random.default_rng(99)
    saatler = pl.datetime_range(datetime(2025, 1, 1), datetime(2026, 8, 1),
                                interval="30m", eager=True, closed="left")
    n = len(saatler)
    pl.concat([
        pl.DataFrame({
            "station": [a] * n, "valid": saatler,
            "sicaklik_c": rng.normal(12, 9, n), "cig_noktasi_c": rng.normal(7, 8, n),
            "gorus_km": rng.gamma(4, 3, n).clip(0.1, 20), "ruzgar_ms": rng.gamma(2, 3, n),
            "ruzgar_yon": rng.uniform(0, 360, n), "yagis_mm": rng.gamma(0.4, 1.0, n),
            "tavan_m": rng.gamma(3, 400, n), "wxcodes": [""] * n, "skyc1": ["FEW"] * n,
            "donma_yagisi": rng.random(n) < 0.01, "kar": rng.random(n) < 0.01,
            "sis": rng.random(n) < 0.05, "gok_gurultusu": rng.random(n) < 0.02,
            "deicing_vekili": rng.random(n) < 0.02, "dusuk_gorus": rng.random(n) < 0.05,
        })
        for a in AIRPORTS
    ]).write_parquet(out / "metar.parquet")

    k = len(AIRPORTS)
    pl.DataFrame({
        "icao": AIRPORTS + OUTSIDE,
        "enlem": rng.uniform(36, 53, k + len(OUTSIDE)),
        "boylam": rng.uniform(-1, 31, k + len(OUTSIDE)),
        "yukseklik_ft": rng.uniform(0, 1500, k + len(OUTSIDE)),
    }).write_parquet(out / "airport_coords.parquet")

    pl.DataFrame({
        "icao": AIRPORTS,
        "pist_sayisi": rng.integers(2, 7, k).astype("int8"),
        "en_uzun_pist_ft": rng.uniform(10000, 14000, k),
        "ort_pist_ft": rng.uniform(9000, 13000, k),
    }).write_parquet(out / "airport_runways.parquet")

    gunler = pl.date_range(date(2025, 1, 1), date(2026, 8, 1), eager=True, closed="left")
    g = len(gunler)
    pl.concat([
        pl.DataFrame({
            "apt": [a] * g, "gun": gunler,
            "atfm_duzenlenen_oran": rng.beta(2, 20, g),
            "atfm_slot_gec_oran": rng.beta(2, 30, g),
            "atfm_slot_erken_oran": rng.beta(2, 30, g),
            "gunluk_kalkis": rng.uniform(200, 800, g),
            "varis_atfm_gecikme_dk": rng.gamma(2, 1.5, g),
            "gunluk_inis": rng.uniform(200, 800, g),
            "varis_gecikme_hava_dk": rng.gamma(1.5, 1.0, g),
            "varis_gecikme_atc_kapasite_dk": rng.gamma(1.2, 0.5, g),
            "varis_gecikme_meydan_kapasite_dk": rng.gamma(1.2, 0.6, g),
            "varis_gecikme_atc_personel_dk": rng.gamma(1.0, 0.3, g),
            "varis_gecikme_atc_ekipman_dk": rng.gamma(1.0, 0.2, g),
        })
        for a in AIRPORTS
    ]).write_parquet(out / "eurocontrol_atfm_daily.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-day", type=int, default=600)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for month in range(1, 13):
        start = datetime(2025, month, 1)
        nxt = datetime(2025 + month // 12, month % 12 + 1, 1)
        build(start, 28, args.per_day, seed=month).write_parquet(
            out / f"training_{start:%Y-%m-%d}_{nxt:%Y-%m-%d}.parquet"
        )

    # siralama seti gercek asimetriyi tasir: Ocak 10 havalimani, Temmuz yalnizca 3 (R03)
    rank = pl.concat([
        build(datetime(2026, 1, 1), 28, args.per_day, seed=101, airports=AIRPORTS),
        build(datetime(2026, 7, 1), 28, args.per_day // 3, seed=107, airports=JULY_AIRPORTS),
    ])
    is_dep = pl.col("PHASE_mvt") == "DEP"
    rank = rank.with_columns(
        pl.when(is_dep).then(None).otherwise(pl.col("BLOCK_TIME_UTC_mvt"))
        .alias("BLOCK_TIME_UTC_mvt"),
        pl.when(is_dep).then(None).otherwise(pl.col("TAXITIME_SEC_mvt"))
        .alias("TAXITIME_SEC_mvt"),
    )
    rank.write_parquet(out / "ranking.parquet")
    rank.filter(is_dep).select("MVT_ID_mvt", "TAXITIME_SEC_mvt").write_parquet(
        out / "submitting.parquet"
    )

    external_data(out)
    print("fixture yazildi:", out, "| siralama satiri:", rank.height, "| dis veri dahil")


if __name__ == "__main__":
    main()
