# De-icing regime: independent validation of the METAR proxy

Produced by: `python scripts/analyse_deicing.py --raw-dir <path>`
**No competition data is used**, only two open sources: IEM METAR and the Taxi-Out
Additional Time indicator published by EUROCONTROL. Coverage: 180 airport-months.

## Why this comparison is meaningful

In its official indicator the PRC **discards flights that de-ice after AOBT**
(ATXOT p.13, step 1). The indicator's "share of flights without a valid reference" field
therefore carries mostly de-icing during the winter months. That is an **independent**
measurement of the `deicing_proxy` field we derive from METAR.

## Result: the proxy works

Over the whole data set the correlation is **r = 0.757** (de-icing proxy
against the share of flights without a reference). Within an airport, across months:

| apt | n_months | r_no_reference | r_additional | mean_deicing | mean_no_reference |
|---|---|---|---|---|---|
| LTFM | 18 | 0.982 | -0.061 | 0.020 | 0.010 |
| LSZH | 18 | 0.967 | -0.392 | 0.025 | 0.037 |
| EDDF | 18 | 0.943 | -0.156 | 0.010 | 0.015 |
| EDDM | 18 | 0.936 | -0.355 | 0.029 | 0.072 |
| LFPG | 18 | 0.873 | -0.116 | 0.005 | 0.020 |
| LEMD | 18 | 0.820 | -0.375 | 0.001 | 0.005 |
| LIRF | 18 | 0.470 | -0.009 | 0.000 | 0.003 |
| LEBL | 18 | 0.302 | 0.194 | 0.000 | 0.001 |
| EGLL | 18 | 0.275 | -0.109 | 0.001 | 0.000 |
| EHAM | 18 | 0.009 | 0.982 | 0.017 | 0.010 |

At the cold airports the correlation is 0.87 to 0.98; at the warm ones (LIRF, LEBL, EGLL)
there is almost no de-icing, so the correlation is noise and is expected to be low.

## The real finding: airports have different de-icing regimes

The correlation between the de-icing proxy and the **additional taxi-out time** is
-0.131 overall, that is, effectively none. But per airport the table splits
in two:

| apt | r_additional | winter_additional | summer_additional | winter_summer_diff |
|---|---|---|---|---|
| LTFM | -0.061 | 4.52 | 5.13 | -0.60 |
| LSZH | -0.392 | 3.12 | 3.51 | -0.39 |
| EDDF | -0.156 | 3.34 | 3.59 | -0.25 |
| EDDM | -0.355 | 2.81 | 3.66 | -0.86 |
| LFPG | -0.116 | 3.78 | 4.50 | -0.72 |
| LEMD | -0.375 | 3.23 | 4.03 | -0.81 |
| LIRF | -0.009 | 5.29 | 8.12 | -2.82 |
| LEBL | 0.194 | 3.11 | 4.18 | -1.07 |
| EGLL | -0.109 | 6.03 | 6.80 | -0.77 |
| EHAM | 0.982 | 4.40 | 2.94 | 1.46 |

**EHAM stands apart on its own.** At Amsterdam the share of flights without a reference
stays flat through the year (~1%), yet the additional taxi-out time rises clearly in
winter. At EDDM and LSZH it is the other way round: in winter a large share of flights
**drops out** of the indicator (31% at Munich in January 2026), while the additional time
does not rise.

One caveat worth recording: the additional taxi-out time is lower in winter than in summer
at **every** airport (between -0.25 and -2.82 min), because the summer traffic peak makes
the queue longer. EHAM's +1.46 min appears in spite of that baseline, so the background
strengthens the anomaly rather than weakening it.

Reading: **how much of the winter delay lands inside taxi-out** varies by airport. At
Amsterdam it lands inside and inflates the target; at Munich and Zurich the affected
flights are flagged and taken out of the official calculation.

This is not a firm causal claim: we have no de-icing records, only a weather condition
proxy and two fields of the official indicator. But two independent sources showing the
same seasonal structure, and the airports splitting into two distinct patterns, is enough
to fix **the first hypothesis to test** once the competition data arrives.

## What it means for us

We predict **raw taxi-out** and we cannot discard any row. So:

- At EHAM the weather effect shows up directly in the target and can be learned.
- At EDDM and LSZH the flights the official indicator **discards** are still in our data
  set, and as outliers they will dominate our January error. No published taxi-out model
  has had to predict those flights, because the standard methodology filters them out.
- The weather effect **varies by airport**; instead of one global weather coefficient we
  need an airport x weather interaction (or a per-airport model).

## Out of scope

Airports with **no data at all** in the official indicator: LTAI
Antalya is not in the EUROCONTROL performance scheme; we have no external validation source
for that airport, and its data quality may differ, which is worth keeping in mind.

Of the two ranking months, **July 2026 has not been published yet** (the series ends in
June 2026), so this indicator cannot be used as a feature. It is for validation only.
