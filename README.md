# PRC Data Challenge 2026: Taxi-Out Time Prediction

An open source solution that predicts the **taxi-out time** (AOBT -> ATOT, in seconds) of
aircraft departing from 11 large European airports. Built for the 2026 data challenge run by
the EUROCONTROL Performance Review Commission (PRC) and the OpenSky Network.

- Competition: <https://ansperformance.eu/study/data-challenge/dc2026/>
- Metric: RMSE (seconds), over the January + July 2026 departures
- Licence: GNU GPLv3 (a competition prize condition)

## Status

Second on the leaderboard, **RMSE 306.41**, 7.4 seconds behind the leader. Three submissions
so far; `docs/experiments.md` records every one of them, including the two that did not work.

| version | change | local holdout | board |
|---|---|---:|---:|
| v1 | LightGBM, 800 rounds, 3 seeds | 378.80 | 331.23 |
| v2 | LightGBM, slower rate, wider trees | ~372 | 331.80 |
| **v3** | **XGBoost + CatBoost, 400 rounds, 1 seed** | **351.69** | **306.41** |

v3 added nothing to the model. Same 90 features, same split, same target, fewer rounds and
fewer seeds than v1. The entire 24.8 second gain came from which library fits the trees, a
choice that had never been tested. See [the learner comparison](docs/experiments.md).

## Approach

The problem is set up by following the decomposition of EUROCONTROL's own *additional taxi-out
time* indicator:

    taxi-out = unimpeded reference + queue + congestion

The **reference component** is a faithful reimplementation of the official methodology: P10 for
every (airport, stand, departure runway) combination, and for validity at least 10 flights at
or below P10 (`src/taxiout/domain/reference.py`). The model can learn either the raw taxi-out
time or the **residual** over that baseline; re-parameterising the target this way was the
single largest gain reported by the 2025 winner, and on this data it makes no measurable
difference either way. The submitted models predict the raw time and take the reference as a
feature, where it is the strongest single one.

The **queue and congestion components** are built from the movement stream. In the ranking set
only the block time and the taxi time of departures are blanked out; the take-off time, the
runway, the stand and all of the arrivals are still there. So the traffic around a departure is
fully observable. That is a natural consequence of the **post-operations** setup (which is also
the stated purpose of the competition), and it makes the queue variable, which a real-time
model would have to predict, measurable here.

The same code produces two models:

| | anchor | use |
|---|---|---|
| retrospective | take-off instant | competition submission; post-ops KPI, filling gaps in data |
| causal | off-block instant | real-time decisions such as A-CDM / TSAT / DMAN |

The two can be compared on the same validation set; the difference between them is the
information value of retrospective observability.

### The learner

Gradient boosting, with the library kept behind a port (`src/taxiout/models/`) rather than
hardcoded, because the choice turned out to matter more than anything else measured here:

| learner | holdout RMSE, same 92 features, 400 rounds |
|---|---:|
| LightGBM, categorical splits | 378.99 |
| XGBoost, categoricals as plain integer codes | 357.80 |
| CatBoost, ordered target statistics | 353.59 |
| XGBoost + CatBoost, equal weight | **351.69** |

The paired noise floor on this holdout is about 5 seconds, so those are real gaps. The reading
is that LightGBM's categorical splitting overfits the high-cardinality fields, of which there
are several: 1,899 stands, a hashed aircraft operator, 11 aircraft types. The evidence is
XGBoost, which applies no categorical handling at all and still beats it by 21 seconds.

Adding LightGBM to the blend makes it worse, so it is contributing error rather than a
different view of the data.

## External data

| Source | Licence | Used for |
|--------|---------|----------|
| [Iowa Environmental Mesonet ASOS/METAR](https://mesonet.agron.iastate.edu/) | public domain | temperature, visibility, wind, precipitation; de-icing proxy |
| [OurAirports](https://ourairports.com/data/) | public domain | coordinates (departure bearing), runway counts |

Detailed rationale and licence texts: `docs/external_data.md`.

## Verification

```bash
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe
$PY -m ruff check src tests scripts
$PY -m pytest tests -q
```

`.github/workflows/ci.yml` runs the same two checks on every push, then drives the whole
documented pipeline over synthetic data: fixture, probe, training and a submission file.
That last step is the one worth having, because it checks the commands in this README
work from a clean checkout.

Note that GitHub Actions is currently blocked on this account for a billing reason, so
the workflow is present and correct but does not execute here. It runs normally in a
fork. Until that is resolved, verification is the two commands above, run locally before
every commit.

## Documents

| File | Contents |
|-------|--------|
| `docs/facts.md` | Register of verified facts (source + date required) |
| `docs/experiments.md` | Experiment log, negative results included |
| `docs/external_data.md` | External data sets used, with their licences (prize condition) |
| `docs/reference/` | EUROCONTROL official ATXOT methodology document and notes |
| `docs/adr/` | Architecture decisions that are expensive to reverse |
| `docs/literature.md` | Literature review; the rationale for each feature family |
| `docs/paper/` | JOAS paper draft and the official LaTeX template |

## Running it

```bash
python -m venv D:/prc-taxiout-2026/.venv
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe
$PY -m pip install -e ".[dev]"

# external data (needs no competition data)
$PY -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01     --out D:/prc-taxiout-2026/00_raw/metar.parquet
$PY -m taxiout.adapters.airports --raw-dir D:/prc-taxiout-2026/00_raw

# once the competition data has arrived
$PY scripts/probe_data.py     --data-dir D:/prc-taxiout-2026   # data diagnosis
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026   # seasonal validation
$PY scripts/run_ablation.py   --data-dir D:/prc-taxiout-2026   # feature family table

# the submitted configuration
$PY scripts/make_submission.py --data-dir D:/prc-taxiout-2026 --team vibrant-lollipop \
    --learners xgboost,catboost --rounds 400 --seeds 1 --raw-target
$PY scripts/submit.py --team vibrant-lollipop      # uploads, verifies, prints the score

$PY -m pytest tests -q
```

`submit.py` rather than a bare `mc cp`: the alias for the OpenSky endpoint is `prc`, and `mc`
does not treat an unknown alias as an error. It reads the argument as a relative local path,
creates the directory, copies the file into it and reports success. One submission was lost
that way. The script refuses to start unless the alias resolves to an https endpoint and
confirms the object is listed in the remote bucket afterwards.

A synthetic fixture, to drive the pipes without the data:

```bash
$PY tests/make_fixture.py --out D:/prc-taxiout-2026/99_fixture/00_raw
$PY scripts/train_baseline.py --data-dir D:/prc-taxiout-2026/99_fixture --rounds 300
```

## Where the data lives

The code is in this repository (backed up through OneDrive). Data and models live under
`D:/prc-taxiout-2026/`, because the C: drive has only 6% free space and a DRAM-less SSD whose
write speed collapses. It can be changed with the `TAXIOUT_DATA_DIR` environment variable.
