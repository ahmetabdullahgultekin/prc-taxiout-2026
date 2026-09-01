"""Oznitelik ailesi kaydinin butunlugu.

Buradaki asil test `test_every_produced_feature_has_a_group`. Amaci sadece bir
tutarlilik kontrolu degil: bir oznitelik aileye yazilmazsa ablation tablosunda
gorunmez, yani hicbir deneyle sinanmadan modelde kalir. Test kirilarak bunu
imkansiz kilar.
"""

from __future__ import annotations

import pytest

from taxiout.features import groups

# Boru hattinin urettigi kolonlar (fixture uzerinde uctan uca kosudan alindi) +
# referans modulunun sonradan ekledikleri.
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
    # airport_state.attach ciktilari (EUROCONTROL gunluk)
    "atfm_regulated_share", "atfm_slot_late_share", "atfm_slot_early_share",
    "daily_departures", "daily_arrivals", "arr_atfm_delay_min",
    "arr_delay_weather_min", "arr_delay_atc_capacity_min",
    "arr_delay_aerodrome_capacity_min", "arr_delay_atc_staffing_min",
    "arr_delay_atc_equipment_min",
    # reference.apply_reference ciktilari
    "reference_sec", "reference_level", "reference_sample",
]


def test_every_produced_feature_has_a_group() -> None:
    orphans = [c for c in PRODUCED if groups.group_of(c) is None]
    assert orphans == [], (
        f"su oznitelikler hicbir aileye ait degil, ablation'da gorunmezler: {orphans}"
    )


def test_no_feature_falls_into_two_groups() -> None:
    """Kolon birden fazla ailenin desenine uyarsa ablation sonucu yaniltici olur."""
    import re

    for c in PRODUCED:
        matches = [
            name for name, pats in groups.GROUPS.items()
            if any(re.compile(p).match(c) for p in pats)
        ]
        assert len(matches) == 1, f"{c} birden cok aileye uyuyor: {matches}"


def test_every_group_is_non_empty() -> None:
    """Bos bir aile, yeniden adlandirilmis ama guncellenmemis bir desendir."""
    assigned = groups.assign(PRODUCED)
    empty = [name for name in groups.GROUPS if not assigned[name]]
    assert empty == [], f"bos oznitelik ailesi: {empty}"


def test_select_drops_exactly_the_named_group() -> None:
    kept = groups.select(PRODUCED, drop={"weather"})
    assert "temperature_c" not in kept
    assert "deicing_proxy" not in kept
    assert "rwy_dep_prev_15m" in kept
    assert len(kept) == len(PRODUCED) - len(groups.assign(PRODUCED)["weather"])


def test_select_rejects_unknown_group_instead_of_silently_ignoring() -> None:
    with pytest.raises(KeyError, match="unknown feature family"):
        groups.select(PRODUCED, drop={"hava_durumu"})


def test_unknown_columns_are_kept_not_dropped() -> None:
    """Kayitta olmayan bir kolon ablation tarafindan sessizce dusurulmemeli."""
    kept = groups.select([*PRODUCED, "yepyeni_oznitelik"], drop={"weather"})
    assert "yepyeni_oznitelik" in kept
