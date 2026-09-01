"""Generates synthetic data that imitates the STRUCTURE of the real data set.

The aim is fidelity, not speed: if the fixture does not reflect the real setup, the tests
verify the wrong thing. That cost us once already. In the first version `ADEP_mvt` was a
competition airport on every row; in reality it is not, and every arrival-derived feature
was grouped at the wrong airport, which no test could see.

The structural properties measured on the real data and reproduced here one for one
(`docs/facts.md` R01-R07):

- **10 airports**, not 11. LTAI (Antalya) is not in the data.
- `ADEP_mvt` is the **departure airport of the flight**, not the airport of the movement.
  On arrival rows it names the airport the aircraft came from, usually one outside the
  competition; it takes 1,582 distinct values in the training set.
- Movement airport = `ADEP_mvt` for DEP, `ADES_mvt` for ARR.
- The ranking set is **asymmetric**: 10 airports in January, only EDDF, EGLL, EHAM in
  July. January is 71% of the rows.
- The identity `MVT_TIME - BLOCK_TIME == TAXITIME` holds exactly.
- Timestamps are second-precision and **UTC-aware** (datetime[us, UTC]); the external
  data sources come back naive, so the joins need alignment.

Real data is NEVER written into this directory (entry condition F11).

    python tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

# The 10 airports in the real data set. LTAI is deliberately absent (R01).
AIRPORTS = ["EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LSZH", "LTFM"]

# In the ranking set July contains only these three (R03).
JULY_AIRPORTS = ["EDDF", "EGLL", "EHAM"]

# Airports outside the competition: where the arrivals come from and the departures go.
# There are 1,582 of them in reality; a handful is enough to carry the structure.
OUTSIDE = ["LTBA", "EGKK", "LFPO", "EDDL", "LIMC", "LOWW", "EKCH", "ESSA", "KJFK", "OMDB"]

TYPES = ["A320", "A321", "B738", "A20N", "B77W", "E195", "A359"]
WAKE = {"A320": "M", "A321": "M", "B738": "M", "A20N": "M", "B77W": "H", "E195": "M", "A359": "H"}


def build(
    start: datetime, days: int, per_day: int, seed: int, airports: list[str] | None = None
) -> pl.DataFrame:
    """Generates movement records for one period."""
    airports = airports or AIRPORTS
    rng = np.random.default_rng(seed)
    n = days * per_day

    # the airport where the movement ACTUALLY HAPPENS
    apt = rng.choice(airports, n)
    phase = rng.choice(["DEP", "ARR"], n)
    other = rng.choice(OUTSIDE + AIRPORTS, n)  # the far end

    # the real setup: DEP -> ADEP=movement apt, ADES=far end; ARR -> the other way round
    adep = np.where(phase == "DEP", apt, other)
    ades = np.where(phase == "DEP", other, apt)

    runways = np.array([f"{a[-2:]}L" if r else f"{a[-2:]}R"
                        for a, r in zip(apt, rng.random(n) < 0.5, strict=True)])
    # Stand identifiers come in two shapes in the real data and the fixture has to carry
    # both, otherwise the pier features are never exercised and the tests prove nothing
    # about them. Frankfurt, Schiphol and Paris label every stand with a pier letter and
    # a number (A11); Munich, Heathrow and Barcelona use bare numbers. Airports at an
    # even index here get letters, the rest get numbers.
    stand_no = rng.integers(1, 21, n)
    lettered = np.isin(apt, [a for i, a in enumerate(airports) if i % 2 == 0])
    piers = np.array(list("ABCD"))[rng.integers(0, 4, n)]
    stand = np.where(
        lettered,
        np.char.add(piers, stand_no.astype(str)),
        stand_no.astype(str),
    )
    actype = rng.choice(TYPES, n)

    offsets = rng.integers(0, days * 86400, n)
    block = [start + timedelta(seconds=int(s)) for s in offsets]

    # taxi-out: a stand/runway baseline plus a queueing tail; taxi-in is shorter
    # The pier carries real signal in the fixture too, not just the number: at a real
    # airport the apron a stand sits on decides most of the taxi distance.
    pier_penalty = np.where(lettered, np.searchsorted(list("ABCD"), piers) * 45, 0)
    base = 300 + stand_no * 6 + pier_penalty + np.char.endswith(runways, "R") * 120
    taxi = np.where(phase == "DEP", base + rng.gamma(2.0, 90.0, n), 240 + rng.gamma(1.5, 40.0, n))
    taxi = np.round(taxi).astype(int)

    # DEP: take-off = block + taxi. ARR: landing = block - taxi (it lands first, then blocks in)
    mvt = [b + timedelta(seconds=int(t)) if p == "DEP" else b - timedelta(seconds=int(t))
           for b, t, p in zip(block, taxi, phase, strict=True)]

    matched = rng.random(n) < 0.985  # 98.5% in reality (R08)
    aobt3 = [b + timedelta(seconds=float(e)) if m else None
             for b, e, m in zip(block, rng.normal(0, 110, n), matched, strict=True)]
    opt_block = [b if m else None for b, m in zip(block, matched, strict=True)]
    opt_fid = [int(i) if m else None for i, m in enumerate(matched)]

    frame = pl.DataFrame({
        "MVT_ID_mvt": np.arange(seed * 10**7, seed * 10**7 + n),
        "FLIGHT_ID_mvt": opt_fid,
        "FLIGHT_mvt": [f"XX{i % 9000 + 100}" for i in range(n)],
        "FLIGHT_RULE_mvt": ["I"] * n,
        "ADEP_mvt": adep,
        "ADES_mvt": ades,
        "PHASE_mvt": phase,
        "MVT_TIME_UTC_mvt": mvt,
        "BLOCK_TIME_UTC_mvt": block,
        # the departure delay varies; a fixed offset would make sched_offset_sec a copy
        # of the target
        "SCHED_TIME_UTC_mvt": [b - timedelta(seconds=int(d)) for b, d in
                               zip(block, rng.normal(600, 900, n).clip(-1800, 7200), strict=True)],
        "AIRCRAFT_TYPE_mvt": actype,
        "RUNWAY_mvt": runways,
        "STAND_mvt": stand,
        "TAXITIME_SEC_mvt": taxi,
        "LOBT_flt": opt_block,
        "CALLSIGN_flt": [f"XXX{i % 9000}" for i in range(n)],
        "ADEP_flt": adep,
        "ADES_flt": ades,
        "ADES_FILED_flt": ades,
        "MARKET_SEGMENT_flt": rng.choice(["Mainline", "Low-Cost", "Regional"], n),
        "IOBT_flt": opt_block,
        "FLIGHT_RULE_flt": ["I"] * n,
        "FLIGHT_TYPE_flt": ["S"] * n,
        "AIRCRAFT_TYPE_flt": actype,
        "WK_TBL_CAT_flt": [WAKE[t] for t in actype],
        "AIRCRAFT_OPERATOR_flt": rng.choice(["AAA", "BBB", "CCC", "DDD"], n),
        "EOBT_1_flt": opt_block,
        "ARVT_1_flt": opt_block,
        "AOBT_3_flt": aobt3,
        "ARVT_3_flt": opt_block,
    })
    # make it UTC-aware, like the real data
    time_cols = [c for c, d in frame.schema.items() if d == pl.Datetime]
    return frame.with_columns(
        [pl.col(c).dt.replace_time_zone("UTC") for c in time_cols]
    )


def external_data(out: Path) -> None:
    """Minimal synthetic external data: METAR, airport reference, daily ATFM.

    Without these the integration tests **pass for nothing**: `load_inputs` returns None
    for the external data, the training and ranking sides end up missing it in the same
    way, and the "can every feature be produced on both sides" test verifies nothing. A
    real bug slipped through for exactly that reason.
    """
    rng = np.random.default_rng(99)
    hours = pl.datetime_range(datetime(2025, 1, 1), datetime(2026, 8, 1),
                              interval="30m", eager=True, closed="left")
    n = len(hours)
    pl.concat([
        pl.DataFrame({
            "station": [a] * n, "valid": hours,
            "temperature_c": rng.normal(12, 9, n), "dewpoint_c": rng.normal(7, 8, n),
            "visibility_km": rng.gamma(4, 3, n).clip(0.1, 20), "wind_ms": rng.gamma(2, 3, n),
            "wind_dir_deg": rng.uniform(0, 360, n), "precip_mm": rng.gamma(0.4, 1.0, n),
            "ceiling_m": rng.gamma(3, 400, n), "wxcodes": [""] * n, "skyc1": ["FEW"] * n,
            "freezing_precip": rng.random(n) < 0.01, "snow": rng.random(n) < 0.01,
            "fog": rng.random(n) < 0.05, "thunderstorm": rng.random(n) < 0.02,
            "deicing_proxy": rng.random(n) < 0.02, "low_visibility": rng.random(n) < 0.05,
        })
        for a in AIRPORTS
    ]).write_parquet(out / "metar.parquet")

    k = len(AIRPORTS)
    pl.DataFrame({
        "icao": AIRPORTS + OUTSIDE,
        "latitude": rng.uniform(36, 53, k + len(OUTSIDE)),
        "longitude": rng.uniform(-1, 31, k + len(OUTSIDE)),
        "elevation_ft": rng.uniform(0, 1500, k + len(OUTSIDE)),
    }).write_parquet(out / "airport_coords.parquet")

    pl.DataFrame({
        "icao": AIRPORTS,
        "runway_count": rng.integers(2, 7, k).astype("int8"),
        "longest_runway_ft": rng.uniform(10000, 14000, k),
        "mean_runway_ft": rng.uniform(9000, 13000, k),
    }).write_parquet(out / "airport_runways.parquet")

    day_range = pl.date_range(date(2025, 1, 1), date(2026, 8, 1), eager=True, closed="left")
    g = len(day_range)
    pl.concat([
        pl.DataFrame({
            "apt": [a] * g, "day": day_range,
            "atfm_regulated_share": rng.beta(2, 20, g),
            "atfm_slot_late_share": rng.beta(2, 30, g),
            "atfm_slot_early_share": rng.beta(2, 30, g),
            "daily_departures": rng.uniform(200, 800, g),
            "arr_atfm_delay_min": rng.gamma(2, 1.5, g),
            "daily_arrivals": rng.uniform(200, 800, g),
            "arr_delay_weather_min": rng.gamma(1.5, 1.0, g),
            "arr_delay_atc_capacity_min": rng.gamma(1.2, 0.5, g),
            "arr_delay_aerodrome_capacity_min": rng.gamma(1.2, 0.6, g),
            "arr_delay_atc_staffing_min": rng.gamma(1.0, 0.3, g),
            "arr_delay_atc_equipment_min": rng.gamma(1.0, 0.2, g),
        })
        for a in AIRPORTS
    ]).write_parquet(out / "eurocontrol_atfm_daily.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-day", type=int, default=600)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for month in range(1, 13):
        start = datetime(2025, month, 1)
        nxt = datetime(2025 + month // 12, month % 12 + 1, 1)
        build(start, 28, args.per_day, seed=month).write_parquet(
            out / f"training_{start:%Y-%m-%d}_{nxt:%Y-%m-%d}.parquet"
        )

    # the ranking set carries the real asymmetry: 10 airports in January, only 3 in July (R03)
    rank = pl.concat([
        build(datetime(2026, 1, 1), 28, args.per_day, seed=101, airports=AIRPORTS),
        build(datetime(2026, 7, 1), 28, args.per_day // 3, seed=107, airports=JULY_AIRPORTS),
    ])
    is_dep = pl.col("PHASE_mvt") == "DEP"
    rank = rank.with_columns(
        pl.when(is_dep).then(None).otherwise(pl.col("BLOCK_TIME_UTC_mvt"))
        .alias("BLOCK_TIME_UTC_mvt"),
        pl.when(is_dep).then(None).otherwise(pl.col("TAXITIME_SEC_mvt"))
        .alias("TAXITIME_SEC_mvt"),
    )
    rank.write_parquet(out / "ranking.parquet")
    rank.filter(is_dep).select("MVT_ID_mvt", "TAXITIME_SEC_mvt").write_parquet(
        out / "submitting.parquet"
    )

    external_data(out)
    print("fixture written:", out, "| ranking rows:", rank.height, "| external data included")


if __name__ == "__main__":
    main()
