"""Uctan uca taban model: oznitelik -> egitim -> degerlendirme.

Dogrulama semasi (AGENTS.md kural 4): 2025'ten **Ocak ve Temmuz cikarilir**, model
kalan 10 ayla egitilir ve o iki ayda ayri ayri degerlendirilir. Rastgele K-fold
burada yalan soyler: siralama seti Ocak + Temmuz 2026, yani iki mevsimsel uc ve
bir yillik kayma.

Ayni kosuda iki hedef parametrelendirmesi karsilastirilir:

  ham       -> dogrudan TAXITIME_SEC_mvt
  artik     -> TAXITIME_SEC_mvt - referans_sn (ATXOT P10), tahminde geri eklenir

2025 birincisinin en buyuk tekil kazanci tam olarak bu turden bir yeniden
parametrelendirmeydi (P05), o yuzden ilk kosuda olcuyoruz.

    python scripts/train_baseline.py --data-dir D:/prc-taxiout-2026
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import polars as pl

from taxiout.domain import reference
from taxiout.features import congestion, routing, weather

TARGET = "TAXITIME_SEC_mvt"
MVT = "MVT_TIME_UTC_mvt"
APT = "ADEP_mvt"
HOLDOUT_MONTHS = (1, 7)

CATEGORICAL = [
    "ADEP_mvt", "RUNWAY_mvt", "STAND_mvt", "AIRCRAFT_TYPE_mvt", "WK_TBL_CAT_flt",
    "MARKET_SEGMENT_flt", "AIRCRAFT_OPERATOR_flt", "referans_seviye",
    "kalkis_pistleri", "inis_pistleri",
]

LGB_PARAMS = {
    "objective": "regression",  # L2: RMSE'nin optimal tahmincisi kosullu ortalamadir
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 127,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "max_bin": 127,  # 16 GB RAM'de bellek yarilanir, dogruluk kaybi ihmal edilebilir
    "verbosity": -1,
    "num_threads": 0,
}


def month(expr: str = MVT) -> pl.Expr:
    return pl.col(expr).dt.month()


def load_movements(raw: Path) -> pl.DataFrame:
    files = sorted(raw.glob("training_*.parquet"))
    if not files:
        raise SystemExit(f"egitim dosyasi bulunamadi: {raw}")
    return pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")


def build_features(
    mvt: pl.DataFrame,
    metar: pl.DataFrame | None,
    coords: pl.DataFrame | None = None,
    runways: pl.DataFrame | None = None,
    aobt3: bool = True,
    causal: bool = False,
) -> pl.DataFrame:
    """Tikaniklik + takvim + (varsa) hava ozniteliklerini uretir. Referans SONRA eklenir.

    `aobt3=False` ablation icindir: NM blok saatinden turetilen naif tahmin
    cikarilir. Bu iki kosunun farki, `AOBT_3_flt` kolonunun gercek bilgi degeridir
    (Q02) ve dogrudan makaleye girer.
    """
    anchor = congestion.BLOCK if causal else MVT
    feats = congestion.build(mvt, causal=causal)
    feats = feats.with_columns(
        saat=pl.col(anchor).dt.hour().cast(pl.Int8),
        hafta_gunu=pl.col(anchor).dt.weekday().cast(pl.Int8),
        ay=month().cast(pl.Int8),
        gun_dakikasi=(pl.col(anchor).dt.hour() * 60
                      + pl.col(anchor).dt.minute()).cast(pl.Int16),
        # plana gore sapma: gecikmis ucus daha yogun bir yuzeyle karsilasir
        plan_sapmasi_sn=(pl.col(anchor) - pl.col("SCHED_TIME_UTC_mvt")).dt.total_seconds()
        .cast(pl.Float32),
    )
    if "EOBT_1_flt" in feats.columns:
        feats = feats.with_columns(
            eobt_sapmasi_sn=(pl.col(anchor) - pl.col("EOBT_1_flt"))
            .dt.total_seconds().cast(pl.Float32)
        )
    if aobt3 and not causal and "AOBT_3_flt" in feats.columns:
        # NM M3 blok saati, APDF blok saatinin BAGIMSIZ bir olcumu (M13).
        # Siralama setinde bosaltilmamis (D06), yani mesru bir ozniteliktir.
        feats = feats.with_columns(
            naif_taxi_sn=(pl.col(MVT) - pl.col("AOBT_3_flt")).dt.total_seconds()
            .cast(pl.Float32),
            nm_eslesti=pl.col("AOBT_3_flt").is_not_null(),
        )
    feats = routing.build(mvt, feats, coords, anchor)
    if runways is not None:
        feats = feats.join(runways.rename({"icao": APT}), on=APT, how="left")
    if metar is not None:
        feats = weather.attach(feats, metar, anchor)
    return feats


def feature_columns(df: pl.DataFrame) -> list[str]:
    """Hedefi ve hedefi dogrudan veren her seyi disarida birak."""
    yasak = {
        TARGET, "BLOCK_TIME_UTC_mvt", "MVT_ID_mvt", MVT, "SCHED_TIME_UTC_mvt",
        "FLIGHT_ID_mvt", "FLIGHT_mvt", "CALLSIGN_flt", "PHASE_mvt",
        "LOBT_flt", "IOBT_flt", "EOBT_1_flt", "ARVT_1_flt", "AOBT_3_flt", "ARVT_3_flt",
        "artik", "saat_kova", "wxcodes", "skyc1", "ADES_mvt", "ADES_flt", "ADES_FILED_flt",
        "ADEP_flt", "FLIGHT_RULE_mvt", "FLIGHT_RULE_flt", "FLIGHT_TYPE_flt",
    }
    keep = []
    for name, dtype in zip(df.columns, df.dtypes, strict=True):
        if name in yasak:
            continue
        if dtype in (pl.Datetime, pl.Date, pl.Duration, pl.Object):
            continue
        keep.append(name)
    return keep


def to_matrix(df: pl.DataFrame, cols: list[str], levels: dict[str, pl.Series] | None = None):
    """polars -> (float32 numpy, kategorik indeksler, seviye sozlugu).

    pandas KULLANILMAZ (AGENTS.md kural 2). Kategorikler tamsayi koda cevrilir;
    seviye sozlugu egitimde uretilip dogrulamaya aynen tasinir, yoksa ayni kategori
    iki tarafta farkli koda duser ve model sessizce bozulur.
    """
    levels = {} if levels is None else levels
    arrays, cat_idx = [], []
    for i, c in enumerate(cols):
        s = df[c]
        if c in CATEGORICAL or s.dtype == pl.String:
            if c not in levels:
                levels[c] = s.drop_nulls().unique().sort()
            codes = s.cast(pl.String).replace_strict(
                old=levels[c].cast(pl.String),
                new=pl.int_range(len(levels[c]), eager=True),
                default=-1,
                return_dtype=pl.Int32,
            )
            arrays.append(codes.cast(pl.Float32).to_numpy())
            cat_idx.append(i)
        elif s.dtype == pl.Boolean:
            arrays.append(s.cast(pl.Float32).fill_null(float("nan")).to_numpy())
        else:
            arrays.append(s.cast(pl.Float32).to_numpy())
    return np.column_stack(arrays).astype(np.float32), cat_idx, levels


def rmse(pred: np.ndarray, truth: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - truth) ** 2)))


def report(name: str, val: pl.DataFrame, pred: np.ndarray) -> None:
    truth = val[TARGET].to_numpy()
    print(f"\n=== {name} ===")
    print(f"  toplam RMSE: {rmse(pred, truth):8.2f} sn   (n={len(truth):,})")
    scored = val.with_columns(_p=pl.Series(pred))
    for label, frame in (
        ("ay", scored.group_by(month().alias("k"))),
        ("havalimani", scored.group_by(pl.col(APT).alias("k"))),
    ):
        out = (
            frame.agg(
                n=pl.len(),
                rmse=((pl.col("_p") - pl.col(TARGET)) ** 2).mean().sqrt(),
            )
            .sort("rmse", descending=True)
        )
        print(f"  -- {label} bazinda --")
        for k, n, r in out.iter_rows():
            print(f"     {str(k):<8} n={n:>8,}  RMSE={r:8.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))
    ap.add_argument("--rounds", type=int, default=1500)
    ap.add_argument("--causal", action="store_true",
                    help="nedensel mod: oznitelikler blok cozulme anina baglanir, "
                         "ileriye bakan pencere yok (yalnizca makale icin)")
    ap.add_argument("--no-aobt3", action="store_true",
                    help="NM blok saatinden turetilen ozniteligi cikar (ablation)")
    args = ap.parse_args()

    raw = Path(args.data_dir) / "00_raw"
    t0 = time.time()

    mvt = load_movements(raw)
    print(f"hareket: {mvt.height:,} satir")

    metar_path = raw / "metar.parquet"
    metar = pl.read_parquet(metar_path) if metar_path.exists() else None
    print(f"METAR: {'yok' if metar is None else f'{metar.height:,} gozlem'}")

    coords_path, rwy_path = raw / "airport_coords.parquet", raw / "airport_runways.parquet"
    coords = pl.read_parquet(coords_path) if coords_path.exists() else None
    runways = pl.read_parquet(rwy_path) if rwy_path.exists() else None
    print(f"havalimani referansi: {'yok' if coords is None else f'{coords.height:,} koordinat'}")

    feats = build_features(
        mvt, metar, coords, runways, aobt3=not args.no_aobt3, causal=args.causal
    )
    mod = "NEDENSEL (blok cipali)" if args.causal else "retrospektif (kalkis cipali)"
    print(f"mod: {mod}")
    feats = feats.filter(pl.col(TARGET).is_not_null())
    print(f"oznitelik tablosu: {feats.height:,} kalkis, {len(feats.columns)} kolon")

    is_val = month().is_in(HOLDOUT_MONTHS)
    fit_raw, val = feats.filter(~is_val), feats.filter(is_val)

    # referans YALNIZCA egitim aylarindan: dogrulama aylarini katmak sizintidir
    tables = reference.fit_reference(mvt.filter(~month().is_in(HOLDOUT_MONTHS)))
    fit_raw = reference.apply_reference(fit_raw, tables)
    val = reference.apply_reference(val, tables)
    print("\nreferans kapsami (resmi ATXOT seviyesi vs geri dusus):")
    print(reference.official_coverage(val))

    cols = feature_columns(fit_raw)
    x_fit, cat_idx, levels = to_matrix(fit_raw, cols)
    x_val, _, _ = to_matrix(val, cols, levels)
    y_fit_raw = fit_raw[TARGET].to_numpy()
    ref_fit = fit_raw["referans_sn"].fill_null(strategy="mean").to_numpy()
    ref_val = val["referans_sn"].fill_null(strategy="mean").to_numpy()

    for name, y_fit, geri_ekle in (
        ("ham hedef", y_fit_raw, np.zeros_like(ref_val)),
        ("artik hedef (taxi - ATXOT P10)", y_fit_raw - ref_fit, ref_val),
    ):
        booster = lgb.train(
            LGB_PARAMS,
            lgb.Dataset(x_fit, label=y_fit, feature_name=cols, categorical_feature=cat_idx),
            num_boost_round=args.rounds,
        )
        pred = booster.predict(x_val) + geri_ekle
        pred = np.clip(pred, 0, None)  # negatif taxi suresi fiziksel olarak imkansiz
        report(name, val, pred)

    print(f"\ntoplam sure: {time.time() - t0:,.0f} sn")


if __name__ == "__main__":
    main()
