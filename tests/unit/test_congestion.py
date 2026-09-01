"""Tikaniklik ozniteliklerinin dogrulanmasi.

Pencere sayimi bu boru hattinin en hataya acik kismi: bir kayma ya da yanlis
pencere siniri, modeli sessizce bozar ve RMSE'de gorunmez. Bu yuzden vektorize
uygulama, ayni seyi apacik ama yavas hesaplayan kaba kuvvet referansiyla
karsilastirilir.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from taxiout.features import congestion


def _sample(n: int = 400, seed: int = 7) -> pl.DataFrame:
    import numpy as np

    rng = np.random.default_rng(seed)
    start = datetime(2025, 3, 1)
    apt = rng.choice(["EDDF", "LTFM"], n)
    rwy = rng.choice(["07L", "25R"], n)
    phase = rng.choice(["DEP", "ARR"], n)
    offs = np.sort(rng.integers(0, 6 * 3600, n))
    return pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(n)),
            "apt_mvt": apt,
            "RUNWAY_mvt": rwy,
            "STAND_mvt": rng.choice(["A1", "B2", "C3"], n),
            "PHASE_mvt": phase,
            "MVT_TIME_UTC_mvt": [start + timedelta(seconds=int(s)) for s in offs],
            "TAXITIME_SEC_mvt": rng.integers(200, 1500, n),
        }
    )


def _brute_count(rows, i, group_cols, minutes, forward):
    """Apacik referans: docstring'deki yari-acik tanimi dogrudan uygular, O(n^2).

    geri:  (t - W, t]   ileri: (t, t + W]
    """
    t = rows[i]["MVT_TIME_UTC_mvt"]
    key = tuple(rows[i][c] for c in group_cols)
    span = timedelta(minutes=minutes)
    total = 0
    for r in rows:
        if tuple(r[c] for c in group_cols) != key:
            continue
        u = r["MVT_TIME_UTC_mvt"]
        if forward:
            if t < u <= t + span:
                total += 1
        elif t - span < u <= t:
            total += 1
    return total


@pytest.mark.parametrize("minutes", [5, 15, 60])
@pytest.mark.parametrize("forward", [False, True])
def test_counts_in_window_matches_brute_force(minutes: int, forward: bool) -> None:
    df = _sample().filter(pl.col("PHASE_mvt") == "DEP")
    group = ["apt_mvt", "RUNWAY_mvt"]
    got = congestion._counts_in_window(df, df, group, minutes, forward, "n").sort("MVT_ID_mvt")

    rows = df.sort("MVT_ID_mvt").to_dicts()
    expected = [_brute_count(rows, i, group, minutes, forward) for i in range(len(rows))]
    assert got["n"].to_list() == expected


def test_forward_and_backward_are_not_identical() -> None:
    """Yon karistirilirsa test sessizce gecmesin diye negatif kontrol."""
    df = _sample().filter(pl.col("PHASE_mvt") == "DEP")
    group = ["apt_mvt", "RUNWAY_mvt"]
    back = congestion._counts_in_window(df, df, group, 15, False, "n").sort("MVT_ID_mvt")["n"]
    fwd = congestion._counts_in_window(df, df, group, 15, True, "n").sort("MVT_ID_mvt")["n"]
    assert back.to_list() != fwd.to_list()


def test_build_produces_one_row_per_departure() -> None:
    mvt = _sample()
    out = congestion.build(mvt)
    n_dep = mvt.filter(pl.col("PHASE_mvt") == "DEP").height
    assert out.height == n_dep
    assert out["MVT_ID_mvt"].n_unique() == n_dep


def test_build_has_no_target_column() -> None:
    """Oznitelik tablosu hedefi tasimamali; sizinti bu sekilde girer."""
    out = congestion.build(_sample())
    leaky = {"BLOCK_TIME_UTC_mvt"}
    assert not leaky & set(out.columns)


def test_taxi_in_pressure_is_available_without_departure_targets() -> None:
    """Siralama setinin kurgusu: DEP taxi sureleri bos, ARR dolu.

    Bu ozniteligin tum degeri o kosulda hesaplanabiliyor olmasindan geliyor.
    """
    mvt = _sample()
    blanked = mvt.with_columns(
        pl.when(pl.col("PHASE_mvt") == "DEP")
        .then(None)
        .otherwise(pl.col("TAXITIME_SEC_mvt"))
        .alias("TAXITIME_SEC_mvt")
    )
    dep = congestion.runway_features(blanked)
    out = congestion.taxi_in_pressure(blanked, dep)
    assert out["varis_taxi_medyan"].null_count() < out.height


@pytest.mark.parametrize("forward", [False, True])
def test_counts_are_correct_when_timestamps_are_minute_rounded(forward: bool) -> None:
    """HH:MM hassasiyeti: ayni dakikada onlarca hareket. Duzeltilen hata tam buydu.

    Satir sirasina dayali bir sayac esit zaman damgalari arasinda tutarsiz sonuc
    verir ve bu gercek veride istisna degil, bazi havalimanlarinda kural (M14).
    """
    import numpy as np

    rng = np.random.default_rng(3)
    n = 300
    start = datetime(2025, 3, 1)
    # saniyeleri sifirla: yogun esitlik uret
    offs = np.sort(rng.integers(0, 120, n) * 60)
    df = pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(n)),
            "apt_mvt": ["EDDF"] * n,
            "RUNWAY_mvt": rng.choice(["07L", "25R"], n),
            "PHASE_mvt": ["DEP"] * n,
            "MVT_TIME_UTC_mvt": [start + timedelta(seconds=int(s)) for s in offs],
        }
    )
    # esitlik gercekten var mi (testin kendi oncululunu dogrula)
    assert df["MVT_TIME_UTC_mvt"].n_unique() < n

    group = ["apt_mvt", "RUNWAY_mvt"]
    got = congestion._counts_in_window(df, df, group, 15, forward, "n").sort("MVT_ID_mvt")
    rows = df.sort("MVT_ID_mvt").to_dicts()
    expected = [_brute_count(rows, i, group, 15, forward) for i in range(len(rows))]
    assert got["n"].to_list() == expected


def _sample_with_block(n: int = 400, seed: int = 5) -> pl.DataFrame:
    """Blok saati de olan ornek: nedensel mod bunu gerektirir."""
    import numpy as np

    df = _sample(n, seed)
    rng = np.random.default_rng(seed)
    taxi = rng.integers(300, 1500, n)
    return df.with_columns(
        BLOCK_TIME_UTC_mvt=pl.col("MVT_TIME_UTC_mvt")
        - pl.duration(seconds=pl.Series(taxi.tolist()))
    )


def test_causal_mode_emits_no_forward_looking_features() -> None:
    """Nedensel modelin tek anlami bu: gelecege dair hicbir sey bilmemesi.

    Ileriye bakan bir kolon sizarsa model 'gercek zamanli' iddiasini kaybeder ve
    makaledeki karsilastirma anlamsizlasir. Bu yuzden kolon adlarindan denetlenir.
    """
    out = congestion.build(_sample_with_block(), causal=True)
    forward = [c for c in out.columns if "sonraki" in c]
    assert forward == [], f"nedensel modda ileriye bakan kolonlar var: {forward}"


def test_retrospective_mode_does_emit_forward_features() -> None:
    """Negatif kontrol: bayrak gercekten bir sey degistiriyor mu."""
    out = congestion.build(_sample_with_block(), causal=False)
    assert [c for c in out.columns if "sonraki" in c]


def test_causal_counts_are_anchored_at_pushback_not_takeoff() -> None:
    """Nedensel sayimlar blok cozulme anina baglanmali.

    Ayni satir icin iki mod farkli sayilar vermeli; ayni cikarsa cipa uygulanmamis
    demektir ve test sessizce gecerdi.
    """
    mvt = _sample_with_block()
    col = "pist_kalkis_onceki_30dk"
    geri = congestion.build(mvt, causal=True).select("MVT_ID_mvt", col).sort("MVT_ID_mvt")
    ileri = congestion.build(mvt, causal=False).select("MVT_ID_mvt", col).sort("MVT_ID_mvt")
    assert geri[col].to_list() != ileri[col].to_list()


def test_causal_window_counts_only_takeoffs_before_pushback() -> None:
    """Elle kurulmus vaka: blok cozulme anindan onceki kalkislar sayilmali."""
    start = datetime(2025, 6, 1, 12, 0)
    mvt = pl.DataFrame(
        {
            "MVT_ID_mvt": [0, 1, 2],
            "apt_mvt": ["EDDF"] * 3,
            "RUNWAY_mvt": ["18"] * 3,
            "STAND_mvt": ["A1"] * 3,
            "PHASE_mvt": ["DEP"] * 3,
            # 0 ve 1 erken kalkti; 2 ise 12:20'de blok cozup 12:40'ta kalkiyor
            "MVT_TIME_UTC_mvt": [
                start, start + timedelta(minutes=10), start + timedelta(minutes=40)
            ],
            "BLOCK_TIME_UTC_mvt": [
                start - timedelta(minutes=10),
                start,
                start + timedelta(minutes=20),
            ],
            "TAXITIME_SEC_mvt": [600, 600, 1200],
        }
    )
    out = congestion.build(mvt, causal=True).sort("MVT_ID_mvt")
    # id=2 icin: blok cozulme 12:20, geriye 30 dk -> (11:50, 12:20] araligindaki
    # kalkislar: 12:00 (id=0) ve 12:10 (id=1) = 2. Kendi kalkisi 12:40, sayilmamali.
    assert out.filter(pl.col("MVT_ID_mvt") == 2)["pist_kalkis_onceki_30dk"][0] == 2
