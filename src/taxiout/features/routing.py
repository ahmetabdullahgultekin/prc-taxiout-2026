"""Departure direction, ATFM pressure and stand turnaround.

Each of these comes directly from the literature (see `docs/literature.md`):

- **Departure direction as a departure-fix proxy.** Lee, Malik and Jung (Charlotte,
  2016) find the departure fix predictive: consecutive departures heading for the same
  exit must be released with wider spacing because of route and wake separation, which
  lengthens the queue. The data has no fix, but it has `ADES_mvt`, so we take the
  great-circle bearing from the departure airport to the destination and round it into
  a sector.

- **Downstream restrictions.** Idris et al. (Logan, 2002) count these among the four
  main factors. The data carries no ATFM slot, but it has `IOBT_flt`, the initially
  planned off-block time, and `LOBT_flt`, the last known one. The drift between them is
  a direct trace of whether the flight was re-timed.

- **Stand turnaround.** An aircraft that has just arrived on the same stand narrows the
  pushback and manoeuvring area, so we measure how long ago the previous arrival went
  on block there.
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
# The airport the movement happened at; added by `pipeline.prepare_movements`.
# NOT `ADEP_mvt`, which on an arrival row names where the aircraft came from.
APT = "apt_mvt"
ADES = "ADES_mvt"
STAND = "STAND_mvt"
PHASE = "PHASE_mvt"

# Number of bearing sectors. Twelve gives 30-degree slices: a coarse stand-in for the
# real SID groupings, but one that needs no hand tuning per airport.
SECTORS = 12
SECTOR_WINDOWS_MIN = (15, 30)


def _bearing_deg(lat1: pl.Expr, lon1: pl.Expr, lat2: pl.Expr, lon2: pl.Expr) -> pl.Expr:
    """Great-circle initial bearing, in degrees from 0 to 360."""
    p1, p2 = lat1.radians(), lat2.radians()
    dl = (lon2 - lon1).radians()
    y = dl.sin() * p2.cos()
    x = p1.cos() * p2.sin() - p1.sin() * p2.cos() * dl.cos()
    return (pl.arctan2(y, x).degrees() + 360.0) % 360.0


def attach_bearing(dep: pl.DataFrame, coords: pl.DataFrame) -> pl.DataFrame:
    """Add departure bearing, its sector, and the great-circle distance."""
    origin = coords.rename({"icao": APT, "latitude": "_lat1", "longitude": "_lon1"}).select(
        APT, "_lat1", "_lon1"
    )
    dest = coords.rename({"icao": ADES, "latitude": "_lat2", "longitude": "_lon2"}).select(
        ADES, "_lat2", "_lon2"
    )
    out = dep.join(origin, on=APT, how="left").join(dest, on=ADES, how="left")

    bearing = _bearing_deg(pl.col("_lat1"), pl.col("_lon1"), pl.col("_lat2"), pl.col("_lon2"))
    # haversine, kilometres
    dlat = (pl.col("_lat2") - pl.col("_lat1")).radians()
    dlon = (pl.col("_lon2") - pl.col("_lon1")).radians()
    a = (dlat / 2).sin() ** 2 + pl.col("_lat1").radians().cos() * pl.col(
        "_lat2"
    ).radians().cos() * (dlon / 2).sin() ** 2
    return out.with_columns(
        departure_bearing=bearing.cast(pl.Float32),
        departure_sector=(bearing / (360.0 / SECTORS)).floor().cast(pl.Int8),
        flight_distance_km=(2 * 6371.0 * a.sqrt().arcsin()).cast(pl.Float32),
    ).drop("_lat1", "_lon1", "_lat2", "_lon2")


def sector_congestion(dep: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """Departures heading the same way inside the window: a departure-fix queue proxy.

    Must be called after `attach_bearing`. The count uses the same tie-safe definition
    as `congestion._counts_in_window`: a backward window of (t-W, t] that includes the
    row itself.
    """
    from taxiout.features.congestion import _counts_in_window

    time_cols = list(dict.fromkeys([anchor, MVT]))
    keys = dep.select("MVT_ID_mvt", APT, "departure_sector", *time_cols).sort(anchor)
    out = keys
    for w in SECTOR_WINDOWS_MIN:
        out = _counts_in_window(
            out, keys, [APT, "departure_sector"], w, False,
            f"sector_dep_prev_{w}m", anchor, MVT,
        )
    return out.drop(APT, "departure_sector", *time_cols)


def atfm_pressure(dep: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """Plan drift: was the flight re-timed, and by how much?

    `lobt_anchor_gap_sec` is tied to the anchor: using the take-off time in causal mode
    would leak the target directly.
    """
    cols = dep.columns
    exprs = []
    if "IOBT_flt" in cols and "LOBT_flt" in cols:
        exprs.append(
            (pl.col("LOBT_flt") - pl.col("IOBT_flt")).dt.total_seconds()
            .cast(pl.Float32).alias("atfm_drift_sec")
        )
    if "LOBT_flt" in cols:
        exprs.append(
            (pl.col(anchor) - pl.col("LOBT_flt")).dt.total_seconds()
            .cast(pl.Float32).alias("lobt_anchor_gap_sec")
        )
    if "ADES_FILED_flt" in cols and ADES in cols:
        # A filed destination different from the actual one means the flight diverted.
        exprs.append(
            (pl.col("ADES_FILED_flt") != pl.col(ADES)).alias("diverted")
        )
    return dep.with_columns(exprs) if exprs else dep


def stand_turnaround(
    mvt: pl.DataFrame, dep: pl.DataFrame, anchor: str = MVT
) -> pl.DataFrame:
    """How long ago the last arrival went on block at the same stand.

    A recently arrived aircraft occupies the stand area and the pushback space.
    """
    arr = (
        mvt.filter((pl.col(PHASE) == "ARR") & pl.col(STAND).is_not_null())
        .select(APT, STAND, _arr_block=pl.col("BLOCK_TIME_UTC_mvt"))
        .filter(pl.col("_arr_block").is_not_null())
        .sort("_arr_block")
    )
    if arr.height == 0:
        return dep.select("MVT_ID_mvt").with_columns(
            stand_turnaround_sec=pl.lit(None, dtype=pl.Float32)
        )
    return (
        dep.select("MVT_ID_mvt", APT, STAND, _anchor=pl.col(anchor))
        .sort("_anchor")
        .join_asof(
            arr, left_on="_anchor", right_on="_arr_block", by=[APT, STAND],
            strategy="backward",
        )
        .with_columns(
            stand_turnaround_sec=(pl.col("_anchor") - pl.col("_arr_block")).dt.total_seconds()
            .cast(pl.Float32)
        )
        .select("MVT_ID_mvt", "stand_turnaround_sec")
    )


def build(
    mvt: pl.DataFrame, dep: pl.DataFrame, coords: pl.DataFrame | None, anchor: str = MVT
) -> pl.DataFrame:
    """Add every routing feature to `dep`.

    `anchor` means the same as in `congestion.build`: the off-block instant in causal
    mode.
    """
    out = atfm_pressure(dep, anchor)
    if coords is not None and ADES in out.columns:
        out = attach_bearing(out, coords)
        out = out.join(sector_congestion(out, anchor), on="MVT_ID_mvt", how="left")
    return out.join(stand_turnaround(mvt, out, anchor), on="MVT_ID_mvt", how="left")
