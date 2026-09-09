"""The surface count and the excess-delay sensor, against hand-counted answers.

Both features are plain arithmetic over the movement stream, which means a wrong
implementation returns a plausible number rather than an error. A count that is off by
one, a window that includes the flight itself, an unsigned subtraction that wraps: all
of them produce a column full of sensible-looking integers. So the scenarios here are
small enough to count by hand and the expected values are written out.

The wrapping one is not hypothetical. The first version totalled with `pl.len()`, which
polars types as u32, and the surface count is a difference of two such totals. Where it
should have been negative it came back as 4,294,967,295.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from taxiout.features import surface_delay


def _mvt(rows: list[tuple[str, str, str, int, int, int | None]]) -> pl.DataFrame:
    """(phase, airport, runway, off-block minute, take-off minute, taxi seconds)."""

    def at(minute: int) -> datetime:
        return datetime(2025, 3, 1, 8, 0, tzinfo=UTC).replace(
            minute=minute % 60, hour=8 + minute // 60
        )

    return pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(len(rows))),
            "PHASE_mvt": [r[0] for r in rows],
            "apt_mvt": [r[1] for r in rows],
            "RUNWAY_mvt": [r[2] for r in rows],
            "AOBT_3_flt": [at(r[3]) for r in rows],
            "MVT_TIME_UTC_mvt": [at(r[4]) for r in rows],
            "TAXITIME_SEC_mvt": [r[5] for r in rows],
        }
    )


def _dep(mvt: pl.DataFrame) -> pl.DataFrame:
    return mvt.filter(pl.col("PHASE_mvt") == "DEP").select(
        "MVT_ID_mvt", "apt_mvt", "RUNWAY_mvt", "AOBT_3_flt", "MVT_TIME_UTC_mvt"
    )


# --------------------------------------------------------------------- surface count


def test_surface_count_is_the_queue_the_flight_joined() -> None:
    """Three aircraft push back in order and take off in the same order.

    A pushes back at 00 and flies at 20. B pushes back at 05, so A is still out there:
    one ahead. C pushes back at 10, with both A and B still out: two ahead.
    """
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 20, 1200),
        ("DEP", "EDDF", "25C", 5, 25, 1200),
        ("DEP", "EDDF", "25C", 10, 30, 1200),
    ])
    out = surface_delay.surface_count(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    assert out["surface_apt_at_pushback"].to_list() == [0, 1, 2]


def test_surface_count_falls_as_aircraft_leave() -> None:
    """A is long gone by the time C pushes back, so it is not in front of anyone."""
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 5, 300),     # away at 05
        ("DEP", "EDDF", "25C", 2, 40, 2280),   # still out at 30
        ("DEP", "EDDF", "25C", 30, 45, 900),
    ])
    out = surface_delay.surface_count(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    # Only the second aircraft is still on the surface when the third pushes back.
    assert out["surface_apt_at_pushback"].to_list() == [0, 1, 1]


def test_surface_count_never_goes_negative() -> None:
    """The regression test for the unsigned wrap.

    A single departure has nothing ahead of it. The count is a difference of two running
    totals and the arithmetic must be signed, or this reads 4,294,967,295.
    """
    mvt = _mvt([("DEP", "EDDF", "25C", 0, 15, 900)])
    out = surface_delay.surface_count(mvt, _dep(mvt))
    for col in ("surface_apt_at_pushback", "surface_apt_at_takeoff",
                "surface_rwy_at_pushback", "surface_rwy_at_takeoff"):
        assert out[col].to_list() == [0], col
        assert out[col].max() < 1000, f"{col} wrapped"


def test_surface_count_separates_airports() -> None:
    """Two aircraft queueing at Munich are not in front of one at Frankfurt."""
    mvt = _mvt([
        ("DEP", "EDDM", "26L", 0, 40, 2400),
        ("DEP", "EDDM", "26L", 1, 41, 2400),
        ("DEP", "EDDF", "25C", 10, 30, 1200),
    ])
    out = surface_delay.surface_count(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    assert out["surface_apt_at_pushback"].to_list() == [0, 1, 0]


def test_runway_scope_is_narrower_than_the_airport() -> None:
    """A busy airport with this flight's own runway empty is not a busy runway."""
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 40, 2400),
        ("DEP", "EDDF", "25C", 1, 41, 2400),
        ("DEP", "EDDF", "18", 10, 30, 1200),
    ])
    out = surface_delay.surface_count(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    assert out["surface_apt_at_pushback"].to_list() == [0, 1, 2]
    assert out["surface_rwy_at_pushback"].to_list() == [0, 1, 0]


def test_a_flight_without_a_network_match_does_not_corrupt_the_counts() -> None:
    """The bug that made this feature constant on real data.

    The Network Manager has no off-block time for about 1.5 percent of departures. If
    those flights are counted in the take-off total but not the push-back total, the
    difference between the two drifts down by the number of unmatched flights seen so
    far. Over a year at Frankfurt that reached about 46, which buries a real queue of
    five to twenty and clips the whole column to zero.

    Nothing failed when this happened. The column was simply constant, and the first
    ablation of it returned numbers that could not be true: removing any one of six
    columns improved the model by ten seconds.

    Here the second aircraft has no network time. The third must still see the first
    ahead of it.
    """
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 40, 2400),   # still out at 30
        ("DEP", "EDDF", "25C", 1, 20, 1140),   # no network match, see below
        ("DEP", "EDDF", "25C", 30, 45, 900),
    ])
    mvt = mvt.with_columns(
        pl.when(pl.col("MVT_ID_mvt") == 1)
        .then(None)
        .otherwise(pl.col("AOBT_3_flt"))
        .alias("AOBT_3_flt")
    )
    out = surface_delay.surface_count(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    counts = out["surface_apt_at_pushback"].to_list()
    assert counts[2] == 1, f"the third aircraft should see one ahead, got {counts[2]}"
    assert min(counts) >= 0


def test_arrivals_are_not_counted_as_departures_on_the_surface() -> None:
    mvt = _mvt([
        ("ARR", "EDDF", "25C", 0, 40, 600),
        ("DEP", "EDDF", "25C", 10, 30, 1200),
    ])
    out = surface_delay.surface_count(mvt, _dep(mvt))
    assert out["surface_apt_at_pushback"].to_list() == [0]


# ---------------------------------------------------------------------- excess delay


def test_excess_delay_excludes_the_flight_itself() -> None:
    """The one property that makes this feature legitimate rather than leakage.

    Four departures share a runway. The baseline is the tenth percentile of their taxi
    times, so the quickest sets it. The last flight's own excess must not appear in the
    average it is given.
    """
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 10, None),    # 600 s
        ("DEP", "EDDF", "25C", 1, 11, None),    # 600 s
        ("DEP", "EDDF", "25C", 2, 22, None),    # 1200 s
        ("DEP", "EDDF", "25C", 3, 33, None),    # 1800 s, the flight under test
    ])
    out = surface_delay.excess_delay(mvt, _dep(mvt), minutes=60).sort("MVT_ID_mvt")

    # Three others precede the last flight, so its window holds exactly three.
    assert out["surface_excess_n"].to_list()[-1] == 3
    # Baseline is about 600 s, so the others are at roughly 0, 0 and 600 over it: a mean
    # near 200. Its own 1200 s of excess would have pulled the mean far above that.
    last = out["surface_excess_sec"].to_list()[-1]
    assert 100 < last < 300, last


