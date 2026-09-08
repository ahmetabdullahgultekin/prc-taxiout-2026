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


## v5: the largest local gain in the project, and it lost on the board

| version | change | local | board |
|---|---|---:|---:|
| v4 | XGBoost + CatBoost depth 10, 92 features | - | **297.08** |
| v5 | the same, plus the surface and overlap families, 105 features | 347.74 | 300.51 |

The overlap family measured **+10.76 seconds** on the holdout, twice the noise floor and
the largest feature result this project has produced. On the board it lost 3.4.

This is the third time here that a locally significant change has failed to transfer,
and the first time the local effect was far too large to blame on measurement. Both
earlier cases sat inside the noise floor. This one did not.

### Ruling out the mechanical explanations first

Two things would have made this a bug rather than a finding, and neither holds.

**Arrival block times are present in the ranking set**, zero percent null, so the arrival
counters are computable there exactly as in training. Only departure block times are
blanked.

**The counter distributions match.** Training January 2025 against the whole ranking set:
`overtaken_by` mean 0.99 against 1.17, `arrivals_inside` 3.92 against 4.84, medians 0
and 3 against 0 and 4. Slightly busier in 2026, no structural break.

So the features are computed correctly on both sides. The failure is in transfer.

### Isolating it on the board

v4 and v5 differ in two ways, not one: the overlap family was added, and the surface
family started working. In v4 those six columns were constant zero, so they were
effectively absent, and the fix that made them real landed between the two submissions.

Three probes settled it. All XGBoost alone, 1000 rounds, the same cached features, so
the comparison is paired:

| submission | features | board |
|---|---:|---:|
| v6, everything | 111 | 317.10 |
| v7, without the surface family | 105 | **313.35** |
| v8, without the overlap family | 98 | **310.07** |

**Both families hurt.** The overlap family costs 7.03 seconds on the board and the
surface family 3.75, against local gains of 10.76 and 5.59. Same magnitudes, opposite
signs, for two families built independently a day apart.

### Why, and what it implies

Both families count what happened inside the flight's own taxi window, and that window
is `take-off minus the Network Manager off-block time`. The target is defined by a
different clock, the airport feed's block time. So every one of these features increases
how much the model leans on the network clock.

The gap between the two clocks is stable across the months of 2025, which was measured
early on: at Zurich it moves 17 seconds across the year, at Schiphol 22. Whether it is
the same in January and July 2026 cannot be measured, because that is the hidden target.
A model that leans harder on the network clock is more exposed to that gap moving, and
the holdout cannot see the exposure because the holdout is 2025.

That is a coherent account of a 10-second local gain becoming a 7-second board loss, and
it makes a prediction that can be tested: modelling the clock gap **explicitly**, rather
than letting it hide inside features that assume it is constant, should be worth more
than either family. That is the reparameterisation experiment.

### The rule this project now works under

Local validation and the board disagree in a way that is not about noise. The holdout is
2025 predicting 2025; the board is 2025 predicting 2026. Any feature whose usefulness
depends on a relationship holding across that year will measure well locally and can
still lose. **Features are proposed locally and decided on the board**, and the board is
cheap enough to use that way now: with the feature cache a probe takes six minutes
instead of ninety.

## The overlap counters: the largest feature result so far

Every congestion feature in this project counted movements in a fixed window around the
flight. Zhang et al. (Applied Sciences 14(21):9968, 2024) enumerate eight ways of
defining the overlap between one flight's taxi and another's, measure each at Shanghai
Pudong, and report that the choice of definition matters more than the choice of model:
their strongest counter reaches 0.81 against taxi time and the FAA-style definition,
which is the shape our windows approximate, reaches 0.17.

Measured here, same holdout, same run, XGBoost at 400 rounds:

| configuration | features | RMSE |
|---|---:|---:|
| everything | 105 | **347.74** |
| without the overlap family | 98 | 358.50 |
| without the fixed-window families | 69 | 361.02 |
| without either | 62 | 359.85 |

