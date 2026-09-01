"""Engelsiz (unimpeded) referans taxi-out suresi.

EUROCONTROL'un resmi ATXOT gostergesinin sadik yeniden uygulamasi
(`docs/reference/atxot-notes.md`, ATXOT Edition 01.00, 16-03-2023):

    Referans(kombo) = P10( taxi-out sureleri )     kombo = (havalimani, stand, kalkis pisti)
    Gecerlilik      = komboda taxi-out <= P10 olan en az 10 ucus

Iki isi birden gorur:

1. **Model tabani.** 2025 birincisinin en buyuk tekil kazanci hedefi yeniden
   parametrelendirmekti: yakit tuketimi yerine yakit akisi ile egitim RMSE'yi
   220.56'dan 201.04'e indirdi, tum oznitelik gruplarindan buyuk bir etki (P05).
   Buradaki karsiligi: ham taxi-out yerine **referans uzerindeki artigi** ogrenmek.
   Agac modelleri sabit bir taban cikarildiginda cok daha az derinlik harcar.

2. **Makale icin dogrulanabilir bir taban cizgi.** Gostergeyi birebir yeniden
   uretebiliyor olmak, katkiyi PRC'nin kendi olcegiyle konusabilmemizi saglar.

**Resmi metottan bilincli iki sapma** (ikisi de makalede raporlanacak):

- ATXOT gecerli referansi olmayan kombolari gostergeden **tamamen duser**. Biz her
  satiri tahmin etmek zorundayiz, bu yuzden hiyerarsik bir geri dusus zinciri var:
  (apt, stand, pist) -> (apt, stand) -> (apt, pist) -> (apt).
- ATXOT kayan 12 ay kullanir. Elimizde yalnizca 2025 takvim yili var; referans
  sabittir, kaymaz.
"""

from __future__ import annotations

import polars as pl

TAXI = "TAXITIME_SEC_mvt"
APT = "ADEP_mvt"
STAND = "STAND_mvt"
RWY = "RUNWAY_mvt"

PERCENTILE = 0.10
MIN_BELOW = 10  # ATXOT s.15: P10'un altinda/esitinde en az 10 ucus
MAX_TAXI_SEC = 120 * 60  # ATXOT s.13 adim 1: 120 dakikayi asanlar referans orneginden cikar

# Genelden ozele: ilk uyan gecerli seviye kullanilir.
LEVELS: tuple[tuple[str, list[str]], ...] = (
    ("apt_stand_rwy", [APT, STAND, RWY]),
    ("apt_stand", [APT, STAND]),
    ("apt_rwy", [APT, RWY]),
    ("apt", [APT]),
)


def _level_reference(fit: pl.DataFrame, keys: list[str], suffix: str) -> pl.DataFrame:
    """Bir gruplama seviyesi icin P10 ve ATXOT gecerlilik bayragi."""
    ref = (
        fit.group_by(keys)
        .agg(
            [
                pl.col(TAXI).quantile(PERCENTILE, interpolation="linear").alias(f"p10_{suffix}"),
                pl.len().alias(f"n_{suffix}"),
            ]
        )
    )
    # gecerlilik: kac ucusun taxi suresi P10'a esit ya da ondan kisa
    below = (
        fit.join(ref, on=keys, how="left")
        .filter(pl.col(TAXI) <= pl.col(f"p10_{suffix}"))
        .group_by(keys)
        .agg(pl.len().alias(f"alti_{suffix}"))
    )
    return ref.join(below, on=keys, how="left").with_columns(
        pl.col(f"alti_{suffix}").fill_null(0),
        gecerli=pl.col(f"alti_{suffix}").fill_null(0) >= MIN_BELOW,
    ).rename({"gecerli": f"gecerli_{suffix}"})


def fit_reference(fit: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Referans tablolarini SADECE verilen egitim parcasindan uretir.

    Dogrulama sirasinda bu fonksiyona **yalnizca egitim aylari** verilmelidir;
    dogrulama aylarini icine katmak sizintidir ve OOF sayilarini yalanci sekilde
    iyilestirir.
    """
    clean = fit.filter(
        (pl.col("PHASE_mvt") == "DEP")
        & pl.col(TAXI).is_not_null()
        & (pl.col(TAXI) > 0)
        & (pl.col(TAXI) <= MAX_TAXI_SEC)
    )
    return {suffix: _level_reference(clean, keys, suffix) for suffix, keys in LEVELS}


def apply_reference(df: pl.DataFrame, tables: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """`referans_sn` ve hangi seviyeden geldigini gosteren `referans_seviye` ekler."""
    out = df
    for suffix, keys in LEVELS:
        out = out.join(tables[suffix], on=keys, how="left")

    # en ozel gecerli seviyeyi sec
    ref_expr = pl.lit(None, dtype=pl.Float64)
    lvl_expr = pl.lit("yok", dtype=pl.String)
    for suffix, _ in reversed(LEVELS):  # genelden ozele dogru uzerine yaz
        usable = (
            pl.col(f"gecerli_{suffix}").fill_null(False)
            & pl.col(f"p10_{suffix}").is_not_null()
        )
        ref_expr = pl.when(usable).then(pl.col(f"p10_{suffix}")).otherwise(ref_expr)
        lvl_expr = pl.when(usable).then(pl.lit(suffix)).otherwise(lvl_expr)

    return out.with_columns(
        referans_sn=ref_expr.cast(pl.Float32),
        referans_seviye=lvl_expr,
        # kombo ne kadar iyi gozlemlenmis: modelin referansa ne kadar guvenecegini soyler
        referans_ornek=pl.col("n_apt_stand_rwy").fill_null(0).cast(pl.Int32),
    ).drop(
        [c for s, _ in LEVELS for c in (f"p10_{s}", f"n_{s}", f"alti_{s}", f"gecerli_{s}")
         if c != "n_apt_stand_rwy"]
    )


def official_coverage(applied: pl.DataFrame) -> pl.DataFrame:
    """ATXOT'un kendi kapsama olcusu: gecerli referansi olmayan ucuslarin orani.

    Resmi metotta bu ucuslar gostergeden duser; PRC bu orani veri kalitesi
    gostergesi olarak izlemeyi sart kosuyor (ATXOT s.16, §6.3).
    """
    return (
        applied.group_by(APT)
        .agg(
            n=pl.len(),
            resmi_kapsam=(pl.col("referans_seviye") == "apt_stand_rwy").mean(),
            geri_dusus=(pl.col("referans_seviye") != "apt_stand_rwy").mean(),
        )
        .sort(APT)
    )
