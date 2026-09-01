# Experiment Log

Every row corresponds to a GitHub issue. **Negative results are written down too**: the 2025
jury explicitly praised the teams that reported what did not work. This table becomes the
ablation section of the paper directly.

Validation scheme: January and July are removed from 2025 for training, and the model is
validated on those two months **separately**. The reason: the ranking set is January + July
2026, two seasonal extremes.

| ID | Hypothesis | Change | OOF RMSE (Jan / Jul / Total) | Delta | Decision | Commit |
|----|---------|-----------|-------------------------------|-------|-------|--------|
| E00 | data diagnosis | - | - | - | ✅ 15 facts recorded (facts R01-R15) | 42b6cd0 |
| E01 | (apt, stand, runway) mean | baseline | - / - / **628.4** | reference | ✅ baseline (probe §7) | 42b6cd0 |
| E02a | full feature set, **raw** target | 95 features, 600 rounds, 1 seed | 423.60 / 240.80 / **378.80** | -249.6 | ✅ keep | 6b095f6 |
| E02b | full feature set, **ATXOT P10 residual** | same | 423.94 / 240.88 / **379.09** | +0.29 | ❌ **no gain** | 6b095f6 |
| **v1** | first submission: raw target, 800 rounds, 3 seeds | - | local 378.80 -> **BOARD 331.23** | - | ✅ baseline board score | 6b095f6 |
| E03a | drop outliers from training (>120 min) | -4,180 rows | 455.11 / 236.25 / **402.92** | **+24.1** | ❌ **HARMFUL** | bc3c88f |
| E03b | drop outliers from training (>60 min) | -7,249 rows | 467.53 / 249.29 / **415.07** | **+36.3** | ❌ **even more harmful** | bc3c88f |

**The local to board relationship (v1).** Local validation gave 378.80, the board 331.23: the
local measurement is **pessimistic**, the board is 12.6% better. That is the safe direction.
The likely reason is that the 2025 January/July holdout carries exactly the right dose of LIRF
label errors. What matters is whether the **ordering** is preserved; that will be tested on the
second submission.

**Note on E02b.** The largest gain of the 2025 winner came from reparameterising the target
(fuel burn -> fuel flow, 220.56 -> 201.04). It **did not transfer** here: the residual target is
statistically the same as the raw target (a difference of 0.29 s, 0.08%). The likely reason is
that their transform reduced skew, whereas here the ATXOT reference is already a constant the
tree learns in its first splits, so subtracting it adds no information. A negative result to
report.

## Target parameterisation: three attempts, none separated

> **Corrected after measuring the resolution of this holdout (next section).** These
> three configurations differ by 2 to 5 seconds, which is inside the noise floor.
> Nothing here is a result. The raw target is kept because it is the simplest, not
> because it was shown to be better.

Same holdout, same 90 features, 400 rounds:

| configuration | RMSE | January | July |
|---|---:|---:|---:|
| naive (no model, MVT - AOBT_3) | 531.40 | - | - |
| **raw target** | **377.84** | 422.42 | 240.63 |
| reference residual (ATXOT P10) | 379.73 | 424.87 | 240.43 |
| NM residual (naive prediction as baseline) | 382.74 | 427.05 | 247.22 |

The largest gain of the 2025 winner came from reparameterising the target (fuel burn -> fuel
flow, 220.56 -> 201.04). Here **two separate baselines were tried and both did harm**. The raw
target wins. The likely reason is that their transform reduced skew, whereas here both
baselines are something the tree already learns in its first splits, so subtracting them adds
no information and instead distorts the distribution of the residual target.

One other thing stands out in the same table: **the model buys 154 seconds over the naive
prediction** (531 -> 378). Even though the gain distribution makes the congestion features look
close to worthless, the model itself is clearly doing its job.

## How large a difference can this holdout resolve?

Measured before trusting any more comparisons, because RMSE here is dominated by a few
hundred rows: at Paris five rows carry two thirds of the squared deviation, at Rome five
carry four fifths.

Two different numbers, and the distinction matters:

| quantity | spread |
|---|---:|
| a single score, unpaired bootstrap | standard deviation about **56 s** |
| a difference between two models on the same rows | resolves to about **5 s** |

Three seeds of the same configuration scored 377.44, 377.57 and 376.67, and every paired
seed-to-seed difference has a confidence interval spanning zero. That spread is the noise
floor. Paired bootstrap results:

