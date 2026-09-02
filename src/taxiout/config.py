"""Paths and competition identifiers, defined once.

The data directory was written out as a literal twenty-one times across the source and
the scripts. That is not only repetition: it hardcodes one machine's drive layout into
a repository the organisers fork and a jury reads. `TAXIOUT_DATA_DIR` overrides it, and
every script now takes its default from here rather than from its own copy.

Nothing secret belongs in this file. The competition data may not be redistributed
(rule F11) and lives outside the repository; credentials live in the `mc` configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

# Where the competition data lives. Outside the repository on purpose: rule F11 forbids
# using the 2026 data beyond the competition until it is publicly released, so it is
# never committed.
DATA_DIR = Path(os.environ.get("TAXIOUT_DATA_DIR", "D:/prc-taxiout-2026"))

RAW_DIR = "00_raw"
CACHE_DIR = "03_cache"
SUBMISSION_DIR = "04_submissions"

# Submission transport. The alias matters: `mc` reads an unknown one as a local
# directory path, creates it, copies the file into it and reports success. One
# submission was lost that way, see scripts/submit.py.
MC_ALIAS = "prc"
BUCKET_PREFIX = "prc-2026-"

COMPETITION_ID = "bb3693e1-26bc-4a9e-8619-4fe78b4eab0c"
LEADERBOARD_URL = (
    f"https://datacomp.opensky-network.org/api/competitions/{COMPETITION_ID}/leaderboard"
)

TEAM = os.environ.get("TAXIOUT_TEAM", "vibrant-lollipop")


def raw(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / RAW_DIR


def cache(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / CACHE_DIR


def submissions(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or DATA_DIR) / SUBMISSION_DIR


def bucket(team: str = TEAM) -> str:
    """The team's MinIO bucket, alias included."""
    return f"{MC_ALIAS}/{BUCKET_PREFIX}{team}"
