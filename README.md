# PRC Data Challenge 2026: Taxi-Out Time Prediction

An open source solution that predicts the **taxi-out time** (AOBT -> ATOT, in seconds) of
aircraft departing from 10 large European airports. Built for the 2026 data challenge run by
the EUROCONTROL Performance Review Commission (PRC) and the OpenSky Network.

The competition page says eleven airports and the data holds ten; the data is right.

- Competition: <https://ansperformance.eu/study/data-challenge/dc2026/>
- Metric: RMSE (seconds), over the January + July 2026 departures
- Licence: GNU GPLv3 (a competition prize condition)

## Status

**RMSE 310.55**, 25th of 69 scoring teams. `docs/experiments.md` records every submission,
including the four that made things worse.

| version | change from the row above | board RMSE |
|---|---|---:|
| v12 | gradient boosting, 92 features, 1000 rounds | 411.23 |
| v13 | predictions capped at 7,200 s, EUROCONTROL's own taxi threshold | 488.84 |
| v14 | capped at 4,500 s | 507.28 |
| v19 | **the mixture: read the schedule off where the feed substituted it** | **334.01** |
| v21 | the weight target clipped to (-0.25, 1.25) rather than (0, 1) | **318.16** |
| v25 | two seeds averaged | **310.55** |
| v26 | averaged with a weaker second model | 314.71 |
| v28 | averaged with a second model of comparable quality | 315.56 |

Every row differs from the one above by one decision, so the differences are an ablation
performed on the scored set rather than on cross-validation.

The two capping rows are the control that matters. Restricting predictions to the
120-minute threshold EUROCONTROL uses to decide what is no longer a taxi touches 114 rows
of 344,841 and costs 77.6 seconds: the extreme predictions are correct. This metric is
decided by a few hundred flights. On the holdout, **24 rows above six hours carry 37.3
percent of the total squared error**.

The last two rows are reported because they contradict the usual advice about ensembles.
The same partner averaged into a one-seed base gained 2.2 s and into a two-seed base lost
4.2; a partner of comparable quality lost 5.0. Here averaging removes seed noise and does
nothing else, and seed averaging captures that more cheaply.

**Three submissions per team per day**, resetting at 00:00 UTC. That is published nowhere;
it was found by hitting the limit. The ranking set was also replaced without announcement
on 2026-09-04, which reset the leaderboard: `scripts/watch_board.py` runs on a timer and
compares the API's `usedPairs` against our own template so the next change is noticed
within twenty minutes rather than three days.

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

### What the target actually is

On 4.86 percent of training rows the taxi-out equals the take-off time minus the
**scheduled** time to within ten seconds. Since the target is the take-off time minus the
block time, the airport feed's block time on those rows *is* the scheduled time: it writes
the schedule into a field it has no measurement for. The share is 18.4 percent at Rome
against 1.1 percent at Zurich, and 53.8 percent at Rome among flights the Network Manager
never matched.

That is where the metric lives. **333 of the 435 training rows above two hours are rows of
this kind**, and their target is a column the ranking set already publishes.

It cannot be checked on the ranking set's departures, whose block times are blanked, but it
can be checked on its arrivals, which keep everything: the same substitution runs at 2.31
percent in January and July 2025 and 2.42 percent in 2026, with the same shape across
airports. The behaviour belongs to the feed, not to the year.

Every other timestamp in the file was searched for the same identity, with shifts of half
an hour to a day. One more exists and carries no long taxis; nothing else does.

`src/taxiout/models/mixture.py` turns this into a mixture rather than a rule, because under
a squared loss the conditional mean is what is wanted, and it fits the mixing weight out of
fold rather than classifying the identity. See `docs/adr/0004-mixture-over-a-substituted-target.md`.

### The learner

Gradient boosting, with the library kept behind a port (`src/taxiout/models/`) rather than
hardcoded, because the choice turned out to matter more than anything else measured before
the mixture:

| learner | holdout RMSE, same 92 features, 400 rounds |
|---|---:|
| LightGBM, categorical splits | 378.99 |
| XGBoost, categoricals as plain integer codes | 357.80 |
| CatBoost, ordered target statistics | 353.59 |
| XGBoost + CatBoost, equal weight | **351.69** |

The paired noise floor on this holdout is about 5 seconds, so those are real gaps. The reading
is that LightGBM's categorical splitting overfits the high-cardinality fields, of which there
are several: 1,899 stands, 269 aircraft types, a hashed aircraft operator. The evidence is
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
$PY -m pytest tests -q          # or: $PY scripts/verify.py, which runs every CI check
```

`scripts/verify.py` is the real check runner here. It runs lint, the tests, and then the
whole documented pipeline over synthetic data (fixture, probe, training, a submission
file), which is the step worth having, because it proves the commands in this README work
from a clean checkout. Install it as a pre-push hook with `--install-hook`.

`.github/workflows/ci.yml` holds the same steps and is set to manual trigger. Not because
it is broken: **GitHub Actions cannot start on this account at all.** Every run ends in
three seconds having executed zero steps, with *"the job was not started because your
account is locked due to a billing issue"*. A wall of red crosses would read as broken
code, which is the opposite of what it means, so the automatic triggers are commented out
and a fork with working Actions restores them by uncommenting two lines.

`tests/unit/test_verify_matches_ci.py` compares the two step lists, so the local runner
cannot fall behind the workflow while looking like it covers it.

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
$PY scripts/audit_data.py     --data-dir D:/prc-taxiout-2026   # data quality audit
$PY scripts/cache_features.py --data-dir D:/prc-taxiout-2026   # build features once, reuse
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
