"""The feature cache, and the fingerprint that stops it being used after the code moves.

The fingerprint is a safety mechanism, and an untested safety mechanism is not one. The
failure it prevents is specific: a cache built before a feature changed does not error,
it answers plausibly for a model that no longer exists. This project spent a night on
exactly that shape of problem when a feature went silently constant.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from taxiout.application import cache


def _frames() -> tuple[pl.DataFrame, pl.DataFrame, list[str]]:
    fit = pl.DataFrame({"a": [1.0, 2.0], "TAXITIME_SEC_mvt": [100.0, 200.0]})
    val = pl.DataFrame({"a": [3.0], "TAXITIME_SEC_mvt": [300.0]})
    return fit, val, ["a"]


def test_a_cache_written_now_loads_now(tmp_path: Path) -> None:
    fit, val, cols = _frames()
    cache.write(tmp_path, fit, val, cols)
    assert cache.stale(tmp_path) == []
    loaded = cache.read(tmp_path)
    assert loaded.fit.height == 2
    assert loaded.val.height == 1
    assert loaded.columns == cols


def test_a_missing_cache_reports_itself_rather_than_raising(tmp_path: Path) -> None:
    # Callers use this to decide whether to build, so it must not throw.
    assert cache.stale(tmp_path) != []


def test_a_changed_source_file_makes_the_cache_stale(tmp_path: Path) -> None:
    """The whole point: edit a feature module, and the cache stops loading."""
    fit, val, cols = _frames()
    cache.write(tmp_path, fit, val, cols)

    stored = json.loads((tmp_path / cache.FINGERPRINT).read_text(encoding="utf-8"))
    victim = next(f for f in stored["sources"] if f.startswith("features/"))
    stored["sources"][victim] = "0000000000000000"
    (tmp_path / cache.FINGERPRINT).write_text(json.dumps(stored), encoding="utf-8")

    assert cache.stale(tmp_path) == [victim]
    with pytest.raises(SystemExit, match="built by different code"):
        cache.read(tmp_path)


def test_force_overrides_the_refusal(tmp_path: Path) -> None:
    fit, val, cols = _frames()
    cache.write(tmp_path, fit, val, cols)
    stored = json.loads((tmp_path / cache.FINGERPRINT).read_text(encoding="utf-8"))
    stored["sources"]["features/congestion.py"] = "0000000000000000"
    (tmp_path / cache.FINGERPRINT).write_text(json.dumps(stored), encoding="utf-8")

    assert cache.read(tmp_path, force=True).fit.height == 2


def test_the_fingerprint_watches_the_files_that_change_columns(tmp_path: Path) -> None:
    """Negative control: a fingerprint over nothing would make every test above vacuous."""
    fit, val, cols = _frames()
    cache.write(tmp_path, fit, val, cols)
    watched = json.loads(
        (tmp_path / cache.FINGERPRINT).read_text(encoding="utf-8")
    )["sources"]

    assert len(watched) > 8, f"only {len(watched)} files watched"
    for expected in ("features/congestion.py", "features/overlap.py",
                     "features/surface_delay.py", "domain/reference.py",
                     "domain/schema.py", "application/pipeline.py"):
        assert expected in watched, f"{expected} is not fingerprinted"


def test_the_submission_pair_is_demanded_when_asked_for(tmp_path: Path) -> None:
    """A submission needs the all-2025 reference frames, and must say so if absent.

    Falling back to the split's training frame would train against one reference and
    predict against another, shifting every prediction by the difference between them.
    """
    fit, val, cols = _frames()
    cache.write(tmp_path, fit, val, cols)  # no rank, no fit_full
    with pytest.raises(SystemExit, match="scripts/cache_features.py --ranking"):
        cache.read(tmp_path, want_rank=True)


def test_the_submission_pair_round_trips(tmp_path: Path) -> None:
    fit, val, cols = _frames()
    rank = pl.DataFrame({"a": [4.0, 5.0], "TAXITIME_SEC_mvt": [None, None]})
    fit_full = pl.DataFrame({"a": [1.0, 2.0, 3.0], "TAXITIME_SEC_mvt": [1.0, 2.0, 3.0]})
    cache.write(tmp_path, fit, val, cols, rank=rank, fit_full=fit_full)

    loaded = cache.read(tmp_path, want_rank=True)
    assert loaded.rank.height == 2
    assert loaded.fit_full.height == 3
    # The submission frame is not the split frame; conflating them is the bug this guards.
    assert loaded.fit_full.height != loaded.fit.height
