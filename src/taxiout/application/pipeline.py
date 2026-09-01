"""Shared pipeline: loading, feature building, training, evaluation.

`scripts/train_baseline.py` and `scripts/run_ablation.py` both use this, so the logic
lives in one place and the scripts only handle their command line and reporting.

Validation scheme (AGENTS.md rule 4): the holdout mirrors the shape of the ranking set
rather than holding out both months everywhere. Random k-fold would lie here, because
the ranking set is January and July 2026, two seasonal extremes plus a year of drift.
The 2025 organisers reported the same difficulty: teams moved up in one month and down
in the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from taxiout import models
from taxiout.domain import reference, schema
from taxiout.domain.schema import Col, Phase
from taxiout.features import (
    airport_state, congestion, groups, routing, surface_delay, weather,
)

# Column names come from taxiout.domain.schema, which is the only place they are
# spelled out. These aliases are kept because they read better inside expressions and
# because every script and test already imports them from here.
TARGET = Col.TARGET
MVT = Col.MVT_TIME
# The airport the movement HAPPENED at. `ADEP_mvt` is not that: it is the origin of the
# flight, so on an arrival row it names where the aircraft came from (the training set
# has 1,582 distinct values for it). Movement airport = ADEP for DEP, ADES for ARR.
APT = schema.MOVEMENT_AIRPORT
HOLDOUT_MONTHS = schema.RANKING_MONTHS

# The ranking set does not cover the same airports in both months: all ten in January,
# only these three in July (measured from the data, docs/facts.md R03). January is 71
# percent of the rows and so dominates the metric. A holdout that does not mirror this
# would make July look far more important than it is and select the wrong model.
JULY_AIRPORTS = schema.JULY_AIRPORTS

CATEGORICAL = {
    APT, Col.RUNWAY, Col.STAND, Col.AIRCRAFT_TYPE, Col.AIRCRAFT_TYPE_FLT,
    Col.WAKE_CATEGORY, Col.MARKET_SEGMENT, Col.OPERATOR, "reference_level",
    "dep_runways_in_use", "arr_runways_in_use", "stand_pier",
}

# Columns that carry or directly give away the target. `AOBT_3_flt` and
# `BLOCK_TIME_UTC_mvt` never become features in raw form; the derived
# `nm_naive_taxi_sec` is built explicitly instead.
EXCLUDED = {
    TARGET, Col.BLOCK_TIME, Col.MVT_ID, MVT, Col.SCHED_TIME,
    Col.FLIGHT_ID, Col.FLIGHT, Col.CALLSIGN, Col.PHASE,
    Col.LOBT, Col.IOBT, Col.EOBT_1, Col.ARVT_1, Col.AOBT_3, Col.ARVT_3,
    "wxcodes", "skyc1", Col.ADES, Col.ADES_FLT, Col.ADES_FILED, Col.ADEP_FLT,
    # Identical to apt_mvt on departure rows; giving the model both is redundant.
    Col.ADEP,
    Col.FLIGHT_RULE, Col.FLIGHT_RULE_FLT, Col.FLIGHT_TYPE,
}

LGB_PARAMS = {
    # L2: the optimal predictor under RMSE is the conditional mean, so no Huber,
    # no MAE, no log target without a correction.
    "objective": "regression",
    "metric": "rmse",
    # Measured, not assumed. A slower rate with wider trees beat the earlier 0.05/127
    # by 5.4 and 3.4 seconds across two seed pairings, both outside the paired noise
    # floor of about 5 seconds. Early stopping puts the optimum near 350 rounds.
    "learning_rate": 0.02,
    "num_leaves": 255,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "max_bin": 127,  # halves memory on a 16 GB machine at negligible accuracy cost
    "verbosity": -1,
    "num_threads": 0,
}


def month(col: str = MVT) -> pl.Expr:
    return pl.col(col).dt.month()


def prepare_movements(mvt: pl.DataFrame) -> pl.DataFrame:
    """Add the canonical `apt_mvt` column.

    Every movement frame, training and ranking alike, must pass through here.
    Otherwise arrival-derived congestion features group on the wrong airport: counting
    the arrivals around a departure would count distant landings of flights that had
    departed this airport, instead of aircraft that landed here.
    """
    return mvt.with_columns(
        pl.when(pl.col(Col.PHASE) == Phase.DEPARTURE)
        .then(pl.col(Col.ADEP))
        .otherwise(pl.col(Col.ADES))
        .alias(APT)
    )


# --------------------------------------------------------------------------- data


@dataclass
class Inputs:
    """Raw inputs. External sources stay None if absent; the pipeline still runs."""

    movements: pl.DataFrame
    metar: pl.DataFrame | None = None
    coords: pl.DataFrame | None = None
    runways: pl.DataFrame | None = None
    atfm_daily: pl.DataFrame | None = None


def load_inputs(raw: Path) -> Inputs:
    files = sorted(raw.glob("training_*.parquet"))
    if not files:
        raise SystemExit(f"no training files found in {raw}")
    mvt = prepare_movements(
        pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")
    )

    def maybe(name: str) -> pl.DataFrame | None:
        p = raw / name
        return pl.read_parquet(p) if p.exists() else None

    return Inputs(
        mvt,
        maybe("metar.parquet"),
        maybe("airport_coords.parquet"),
        maybe("airport_runways.parquet"),
        maybe("eurocontrol_atfm_daily.parquet"),
    )


# --------------------------------------------------------------------------- features


def build_features(inputs: Inputs, causal: bool = False, aobt3: bool = True) -> pl.DataFrame:
    """Full feature table for departure rows. The reference is applied afterwards."""
    mvt = inputs.movements
    anchor = congestion.BLOCK if causal else MVT

    feats = congestion.build(mvt, causal=causal)
    feats = feats.with_columns(
        hour=pl.col(anchor).dt.hour().cast(pl.Int8),
        weekday=pl.col(anchor).dt.weekday().cast(pl.Int8),
        month_num=month().cast(pl.Int8),
        minute_of_day=(pl.col(anchor).dt.hour() * 60 + pl.col(anchor).dt.minute()).cast(pl.Int16),
        sched_offset_sec=(pl.col(anchor) - pl.col(Col.SCHED_TIME)).dt.total_seconds()
        .cast(pl.Float32),
    )
    if Col.EOBT_1 in feats.columns:
        feats = feats.with_columns(
            eobt_offset_sec=(pl.col(anchor) - pl.col(Col.EOBT_1)).dt.total_seconds()
            .cast(pl.Float32)
        )
    if aobt3 and not causal and Col.AOBT_3 in feats.columns:
        # The NM M3 off-block time is an INDEPENDENT measurement of the same event as
        # the airport feed block time. It is not blanked in the ranking set, so it is a
        # legitimate feature. The causal variant cannot use it, being anchored on the
        # take-off time.
        feats = feats.with_columns(
            nm_naive_taxi_sec=(pl.col(MVT) - pl.col(Col.AOBT_3)).dt.total_seconds()
            .cast(pl.Float32),
            nm_matched=pl.col(Col.AOBT_3).is_not_null(),
        )

    # Stand identifiers are not opaque labels. At Frankfurt, Schiphol and Paris every
    # one of them is a pier letter followed by a number (A11, B24); at Munich, Heathrow
    # and Barcelona they are purely numeric. The letter groups stands that sit together
    # on the same apron, and the number orders them along it, so a stand seen a handful
    # of times still inherits the taxi distance of its neighbours. Without this the
    # model has to learn each of the 1,899 stands on its own.
    feats = feats.with_columns(
        stand_pier=pl.col(Col.STAND).str.extract(r"^([A-Za-z]+)"),
        stand_number=pl.col(Col.STAND).str.extract(r"(\d+)").cast(pl.Int32, strict=False),
    )

    if aobt3 and not causal and Col.AOBT_3 in feats.columns:
        # The queue this flight joined, counted rather than forecast, and how far the
        # surface is running over its own baseline. Both need the Network Manager
        # off-block time, so the causal variant cannot have them.
        feats = feats.join(
            surface_delay.build(mvt, feats), on=Col.MVT_ID, how="left"
        )

    feats = routing.build(mvt, feats, inputs.coords, anchor)
    if inputs.runways is not None:
        feats = feats.join(inputs.runways.rename({"icao": APT}), on=APT, how="left")
    if inputs.metar is not None:
        feats = weather.attach(feats, inputs.metar, anchor)
    if inputs.atfm_daily is not None and not causal:
        # Whole-day totals, unusable by a real-time model (see airport_state).
        feats = airport_state.attach(feats, inputs.atfm_daily, anchor)
    return feats


def feature_columns(df: pl.DataFrame) -> list[str]:
    """Modellable columns: target-bearing and time-typed columns are excluded."""
    keep = []
    for name, dtype in zip(df.columns, df.dtypes, strict=True):
        if name in EXCLUDED or dtype in (pl.Datetime, pl.Date, pl.Duration, pl.Object):
            continue
        keep.append(name)
    return keep


# --------------------------------------------------------------------------- splitting


@dataclass
class Split:
    fit: pl.DataFrame
    val: pl.DataFrame
    columns: list[str] = field(default_factory=list)


def holdout_mask() -> pl.Expr:
    """The validation mask, shaped like the ranking set.

    January: every airport. July: only `JULY_AIRPORTS`. Everything else trains,
    including July at the other airports, which is also what the final model does since
    it trains on all of 2025.
    """
    return (month() == 1) | ((month() == 7) & pl.col(APT).is_in(JULY_AIRPORTS))


def seasonal_split(
    feats: pl.DataFrame, movements: pl.DataFrame, max_train_sec: float | None = None
) -> Split:
    """Split off the validation slice; fit the reference on the training slice ONLY.

    `max_train_sec` drops rows whose target exceeds the threshold **from training
    only**; validation always stays complete, because the board is complete.

    Measured, and it does not help. The 584 departures above two hours are label errors,
    since the NM off-block time is plausible in 94 percent of matched cases, yet
    removing them made RMSE worse in proportion to how many were dropped. They are wrong
    but they still teach the model that the tail exists. Kept as an experiment switch,
    off by default; see `docs/experiments.md`.
    """
    labelled = feats.filter(pl.col(TARGET).is_not_null())
    is_val = holdout_mask()

    tables = reference.fit_reference(movements.filter(~holdout_mask()))
    fit_rows = labelled.filter(~is_val)
    if max_train_sec is not None:
        fit_rows = fit_rows.filter(pl.col(TARGET) <= max_train_sec)
    fit = reference.apply_reference(fit_rows, tables)
    val = reference.apply_reference(labelled.filter(is_val), tables)
    return Split(fit, val, feature_columns(fit))


# --------------------------------------------------------------------------- model


def to_matrix(
    df: pl.DataFrame, cols: list[str], levels: dict[str, pl.Series] | None = None
) -> tuple[np.ndarray, list[int], dict[str, pl.Series]]:
    """polars -> (float32 numpy, categorical indices, level dictionary).

    pandas is deliberately not used (AGENTS.md rule 2). The level dictionary is built on
    the training side and carried to validation unchanged; otherwise the same category
    would map to different codes on the two sides and the model would break silently.
    """
    levels = {} if levels is None else levels
    arrays, cat_idx = [], []
    for i, c in enumerate(cols):
        s = df[c]
        if c in CATEGORICAL or s.dtype == pl.String:
            if c not in levels:
                levels[c] = s.drop_nulls().unique().sort()
            codes = s.cast(pl.String).replace_strict(
                old=levels[c].cast(pl.String),
                new=pl.int_range(len(levels[c]), eager=True),
                default=-1,
                return_dtype=pl.Int32,
            )
            arrays.append(codes.cast(pl.Float32).to_numpy())
            cat_idx.append(i)
        elif s.dtype == pl.Boolean:
            arrays.append(s.cast(pl.Float32).fill_null(float("nan")).to_numpy())
        else:
            arrays.append(s.cast(pl.Float32).to_numpy())
    return np.column_stack(arrays).astype(np.float32), cat_idx, levels


def rmse(pred: np.ndarray, truth: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - truth) ** 2)))


def train_predict(
    split: Split,
    cols: list[str],
    rounds: int = 1500,
    residual: bool = True,
    seeds: tuple[int, ...] = (1,),
    learners: tuple[str, ...] = ("lightgbm",),
    weights: list[float] | None = None,
) -> np.ndarray:
    """Train and return predictions for the validation slice.

    `residual=True` learns the target as a residual over the ATXOT P10 reference. That
    kind of re-parameterisation was last year's single largest gain, which is why it is
    measured here; on this data it made no difference.

    `learners` names the libraries to fit, from `taxiout.models`. Every named learner is
    fitted once per seed and everything is averaged together, so seed averaging (the
    method of the 2024 winner) and library averaging are the same operation. The default
    is LightGBM alone for compatibility with the runs already recorded in the experiment
    log; it is not the best choice, see the table in `taxiout.models.base`.
    """
    ref_fit = split.fit["reference_sec"].fill_null(strategy="mean").to_numpy()
    ref_val = split.val["reference_sec"].fill_null(strategy="mean").to_numpy()
    y = split.fit[TARGET].to_numpy().astype(np.float64)
    if residual:
        y = y - ref_fit

    preds, blend_weights = [], []
    for i, name in enumerate(learners):
        learner = models.build(name)
        for seed in seeds:
            preds.append(
                learner.fit_predict(split.fit, split.val, cols, y, rounds, seed)
            )
            blend_weights.append(1.0 if weights is None else weights[i] / len(seeds))

    pred = models.blend(preds, blend_weights)
    if residual:
        pred = pred + ref_val
    return np.clip(pred, 0.0, None)  # a negative taxi time is physically impossible


# --------------------------------------------------------------------------- evaluation


def evaluate(split: Split, pred: np.ndarray) -> dict[str, float]:
    """RMSE overall, per holdout month, and per airport."""
    truth = split.val[TARGET].to_numpy()
    scored = split.val.with_columns(_p=pl.Series(pred))
    out = {"total": rmse(pred, truth)}
    for m in HOLDOUT_MONTHS:
        sub = scored.filter(month() == m)
        if sub.height:
            out[f"month_{m}"] = rmse(sub["_p"].to_numpy(), sub[TARGET].to_numpy())
            out[f"month_{m}_n"] = float(sub.height)
    per_apt = (
        scored.group_by(APT)
        .agg(r=((pl.col("_p") - pl.col(TARGET)) ** 2).mean().sqrt())
        .sort(APT)
    )
    for apt, r in per_apt.iter_rows():
        out[f"apt_{apt}"] = float(r)
    return out


def group_report(columns: list[str]) -> str:
    """How many features each family holds; printed beside the ablation table."""
    assigned = groups.assign(columns)
    lines = [f"  {name:<22} {len(cols):>3}" for name, cols in assigned.items() if cols]
    return "\n".join(lines)
