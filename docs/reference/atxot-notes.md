# The official EUROCONTROL taxi-out methodology: distilled notes

Source: `ATXOT_indicator_documentation_mar23.pdf`, Edition 01.00, 16-03-2023, EUROCONTROL EGSD/AIU/OPS.
Full text: `ATXOT_methodology.txt`. Page numbers are PDF pages.

This is **the official definition of the indicator of the organisation running the competition.**
The reference component of our model has to reproduce it one for one; our contribution comes from
closing the gaps the organisation writes down itself.

## The official definition

```
TaxiOut(f)            = ATOT(f) - AOBT(f)                       (p.13, step 3)
Reference(combo)      = P10( TaxiOut times in combo )           (p.14, step 4b)
Additional(f, combo)  = TaxiOut(f) - Reference(combo)           (p.13, step 5)
```

- **combo = (airport, departure STAND, departure RUNWAY).** No other variable.
- Reference sample: a **rolling 12 months**, selected by the take-off time in local time
  (p.13, step 2).
- **Validity condition:** the combination must hold **at least 10 flights** whose taxi-out time
  is at or below P10. If that fails, no reference is assigned to the combination and those
  flights are **dropped entirely** from the indicator (p.15).

## The official filters (p.13, step 1)

The following are taken out of the calculation:
- taxi-out time **> 120 minutes**
- rows with missing runway, stand or block time
- **helicopters**
- **flights that de-ice after AOBT, that is, during the taxi**

Note: the last item matters. The PRC discards de-icing flights from the indicator because they
break the "unimpeded" assumption. Our target, in contrast, is raw taxi-out, so **we cannot
discard the de-icing rows, we have to model them.** Most of the January 2026 error will be there.

## What the PRC DELIBERATELY leaves out: our contribution surface

| Factor | The PRC's rationale | Our position |
|--------|-------------------|-----------------|
| **Aircraft type / weight class** (p.11, §3.2) | it "may affect taxi speed", but adding it to the grouping shrinks the sample size | sample size is not a problem for a GBDT, it enters directly as a feature |
| **Taxi route** (p.15, §5) | there is no route in the data | we do not have it either; it is proxied by the stand-runway pair |
| **Taxi speed** (p.15, §5) | there is no speed in the data | partly proxied by aircraft type and operator |
| **Special events** (apron works and similar) | needs a dedicated sample | partly captured by the time trend and the airport x month interaction |
| **Queue** | already the quantity being measured (additional time = queue) | our target is the total time, so we model the queue **explicitly** |

The PRC also treats push-back time and the runway occupancy of the take-off roll as "systemic"
and buries them inside the reference (p.10, §3.1).

## The data source: critical for the target leakage question

Table 3 (p.17):

| Quantity | Main source | Alternative source |
|----------|-----------|-------------------|
| Actual take-off time (ATOT) | Airport (APDF) | ANSP **or Network Manager** |
| **Actual block time (AOBT)** | **Airport (APDF)** | **none** |
| Departure runway / stand | Airport (APDF) | none |

The inference: `BLOCK_TIME_UTC_mvt` in the competition data is the APDF AOBT, while `AOBT_3_flt`
is the block time of the **Network Manager M3 trajectory**. Two different measurements of the
same physical event, correlated but not identical. This is not leakage, it reflects the real
operational situation: NM keeps an estimate for every flight, while APDF exists only at airports
that share data.

**To measure (Q02):** in the 2025 data, what is the RMSE between `MVT_TIME_UTC_mvt - AOBT_3_flt`
and the actual `TAXITIME_SEC_mvt`? That number sets the difficulty floor of the competition.

## Quality warning

Timestamps may be at **HH:MM** precision only in some sources (p.15, §4); the seconds field is
not always meaningful. `probe_data.py` measures this per airport.
