"""The day regime: does it actually see a bad day, and does the ratio survive a shift.

The whole claim of `regime.py` is that a ratio means the same thing in two different
years while a level does not. These tests check that claim mechanically rather than
trusting the sentence: the same day, rebuilt at a different overall level, must produce
the same ratio and a different median.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from taxiout.features import regime


def _movements(daily_taxi: dict[int, float], airport: str = "EDDF",
               per_day: int = 40) -> pl.DataFrame:
    """One arrival stream where day `d` of January has a fixed taxi-in."""
    rows = []
    for day, taxi in daily_taxi.items():
        for i in range(per_day):
            rows.append({
                "MVT_ID_mvt": f"a{airport}{day:02d}{i:03d}",
                "apt_mvt": airport,
                "PHASE_mvt": "ARR",
                "MVT_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
                "TAXITIME_SEC_mvt": taxi,
                "SCHED_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
                "BLOCK_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
            })
    return pl.DataFrame(rows)


def _departure(day: int, airport: str = "EDDF") -> pl.DataFrame:
    return pl.DataFrame({
        "MVT_ID_mvt": ["d1"],
        "apt_mvt": [airport],
        "PHASE_mvt": ["DEP"],
        "MVT_TIME_UTC_mvt": [datetime(2025, 1, day, 12)],
        "TAXITIME_SEC_mvt": [900.0],
        "SCHED_TIME_UTC_mvt": [datetime(2025, 1, day, 11)],
        "BLOCK_TIME_UTC_mvt": [datetime(2025, 1, day, 11, 45)],
    })


def test_a_slow_day_reads_as_a_slow_day() -> None:
    quiet = dict.fromkeys(range(1, 26), 500.0)
    daily = {**quiet, 26: 750.0}
    mvt = pl.concat([_movements(daily), _departure(26)], how="diagonal_relaxed")

    out = regime.attach(mvt, _departure(26))
    assert out.height == 1
    assert out["arr_taxi_day_med_sec"][0] == 750.0
    assert abs(out["arr_taxi_day_ratio"][0] - 1.5) < 1e-5


def test_the_ratio_ignores_the_level_and_the_median_does_not() -> None:
    """The point of the whole module, stated as a test.

    Two airports with the same day shape and a factor of two between their levels must
    produce the same ratio. If the ratio moved with the level it would carry the airport
    identity, which the airport column already carries, and it would not carry across a
    year in which the level moved.
    """
    def build(level: float, airport: str) -> pl.DataFrame:
        daily = {**dict.fromkeys(range(1, 26), level), 26: level * 1.4}
        return regime.attach(
            pl.concat([_movements(daily, airport), _departure(26, airport)],
                      how="diagonal_relaxed"),
            _departure(26, airport),
        )

    slow, fast = build(900.0, "EGLL"), build(450.0, "LSZH")
    assert abs(slow["arr_taxi_day_ratio"][0] - fast["arr_taxi_day_ratio"][0]) < 1e-5
    assert slow["arr_taxi_day_med_sec"][0] != fast["arr_taxi_day_med_sec"][0]


def test_the_baseline_excludes_the_day_itself() -> None:
    """A day compared against itself would report 1.0 and see nothing.

    The negative control for the test above: if the shift were missing, a single
    outlying day would drag its own baseline and the ratio would shrink towards one.
    """
    daily = {**dict.fromkeys(range(1, 26), 500.0), 26: 1000.0}
    mvt = pl.concat([_movements(daily), _departure(26)], how="diagonal_relaxed")
    out = regime.attach(mvt, _departure(26))
    assert abs(out["arr_taxi_day_ratio"][0] - 2.0) < 1e-5


def test_departures_do_not_feed_the_arrival_regime() -> None:
    """Departure taxi times are the target. They must not reach a feature.

    Built so that including them would be visible: the departures on the day carry a
    taxi time ten times the arrivals', so a median over both would be far from 500.
    """
    daily = dict.fromkeys(range(1, 27), 500.0)
    deps = pl.DataFrame({
        "MVT_ID_mvt": [f"dd{i}" for i in range(200)],
        "apt_mvt": ["EDDF"] * 200,
        "PHASE_mvt": ["DEP"] * 200,
        "MVT_TIME_UTC_mvt": [datetime(2025, 1, 26, 6) + timedelta(minutes=4 * i)
                             for i in range(200)],
        "TAXITIME_SEC_mvt": [5000.0] * 200,
        "SCHED_TIME_UTC_mvt": [datetime(2025, 1, 26, 5) + timedelta(minutes=4 * i)
                               for i in range(200)],
        "BLOCK_TIME_UTC_mvt": [datetime(2025, 1, 26, 5) + timedelta(minutes=4 * i)
                               for i in range(200)],
    })
    mvt = pl.concat([_movements(daily), deps], how="diagonal_relaxed")
    out = regime.attach(mvt, deps.head(1))
    assert out["arr_taxi_day_med_sec"][0] == 500.0


def test_an_early_day_has_no_baseline_rather_than_a_wrong_one() -> None:
    daily = dict.fromkeys(range(1, 10), 500.0)
    mvt = pl.concat([_movements(daily), _departure(2)], how="diagonal_relaxed")
    out = regime.attach(mvt, _departure(2))
    assert out["arr_taxi_day_ratio"][0] is None
    assert out["arr_taxi_day_med_sec"][0] == 500.0


def test_a_departure_at_an_airport_with_no_arrivals_gets_nulls_not_an_error() -> None:
    daily = dict.fromkeys(range(1, 27), 500.0)
    mvt = pl.concat([_movements(daily, "EDDF"), _departure(26, "LTFM")],
                    how="diagonal_relaxed")
    out = regime.attach(mvt, _departure(26, "LTFM"))
    assert out.height == 1
    assert out["arr_taxi_day_med_sec"][0] is None


def test_the_volume_ratio_sees_a_quiet_day() -> None:
    rows = []
    for day in range(1, 27):
        count = 40 if day < 26 else 10
        for i in range(count):
            rows.append({
                "MVT_ID_mvt": f"a{day:02d}{i:03d}", "apt_mvt": "EDDF", "PHASE_mvt": "ARR",
                "MVT_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
                "TAXITIME_SEC_mvt": 500.0,
                "SCHED_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
                "BLOCK_TIME_UTC_mvt": datetime(2025, 1, day, 6) + timedelta(minutes=7 * i),
            })
    mvt = pl.concat([pl.DataFrame(rows), _departure(26)], how="diagonal_relaxed")
    out = regime.attach(mvt, _departure(26))
    assert abs(out["arr_volume_day_ratio"][0] - 0.25) < 1e-5


def test_the_substitution_rate_counts_arrivals_whose_block_is_their_schedule() -> None:
    """The feed writing the schedule into a field it had no measurement for.

    Built with a known share so the number is checked rather than merely produced: ten of
    forty arrivals a day are given an in-block time equal to their scheduled one.
    """
    rows = []
    for day in range(1, 27):
        for i in range(40):
            when = datetime(2025, 1, day, 6) + timedelta(minutes=7 * i)
            substituted = i < 10
            rows.append({
                "MVT_ID_mvt": f"a{day:02d}{i:03d}", "apt_mvt": "EDDF", "PHASE_mvt": "ARR",
                "MVT_TIME_UTC_mvt": when, "TAXITIME_SEC_mvt": 500.0,
                "SCHED_TIME_UTC_mvt": when,
                "BLOCK_TIME_UTC_mvt": when if substituted else when + timedelta(minutes=17),
            })
    mvt = pl.concat([pl.DataFrame(rows), _departure(26)], how="diagonal_relaxed")
    out = regime.attach(mvt, _departure(26))
    assert abs(out["arr_substitution_day_rate"][0] - 0.25) < 1e-5
