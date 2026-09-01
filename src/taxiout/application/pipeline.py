"""Ortak boru hatti: veri yukleme, oznitelik uretimi, egitim, degerlendirme.

`scripts/train_baseline.py` ve `scripts/run_ablation.py` bunu kullanir; mantik tek
yerde durur. Betikler yalnizca komut satiri ve raporlama yapar.

Dogrulama semasi (AGENTS.md kural 4): 2025'ten **Ocak ve Temmuz cikarilir**, model
kalan 10 ayla egitilir, o iki ayda ayri ayri degerlendirilir. Rastgele K-fold burada
yalan soyler: siralama seti Ocak + Temmuz 2026, yani iki mevsimsel uc ve bir yillik
kayma. 2025 duzenleyicileri de bu zorlugu acikca raporladi: bazi takimlar bir ayda
yukselip digerinde dustu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import polars as pl

from taxiout.domain import reference
from taxiout.features import airport_state, congestion, groups, routing, weather

TARGET = "TAXITIME_SEC_mvt"
MVT = "MVT_TIME_UTC_mvt"
# Hareketin GERCEKLESTIGI havalimani. `ADEP_mvt` bu degildir: o, ucusun kalkis
# havalimanidir ve varis satirlarinda ucagin GELDIGI yeri gosterir (egitim setinde
# 1.582 farkli deger aliyor). Hareket havalimani = DEP ise ADEP, ARR ise ADES.
APT = "apt_mvt"
HOLDOUT_MONTHS = (1, 7)

# Siralama seti iki ayinda ayni havalimanlarini icermiyor: Ocak'ta 10'unun hepsi,
# Temmuz'da yalnizca bu ucu (gercek veriden olculdu, docs/facts.md R03). Ocak
# satirlarin %71'i, yani metrigi o domine ediyor. Dogrulama bu sekli taklit etmezse
# Temmuz performansini olmadigi kadar onemli sanip yanlis model seceriz.
JULY_AIRPORTS = ("EDDF", "EGLL", "EHAM")

CATEGORICAL = {
    APT, "RUNWAY_mvt", "STAND_mvt", "AIRCRAFT_TYPE_mvt", "AIRCRAFT_TYPE_flt",
    "WK_TBL_CAT_flt", "MARKET_SEGMENT_flt", "AIRCRAFT_OPERATOR_flt", "referans_seviye",
    "kalkis_pistleri", "inis_pistleri",
}

# Hedefi tasiyan ya da dogrudan veren kolonlar. `AOBT_3_flt` ve `BLOCK_TIME_UTC_mvt`
# ham haliyle asla ozniteligie donmez; turevleri (naif_taxi_sn) acikca uretilir.
EXCLUDED = {
    TARGET, "BLOCK_TIME_UTC_mvt", "MVT_ID_mvt", MVT, "SCHED_TIME_UTC_mvt",
    "FLIGHT_ID_mvt", "FLIGHT_mvt", "CALLSIGN_flt", "PHASE_mvt",
    "LOBT_flt", "IOBT_flt", "EOBT_1_flt", "ARVT_1_flt", "AOBT_3_flt", "ARVT_3_flt",
    "wxcodes", "skyc1", "ADES_mvt", "ADES_flt", "ADES_FILED_flt", "ADEP_flt",
    # kalkis satirlarinda apt_mvt ile ozdes; ikisini birden vermek gereksiz
    "ADEP_mvt",
    "FLIGHT_RULE_mvt", "FLIGHT_RULE_flt", "FLIGHT_TYPE_flt",
}

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


def month(col: str = MVT) -> pl.Expr:
    return pl.col(col).dt.month()


def prepare_movements(mvt: pl.DataFrame) -> pl.DataFrame:
    """Kanonik `apt_mvt` kolonunu ekler.

    Her hareket cercevesi (egitim ve siralama) bu fonksiyondan gecmeli. Aksi halde
    varis turevli tikaniklik oznitelikleri yanlis havalimaninda gruplanir: bir
    kalkisin cevresindeki inisleri sayarken, o havalimanina inenleri degil, o
    havalimanindan KALKMIS olan uzak inisleri saymis oluruz.
    """
    return mvt.with_columns(
        pl.when(pl.col("PHASE_mvt") == "DEP")
        .then(pl.col("ADEP_mvt"))
        .otherwise(pl.col("ADES_mvt"))
        .alias(APT)
    )


# --------------------------------------------------------------------------- veri


@dataclass
class Inputs:
    """Ham girdiler. Dis veri yoksa None kalir; boru hatti yine calisir."""

    movements: pl.DataFrame
    metar: pl.DataFrame | None = None
    coords: pl.DataFrame | None = None
    runways: pl.DataFrame | None = None
    atfm_daily: pl.DataFrame | None = None


def load_inputs(raw: Path) -> Inputs:
    files = sorted(raw.glob("training_*.parquet"))
    if not files:
        raise SystemExit(f"egitim dosyasi bulunamadi: {raw}")
    mvt = prepare_movements(
        pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")
    )

    def maybe(name: str) -> pl.DataFrame | None:
        p = raw / name
        return pl.read_parquet(p) if p.exists() else None

    return Inputs(
        mvt,
        maybe("metar.parquet"),
        maybe("airport_coords.parquet"),
        maybe("airport_runways.parquet"),
        maybe("eurocontrol_atfm_daily.parquet"),
    )


# --------------------------------------------------------------------------- oznitelik


def build_features(inputs: Inputs, causal: bool = False, aobt3: bool = True) -> pl.DataFrame:
    """Kalkis satirlari icin tam oznitelik tablosu. Referans SONRA eklenir."""
    mvt = inputs.movements
    anchor = congestion.BLOCK if causal else MVT

    feats = congestion.build(mvt, causal=causal)
    feats = feats.with_columns(
        saat=pl.col(anchor).dt.hour().cast(pl.Int8),
        hafta_gunu=pl.col(anchor).dt.weekday().cast(pl.Int8),
        ay=month().cast(pl.Int8),
        gun_dakikasi=(pl.col(anchor).dt.hour() * 60 + pl.col(anchor).dt.minute()).cast(pl.Int16),
        plan_sapmasi_sn=(pl.col(anchor) - pl.col("SCHED_TIME_UTC_mvt")).dt.total_seconds()
        .cast(pl.Float32),
    )
    if "EOBT_1_flt" in feats.columns:
        feats = feats.with_columns(
            eobt_sapmasi_sn=(pl.col(anchor) - pl.col("EOBT_1_flt")).dt.total_seconds()
            .cast(pl.Float32)
        )
    if aobt3 and not causal and "AOBT_3_flt" in feats.columns:
        # NM M3 blok saati, APDF blok saatinin BAGIMSIZ bir olcumu (M13). Siralama
        # setinde bosaltilmamis (D06), yani mesru bir ozniteliktir. Nedensel modda
        # kalkis saatini gerektirdigi icin kullanilmaz.
        feats = feats.with_columns(
            naif_taxi_sn=(pl.col(MVT) - pl.col("AOBT_3_flt")).dt.total_seconds().cast(pl.Float32),
            nm_eslesti=pl.col("AOBT_3_flt").is_not_null(),
        )

    feats = routing.build(mvt, feats, inputs.coords, anchor)
    if inputs.runways is not None:
        feats = feats.join(inputs.runways.rename({"icao": APT}), on=APT, how="left")
    if inputs.metar is not None:
        feats = weather.attach(feats, inputs.metar, anchor)
    if inputs.atfm_daily is not None and not causal:
        # gun boyunun toplami; nedensel modelde kullanilamaz (bkz. airport_state)
        feats = airport_state.attach(feats, inputs.atfm_daily, anchor)
    return feats


def feature_columns(df: pl.DataFrame) -> list[str]:
    """Modellenebilir kolonlar: hedefi verenler ve zaman tipleri disarida."""
    keep = []
    for name, dtype in zip(df.columns, df.dtypes, strict=True):
        if name in EXCLUDED or dtype in (pl.Datetime, pl.Date, pl.Duration, pl.Object):
            continue
        keep.append(name)
    return keep


# --------------------------------------------------------------------------- bolme


@dataclass
class Split:
    fit: pl.DataFrame
    val: pl.DataFrame
    columns: list[str] = field(default_factory=list)


def holdout_mask() -> pl.Expr:
    """Siralama setinin seklini taklit eden dogrulama maskesi.

    Ocak: tum havalimanlari. Temmuz: yalnizca `JULY_AIRPORTS`. Kalan her sey egitim,
    Temmuz'un diger havalimanlari dahil (gercek modelde de 2025'in tamamiyla
    egitiliyor).
    """
    return (month() == 1) | ((month() == 7) & pl.col(APT).is_in(JULY_AIRPORTS))


def seasonal_split(
    feats: pl.DataFrame, movements: pl.DataFrame, max_train_sec: float | None = None
) -> Split:
    """Dogrulama parcasini ayirir; referansi SADECE egitim parcasindan uretir.

    `max_train_sec` verilirse hedefi bu esigi asan satirlar **yalnizca egitimden**
    cikarilir; dogrulama kumesi hep tam kalir, cunku board da tam olacak.

    Gerekcesi olculdu: 2 saati asan 584 kalkisin NM eslesmesi olanlarinda %94,2'sinde
    NM blok saati makul (medyan 18 dk) ama APDF 2,3 saat diyor. Yani bunlar taxi
    suresi degil, **etiket hatasi**. Sayilari cok az (%0,028) ama LIRF'te en ust %1
    varyansin %88'ini tasiyor, dolayisiyla L2 kaybi onlari kovaliyor. PRC kendi resmi
    gostergesinde de 120 dakikayi asanlari eliyor (ATXOT s.13).
    """
    labelled = feats.filter(pl.col(TARGET).is_not_null())
    is_val = holdout_mask()

    tables = reference.fit_reference(movements.filter(~holdout_mask()))
    fit_rows = labelled.filter(~is_val)
    if max_train_sec is not None:
        fit_rows = fit_rows.filter(pl.col(TARGET) <= max_train_sec)
    fit = reference.apply_reference(fit_rows, tables)
    val = reference.apply_reference(labelled.filter(is_val), tables)
    return Split(fit, val, feature_columns(fit))


# --------------------------------------------------------------------------- model


def to_matrix(
    df: pl.DataFrame, cols: list[str], levels: dict[str, pl.Series] | None = None
) -> tuple[np.ndarray, list[int], dict[str, pl.Series]]:
    """polars -> (float32 numpy, kategorik indeksler, seviye sozlugu).

    pandas KULLANILMAZ (AGENTS.md kural 2). Seviye sozlugu egitimde uretilip
    dogrulamaya aynen tasinir; yoksa ayni kategori iki tarafta farkli koda duser ve
    model sessizce bozulur.
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


