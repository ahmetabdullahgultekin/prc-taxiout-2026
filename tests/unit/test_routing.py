"""Validation of the routing features.

Bearing and distance formulas can be wrong silently: a sign error or a degree/radian mix-up
produces numbers that look plausible and are completely wrong. So the polars expressions
are compared against an independent pure-python implementation of the same formula.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import polars as pl
import pytest

from taxiout.features import routing

# real coordinates from OurAirports
COORDS = pl.DataFrame(
    {
        "icao": ["EDDF", "EGLL", "LTFM", "LTAI", "EHAM"],
        "latitude": [50.026706, 51.470748, 41.274874, 36.898701, 52.308601],
        "longitude": [8.55835, -0.459909, 28.732136, 30.800501, 4.76389],
    }
)


def _ref_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Independent reference: the standard great-circle initial bearing."""
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
            "apt_mvt": [a for a, _ in pairs],
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
    lat1, lon1 = row["latitude"], row["longitude"]
    lat2, lon2 = row2["latitude"], row2["longitude"]
    expected_b = _ref_bearing(lat1, lon1, lat2, lon2)
    expected_d = _ref_distance_km(lat1, lon1, lat2, lon2)
    assert out["departure_bearing"][0] == pytest.approx(expected_b, abs=0.01)
    assert out["flight_distance_km"][0] == pytest.approx(expected_d, rel=1e-4)


def test_bearing_directions_are_physically_sensible() -> None:
    """A sense-of-direction check: if the formula were right but the axis flipped, this
    test would catch it."""
    out = routing.attach_bearing(_dep([("EDDF", "EGLL"), ("LTFM", "LTAI")]), COORDS)
    frankfurt_to_london = out["departure_bearing"][0]
    istanbul_to_antalya = out["departure_bearing"][1]
    assert 260 < frankfurt_to_london < 310, "London is west of Frankfurt"
    assert 130 < istanbul_to_antalya < 200, "Antalya is south of Istanbul"


def test_sector_is_in_range() -> None:
    out = routing.attach_bearing(
        _dep([("EDDF", "EGLL"), ("LTFM", "LTAI"), ("EHAM", "LTFM"), ("LTAI", "EDDF")]), COORDS
    )
    sectors = out["departure_sector"].to_list()
    assert all(0 <= s < routing.SECTORS for s in sectors)


def test_unknown_destination_yields_null_not_crash() -> None:
    """If the arrival airport is missing from the reference table the row must still be
    produced."""
    out = routing.attach_bearing(_dep([("EDDF", "ZZZZ")]), COORDS)
    assert out.height == 1
    assert out["departure_bearing"][0] is None


def test_sector_congestion_counts_only_same_direction() -> None:
    """Neighbours going the same way must count, ones going elsewhere must not."""
    start = datetime(2025, 5, 1, 8, 0)
    # all three from EDDF: two to London (same sector), one to Antalya (different sector)
    dep = pl.DataFrame(
        {
            "MVT_ID_mvt": [0, 1, 2],
            "apt_mvt": ["EDDF"] * 3,
            "ADES_mvt": ["EGLL", "LTAI", "EGLL"],
            "MVT_TIME_UTC_mvt": [start, start + timedelta(minutes=2), start + timedelta(minutes=4)],
        }
    )
    out = routing.attach_bearing(dep, COORDS)
    counts = routing.sector_congestion(out).sort("MVT_ID_mvt")
    # the last flight (id=2) heads for London; looking 15 min back gives itself + id=0 = 2
    assert counts.filter(pl.col("MVT_ID_mvt") == 2)["sector_dep_prev_15m"][0] == 2
    # the Antalya flight (id=1) is alone in its own sector
    assert counts.filter(pl.col("MVT_ID_mvt") == 1)["sector_dep_prev_15m"][0] == 1


def test_stand_turnaround_measures_time_since_previous_arrival() -> None:
    start = datetime(2025, 5, 1, 8, 0)
    mvt = pl.DataFrame(
        {
            "apt_mvt": ["EDDF", "EDDF"],
            "STAND_mvt": ["A1", "A1"],
            "PHASE_mvt": ["ARR", "ARR"],
            "BLOCK_TIME_UTC_mvt": [start, start + timedelta(minutes=40)],
        }
    )
    dep = pl.DataFrame(
        {
            "MVT_ID_mvt": [10],
            "apt_mvt": ["EDDF"],
            "STAND_mvt": ["A1"],
            "MVT_TIME_UTC_mvt": [start + timedelta(minutes=50)],
        }
    )
    out = routing.stand_turnaround(mvt, dep)
    # the last arrival came in at minute 40, the departure is at minute 50 -> 10 min = 600 s
    assert out["stand_turnaround_sec"][0] == pytest.approx(600.0)


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
    assert out["atfm_drift_sec"][0] == pytest.approx(720.0)  # pushed back by 12 min
    assert out["lobt_anchor_gap_sec"][0] == pytest.approx(480.0)
