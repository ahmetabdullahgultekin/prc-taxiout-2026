"""Gun-sifir veri tanisi.

Veri iner inmez calistir. Cevapladigi sorular (bkz. docs/facts.md):

  Q02 / D06  AOBT_3_flt ranking setinde duruyor mu, duruyorsa ne kadar iyi bir tahmin?
  D13        MVT_TIME - BLOCK_TIME == TAXITIME kimligi 2025'te tutuyor mu?
  M14        Zaman damgalari saniye hassasiyetinde mi, yoksa HH:MM mi?
  D10        NM ucus eslesme orani ne?
  --         Soguk baslangic: siralama setindeki (stand, pist) kombolari egitimde var mi?
  --         Onemsiz temel modellerin RMSE tabani ne?

Kullanim:
    python scripts/probe_data.py [--data-dir D:/prc-taxiout-2026]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import polars as pl

RAW_SUBDIR = "00_raw"
REPORT_PATH = Path("docs/data_probe_report.md")

TIME_COLS = ["MVT_TIME_UTC_mvt", "BLOCK_TIME_UTC_mvt", "SCHED_TIME_UTC_mvt"]
FLT_TIME_COLS = ["LOBT_flt", "IOBT_flt", "EOBT_1_flt", "ARVT_1_flt", "AOBT_3_flt", "ARVT_3_flt"]

_lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    _lines.append(text)


def section(title: str) -> None:
    say()
    say("## " + title)
    say()


def resolve_data_dir(cli_value: str | None) -> Path:
    for candidate in (cli_value, os.environ.get("TAXIOUT_DATA_DIR"), "D:/prc-taxiout-2026"):
        if candidate:
            return Path(candidate)
    raise SystemExit("veri dizini belirlenemedi")


def as_datetime(expr: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    """Kolon string olarak geldiyse datetime'a cevir, zaten datetime ise dokunma."""
    if dtype == pl.String:
        return expr.str.to_datetime(strict=False)
    return expr


def load(paths: list[Path]) -> pl.LazyFrame:
    lf = pl.scan_parquet([str(p) for p in paths])
    schema = lf.collect_schema()
    names = schema.names()
    casts = [
        as_datetime(pl.col(c), schema[c]).alias(c)
        for c in TIME_COLS + FLT_TIME_COLS
        if c in names
    ]
    return lf.with_columns(casts) if casts else lf


def secs(a: str, b: str) -> pl.Expr:
    """a - b, saniye cinsinden."""
    return (pl.col(a) - pl.col(b)).dt.total_seconds()


def rmse(pred: pl.Expr, truth: pl.Expr) -> pl.Expr:
    return ((pred - truth) ** 2).mean().sqrt()


