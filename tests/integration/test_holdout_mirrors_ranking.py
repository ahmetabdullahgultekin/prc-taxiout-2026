"""The holdout must have the same shape as the ranking set, read from the ranking set.

This test exists because of a failure. Until 2026-09-04 the ranking set covered all ten
airports in January but only three in July, and the code said so in a constant:

    JULY_AIRPORTS = ("EDDF", "EGLL", "EHAM")

The organisers then completed July. Scored departures went from 215,876 to 344,841 and
every score on the leaderboard moved by roughly twenty-five seconds. Our code did not
notice: it went on validating against a July that was three airports wide, which is a
holdout that no longer resembles the thing being scored. A model selected on it is
selected for the wrong distribution.

The lesson is not "update the constant". It is that a property of somebody else's file
should be read from that file. So this reads it, and fails when the two disagree.

Skipped when the competition data is absent, which is the case in CI: rule F11 keeps it
out of the repository. It is not skipped on any machine that can actually build a
submission, which is where it matters.
"""

from __future__ import annotations

import polars as pl
import pytest

from taxiout import config
from taxiout.application import pipeline
from taxiout.domain import schema

RANKING = config.raw() / "ranking.parquet"
pytestmark = pytest.mark.skipif(
    not RANKING.exists(), reason=f"competition data not present at {RANKING}"
)


def _scored_pairs() -> set[tuple[int, str]]:
    """The (month, airport) pairs that the ranking script will actually score.

    Departures only, and only those whose id appears in `submitting.parquet`: the
    ranking file also carries the arrival rows, which exist to let features be built and
    are never scored.
    """
    ranking = pl.read_parquet(RANKING)
    ids = pl.read_parquet(config.raw() / "submitting.parquet")["MVT_ID_mvt"]
    scored = ranking.filter(pl.col(schema.Col.MVT_ID).is_in(ids.implode()))
    return set(
        scored.select(
            pl.col(schema.Col.MVT_TIME).dt.month().alias("m"),
            pl.col(schema.Col.ADEP).alias("apt"),
        ).unique().iter_rows()
    )


def test_the_holdout_covers_exactly_what_is_scored() -> None:
    pairs = _scored_pairs()
    assert pairs, "the ranking set scored nothing, which cannot be right"

    scored_months = {m for m, _ in pairs}
    assert scored_months == set(pipeline.HOLDOUT_MONTHS), (
        f"the board scores months {sorted(scored_months)} but the holdout uses "
        f"{sorted(pipeline.HOLDOUT_MONTHS)}"
    )

    for month in sorted(scored_months):
        scored_here = {a for m, a in pairs if m == month}
        missing = scored_here - set(schema.AIRPORTS)
        assert not missing, f"month {month} scores airports we do not model: {missing}"


def test_the_holdout_mask_selects_every_scored_pair() -> None:
    """The mask itself, evaluated, not the constants it is built from.

    The negative control for the test above: the pairs could line up while the mask
    dropped them anyway, which is exactly what the old `JULY_AIRPORTS` clause did.
    """
    pairs = sorted(_scored_pairs())
    frame = pl.DataFrame({
        schema.Col.MVT_TIME: pl.Series(
            [f"2026-{m:02d}-15T12:00:00" for m, _ in pairs]
        ).str.to_datetime(),
        pipeline.APT: [a for _, a in pairs],
    })

    selected = frame.select(pipeline.holdout_mask().alias("in_holdout"))["in_holdout"]
    dropped = [p for p, keep in zip(pairs, selected, strict=True) if not keep]
    assert not dropped, f"the holdout mask drops scored pairs: {dropped}"