**The overlap family is worth 10.76 seconds.** For scale, the fixed-window congestion
families this project was designed around carried about three percent of the gain before
this, and the whole distance between our board score and the leader's on the day this was
measured was 47.

### The two are complementary, not substitutes

The window families cost 13.28 seconds when the overlap counters are present and 1.35
when they are absent. Whatever the fixed windows carry, the model can only use it once it
also knows who actually passed this aircraft. Both stay.

### What each column is worth

| removed | RMSE | cost |
|---|---:|---:|
| `arrivals_inside` | 360.12 | **+12.38** |
| `overtaken_rate` | 359.69 | **+11.95** |
| `overtaken_by` | 358.16 | +10.42 |
| `overtook` | 358.08 | +10.40 |
| `net_overtaking` | 356.94 | +9.20 |
| `arrivals_inside_rate` | 355.69 | +7.95 |
| `departure_share` | 355.28 | +7.54 |

Every one of the seven costs more on its own than the family costs as a whole, which
means they substitute heavily for one another: the model needs several views of the same
underlying quantity and does not much mind which. That is also why dropping any single
one looks catastrophic and dropping all seven does not.

`overtaken_rate` being second is the interesting part. It is `overtaken_by` divided by
the length of the taxi window, and the division is the point: a forty-minute taxi
contains more of everything than an eight-minute one, so the raw count is partly
arithmetic. The rate is what is left after that is taken out, and the model values it
more than the count it came from.

### A methodological correction

The paper rates six of the eight counters "low" and only two worth having. On this data
the departure counter it rates low, `overtook`, is worth 10.40 seconds, and the highest
single column is an arrival counter at 12.38. **Correlation with the target is not
marginal value inside a gradient boosted tree**, and reading the paper's ranking as a
build order would have left four counters unwritten. All eight shapes are built.

### Three bugs on the way, all of the same kind

The dominance counting is arithmetic over the movement stream, which does not fail
loudly. It returns a column of plausible integers.

1. **D3 derived instead of counted.** `D2 - D3 = rank(end) - rank(start)` holds only when
   no two flights share a timestamp. Off-block times are recorded to the minute and
   dozens of departures share an instant, so ties are the normal case, not an edge one.
2. **The same mistake again**, in the two counters assembled from D2, where the
   subtracted term needs to include equal take-off times and D2 excludes them. Adding one
   second to the integer timestamps turns the non-strict comparison into a strict one and
   lets the audited routine answer it.
3. **An unbounded window.** A flight whose off-block time is wrong by a day has a taxi
   window of a day, and the first run counted 21,167 arrivals inside one window against a
   median of 1.

Each was caught by a test comparing against a literal transcription of the definition on
inputs built to collide, not by inspection. That is now the standard for anything in this
family.

## v4: 297.08, and how a broken feature announced itself

| version | change | local | board |
|---|---|---:|---:|
| v1 | LightGBM, 800 rounds, 3 seeds | 378.80 | 331.23 |
| v2 | LightGBM, slower rate, wider trees | ~372 | 331.80 |
| v3 | XGBoost + CatBoost depth 8, 400 rounds | 351.69 | 306.41 |
| **v4** | **XGBoost + CatBoost depth 10, 1000 rounds, stand features** | - | **297.08** |

Another 9.33 seconds, third place, 22.3 behind the leader. Two changes went in together,
CatBoost depth 8 to 10 (measured at 9.4 seconds on the holdout) and the two stand
features, so the board number does not separate them. Depth is almost certainly most of
it.

### The bug the next experiment found

The surface features went in straight after v4 and were ablated. The result could not
be true:

| configuration | features | RMSE |
|---|---:|---:|
| everything | 98 | 359.44 |
| without the surface family | 92 | 361.20 |
| without `surface_apt_at_pushback` | 97 | **347.66** |
| without `surface_apt_at_takeoff` | 97 | **347.66** |
| without `surface_rwy_at_takeoff` | 97 | **346.75** |

