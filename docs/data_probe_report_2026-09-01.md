# Data Diagnosis Report

Source: `D:\prc-taxiout-2026\00_raw` - training files: 12

## 1. Schema comparison (D05 / D06)

- training column count: **30**, ranking: **30**
- columns absent from ranking: none
- columns present only in ranking: none
- submitting.parquet columns: ['MVT_ID_mvt', 'TAXITIME_SEC_mvt']

**Fill rate on the DEP rows of the ranking set** (0.0 = blanked out entirely):

- DEP row count: **215,876**
- `FLIGHT_ID_mvt`: 0.9852
- `MVT_TIME_UTC_mvt`: 1.0000
- `BLOCK_TIME_UTC_mvt`: 0.0000  <-- BLANKED
- `SCHED_TIME_UTC_mvt`: 1.0000
- `RUNWAY_mvt`: 1.0000
- `STAND_mvt`: 1.0000
- `TAXITIME_SEC_mvt`: 0.0000  <-- BLANKED
- `LOBT_flt`: 0.9852
- `IOBT_flt`: 0.9852
- `EOBT_1_flt`: 0.9852
- `ARVT_1_flt`: 0.9852
- `AOBT_3_flt`: 0.9852  <-- **FILLED, critical finding**
- `ARVT_3_flt`: 0.9852

## 2. Taxi-out identity: MVT_TIME - BLOCK_TIME == TAXITIME ? (D13)

- DEP rows: **2,085,047**, rows with all three filled: **2,085,047**
- share where the identity holds within 1 s: **1.0000**
- largest absolute deviation: **0 s**

Reading: a share of 1.0 means TAXITIME is derived and the timestamps are internally consistent; anything below 1.0 means the difference is an independent measurement error, and it sets the noise floor for the queue features.

## 3. Timestamp precision (M14)

| ADEP_mvt | n | mvt_second_is_zero | block_second_is_zero |
|---|---|---|---|
| EDDF | 230,141 | 0.0177 | 0.0169 |
| EDDM | 167,334 | 0.0831 | 0.0834 |
| EGLL | 239,546 | 0.0828 | 0.0838 |
| EHAM | 247,951 | 0.0173 | 0.0169 |
| LEBL | 179,705 | 0.0166 | 0.0830 |
| LEMD | 212,242 | 0.0164 | 0.0837 |
| LFPG | 239,552 | 0.0832 | 0.0828 |
| LIRF | 160,704 | 0.0838 | 0.0835 |
| LSZH | 134,907 | 0.0168 | 0.0198 |
| LTFM | 272,965 | 0.0833 | 0.0830 |

An airport whose share is near 1.0 has data at **HH:MM** precision: taxi-out there carries +-60 s of floor noise, so the reachable RMSE lower bound for that airport is higher.

## 4. Network Manager match rate (D10)

**training 2025**

| ADEP_mvt | n | flight_id_filled | aobt3_filled |
|---|---|---|---|
| EDDF | 230,141 | 0.9915 | 0.9915 |
| EDDM | 167,334 | 0.9940 | 0.9940 |
| EGLL | 239,546 | 0.9941 | 0.9941 |
| EHAM | 247,951 | 0.9835 | 0.9835 |
| LEBL | 179,705 | 0.9897 | 0.9896 |
| LEMD | 212,242 | 0.9956 | 0.9955 |
| LFPG | 239,552 | 0.9843 | 0.9842 |
| LIRF | 160,704 | 0.9907 | 0.9907 |
| LSZH | 134,907 | 0.9830 | 0.9830 |
| LTFM | 272,965 | 0.9867 | 0.9866 |

**ranking 2026**

| ADEP_mvt | n | flight_id_filled | aobt3_filled |
|---|---|---|---|
| EDDF | 36,317 | 0.9884 | 0.9884 |
| EDDM | 10,953 | 0.9891 | 0.9891 |
| EGLL | 39,840 | 0.9938 | 0.9938 |
| EHAM | 38,182 | 0.9684 | 0.9684 |
| LEBL | 12,201 | 0.9937 | 0.9937 |
| LEMD | 16,802 | 0.9963 | 0.9963 |
| LFPG | 18,129 | 0.9821 | 0.9821 |
| LIRF | 11,061 | 0.9903 | 0.9903 |
| LSZH | 9,995 | 0.9700 | 0.9700 |
| LTFM | 22,396 | 0.9852 | 0.9851 |


## 5. CRITICAL: how good a predictor is AOBT_3_flt? (Q02)

Naive predictor: `taxi_out = MVT_TIME_UTC_mvt - AOBT_3_flt`

| n | rmse | mae | bias | median_abs_error |
|---|---|---|---|---|
| 2,062,577 | 384.9 | 238.1 | 17.0 | 175.0 |

| ADEP_mvt | n | rmse | bias |
|---|---|---|---|
| EDDF | 228,185 | 255.1 | 53.2 |
| LSZH | 132,616 | 268.4 | -59.4 |
| LEMD | 211,295 | 276.4 | -33.9 |
| LEBL | 177,843 | 311.4 | -67.5 |
| EHAM | 243,867 | 329.6 | 151.7 |
| EDDM | 166,324 | 348.9 | -81.8 |
| LFPG | 235,779 | 379.5 | -35.4 |
| EGLL | 238,132 | 418.5 | 22.7 |
| LTFM | 269,320 | 530.6 | 236.4 |
| LIRF | 159,216 | 557.4 | -214.2 |

