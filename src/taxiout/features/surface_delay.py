"""Two quantities the movement stream gives away that counting movements does not.

Both rest on the same observation. `AOBT_3_flt`, the Network Manager's off-block time,
is **not blanked in the ranking set** and is present for 98.5 percent of departures, and
the take-off time is present for all of them. So for every departure, on both sides of
the competition, the interval it spent on the surface is observable without ever looking
at the target.

**The surface count.** The number of aircraft that had pushed back but not yet taken off
at an instant is

    on_surface(t) = #{j : off_block_j <= t} - #{j : take_off_j <= t}

evaluated at this flight's own off-block instant, that is the queue it joined. This is
Idris's queue variable, the strongest predictor in the taxi-out literature, and it is
usually the hard one: a real-time system has to forecast it. Here it is simply counted.

Every congestion feature already in this project counts movements in a window, which is
a **flow**: how many aircraft took off in the last half hour. The surface count is a
**stock**: how many are out there right now. Thirty departures in half an hour means
something different when they are all still queueing than when they have all gone.

**The excess delay sensor.** For each departure, take-off minus network off-block gives
a taxi-out estimate that costs nothing. Subtract the tenth percentile for that airport
and runway and it becomes an excess over the unimpeded baseline. Averaged over the
*other* departures in the last half hour, it measures how badly the surface is running
at this moment.

That is a different kind of feature from the weather columns beside it. Those name
causes and hope the model connects them to an effect: freezing precipitation, low
visibility, a de-icing proxy. This measures the effect directly, so it also carries the
causes nobody thought to encode, a closed runway, an ATFM regulation, a stand block, a
security incident. The flight's own value is excluded, so it cannot leak.

Both are unavailable to the causal model, which is anchored at off-block and may not use
the Network Manager time (see the table in `congestion`).
"""

from __future__ import annotations

import polars as pl

from taxiout.domain.schema import Col, Phase

MVT = Col.MVT_TIME
APT = "apt_mvt"
RWY = Col.RUNWAY
PHASE = Col.PHASE
AOBT = Col.AOBT_3

# Baseline percentile for the unimpeded taxi-out estimate. The tenth is what
# EUROCONTROL's own additional taxi-out time indicator uses.
BASELINE_Q = 0.10
EXCESS_WINDOW_MIN = 30


def _running_total(events: pl.DataFrame, group: list[str], at: str,
                   value: pl.Expr | None = None) -> pl.DataFrame:
    """(group, instant) -> total up to and including that instant.

    One row per distinct instant, not per event. Several airports report to the minute,
    so dozens of movements share a timestamp, and a total based on row order would give
    tied rows different answers depending on how the frame happened to be sorted.
    """
    # Int64, not the u32 that `pl.len()` produces. The surface count is the difference
    # of two of these totals, and on unsigned integers a difference that should be
    # negative wraps to about four billion instead of raising.
    agg = (
        pl.len().cast(pl.Int64).alias("_k")
        if value is None
        else value.sum().cast(pl.Float64).alias("_k")
    )
    return (
        events.filter(pl.col(at).is_not_null())
        .group_by([*group, at])
        .agg(agg)
        .sort(at)
        .with_columns(_cum=pl.col("_k").cum_sum().over(group))
        .select(*group, at, "_cum")
        .sort(at)
    )


def _total_at(keys: pl.DataFrame, cum: pl.DataFrame, group: list[str],
              probe: pl.Expr, event_at: str) -> pl.Series:
    """The running total at the instant `probe` names, for every key row."""
    frame = keys.select(*group, _probe=probe).with_row_index("_row")
    return (
        frame.sort("_probe")
        .join_asof(cum, left_on="_probe", right_on=event_at, by=group, strategy="backward")
        .sort("_row")
        .get_column("_cum")
        .fill_null(0)
    )


def surface_count(mvt: pl.DataFrame, dep: pl.DataFrame) -> pl.DataFrame:
    """How many departures were already on the surface when this one pushed back.

    Counted at two instants and at two scopes. At push-back it is the queue this flight
    joined; at take-off it is what the surface looked like when it left, which says
    whether the queue was clearing or still building. Airport-wide and per runway,
    because a busy airport with this flight's own runway empty is not a busy runway.
    """
    # Both totals must run over the SAME flights. The Network Manager has no match for
    # about 1.5 percent of departures, and counting those in the take-off total but not
    # the push-back total makes the difference drift down by the number of unmatched
    # flights seen so far. Over a year that reached about 46 at Frankfurt, which buries a
    # real queue of five to twenty and clips the whole column to zero. Nothing raised:
    # the feature was simply constant, and the first ablation of it produced numbers that
    # could not be true.
    departures = mvt.filter(
        (pl.col(PHASE) == Phase.DEPARTURE)
        & pl.col(AOBT).is_not_null()
        & pl.col(MVT).is_not_null()
    )
    out = dep.select(Col.MVT_ID, APT, RWY, _off=pl.col(AOBT), _on=pl.col(MVT))

    for scope, group in (("apt", [APT]), ("rwy", [APT, RWY])):
        pushed = _running_total(departures.select(*group, _t=pl.col(AOBT)), group, "_t")
        flown = _running_total(departures.select(*group, _t=pl.col(MVT)), group, "_t")
        for when, probe in (("pushback", pl.col("_off")), ("takeoff", pl.col("_on"))):
            count = (
                _total_at(out, pushed, group, probe, "_t")
                - _total_at(out, flown, group, probe, "_t")
            )
            # A flight is on the surface from its own push-back onward, so the count at
            # push-back includes itself. Ahead of it is one fewer.
            out = out.with_columns(
                (count - 1).clip(0).cast(pl.Int32).alias(f"surface_{scope}_at_{when}")
            )

    return out.drop("_off", "_on", APT, RWY, strict=False)