Removing one column improved the model by ten seconds, six times over, while removing all
six made it worse. And two different columns gave a score identical to two decimal
places, which cannot happen unless they hold the same values.

They did. Both were zero for every row in the training set: mean 0.000, standard
deviation 0.000, maximum 0.000.

**The cause.** The surface count is the difference of two running totals, aircraft that
have pushed back and aircraft that have taken off. The Network Manager has no off-block
time for 1.5 percent of departures. Those flights entered the take-off total and not the
push-back total, so the difference drifted downward by the number of unmatched flights
seen so far. At Frankfurt over a year that reached about 46, against a real queue of
five to twenty, and the clip at zero did the rest.

Fixed by filtering to flights present in both totals. The column now reads: mean 10.08
aircraft on the airport surface at push-back, median 9, maximum 44; per runway 6.70,
median 6. Physically sensible for a large European airport, and the airport count is now
never below the runway count, which it had no way of satisfying before.

### What it says about the tests

Ten unit tests passed throughout, including hand-counted queue scenarios. They could not
have caught this: every fixture row had a network match, so the two totals ran over the
same flights by construction. There is now a case with an unmatched flight, and it fails
against the old code.

That is the third time in this project that arithmetic over the movement stream has
returned a plausible wrong number rather than an error, after the wrong movement airport
and the unsigned counter wrap. The pattern is specific enough to name: **a feature built
by counting does not fail, it goes quiet.** Worth checking every such column for being
constant before trusting an ablation of it.

## Data quality audit: the cleaning that is not needed

The BTK Datathon playbook names lowercase-and-trim on the text categories as the largest
easy win, because there train and test arrived in different formats and a raw category
became noise on the test side. That check had never been run here, and this competition
lives in its categorical fields.

It found nothing, and that is the result.

| field | distinct values | after strip and uppercase |
|---|---:|---:|
| STAND_mvt | 1,899 | 1,899 |
| AIRCRAFT_TYPE_mvt | 269 | 269 |
| RUNWAY_mvt | 53 | 53 |
| the other six | unchanged | unchanged |

Not one case or whitespace variant in nine fields. This is a machine-generated
operational feed, not a form somebody typed into, and the cleaning playbook written for
human-entered data does not transfer. Worth knowing precisely so that no more time goes
into it.

Cold start is a non-issue too. Twenty stands in the ranking set were never seen in
training, covering 0.106 percent of its rows; three aircraft types, 0.005 percent; zero
runways and zero airports. Rare values are similarly thin: 137 stands appear exactly once
in training, together 0.007 percent of the rows.

### Where the dirt actually is

| condition | rows | share |
|---|---:|---:|
| taxi-out zero or negative | 388 | 0.019% |
| taxi-out above 2 hours | 584 | 0.028% |
| taxi-out above 6 hours | 69 | 0.003% |
| network off-block after take-off | 1,012 | 0.049% |

Of the 103 departures above two hours that the Network Manager also recorded, **96
(93.2%) have a plausible network time**. So the taxi-out is not really twelve hours; the
airport feed's block time is wrong for that flight.

### Why they are being left alone

The obvious move is to drop or correct those rows, and the evidence says not to.
Dropping them was measured (E03) and cost 24 and 36 seconds at two thresholds, both far
outside the noise floor, with the damage growing as the threshold rose.

The reason is what RMSE optimises. Under squared loss the best prediction is the
conditional mean, and that mean includes the small probability of a very large value.
Removing those rows removes that mass and shifts every prediction down. Correcting the
labels shifts them down the same way. The clock errors are unpredictable, but their
*frequency* is not, and the metric pays for carrying it.

This is worth stating plainly because it runs against the instinct that cleaner training
data is better. Here it is measurably worse.

## v3: the learner change transferred to the board

| version | change | local | board |
|---|---|---:|---:|
| v1 | LightGBM, lr 0.05, 127 leaves, 800 rounds, 3 seeds | 378.80 | 331.23 |
| v2 | LightGBM, lr 0.02, 255 leaves, 380 rounds, 5 seeds | ~372 | 331.80 |
| **v3** | **XGBoost + CatBoost, 400 rounds, 1 seed** | **351.69** | **306.41** |

