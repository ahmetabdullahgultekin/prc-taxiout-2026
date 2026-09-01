"""Validation of the congestion features.

Window counting is the most error-prone part of this pipeline: an off-by-one or a wrong
window boundary breaks the model silently and never shows up in the RMSE. So the
vectorised implementation is compared against a brute-force reference that computes the
same thing in the obvious but slow way.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from taxiout.features import congestion


def _sample(n: int = 400, seed: int = 7) -> pl.DataFrame:
    import numpy as np

    rng = np.random.default_rng(seed)
    start = datetime(2025, 3, 1)
    apt = rng.choice(["EDDF", "LTFM"], n)
    rwy = rng.choice(["07L", "25R"], n)
    phase = rng.choice(["DEP", "ARR"], n)
    offs = np.sort(rng.integers(0, 6 * 3600, n))
    return pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(n)),
            "apt_mvt": apt,
            "RUNWAY_mvt": rwy,
            "STAND_mvt": rng.choice(["A1", "B2", "C3"], n),
            "PHASE_mvt": phase,
            "MVT_TIME_UTC_mvt": [start + timedelta(seconds=int(s)) for s in offs],
            "TAXITIME_SEC_mvt": rng.integers(200, 1500, n),
        }
    )


def _brute_count(rows, i, group_cols, minutes, forward):
    """The obvious reference: applies the half-open definition from the docstring, O(n^2).

    backward:  (t - W, t]   forward: (t, t + W]
    """
    t = rows[i]["MVT_TIME_UTC_mvt"]
    key = tuple(rows[i][c] for c in group_cols)
    span = timedelta(minutes=minutes)
    total = 0
    for r in rows:
        if tuple(r[c] for c in group_cols) != key:
            continue
        u = r["MVT_TIME_UTC_mvt"]
        if forward:
            if t < u <= t + span:
                total += 1
        elif t - span < u <= t:
            total += 1
    return total


@pytest.mark.parametrize("minutes", [5, 15, 60])
@pytest.mark.parametrize("forward", [False, True])
def test_counts_in_window_matches_brute_force(minutes: int, forward: bool) -> None:
    df = _sample().filter(pl.col("PHASE_mvt") == "DEP")
    group = ["apt_mvt", "RUNWAY_mvt"]
    got = congestion._counts_in_window(df, df, group, minutes, forward, "n").sort("MVT_ID_mvt")

    rows = df.sort("MVT_ID_mvt").to_dicts()
    expected = [_brute_count(rows, i, group, minutes, forward) for i in range(len(rows))]
    assert got["n"].to_list() == expected


def test_forward_and_backward_are_not_identical() -> None:
    """A negative control, so the test does not pass silently if the direction is mixed up."""
    df = _sample().filter(pl.col("PHASE_mvt") == "DEP")
    group = ["apt_mvt", "RUNWAY_mvt"]
    back = congestion._counts_in_window(df, df, group, 15, False, "n").sort("MVT_ID_mvt")["n"]
    fwd = congestion._counts_in_window(df, df, group, 15, True, "n").sort("MVT_ID_mvt")["n"]
    assert back.to_list() != fwd.to_list()


def test_build_produces_one_row_per_departure() -> None:
    mvt = _sample()
    out = congestion.build(mvt)
    n_dep = mvt.filter(pl.col("PHASE_mvt") == "DEP").height
    assert out.height == n_dep
    assert out["MVT_ID_mvt"].n_unique() == n_dep


def test_build_has_no_target_column() -> None:
    """The feature table must not carry the target; that is how leakage gets in."""
    out = congestion.build(_sample())
    leaky = {"BLOCK_TIME_UTC_mvt"}
    assert not leaky & set(out.columns)


def test_taxi_in_pressure_is_available_without_departure_targets() -> None:
    """The setup of the ranking set: DEP taxi times are empty, ARR ones are filled.

    The whole value of this feature comes from being computable under that condition.
    """
    mvt = _sample()
    blanked = mvt.with_columns(
        pl.when(pl.col("PHASE_mvt") == "DEP")
        .then(None)
        .otherwise(pl.col("TAXITIME_SEC_mvt"))
        .alias("TAXITIME_SEC_mvt")
    )
    dep = congestion.runway_features(blanked)
    out = congestion.taxi_in_pressure(blanked, dep)
    assert out["arr_taxi_median_sec"].null_count() < out.height


@pytest.mark.parametrize("forward", [False, True])
def test_counts_are_correct_when_timestamps_are_minute_rounded(forward: bool) -> None:
    """HH:MM precision: dozens of movements in the same minute. This was the bug we fixed.

    A counter that relies on row order gives inconsistent results across equal timestamps,
    and in the real data that is not the exception but the rule at some airports (M14).
    """
    import numpy as np

    rng = np.random.default_rng(3)
    n = 300
    start = datetime(2025, 3, 1)
    # zero out the seconds: produce a lot of ties
    offs = np.sort(rng.integers(0, 120, n) * 60)
    df = pl.DataFrame(
        {
            "MVT_ID_mvt": list(range(n)),
            "apt_mvt": ["EDDF"] * n,
            "RUNWAY_mvt": rng.choice(["07L", "25R"], n),
            "PHASE_mvt": ["DEP"] * n,
            "MVT_TIME_UTC_mvt": [start + timedelta(seconds=int(s)) for s in offs],
        }
    )
    # are there really ties (verify the test's own premise)
    assert df["MVT_TIME_UTC_mvt"].n_unique() < n

    group = ["apt_mvt", "RUNWAY_mvt"]
    got = congestion._counts_in_window(df, df, group, 15, forward, "n").sort("MVT_ID_mvt")
    rows = df.sort("MVT_ID_mvt").to_dicts()
    expected = [_brute_count(rows, i, group, 15, forward) for i in range(len(rows))]
    assert got["n"].to_list() == expected


def _sample_with_block(n: int = 400, seed: int = 5) -> pl.DataFrame:
    """A sample that also has the block time: causal mode needs it."""
    import numpy as np

    df = _sample(n, seed)
    rng = np.random.default_rng(seed)
    taxi = rng.integers(300, 1500, n)
    return df.with_columns(
        BLOCK_TIME_UTC_mvt=pl.col("MVT_TIME_UTC_mvt")
        - pl.duration(seconds=pl.Series(taxi.tolist()))
    )


def test_causal_mode_emits_no_forward_looking_features() -> None:
    """This is the only thing a causal model means: it knows nothing about the future.

    If a forward-looking column leaks in, the model loses its 'real time' claim and the
    comparison in the paper becomes meaningless. So it is audited from the column names.
    """
    out = congestion.build(_sample_with_block(), causal=True)
    forward = [c for c in out.columns if "_next_" in c]
    assert forward == [], f"forward-looking columns in causal mode: {forward}"


def test_retrospective_mode_does_emit_forward_features() -> None:
    """Negative control: does the flag actually change anything."""
    out = congestion.build(_sample_with_block(), causal=False)
    assert [c for c in out.columns if "_next_" in c]


def test_causal_counts_are_anchored_at_pushback_not_takeoff() -> None:
    """Causal counts must be anchored at the off-block instant.

    The two modes must give different counts for the same row; if they come out the same
    the anchor was not applied and the test would have passed silently.
    """
    mvt = _sample_with_block()
    col = "rwy_dep_prev_30m"
    causal = congestion.build(mvt, causal=True).select("MVT_ID_mvt", col).sort("MVT_ID_mvt")
    retro = congestion.build(mvt, causal=False).select("MVT_ID_mvt", col).sort("MVT_ID_mvt")
    assert causal[col].to_list() != retro[col].to_list()


def test_causal_window_counts_only_takeoffs_before_pushback() -> None:
    """A hand-built case: only take-offs before the off-block instant may be counted."""
    start = datetime(2025, 6, 1, 12, 0)
    mvt = pl.DataFrame(
        {
            "MVT_ID_mvt": [0, 1, 2],
            "apt_mvt": ["EDDF"] * 3,
            "RUNWAY_mvt": ["18"] * 3,
            "STAND_mvt": ["A1"] * 3,
            "PHASE_mvt": ["DEP"] * 3,
            # 0 and 1 took off early; 2 goes off block at 12:20 and takes off at 12:40
            "MVT_TIME_UTC_mvt": [
                start, start + timedelta(minutes=10), start + timedelta(minutes=40)
            ],
            "BLOCK_TIME_UTC_mvt": [
                start - timedelta(minutes=10),
                start,
                start + timedelta(minutes=20),
            ],
            "TAXITIME_SEC_mvt": [600, 600, 1200],
        }
    )
    out = congestion.build(mvt, causal=True).sort("MVT_ID_mvt")
    # for id=2: off block at 12:20, 30 min back -> take-offs in (11:50, 12:20] are
    # 12:00 (id=0) and 12:10 (id=1) = 2. Its own take-off at 12:40 must not be counted.
    assert out.filter(pl.col("MVT_ID_mvt") == 2)["rwy_dep_prev_30m"][0] == 2