| comparison | difference | 95% CI | verdict |
|---|---:|---|---|
| seed 2 minus seed 1 | +0.13 | [-4.73, +4.03] | not distinguishable |
| seed 3 minus seed 1 | -0.77 | [-2.91, +0.83] | not distinguishable |
| slow seed 2 minus slow seed 1 | +2.11 | [-2.01, +6.67] | not distinguishable |
| **slow minus base, seed 1** | **-5.42** | **[-9.45, -1.59]** | **significant** |
| **slow minus base, seed 2** | **-3.45** | **[-6.56, -0.35]** | **significant** |

### What this invalidates

**The target parameterisation results above were reported as conclusions and they are
not.** Raw at 377.84, reference residual at 379.73 and NM residual at 382.74 differ by 2
to 5 seconds, which sits inside the noise floor. The honest statement is that no
parameterisation was shown to beat any other, not that the raw target wins. The claim
that last year's largest lever "does not transfer" is unsupported by this evidence; it
was not measured either way.

**E03 survives.** Removing outliers from training cost 24 and 36 seconds at the two
thresholds, both well outside the floor, and the effect grows with the threshold. That
negative result stands.

**The gain shares are unaffected.** Feature importance is a direct measurement of the
fitted model, not a comparison of noisy scores.

### What follows for how we run experiments

The board is a **better** comparator than this holdout, which is not the usual situation.
It is a fixed set, so every submission is scored on the same rows and board comparisons
are paired in exactly the way the local ones need bootstrapping to become. Feedback
arrives in about fifteen seconds and no submission limit is published. Local runs are
for deciding what is worth submitting; the board decides what is true.

## Gain distribution: it falsifies my thesis

| family | gain | feature count |
|---|---:|---:|
| atfm | 36.8% | 5 |
| geometry | 31.5% | 9 |
| nm_aobt | 10.4% | 2 |
| runway_configuration | 5.9% | 3 |
| atfm_daily | 3.7% | 6 |
| aircraft | 2.8% | 5 |
| routing | 2.0% | 5 |
| weather | 1.8% | 14 |
| **runway_queue** | **1.6%** | **13** |
| **airport_flow** | **1.4%** | **21** |
| stand_turnaround | 1.0% | 1 |
| calendar | 0.6% | 4 |
| taxi_in_pressure | 0.5% | 2 |

The rationale for the design was that the queue variable of Idris et al. is **observable**
here, and I assumed that observability would give an advantage. The 34 window counts carry 3%
of the total gain. `reference_sec` on its own carries 18.8%.

A possible explanation: `sched_offset_sec` and `eobt_offset_sec` already encode the delay
state and carry congestion indirectly, so separate counts add nothing. That does not mean the
observability thesis is wrong, but it does show that **in this feature form** it did not pay
off.

## Where the error is (2026-09-01)

Total RMSE is 378.80, but **two airports dominate it**:

| airport | RMSE | note |
|---|---:|---|
| LIRF | 966.5 | outliers |
| LFPG | 801.5 | outliers |
| EGLL | 297.8 | the longest taxi (mean 22.7 min) |
| LTFM | 228.2 | |
| LSZH | 220.6 | |
| EHAM | 201.0 | |
| EDDF | 189.4 | |
| EDDM | 187.6 | |
| LEMD | 165.5 | |
| LEBL | 151.1 | the easiest |

By month: **January 423.6 · July 240.8**. January is both harder and 71% of the rows.

### E03: dropping outliers from training is HARMFUL (the opposite of what was expected)

| threshold | training rows | LIRF RMSE | total RMSE | Δ |
|---|---:|---:|---:|---:|
| none | 1,870,367 | 966.5 | **378.80** | - |
| ≤120 min | 1,866,187 | 1,149.4 | 402.92 | +24.1 |
| ≤60 min | 1,863,118 | 1,205.0 | 415.07 | +36.3 |

The hypothesis said: these rows are label errors, the L2 loss chases unpredictable noise, and
if we drop them the model fits the signal better. **It turned out wrong**, and the harm grows
with the threshold. LIRF's own RMSE goes from 966 to 1,205.

The explanation: however wrong these rows are, they teach the model **that the tail exists**.
Once they are removed the model systematically underpredicts long taxi times, and under L2 the
cost of underpredicting a large value is very heavy. Because the validation set stays complete
(and the board is complete too), that cost is directly visible.

**Decision: no filter.** The outliers stay in training. This also says that clipping the target
or using a robust loss such as Huber would probably do harm too: anything that looks away from
the tail while being evaluated with RMSE falls into the same trap.