A gain of **24.82 seconds** on the board against a locally measured 27.30. The local
measurement predicted the board result to within 2.5 seconds, and this is the first
change in this project for which that is true.

That is worth being precise about, because the opposite has been recorded here twice.
v2 was locally significant and did not transfer. The difference is size: v2 moved the
score by a few seconds, inside the region where a holdout dominated by a few hundred
rows cannot tell one model from another, while the learner change is five times the
noise floor. Small local differences still do not carry. Large structural ones do.

The board position moves from fourth to second, and the gap to the leader from 32.19
seconds to 7.37.

### What this cost and what it did not

Nothing was added to the model. The features are identical, 90 of them, the split is
identical, the target is identical. v3 uses **fewer** rounds than v1 (400 against 800)
and **one** seed against three. The entire gain came from which library fits the trees.

### A silent failure on the way

The first upload of v3 never happened. `make_submission.py` printed

    mc cp <file> opensky/prc-2026-<team>/

and the configured alias is `prc`, not `opensky`. `mc` does not treat an unknown alias
as an error; it reads the argument as a relative local path, creates the directory, and
copies the file into it. It reported success. The only visible symptom was the transfer
rate, 122 MiB/s for what should have been an upload, and no result file ever appeared.

`scripts/submit.py` now performs the upload: it refuses to run unless the alias resolves
to an https endpoint, checks the object is listed in the remote bucket afterwards, and
polls for the score. A control that reports success without checking anything is worse
than no control, and this is the second one found in this project.

## The learner itself was the largest lever found so far

Every result up to this point was measured with LightGBM, and the choice was never
tested. It should have been. Same 92 features, same split, same 400 rounds, one seed:

| learner | holdout RMSE | against LightGBM | fit time |
|---|---:|---:|---:|
| LightGBM, categorical splits | 378.99 | - | 124 s |
| XGBoost, categoricals as integer codes | 357.80 | **-21.19** | 149 s |
| CatBoost, ordered target statistics | 353.59 | **-25.40** | 1074 s |
| XGBoost + CatBoost, equal weight | **351.69** | **-27.30** | - |
| all three, equal weight | 357.49 | -21.50 | - |
| best searched weighting (0.0 / 0.4 / 0.6) | 351.42 | -27.57 | - |

The paired noise floor on this holdout is about 5 seconds, so a 27 second gap is not
close to a judgement call. For comparison, the entire congestion feature family, which
this project was designed around and which took the most work, carries about 3 percent
of the gain.

**Adding LightGBM to the blend makes it worse** (357.49 against 351.69 for the pair). It
is not contributing a different view of the data, it is contributing error.

### Why

The reading is that LightGBM's categorical splitting overfits the high cardinality
fields, and there are several: 1,899 stands, a hashed aircraft operator, 11 aircraft
types. LightGBM sorts categories by gradient statistics and splits the sorted order,
which on a category seen a handful of times fits noise.

The evidence for that reading is XGBoost. It applies **no categorical handling at all**,
receiving the same integer codes as bare numbers, and still beats LightGBM by 21
seconds. A learner that throws the categorical structure away should not beat one that
models it, unless the modelling is doing harm.

The prediction that follows is testable: LightGBM with the categorical declaration
removed should close most of the gap to XGBoost. That is what `lightgbm-nocat` in
`taxiout.models` is for, and it is the next thing to measure.

### What was changed

The learner is no longer hardcoded. `taxiout.models` holds a `Regressor` port with one
adapter per library, and `train_predict` takes a `learners` tuple. The port is defined at
the frame level rather than the matrix level on purpose: each library encodes the
categoricals its own way, and forcing a single encoding on all three would have assumed
away the thing being measured.

The equal-weight blend is used rather than the searched weighting. The search is fitted
on the same rows the score is read from, and the difference between them is 0.27
seconds, inside the noise.

## v2: a local gain that did not transfer

