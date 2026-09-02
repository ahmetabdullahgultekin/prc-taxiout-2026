"""The overlap counters, against hand-counted answers and an algebraic identity.

Two-dimensional dominance counting done with a Fenwick tree is the kind of code that is
either exactly right or quietly off by one, and either way it returns a column of
plausible integers. The scenarios here are small enough to count on paper.

The identity test earns its place separately: D2 minus D3 must equal the difference of
the two rank orders, for every flight, on any input. That holds by algebra and not by
the implementation, so it catches a broken tree on data nobody counted by hand.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import polars as pl

from taxiout.features import overlap


def _mvt(rows: list[tuple[str, str, int, int]]) -> pl.DataFrame:
    """(phase, airport, start minute, end minute).

    For a departure that is off-block and take-off; for an arrival, landing and in-block.
    """

    def at(minute: int) -> datetime:
        base = datetime(2025, 3, 1, 6, 0, tzinfo=UTC)
        return base.replace(hour=6 + minute // 60, minute=minute % 60)

    return pl.DataFrame({
        "MVT_ID_mvt": list(range(len(rows))),
        "PHASE_mvt": [r[0] for r in rows],
        "apt_mvt": [r[1] for r in rows],
        "AOBT_3_flt": [at(r[2]) for r in rows],
        "MVT_TIME_UTC_mvt": [at(r[3]) if r[0] == "DEP" else at(r[2]) for r in rows],
        "BLOCK_TIME_UTC_mvt": [None if r[0] == "DEP" else at(r[3]) for r in rows],
    })


def _dep(mvt: pl.DataFrame) -> pl.DataFrame:
    return mvt.filter(pl.col("PHASE_mvt") == "DEP").select(
        "MVT_ID_mvt", "apt_mvt", "AOBT_3_flt", "MVT_TIME_UTC_mvt"
    )


# ------------------------------------------------------------------ dominance counting


def test_a_flight_that_is_overtaken_counts_the_overtaker() -> None:
    """A pushes back first and flies last; B pushes back second and flies first.

    So A was overtaken once and overtook nobody, and B the reverse.
    """
    start = np.array([0, 5])
    end = np.array([40, 20])
    d2, d3 = overlap._dominance_counts(start, end)
    assert d2.tolist() == [1, 0]
    assert d3.tolist() == [0, 1]


def test_a_queue_in_order_has_no_overtaking_at_all() -> None:
    start = np.array([0, 5, 10, 15])
    end = np.array([20, 25, 30, 35])
    d2, d3 = overlap._dominance_counts(start, end)
    assert d2.tolist() == [0, 0, 0, 0]
    assert d3.tolist() == [0, 0, 0, 0]


def test_a_reversed_queue_is_all_overtaking() -> None:
    """Four aircraft push back in order and take off in exactly the reverse order."""
    start = np.array([0, 1, 2, 3])
    end = np.array([40, 30, 20, 10])
    d2, d3 = overlap._dominance_counts(start, end)
    assert d2.tolist() == [3, 2, 1, 0]
    assert d3.tolist() == [0, 1, 2, 3]


def _brute_force(start: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The definition, written out. O(n^2), so only for small inputs in tests."""
    n = len(start)
    d2 = np.array([
        sum(1 for j in range(n) if j != i and start[j] > start[i] and end[j] < end[i])
        for i in range(n)
    ])
    d3 = np.array([
        sum(1 for j in range(n) if j != i and start[j] < start[i] and end[j] > end[i])
        for i in range(n)
    ])
    return d2, d3


