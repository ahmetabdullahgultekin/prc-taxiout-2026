"""Belgelenen semaya birebir uyan sentetik veri uretir.

Amac: gercek veri gelmeden once boru hattini uctan uca calistirabilmek.
Gercek veri ASLA bu dizine yazilmaz (form sarti F11).

    python tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

AIRPORTS = ["EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH"]
RUNWAYS = {a: [f"{a[-2:]}L", f"{a[-2:]}R"] for a in AIRPORTS}
TYPES = ["A320", "A321", "B738", "A20N", "B77W", "E195", "A359"]
WAKE = {"A320": "M", "A321": "M", "B738": "M", "A20N": "M", "B77W": "H", "E195": "M", "A359": "H"}


def build(start: datetime, days: int, per_day: int, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = days * per_day
    apt = rng.choice(AIRPORTS, n)
    rwy = np.array([rng.choice(RUNWAYS[a]) for a in apt])
    stand = np.array([f"{rng.integers(1, 21)}" for _ in range(n)])
    actype = rng.choice(TYPES, n)
    phase = rng.choice(["DEP", "ARR"], n)

    offsets = rng.integers(0, days * 86400, n)
    block = np.array([start + timedelta(seconds=int(s)) for s in offsets])

    # taxi-out: stand/pist tabani + kuyruk kuyrugu; ARR icin taxi-in daha kisa
    base = 300 + stand.astype(int) * 6 + (rwy == np.array([RUNWAYS[a][1] for a in apt])) * 120
    queue = rng.gamma(2.0, 90.0, n)
    taxi = np.where(phase == "DEP", base + queue, 240 + rng.gamma(1.5, 40.0, n))
    taxi = np.round(taxi).astype(int)

    mvt = np.array([b + timedelta(seconds=int(t)) for b, t in zip(block, taxi, strict=True)])
    # ARR icin mantik ters: once iner, sonra bloga girer
    mvt = [m if p == "DEP" else b - timedelta(seconds=int(x))
           for m, p, b, x in zip(mvt, phase, block, taxi, strict=True)]

    matched = rng.random(n) < 0.85  # NM eslesme orani
    # AOBT_3 = APDF blok saatinin gurultulu NM olcumu
    aobt3_noise = rng.normal(0, 110, n)
    aobt3 = [b + timedelta(seconds=float(e)) if m else None
             for b, e, m in zip(block, aobt3_noise, matched, strict=True)]
    opt_block = [b if m else None for b, m in zip(block, matched, strict=True)]
    opt_fid = [int(i) if m else None for i, m in enumerate(matched)]

    return pl.DataFrame(
        {
            "MVT_ID_mvt": np.arange(seed * 10**7, seed * 10**7 + n),
            "FLIGHT_ID_mvt": opt_fid,
            "FLIGHT_mvt": [f"XX{i % 9000 + 100}" for i in range(n)],
            "FLIGHT_RULE_mvt": ["I"] * n,
            "ADEP_mvt": apt,
            "ADES_mvt": rng.choice(AIRPORTS, n),
            "PHASE_mvt": phase,
            "MVT_TIME_UTC_mvt": list(mvt),
            "BLOCK_TIME_UTC_mvt": list(block),
            "SCHED_TIME_UTC_mvt": [b - timedelta(minutes=10) for b in block],
            "AIRCRAFT_TYPE_mvt": actype,
            "RUNWAY_mvt": rwy,
            "STAND_mvt": stand,
            "TAXITIME_SEC_mvt": taxi,
            "LOBT_flt": opt_block,
            "CALLSIGN_flt": [f"XXX{i % 9000}" for i in range(n)],
            "ADEP_flt": apt,
            "ADES_flt": rng.choice(AIRPORTS, n),
            "ADES_FILED_flt": rng.choice(AIRPORTS, n),
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
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-day", type=int, default=600)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for month in range(1, 13):
        start = datetime(2025, month, 1)
        df = build(start, 28, args.per_day, seed=month)
        nxt = datetime(2025 + month // 12, month % 12 + 1, 1)
        name = f"training_{start:%Y-%m-%d}_{nxt:%Y-%m-%d}.parquet"
        df.write_parquet(out / name)

    rank_parts = [build(datetime(2026, m, 1), 28, args.per_day, seed=100 + m) for m in (1, 7)]
    rank = pl.concat(rank_parts)
    # siralama seti: DEP satirlarinda blok saati ve taxi suresi bosaltilir (D05)
    is_dep = pl.col("PHASE_mvt") == "DEP"
    rank = rank.with_columns(
        pl.when(is_dep).then(None).otherwise(pl.col("BLOCK_TIME_UTC_mvt")).alias("BLOCK_TIME_UTC_mvt"),
        pl.when(is_dep).then(None).otherwise(pl.col("TAXITIME_SEC_mvt")).alias("TAXITIME_SEC_mvt"),
    )
    rank.write_parquet(out / "ranking.parquet")
    rank.filter(is_dep).select("MVT_ID_mvt", "TAXITIME_SEC_mvt").write_parquet(
        out / "submitting.parquet"
    )
    print("fixture yazildi:", out, "| ranking satiri:", rank.height)


if __name__ == "__main__":
    main()
