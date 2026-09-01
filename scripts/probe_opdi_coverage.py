"""Measures the coverage of OPDI ground events at the 11 airports.

**Why we looked.** OPDI (Open Performance Data Initiative, the PRC's own initiative with
the OpenSky Network) publishes flight events derived from ADS-B, and v0.0.2 added
**parking position entry/exit** events. `exit-parking_position` would be an **independent
measurement** of the off-block instant, which is blanked out in the ranking set. The
coverage runs January 2022 to August 2026, so both ranking months are inside it.

This is also exactly the stated purpose of the competition: taxi-out is "a quantity that is
hard to obtain", and the model is meant for the gap at airports that do not share A-CDM
data. Filling that gap with open ADS-B events would have been a directly relevant result.

**Result: unusable.** The measured coverage is below; the summary is in
`docs/opdi_negative_result.md`.

    python scripts/probe_opdi_coverage.py --events <flight_events_*.parquet>
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import polars as pl

# ICAO -> (latitude, longitude). OurAirports.
AIRPORTS = {
    "EDDF": (50.026706, 8.55835), "EDDM": (48.353802, 11.7861),
    "EGLL": (51.470748, -0.459909), "EHAM": (52.308601, 4.76389),
    "LEBL": (41.2971, 2.07846), "LEMD": (40.471926, -3.562664),
    "LFPG": (49.00896, 2.554117), "LIRF": (41.804532, 12.251998),
    "LTAI": (36.898701, 30.800501), "LTFM": (41.274874, 28.732136),
    "LSZH": (47.458056, 8.548056),
}

GROUND_EVENTS = [
    "exit-parking_position", "entry-parking_position", "take-off",
    "entry-runway", "exit-runway", "entry-taxiway",
]

RADIUS_KM = 10.0


def near(lat: float, lon: float) -> pl.Expr:
    """A rough box around the airport. The longitude scale is corrected for latitude."""
    dlat = RADIUS_KM / 111.0
    dlon = RADIUS_KM / (111.0 * max(0.1, math.cos(math.radians(lat))))
    return ((pl.col("latitude") - lat).abs() < dlat) & (
        (pl.col("longitude") - lon).abs() < dlon
    )


def coverage(event_files: list[Path]) -> pl.DataFrame:
    ev = (
        pl.scan_parquet([str(p) for p in event_files])
        .filter(pl.col("type").is_in(GROUND_EVENTS))
        .select("type", "latitude", "longitude")
        .collect()
    )
    rows = []
    for icao, (la, lo) in AIRPORTS.items():
        sub = ev.filter(near(la, lo))
        counts = dict(sub.group_by("type").agg(n=pl.len()).iter_rows())
        rows.append({"apt": icao, **{e: counts.get(e, 0) for e in GROUND_EVENTS}})
    return pl.DataFrame(rows).sort("exit-parking_position", descending=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", nargs="+", required=True,
                    help="OPDI flight_events_*.parquet files")
    args = ap.parse_args()
    files = [Path(p) for p in args.events]
    df = coverage(files)
    print(f"files: {len(files)}")
    print(df)
    zero = df.filter(pl.col("exit-parking_position") == 0)["apt"].to_list()
    print(f"\nairports with NO parking position exit event at all: {sorted(zero)}")


if __name__ == "__main__":
    main()
