"""Hareket havalimaninin dogru turetildigini dogrular.

Bu testlerin var olma nedeni somut bir hata. `ADEP_mvt` uzun sure "hareketin
havalimani" sanildi; gercekte **ucusun kalkis havalimani** ve varis satirlarinda
ucagin GELDIGI yeri gosteriyor (egitim setinde 1.582 farkli deger). Sonuc: bir
kalkisin cevresindeki inisleri sayarken, o havalimanina inenler yerine o
havalimanindan kalkmis olan uzak inisler sayiliyordu.

Sentetik fixture o donemde `ADEP_mvt`'yi her satirda yarisma havalimani yaptigi
icin hicbir test bunu goremedi. Fixture duzeltildi, bu testler de duzeltmeyi
yerinde tutuyor.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from taxiout.application import pipeline
from taxiout.features import congestion


def _frame() -> pl.DataFrame:
    """EDDF'te bir kalkis, EDDF'e LTFM'den bir inis, LTFM'de bir kalkis."""
    t0 = datetime(2025, 5, 1, 10, 0)
    return pl.DataFrame({
        "MVT_ID_mvt": [1, 2, 3],
        "PHASE_mvt": ["DEP", "ARR", "DEP"],
        "ADEP_mvt": ["EDDF", "LTFM", "LTFM"],   # ucusun kalkis havalimani
        "ADES_mvt": ["LTFM", "EDDF", "EGLL"],   # ucusun varis havalimani
        "RUNWAY_mvt": ["07L", "07R", "34L"],
        "STAND_mvt": ["A1", "B2", "C3"],
        "MVT_TIME_UTC_mvt": [t0, t0 - timedelta(minutes=5), t0],
        "BLOCK_TIME_UTC_mvt": [t0 - timedelta(minutes=15), t0, t0 - timedelta(minutes=12)],
        "TAXITIME_SEC_mvt": [900, 300, 720],
    })


def test_movement_airport_is_adep_for_departures_and_ades_for_arrivals() -> None:
    out = pipeline.prepare_movements(_frame()).sort("MVT_ID_mvt")
    assert out[pipeline.APT].to_list() == ["EDDF", "EDDF", "LTFM"]


def test_arrivals_are_counted_at_the_airport_they_landed_at() -> None:
    """Asil hata buydu: inis, geldigi havalimaninda degil indigi havalimaninda sayilmali.

    Ornekteki inis LTFM'den kalkip EDDF'e inmis. EDDF'teki kalkisin cevresinde
    sayilmali, LTFM'dekinin cevresinde degil.
    """
    mvt = pipeline.prepare_movements(_frame())
    dep = congestion.runway_features(mvt)
    out = congestion.airport_features(mvt, dep).join(
        dep.select("MVT_ID_mvt", pipeline.APT), on="MVT_ID_mvt"
    )
    eddf = out.filter(pl.col(pipeline.APT) == "EDDF")["apt_inis_onceki_15dk"][0]
    ltfm = out.filter(pl.col(pipeline.APT) == "LTFM")["apt_inis_onceki_15dk"][0]
    assert eddf == 1, "EDDF'e inen ucak EDDF kalkisinin cevresinde sayilmali"
    assert ltfm == 0, "o inis LTFM'de sayilmamali, oradan yalnizca kalkmis"


def test_grouping_on_adep_would_give_the_wrong_answer() -> None:
    """Negatif kontrol: eski (hatali) gruplama farkli bir sonuc uretiyor mu.

    Uretmiyorsa bu test hicbir seyi korumuyor demektir.
    """
    mvt = pipeline.prepare_movements(_frame())
    dogru = mvt.filter((pl.col("PHASE_mvt") == "ARR") & (pl.col(pipeline.APT) == "EDDF")).height
    hatali = mvt.filter((pl.col("PHASE_mvt") == "ARR") & (pl.col("ADEP_mvt") == "EDDF")).height
    assert dogru == 1
    assert hatali == 0
    assert dogru != hatali
