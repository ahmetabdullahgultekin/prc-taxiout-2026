"""Daily airport state: ATFM regulation and arrival delay.

Idris et al. (Logan, 2002) name **downstream restrictions** as one of the four factors
driving taxi-out. Until now we proxied it only through the drift between the initial and
last known off-block time; EUROCONTROL's open daily series give the direct measurement:

- what share of the day's departures sat under an **ATFM slot**
- slot adherence, meaning the share leaving early or late
- daily **arrival ATFM delay** by cause code: weather, ATC capacity, aerodrome
  capacity, staffing, equipment

Both series cover January and July 2026, that is both ranking months.

**Causality caveat.** These are whole-day totals, so they include hours after a given
departure, and they are published months in arrears. Legitimate for the retrospective
model, not for a real-time one. `groups.py` keeps them in their own `atfm_daily` family
and `pipeline.build_features` never attaches them on the causal path.
"""

from __future__ import annotations

import polars as pl

# The airport the movement happened at; added by `pipeline.prepare_movements`.
# NOT `ADEP_mvt`, which on an arrival row names where the aircraft came from.
APT = "apt_mvt"

STATE_COLS = [
    "atfm_regulated_share", "atfm_slot_late_share", "atfm_slot_early_share",
    "daily_departures", "daily_arrivals", "arr_atfm_delay_min",
    "arr_delay_weather_min", "arr_delay_atc_capacity_min",
    "arr_delay_aerodrome_capacity_min", "arr_delay_atc_staffing_min",
    "arr_delay_atc_equipment_min",
]


def attach(dep: pl.DataFrame, daily: pl.DataFrame, anchor: str) -> pl.DataFrame:
    """Add that day's airport state to each departure row."""
    have = [c for c in STATE_COLS if c in daily.columns]
    state = daily.select("apt", "day", *have).rename({"apt": APT, "day": "_day"})
    return (
        dep.with_columns(_day=pl.col(anchor).dt.date())
        .join(state, on=[APT, "_day"], how="left")
        .drop("_day")
    )
