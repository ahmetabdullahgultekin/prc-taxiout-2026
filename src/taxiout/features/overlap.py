"""Who else was moving during this flight's taxi, counted the way that works.

Every congestion feature in this project until now counts movements in a fixed window
around the flight: how many departures in the last fifteen minutes, the last thirty, the
last hour. Zhang et al. (Applied Sciences 14(21):9968, 2024) enumerate eight ways of
defining the overlap between one flight's taxi and another's, measure each against taxi
time at Shanghai Pudong, and find the choice of definition matters more than the choice
of model:

| counter | definition, relative to flight i | correlation |
|---|---|---:|
| **D2** | departures that pushed back **after** i and took off **before** it | **0.81** |
| **A2** | arrivals that landed after i pushed back and parked before it flew | **0.74** |
| D1, D3, D4, A1, A3, A4 | the other six overlap shapes | low |
| the FAA definition (D1+D3, A1+A3) | | **0.17 and 0.05** |

D2 is the set of aircraft that overtook this one. It is not a count of traffic, it is a
count of *being passed*, which is what a queue does to the flight sitting in it.

Both are computable here, on both sides of the competition, because the take-off instant
is given for every ranking row and the Network Manager off-block time is not blanked.
An operational forecaster could not use either one: Wang et al. (TRC 111, 2020)
explicitly discard this whole family because the counts are only known once the flight
has finished taxiing. The post-operations framing of this challenge is what makes them
available, and it is the same reason the naive predictor works at all.

**The mechanical part, and what to do about it.** A flight that taxis for forty minutes
contains more of everything than one that taxis for eight, so part of D2's correlation
with taxi-out is arithmetic rather than congestion. The rates divide it back out: D2 per
minute of taxi window says how fast the queue was passing this aircraft, which is the
part the window length does not already tell the model.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from taxiout.domain.schema import Col, Phase

MVT = Col.MVT_TIME
BLOCK = Col.BLOCK_TIME
APT = "apt_mvt"
AOBT = Col.AOBT_3
PHASE = Col.PHASE

# Beyond this the off-block time is a clock error, not a long taxi.
MAX_WINDOW_SEC = 4 * 3600


def _count_dominated(
    q_start: np.ndarray, q_end: np.ndarray,
    p_start: np.ndarray, p_end: np.ndarray,
) -> np.ndarray:
    """For each query i, how many points j have `p_start_j > q_start_i` and
    `p_end_j < q_end_i`.

    One sweep serves every counter in this module. Points are swept in descending order
    of their start; when the sweep reaches a query, everything inserted so far starts
    later than it does, and a Fenwick tree over the ranks of `end` answers how many of
    those ended sooner.

    Both comparisons are strict, and that matters here rather than being a nicety. The
    Network Manager records off-block times to the minute, so dozens of departures at a
    busy airport share an instant. Two aircraft that pushed back in the same minute did
    not overtake each other, and a tie-breaking rule that says one did would invent
    overtaking out of the timestamp resolution.

    Strictness is kept two ways: `end` values are reduced to a dense rank, so ties share
    a tree position and can never count as smaller than one another; and equal starts are
    processed as a block, every query in it answered before any point in it is inserted.
    When the points are the queries, that also excludes each flight from its own count.
    """
    n_q, n_p = len(q_start), len(p_start)
    if n_q == 0:
        return np.zeros(0, dtype=np.int32)
    if n_p == 0:
        return np.zeros(n_q, dtype=np.int32)

    edges = np.unique(p_end)
    size = len(edges)
    # Rank of a point's end among point ends, 1-based; and for a query, how many
    # distinct point-end values lie strictly below it.
    p_pos = np.searchsorted(edges, p_end, side="left") + 1
    q_pos = np.searchsorted(edges, q_end, side="left")

    # One combined stream: points first at equal starts is wrong, so sort by
    # (-start, is_query) and process ties as a block.
    starts = np.concatenate([q_start, p_start])
    is_query = np.concatenate([np.ones(n_q, dtype=bool), np.zeros(n_p, dtype=bool)])
    order = np.argsort(-starts, kind="stable")
    starts_sorted = starts[order]

    tree = np.zeros(size + 1, dtype=np.int64)
    counts = np.zeros(n_q, dtype=np.int64)

    i = 0
    total_events = n_q + n_p
    while i < total_events:
        j = i
        while j < total_events and starts_sorted[j] == starts_sorted[i]:
            j += 1

        for k in range(i, j):  # every query in the block, before any insertion
            idx = order[k]
            if not is_query[idx]:
                continue
            pos = int(q_pos[idx])
            total = 0
            while pos > 0:
                total += int(tree[pos])
                pos -= pos & (-pos)
            counts[idx] = total

        for k in range(i, j):
            idx = order[k]
            if is_query[idx]:
                continue
            pos = int(p_pos[idx - n_q])
            while pos <= size:
                tree[pos] += 1
                pos += pos & (-pos)

        i = j

    return counts.astype(np.int32)


def _dominance_counts(start: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """D2 and D3: how many overtook this flight, and how many it overtook.

    D3 is the same question with both orderings reversed, so it is the same routine on
    negated inputs rather than a derivation. Deriving it algebraically from the two rank
    orders is correct only when no two flights share a timestamp, which is exactly what
    minute-resolution off-block times guarantee will not hold.
    """
    return (
        _count_dominated(start, end, start, end),
        _count_dominated(-start, -end, -start, -end),
    )


def _companions(
    start: np.ndarray, end: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """D1 and D4: the queue this flight joined, and the one that formed behind it.

    D1 counts aircraft that had already pushed back when this one did and took off
    during its taxi: the queue it joined the back of. D4 counts those that pushed back
    during its taxi and were still out when it left: the queue that formed behind it.

    Both are one-dimensional counts minus a dominance count:

        D1 = #{start_j < start_i, end_j < end_i} - #{end_j <= start_i}
        D4 = #{start_i < start_j < end_i}        - #{start_j > start_i, end_j <= end_i}

    The subtracted terms simplify because a flight cannot take off before it pushes
    back: `end_j <= start_i` already implies `start_j < start_i`, and `end_j <= end_i`
    with `start_j > start_i` already implies `start_j < end_i`.

    Both shortcuts were first written with `D2` standing in for the second dominance
    count, and both were wrong, in the same way and for the same reason. `D2` compares
    the ends strictly, and these two need `<=`; off-block and take-off times are shared
    by many flights, so the ties are not an edge case. `end + 1` turns `<=` into `<` for
    the integer timestamps this is called with, which is what makes the strict routine
    answer the non-strict question. The tests caught both.

    `start` and `end` must be integers, epoch seconds, for that trick to hold.
    """
    # `start_j < start_i and end_j < end_i`: the sign flip turns the first comparison
    # around so the same strict routine answers it.
    both_earlier = _count_dominated(-start, end, -start, end)
    gone_before = np.searchsorted(np.sort(end), start, side="right")

    sorted_start = np.sort(start)
    pushed_during = (
        np.searchsorted(sorted_start, end, side="left")
        - np.searchsorted(sorted_start, start, side="right")
    )
    later_start_not_later_end = _count_dominated(start, end + 1, start, end)

    d1 = np.maximum(both_earlier - gone_before, 0)
    d4 = np.maximum(pushed_during - later_start_not_later_end, 0)
    return d1.astype(np.int32), d4.astype(np.int32)


def _arrival_counts(
    b: np.ndarray, d: np.ndarray, land: np.ndarray, park: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The four ways an arrival's taxi-in can overlap a departure's taxi-out.

    With `b` and `d` the departure's off-block and take-off, and `land` and `park` the
    arrival's touchdown and in-block:

        A2  landed after b, parked before d      entirely inside the window
        A1  landed before b, parked inside       already down, parks while we taxi
        A4  landed inside, parks after d         lands while we taxi, still moving
        A3  landed before b, parks after d       spans the whole window

    Zhang et al. measured A2 at 0.74 against taxi time and called the other three low,
    but correlation is not marginal value in a tree: the equivalent departure counter
    they also called low turned out to be worth ten seconds here. All four are cheap
    once the sweep exists, so all four are built and the ablation can decide.

    A1 and A4 follow the same shape as their departure counterparts, D1 and D4, and
    carry the same hazard: the subtracted term needs `<=` where the sweep gives `<`, so
    `+ 1` on the integer timestamps stands in for it.
    """
    a2 = _count_dominated(b, d, land, park)

    # A1: landed before we pushed back, parked before we flew, and had not already
    # parked by the time we pushed. `park_j <= b` implies `land_j < b` on its own.
    landed_and_parked_earlier = _count_dominated(-b, d, -land, park)
    parked_before_we_pushed = np.searchsorted(np.sort(park), b, side="right")
    a1 = np.maximum(landed_and_parked_earlier - parked_before_we_pushed, 0)

    # A4: landed during our taxi, still taxiing when we left.
    sorted_land = np.sort(land)
    landed_during = (
        np.searchsorted(sorted_land, d, side="left")
        - np.searchsorted(sorted_land, b, side="right")
    )
    a4 = np.maximum(landed_during - _count_dominated(b, d + 1, land, park), 0)

    # A3: on the surface throughout, landing before us and parking after us.
    landed_before = np.searchsorted(sorted_land, b, side="left")
    a3 = np.maximum(landed_before - _count_dominated(-b, d + 1, -land, park), 0)

    return (a2.astype(np.int32), a1.astype(np.int32),
            a4.astype(np.int32), a3.astype(np.int32))