def fmt(value: object, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        # oranlar (0..1) icin 4 hane, saniye cinsinden buyuklukler icin 1 hane
        places = 4 if -1.0 <= value <= 1.0 else digits
        return format(value, ",." + str(places) + "f")
    if isinstance(value, int):
        return format(value, ",")
    return str(value)


def table(df: pl.DataFrame) -> None:
    if df.height == 0:
        say("_(bos)_")
        return
    cols = df.columns
    say("| " + " | ".join(cols) + " |")
    say("|" + "|".join("---" for _ in cols) + "|")
    for row in df.iter_rows():
        say("| " + " | ".join(fmt(v) for v in row) + " |")


# --------------------------------------------------------------------------- kontroller


def check_schema(train: pl.LazyFrame, rank: pl.LazyFrame, submit: pl.LazyFrame | None) -> None:
    section("1. Sema karsilastirmasi (D05 / D06)")
    tcols = train.collect_schema().names()
    rcols = rank.collect_schema().names()
    missing = [c for c in tcols if c not in rcols]
    extra = [c for c in rcols if c not in tcols]
    say("- egitim kolon sayisi: **" + str(len(tcols)) + "**, siralama: **" + str(len(rcols)) + "**")
    say("- siralamada olmayan kolonlar: " + str(missing or "yok"))
    say("- siralamada fazladan olan kolonlar: " + str(extra or "yok"))
    if submit is not None:
        say("- submitting.parquet kolonlari: " + str(submit.collect_schema().names()))

    say()
    say("**Siralama setinde DEP satirlarinda doluluk orani** (0.0 = tamamen bosaltilmis):")
    dep = rank.filter(pl.col("PHASE_mvt") == "DEP")
    watch = set(TIME_COLS + FLT_TIME_COLS) | {
        "TAXITIME_SEC_mvt", "RUNWAY_mvt", "STAND_mvt", "FLIGHT_ID_mvt",
    }
    interesting = [c for c in rcols if c in watch]
    filled = dep.select(
        [pl.len().alias("n_dep")]
        + [pl.col(c).is_not_null().mean().alias(c) for c in interesting]
    ).collect()
    say()
    for name, value in zip(filled.columns, filled.row(0), strict=True):
        if name == "n_dep":
            say("- DEP satir sayisi: **" + fmt(value) + "**")
            continue
        note = ""
        if value == 0:
            note = "  <-- BOSALTILMIS"
        elif name == "AOBT_3_flt":
            note = "  <-- **DOLU, kritik bulgu**"
        say("- `" + name + "`: " + format(value, ".4f") + note)


def check_identity(train: pl.LazyFrame) -> None:
    section("2. Taxi-out kimligi: MVT_TIME - BLOCK_TIME == TAXITIME ? (D13)")
    dep = train.filter(pl.col("PHASE_mvt") == "DEP")
    diff = secs("MVT_TIME_UTC_mvt", "BLOCK_TIME_UTC_mvt") - pl.col("TAXITIME_SEC_mvt")
    res = dep.select(
        n=pl.len(),
        n_complete=(
            pl.col("MVT_TIME_UTC_mvt").is_not_null()
            & pl.col("BLOCK_TIME_UTC_mvt").is_not_null()
            & pl.col("TAXITIME_SEC_mvt").is_not_null()
        ).sum(),
        exact_match=(diff.abs() < 1).mean(),
        max_abs_diff=diff.abs().max(),
    ).collect()
    n, n_complete, match, maxdiff = res.row(0)
    say("- DEP satiri: **" + fmt(n) + "**, ucu de dolu olan: **" + fmt(n_complete) + "**")
    say("- kimlik <1 sn hata ile tutan oran: **" + fmt(match, 6) + "**")
    say("- en buyuk mutlak sapma: **" + fmt(maxdiff) + " sn**")
    say()
    say("Yorum: oran 1.0 ise TAXITIME turetilmis demektir ve zaman damgalari kendi icinde "
        "tutarlidir; 1.0 degilse aradaki fark bagimsiz bir olcum hatasidir ve kuyruk "
        "ozelliklerinin gurultu tabanini belirler.")


def check_precision(train: pl.LazyFrame) -> None:
    section("3. Zaman damgasi hassasiyeti (M14)")
    dep = train.filter(pl.col("PHASE_mvt") == "DEP")
    df = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            mvt_saniye_sifir=(pl.col("MVT_TIME_UTC_mvt").dt.second() == 0).mean(),
            blok_saniye_sifir=(pl.col("BLOCK_TIME_UTC_mvt").dt.second() == 0).mean(),
        )
        .sort("ADEP_mvt")
        .collect()
    )
    table(df)
    say()
    say("Oran ~1.0 olan havalimaninda veri **HH:MM** hassasiyetindedir: taxi-out'ta +-60 sn "
        "taban gurultu vardir ve o havalimani icin ulasilabilir RMSE alt siniri daha yuksektir.")


def check_nm_match(train: pl.LazyFrame, rank: pl.LazyFrame) -> None:
    section("4. Network Manager eslesme orani (D10)")
    for label, lf in (("egitim 2025", train), ("siralama 2026", rank)):
        cols = lf.collect_schema().names()
        aggs = {"n": pl.len()}
        if "FLIGHT_ID_mvt" in cols:
            aggs["flight_id_dolu"] = pl.col("FLIGHT_ID_mvt").is_not_null().mean()
        if "AOBT_3_flt" in cols:
            aggs["aobt3_dolu"] = pl.col("AOBT_3_flt").is_not_null().mean()
        df = (
            lf.filter(pl.col("PHASE_mvt") == "DEP")
            .group_by("ADEP_mvt")
            .agg(**aggs)
            .sort("ADEP_mvt")
            .collect()
        )
        say("**" + label + "**")
        say()
        table(df)
        say()


