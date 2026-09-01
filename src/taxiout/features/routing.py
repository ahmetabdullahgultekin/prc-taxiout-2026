"""Kalkis yonu, ATFM baskisi ve stand donusu oznitelikleri.

Literaturden dogrudan turetilmis (bkz. `docs/literature.md`):

- **Kalkis yonu / departure fix.** Lee, Malik ve Jung (Charlotte, 2016) "departure fix"i
  anlamli bir tahmin edici buluyor. Ayni cikis noktasina giden ardisik kalkislar rota ve
  girdap ayirmasi nedeniyle daha genis araliklarla salinir; bu da kuyrugu uzatir.
  Veride departure fix yok, `ADES_mvt` var: kalkis havalimanindan varis havalimanina
  buyuk-daire kerterizi hesaplanip sektore yuvarlanir.

- **Asagi-akis kisitlari (ATFM).** Idris ve ark. (Logan, 2002) dort ana faktorden biri
  olarak "downstream restrictions"i sayiyor. Veride ATFM slotu yok, ama `IOBT_flt`
  (ilk planlanan blok saati) ve `LOBT_flt` (son bilinen blok saati) var: ikisi
  arasindaki suruklenme, ucusun yeniden zamanlanip zamanlanmadiginin dogrudan izidir.

- **Stand donusu.** Ayni standa yeni inen bir ucak varsa push-back ve manevra alani
  daralir; onceki varisin ne kadar once bloga girdigi olculur.
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
# Hareketin gerceklestigi havalimani; `pipeline.prepare_movements` ekler.
# `ADEP_mvt` DEGIL: o, ucusun kalkis havalimani (varislarda gelinen yer).
APT = "apt_mvt"
ADES = "ADES_mvt"
STAND = "STAND_mvt"
PHASE = "PHASE_mvt"

# Kerteriz sektor sayisi. 12 sektor = 30 derecelik dilimler; gercek SID gruplarindan
# kaba ama tek bir havalimanina ozel el ayari gerektirmeyen bir vekil.
SECTORS = 12
SECTOR_WINDOWS_MIN = (15, 30)


def _bearing_deg(lat1: pl.Expr, lon1: pl.Expr, lat2: pl.Expr, lon2: pl.Expr) -> pl.Expr:
    """Buyuk-daire baslangic kerterizi, derece (0-360)."""
    p1, p2 = lat1.radians(), lat2.radians()
    dl = (lon2 - lon1).radians()
    y = dl.sin() * p2.cos()
    x = p1.cos() * p2.sin() - p1.sin() * p2.cos() * dl.cos()
    return (pl.arctan2(y, x).degrees() + 360.0) % 360.0


def attach_bearing(dep: pl.DataFrame, coords: pl.DataFrame) -> pl.DataFrame:
    """Kalkis kerterizi, sektoru ve buyuk-daire mesafesini ekler."""
    origin = coords.rename({"icao": APT, "enlem": "_lat1", "boylam": "_lon1"}).select(
        APT, "_lat1", "_lon1"
    )
    dest = coords.rename({"icao": ADES, "enlem": "_lat2", "boylam": "_lon2"}).select(
        ADES, "_lat2", "_lon2"
    )
    out = dep.join(origin, on=APT, how="left").join(dest, on=ADES, how="left")

    bearing = _bearing_deg(pl.col("_lat1"), pl.col("_lon1"), pl.col("_lat2"), pl.col("_lon2"))
    # haversine, km
    dlat = (pl.col("_lat2") - pl.col("_lat1")).radians()
    dlon = (pl.col("_lon2") - pl.col("_lon1")).radians()
    a = (dlat / 2).sin() ** 2 + pl.col("_lat1").radians().cos() * pl.col(
        "_lat2"
    ).radians().cos() * (dlon / 2).sin() ** 2
    return out.with_columns(
        kalkis_kerterizi=bearing.cast(pl.Float32),
        kalkis_sektoru=(bearing / (360.0 / SECTORS)).floor().cast(pl.Int8),
        ucus_mesafesi_km=(2 * 6371.0 * a.sqrt().arcsin()).cast(pl.Float32),
    ).drop("_lat1", "_lon1", "_lat2", "_lon2")


def sector_congestion(dep: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """Ayni yone giden kalkislarin penceredeki sayisi = departure-fix kuyrugu vekili.

    `attach_bearing` sonrasi cagrilmali. Sayim `congestion._counts_in_window` ile ayni
    esitlik-guvenli tanimi kullanir: geri pencere (t-W, t], kendini dahil eder.
    """
    from taxiout.features.congestion import _counts_in_window

    zaman = list(dict.fromkeys([anchor, MVT]))
    keys = dep.select("MVT_ID_mvt", APT, "kalkis_sektoru", *zaman).sort(anchor)
    out = keys
    for w in SECTOR_WINDOWS_MIN:
        out = _counts_in_window(
            out, keys, [APT, "kalkis_sektoru"], w, False,
            f"sektor_kalkis_onceki_{w}dk", anchor, MVT,
        )
    # ayni sektore giden kalkislarin havalimani genelindeki kalkislara orani:
    # yuzeyin ne kadarinin ayni cikisa yigildigini gosterir
    return out.drop(APT, "kalkis_sektoru", *zaman)


def atfm_pressure(dep: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """Plan suruklenmesi: ucus yeniden zamanlandi mi, ne kadar?

    `lobt_kalkis_farki_sn` cipaya baglidir: nedensel modda kalkis saatini kullanmak
    dogrudan hedefi sizdirirdi.
    """
    cols = dep.columns
    exprs = []
    if "IOBT_flt" in cols and "LOBT_flt" in cols:
        exprs.append(
            (pl.col("LOBT_flt") - pl.col("IOBT_flt")).dt.total_seconds()
            .cast(pl.Float32).alias("atfm_suruklenme_sn")
        )
    if "LOBT_flt" in cols:
        exprs.append(
            (pl.col(anchor) - pl.col("LOBT_flt")).dt.total_seconds()
            .cast(pl.Float32).alias("lobt_cipa_farki_sn")
        )
    if "ADES_FILED_flt" in cols and ADES in cols:
        # dosyalanan varis ile gerceklesen farkliysa ucus yonlendirilmis demektir
        exprs.append(
            (pl.col("ADES_FILED_flt") != pl.col(ADES)).alias("yonlendirildi")
        )
    return dep.with_columns(exprs) if exprs else dep


def stand_turnaround(
    mvt: pl.DataFrame, dep: pl.DataFrame, anchor: str = MVT
) -> pl.DataFrame:
    """Ayni standa en son inen ucak ne kadar once bloga girdi.

    Yeni inmis bir ucak stand cevresini ve push-back alanini mesgul eder.
    """
    arr = (
        mvt.filter((pl.col(PHASE) == "ARR") & pl.col(STAND).is_not_null())
        .select(APT, STAND, _varis_blok=pl.col("BLOCK_TIME_UTC_mvt"))
        .filter(pl.col("_varis_blok").is_not_null())
        .sort("_varis_blok")
    )
    if arr.height == 0:
        return dep.select("MVT_ID_mvt").with_columns(
            stand_donus_sn=pl.lit(None, dtype=pl.Float32)
        )
    return (
        dep.select("MVT_ID_mvt", APT, STAND, _cipa=pl.col(anchor))
        .sort("_cipa")
        .join_asof(
            arr, left_on="_cipa", right_on="_varis_blok", by=[APT, STAND],
            strategy="backward",
        )
        .with_columns(
            stand_donus_sn=(pl.col("_cipa") - pl.col("_varis_blok")).dt.total_seconds()
            .cast(pl.Float32)
        )
        .select("MVT_ID_mvt", "stand_donus_sn")
    )


def build(
    mvt: pl.DataFrame, dep: pl.DataFrame, coords: pl.DataFrame | None, anchor: str = MVT
) -> pl.DataFrame:
    """Tum yonlendirme ozniteliklerini `dep` uzerine ekler.

    `anchor`, `congestion.build` ile ayni anlama gelir: nedensel modda blok
    cozulme anidir.
    """
    out = atfm_pressure(dep, anchor)
    if coords is not None and ADES in out.columns:
        out = attach_bearing(out, coords)
        out = out.join(sector_congestion(out, anchor), on="MVT_ID_mvt", how="left")
    return out.join(stand_turnaround(mvt, out, anchor), on="MVT_ID_mvt", how="left")