def test_a_lone_departure_has_no_one_to_average() -> None:
    mvt = _mvt([("DEP", "EDDF", "25C", 0, 20, None)])
    out = surface_delay.excess_delay(mvt, _dep(mvt))
    assert out["surface_excess_n"].to_list() == [0]
    assert out["surface_excess_sec"].to_list() == [None]


def test_a_congested_airport_reads_higher_than_a_quiet_one() -> None:
    """The whole point: the number has to move with how the surface is actually running."""
    quiet = _mvt([("DEP", "EDDM", "26L", i, i + 10, None) for i in range(6)])
    busy = _mvt([("DEP", "EDDF", "25C", i, i + 10, None) for i in range(3)]
                + [("DEP", "EDDF", "25C", i, i + 50, None) for i in range(3, 6)])
    q = surface_delay.excess_delay(quiet, _dep(quiet), minutes=60)
    b = surface_delay.excess_delay(busy, _dep(busy), minutes=60)
    assert q["surface_excess_sec"].max() == pytest.approx(0.0, abs=1.0)
    assert b["surface_excess_sec"].max() > 500


def test_an_impossible_taxi_time_is_kept_out_of_the_average() -> None:
    """A clock error of thirty hours must not become the airport's excess delay.

    It also must not be subtracted as the flight's own contribution, since it was never
    added: that would bias the window the other way and still look plausible.
    """
    mvt = _mvt([
        ("DEP", "EDDF", "25C", 0, 10, None),
        ("DEP", "EDDF", "25C", 1, 11, None),
        ("DEP", "EDDF", "25C", 2, 12, None),
    ])
    # Push one off-block back by 30 hours, well past the four-hour filter.
    broken = mvt.with_columns(
        pl.when(pl.col("MVT_ID_mvt") == 1)
        .then(pl.col("AOBT_3_flt") - pl.duration(hours=30))
        .otherwise(pl.col("AOBT_3_flt"))
        .alias("AOBT_3_flt")
    )
    out = surface_delay.excess_delay(broken, _dep(broken), minutes=60).sort("MVT_ID_mvt")
    assert out["surface_excess_n"].min() >= 0
    values = [v for v in out["surface_excess_sec"].to_list() if v is not None]
    assert all(v < 3600 for v in values), values
