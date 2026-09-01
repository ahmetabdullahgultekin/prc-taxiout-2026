"""Airport and runway reference data (OurAirports, public domain).

Needed for two things:

1. **Departure direction.** Lee, Malik and Jung (Charlotte, 2016) find the departure fix
   predictive: aircraft leaving for the same exit need wider separation, so one whose
   neighbours share its heading waits longer. The data has no fix, but it has
   `ADES_mvt`, so we take the bearing from departure to destination and round it into a
   sector.

2. **Airport structure.** Runway count bounds capacity: Heathrow and Munich have two,
   Istanbul and Schiphol six. That is part of why the airports behave differently.

Licence: "All data is released to the Public Domain" (ourairports.com/data/, read
2026-09-01). Attribution is optional but given anyway. See `docs/external_data.md`.

Note: the list below carries all eleven airports named on the challenge page, but the
delivered dataset contains only ten. LTAI (Antalya) appears nowhere in it.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import polars as pl

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"

CHALLENGE_AIRPORTS = [
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL", "LEMD", "LFPG", "LIRF", "LTAI", "LTFM", "LSZH",
]


def _download(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as r, dest.open("wb") as f:  # noqa: S310
            f.write(r.read())
    return dest


def build(raw_dir: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (coordinates for every airport, runway summary for the challenge ones).

    The coordinate table covers **every** airport: a destination can be anywhere in
    the world and all of them are needed for the bearing.
    """
    apt_csv = _download(AIRPORTS_URL, raw_dir / "ourairports_airports.csv")
    rwy_csv = _download(RUNWAYS_URL, raw_dir / "ourairports_runways.csv")

    coords = (
        pl.read_csv(apt_csv, infer_schema_length=50_000)
        .filter(pl.col("latitude_deg").is_not_null() & pl.col("longitude_deg").is_not_null())
        .select(
            icao=pl.col("ident"),
            latitude=pl.col("latitude_deg").cast(pl.Float64),
            longitude=pl.col("longitude_deg").cast(pl.Float64),
            elevation_ft=pl.col("elevation_ft").cast(pl.Float32, strict=False),
        )
        .unique(subset="icao")
    )

    runways = (
        pl.read_csv(rwy_csv, infer_schema_length=50_000)
        .filter(pl.col("airport_ident").is_in(CHALLENGE_AIRPORTS) & (pl.col("closed") == 0))
        .group_by("airport_ident")
        .agg(
            runway_count=pl.len().cast(pl.Int8),
            longest_runway_ft=pl.col("length_ft").max().cast(pl.Float32),
            mean_runway_ft=pl.col("length_ft").mean().cast(pl.Float32),
        )
        .rename({"airport_ident": "icao"})
    )
    return coords, runways


def main() -> None:
    ap = argparse.ArgumentParser(description="prepare OurAirports reference data")
    ap.add_argument("--raw-dir", required=True)
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    coords, runways = build(raw)
    coords.write_parquet(raw / "airport_coords.parquet")
    runways.write_parquet(raw / "airport_runways.parquet")
    print(f"{coords.height:,} airport coordinates, {runways.height} challenge airports")
    print(runways.sort("runway_count", descending=True))


if __name__ == "__main__":
    main()