| submission | configuration | local holdout | **board** |
|---|---|---:|---:|
| v1 | lr 0.05, 127 leaves, 800 rounds, 3 seeds | 378.80 | **331.23** |
| v2 | lr 0.02, 255 leaves, 380 rounds, 5 seeds | ~372 | **331.80** |

The change was significant on the local paired test in both seed pairings, at 5.4 and
3.4 seconds against a noise floor near 5. On the board it moved 0.57 the wrong way.

So local significance is not sufficient. The holdout is January and July 2025 and the
board is January and July 2026, and since the score is set by a few hundred extreme rows
in each, the two sets do not have to agree about which model is better. A paired test
tells you a difference is real *on those rows*; it says nothing about whether the same
rows exist next year.

The practical rule, which is now measured rather than assumed: **the local holdout picks
what is worth submitting, and only the board decides.** Ranking uses each team's best
score, so a submission that does not improve costs nothing but the run.

v1 stays our best at 331.23.

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

## The night of 2026-09-06, on the holdout that mirrors the new scored set

Everything below is 400 rounds of XGBoost on 1,740,628 training rows, scored on the
344,419-row holdout, which is January and July 2025 at all ten airports. The board's own
set is 344,841 rows, so the two are the same shape for the first time in this project.
They also agree in direction and size on the one thing tested on both: capping
predictions at 7,200 s costs 49 s here and 78 s there.

| what | RMSE | against the plain model |
|---|---:|---:|
| plain model | 474.91 | |
| one model per airport | 484.10 | **+9.19, it loses** |
| the best global tail transform | 472.35 | -2.56, inside noise |
| a model per network-match segment | 417.24 | -57.67 |
| **the mixture, weight from a classifier** | **393.99** | **-80.92** |
| the mixture, classifier weight scaled by 1.5 | 375.58 | -99.33 |
| the mixture, classifier weight scaled by 2.0 | 368.52 | -106.39 |
| **the mixture, weight fitted out of fold** | **362.38** | **-112.53, and no tuned parameter** |
| an oracle told which rows are substituted | 413.19 | -61.72 |

The oracle line is worth reading twice. Knowing exactly which rows have a substituted
block time, and reading the schedule off for those and only those, is *worse* than the
fitted-weight mixture. The exact identity is not the whole population: a flight whose
taxi lands within a few minutes of its schedule offset is not a match under a ten second
rule and the offset is still the better prediction for it. Fitting the weight finds that;
classifying the identity cannot.

Widening the tolerance does not find it either, which is the control for that reading:

| tolerance | share | scale 1.0 | scale 1.5 | scale 2.0 |
|---:|---:|---:|---:|---:|
| 10 s | 4.86% | **393.99** | **375.58** | **368.52** |
| 30 s | 5.52% | 395.41 | 380.04 | 374.04 |
| 60 s | 9.72% | 393.57 | 376.83 | 373.37 |
| 120 s | 17.34% | 395.34 | 380.55 | 377.66 |

### Closed, do not revisit

* **One model per airport.** It loses overall and loses at Rome specifically, 1377.7 to
  1432.7, which is the airport it was meant to serve.
* **Capping or stretching the tail.** Capping loses on both instruments. Stretching gains
  0.5 s at best, inside the paired noise floor of about 5 s.
* **The stand as an upper bound.** An aircraft cannot go off-block before it went
  on-block, so the last arrival on the same stand should bound the taxi. It does not:
  violated on 10% of all rows and on 70% of the rows above two hours, because the last
  arrival on a stand is frequently a different aircraft.
* **A year-on-year correction from arrival taxi-in.** Pooled correlation -0.11 over the
  126 airport-months of 2025, and the sign flips per airport. It would have cut every
  Amsterdam departure in July by 140 s at the one airport whose departures move the other
  way.

### The day regime does not earn its place

Measured on Hetzner under the fitted-weight mixture, which is what will ship, on a cache
built with the family present:

| | features | RMSE |
|---|---:|---:|
| with the day regime | 97 | 358.89 |
| without it | 92 | **358.11** |

