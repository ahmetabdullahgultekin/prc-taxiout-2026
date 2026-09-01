# OPDI ADS-B ground events: assessed and ruled out

**Result: unusable.** The rationale and the measurement are below. To reproduce:
`python scripts/probe_opdi_coverage.py --events <flight_events_*.parquet>`

## Why we looked

The **off-block instant** of departures is blanked out in the ranking set (D05). OPDI, the
PRC's own open data initiative run jointly with the OpenSky Network, publishes flight events
derived from ADS-B, and v0.0.2 added **parking position entry/exit** events.
`exit-parking_position` would be an independent measurement of the blanked field.

The coverage runs **2022-01 to 2026-08-08**, so both ranking months are inside it. The data is
open, documented and listed on the PRC's own data page; the competition itself states that its
purpose includes using open data. So there is no legitimacy problem.

More than that, it lined up exactly with the rationale of the competition: taxi-out is "a
quantity that is hard to obtain", and the real job of the model is to fill the gap at airports
that do not share A-CDM data. Whether open ADS-B events can fill that gap is a directly
relevant question.

## Measurement

A single 10-day file (`flight_events_20260110_20260120.parquet`, 260 MB, 7.48M events), events
within 10 km of the airport centre:

| airport | exit-parking_position | take-off | entry-runway | entry-taxiway |
|---|---:|---:|---:|---:|
| LSZH | 9,611 | 1,412 | 7,121 | 42,816 |
| EDDF | 4,399 | 704 | 9,032 | 23,174 |
| LEBL | 7 | 853 | 4,875 | 2,045 |
| EGLL | 4 | 10 | 5,629 | 799 |
| EDDM | 2 | 31 | 2,359 | 342 |
| LEMD | 2 | 20 | 1,421 | 149 |
| LFPG | 1 | 1 | 1,684 | 69 |
| **EHAM** | **0** | 1,398 | 9,535 | 1,428 |
| **LIRF** | **0** | 7 | 781 | 77 |
| **LTAI** | **0** | 5 | 119 | 6 |
| **LTFM** | **0** | 0 | 25 | 9 |

For comparison, the expected number of departures over 10 days is on the order of 3,000 to
7,500 per airport (from the 2025 official traffic data).

## Reading

Parking position events exist **only at Zurich and Frankfurt**. The reason is in OPDI's
methodology: these events are produced by matching OpenStreetMap parking position polygons
against an H3 resolution 12 grid, and those polygons are not mapped at most airports. It is the
same problem Ravizza and colleagues complained about, the inadequacy of OSM taxiway and parking
position data.

One other thing stands out: **open ADS-B ground coverage at LTFM and LTAI is nearly zero**
(25 and 119 runway entries over 10 days, 0 and 5 take-off events). So any ADS-B based approach
would collapse at exactly the two Turkish airports.

## Decision

No feature will be **built** on this source. A feature that exists at 2 of the 11 airports
would be a column the model carries as mostly missing, and the cost of the join infrastructure
(flight matching, a ~1.6 GB download) does not pay for itself.

## The form it takes in the paper

This is a result to report, not to throw away. The 2025 jury praised the teams that reported
the paths that did not work. It is also a concrete finding about the PRC's own initiative:
**open ADS-B ground events, at today's coverage, cannot stand in for missing A-CDM block
times**, because the limiting factor is not ADS-B but the missing parking position mapping in
OpenStreetMap. That is actionable feedback for OPDI.
