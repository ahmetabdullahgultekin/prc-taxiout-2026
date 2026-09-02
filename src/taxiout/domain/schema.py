"""Column names and coded values, defined once.

The competition's column names are long, similar to each other and easy to mistype:
`ADEP_mvt` against `ADEP_flt`, `AOBT_3_flt` against `ARVT_3_flt`, `MVT_TIME_UTC_mvt`
against `BLOCK_TIME_UTC_mvt`. Spread as string literals across thirteen modules they
were repeated up to twenty-seven times each, and a typo in any of them produces a
`ColumnNotFoundError` at best and a silently wrong join at worst. One of those has
already happened here: `ADEP_mvt` was used as the movement airport, which it is not,
and every arrival-derived feature was grouped on the wrong airport for weeks.

`StrEnum` rather than plain constants because its members *are* strings. `pl.col(Col.TARGET)`
works, `Col.TARGET == "TAXITIME_SEC_mvt"` is true, and f-strings interpolate them
directly, so nothing has to be unwrapped at the call site.
"""

from __future__ import annotations

from enum import StrEnum


class Col(StrEnum):
    """Raw column names as they arrive in the competition parquet files."""

    # Identity
    MVT_ID = "MVT_ID_mvt"
    FLIGHT_ID = "FLIGHT_ID_mvt"

    # What is being predicted, and the two instants it is the gap between
    TARGET = "TAXITIME_SEC_mvt"
    BLOCK_TIME = "BLOCK_TIME_UTC_mvt"
    MVT_TIME = "MVT_TIME_UTC_mvt"
    SCHED_TIME = "SCHED_TIME_UTC_mvt"

    # Where the movement happened.
    # ADEP is the ORIGIN of the flight, not the airport of the movement: on an arrival
    # row it names where the aircraft came from. The movement airport is derived, see
    # `MOVEMENT_AIRPORT` below.
    ADEP = "ADEP_mvt"
    ADES = "ADES_mvt"
    ADEP_FLT = "ADEP_flt"
    ADES_FLT = "ADES_flt"
    ADES_FILED = "ADES_FILED_flt"
    PHASE = "PHASE_mvt"
    STAND = "STAND_mvt"
    RUNWAY = "RUNWAY_mvt"

    # Flight identity and rules
    FLIGHT = "FLIGHT_mvt"
    CALLSIGN = "CALLSIGN_flt"
    FLIGHT_RULE = "FLIGHT_RULE_mvt"
    FLIGHT_RULE_FLT = "FLIGHT_RULE_flt"
    FLIGHT_TYPE = "FLIGHT_TYPE_flt"

    # Aircraft
    AIRCRAFT_TYPE = "AIRCRAFT_TYPE_mvt"
    AIRCRAFT_TYPE_FLT = "AIRCRAFT_TYPE_flt"
    WAKE_CATEGORY = "WK_TBL_CAT_flt"
    MARKET_SEGMENT = "MARKET_SEGMENT_flt"
    OPERATOR = "AIRCRAFT_OPERATOR_flt"

    # Network Manager times. AOBT_3 is an independent measurement of the off-block
    # instant and is NOT blanked in the ranking set, which is what makes it usable.
    AOBT_3 = "AOBT_3_flt"
    ARVT_3 = "ARVT_3_flt"
    ARVT_1 = "ARVT_1_flt"
    EOBT_1 = "EOBT_1_flt"
    IOBT = "IOBT_flt"
    LOBT = "LOBT_flt"


# Derived, not present in the raw files: the airport the movement actually happened at,
# ADEP for a departure and ADES for an arrival.
MOVEMENT_AIRPORT = "apt_mvt"


class Phase(StrEnum):
    """The value of `Col.PHASE`."""

    DEPARTURE = "DEP"
    ARRIVAL = "ARR"


# The ten airports present in the data. LTAI appears in the competition description but
# not in a single row of it (docs/facts.md R02).
AIRPORTS = (
    "EDDF", "EDDM", "EGLL", "EHAM", "LEBL",
    "LEMD", "LFPG", "LIRF", "LSZH", "LTFM",
)

# The ranking set is January and July 2026, but it does not cover the same airports in
# both: all ten in January, only these three in July.
RANKING_MONTHS = (1, 7)
JULY_AIRPORTS = ("EDDF", "EGLL", "EHAM")