### Where the outliers come from: label error

| measurement | value |
|---|---|
| departures over 2 hours | 584 (0.028%) |
| of those, 480 | are at LIRF |
| maximum taxi-out | LIRF 131,167 s (36.4 hours), LSZH 87,341, LFPG 84,240 |
| variance share of the top 1% at LIRF | **88.1%** (LFPG 48.3%, EGLL 32.7%) |
| of those over 2 hours, with an NM match | 103 |
| of those, **plausible** according to NM (<2h) | **94.2%** (NM median 18 min, APDF median 2.3 hours) |

So on these rows the taxi time is not long, **the APDF block time is wrong**. A label error.
The PRC also filters out anything over 120 minutes in its official indicator (ATXOT p.13 step 1).

The consequence: the L2 loss chases unpredictable noise. **Next experiment (E03):** drop the
rows above the threshold from **training only**; validation stays complete, because the board
will be complete too. `train_baseline.py --max-train-sec <s>`.

## Paths closed before the data arrived (negative results)

| Path | Why we looked | Result | Document |
|-----|---------------|-------|-------|
| OPDI ADS-B parking position events | It would be an independent measurement of the blanked block time; open and documented data | **RULED OUT**: the events exist at only 2 of the 11 airports (LSZH, EDDF); ADS-B ground coverage at LTFM/LTAI is close to zero | `docs/opdi_negative_result.md` |
| The `D` (de-icing) reason code in the EUROCONTROL arrival ATFM delay | It would be a daily, direct measurement of de-icing | **RULED OUT**: the column is entirely empty; de-icing is not coded as an *arrival* ATFM reason | `docs/external_data.md` |
| Using the official EUROCONTROL taxi-out indicator as a **feature** | Reference and additional time per airport-month | **RULED OUT**: monthly, published with about a two-month lag, July 2026 not covered; and it would be circular anyway. **It is used for validation** | `docs/deicing_analysis.md` |

## The order to run in as soon as the data arrives

This order is not arbitrary: the ablation table of the 2025 winner (P06) was the presentation
of the contribution itself, and they produced that table **directly on the ranking set** (P04).
So our submissions have to be a **designed experiment**, not tuning attempts.

| Order | Experiment | Why this one first | Command |
|------|-------|---------------|-------|
| E00 | Data diagnosis | The questions that decide the architecture are answered here (Q02, D13, M14) | `scripts/probe_data.py` |
| E01 | (apt, stand, runway) mean | First valid submission plus an RMSE floor | the baseline inside `train_baseline.py` |
| E02 | Raw target vs ATXOT residual | The largest single gain in 2025 was a reparameterisation of this kind (P05) | `train_baseline.py` (runs both) |
| E03 | `AOBT_3_flt` present / absent | The real information value of the NM block time; it decides the whole architecture | `--no-aobt3` |
| E04 | Congestion features present / absent | The intellectual core of the work; the largest gain is expected here | by switching the feature group off |
| E05 | METAR present / absent, January in particular | LSZH/EHAM/EDDM/LTFM are in de-icing conditions 10-18% of January (W03) | by hiding the METAR file |
| E06 | Per-airport model vs global | LTFM/LTAI and LSZH do not behave the same | - |
| E07 | Seasonal specialisation (winter/summer) | The ranking set is two seasonal extremes | - |
| E08 | The `SCHED_TIME` handle present / absent | `MVT - SCHED = taxi + delay_sec`; its value depends on the distribution of the delay (A01-A03) | `run_ablation.py` (the `atfm` family) |
| E09 | Seed averaging (5 models) | The method of the 2024 winner: same data, same hyperparameters, different seed | `--seeds 5` |

## How to run the ablation

```bash
PY=D:/prc-taxiout-2026/.venv/Scripts/python.exe
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --rounds 1200 --seeds 3
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --causal      # for the paper
$PY scripts/run_ablation.py --data-dir D:/prc-taxiout-2026 --raw-target  # the E02 comparison
```

One run per family; the output is `docs/ablation_report.md` (not committed, regenerated on
every run). A negative Δ means removing that family **lowered** the RMSE, that is, the family
is doing harm, and that is a result worth reporting too.

**Warning.** Ablation numbers on the synthetic fixture are meaningless; they only show that the
pipes work. The fixture's own generation process makes some families artificially dominant (for
example, while `SCHED_TIME` had a fixed offset the `atfm` family was leaking the target one for
one; fixed on 2026-09-01).
