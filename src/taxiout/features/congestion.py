"""Congestion and departure-queue features.

These are the substantive part of the model. The reasoning:

In the ranking set, departures have **only** their block time and taxi time blanked
(fact D05). The take-off time (`MVT_TIME_UTC_mvt`), runway and stand are all present,
and arrival rows are untouched (D09). The challenge asks for a **post-operations**
model, used to identify constrained intervals and measure excess fuel burn (M01), so
using traffic that occurred after a departure's own take-off is legitimate here rather
than a trick; it is the shape of the problem.

The strongest single explanatory variable in the literature is the takeoff queue size
of Idris et al. (Boston Logan, 2002): the number of aircraft that departed from the
runway between an aircraft's pushback and its own take-off. In live operation that
variable has to be *forecast*, because future departures are unknown. Here they are
observed.

**The circularity trap.** Counting that queue exactly requires the pushback time, which
is the quantity we are predicting, so a fixed-point iteration could feed on itself. The
core features are therefore **non-circular** proxies: fixed look-back and look-forward
windows (5/10/15/30/60 minutes). The model learns which horizon matters at which
airport, which is strictly better than committing to one, and no loop is involved.

## Two anchors: retrospective and causal

The same code produces two models. The difference is **which instant the features are
anchored to**:

| | anchor | forward windows | where it can be evaluated |
|---|---|---|---|
| **retrospective** | take-off (`MVT_TIME_UTC_mvt`) | yes | anywhere, ranking set included |
| **causal** | off-block (`BLOCK_TIME_UTC_mvt`) | no | only where block time is known |

The retrospective model is the competition submission, and is also what a KPI
calculation or a data-gap fill would use. The causal model is the one an A-CDM, TSAT or
DMAN system could run in real time, and is reported in the paper only.

Both can be scored on the same holdout, because both anchors are known there. The gap
between them is the **information value of retrospective observability**, and it bounds
what a real-time system could gain. Idris's queue variable must be forecast in
operation; this puts a number on that (see `docs/literature.md`).
"""

from __future__ import annotations

import polars as pl

from taxiout.domain.schema import Col

MVT = Col.MVT_TIME
# The airport the movement happened at; added by `pipeline.prepare_movements`.
# NOT `ADEP_mvt`, which is the flight's origin and names, on an arrival row, the
# airport the aircraft came from.
APT = "apt_mvt"
RWY = Col.RUNWAY
PHASE = Col.PHASE
BLOCK = Col.BLOCK_TIME

# Look-back and look-forward horizons, in minutes. The model picks what it needs.
WINDOWS_MIN = (5, 10, 15, 30, 60)


def _cumulative_by_time(events: pl.DataFrame, group: list[str], at: str) -> pl.DataFrame:
    """(group, time) -> number of events up to and including that instant.

    Produces a single value per distinct timestamp. That matters: several airports
    report to the minute, so dozens of movements can share an instant, and a counter
    based on row order would give tied rows inconsistent answers.
    """
    return (
        events.filter(pl.col(at).is_not_null())
        .group_by([*group, at])
        .agg(_k=pl.len())
        .sort(at)
        .with_columns(_cum=pl.col("_k").cum_sum().over(group))
        .select(*group, at, "_cum")
        .sort(at)
    )


def _cum_at(
    keys: pl.DataFrame, cum: pl.DataFrame, group: list[str], probe: pl.Expr, event_at: str
) -> pl.Series:
    """Cumulative count at the instant given by `probe`, for every key row."""
    frame = keys.select(*group, _probe=probe).with_row_index("_row")
    return (
        frame.sort("_probe")
        .join_asof(cum, left_on="_probe", right_on=event_at, by=group, strategy="backward")
        .sort("_row")
        .get_column("_cum")
        .fill_null(0)
    )


