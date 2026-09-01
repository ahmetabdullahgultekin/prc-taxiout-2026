"""Attaches METAR observations to movement records.

The join is **as-of, backward**: each departure takes the most recent valid observation
before its anchor instant. Looking forward would make no sense here; the weather feature
describes the conditions the aircraft actually faced.

`observation_age_min` is exposed deliberately. Reports are half-hourly, conditions can
change between them, and the model should know how stale the observation is.
"""

from __future__ import annotations

import polars as pl

MVT = "MVT_TIME_UTC_mvt"
# The airport the movement happened at; added by `pipeline.prepare_movements`.
# NOT `ADEP_mvt`, which on an arrival row names where the aircraft came from.
APT = "apt_mvt"

WEATHER_COLS = [
    "temperature_c", "dewpoint_c", "visibility_km", "wind_ms", "precip_mm", "ceiling_m",
    "freezing_precip", "snow", "fog", "thunderstorm", "deicing_proxy", "low_visibility",
]


def attach(dep: pl.DataFrame, metar: pl.DataFrame, anchor: str = MVT) -> pl.DataFrame:
    """Add the latest METAR observation to each departure row.

    In causal mode `anchor` is the off-block instant: knowing the weather at take-off
    is not something a real-time model would have.
    """
    # Challenge timestamps are timezone-aware (datetime[us, UTC]) while the IEM archive
    # returns naive UTC. Polars refuses the join outright unless they are aligned. Same
    # instant, two representations, no shift.
    tz = dep.schema[anchor].time_zone
    observed_at = pl.col("valid")
    if tz is not None:
        observed_at = observed_at.dt.replace_time_zone(tz)
    obs = (
        metar.select("station", _observed_at=observed_at, **{c: pl.col(c) for c in WEATHER_COLS})
        .sort("_observed_at")
    )
    joined = (
        dep.sort(anchor)
        .join_asof(
            obs,
            left_on=anchor,
            right_on="_observed_at",
            by_left=APT,
            by_right="station",
            strategy="backward",
        )
    )
    return joined.with_columns(
        observation_age_min=((pl.col(anchor) - pl.col("_observed_at")).dt.total_seconds() / 60.0)
        .cast(pl.Float32),
        # Dewpoint spread: the closer to zero, the higher the risk of fog and of icing.
        dewpoint_spread_c=(pl.col("temperature_c") - pl.col("dewpoint_c")).cast(pl.Float32),
    ).drop("_observed_at", "station", strict=False)
