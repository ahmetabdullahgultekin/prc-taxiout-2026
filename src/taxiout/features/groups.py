"""Feature families: the unit of ablation.

Why a separate registry. In last year's winning paper the contribution was presented as
a single feature-family by RMSE table, and that table was produced directly on the
ranking set rather than on cross-validation. Submissions are therefore experiments, not
tuning attempts, and "drop this family" has to be expressible as one name.

The family names follow the taxonomy of Wang et al. (Shanghai Pudong, 2018), cited in
`docs/literature.md`: surface instantaneous flow, surface cumulative flow, aircraft
queue length, and slot resource demand.

`test_groups.py` asserts that every produced column falls into **exactly one** family.
Adding a feature without registering it here breaks that test, which is what stops
features accumulating in the model without ever being ablated.
"""

from __future__ import annotations

import re

# Order matters: a column is assigned to the first family whose pattern it matches.
GROUPS: dict[str, list[str]] = {
    # Layout and the unimpeded baseline: static information, before any queueing.
    "geometry": [
        r"^apt_mvt$", r"^RUNWAY_mvt$", r"^STAND_mvt$",
        r"^stand_pier$", r"^stand_number$",
        r"^runway_count$", r"^longest_runway_ft$", r"^mean_runway_ft$",
        r"^reference_",
    ],
    # Runway queue: non-circular proxies for Idris's strongest variable.
    "runway_queue": [
        r"^rwy_dep_", r"^prev_dep_gap_sec$", r"^next_dep_gap_sec$",
        r"^rwy_service_interval_sec$",
    ],
    # Airport-wide flow, instantaneous and cumulative.
    "airport_flow": [r"^apt_dep_", r"^apt_arr_", r"^arr_dep_ratio_"],
    # Live surface congestion; computable on the ranking set too, since arrivals
    # are not blanked there.
    "taxi_in_pressure": [r"^arr_taxi_"],
    # Inferred runway configuration.
    "runway_configuration": [
        r"^dep_runways_in_use$", r"^arr_runways_in_use$", r"^active_runway_count$",
    ],
    # Departure-fix proxy, after Lee, Malik and Jung (Charlotte, 2016).
    "routing": [
        r"^departure_bearing$", r"^departure_sector$", r"^sector_dep_",
        r"^flight_distance_km$",
    ],
    # Downstream restrictions and slot demand: Idris's fourth factor.
    "atfm": [
        r"^atfm_drift_sec$", r"^lobt_anchor_gap_sec$", r"^sched_offset_sec$",
        r"^eobt_offset_sec$", r"^diverted$",
    ],
    "stand_turnaround": [r"^stand_turnaround_sec$"],
    # The queue as a stock rather than a flow, and the surface running over its own
    # baseline right now. Both are derived from the Network Manager off-block time, so
    # they share the fate of the nm_aobt family: unavailable to the causal model.
    "surface": [r"^surface_"],
    # Overlap counters after Zhang et al. (2024): who passed this flight during its own
    # taxi, and which arrivals landed and parked inside its window. Needs the Network
    # Manager off-block time, so unavailable to the causal model.
    "overlap": [
        r"^overtaken_by$", r"^overtook$", r"^net_overtaking$", r"^overtaken_rate$",
        r"^arrivals_inside$", r"^arrivals_inside_rate$", r"^departure_share$",
        r"^window_sec$",
    ],
    # Weather: the family that carries the January de-icing regime.
    "weather": [
        r"^temperature_c$", r"^dewpoint_c$", r"^dewpoint_spread_c$", r"^visibility_km$",
        r"^wind_ms$", r"^wind_dir_deg$", r"^precip_mm$", r"^ceiling_m$",
        r"^freezing_precip$", r"^snow$", r"^fog$", r"^thunderstorm$",
        r"^deicing_proxy$", r"^low_visibility$", r"^observation_age_min$",
        # EUROCONTROL's own ATMAP freezing coefficient, which is the organisation that
        # runs this competition and defines the indicator being predicted.
        r"^atmap_freezing$", r"^atmap_moisture$", r"^frost_risk$",
    ],
    "calendar": [r"^hour$", r"^weekday$", r"^month_num$", r"^minute_of_day$"],
    "aircraft": [
        r"^AIRCRAFT_TYPE_", r"^WK_TBL_CAT_flt$", r"^MARKET_SEGMENT_flt$",
        r"^AIRCRAFT_OPERATOR_flt$",
    ],
    # EUROCONTROL daily airport state. Kept separate because it is external and
    # cannot be used by the causal model, being a whole-day total.
    "atfm_daily": [
        r"^atfm_regulated_share$", r"^atfm_slot_", r"^daily_departures$",
        r"^daily_arrivals$", r"^arr_atfm_delay_min$", r"^arr_delay_",
    ],
    # Derived from the NM M3 off-block time. Its own family because how much it gives
    # away decides the whole architecture.
    "nm_aobt": [r"^nm_naive_taxi_sec$", r"^nm_matched$"],
}

_COMPILED = {name: [re.compile(p) for p in pats] for name, pats in GROUPS.items()}


def group_of(column: str) -> str | None:
    """The family a column belongs to, or None if it matches no pattern."""
    for name, patterns in _COMPILED.items():
        if any(p.match(column) for p in patterns):
            return name
    return None


def assign(columns: list[str]) -> dict[str, list[str]]:
    """Family to columns. Anything unmatched is collected under 'UNASSIGNED'."""
    out: dict[str, list[str]] = {name: [] for name in GROUPS}
    out["UNASSIGNED"] = []
    for c in columns:
        out[group_of(c) or "UNASSIGNED"].append(c)
    return out


def select(columns: list[str], drop: set[str] | None = None) -> list[str]:
    """The column list with the named families removed.

    Columns with no family are **kept**: an ablation must not silently drop a feature
    because the registry is out of date. A missing entry is caught by `test_groups.py`.
    """
    drop = drop or set()
    unknown = drop - set(GROUPS)
    if unknown:
        raise KeyError(f"unknown feature family: {sorted(unknown)}")
    return [c for c in columns if group_of(c) not in drop]