**How to read this.** If this RMSE is low (say <60 s) the competition is mostly a 'reconcile the NM block time with the APDF block time and fill in the unmatched rows' problem, and the whole architecture follows from that. If it is high (say >200 s) then AOBT_3 is only a strong feature, not the solution. The coverage share (n / total DEP) matters at least as much as the RMSE: the rows it does not cover need a separate model.

## 6. Target distribution

| ADEP_mvt | n | mean | std | p10 | p50 | p99 | over_120min_share | negative_share |
|---|---|---|---|---|---|---|---|---|
| EDDF | 230,141 | 863.5 | 329.8 | 478.0 | 837.0 | 1,819.0 | 0.0000 | 0.0000 |
| EDDM | 167,334 | 811.9 | 301.8 | 533.0 | 774.0 | 1,921.0 | 0.0000 | 0.0000 |
| EGLL | 239,546 | 1,364.2 | 421.8 | 909.0 | 1,319.0 | 2,701.0 | 0.0002 | 0.0000 |
| EHAM | 247,951 | 784.6 | 318.5 | 458.0 | 742.0 | 1,775.0 | 0.0000 | 0.0000 |
| LEBL | 179,705 | 956.5 | 330.9 | 595.0 | 906.0 | 1,962.0 | 0.0000 | 0.0000 |
| LEMD | 212,242 | 1,014.7 | 312.5 | 656.0 | 985.0 | 1,932.0 | 0.0000 | 0.0000 |
| LFPG | 239,552 | 1,019.5 | 453.0 | 655.0 | 954.0 | 2,409.0 | 0.0002 | 0.0003 |
| LIRF | 160,704 | 1,194.6 | 1,332.0 | 670.0 | 1,025.0 | 4,019.0 | 0.0030 | 0.0000 |
| LSZH | 134,907 | 740.5 | 385.4 | 400.0 | 711.0 | 1,707.0 | 0.0000 | 0.0022 |
| LTFM | 272,965 | 1,053.0 | 427.6 | 662.0 | 963.0 | 2,587.0 | 0.0001 | 0.0000 |

`over_120min_share` is the share above the official PRC filter (M08); `negative_share` marks a data error. Both are the tail that RMSE punishes hardest: they call for a **modelling** decision, not clipping.

**By month (watch the January and July rows: they are the two ranking months):**

| month_num | n | mean | std |
|---|---|---|---|
| 1 | 153,706 | 995.3 | 604.8 |
| 2 | 143,732 | 1,002.4 | 628.3 |
| 3 | 164,449 | 972.0 | 461.7 |
| 4 | 175,288 | 971.4 | 436.0 |
| 5 | 185,202 | 986.6 | 469.4 |
| 6 | 183,142 | 973.2 | 554.9 |
| 7 | 190,713 | 1,025.7 | 745.0 |
| 8 | 191,182 | 993.8 | 533.8 |
| 9 | 183,950 | 989.8 | 560.3 |
| 10 | 185,674 | 992.0 | 437.1 |
| 11 | 162,332 | 997.0 | 532.0 |
| 12 | 165,677 | 995.0 | 514.7 |

## 7. Baselines and cold start

| n_validation | combo_coverage | rmse_global_mean | rmse_airport_mean | rmse_combo_mean |
|---|---|---|---|---|
| 344,419 | 0.9986 | 686.6 | 660.0 | 628.4 |

`rmse_combo_mean` is the expected level of our first real submission. Everything we put on top of it is the queue / congestion / weather component.

**Share of ranking set combinations never seen in training (cold start risk):**

| n | seen_combo_share | stand_null_share | runway_null_share |
|---|---|---|---|
| 215,876 | 0.9946 | 0.0000 | 0.0000 |

## 8. Second handle: scheduled block time (SCHED_TIME)

Identity: `MVT_TIME - SCHED_TIME = taxi_out + departure_delay`.
`SCHED_TIME_UTC_mvt` is not blanked out in the ranking set (D05), so this is a
legitimate feature too. What it is worth depends entirely on how predictable the
**departure delay** is: a narrow delay_sec distribution nearly hands us the target,
a wide one leaves us only an upper bound.

**Departure delay (actual block - scheduled block), seconds:**

| n | mean | std | p10 | p50 | p90 | early_share |
|---|---|---|---|---|---|---|
| 2,085,047 | 901.3 | 2,238.0 | -242.0 | 415.0 | 2,396.0 | 0.2421 |

**The `MVT - SCHED` naive predictor (it treats the delay as zero):**

| rmse | bias |
|---|---|
| 2,412.7 | 901.3 |

Compare with the AOBT_3 naive predictor in section 5. Which of the two handles is
narrower, and how much is left once both are used, is the architecture decision. The
standard deviation of the delay may be **most of the irreducible uncertainty** in
this problem.