def _overtaking(dep: pl.DataFrame) -> pl.DataFrame:
    """D1 to D4 per departure, computed within each airport."""
    frames = []
    for (airport,), part in dep.group_by([APT], maintain_order=True):
        usable = part.filter(pl.col("_start").is_not_null() & pl.col("_end").is_not_null())
        if usable.height == 0:
            frames.append(part.select(Col.MVT_ID).with_columns(
                overtaken_by=pl.lit(None, dtype=pl.Int32),
                overtook=pl.lit(None, dtype=pl.Int32),
                queue_ahead=pl.lit(None, dtype=pl.Int32),
                queue_behind=pl.lit(None, dtype=pl.Int32),
            ))
            continue
        start = usable["_start"].dt.epoch("s").to_numpy().astype(np.int64)
        end = usable["_end"].dt.epoch("s").to_numpy().astype(np.int64)
        d2, d3 = _dominance_counts(start, end)
        d1, d4 = _companions(start, end)
        frames.append(usable.select(Col.MVT_ID).with_columns(
            overtaken_by=pl.Series(d2), overtook=pl.Series(d3),
            queue_ahead=pl.Series(d1), queue_behind=pl.Series(d4),
        ))
        _ = airport
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame(
        schema={str(Col.MVT_ID): pl.Float64, "overtaken_by": pl.Int32,
                "overtook": pl.Int32, "queue_ahead": pl.Int32, "queue_behind": pl.Int32}
    )