def excess_delay(mvt: pl.DataFrame, dep: pl.DataFrame,
                 minutes: int = EXCESS_WINDOW_MIN) -> pl.DataFrame:
    """How far the other departures around this one are running over their baseline.

    The baseline comes from the same frame the flights come from, never from the
    training targets, so the ranking set computes its own from its own January and July.
    That is the same rule the congestion features follow.
    """
    departures = (
        mvt.filter(
            (pl.col(PHASE) == Phase.DEPARTURE)
            & pl.col(AOBT).is_not_null()
            & pl.col(MVT).is_not_null()
        )
        .with_columns(_naive=(pl.col(MVT) - pl.col(AOBT)).dt.total_seconds())
        .filter(pl.col("_naive").is_between(0, 4 * 3600))  # drop the clock errors
    )
    if departures.height == 0:
        return dep.select(Col.MVT_ID).with_columns(
            surface_excess_sec=pl.lit(None, dtype=pl.Float32),
            surface_excess_n=pl.lit(0, dtype=pl.Int32),
        )

    baseline = departures.group_by([APT, RWY]).agg(
        _base=pl.col("_naive").quantile(BASELINE_Q)
    )
    departures = departures.join(baseline, on=[APT, RWY], how="left").with_columns(
        _excess=(pl.col("_naive") - pl.col("_base")).cast(pl.Float64)
    )

    group = [APT]
    totals = _running_total(
        departures.select(*group, _t=pl.col(MVT), _excess="_excess"), group, "_t",
        value=pl.col("_excess"))
    counts = _running_total(departures.select(*group, _t=pl.col(MVT)), group, "_t")

    # `_own` is this flight's own contribution to the window, subtracted below. It is
    # null when the Network Manager has no match for the flight, which is 1.5 percent of
    # them; those rows never entered the totals either, so nothing needs removing.
    # `_own` is this flight's own contribution to the window, subtracted below. It stays
    # null when the flight is not in the totals to begin with: the Network Manager has no
    # match for 1.5 percent of departures, and rows whose implied taxi-out is impossible
    # were filtered out above. Subtracting a row that was never added would bias the
    # window the other way and go unnoticed, since the result is still a plausible number.
    keys = (
        dep.select(Col.MVT_ID, APT, RWY, AOBT, _t=pl.col(MVT))
        .join(baseline, on=[APT, RWY], how="left")
        .with_columns(_naive=(pl.col("_t") - pl.col(AOBT)).dt.total_seconds())
        .with_columns(
            _own=pl.when(pl.col("_naive").is_between(0, 4 * 3600))
            .then(pl.col("_naive") - pl.col("_base"))
            .otherwise(None)
        )
    )

    delta = pl.duration(minutes=minutes)
    total_here = _total_at(keys, totals, group, pl.col("_t"), "_t")
    total_back = _total_at(keys, totals, group, pl.col("_t") - delta, "_t")
    count_here = _total_at(keys, counts, group, pl.col("_t"), "_t")
    count_back = _total_at(keys, counts, group, pl.col("_t") - delta, "_t")

    # The backward window (t - W, t] includes flights sharing this instant, this one
    # among them. Removing its own contribution is what stops the feature leaking.
    own = keys.get_column("_own").fill_null(0.0)
    has_own = keys.get_column("_own").is_not_null().cast(pl.Int32)
    window_sum = (total_here - total_back) - own
    window_n = (count_here - count_back) - has_own

    return keys.with_columns(
        surface_excess_sec=pl.when(window_n > 0)
        .then(window_sum / window_n)
        .otherwise(None)
        .cast(pl.Float32),
        surface_excess_n=window_n.cast(pl.Int32),
    ).select(Col.MVT_ID, "surface_excess_sec", "surface_excess_n")


def build(mvt: pl.DataFrame, dep: pl.DataFrame) -> pl.DataFrame:
    """Both families, keyed by departure."""
    out = surface_count(mvt, dep.select(Col.MVT_ID, APT, RWY, AOBT, MVT))
    return out.join(
        excess_delay(mvt, dep.select(Col.MVT_ID, APT, RWY, AOBT, MVT)),
        on=Col.MVT_ID, how="left",
    )
