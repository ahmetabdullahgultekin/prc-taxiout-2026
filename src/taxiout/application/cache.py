"""On-disk cache of the built feature tables, with a fingerprint that invalidates it.

Building the features takes minutes and every submission and every experiment pays it
again. In a competition where the previous winner made roughly 250 submissions, that
cost is the binding constraint rather than the modelling.

The fingerprint is the point. A cache that is merely old is harmless; a cache built
before a feature changed is not, because it produces a perfectly plausible number for a
model that no longer exists. This project has already lost a night to a feature that was
silently constant, so the rule here is that the cache refuses to load when the code that
produced it has moved, and says which files moved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl

SRC = Path(__file__).resolve().parents[1]
# Everything whose change would alter a column. The reference table and the schema count
# as much as the feature modules do.
WATCHED = ("features", "domain", "application/pipeline.py")

FINGERPRINT = "fingerprint.json"


def _hash_sources() -> dict[str, str]:
    """A digest per watched source file, so a mismatch can name what changed."""
    out: dict[str, str] = {}
    for entry in WATCHED:
        path = SRC / entry
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for f in files:
            if f.name == "__pycache__":
                continue
            digest = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
            out[str(f.relative_to(SRC)).replace("\\", "/")] = digest
    return out


@dataclass
class Cached:
    """`fit` and `val` are the seasonal split, for experiments.

    `fit_full` and `rank` are the submission pair, and they exist separately because
    the reference table differs. The split's reference is fitted WITHOUT the holdout
    months, so that validation does not score against a baseline that saw its own
    answers. A submission has no such constraint and wants all of 2025. Training on one
    reference and predicting against the other would shift every prediction by the
    difference between them, quietly.
    """

    fit: pl.DataFrame
    val: pl.DataFrame
    columns: list[str]
    rank: pl.DataFrame | None = None
    fit_full: pl.DataFrame | None = None


def write(directory: Path, fit: pl.DataFrame, val: pl.DataFrame,
          columns: list[str], rank: pl.DataFrame | None = None,
          fit_full: pl.DataFrame | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fit.write_parquet(directory / "fit.parquet")
    val.write_parquet(directory / "val.parquet")
    pl.DataFrame({"column": columns}).write_parquet(directory / "columns.parquet")
    if rank is not None:
        rank.write_parquet(directory / "rank.parquet")
    if fit_full is not None:
        fit_full.write_parquet(directory / "fit_full.parquet")
    (directory / FINGERPRINT).write_text(
        json.dumps({"sources": _hash_sources(), "columns": columns}, indent=2),
        encoding="utf-8",
    )


def stale(directory: Path) -> list[str]:
    """Which watched source files differ from the ones that built this cache.

    An empty list means the cache is safe to use. A missing cache reports itself rather
    than raising, so callers can fall back to building.
    """
    path = directory / FINGERPRINT
    if not path.exists():
        return ["(no fingerprint; the cache predates this check or is absent)"]
    stored = json.loads(path.read_text(encoding="utf-8"))["sources"]
    current = _hash_sources()
    changed = [f for f in sorted(set(stored) | set(current))
               if stored.get(f) != current.get(f)]
    return changed


def read(directory: Path, want_rank: bool = False, force: bool = False) -> Cached:
    """Load the cache, refusing a stale one unless explicitly forced."""
    changed = stale(directory)
    if changed and not force:
        raise SystemExit(
            f"the feature cache in {directory} was built by different code:\n  "
            + "\n  ".join(changed[:10])
            + "\n\nRebuild it with scripts/cache_features.py, or pass --force-cache to "
            "use it anyway. A stale cache does not fail, it quietly answers for a model "
            "that no longer exists."
        )
    rank = fit_full = None
    if want_rank:
        for name in ("rank", "fit_full"):
            if not (directory / f"{name}.parquet").exists():
                raise SystemExit(
                    f"no {name} features in {directory}. Build them with "
                    "scripts/cache_features.py --ranking"
                )
        rank = pl.read_parquet(directory / "rank.parquet")
        fit_full = pl.read_parquet(directory / "fit_full.parquet")
    return Cached(
        fit=pl.read_parquet(directory / "fit.parquet"),
        val=pl.read_parquet(directory / "val.parquet"),
        columns=pl.read_parquet(directory / "columns.parquet")["column"].to_list(),
        rank=rank,
        fit_full=fit_full,
    )