def build(mvt: pl.DataFrame, dep: pl.DataFrame) -> pl.DataFrame:
    """Overlap counters keyed by departure.

    `dep` supplies the flight's own window; `mvt` supplies everyone it overlapped with.
    The window runs from the Network Manager off-block time to the take-off instant,
    both of which survive in the ranking set.
    """
    # A flight whose off-block time is wrong by a day has a "taxi window" of a day, and
    # everything that moved in it lands in the counters: the first run of this reached
    # 21,167 arrivals inside one window against a median of 1. Those rows get no
    # counters rather than absurd ones. The bound matches the one in `surface_delay`,
    # and is far above the 120 minutes EUROCONTROL's own indicator filters at.
    keys = dep.select(
        Col.MVT_ID, APT, _start=pl.col(AOBT), _end=pl.col(MVT)
    ).with_columns(
        window_sec=(pl.col("_end") - pl.col("_start")).dt.total_seconds().cast(pl.Float32)
    ).with_columns(
        pl.when(pl.col("window_sec").is_between(0, MAX_WINDOW_SEC))
        .then(pl.col("_start"))
        .otherwise(None)
        .alias("_start"),
        pl.when(pl.col("window_sec").is_between(0, MAX_WINDOW_SEC))
        .then(pl.col("window_sec"))
        .otherwise(None)
        .alias("window_sec"),
    )

    departures = mvt.filter(pl.col(PHASE) == Phase.DEPARTURE).select(
        Col.MVT_ID, APT, _start=pl.col(AOBT), _end=pl.col(MVT)
    )
    out = keys.join(_overtaking(departures), on=Col.MVT_ID, how="left")

    # A2: arrivals that both landed and reached their stand inside this taxi window.
    # Arrival rows keep their block time in the ranking set, which is what makes the
    # in-block instant available; only departures are blanked.
    arrivals = mvt.filter(
        (pl.col(PHASE) == Phase.ARRIVAL)
        & pl.col(MVT).is_not_null()
        & pl.col(BLOCK).is_not_null()
    ).select(APT, _land=pl.col(MVT), _park=pl.col(BLOCK))

    # The same sweep answers this: the departure's window is the query, an arrival's
    # landing and parking instants are the point. "Landed after we pushed back and
    # parked before we flew" is exactly the dominance the routine counts.
    arrival_cols = ("arrivals_inside", "arrivals_landed_before",
                    "arrivals_still_taxiing", "arrivals_spanning")
    if arrivals.height:
        frames = []
        for (airport,), part in out.group_by([APT], maintain_order=True):
            usable = part.filter(pl.col("_start").is_not_null())
            here = arrivals.filter(pl.col(APT) == airport)
            if usable.height == 0 or here.height == 0:
                frames.append(part.select(Col.MVT_ID).with_columns(
                    **{c: pl.lit(None, dtype=pl.Int32) for c in arrival_cols}))
                continue
            b = usable["_start"].dt.epoch("s").to_numpy().astype(np.int64)
            d = usable["_end"].dt.epoch("s").to_numpy().astype(np.int64)
            land = here["_land"].dt.epoch("s").to_numpy().astype(np.int64)
            park = here["_park"].dt.epoch("s").to_numpy().astype(np.int64)
            frames.append(usable.select(Col.MVT_ID).with_columns(
                **{c: pl.Series(v) for c, v in
                   zip(arrival_cols, _arrival_counts(b, d, land, park), strict=True)}))
        out = out.join(pl.concat(frames, how="vertical"), on=Col.MVT_ID, how="left")
    else:
        out = out.with_columns(**{c: pl.lit(None, dtype=pl.Int32) for c in arrival_cols})

    # Rates, in movements per minute of taxi window. A long taxi contains more of
    # everything; the rate is the part the window length does not already say.
    minutes = (pl.col("window_sec") / 60.0).clip(1.0, None)
    return out.with_columns(
        overtaken_by=pl.col("overtaken_by").cast(pl.Int32),
        overtook=pl.col("overtook").cast(pl.Int32),
        queue_ahead=pl.col("queue_ahead").cast(pl.Int32),
        queue_behind=pl.col("queue_behind").cast(pl.Int32),
        queue_ahead_rate=(pl.col("queue_ahead") / minutes).cast(pl.Float32),
        net_overtaking=(pl.col("overtaken_by") - pl.col("overtook")).cast(pl.Int32),
        overtaken_rate=(pl.col("overtaken_by") / minutes).cast(pl.Float32),
        arrivals_inside_rate=(pl.col("arrivals_inside") / minutes).cast(pl.Float32),
        arrivals_landed_before=pl.col("arrivals_landed_before").cast(pl.Int32),
        arrivals_still_taxiing=pl.col("arrivals_still_taxiing").cast(pl.Int32),
        arrivals_spanning=pl.col("arrivals_spanning").cast(pl.Int32),
        # Zhang et al. report an inverted U: taxi time peaks when departures and
        # arrivals are balanced, because that is when their paths cross most.
        departure_share=(
            pl.col("overtaken_by")
            / (pl.col("overtaken_by") + pl.col("arrivals_inside")).replace(0, None)
        ).cast(pl.Float32),
    ).select(
        Col.MVT_ID, "overtaken_by", "overtook", "net_overtaking", "overtaken_rate",
        "queue_ahead", "queue_behind", "queue_ahead_rate",
        "arrivals_inside", "arrivals_inside_rate", "arrivals_landed_before",
        "arrivals_still_taxiing", "arrivals_spanning", "departure_share",
    )
