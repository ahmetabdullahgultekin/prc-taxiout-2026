"""Yonlendirme ozniteliklerinin dogrulanmasi.

Kerteriz ve mesafe formulleri sessizce yanlis olabilir: isaret hatasi ya da
derece/radyan karisikligi makul gorunen ama tamamen yanlis sayilar uretir. Bu yuzden
polars ifadeleri, ayni formulun bagimsiz saf-python uygulamasiyla karsilastirilir.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import polars as pl
import pytest

from taxiout.features import routing

# OurAirports'tan gercek koordinatlar
COORDS = pl.DataFrame(
    {
        "icao": ["EDDF", "EGLL", "LTFM", "LTAI", "EHAM"],
        "enlem": [50.026706, 51.470748, 41.274874, 36.898701, 52.308601],
        "boylam": [8.55835, -0.459909, 28.732136, 30.800501, 4.76389],
    }
)


def _ref_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bagimsiz referans: standart buyuk-daire baslangic kerterizi."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _ref_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _dep(pairs: list[tuple[str, str]]) -> pl.DataFrame:
    start = datetime(2025, 5, 1, 8, 0)
    return pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(len(pairs))),
            "ADEP_mvt": [a for a, _ in pairs],
            "ADES_mvt": [b for _, b in pairs],
            "MVT_TIME_UTC_mvt": [start + timedelta(minutes=3 * i) for i in range(len(pairs))],
        }
    )


@pytest.mark.parametrize(
    "origin,dest",
    [("EDDF", "EGLL"), ("LTFM", "LTAI"), ("EHAM", "LTFM"), ("LTAI", "EDDF")],
)
def test_bearing_and_distance_match_reference_implementation(origin: str, dest: str) -> None:
    out = routing.attach_bearing(_dep([(origin, dest)]), COORDS)
    row = COORDS.filter(pl.col("icao") == origin).row(0, named=True)
    row2 = COORDS.filter(pl.col("icao") == dest).row(0, named=True)
    expected_b = _ref_bearing(row["enlem"], row["boylam"], row2["enlem"], row2["boylam"])
    expected_d = _ref_distance_km(row["enlem"], row["boylam"], row2["enlem"], row2["boylam"])
    assert out["kalkis_kerterizi"][0] == pytest.approx(expected_b, abs=0.01)
    assert out["ucus_mesafesi_km"][0] == pytest.approx(expected_d, rel=1e-4)


def test_bearing_directions_are_physically_sensible() -> None:
    """Yon duygusu kontrolu: formul dogru ama eksen ters olsaydi bu test yakalardi."""
    out = routing.attach_bearing(_dep([("EDDF", "EGLL"), ("LTFM", "LTAI")]), COORDS)
    frankfurt_to_london = out["kalkis_kerterizi"][0]
    istanbul_to_antalya = out["kalkis_kerterizi"][1]
    assert 260 < frankfurt_to_london < 310, "Londra Frankfurt'un batisinda"
    assert 130 < istanbul_to_antalya < 200, "Antalya Istanbul'un guneyinde"


def test_sector_is_in_range() -> None:
    out = routing.attach_bearing(
        _dep([("EDDF", "EGLL"), ("LTFM", "LTAI"), ("EHAM", "LTFM"), ("LTAI", "EDDF")]), COORDS
    )
    sectors = out["kalkis_sektoru"].to_list()
    assert all(0 <= s < routing.SECTORS for s in sectors)


def test_unknown_destination_yields_null_not_crash() -> None:
    """Varis havalimani referans tablosunda yoksa satir yine de uretilmeli."""
    out = routing.attach_bearing(_dep([("EDDF", "ZZZZ")]), COORDS)
    assert out.height == 1
    assert out["kalkis_kerterizi"][0] is None


def test_sector_congestion_counts_only_same_direction() -> None:
    """Ayni yone giden komsular sayilmali, farkli yone gidenler sayilmamali."""
    start = datetime(2025, 5, 1, 8, 0)
    # ucu de EDDF'ten: ikisi Londra'ya (ayni sektor), biri Antalya'ya (farkli sektor)
    dep = pl.DataFrame(
        {
            "MVT_ID_mvt": [0, 1, 2],
            "ADEP_mvt": ["EDDF"] * 3,
            "ADES_mvt": ["EGLL", "LTAI", "EGLL"],
            "MVT_TIME_UTC_mvt": [start, start + timedelta(minutes=2), start + timedelta(minutes=4)],
        }
    )
    out = routing.attach_bearing(dep, COORDS)
    counts = routing.sector_congestion(out).sort("MVT_ID_mvt")
    # son ucus (id=2) Londra yonunde; 15 dk geriye bakinca kendisi + id=0 = 2
    assert counts.filter(pl.col("MVT_ID_mvt") == 2)["sektor_kalkis_onceki_15dk"][0] == 2
    # Antalya ucusu (id=1) tek basina kendi sektorunde
    assert counts.filter(pl.col("MVT_ID_mvt") == 1)["sektor_kalkis_onceki_15dk"][0] == 1


def test_stand_turnaround_measures_time_since_previous_arrival() -> None:
    start = datetime(2025, 5, 1, 8, 0)
    mvt = pl.DataFrame(
        {
            "ADEP_mvt": ["EDDF", "EDDF"],
            "STAND_mvt": ["A1", "A1"],
            "PHASE_mvt": ["ARR", "ARR"],
            "BLOCK_TIME_UTC_mvt": [start, start + timedelta(minutes=40)],
        }
    )
    dep = pl.DataFrame(
        {
            "MVT_ID_mvt": [10],
            "ADEP_mvt": ["EDDF"],
            "STAND_mvt": ["A1"],
            "MVT_TIME_UTC_mvt": [start + timedelta(minutes=50)],
        }
    )
    out = routing.stand_turnaround(mvt, dep)
    # en son varis 40. dakikada geldi, kalkis 50. dakikada -> 10 dk = 600 sn
    assert out["stand_donus_sn"][0] == pytest.approx(600.0)


def test_atfm_drift_is_signed_difference() -> None:
    start = datetime(2025, 5, 1, 8, 0)
    dep = pl.DataFrame(
        {
            "MVT_ID_mvt": [0],
            "MVT_TIME_UTC_mvt": [start + timedelta(minutes=20)],
            "IOBT_flt": [start],
            "LOBT_flt": [start + timedelta(minutes=12)],
        }
    )
    out = routing.atfm_pressure(dep)
    assert out["atfm_suruklenme_sn"][0] == pytest.approx(720.0)  # 12 dk geri itilmis
    assert out["lobt_cipa_farki_sn"][0] == pytest.approx(480.0)
