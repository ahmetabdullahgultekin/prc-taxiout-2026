"""Tikaniklik ve pist kuyrugu oznitelikleri.

Bunlar problemin fikri cekirdegi. Gerekce:

Siralama setinde kalkislar icin **yalnizca** blok saati ve taxi suresi bosaltilmis
(D05). Kalkis saati (`MVT_TIME_UTC_mvt`), pist ve stand duruyor; varis satirlarinin
hicbir alani bosaltilmamis (D09). Yarismanin amaci gercek zamanli tahmin degil,
**post-operasyon** analizi (M01) — dolayisiyla bir kalkisin kendi kalkis anindan
sonraki trafigi de kullanmak mesrudur ve problemin dogasidir.

Literaturde taxi-out'un en guclu tekil aciklayicisi Idris ve ark.'nin (Boston Logan)
"takeoff queue size" degiskenidir: bir ucagin push-back'i ile kendi kalkisi arasinda
pistten kalkan diger ucak sayisi. Gercek operasyonda bu degisken **tahmin edilmek**
zorundadir cunku gelecekteki kalkislar bilinmez. Bizde bilinir.

**Dairesellik tuzagi.** Kuyrugu tam olarak saymak push-back saatini gerektirir, o da
tahmin etmeye calistigimiz seydir; sabit nokta iterasyonu kendini besleyen bir donguye
donusebilir. Bu yuzden cekirdek oznitelikler **dairesel olmayan** vekillerdir: sabit
geriye/ileriye bakis pencereleri (5/10/15/30/60 dk). Hangi pencerenin hangi havalimaninda
anlamli oldugunu modelin kendisi ogrenir. Bu, tek bir pencere secmekten kesinlikle daha
iyidir ve hicbir donguye girmez.
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
APT = "ADEP_mvt"
RWY = "RUNWAY_mvt"
PHASE = "PHASE_mvt"

# Geriye ve ileriye bakis pencereleri (dakika). Model hangisinin isine yaradigini secer.
WINDOWS_MIN = (5, 10, 15, 30, 60)


def _cumulative_by_time(events: pl.DataFrame, group: list[str]) -> pl.DataFrame:
    """(grup, zaman) -> o ana KADAR ve o an DAHIL toplam olay sayisi.

    Esit zaman damgalari icin tek bir deger uretir. Bu onemli: veri bazi
    havalimanlarinda HH:MM hassasiyetinde olabiliyor (M14), yani ayni saniyede
    onlarca hareket gorunur. Satir sirasina dayali bir sayac o durumda esitler
    arasinda tutarsiz sonuc verir.
    """
    return (
        events.group_by([*group, MVT])
        .agg(_k=pl.len())
        .sort(MVT)
        .with_columns(_cum=pl.col("_k").cum_sum().over(group))
        .select(*group, MVT, "_cum")
        .sort(MVT)
    )


def _cum_at(keys: pl.DataFrame, cum: pl.DataFrame, group: list[str], at: pl.Expr) -> pl.Series:
    """`at` ifadesinin verdigi ana kadarki kumulatif sayaci her anahtar satiri icin dondurur."""
    probe = keys.select(*group, _probe=at).with_row_index("_row")
    return (
        probe.sort("_probe")
        .join_asof(cum, left_on="_probe", right_on=MVT, by=group, strategy="backward")
        .sort("_row")
        .get_column("_cum")
        .fill_null(0)
    )


def _counts_in_window(
    keys: pl.DataFrame,
    events: pl.DataFrame,
    group: list[str],
    minutes: int,
    forward: bool,
    name: str,
) -> pl.DataFrame:
    """`keys` satirlarinin her biri icin `events` icindeki pencere sayimi.

    Pencere tanimlari (esitlik-guvenli, acikca yari-acik):

    - geri:  ``(t - W, t]``  -- satirin kendisini ve t anindaki esitlerini **sayar**
    - ileri: ``(t, t + W]``  -- satirin kendisini ve t anindaki esitlerini **saymaz**

    `keys` ile `events` farkli olabilir: orn. kalkis satirlari icin inisleri saymak.
    """
    cum = _cumulative_by_time(events, group)
    delta = pl.duration(minutes=minutes)
    here = _cum_at(keys, cum, group, pl.col(MVT))
    if forward:
        other = _cum_at(keys, cum, group, pl.col(MVT) + delta)
        counts = other - here
    else:
        other = _cum_at(keys, cum, group, pl.col(MVT) - delta)
        counts = here - other
    return keys.with_columns(counts.cast(pl.Int32).alias(name))


def runway_features(mvt: pl.DataFrame) -> pl.DataFrame:
    """Pist servis hizi ve kalkis sirasi oznitelikleri.

    Girdi: tek bir veri setinin (egitim ya da siralama) TUM hareketleri — hem DEP hem ARR.
    Cikti: her DEP satiri icin oznitelikler, `MVT_ID_mvt` ile anahtarlanmis.
    """
    dep = mvt.filter(pl.col(PHASE) == "DEP").sort(MVT)

    # ardisik kalkislar arasi bosluk = pistin o andaki servis araligi
    dep = dep.with_columns(
        onceki_kalkis_sn=(pl.col(MVT) - pl.col(MVT).shift(1).over([APT, RWY]))
        .dt.total_seconds()
        .cast(pl.Float32),
        sonraki_kalkis_sn=(pl.col(MVT).shift(-1).over([APT, RWY]) - pl.col(MVT))
        .dt.total_seconds()
        .cast(pl.Float32),
    )
    # son 5 kalkis araliginin ortalamasi: pistin anlik kapasitesi
    dep = dep.with_columns(
        pist_servis_araligi_sn=pl.col("onceki_kalkis_sn")
        .rolling_mean(window_size=5, min_samples=2)
        .over([APT, RWY])
        .cast(pl.Float32)
    )

    for w in WINDOWS_MIN:
        dep = _counts_in_window(dep, dep, [APT, RWY], w, False, f"pist_kalkis_onceki_{w}dk")
        dep = _counts_in_window(dep, dep, [APT, RWY], w, True, f"pist_kalkis_sonraki_{w}dk")

    return dep


def airport_features(mvt: pl.DataFrame, dep: pl.DataFrame) -> pl.DataFrame:
    """Havalimani genelinde trafik baskisi: kalkis ve inis yogunlugu.

    Inis sayimlari ozellikle degerli: varis satirlari siralama setinde hic
    bosaltilmamis (D09), yani Ocak/Temmuz 2026'da da tam olarak hesaplanabilir.
    Inen ucaklar taxiway'i ve standlari isgal eder, kalkis akisini yavaslatir.
    """
    arr = mvt.filter(pl.col(PHASE) == "ARR").select(APT, MVT).sort(MVT)
    dep_all = dep.select("MVT_ID_mvt", APT, MVT).sort(MVT)

    out = dep_all
    for w in WINDOWS_MIN:
        out = _counts_in_window(out, arr, [APT], w, False, f"apt_inis_onceki_{w}dk")
        out = _counts_in_window(out, arr, [APT], w, True, f"apt_inis_sonraki_{w}dk")
        out = _counts_in_window(out, dep_all, [APT], w, False, f"apt_kalkis_onceki_{w}dk")
        out = _counts_in_window(out, dep_all, [APT], w, True, f"apt_kalkis_sonraki_{w}dk")

    # inis/kalkis dengesi: yuzeyin hangi akisa tahsis edildigini gosterir
    out = out.with_columns(
        inis_kalkis_orani_30dk=(
            pl.col("apt_inis_onceki_30dk")
            / (pl.col("apt_kalkis_onceki_30dk") + pl.col("apt_inis_onceki_30dk")).replace(0, None)
        ).cast(pl.Float32)
    )
    return out.drop(APT, MVT)


def taxi_in_pressure(mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30) -> pl.DataFrame:
    """Son varislarin taxi-in medyani = yuzeyin o andaki tikanikligi.

    Bu ozniteligin degeri, **siralama setinde de dolu olmasidir**: varis satirlarinin
    hicbir alani bosaltilmamis (D09), dolayisiyla Ocak/Temmuz 2026'da da hesaplanabilir.
    Yuzey tikanikligi kalkis ve varis akisi arasinda ortaktir; canli bir gostergedir.
    """
    arr = (
        mvt.filter((pl.col(PHASE) == "ARR") & pl.col("TAXITIME_SEC_mvt").is_not_null())
        .select(APT, MVT, "TAXITIME_SEC_mvt")
        .sort(MVT)
    )
    if arr.height == 0:
        return dep.select("MVT_ID_mvt").with_columns(
            varis_taxi_medyan=pl.lit(None, dtype=pl.Float32),
            varis_taxi_sayi=pl.lit(0, dtype=pl.Int32),
        )

    # her havalimani-zaman penceresi icin medyan: group_by_dynamic ile ozetleyip asof birlestir
    binned = (
        arr.group_by_dynamic(MVT, every="10m", period=f"{minutes}m", group_by=APT)
        .agg(
            varis_taxi_medyan=pl.col("TAXITIME_SEC_mvt").median().cast(pl.Float32),
            varis_taxi_sayi=pl.len().cast(pl.Int32),
        )
        .sort(MVT)
    )
    return (
        dep.select("MVT_ID_mvt", APT, MVT)
        .sort(MVT)
        .join_asof(binned, on=MVT, by=APT, strategy="backward")
        .drop(APT, MVT)
    )


def runway_configuration(mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30) -> pl.DataFrame:
    """Pist konfigurasyonu cikarimi: +-30 dk icinde kullanimda olan pistlerin kumesi.

    Veride konfigurasyon alani yok; ama hangi pistlerin es zamanli kullanildigi
    konfigurasyonu belirler ve taxi mesafelerini topluca degistirir.
    """
    used = (
        mvt.filter(pl.col(RWY).is_not_null())
        .select(APT, MVT, RWY, PHASE)
        .with_columns(saat=pl.col(MVT).dt.truncate(f"{minutes}m"))
    )
    config = (
        used.group_by(APT, "saat")
        .agg(
            kalkis_pistleri=pl.col(RWY).filter(pl.col(PHASE) == "DEP")
            .unique().sort().str.join("+"),
            inis_pistleri=pl.col(RWY).filter(pl.col(PHASE) == "ARR")
            .unique().sort().str.join("+"),
            aktif_pist_sayisi=pl.col(RWY).n_unique().cast(pl.Int8),
        )
    )
    return (
        dep.select("MVT_ID_mvt", APT, MVT)
        .with_columns(saat=pl.col(MVT).dt.truncate(f"{minutes}m"))
        .join(config, on=[APT, "saat"], how="left")
        .drop(APT, MVT, "saat")
    )


def build(mvt: pl.DataFrame) -> pl.DataFrame:
    """Tum tikaniklik ozniteliklerini uretir; DEP satirlari icin tek tablo dondurur."""
    dep = runway_features(mvt)
    out = dep
    for part in (
        airport_features(mvt, dep),
        taxi_in_pressure(mvt, dep),
        runway_configuration(mvt, dep),
    ):
        out = out.join(part, on="MVT_ID_mvt", how="left")
    return out
