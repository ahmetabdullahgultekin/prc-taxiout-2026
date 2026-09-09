# Project Instructions: PRC Data Challenge 2026 (taxi-out)

## What we are doing

We predict the taxi-out time, in seconds, of **departure** movements at **10** European
airports. The competition page says eleven and the data holds ten; the data is right
(`docs/facts.md` R01). The metric is **RMSE**.

The ranking set is January and July 2026 at all ten, **344,841 scored departures**. It was
not always: until 2026-09-04 July held only three airports and the set was 215,876 rows.
The organisers replaced it without announcing it and reset the leaderboard, so:

* **Never write the shape of the ranking set into the code.** Read it from the file.
  `tests/integration/test_holdout_mirrors_ranking.py` fails if the holdout stops matching.
* `scripts/watch_board.py` runs on a timer and compares the API's `usedPairs` with our own
  `submitting.parquet`. If it ever disagrees, everything local is stale.

**Three submissions per team per day**, resetting at 00:00 UTC. This is published nowhere;
we found it by hitting `DAILY_LIMIT_REACHED`. Plan each day around three answers.

Deadline **2026-10-11**. The site says 23:59:59 CET on a date when Europe is still on CEST,
so treat it as **21:59:59 UTC** and finish a day early.

Target: top 3. The prize is not won on RMSE alone, the jury also assesses the repository and
the documentation (see `docs/facts.md` F14).

## Read first

Before any modelling decision, read **`docs/facts.md`** and **`docs/reference/atxot-notes.md`**.
The competition rules and the official methodology are there, with source and date.
Do not quote a rule or a column name from memory: if it is not in the register, verify it and
add it to the register.

## Hard rules

1. **No absolute paths.** The data path comes from the `TAXIOUT_DATA_DIR` environment variable
   or the `--data-dir` flag. The 2025 jury criticised hardcoded Windows paths explicitly.
2. **Do not use pandas, use polars.** 4.2M rows by many columns blows up in pandas on 16 GB of
   RAM. Use `polars.scan_parquet` (lazy) or duckdb for bulk reads. We do not switch to pandas
   at the LightGBM boundary either: categoricals are turned into integer codes and handed over
   as float32 numpy (`scripts/train_baseline.py:to_matrix`). The category level dictionary
   **must be carried** from training to validation, otherwise the same category lands on a
   different code on each side and the model breaks silently.
3. **The loss function is L2.** The optimal predictor under RMSE is the conditional mean.
   Huber, MAE, quantile, or an uncorrected log target introduce a systematic bias. If one is
   tried, it goes into `docs/experiments.md` as a negative result.
4. **Random K-fold is forbidden.** Validation: January and July are removed from 2025, the
   model is trained on the remaining 10 months, and those two months are reported
   **separately**. Per-airport RMSE is always written down.
5. **Every experiment goes into `docs/experiments.md`**, including the ones that did not work.
6. **Raw competition data is never committed.** Entry condition: the data may not be used
   outside the competition until it is public (F11).
7. **`docs/external_data.md` is filled in before an external data source is added.** No source
   is used before its licence is written down; this is a prize eligibility condition.
8. **No vendor or model name appears in the repository** (commits, PRs, branch names, file
   names, documents).

## Code layout

```
src/taxiout/
  domain/       pure logic, no IO, no third-party model library
  features/     pure transforms: (LazyFrame) -> LazyFrame
  adapters/     IO: parquet, minio, metar, model libraries
  application/  orchestration: build features, train, predict, evaluate
scripts/        one-off and diagnostic tools
```

There is **no port/interface layer**: for a six-week single-purpose batch pipeline it is
needless abstraction, and the 2025 jury criticised one team for being "structured to the point
of being over-structured". The value is in testable pure functions and in reproducibility.

## Commands

```bash
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe

# data diagnosis (the first thing to run once the data lands)
$PY scripts/probe_data.py

# external data: METAR (already downloaded, no need to fetch again)
$PY -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01     --out D:/prc-taxiout-2026/00_raw/metar.parquet

# end-to-end baseline model + evaluation
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026 --no-aobt3   # ablation

# synthetic fixture, to exercise the pipes before the real data arrives
$PY tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026/99_fixture --rounds 300

$PY -m pytest tests/unit -q
$PY -m ruff check src tests scripts
```

The team name is **`vibrant-lollipop`**, the submission bucket is
**`prc-2026-vibrant-lollipop`**, and the file name is `vibrant-lollipop_vN.parquet`. The `mc`
client is installed under `~/bin/mc.exe`.

**Network trap:** OSN is unreachable while Cloudflare WARP is on. Run `warp-cli disconnect`
before downloading data.

`make` is not installed on this machine, so there is no Makefile; python is called directly.

## Environment

Windows 11, 16 GB RAM, GTX 1650 (4 GB). **Do not use the GPU**: at this data size LightGBM
histogram on CPU is faster, the data transfer eats the gain. Memory discipline: float32,
categoricals as `pl.Categorical`, feature generation split per airport and written to disk.
