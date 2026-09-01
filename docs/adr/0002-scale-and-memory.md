# ADR-0002: An in-memory pipeline is enough, out-of-core is not needed

Date: 2026-09-01 · Status: accepted

## Context

The machine has 16 GB of RAM (15.9 usable). The competition data is 4,167,797 movements, about
277 MB of parquet. The question left open at the start of the design: can feature generation be
done in memory, or does it have to be split per airport and written to disk?

We closed the uncertainty by measuring rather than guessing: synthetic data at the real size
(4,166,400 movements, 252 MB of parquet) was generated with
`tests/make_fixture.py --per-day 12400` and the pipeline was run end to end.

## Measurement (2026-09-01)

| Stage | Time | Peak RSS |
|---|---|---|
| data loading (4.17M movements) | 1 s | 1.75 GB |
| feature generation (2.08M departures x 114 columns) | 28 s | 3.91 GB |
| split + ATXOT reference | 2 s | **5.15 GB** |
| matrix (1.74M x 95 float32 = 0.61 GB) | 3 s | 4.68 GB |
| training (LightGBM, 200 rounds) | 63 s | 4.16 GB |
| **end-to-end validation run** | **96 s** | **5.15 GB** |
| **submission path** (training and ranking features at the same time) | **171 s** | **7.06 GB** |

## Decision

The pipeline runs **entirely in memory**. Per-airport splitting, intermediate writes to disk and
an out-of-core setup **will not be built**.

## Rationale

Even at the highest memory point, the submission path, it uses 7.06 GB of 15.9 GB, so there is
more than a factor of two in hand. Splitting would make the code markedly more complicated, and
the 2025 jury criticised one team explicitly for needless structure.

## Consequences

- A full ablation (13 configurations x 1500 rounds) takes about **1.7 hours**; about 8.5 hours
  with 5 seeds. It can be planned as an overnight run, and the round count is kept low for
  iteration during the day.
- The `float32` and `max_bin=127` choices stay; the headroom was measured with them in place.
- The scale test is repeatable: `tests/make_fixture.py --per-day 12400`.
- **Warning:** the measurement was made on synthetic data. The categorical cardinality of the
  real data (`STAND_mvt` and `AIRCRAFT_OPERATOR_flt` in particular) may be higher; memory will
  be measured again on the first full run once the data arrives.