def check_aobt_strength(train: pl.LazyFrame) -> None:
    section("5. KRITIK: AOBT_3_flt ne kadar iyi bir tahmin? (Q02)")
    if "AOBT_3_flt" not in train.collect_schema().names():
        say("`AOBT_3_flt` egitim setinde yok — kontrol atlandi.")
        return
    say("Naif tahminci: `taxi_out = MVT_TIME_UTC_mvt - AOBT_3_flt`")
    say()
    dep = train.filter(
        (pl.col("PHASE_mvt") == "DEP")
        & pl.col("TAXITIME_SEC_mvt").is_not_null()
        & pl.col("AOBT_3_flt").is_not_null()
        & pl.col("MVT_TIME_UTC_mvt").is_not_null()
    ).with_columns(naive=secs("MVT_TIME_UTC_mvt", "AOBT_3_flt"))

    err = pl.col("naive") - pl.col("TAXITIME_SEC_mvt")
    overall = dep.select(
        n=pl.len(),
        rmse=rmse(pl.col("naive"), pl.col("TAXITIME_SEC_mvt")),
        mae=err.abs().mean(),
        yanlilik=err.mean(),
        medyan_mutlak_hata=err.abs().median(),
    ).collect()
    table(overall)
    say()
    per_apt = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            rmse=rmse(pl.col("naive"), pl.col("TAXITIME_SEC_mvt")),
            yanlilik=err.mean(),
        )
        .sort("rmse")
        .collect()
    )
    table(per_apt)
    say()
    say("**Nasil okunur.** Bu RMSE dusukse (orn. <60 sn) yarisma buyuk olcude "
        "'NM blok saatini APDF blok saatiyle uzlastirma + eslesmeyen satirlari doldurma' "
        "problemidir ve tum mimari buna gore kurulur. Yuksekse (orn. >200 sn) AOBT_3 "
        "yalnizca guclu bir ozelliktir, cozum degildir. Kapsama orani (n / toplam DEP) "
        "en az RMSE kadar onemli: kapsanmayan satirlar icin ayri bir model gerekir.")


def check_target(train: pl.LazyFrame) -> None:
    section("6. Hedef dagilimi")
    dep = train.filter((pl.col("PHASE_mvt") == "DEP") & pl.col("TAXITIME_SEC_mvt").is_not_null())
    t = pl.col("TAXITIME_SEC_mvt")
    df = (
        dep.group_by("ADEP_mvt")
        .agg(
            n=pl.len(),
            ort=t.mean(),
            std=t.std(),
            p10=t.quantile(0.10),
            p50=t.median(),
            p99=t.quantile(0.99),
            ust_120dk=(t > 7200).mean(),
            negatif=(t < 0).mean(),
        )
        .sort("ADEP_mvt")
        .collect()
    )
    table(df)
    say()
    say("`ust_120dk` PRC'nin resmi filtresini asan orandir (M08); `negatif` veri hatasi "
        "isaretidir. Ikisi de RMSE'de agir cezalandirilan kuyruktur: kirpma degil, "
        "**modelleme** karari gerektirir.")

    aylik = (
        dep.with_columns(ay=pl.col("MVT_TIME_UTC_mvt").dt.month())
        .group_by("ay")
        .agg(n=pl.len(), ort=t.mean(), std=t.std())
        .sort("ay")
        .collect()
    )
    say()
    say("**Aylik (Ocak ve Temmuz satirlarina dikkat: siralama seti o iki ay):**")
    say()
    table(aylik)


