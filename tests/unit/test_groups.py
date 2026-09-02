"""Integrity of the feature family registry.

The test that matters here is `test_every_produced_feature_has_a_group`. It is not just a
consistency check: a feature that is not written into a family never appears in the
ablation table, so it stays in the model without a single experiment testing it. Breaking
the test makes that impossible.
"""

from __future__ import annotations

import pytest

from taxiout.features import groups

# The columns the pipeline produces (taken from an end-to-end run over the fixture) plus
# the ones the reference module adds afterwards.
PRODUCED = [
    "apt_mvt", "AIRCRAFT_OPERATOR_flt", "AIRCRAFT_TYPE_flt", "AIRCRAFT_TYPE_mvt",
    "MARKET_SEGMENT_flt", "RUNWAY_mvt", "STAND_mvt", "WK_TBL_CAT_flt", "active_runway_count",
    "apt_arr_prev_5m", "apt_arr_prev_10m", "apt_arr_prev_15m",
    "apt_arr_prev_30m", "apt_arr_prev_60m",
    "apt_arr_next_5m", "apt_arr_next_10m", "apt_arr_next_15m",
    "apt_arr_next_30m", "apt_arr_next_60m",
    "apt_dep_prev_5m", "apt_dep_prev_10m", "apt_dep_prev_15m",
    "apt_dep_prev_30m", "apt_dep_prev_60m",
    "apt_dep_next_5m", "apt_dep_next_10m", "apt_dep_next_15m",
    "apt_dep_next_30m", "apt_dep_next_60m",
    "atfm_drift_sec", "month_num", "dewpoint_spread_c", "dewpoint_c", "deicing_proxy",
    "freezing_precip", "low_visibility", "longest_runway_ft", "eobt_offset_sec", "thunderstorm",
    "visibility_km", "observation_age_min", "minute_of_day", "weekday", "arr_dep_ratio_30m",
    "arr_runways_in_use", "departure_bearing", "dep_runways_in_use", "departure_sector", "snow",
    "lobt_anchor_gap_sec", "nm_naive_taxi_sec", "nm_matched", "prev_dep_gap_sec", "mean_runway_ft",
    "rwy_dep_prev_5m", "rwy_dep_prev_10m", "rwy_dep_prev_15m",
    "rwy_dep_prev_30m", "rwy_dep_prev_60m",
    "rwy_dep_next_5m", "rwy_dep_next_10m", "rwy_dep_next_15m",
    "rwy_dep_next_30m", "rwy_dep_next_60m",
    "runway_count", "rwy_service_interval_sec", "sched_offset_sec", "wind_ms", "hour",
    "sector_dep_prev_15m", "sector_dep_prev_30m", "temperature_c", "fog",
    "next_dep_gap_sec", "stand_turnaround_sec", "ceiling_m", "flight_distance_km",
    "arr_taxi_median_sec", "arr_taxi_count", "precip_mm", "diverted",
    # airport_state.attach outputs (EUROCONTROL daily)
    "atfm_regulated_share", "atfm_slot_late_share", "atfm_slot_early_share",
    "daily_departures", "daily_arrivals", "arr_atfm_delay_min",
    "arr_delay_weather_min", "arr_delay_atc_capacity_min",
    "arr_delay_aerodrome_capacity_min", "arr_delay_atc_staffing_min",
    "arr_delay_atc_equipment_min",
    # reference.apply_reference outputs
    "reference_sec", "reference_level", "reference_sample",
    # surface_delay.build outputs
    "surface_apt_at_pushback", "surface_apt_at_takeoff",
    "surface_rwy_at_pushback", "surface_rwy_at_takeoff",
    "surface_excess_sec", "surface_excess_n",
    # overlap.build outputs
    "overtaken_by", "overtook", "net_overtaking", "overtaken_rate",
    "arrivals_inside", "arrivals_inside_rate", "departure_share", "window_sec",
    # icing.attach outputs
    "atmap_freezing", "atmap_moisture", "frost_risk",
]


def test_every_produced_feature_has_a_group() -> None:
    orphans = [c for c in PRODUCED if groups.group_of(c) is None]
    assert orphans == [], (
        f"these features belong to no family, they will not appear in the ablation: {orphans}"
    )


def test_no_feature_falls_into_two_groups() -> None:
    """If a column matches more than one family pattern, the ablation result misleads."""
    import re

    for c in PRODUCED:
        matches = [
            name for name, pats in groups.GROUPS.items()
            if any(re.compile(p).match(c) for p in pats)
        ]
        assert len(matches) == 1, f"{c} matches more than one family: {matches}"


def test_every_group_is_non_empty() -> None:
    """An empty family is a pattern that was renamed but not updated."""
    assigned = groups.assign(PRODUCED)
    empty = [name for name in groups.GROUPS if not assigned[name]]
    assert empty == [], f"empty feature family: {empty}"


def test_select_drops_exactly_the_named_group() -> None:
    kept = groups.select(PRODUCED, drop={"weather"})
    assert "temperature_c" not in kept
    assert "deicing_proxy" not in kept
    assert "rwy_dep_prev_15m" in kept
    assert len(kept) == len(PRODUCED) - len(groups.assign(PRODUCED)["weather"])


def test_select_rejects_unknown_group_instead_of_silently_ignoring() -> None:
    with pytest.raises(KeyError, match="unknown feature family"):
        groups.select(PRODUCED, drop={"weather_conditions"})


def test_unknown_columns_are_kept_not_dropped() -> None:
    """A column that is not in the registry must not be dropped silently by the ablation."""
    kept = groups.select([*PRODUCED, "brand_new_feature"], drop={"weather"})
    assert "brand_new_feature" in kept
