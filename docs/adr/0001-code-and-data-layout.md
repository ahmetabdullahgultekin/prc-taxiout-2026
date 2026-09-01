# ADR-0001: Code on OneDrive, data on the D: drive

Date: 2026-09-01 · Status: accepted

## Context

The development machine has 16 GB of RAM, 30 GB free of 475 GB on C: (6.4%), and 39 GB free of
231 GB on D:. C: is a DRAM-less Toshiba BG4 SSD; past 90% full its write speed collapses to
about 28 MB/s (measured earlier). The repository also sits in a OneDrive folder, so `.venv/`
and parquet files would generate constant sync traffic.

## Decision

- **Code, documents, tests:** `C:/Users/ahabg/OneDrive/Belgeler/GitHub/prc-taxiout-2026`
  (OneDrive sync acts as a backup for source code, consistent with the other projects).
- **Data, features, models, virtual environment:** `D:/prc-taxiout-2026/`
  (`00_raw`, `01_interim`, `02_features`, `03_models`, `04_submissions`, `.venv`).
- The path can be changed with the `TAXIOUT_DATA_DIR` environment variable or the `--data-dir`
  flag. **No absolute path is written in the code**: the 2025 jury criticised hardcoded Windows
  paths explicitly.

## Consequences

- `.gitignore` covers `data/` and `*.parquet`; raw competition data is never committed (form
  condition: the data may not be used outside the competition until it is public, F11).
- Because the virtual environment lives outside the repository, the run commands give the
  interpreter path explicitly.