def check_baselines(train: pl.LazyFrame, rank: pl.LazyFrame) -> None:
    section("7. Temel modeller ve soguk baslangic")
    dep = train.filter(
        (pl.col("PHASE_mvt") == "DEP") & pl.col("TAXITIME_SEC_mvt").is_not_null()
    ).select("ADEP_mvt", "STAND_mvt", "RUNWAY_mvt", "TAXITIME_SEC_mvt", "MVT_TIME_UTC_mvt")

    # Ocak + Temmuz tutulur, kalan 10 ayla egitilir:
    # siralama setinin mevsimsel kurgusunu taklit eder.
    ay = pl.col("MVT_TIME_UTC_mvt").dt.month()
    fit = dep.filter(~ay.is_in([1, 7]))
    val = dep.filter(ay.is_in([1, 7]))

    genel_ort = fit.select(pl.col("TAXITIME_SEC_mvt").mean()).collect().item()
    apt_ort = fit.group_by("ADEP_mvt").agg(pl.col("TAXITIME_SEC_mvt").mean().alias("apt_ort"))
    combo = fit.group_by("ADEP_mvt", "STAND_mvt", "RUNWAY_mvt").agg(
        pl.col("TAXITIME_SEC_mvt").mean().alias("combo_ort"),
        pl.col("TAXITIME_SEC_mvt").quantile(0.10).alias("combo_p10"),
        pl.len().alias("combo_n"),
    )

    scored = (
        val.join(apt_ort, on="ADEP_mvt", how="left")
        .join(combo, on=["ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"], how="left")
        .with_columns(
            genel=pl.lit(genel_ort),
            combo_dolgulu=pl.col("combo_ort").fill_null(pl.col("apt_ort")),
        )
    )
    out = scored.select(
        n_dogrulama=pl.len(),
        kombo_kapsam=pl.col("combo_ort").is_not_null().mean(),
        rmse_genel_ort=rmse(pl.col("genel"), pl.col("TAXITIME_SEC_mvt")),
        rmse_apt_ort=rmse(pl.col("apt_ort"), pl.col("TAXITIME_SEC_mvt")),
        rmse_combo_ort=rmse(pl.col("combo_dolgulu"), pl.col("TAXITIME_SEC_mvt")),
    ).collect()
    table(out)
    say()
    say("`rmse_combo_ort` ilk gercek gonderimimizin tahmini seviyesidir. Bunun uzerine "
        "koyacagimiz her sey kuyruk / tikaniklik / hava bilesenidir.")

    rank_dep = rank.filter(pl.col("PHASE_mvt") == "DEP").select(
        "ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"
    )
    cold = (
        rank_dep.join(combo, on=["ADEP_mvt", "STAND_mvt", "RUNWAY_mvt"], how="left")
        .select(
            n=pl.len(),
            gorulmus_kombo=pl.col("combo_n").is_not_null().mean(),
            stand_bos=pl.col("STAND_mvt").is_null().mean(),
            pist_bos=pl.col("RUNWAY_mvt").is_null().mean(),
        )
        .collect()
    )
    say()
    say("**Siralama setinin egitimde gorulmemis kombo orani (soguk baslangic riski):**")
    say()
    table(cold)


# --------------------------------------------------------------------------- giris


def main() -> int:
    ap = argparse.ArgumentParser(description="PRC 2026 taxi-out veri tanisi")
    ap.add_argument("--data-dir", default=None, help="ham parquet dosyalarinin ust dizini")
    args = ap.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    raw = data_dir / RAW_SUBDIR
    train_files = sorted(raw.glob("training_*.parquet"))
    rank_file = raw / "ranking.parquet"
    submit_file = raw / "submitting.parquet"

    if not train_files or not rank_file.exists():
        print("Ham veri bulunamadi: " + str(raw))
        print("Beklenen: training_2025-*.parquet (12 adet), ranking.parquet, submitting.parquet")
        print("Takim onayi ve bucket anahtarlari geldiginde buraya indir, sonra tekrar calistir.")
        return 1

    say("# Veri Tani Raporu")
    say()
    say("Kaynak: `" + str(raw) + "` - egitim dosyasi: " + str(len(train_files)))

    train = load(train_files)
    rank = load([rank_file])
    submit = load([submit_file]) if submit_file.exists() else None

    check_schema(train, rank, submit)
    check_identity(train)
    check_precision(train)
    check_nm_match(train, rank)
    check_aobt_strength(train)
    check_target(train)
    check_baselines(train, rank)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print("\nRapor yazildi: " + str(REPORT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