Slightly worse with it, which is inside the noise floor and therefore not evidence of
harm, but it is certainly not evidence of value. The family stays in the code and out of
the submissions, which is what an ablatable family is for.

One thing that reading cost, worth recording: these two numbers are 358 while the same
configuration measured 362.38 on the Windows machine. The same code, the same cache
contents, a different core count, and XGBoost sums in a different order. Four seconds is
larger than it sounds because a single row above two hours moves the RMSE by several
seconds on its own. **Compare within a machine, never across one.**

## The night of 2026-09-07: what the board said, and what the seeds said

The board settled the mixture. Same features, same rounds, same everything except the
model:

| submission | model | board RMSE |
|---|---|---:|
| v12 | plain XGBoost | 411.23 |
| v19 | fitted-weight mixture | **334.01** |
| v21 | the same, weight target clipped to (-0.25, 1.25) | **318.16** |
| v22 | v21 averaged with a segmented-inner mixture | **315.94** |

Then the overnight run measured the same configuration three times with three seeds:

| | RMSE |
|---|---:|
| wide, seed 1 | 353.26 |
| wide, seed 2 | 348.38 |
| wide, seed 3 | 358.00 |
| the three averaged | **347.82** |

**A ten second spread between seeds.** That is much larger than the paired bootstrap noise
floor of about 5 s quoted earlier in this project, because the metric is dominated by a
few hundred rows and a different seed puts them in different leaves. It means several
comparisons made on single runs were never conclusive, and they are re-read here honestly:

| comparison | difference | verdict now |
|---|---:|---|
| mixture against plain | 112 s | real, and the board confirmed it at 77 s |
| fitted weight against a classifier weight | 31 s | real |
| the wide weight clip | 6.7 s | **was inside seed noise locally**, but the board confirmed it at 15.8 s |
| the segmented inner learner | 1.7 s | inside noise; kept only for blending diversity |
| the day regime family | 0.8 s | inside noise; still no reason to ship it |

The lesson is not that the small results were wrong. It is that they were not evidence
either way, and two of them were only settled by spending a submission.

### Rounds and the inner learner

| | RMSE |
|---|---:|
| wide, 400 rounds | 353.26 |
| wide, 800 rounds | 359.98 |
| wide, 1500 rounds | 355.39 |
| wide over a segmented inner, 400 | 348.45 |
| **wide with a CatBoost inner** | 359.44 (against 357.55 for XGBoost in the same run) |

More rounds do not help inside the mixture, which is worth knowing: the ordinary learner
is fitted on the rows the mixture does not reach, and those are the easy ones. CatBoost is
not better either, reversing what it did as a plain model, but it blends: 0.6 XGBoost plus
0.4 CatBoost gives 353.77 in the run where XGBoost alone gave 357.55. It costs thirteen
times as long, which is affordable only because a second machine is idle.

### What averages best

| | RMSE |
|---|---:|
| best single (seed 2) | 348.38 |
| seed 1 averaged with the segmented inner | **344.84** |
| everything averaged | 346.20 |

Given the seed spread, the gap between 344.84 and 346.20 is not a result. Averaging more
things is the reliable move, not picking the best pair.

### A second identity as a second candidate: refuted, and reverted

The network off-block time matches the target exactly on 8.25 percent of rows against the
schedule's 4.86, so declaring it as a second candidate in the mixture looked free. It is
not, and a test caught it before a submission did.

Declaring a candidate does two things: it earns a weight, and it removes its rows from the
ordinary learner's training set, because a learner fitted on rows whose target is a column
learns to reproduce a coincidence. The second effect is the larger one here. On a
synthetic population with the real proportions, the two-candidate mixture was more than
fifteen percent worse than the one-candidate mixture overall, and worse even on the rows
that follow the second candidate.