def _counts_in_window(
    keys: pl.DataFrame,
    events: pl.DataFrame,
    group: list[str],
    minutes: int,
    forward: bool,
    name: str,
    key_at: str = MVT,
    event_at: str | None = None,
) -> pl.DataFrame:
    """Count `events` inside a window around each row of `keys`.

    Window definitions, deliberately half-open so that ties are handled consistently:

    - backward: ``(t - W, t]``  -- **counts** events sharing the instant
    - forward:  ``(t, t + W]``  -- **excludes** events sharing the instant

    `key_at` is the time column of the query instant and `event_at` that of the counted
    events, and they **can differ**. The causal question is not symmetric: it asks how
    many aircraft had already taken off (event_at = take-off) by the time this one
    pushed back (key_at = off-block). In retrospective mode both are the take-off time.
    """
    event_at = event_at or key_at
    cum = _cumulative_by_time(events, group, event_at)
    delta = pl.duration(minutes=minutes)
    here = _cum_at(keys, cum, group, pl.col(key_at), event_at)
    other = _cum_at(
        keys, cum, group, pl.col(key_at) + delta if forward else pl.col(key_at) - delta, event_at
    )
    counts = (other - here) if forward else (here - other)
    return keys.with_columns(counts.cast(pl.Int32).alias(name))


def runway_features(mvt: pl.DataFrame, anchor: str = MVT, forward: bool = True) -> pl.DataFrame:
    """Runway service rate and departure sequencing.

    Input: **all** movements of one dataset (training or ranking), arrivals included.
    Output: one row per departure, keyed by `MVT_ID_mvt`.

    `anchor` selects the instant features are tied to; `forward=False` disables the
    look-forward windows for the causal variant (see the table in the module docstring).
    """
    dep = mvt.filter(pl.col(PHASE) == "DEP").filter(pl.col(anchor).is_not_null()).sort(anchor)

    # Gap between consecutive departures: the runway's service interval at that moment.
    dep = dep.with_columns(
        prev_dep_gap_sec=(pl.col(anchor) - pl.col(anchor).shift(1).over([APT, RWY]))
        .dt.total_seconds()
        .cast(pl.Float32),
    )
    if forward:
        dep = dep.with_columns(
            next_dep_gap_sec=(pl.col(anchor).shift(-1).over([APT, RWY]) - pl.col(anchor))
            .dt.total_seconds()
            .cast(pl.Float32),
        )
    # Mean of the last five gaps: the runway's throughput right now.
    dep = dep.with_columns(
        rwy_service_interval_sec=pl.col("prev_dep_gap_sec")
        .rolling_mean(window_size=5, min_samples=2)
        .over([APT, RWY])
        .cast(pl.Float32)
    )

    for w in WINDOWS_MIN:
        dep = _counts_in_window(
            dep, dep, [APT, RWY], w, False, f"rwy_dep_prev_{w}m", anchor, MVT
        )
        if forward:
            dep = _counts_in_window(
                dep, dep, [APT, RWY], w, True, f"rwy_dep_next_{w}m", anchor, MVT
            )

    return dep


def airport_features(
    mvt: pl.DataFrame, dep: pl.DataFrame, anchor: str = MVT, forward: bool = True
) -> pl.DataFrame:
    """Airport-wide traffic pressure: departure and arrival intensity.

    The arrival counts are particularly useful because arrival rows are not blanked in
    the ranking set (D09), so they can be computed exactly for January and July 2026.
    Landing aircraft occupy taxiways and stands and slow the departure flow.
    """
    arr = mvt.filter(pl.col(PHASE) == "ARR").select(APT, MVT).sort(MVT)
    # `anchor` and MVT can be the same column; selecting it twice is an error in polars.
    time_cols = list(dict.fromkeys([anchor, MVT]))
    dep_all = dep.select(Col.MVT_ID, APT, *time_cols).sort(anchor)

    out = dep_all
    for w in WINDOWS_MIN:
        out = _counts_in_window(out, arr, [APT], w, False, f"apt_arr_prev_{w}m", anchor, MVT)
        out = _counts_in_window(
            out, dep_all, [APT], w, False, f"apt_dep_prev_{w}m", anchor, MVT
        )
        if forward:
            out = _counts_in_window(
                out, arr, [APT], w, True, f"apt_arr_next_{w}m", anchor, MVT
            )
            out = _counts_in_window(
                out, dep_all, [APT], w, True, f"apt_dep_next_{w}m", anchor, MVT
            )

    # Arrival/departure balance: which flow the surface is currently serving.
    out = out.with_columns(
        arr_dep_ratio_30m=(
            pl.col("apt_arr_prev_30m")
            / (pl.col("apt_dep_prev_30m") + pl.col("apt_arr_prev_30m")).replace(0, None)
        ).cast(pl.Float32)
    )
    return out.drop(APT, *time_cols, strict=False)


