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

## Iki cipa: retrospektif ve nedensel

Ayni kod iki farkli modeli uretir; fark **oznitelikleri hangi ana bagladigimizdir**:

| | cipa | ileri pencere | degerlendirilebildigi yer |
|---|---|---|---|
| **retrospektif** | kalkis ani (`MVT_TIME_UTC_mvt`) | var | siralama seti dahil her yerde |
| **nedensel** | blok cozulme ani (`BLOCK_TIME_UTC_mvt`) | yok | blok saatinin bilindigi yerde |

Retrospektif model yarisma gonderimidir; ayrica post-ops KPI hesabi ve eksik veri
doldurma icin kullanilir. Nedensel model A-CDM / TSAT / DMAN gibi gercek zamanli
kararlarin modelidir ve yalnizca makalede raporlanir.

Ikisi ayni dogrulama kumesinde (2025 Ocak + Temmuz) karsilastirilabilir, cunku orada
her iki cipa da bilinir. Aradaki RMSE farki **retrospektif gozlenebilirligin bilgi
degeridir** ve gercek zamanli sistemler icin ulasilabilir iyilesmenin ust sinirini verir.
Idris ve ark.'nin kuyruk degiskeni operasyonda tahmin edilmek zorunda; burada o farki
sayiyla ifade ediyoruz (bkz. `docs/literature.md` §5.2).
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
# Hareketin gerceklestigi havalimani; `pipeline.prepare_movements` ekler.
# `ADEP_mvt` DEGIL: o, ucusun kalkis havalimani (varislarda gelinen yer).
APT = "apt_mvt"
RWY = "RUNWAY_mvt"
PHASE = "PHASE_mvt"
BLOCK = "BLOCK_TIME_UTC_mvt"

# Geriye ve ileriye bakis pencereleri (dakika). Model hangisinin isine yaradigini secer.
WINDOWS_MIN = (5, 10, 15, 30, 60)


def _cumulative_by_time(events: pl.DataFrame, group: list[str], at: str) -> pl.DataFrame:
    """(grup, zaman) -> o ana KADAR ve o an DAHIL toplam olay sayisi.

    Esit zaman damgalari icin tek bir deger uretir. Bu onemli: veri bazi
    havalimanlarinda HH:MM hassasiyetinde olabiliyor (M14), yani ayni saniyede
    onlarca hareket gorunur. Satir sirasina dayali bir sayac o durumda esitler
    arasinda tutarsiz sonuc verir.
    """
    return (
        events.filter(pl.col(at).is_not_null())
        .group_by([*group, at])
        .agg(_k=pl.len())
        .sort(at)
        .with_columns(_cum=pl.col("_k").cum_sum().over(group))
        .select(*group, at, "_cum")
        .sort(at)
    )


def _cum_at(
    keys: pl.DataFrame, cum: pl.DataFrame, group: list[str], probe: pl.Expr, event_at: str
) -> pl.Series:
    """`probe` ifadesinin verdigi ana kadarki kumulatif sayaci her anahtar satiri icin dondurur."""
    frame = keys.select(*group, _probe=probe).with_row_index("_row")
    return (
        frame.sort("_probe")
        .join_asof(cum, left_on="_probe", right_on=event_at, by=group, strategy="backward")
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
    key_at: str = MVT,
    event_at: str | None = None,
) -> pl.DataFrame:
    """`keys` satirlarinin her biri icin `events` icindeki pencere sayimi.

    Pencere tanimlari (esitlik-guvenli, acikca yari-acik):

    - geri:  ``(t - W, t]``  -- ayni ana denk gelen olaylari **sayar**
    - ileri: ``(t, t + W]``  -- ayni ana denk gelen olaylari **saymaz**

    `key_at` sorgu aninin, `event_at` sayilan olaylarin zaman kolonudur ve **farkli
    olabilirler**. Nedensel modda soru sudur: "bu ucak blok cozerken (key_at =
    BLOCK_TIME) o ana kadar pistten kac ucak kalkmisti (event_at = MVT_TIME)?"
    Retrospektif modda ikisi de kalkis anidir.
    """
    event_at = event_at or key_at
    cum = _cumulative_by_time(events, group, event_at)
    delta = pl.duration(minutes=minutes)
    here = _cum_at(keys, cum, group, pl.col(key_at), event_at)
    other = _cum_at(
        keys, cum, group, pl.col(key_at) + delta if forward else pl.col(key_at) - delta, event_at
    )
    counts = (other - here) if forward else (here - other)
    return keys.with_columns(counts.cast(pl.Int32).alias(name))