The asymmetry between the two identities explains it. The schedule identity covers 333 of
the 435 training rows above two hours, so its rows are ones the ordinary learner cannot
serve anyway and losing them costs nothing. The network identity covers none of them: its
rows are ordinary flights that the learner predicts perfectly well, and taking eight
percent of the training set away to gain an exact answer on them is a bad trade.

Reverted. The code is back to a single candidate, which is what the board has scored.

### The mirror identity, and why it does not matter

If the feed writes the scheduled time into the off-block field when it has no
measurement, it might also write the take-off time, which would give a taxi of exactly
zero. Over all 2,085,047 departures of 2025, 1,117 have a taxi at or below sixty seconds,
19 of them exactly zero and 369 negative, and they concentrate at Zurich: 674 of the
1,117, against 4 at Frankfurt.

So the quirk is real and it is a Zurich quirk. It is also worth nothing. Predicting all of
them at the global mean instead of their truth costs 1.11e9 of squared error against about
3.34e11 for a model scoring 400, which is a third of one percent, or under a second of
RMSE. Closed.

## Blending is not free: what the board said on 2026-09-08

| submission | model | board |
|---|---|---:|
| v21 | wide mixture, one seed | 318.16 |
| v22 | v21 averaged with a narrow-clip segmented mixture | **315.94** |
| v25 | wide mixture, two seeds averaged | **310.55** |
| v26 | v25 averaged with the same narrow-clip segmented mixture | 314.71 |

The same partner, averaged into two different bases, gained 2.2 s on one and lost 4.2 on
the other. The difference is what the base already was. A single seed carries about five
seconds of seed noise, and averaging anything half-decent into it removes some of that,
which is most of what v22's gain was. Two seeds have already had that removed, so all the
partner brings is its own inferiority: it was built with the weight target clipped to the
unit interval, which the board has separately measured as 15.8 s worse.

A third submission tested the obvious objection: perhaps v20 lost only because it was
built with the narrower weight clip, and a partner of comparable quality would still gain.

| submission | model | board |
|---|---|---:|
| v25 | wide mixture, two seeds averaged | **310.55** |
| v28 | v25 averaged with a wide-clip segmented mixture | 315.56 |

It lost by 5.0 s. So the partner's quality was not the issue and the rule is simpler and
harsher than the one usually quoted about ensembles: **on this board, averaging helps a
noisy base and costs a denoised one, whatever the partner.** Two board measurements now
say so, against a local holdout that said the opposite. The local gain, 353.26 for a
single seed against 344.84 blended, was seed noise being averaged away and nothing else;
seed averaging captures all of it and more cheaply.

Seed averaging itself transferred almost exactly: 6 s locally, 5.4 s on the board.

Two of the day's three submissions went on blends that lost. The information was worth
having and it was not available any other way, since the holdout had said the opposite,
but the honest accounting is that the day's score came from one submission.

## Where the error lives after the mixture

Three seeds of the shipped model, averaged, scoring 347.82 on the holdout. The map has
changed completely from the one that motivated the mixture.

| | rows | RMSE | share of the squared error |
|---|---:|---:|---:|
| the feed substituted the schedule | 15,531 | 515 | **9.9%** |
| everything else | 328,888 | 338 | 90.1% |
| no Network Manager match | 5,373 | 1,998 | **51.5%** |
| a match | 339,046 | 244 | 48.5% |
| truth below one hour | 343,438 | 249 | **51.1%** |
| truth above one hour | 981 | 4,556 | 48.9% |
| truth above six hours | **24** | 25,434 | **37.3%** |

Before the mixture the substituted rows were the problem and the unmatched rows carried
66.9 percent. The substituted rows are now 9.9 percent, which is what the mixture was
built to do, and the remainder has split almost exactly in half: 51 percent of the error
is spread across 343,438 ordinary flights at an RMSE of 249, and 49 percent sits in about
a thousand long ones.

Two consequences for what to do next.

**The ordinary half is now worth tuning.** It is half the metric, it is smooth, and the
learner behind it has had the same settings since the first week: learning rate 0.05,
depth 9, subsample 0.8, colsample 0.8, 127 bins, chosen as a first guess and never
revisited because every question since was about structure. Structure is exhausted.