def train_predict(
    split: Split,
    cols: list[str],
    rounds: int = 1500,
    residual: bool = True,
    seeds: tuple[int, ...] = (1,),
) -> np.ndarray:
    """Egitir ve dogrulama kumesi icin tahmin dondurur.

    `residual=True` hedefi ATXOT P10 referansi uzerinden artik olarak ogrenir; 2025'te
    en buyuk tekil kazanc bu turden bir yeniden parametrelendirmeydi (P05).

    `seeds` birden fazlaysa ayni veri ve hiperparametrelerle farkli tohumlarla egitilen
    modellerin ortalamasi alinir — 2024 birincisinin yontemi buydu.
    """
    x_fit, cat_idx, levels = to_matrix(split.fit, cols)
    x_val, _, _ = to_matrix(split.val, cols, levels)

    ref_fit = split.fit["referans_sn"].fill_null(strategy="mean").to_numpy()
    ref_val = split.val["referans_sn"].fill_null(strategy="mean").to_numpy()
    y = split.fit[TARGET].to_numpy().astype(np.float64)
    if residual:
        y = y - ref_fit

    preds = []
    for seed in seeds:
        params = {**LGB_PARAMS, "seed": seed, "bagging_seed": seed, "feature_fraction_seed": seed}
        booster = lgb.train(
            params,
            lgb.Dataset(x_fit, label=y, feature_name=cols, categorical_feature=cat_idx),
            num_boost_round=rounds,
        )
        preds.append(booster.predict(x_val))
    pred = np.mean(preds, axis=0)
    if residual:
        pred = pred + ref_val
    return np.clip(pred, 0.0, None)  # negatif taxi suresi fiziksel olarak imkansiz


# --------------------------------------------------------------------------- degerlendirme


def evaluate(split: Split, pred: np.ndarray) -> dict[str, float]:
    """Toplam, Ocak, Temmuz ve havalimani bazinda RMSE."""
    truth = split.val[TARGET].to_numpy()
    scored = split.val.with_columns(_p=pl.Series(pred))
    out = {"toplam": rmse(pred, truth)}
    for m in HOLDOUT_MONTHS:
        sub = scored.filter(month() == m)
        if sub.height:
            out[f"ay_{m}"] = rmse(sub["_p"].to_numpy(), sub[TARGET].to_numpy())
            out[f"ay_{m}_n"] = float(sub.height)
    per_apt = (
        scored.group_by(APT)
        .agg(r=((pl.col("_p") - pl.col(TARGET)) ** 2).mean().sqrt())
        .sort(APT)
    )
    for apt, r in per_apt.iter_rows():
        out[f"apt_{apt}"] = float(r)
    return out


def group_report(columns: list[str]) -> str:
    """Aile basina kac oznitelik var — ablation tablosunun yanina yazilir."""
    assigned = groups.assign(columns)
    lines = [f"  {name:<22} {len(cols):>3}" for name, cols in assigned.items() if cols]
    return "\n".join(lines)
