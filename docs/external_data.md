# External Data Sets

**Prize eligibility condition:** every additional data set used must be openly accessible,
openly licensed and documented (dc2026/eligibility.html). This file is that documentation.
When adding a data source, **fill this in first.**

| Source | Used for | Access URL | Licence | Date added |
|--------|---------|------------|--------|-----------------|
| EUROCONTROL ATXOT methodology document | The official reference taxi-out definition (P10 / stand-runway) | https://ansperformance.eu/library/ATXOT_indicator_documentation_mar23.pdf | EUROCONTROL public publication | 2026-09-01 |
| Iowa Environmental Mesonet (IEM) ASOS/METAR archive | Temperature, dew point, visibility, wind, precipitation, present weather codes; **the de-icing proxy** | https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py | **Public domain** | 2026-09-01 |
| OurAirports (airports.csv, runways.csv) | Airport coordinates (departure bearing / departure-fix proxy), runway counts and lengths | https://davidmegginson.github.io/ourairports-data/ | **Public domain** | 2026-09-01 |
| EUROCONTROL Taxi-Out Additional Time indicator | **Validation only**: an independent check on our ATXOT reimplementation and on the METAR de-icing proxy | https://www.eurocontrol.int/performance/data/download/xls/Taxi-Out_Additional_Time.xlsx | EUROCONTROL public publication | 2026-09-01 |
| EUROCONTROL ATFM Slot Adherence (daily) | How many of the day's departures were under an ATFM slot, and slot adherence; a direct measurement of Idris's "downstream restrictions" factor | https://www.eurocontrol.int/performance/data/download/xls/ATFM_Slot_Adherence.xlsx | EUROCONTROL public publication | 2026-09-01 |
| EUROCONTROL Airport Arrival ATFM Delay (daily) | Daily arrival ATFM delay by reason code (weather, ATC / aerodrome capacity, staffing, equipment) | https://www.eurocontrol.int/performance/data/download/xls/Airport_Arrival_ATFM_Delay.xlsx | EUROCONTROL public publication | 2026-09-01 |

## Candidate sources (not used yet)

| Source | Used for | Licence | Status |
|--------|---------|--------|-------|
| OpenStreetMap (aeroway=taxiway/parking_position) | Fallback distance for sparse (stand, runway) cells; a runway crossing flag | ODbL | Low priority, the empirical P10 is probably better |

## The IEM licence text (verbatim)

> "The materials found on this website are in the public domain and may be used freely
> by anyone for any lawful purpose. Attributing the Iowa Environmental Mesonet of Iowa
> State University would be appreciated."
> -- https://mesonet.agron.iastate.edu/disclaimer.php (2026-09-01)

Disclaimer: "we provide this information without any warranty of accuracy."
The attribution will be given in the JOAS paper and in the README.

## The METAR data downloaded

- Fetch: `python -m taxiout.adapters.metar_iem --start 2025-01-01 --end 2026-08-01`
- 11 airports x 2025-01-01 to 2026-07-31 = **306,222 observations**, 48 a day per airport
  (half hourly)
- The share of missing temperature or visibility is <0.03%; all 577 days are covered at
  every airport
- The `report_type` parameter is **deliberately not sent**: filtering on it drops Europe's
  half-hourly publication to hourly and throws away the SPECI reports issued when
  conditions change suddenly

## The OurAirports licence text (verbatim)

> "All data is released to the Public Domain, and comes with no guarantee of accuracy
> or fitness for use." … "We'd love you to give us credit, like we give credit to our
> sources, but you're not required to."
> -- https://ourairports.com/data/ (2026-09-01)

Attribution is not required; it will be given in the paper and in the README anyway.

## The airport data downloaded

- 86,013 airport coordinates (the arrival point can be anywhere in the world, so all of them
  are needed for the bearing) plus an open runway summary for the 11 competition airports.
- Runway counts: EHAM 6 · LTFM 6 · LFPG 5 · LEMD 4 · EDDF 4 · LSZH 4 · LIRF 3 · LTAI 3
  · LEBL 3 · **EDDM 2 · EGLL 2**. The two most constrained airports are EDDM and EGLL.

## The EUROCONTROL indicator: why validation and not a feature

The series is **monthly** and published with about a two-month lag: as of 2026-09-01 it ends in
June 2026. Of the ranking months, **July 2026 is not covered**, so it cannot be used as a
feature. And since it is derived from the same underlying data, using it as a feature would be
circular.

Its validation value is high: `scripts/analyse_deicing.py` measures our METAR de-icing proxy
against the "share of flights without a valid reference" field of this series (r = 0.757
overall; 0.87 to 0.98 at the cold airports). The results are in `docs/deicing_analysis.md`.

**LTAI is entirely absent from the official indicator** (TF = 0 across 24 months): Antalya is
not in the EUROCONTROL performance scheme.

## The daily ATFM series: coverage and constraints

- **They cover both ranking months**: 2019-01-01 to 2026-07-31, all 11 airports (LTAI
  included), 30,451 airport-days.
- Share of departures under ATFM regulation in January 2026: LSZH 16.6% · LFPG 13.3% ·
  LEMD 12.3% · EDDM 12.3% · EDDF 12.0% ... LTFM 6.6% · LTAI 5.1%.
- **They cannot be used in the causal model**: they are a whole-day total (they include the
  hours after the departure instant) and they are published months late. `groups.py` keeps
  them apart in the `atfm_daily` family; `pipeline.build_features` never adds them in a causal
  run.
- **The `D` (de-icing) reason column is entirely empty.** The hypothesis was tested and
  rejected: de-icing is not coded as an *arrival* ATFM reason. Our de-icing signal comes from
  METAR.
