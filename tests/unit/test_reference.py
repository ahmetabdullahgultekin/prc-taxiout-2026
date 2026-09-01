"""Resmi ATXOT referansinin dogrulanmasi.

Bu modul, yarismayi duzenleyen kurumun kendi gostergesini yeniden uretme
iddiasinda. Iddia testle tutulmali: elle hesaplanabilir kucuk vakalar uzerinde
P10 ve gecerlilik kurali birebir dogrulanir.
"""

from __future__ import annotations

import polars as pl

from taxiout.domain import reference


def _frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows).with_columns(PHASE_mvt=pl.lit("DEP"))


def test_p10_matches_hand_computed_value() -> None:
    # 100..1090 arasi 100 deger; P10 (dogrusal interpolasyon) = 199.0
    taxis = list(range(100, 1100, 10))
    df = _frame(
        [
            {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": t}
            for t in taxis
        ]
    )
    tables = reference.fit_reference(df)
    got = tables["apt_stand_rwy"]["p10_apt_stand_rwy"][0]
    expected = pl.Series(taxis).quantile(0.10, interpolation="linear")
    assert abs(got - expected) < 1e-6


def test_validity_rule_needs_ten_flights_at_or_below_p10() -> None:
    """ATXOT s.15: P10'a esit ya da ondan kisa en az 10 ucus olmali."""
    # 12 ucus: P10'un altinda 10'dan az kalir -> gecersiz
    small = _frame(
        [
            {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": t}
            for t in range(300, 420, 10)
        ]
    )
    assert not reference.fit_reference(small)["apt_stand_rwy"]["gecerli_apt_stand_rwy"][0]

    # ayni degerden 20 ucus: hepsi P10'a esit -> gecerli
    flat = _frame(
        [
            {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": 400}
            for _ in range(20)
        ]
    )
    assert reference.fit_reference(flat)["apt_stand_rwy"]["gecerli_apt_stand_rwy"][0]


def test_official_filters_drop_impossible_taxi_times() -> None:
    """ATXOT s.13 adim 1: 120 dakikayi asanlar ve pozitif olmayanlar referansa girmez."""
    rows = [
        {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": 400}
        for _ in range(20)
    ]
    rows += [
        {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": 99_999},
        {"apt_mvt": "EDDF", "STAND_mvt": "A1", "RUNWAY_mvt": "18", "TAXITIME_SEC_mvt": -50},
    ]
    tables = reference.fit_reference(_frame(rows))
    assert tables["apt_stand_rwy"]["n_apt_stand_rwy"][0] == 20


def test_falls_back_when_combo_is_unseen() -> None:
    """Siralama setinde egitimde hic gorulmemis stand cikabilir; satir yine de tahmin edilmeli."""
    fit = _frame(
        [
            {"apt_mvt": "LTFM", "STAND_mvt": "A1", "RUNWAY_mvt": "34L", "TAXITIME_SEC_mvt": 500}
            for _ in range(30)
        ]
        + [
            {"apt_mvt": "LTFM", "STAND_mvt": "B9", "RUNWAY_mvt": "34L", "TAXITIME_SEC_mvt": 700}
            for _ in range(30)
        ]
    )
    tables = reference.fit_reference(fit)
    unseen = _frame(
        [{"apt_mvt": "LTFM", "STAND_mvt": "ZZ", "RUNWAY_mvt": "34L", "TAXITIME_SEC_mvt": None}]
    )
    out = reference.apply_reference(unseen, tables)
    assert out["referans_sn"][0] is not None
    assert out["referans_seviye"][0] == "apt_rwy"  # stand bilinmiyor, pist biliniyor


def test_most_specific_valid_level_wins() -> None:
    fit = _frame(
        [
            {"apt_mvt": "LSZH", "STAND_mvt": "A1", "RUNWAY_mvt": "28", "TAXITIME_SEC_mvt": 400}
            for _ in range(30)
        ]
        + [
            {"apt_mvt": "LSZH", "STAND_mvt": "B2", "RUNWAY_mvt": "28", "TAXITIME_SEC_mvt": 900}
            for _ in range(30)
        ]
    )
    tables = reference.fit_reference(fit)
    seen = _frame(
        [{"apt_mvt": "LSZH", "STAND_mvt": "A1", "RUNWAY_mvt": "28", "TAXITIME_SEC_mvt": None}]
    )
    out = reference.apply_reference(seen, tables)
    assert out["referans_seviye"][0] == "apt_stand_rwy"
    # havalimani geneli ~650 olurdu; en ozel seviye 400'u vermeli
    assert out["referans_sn"][0] < 500


def test_reference_is_below_typical_taxi_time() -> None:
    """Referans 'engelsiz' suredir: tanimi geregi tipik surenin altinda olmali."""
    import numpy as np

    rng = np.random.default_rng(11)
    taxis = 400 + rng.gamma(2.0, 120.0, 2000)
    df = _frame(
        [
            {"apt_mvt": "EHAM", "STAND_mvt": "D5", "RUNWAY_mvt": "24",
             "TAXITIME_SEC_mvt": float(t)}
            for t in taxis
        ]
    )
    tables = reference.fit_reference(df)
    applied = reference.apply_reference(df, tables)
    assert applied["referans_sn"][0] < applied["TAXITIME_SEC_mvt"].median()
