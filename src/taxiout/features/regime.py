"""What kind of day is it at this airport, measured on the arrival stream.

The ranking set blanks two columns and only for departures: the off-block time and the
taxi time. Every arrival keeps its landing time, its in-block time and therefore its
full taxi-in duration. So the surface of January and July 2026 is directly observable,
on the airport's own clock, in the period being scored. Nothing here touches the target.

That matters because a model fitted on 2025 carries 2025's level. A runway closed for
resurfacing, a new taxiway, a stand reallocation, a week of snow: each moves the whole
airport for a day or a month, and none of it is visible in a feature built from the
flight's own attributes. The arrival stream sees all of it.

**What was measured before building this.** The obvious version of the idea is a
correction: scale the prediction by how much slower arrivals are in 2026 than in 2025.
Tested across the 126 airport-months of 2025, where both quantities are observable, the
month-to-month movement of median taxi-in tracks median taxi-out with a correlation of
**-0.11**. Pooled, it is nothing. Per airport it is incoherent:

| airport | corr | | airport | corr |
|---|---:|---|---|---:|
| EDDF | +0.82 | | EGLL | +0.09 |
| EDDM | +0.76 | | LTFM | +0.02 |
| LFPG | +0.68 | | LEMD | -0.17 |
| LIRF | +0.62 | | EHAM | **-0.66** |

A blanket multiplicative correction would therefore have pushed Amsterdam the wrong way,
and Amsterdam is where the year-on-year arrival shift is largest: median taxi-in in July
fell from 412 s to 335 s, which the correction would have read as a 140 s cut to every
departure at an airport whose departures move the other way.

So this is a feature and not a correction. The airport is already a categorical, the
sign is different at each one, and a model can learn a sign per airport from 2025's own
day-to-day variation. What it cannot do is invent the regime out of nothing, which is
what it has to do today.

The ratio, rather than the level, is what carries across the year. A level says "the
median taxi-in here is 550 seconds", which the airport identifier already implies. The
ratio says "today is running twelve percent slow for this airport", and that sentence
means the same thing in 2025 and in 2026.
"""

from __future__ import annotations

import polars as pl

from taxiout.domain.schema import Col, Phase

APT = "apt_mvt"
MVT = Col.MVT_TIME
TAXI = Col.TARGET

# The trailing window the day is compared against. Thirty days is long enough to average
# over the weekly cycle and short enough to follow a seasonal turn, and it is the window
# the ATXOT reference uses for its own rolling baseline at a coarser scale.
BASELINE_DAYS = 30

# Above this, the movement is not a taxi any more: a two hour taxi-in is a data artefact
# or an aircraft that went somewhere else first. Same threshold the reference uses.
MAX_TAXI_SEC = 120 * 60


# How close an in-block time has to be to the scheduled one to count as substituted.
# The same ten seconds `models/mixture.py` uses on the departure side, because it is the
# same failure seen from the other end of the turn.
SUBSTITUTION_TOLERANCE_SEC = 10.0


def _daily_arrival_state(mvt: pl.DataFrame) -> pl.DataFrame:
    """One row per airport-day: how the arrivals went, and how often the feed gave up.

    The substitution share is the interesting one. An arrival whose in-block time equals
    its scheduled time to the second is the airport feed writing the schedule into a
    field it had no measurement for, which is exactly what it does on the departure side
    to produce the rows whose taxi time is a schedule offset. Departures cannot be
    watched for it in the ranking set; arrivals can, in both years.

    Whether it carries anything beyond the airport identity was measured before it was
    built. Pooled across airport-days the two rates correlate at +0.90, but that is
    almost entirely between airports and the airport is already a feature. Within an
    airport, day to day, it is weak at most of them and real at some: Rome +0.44, Munich
    +0.33, Zurich +0.26, Heathrow +0.22, against Frankfurt +0.06 and Barcelona -0.01.
    Rome is 55 percent of the holdout's squared error, which is why this is here.
    """
    arrivals = mvt.filter(
        (pl.col(Col.PHASE) == Phase.ARRIVAL)
        & pl.col(TAXI).is_not_null()
        & pl.col(TAXI).is_between(0, MAX_TAXI_SEC)
    )
    if arrivals.height == 0:
        return pl.DataFrame(
            schema={APT: pl.String, "_day": pl.Date,
                    "arr_taxi_day_med_sec": pl.Float64, "arr_taxi_day_n": pl.UInt32,
                    "arr_substitution_day_rate": pl.Float64}
        )
    substituted = (
        (pl.col(Col.BLOCK_TIME) - pl.col(Col.SCHED_TIME)).dt.total_seconds().abs()
        <= SUBSTITUTION_TOLERANCE_SEC
    ) if Col.SCHED_TIME in arrivals.columns else pl.lit(None, dtype=pl.Boolean)
    return (
        arrivals.with_columns(_day=pl.col(MVT).dt.date(), _sub=substituted)
        .group_by(APT, "_day")
        .agg(
            arr_taxi_day_med_sec=pl.col(TAXI).median(),
            arr_taxi_day_n=pl.len(),
            arr_substitution_day_rate=pl.col("_sub").mean(),
        )
        .sort(APT, "_day")
    )


def _with_baseline(daily: pl.DataFrame) -> pl.DataFrame:
    """Each day against the trailing thirty days at the same airport.

    Trailing and not centred, and shifted by one day, so that a day is compared against
    days that came before it. Not because of leakage - the whole month is given to us in
    both periods - but because a centred window at the edge of the data is computed from
    a different number of days than one in the middle, which makes the first and last
    days of January mean something different from the rest.
    """
    if daily.height == 0:
        return daily.with_columns(
            arr_taxi_base_med_sec=pl.lit(None, dtype=pl.Float64),
            arr_taxi_day_ratio=pl.lit(None, dtype=pl.Float64),
            arr_volume_day_ratio=pl.lit(None, dtype=pl.Float64),
        )
    rolling = daily.with_columns(
        arr_taxi_base_med_sec=pl.col("arr_taxi_day_med_sec")
        .shift(1)
        .rolling_mean(BASELINE_DAYS, min_samples=5)
        .over(APT),
        _volume_base=pl.col("arr_taxi_day_n")
        .shift(1)
        .rolling_mean(BASELINE_DAYS, min_samples=5)
        .over(APT),
    )
    return rolling.with_columns(
        arr_taxi_day_ratio=pl.col("arr_taxi_day_med_sec") / pl.col("arr_taxi_base_med_sec"),
        arr_volume_day_ratio=pl.col("arr_taxi_day_n") / pl.col("_volume_base"),
    ).drop("_volume_base")


def attach(mvt: pl.DataFrame, dep: pl.DataFrame) -> pl.DataFrame:
    """Per departure: the arrival regime of its own airport on its own day.

    `mvt` is every movement, arrivals included; `dep` is the departures being described.
    Returns one row per departure keyed on `MVT_ID_mvt`.
    """
    daily = _with_baseline(_daily_arrival_state(mvt))
    keyed = dep.select(Col.MVT_ID, APT, _day=pl.col(MVT).dt.date())
    joined = keyed.join(daily, on=[APT, "_day"], how="left")
    return joined.select(
        Col.MVT_ID,
        pl.col("arr_taxi_day_med_sec").cast(pl.Float32),
        pl.col("arr_taxi_day_ratio").cast(pl.Float32),
        pl.col("arr_volume_day_ratio").cast(pl.Float32),
        pl.col("arr_taxi_day_n").cast(pl.Int32).alias("arr_day_count"),
        pl.col("arr_substitution_day_rate").cast(pl.Float32),
    )