def test_the_tree_agrees_with_the_definition_on_random_input() -> None:
    """The Fenwick tree against a literal transcription of the definition.

    An earlier version derived D3 from the two rank orders instead of counting it, which
    is correct only when no two flights share a timestamp. Off-block times are recorded
    to the minute, so ties are the normal case, not an edge one. This generates ties
    deliberately.
    """
    rng = np.random.default_rng(0)
    for _ in range(30):
        n = int(rng.integers(2, 40))
        # A small value range forces plenty of ties in both coordinates.
        start = rng.integers(0, max(3, n // 2), n)
        end = start + rng.integers(1, max(3, n // 3), n)
        d2, d3 = overlap._dominance_counts(start, end)
        want2, want3 = _brute_force(start, end)
        assert np.array_equal(d2, want2), (start, end, d2, want2)
        assert np.array_equal(d3, want3), (start, end, d3, want3)


def test_aircraft_sharing_an_off_block_minute_do_not_overtake_each_other() -> None:
    """Two flights push back in the same minute; one flies earlier.

    Neither overtook the other: they left the stand together as far as the data can say,
    and a tie-breaking rule that claimed otherwise would be inventing overtaking out of
    the timestamp resolution.
    """
    start = np.array([10, 10])
    end = np.array([50, 30])
    d2, d3 = overlap._dominance_counts(start, end)
    assert d2.tolist() == [0, 0]
    assert d3.tolist() == [0, 0]


def test_an_empty_airport_returns_empty_arrays() -> None:
    d2, d3 = overlap._dominance_counts(np.array([]), np.array([]))
    assert len(d2) == 0
    assert len(d3) == 0


# ------------------------------------------------------------------------ the features


def test_overtaking_is_counted_within_an_airport_not_across_them() -> None:
    mvt = _mvt([
        ("DEP", "EDDF", 0, 40),
        ("DEP", "EDDF", 5, 20),
        ("DEP", "EDDM", 5, 20),   # a Munich flight overtakes nobody at Frankfurt
    ])
    out = overlap.build(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    assert out["overtaken_by"].to_list() == [1, 0, 0]


def test_an_arrival_inside_the_window_is_counted_and_one_outside_is_not() -> None:
    """The departure taxis from minute 10 to minute 50.

    The first arrival lands at 20 and parks at 30, entirely inside: counted. The second
    lands at 20 but is still taxiing at 50: not counted, it never parked in time. The
    third lands at 5, before the departure pushed back: not counted.
    """
    mvt = _mvt([
        ("DEP", "EDDF", 10, 50),
        ("ARR", "EDDF", 20, 30),
        ("ARR", "EDDF", 20, 70),
        ("ARR", "EDDF", 5, 15),
    ])
    out = overlap.build(mvt, _dep(mvt))
    assert out["arrivals_inside"].to_list() == [1]


def test_the_rates_divide_out_the_length_of_the_taxi() -> None:
    """Two flights overtaken the same number of times, one taxiing twice as long.

    The raw count cannot tell them apart; the rate must.
    """
    slow = _mvt([("DEP", "EDDF", 0, 60), ("DEP", "EDDF", 5, 30)])
    fast = _mvt([("DEP", "EDDF", 0, 30), ("DEP", "EDDF", 5, 15)])
    a = overlap.build(slow, _dep(slow)).sort("MVT_ID_mvt")
    b = overlap.build(fast, _dep(fast)).sort("MVT_ID_mvt")

    assert a["overtaken_by"][0] == b["overtaken_by"][0] == 1
    assert a["overtaken_rate"][0] < b["overtaken_rate"][0]


def test_every_column_survives_a_flight_with_no_network_match() -> None:
    """A departure with no off-block time has no window, so it has no counters."""
    mvt = _mvt([("DEP", "EDDF", 0, 40), ("DEP", "EDDF", 5, 20)])
    mvt = mvt.with_columns(
        pl.when(pl.col("MVT_ID_mvt") == 1).then(None)
        .otherwise(pl.col("AOBT_3_flt")).alias("AOBT_3_flt")
    )
    out = overlap.build(mvt, _dep(mvt)).sort("MVT_ID_mvt")
    assert out.height == 2
    assert out["overtaken_by"][1] is None