**The long rows are under-predicted, not over-predicted.** Above six hours the median
truth is 45,580 seconds against a median prediction of 37,970: sixteen percent short.
That is the opposite of the failure the cap experiment was testing for, and it says the
mixture is still shrinking the largest cases toward the middle.

## The tail is not a board lever, and the holdout said the opposite three times

The map above named two candidates: a slower learner for the smooth ordinary half, and a
correction for the under-predicted giants. Both were built, validated on the holdout, and
put on the board. Both lost, and the board disagreed with the holdout in the same
direction each time.

| version | change from the champion (v25, 310.55) | holdout | board |
|---|---|---:|---:|
| v29 | slower rate, 800 rounds, inside the mixture (`mixture-wide-slow-xgboost`) | 343.51 (−9.6) | **327.62 (+17.1)** |
| v30 | v25 with the extreme tail pushed to the schedule offset | 335.16 (−18.1) | **470.18 (+159.6)** |

**v29, the slower rate.** On the holdout the slower rate over 800 rounds took the mixture
from 353.07 to 343.51, well past the ~5 s seed floor. On the board it went the other way,
from 310.55 to 327.62. The holdout is 2025 January and July; the board is 2026. A slower
fit suited one and not the other, which is the whole reason the round count and rate were
never made defaults on a holdout measurement.

**v30, the tail push.** The 24 giants are under-predicted, so the obvious move is to push
them up. `tail_sweep` had already refuted a blanket multiplier, so the push was gated on
the model's *own* extreme predictions and aimed at the schedule offset, which for a real
monster is very nearly its truth: `pred → offset where pred > 6 h and offset > pred`. On
the holdout it gained 18 seconds, touching 13 rows of which all 13 were monsters — 96 %
precision at that gate. On the ranking set the identical transform touched 29 rows and
cost **160 seconds**. The precision did not survive the year: the rows the mixture
predicts above six hours on the 2026 set are dominated by ordinary flights with a large
schedule offset that the fitted weight had *correctly* discounted, and forcing them onto
the offset is exactly the catastrophe the mixture was built to avoid. The mixture's own
weight is already the right answer for these rows; overriding it is not.

Neither hurt the standing — teams rank by their best score (F04) and v25 remains it — but
the day bought three answers from the board and two of them said the same thing the log
has said since v1: **the holdout orders levers, the board decides them, and a tuned RMSE
gain on 2025 is not a modelling result until 2026 confirms it.** The tail is where the
metric lives, but it is not somewhere a post-hoc rule can reach.

## Is there a second provenance rule? No.

The schedule substitution explains 430 of the 584 training departures above two hours.
The remaining **154** were searched for a second identity of the same kind — a timestamp
the feed wrote into the block field — because one clean rule is worth more than any amount
of tail tuning (it transfers; tuning does not). The block time on those rows is the
substituted value directly, so the question is only what it equals.

| candidate for the written block time | matches within 60 s (of 154) |
|---|---:|
| `SCHED_TIME` (the known rule, by construction excluded) | 2 |
| `EOBT_1` | 6 |
| `IOBT` | 3 |
| `LOBT` | 3 |
| `AOBT_3`, `ARVT_1`, `ARVT_3` | 0 |
| `SCHED_TIME` shifted a whole number of days | 1 |
| a *different* movement at the same stand (previous occupant) | 7 (5 %) vs 3 % on ordinary rows |

Nothing clusters. `BLOCK − SCHED` on the 154 is spread from −7.7 h to +1.8 h across the
5th–95th percentiles with no spike, which is the signature of assorted label errors rather
than one mechanism — consistent with the note that the NM off-block time is plausible on
94 % of matched cases, i.e. the block field is wrong in a different way each time. The
cross-row joins that would have been the strongest evidence are not constructible on this
data: there is no registration column, so "the same aircraft's previous leg" cannot be
formed, and `TOBT`/`CTOT` are not present either. The one clean provenance rule is the one
already in the model.