def taxi_in_pressure(
    mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30, anchor: str = MVT
) -> pl.DataFrame:
    """Median taxi-in of recent arrivals: how congested the surface is right now.

    The value of this feature is that it **is available in the ranking set**. Arrival
    rows are not blanked (D09), so it can be computed for January and July 2026 as well.
    Surface congestion is shared between the arrival and departure flows, which makes
    this a live indicator rather than a historical average.
    """
    arr = (
        mvt.filter((pl.col(PHASE) == "ARR") & pl.col(Col.TARGET).is_not_null())
        .select(APT, MVT, Col.TARGET)
        .sort(MVT)
    )
    if arr.height == 0:
        return dep.select(Col.MVT_ID).with_columns(
            arr_taxi_median_sec=pl.lit(None, dtype=pl.Float32),
            arr_taxi_count=pl.lit(0, dtype=pl.Int32),
        )

    # Summarise into rolling bins first, then join as-of; cheaper than a per-row window.
    binned = (
        arr.group_by_dynamic(MVT, every="10m", period=f"{minutes}m", group_by=APT)
        .agg(
            arr_taxi_median_sec=pl.col(Col.TARGET).median().cast(pl.Float32),
            arr_taxi_count=pl.len().cast(pl.Int32),
        )
        .sort(MVT)
    )
    return (
        dep.select(Col.MVT_ID, APT, _anchor=pl.col(anchor))
        .sort("_anchor")
        .join_asof(binned, left_on="_anchor", right_on=MVT, by=APT, strategy="backward")
        .select(Col.MVT_ID, "arr_taxi_median_sec", "arr_taxi_count")
    )


def runway_configuration(
    mvt: pl.DataFrame, dep: pl.DataFrame, minutes: int = 30, anchor: str = MVT
) -> pl.DataFrame:
    """Infer the runway configuration: which runways are in use around this movement.

    The data carries no configuration field, but which runways are worked at the same
    time defines the configuration, and that shifts taxi distances for everyone at once.
    """
    used = (
        mvt.filter(pl.col(RWY).is_not_null())
        .select(APT, MVT, RWY, PHASE)
        .with_columns(_bin=pl.col(MVT).dt.truncate(f"{minutes}m"))
    )
    config = (
        used.group_by(APT, "_bin")
        .agg(
            dep_runways_in_use=pl.col(RWY).filter(pl.col(PHASE) == "DEP")
            .unique().sort().str.join("+"),
            arr_runways_in_use=pl.col(RWY).filter(pl.col(PHASE) == "ARR")
            .unique().sort().str.join("+"),
            active_runway_count=pl.col(RWY).n_unique().cast(pl.Int8),
        )
    )
    return (
        dep.select(Col.MVT_ID, APT, _anchor=pl.col(anchor))
        .with_columns(_bin=pl.col("_anchor").dt.truncate(f"{minutes}m"))
        .join(config, on=[APT, "_bin"], how="left")
        .drop(APT, "_anchor", "_bin")
    )


def build(mvt: pl.DataFrame, causal: bool = False) -> pl.DataFrame:
    """Build every congestion feature; returns one table keyed by departure.

    `causal=True` switches to the causal variant: features are anchored at off-block
    rather than take-off and the forward windows are dropped. That mode only works
    where block times are known, so it cannot be applied to the ranking set, which is
    not what it is for anyway (see the table in the module docstring).
    """
    anchor = BLOCK if causal else MVT
    forward = not causal
    dep = runway_features(mvt, anchor, forward)
    out = dep
    for part in (
        airport_features(mvt, dep, anchor, forward),
        taxi_in_pressure(mvt, dep, anchor=anchor),
        runway_configuration(mvt, dep, anchor=anchor),
    ):
        out = out.join(part, on=Col.MVT_ID, how="left")
    return out