def runway_features(mvt: pl.DataFrame, anchor: str = MVT, forward: bool = True) -> pl.DataFrame:
    """Pist servis hizi ve kalkis sirasi oznitelikleri.

    Girdi: tek bir veri setinin (egitim ya da siralama) TUM hareketleri — hem DEP hem ARR.
    Cikti: her DEP satiri icin oznitelikler, `MVT_ID_mvt` ile anahtarlanmis.

    `anchor` ozniteliklerin baglandigi ani secer; `forward=False` nedensel modda ileriye
    bakan pencereleri kapatir (modul dokumanindaki tabloya bakiniz).
    """
    dep = mvt.filter(pl.col(PHASE) == "DEP").filter(pl.col(anchor).is_not_null()).sort(anchor)

    # ardisik kalkislar arasi bosluk = pistin o andaki servis araligi
    dep = dep.with_columns(
        onceki_kalkis_sn=(pl.col(anchor) - pl.col(anchor).shift(1).over([APT, RWY]))
        .dt.total_seconds()
        .cast(pl.Float32),
    )
    if forward:
        dep = dep.with_columns(
            sonraki_kalkis_sn=(pl.col(anchor).shift(-1).over([APT, RWY]) - pl.col(anchor))
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
        dep = _counts_in_window(
            dep, dep, [APT, RWY], w, False, f"pist_kalkis_onceki_{w}dk", anchor, MVT
        )
        if forward:
            dep = _counts_in_window(
                dep, dep, [APT, RWY], w, True, f"pist_kalkis_sonraki_{w}dk", anchor, MVT
            )

    return dep


def airport_features(
    mvt: pl.DataFrame, dep: pl.DataFrame, anchor: str = MVT, forward: bool = True
) -> pl.DataFrame:
    """Havalimani genelinde trafik baskisi: kalkis ve inis yogunlugu.

    Inis sayimlari ozellikle degerli: varis satirlari siralama setinde hic
    bosaltilmamis (D09), yani Ocak/Temmuz 2026'da da tam olarak hesaplanabilir.
    Inen ucaklar taxiway'i ve standlari isgal eder, kalkis akisini yavaslatir.
    """
    arr = mvt.filter(pl.col(PHASE) == "ARR").select(APT, MVT).sort(MVT)
    # anchor ile MVT ayni olabilir; tekrarli secim polars'ta hata verir
    zaman_kolonlari = list(dict.fromkeys([anchor, MVT]))
    dep_all = dep.select("MVT_ID_mvt", APT, *zaman_kolonlari).sort(anchor)

    out = dep_all
    for w in WINDOWS_MIN:
        out = _counts_in_window(out, arr, [APT], w, False, f"apt_inis_onceki_{w}dk", anchor, MVT)
        out = _counts_in_window(
            out, dep_all, [APT], w, False, f"apt_kalkis_onceki_{w}dk", anchor, MVT
        )
        if forward:
            out = _counts_in_window(
                out, arr, [APT], w, True, f"apt_inis_sonraki_{w}dk", anchor, MVT
            )
            out = _counts_in_window(
                out, dep_all, [APT], w, True, f"apt_kalkis_sonraki_{w}dk", anchor, MVT
            )

    # inis/kalkis dengesi: yuzeyin hangi akisa tahsis edildigini gosterir
    out = out.with_columns(
        inis_kalkis_orani_30dk=(
            pl.col("apt_inis_onceki_30dk")
            / (pl.col("apt_kalkis_onceki_30dk") + pl.col("apt_inis_onceki_30dk")).replace(0, None)
        ).cast(pl.Float32)
    )
    return out.drop(APT, *zaman_kolonlari, strict=False)


def taxi_in_pressure(
    mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30, anchor: str = MVT
) -> pl.DataFrame:
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
        dep.select("MVT_ID_mvt", APT, _cipa=pl.col(anchor))
        .sort("_cipa")
        .join_asof(binned, left_on="_cipa", right_on=MVT, by=APT, strategy="backward")
        .select("MVT_ID_mvt", "varis_taxi_medyan", "varis_taxi_sayi")
    )


def runway_configuration(
    mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30, anchor: str = MVT
) -> pl.DataFrame:
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
        dep.select("MVT_ID_mvt", APT, _cipa=pl.col(anchor))
        .with_columns(saat=pl.col("_cipa").dt.truncate(f"{minutes}m"))
        .join(config, on=[APT, "saat"], how="left")
        .drop(APT, "_cipa", "saat")
    )


def build(mvt: pl.DataFrame, causal: bool = False) -> pl.DataFrame:
    """Tum tikaniklik ozniteliklerini uretir; DEP satirlari icin tek tablo dondurur.

    `causal=True` nedensel modu acar: oznitelikler kalkis anina degil **blok cozulme
    anina** baglanir ve ileriye bakan pencereler kapatilir. Bu mod yalnizca blok saati
    bilinen veride (2025) calisir ve siralama setine uygulanamaz — zaten amaci da o degil
    (modul dokumanindaki tabloya bakiniz).
    """
    anchor = BLOCK if causal else MVT
    forward = not causal
    dep = runway_features(mvt, anchor, forward)
    out = dep
    for part in (
        airport_features(mvt, dep, anchor, forward),
        taxi_in_pressure(mvt, dep, anchor=anchor),
        runway_configuration(mvt, dep, anchor=anchor),
    ):
        out = out.join(part, on="MVT_ID_mvt", how="left")
    return out
