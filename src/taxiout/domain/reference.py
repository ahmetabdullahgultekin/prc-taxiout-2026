"""Unimpeded reference taxi-out time.

A faithful reimplementation of EUROCONTROL's own additional taxi-out time indicator
(see `docs/reference/atxot-notes.md`; ATXOT Edition 01.00, 16 March 2023):

    reference(combo) = P10(taxi-out times)   combo = (airport, stand, departure runway)
    valid            = at least 10 flights in the combo with taxi-out <= P10

It does two jobs at once.

1. **A base for the model.** Last year's winner gained more from re-parameterising the
   target than from any feature group, training on fuel flow instead of fuel burn and
   moving RMSE from 220.56 to 201.04. The analogue here is to learn the **residual over
   the reference** rather than the raw taxi-out, since a tree spends far less depth once
   a constant baseline is subtracted. Whether it actually helps is an experiment, and
   on this data it did not; see `docs/experiments.md`.

2. **A checkable baseline for the paper.** Being able to reproduce the published
   indicator lets us discuss the contribution in EUROCONTROL's own units.

**Two deliberate departures from the official method**, both reported in the paper:

- ATXOT **drops** flights whose combo has no valid reference. We have to predict every
  row, so there is a fallback chain instead:
  (apt, stand, runway) -> (apt, stand) -> (apt, runway) -> (apt).
- ATXOT uses a rolling twelve months. We only have calendar 2025, so the reference is
  fixed rather than rolling.
"""

from __future__ import annotations

import polars as pl

from taxiout.domain.schema import Col, Phase

TAXI = Col.TARGET
# The airport the movement happened at (added by `pipeline.prepare_movements`).
# Identical to `ADEP_mvt` here, since the reference is built from departures only, but
# one canonical name across the pipeline avoids the confusion that caused a real bug.
APT = "apt_mvt"
STAND = Col.STAND
RWY = Col.RUNWAY

PERCENTILE = 0.10
MIN_BELOW = 10  # ATXOT p.15: at least ten flights at or below the P10
MAX_TAXI_SEC = 120 * 60  # ATXOT p.13 step 1: anything above two hours leaves the sample

# Most specific first; the first valid level wins.
LEVELS: tuple[tuple[str, list[str]], ...] = (
    ("apt_stand_rwy", [APT, STAND, RWY]),
    ("apt_stand", [APT, STAND]),
    ("apt_rwy", [APT, RWY]),
    ("apt", [APT]),
)


def _level_reference(fit: pl.DataFrame, keys: list[str], suffix: str) -> pl.DataFrame:
    """P10 and the ATXOT validity flag for one grouping level."""
    ref = (
        fit.group_by(keys)
        .agg(
            [
                pl.col(TAXI).quantile(PERCENTILE, interpolation="linear").alias(f"p10_{suffix}"),
                pl.len().alias(f"n_{suffix}"),
            ]
        )
    )
    # Validity: how many flights have a taxi-out at or below the percentile.
    below = (
        fit.join(ref, on=keys, how="left")
        .filter(pl.col(TAXI) <= pl.col(f"p10_{suffix}"))
        .group_by(keys)
        .agg(pl.len().alias(f"below_{suffix}"))
    )
    return ref.join(below, on=keys, how="left").with_columns(
        pl.col(f"below_{suffix}").fill_null(0),
        _valid=pl.col(f"below_{suffix}").fill_null(0) >= MIN_BELOW,
    ).rename({"_valid": f"valid_{suffix}"})


def fit_reference(fit: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Build the reference tables from the given fitting slice ONLY.

    During validation this must be given **only the training months**. Including the
    holdout months is leakage and would flatter the out-of-fold numbers in a way the
    board would later take back.
    """
    clean = fit.filter(
        (pl.col(Col.PHASE) == Phase.DEPARTURE)
        & pl.col(TAXI).is_not_null()
        & (pl.col(TAXI) > 0)
        & (pl.col(TAXI) <= MAX_TAXI_SEC)
    )
    return {suffix: _level_reference(clean, keys, suffix) for suffix, keys in LEVELS}


def apply_reference(df: pl.DataFrame, tables: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Add `reference_sec` and the `reference_level` it came from."""
    out = df
    for suffix, keys in LEVELS:
        out = out.join(tables[suffix], on=keys, how="left")

    # Pick the most specific level that is valid.
    ref_expr = pl.lit(None, dtype=pl.Float64)
    lvl_expr = pl.lit("none", dtype=pl.String)
    for suffix, _ in reversed(LEVELS):  # general to specific, overwriting as we go
        usable = (
            pl.col(f"valid_{suffix}").fill_null(False)
            & pl.col(f"p10_{suffix}").is_not_null()
        )
        ref_expr = pl.when(usable).then(pl.col(f"p10_{suffix}")).otherwise(ref_expr)
        lvl_expr = pl.when(usable).then(pl.lit(suffix)).otherwise(lvl_expr)

    return out.with_columns(
        reference_sec=ref_expr.cast(pl.Float32),
        reference_level=lvl_expr,
        # How well observed the combo is: tells the model how far to trust the reference.
        reference_sample=pl.col("n_apt_stand_rwy").fill_null(0).cast(pl.Int32),
    ).drop(
        # `reference_sample` already carries n_apt_stand_rwy. None of the intermediate
        # columns may escape, or they fall outside the feature-family registry.
        [c for s, _ in LEVELS for c in (f"p10_{s}", f"n_{s}", f"below_{s}", f"valid_{s}")]
    )


def official_coverage(applied: pl.DataFrame) -> pl.DataFrame:
    """ATXOT's own coverage measure: the share of flights without a valid reference.

    The official method drops those flights from the indicator, and PRC requires this
    share to be monitored as a data-quality signal (ATXOT p.16, section 6.3).
    """
    return (
        applied.group_by(APT)
        .agg(
            n=pl.len(),
            official_coverage_share=(pl.col("reference_level") == "apt_stand_rwy").mean(),
            fallback_share=(pl.col("reference_level") != "apt_stand_rwy").mean(),
        )
        .sort(APT)
    )
