"""Verifies that the movement airport is derived correctly.

These tests exist because of a concrete bug. `ADEP_mvt` was taken to mean "the airport of
the movement" for a long time; it is in fact **the departure airport of the flight**, and
on arrival rows it names the place the aircraft CAME FROM (1,582 distinct values in the
training set). The result: when counting the arrivals around a departure, we were counting
distant arrivals that had departed from that airport instead of the ones landing there.

At the time the synthetic fixture made `ADEP_mvt` a competition airport on every row, so no
test could see it. The fixture was fixed, and these tests hold the fix in place.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from taxiout.application import pipeline
from taxiout.features import congestion


def _frame() -> pl.DataFrame:
    """A departure at EDDF, an arrival at EDDF from LTFM, a departure at LTFM."""
    t0 = datetime(2025, 5, 1, 10, 0)
    return pl.DataFrame({
        "MVT_ID_mvt": [1, 2, 3],
        "PHASE_mvt": ["DEP", "ARR", "DEP"],
        "ADEP_mvt": ["EDDF", "LTFM", "LTFM"],   # departure airport of the flight
        "ADES_mvt": ["LTFM", "EDDF", "EGLL"],   # arrival airport of the flight
        "RUNWAY_mvt": ["07L", "07R", "34L"],
        "STAND_mvt": ["A1", "B2", "C3"],
        "MVT_TIME_UTC_mvt": [t0, t0 - timedelta(minutes=5), t0],
        "BLOCK_TIME_UTC_mvt": [t0 - timedelta(minutes=15), t0, t0 - timedelta(minutes=12)],
        "TAXITIME_SEC_mvt": [900, 300, 720],
    })


def test_movement_airport_is_adep_for_departures_and_ades_for_arrivals() -> None:
    out = pipeline.prepare_movements(_frame()).sort("MVT_ID_mvt")
    assert out[pipeline.APT].to_list() == ["EDDF", "EDDF", "LTFM"]


def test_arrivals_are_counted_at_the_airport_they_landed_at() -> None:
    """This was the bug: an arrival counts at the airport it landed at, not the one it left.

    The arrival in the example departed from LTFM and landed at EDDF. It must be counted
    around the EDDF departure, not around the LTFM one.
    """
    mvt = pipeline.prepare_movements(_frame())
    dep = congestion.runway_features(mvt)
    out = congestion.airport_features(mvt, dep).join(
        dep.select("MVT_ID_mvt", pipeline.APT), on="MVT_ID_mvt"
    )
    eddf = out.filter(pl.col(pipeline.APT) == "EDDF")["apt_arr_prev_15m"][0]
    ltfm = out.filter(pl.col(pipeline.APT) == "LTFM")["apt_arr_prev_15m"][0]
    assert eddf == 1, "an aircraft landing at EDDF counts around the EDDF departure"
    assert ltfm == 0, "that arrival must not count at LTFM, it only departed from there"


def test_grouping_on_adep_would_give_the_wrong_answer() -> None:
    """Negative control: does the old (wrong) grouping produce a different answer.

    If it does not, this test protects nothing.
    """
    mvt = pipeline.prepare_movements(_frame())
    right = mvt.filter((pl.col("PHASE_mvt") == "ARR") & (pl.col(pipeline.APT) == "EDDF")).height
    wrong = mvt.filter((pl.col("PHASE_mvt") == "ARR") & (pl.col("ADEP_mvt") == "EDDF")).height
    assert right == 1
    assert wrong == 0
    assert right != wrong
