# Register of Verified Facts

Rule: **never write a line without a source and a date.** Every ✅ line is re-checked once a week.
The competition page says it "reserves the right to change the rules or stop the competition", so what is true today can be wrong tomorrow.

Statuses: ✅ verified · ⏳ to be measured once the data arrives · ⚠️ needs confirmation · 🔴 open problem · ❌ turned out wrong

## Competition rules

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| F01 | Competition runs 2026-09-01 to 2026-10-11 23:59:59 CET | dc2026/index.html | 2026-09-01 | ✅ |
| F02 | Prize of 5000 EUR total for the top 3 teams | dc2026/index.html | 2026-09-01 | ✅ |
| F03 | Ranking = RMSE on the January + July 2026 departures | dc2026/index.html | 2026-09-01 | ✅ |
| F04 | A team is ranked by its **best** RMSE (not the last one, the best) | dc2026/ranking.html | 2026-09-01 | ✅ |
| F05 | **NO published submission limit** | dc2026/ranking.html | 2026-09-01 | ⚠️ confirm on Discord |
| F06 | Attempts to "learn from or exploit" the ranking process are monitored and counted as unfair | dc2026/ranking.html | 2026-09-01 | ✅ |
| F07 | Submission name `<team>_v<N>.parquet`; columns `MVT_ID_mvt` + `TAXITIME_SEC_mvt` | dc2026/ranking.html | 2026-09-01 | ✅ |
| F08 | Validation: every MVT_ID must match, no missing rows, no extra rows | dc2026/ranking.html | 2026-09-01 | ✅ |
| F09 | The team form is **LIVE** -> docs.google.com/forms/d/e/1FAIpQLScgRRk0j5Giot8puUAjzXC7ScR926Oupd62LbRVS1g8Y2p4hw | dc2026/index.html link | 2026-09-01 | ✅ (the earlier "example.com" claim was ❌) |
| F10 | The form is 22 pages; publishing participant names is **subject to consent**; it asks for confirmation that the rules are accepted | form page 1 | 2026-09-01 | ✅ |
| F11 | Form condition: **the 2026 data set may not be used outside the competition until it is public** | form page 1 | 2026-09-01 | ✅ |
| F12 | EUROCONTROL / OpenSky Network staff may take part but **are not eligible for a prize** | form page 1 | 2026-09-01 | ✅ |
| F13 | Turkey is a EUROCONTROL Member State (since 1989), so participation and prize are both eligible | eurocontrol.int member list | 2026-09-01 | ✅ |
| F14 | Prize condition: code on GitHub under **GPLv3**, every external data set openly licensed and documented, reproducible, original | dc2026/eligibility.html | 2026-09-01 | ✅ |
| F15 | Approval takes two rounds: form -> verification e-mail -> reply -> bucket keys | dc2026/index.html | 2026-09-01 | ✅ |

## Data set

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| D01 | 11 airports: EDDF EDDM EGLL EHAM LEBL LEMD LFPG LIRF **LTAI LTFM** LSZH | dc2026/data.html | 2026-09-01 | ✅ |
| D02 | Training: 12 monthly parquet files, all of 2025, ~277 MB total | dc2026/data.html | 2026-09-01 | ✅ |
| D03 | `ranking.parquet` 27 MB (January + July 2026); `submitting.parquet` 1.1 MB | dc2026/data.html | 2026-09-01 | ✅ |
| D04 | 4,167,797 movements in total (ARR + DEP) | dc2026/data.html | 2026-09-01 | ✅ |
| D05 | In ranking, **ONLY for DEP**, `BLOCK_TIME_UTC_mvt` and `TAXITIME_SEC_mvt` are blanked out | dc2026/data.html | 2026-09-01 | ✅ |
| D06 | `AOBT_3_flt` (the M3 actual block time) is **NOT on the blanked list** | dc2026/data.html | 2026-09-01 | 🔴 **measure at I0: how good a predictor is `MVT_TIME - AOBT_3`?** |
| D07 | `MVT_TIME_UTC_mvt` is not blanked for DEP, so the take-off time is known | dc2026/data.html | 2026-09-01 | ✅ |
| D08 | `RUNWAY_mvt` and `STAND_mvt` are not blanked | dc2026/data.html | 2026-09-01 | ✅ |
| D09 | No column of the ARR rows is blanked | dc2026/data.html | 2026-09-01 | ✅ |
| D10 | Flight (`*_flt`) columns are filled only when there is an NM match (`FLIGHT_ID_mvt` "if matched") | dc2026/data.html | 2026-09-01 | ⏳ measure the match rate |
| D11 | Military / head of state / sensitive movements have been removed from the data set | dc2026/data.html | 2026-09-01 | ✅ |
| D12 | Organiser warning: there are inconsistencies between the movement and the flight information, and they have not been reconciled | dc2026/data.html | 2026-09-01 | ✅ |
| D13 | `MVT_TIME_UTC_mvt` is defined as "(best available) movement time", so its source and precision are unclear | dc2026/data.html | 2026-09-01 | ⏳ does the identity `MVT - BLOCK == TAXITIME` hold in 2025? |

## Domain knowledge and methodology

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| M01 | Purpose of the competition: find the constrained operating intervals in **post-ops** analysis and measure the extra fuel and CO2 against the unconstrained case | dc2026/rationale.html | 2026-09-01 | ✅ |
| M02 | Why taxi-out was chosen: it is "hard to obtain and hard to predict accurately" | dc2026/rationale.html | 2026-09-01 | ✅ |
| M03 | Sources of variability: airline constraints, airport procedures and load, ATFM | dc2026/rationale.html | 2026-09-01 | ✅ |
| M04 | Official PRC KPI: additional taxi-out = actual taxi-out minus the reference time estimated **for each stand-runway combination** | ansperformance.eu/definition/additional-taxi-out-time | 2026-09-01 | ✅ |
| M05 | Official methodology document: `library/ATXOT_indicator_documentation_mar23.pdf` (2023 revision) | ansperformance.eu/methodology/additional-taxi-out-time | 2026-09-01 | ✅ downloaded to docs/reference/ |
| M06 | The official reference is **P10 for each (airport, STAND, departure RUNWAY) combination**, over a rolling 12 months | ATXOT p.14, §3.5 4b | 2026-09-01 | ✅ (the earlier "P20" guess was ❌) |
| M07 | Reference validity condition: the combination must have **at least 10 flights with taxi-out ≤ P10**; otherwise no reference is assigned | ATXOT p.15, §3.5 | 2026-09-01 | ✅ |
| M08 | Official filters: taxi-out > 120 min excluded, missing runway/stand/block time excluded, **helicopters excluded**, **flights that de-ice after AOBT excluded** | ATXOT p.13, §3.4 step 1 | 2026-09-01 | ✅ |
| M09 | Official formula: `TaxiOut(f) = ATOT(f) - AOBT(f)` | ATXOT p.13, §3.4 step 3 | 2026-09-01 | ✅ |
| M10 | The PRC **deliberately does NOT use aircraft type or class in the grouping**, to keep the samples from shrinking; but it accepts that it "may affect taxi speed" | ATXOT p.11, §3.2 | 2026-09-01 | ✅ **-> gap #1 that our model closes** |
| M11 | Factors the PRC **explicitly writes that it does not account for**: different taxi routes, aircraft taxi speed, special events (apron works and similar) | ATXOT p.15, §5 | 2026-09-01 | ✅ **-> gap #2, the contribution surface of the paper** |
| M12 | Push-back time and the runway occupancy of the take-off roll are treated as "systemic" and buried inside the reference | ATXOT p.10, §3.1 | 2026-09-01 | ✅ |
| M13 | **The only AOBT source is the airport APDF stream** (no alternative source); the NM stream is used only to complete the take-off time | ATXOT p.17, Table 3 | 2026-09-01 | ✅ **-> `BLOCK_TIME_UTC_mvt` = APDF AOBT, `AOBT_3_flt` = NM M3 AOBT: two DIFFERENT measurements of the same event, not identical** |
| M14 | Timestamps may be at HH:MM precision only in some sources | ATXOT p.15, §4 | 2026-09-01 | ✅ |

## Previous editions and infrastructure (2026-09-01 research)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| P01 | Team names are **assigned automatically** (adjective-noun): `resourceful-quiver`, `jubilant-vase`, `team_likable_jelly` | 2024 and 2025 GitHub org listings | 2026-09-01 | ✅ the name is not our decision |
| P02 | Submission goes to a **MinIO bucket**: `mc ls opensky/prc-2025-<team>/`, file `<team>_v<N>.parquet` | resourceful-quiver/scripts/check_submission_ver.sh | 2026-09-01 | ✅ `mc.exe` installed (~/bin) |
| P03 | The 2025 winner (resourceful-quiver) is **TU Delft Faculty of Aerospace Engineering**; the 2024 winners were ENAC academics | PRC_2025_report.pdf, 2024 announcement | 2026-09-01 | ✅ the field leans academic |
| P04 | The 2025 winner ran the ablation **directly on the ranking set (leaderboard), not with CV**; "we removed k-fold from the report, the ranking RMSE is more valuable" | PRC_2025_report.pdf §6 | 2026-09-01 | ✅ an ablation of ~18 submissions, so no real limit |
| P05 | The single largest gain in 2025 was **reparameterising the target**: training on fuel *flow* instead of fuel burn (RMSE 220.56 -> 201.04), larger than any of the feature groups | PRC_2025_report.pdf §6.3 | 2026-09-01 | ✅ **our equivalent: the residual over the P10 reference instead of raw taxi-out** |
| P06 | The 2025 winner's paper is 14 pages in JOAS preprint format: Abstract/Keywords/Abbreviations + Introduction, Data, Preprocessing, Features, Model, Results, Conclusion; the contribution is presented as **a single feature x RMSE ablation table** | PRC_2025_report.pdf | 2026-09-01 | ✅ template |
| P07 | There is **NO trajectory (ADS-B) data in 2026**, only movement records. 2024 and 2025 required ADS-B plus OpenAP / aerodynamics expertise | dc2026/data.html | 2026-09-01 | ✅ **the field is levelled for non-aviation tabular teams** |
| P08 | **The 2024 winners were announced at the 12th OpenSky Symposium (Hamburg, 7-8 November 2024)**, so there is a symposium after the competition where the winners are announced | search result, the page itself was not read | 2026-09-01 | ⚠️ needs confirmation for 2026 |
| P09 | JOAS ran a **special issue** for the 2025 competition (Vol. 4 No. 3, 2026: "EUROCONTROL PRC 2025 Data Challenge"), so there is a ready publication route for the paper | journals.open.tudelft.nl/joas/issue/view/1058 | 2026-09-01 | ✅ |
| P10 | The 2026 page **does not say how the prize is split across the top 3**; in 2025 it was 2500/1750/750. It also does not give the payment method or date | dc2026/index.html | 2026-09-01 | ⚠️ ask challenge@opensky-network.org if needed |
| W01 | IEM ASOS/METAR covers all 11 airports, all 577 days between 2025-01-01 and 2026-07-31, 48 observations a day, less than 0.03% missing | our own download | 2026-09-01 | ✅ 306,222 rows downloaded |
| W02 | IEM data is **public domain**, attribution appreciated | mesonet.agron.iastate.edu/disclaimer.php | 2026-09-01 | ✅ meets the prize condition |
| W03 | Share of de-icing conditions in January 2026: **LSZH 18.0% · EHAM 13.4% · EDDM 11.2% · LTFM 9.9% · EDDF 8.3%**; LTAI/LEBL/LIRF **0%** | our own METAR analysis | 2026-09-01 | ✅ **the January error will pile up at these five airports; there is no de-icing at LTAI** |
| W04 | The de-icing proxy passes the seasonal check: 2.3% in 2025-01 -> 0.04% in 2026-07 | our own METAR analysis | 2026-09-01 | ✅ |
| A01 | `SCHED_TIME_UTC_mvt` is **not blanked** in the ranking set, so the identity `MVT_TIME - SCHED_TIME = taxi_out + departure_delay` can be used | dc2026/data.html D05 + our own derivation | 2026-09-01 | ✅ a second legitimate handle |
| A02 | There are **two independent handles** on the block time: the NM measurement `AOBT_3_flt` and the scheduled `SCHED_TIME`. The core of the problem is reconciling the two and modelling the residual uncertainty | our own analysis | 2026-09-01 | ⏳ the RMSE of both is measured in `probe_data.py` §5 and §8 |
| A03 | Most of the irreducible uncertainty is in the distribution of the **departure delay** (actual block minus scheduled block); its standard deviation should be compared against the standard deviation of taxi-out itself | our own analysis | 2026-09-01 | ⏳ §8 |

## The JOAS paper (2026-09-01 research)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| J01 | **LaTeX is mandatory**, Word is rejected; template at `github.com/open-aviation/joas-template` | joas/about/submissions | 2026-09-01 | ✅ template taken into the repository |
| J02 | All content goes in **a single `main.tex`**; `\input{}` and `\include{}` are forbidden; file names may not be changed | joas-template/main.tex | 2026-09-01 | ✅ |
| J03 | The abstract is **a single paragraph of ≤300 words** and must cover four elements (purpose, design, findings, interpretation); the title is ≤12 words | joas-template/main.tex | 2026-09-01 | ✅ |
| J04 | An **Open data statement** and a **Reproducibility statement** are MANDATORY sections | joas-template/main.tex | 2026-09-01 | ✅ present in the skeleton |
| J05 | An abbreviation is defined only if it occurs **more than 10 times** in the text; tables must be plain `tabular` (custom styling breaks the HTML version) | joas-template/main.tex | 2026-09-01 | ✅ |
| J06 | Submission: the compiled PDF plus a ZIP of the LaTeX source. Review is **open** (identities are shared, reviews are published). No fee | joas/about/submissions | 2026-09-01 | ✅ |
| J07 | Article type: `manuscript=article` (Research Article, General). "Open Software Focus" requires the author to be the main developer of the software and the focus to be the software itself, whereas our contribution is the method | joas/about/submissions | 2026-09-01 | ✅ decided |

## The official EUROCONTROL indicator and de-icing (2026-09-01 analysis)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| E01 | The official ATXOT indicator is openly downloadable: reference and additional taxi-out time per airport-month, 2018-2026 | eurocontrol.int/performance/data/download/xls/Taxi-Out_Additional_Time.xlsx | 2026-09-01 | ✅ downloaded |
| E02 | **2025 mean total taxi-out (min per departure):** EGLL 22.7 · LIRF 19.0 · LTFM 16.9 · LEMD 16.8 · LEBL 15.8 · EDDF 14.2 · EHAM 13.0 · EDDM 12.9 · LSZH 11.9 | official indicator | 2026-09-01 | ✅ **the scale of the target: ~715-1365 s** |
| E03 | **LTAI is entirely absent from the official indicator** (24 months, TF=0); Antalya is not in the EUROCONTROL performance scheme | official indicator | 2026-09-01 | ✅ no external validation source; the data quality may differ |
| E04 | The indicator ends in June 2026, so **July 2026 is not covered** and it cannot be used as a feature | official indicator META | 2026-09-01 | ✅ validation only |
| E05 | Our METAR de-icing proxy correlates with the official "share of flights without a reference" at **r = 0.757**; within an airport LTFM 0.98 · LSZH 0.97 · EDDF 0.94 · EDDM 0.94 · LFPG 0.87 | our own analysis | 2026-09-01 | ✅ the proxy is independently validated |
| E06 | **Airports have different de-icing regimes.** EHAM: the share without a reference stays flat at ~1% through the year, yet the additional time rises by +1.46 min in winter. EDDM/LSZH: in winter a large share of flights drops out of the indicator (31% at EDDM in January 2026) and the additional time does not rise | our own analysis | 2026-09-01 | ✅ **the January error will pile up on the flights EDDM/LSZH DISCARD from the official indicator** |
| E07 | Additional taxi-out time is lower in winter than in summer at **every** airport (the summer traffic peak); EHAM is the only exception | our own analysis | 2026-09-01 | ✅ it strengthens the EHAM anomaly |

## Scale and performance (2026-09-01 measurement)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| S01 | At the real scale (4.17M movements) the end-to-end validation run takes **96 s**, peak memory **5.15 GB of 15.9** | our own measurement, synthetic data | 2026-09-01 | ✅ ADR-0002 |
| S02 | The submission path (the highest memory point) takes **171 s**, peak **7.06 GB** | our own measurement | 2026-09-01 | ✅ out-of-core is not needed |
| S03 | **2.08M of the 4.17M movements are departures**; 114 raw columns, 95 modellable features | our own measurement | 2026-09-01 | ⏳ to be confirmed on the real data |
| S04 | A full ablation (13 configurations x 1500 rounds) is estimated at **~1.7 hours**, ~8.5 hours with 5 seeds | scaled from S01 | 2026-09-01 | ✅ an overnight run can be planned |

## External data sources (2026-09-01 investigation)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| O01 | OPDI (the open PRC + OpenSky initiative) publishes flight events derived from ADS-B; v0.0.2 includes **parking position entry/exit**, covering 2022-01 to 2026-08-08 (both ranking months) | opdi.aero/flight-event-data.html | 2026-09-01 | ✅ |
| O02 | **Parking position events exist only at LSZH and EDDF**; there are **zero** at EHAM/LIRF/LTAI/LTFM. The reason: OPDI derives these events from OSM parking position polygons, and those polygons are missing at most airports | our own measurement, a 10-day file | 2026-09-01 | ✅ **RULED OUT** (docs/opdi_negative_result.md) |
| O03 | **Open ADS-B ground coverage at LTFM and LTAI is nearly zero** (25 and 119 runway entries in 10 days), so any ADS-B based approach would collapse at exactly the two Turkish airports | our own measurement | 2026-09-01 | ✅ |

## Team approved (2026-09-01 13:45)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| T01 | **Team name: `vibrant-lollipop`** (assigned automatically, P01 confirmed) | hello-noreply@opensky-network.org | 2026-09-01 | ✅ |
| T02 | **Submission bucket: `prc-2026-vibrant-lollipop`** | same e-mail | 2026-09-01 | ✅ |
| T03 | Submission file name: `vibrant-lollipop_vN.parquet` | same e-mail | 2026-09-01 | ✅ matches the pattern in `submission.py` |
| T04 | Login is **through SSO**: in the console, "Other Authentication Methods" -> "Login with SSO" -> Keycloak -> OpenSky credentials | same e-mail | 2026-09-01 | ✅ |
| T05 | Shortly after a submission a **result file** appears in the bucket, so there is feedback for every submission | same e-mail | 2026-09-01 | ✅ no need to wait for the leaderboard |
| T06 | In 2024 the endpoint was `https://s3.opensky-network.org/`, alias `mc alias set dc24 <endpoint> ACCESS SECRET` | dc2024/data.html | 2026-09-01 | ⏳ the 2026 console URL is in the link in the e-mail |
| T07 | Contact: the "PRC Data Challenge 2026" Discord server, challenge@opensky-network.org | same e-mail | 2026-09-01 | ✅ |
| T08 | **OSN is unreachable while Cloudflare WARP is on** (WARP takes over DNS and TLS is cut); Discord in turn is blocked without WARP | our own diagnosis | 2026-09-01 | ✅ the two do not work at the same time |

## THE REAL DATA (2026-09-01, downloaded and measured)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| R01 | **The data set has 10 airports, not 11. LTAI (Antalya) is ABSENT.** Not a single row in training or in ranking | our own measurement | 2026-09-01 | ✅ **the competition page says 11, the data says 10** (consistent with E03: LTAI is not in the performance scheme) |
| R02 | **`ADEP_mvt` is NOT the airport of the movement, it is the departure airport of the flight.** Movement airport = `ADEP_mvt` for DEP, `ADES_mvt` for ARR. Training holds 1,582 distinct `ADEP_mvt` values | our own measurement | 2026-09-01 | 🔴 **bug in the code: every arrival-derived feature was grouped at the wrong airport** |
| R03 | **The ranking set has only 3 airports in July: EDDF, EGLL, EHAM.** All 10 in January | our own measurement | 2026-09-01 | 🔴 **the validation scheme has to reflect this** |
| R04 | Ranking set: 152,719 January departures (10 apt) + 63,157 July departures (3 apt) = **215,876**. January is **71%** of the total rows | our own measurement | 2026-09-01 | ✅ January dominates the RMSE |
| R05 | Training holds exactly **4,167,797** movements (matching the published figure), 2,085,047 of them departures | our own measurement | 2026-09-01 | ✅ |
| R06 | The identity `MVT_TIME - BLOCK_TIME == TAXITIME` **holds exactly** (share 1.0000, maximum deviation 0 s) | probe §2 | 2026-09-01 | ✅ TAXITIME is derived, the timestamps are consistent |
| R07 | Timestamps are at **second precision** (the share with a zero second is 1.6% to 8.4%), so there is NO HH:MM problem | probe §3 | 2026-09-01 | ✅ the M14 worry does not apply |
| R08 | **`AOBT_3_flt` is 98.52% filled in the ranking set**; the naive `MVT - AOBT_3` predictor gives **RMSE 384.9 s** (MAE 238, median absolute error 175, bias +17) | probe §5 | 2026-09-01 | ✅ **a strong feature, not the solution** (my own threshold was >200 s) |
| R09 | Naive AOBT_3 per airport: EDDF 255 · LSZH 268 · LEMD 276 · LEBL 311 · EHAM 330 · EDDM 349 · LFPG 380 · EGLL 419 · **LTFM 531 · LIRF 557** | probe §5 | 2026-09-01 | ✅ LTFM and LIRF are the hardest |
| R10 | **The scale of the target matches the published indicator one for one:** EGLL mean 1364 s (22.7 min), LSZH 740 s (12.3 min), against 22.7 and 11.9 min in the official series in E02 | probe §6 | 2026-09-01 | ✅ the external data work is confirmed |
| R11 | **LIRF is the outlier nest:** std 1332 s, p99 4019 s, 0.30% above 120 minutes. LSZH has 0.22% **negative** taxi times | probe §6 | 2026-09-01 | ✅ a modelling decision, not clipping |
| R12 | The highest variance months are **July (std 745) and January (605)**, so the two ranking months are the two hardest | probe §6 | 2026-09-01 | ✅ |
| R13 | Combination (apt, stand, runway) mean baseline: **RMSE 628.4 s**; airport mean 660.0; global mean 686.6 | probe §7 | 2026-09-01 | ✅ the level of the first submission |
| R14 | Cold start is low: **99.46%** of the ranking combinations were seen in training; the null share for stand and runway is 0 | probe §7 | 2026-09-01 | ✅ |
| R15 | Departure delay (actual block minus scheduled) has std **2238 s**, 24.2% of it early. The naive `MVT - SCHED` predictor gives RMSE **2412.7** | probe §8 | 2026-09-01 | ✅ SCHED is a far weaker handle than AOBT_3 |

## Data quality (2026-09-01 audit)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| Q01 | **The categorical fields carry no case or whitespace variants at all** (9 fields, 1,899 stands and 269 aircraft types included). A machine-generated feed, so the human-entry cleaning playbook does not transfer | our own audit | 2026-09-01 | ✅ do not spend time on normalisation |
| Q02 | **Cold start is negligible:** 20 unseen stands (0.106% of ranking rows), 3 unseen aircraft types (0.005%), zero unseen runways or airports | our own audit | 2026-09-01 | ✅ |
| Q03 | **388 training departures have a taxi-out of zero or less** and 584 are above two hours; of the 103 above two hours with a network match, **96 (93.2%) have a plausible network time**, so the airport feed's block time is the wrong field | our own audit | 2026-09-01 | ✅ label error, not real taxi time |
| Q04 | **Those rows are kept on purpose.** Dropping them cost 24 and 36 s (E03). Under squared loss the optimal prediction is the conditional mean, which carries the small probability of a huge value; removing it shifts every prediction down | E03 + reasoning | 2026-09-01 | ✅ cleaner training data is measurably worse here |

## Board (submission results)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| B01 | **v1 board score: RMSE 331.2256**, status Succeeded, all 215,876 pairs used | bucket `vibrant-lollipop_v1.parquet_result.json` | 2026-09-01 | ✅ the first baseline |
| B02 | After a submission **two files** land in the bucket: `<name>_result.json` (the score) and `<name>_persist.json` (the status). The result arrives in about 15 seconds | same | 2026-09-01 | ✅ fast feedback, no need to wait for the leaderboard |
| B03 | The real target is held in `prc-2026-testsets/truthing.parquet` (closed to us) | the `inputs` field of result.json | 2026-09-01 | ✅ |
| B04 | **Local validation is PESSIMISTIC against the board:** local 378.80 -> board 331.23 (12.6% better). That is the safe direction; whether a local improvement carries to the board is another matter | our own measurement | 2026-09-01 | ⏳ the relationship will be confirmed on the second submission |
| B05 | **The live leaderboard is behind a REST API:** `https://datacomp.opensky-network.org/api/competitions/bb3693e1-26bc-4a9e-8619-4fe78b4eab0c/leaderboard`. The page shows no table, it is embedded through Observable. `scripts/leaderboard.py` fetches it | extracted from dc2026/ranking.html | 2026-09-01 | ✅ |
| B06 | **32 teams registered**, all of them on 2026-09-01. `vibrant-lollipop` is listed under Turkey | dc2026/teams.html | 2026-09-01 | ✅ |
| B07 | State at 2026-09-01 15:35: **only 2 teams have submitted.** enthusiastic-daisy 304.98 (v2) · **vibrant-lollipop 331.23 (v1)** · enthusiastic-daisy 485.23 (v1) | leaderboard API | 2026-09-01 | ✅ 26.25 behind the leader |
| B08 | **v2 board 331.7983** (lr 0.02, 255 leaves, 380 rounds, 5 seeds) vs **v1 331.2256**. Locally v2 was significantly better by the paired test; on the board it was 0.57 worse | bucket result.json | 2026-09-01 | ✅ **local significance does not imply board improvement** |
| B09 | **v3 board 306.4068** (XGBoost+CatBoost, 400 rounds, 1 seed) against v1 331.2256. A gain of 24.82 s, local predicted 27.30 | result.json | 2026-09-01 | ✅ second place, 7.37 s behind the leader |
| B10 | **A large local gain DOES transfer; a small one does not.** v2 moved a few seconds locally and lost 0.57 on the board; v3 moved 27 s locally and gained 24.8. The noise floor of ~5 s is the dividing line | v1/v2/v3 boards | 2026-09-01 | ✅ |
| B11 | **`mc` silently turns an unknown alias into a local directory copy and reports success.** The alias is `prc`, not `opensky`; the first v3 upload never left the machine. `scripts/submit.py` now verifies the object is in the remote bucket | our own measurement | 2026-09-01 | ✅ control closed |

## Model findings (2026-09-01 measurements)

| # | Fact | Source | Checked | Status |
|---|--------|--------|---------|-------|
| M20 | The model is best at **round 328** (RMSE 377.28); by 500 rounds it degrades to 379.04. The v1 submission used 800 rounds, so it **overfitted** | early stopping run | 2026-09-01 | ✅ the round count will be lowered |
| M21 | **Gain distribution:** atfm 36.8% · geometry 31.5% · nm_aobt 10.4% · runway_configuration 5.9% · weather 1.8% · **runway_queue 1.6%** · **airport_flow 1.4%** | LightGBM gain | 2026-09-01 | 🔴 **the congestion features (34 of them) come to 3% in total** |
| M22 | The strongest single features: `reference_sec` 18.8% · `eobt_offset_sec` 16.0% · `sched_offset_sec` 15.4% · `nm_naive_taxi_sec` 10.4% · `STAND_mvt` 7.5% | LightGBM gain | 2026-09-01 | ✅ |
| M23 | **Block time handles, naive RMSE:** AOBT_3 385 · EOBT_1 677 · IOBT 740 · LOBT 740 · SCHED 2413. All of them have the same coverage (98.92%) | our own measurement | 2026-09-01 | ✅ AOBT_3 is the best by a wide margin, there is no hidden handle |
| M24 | Despite its name `LOBT_flt` is **not the actual block time**, it is nearly identical to IOBT (740 vs 740), so it is a planned time | our own measurement | 2026-09-01 | ✅ |
| M25 | On the holdout the **naive prediction is 531.40** and the model 377.84. The model buys **154 s** over the naive prediction | our own measurement | 2026-09-01 | ✅ the modelling effort pays for itself |

| M26 | **The learner was the largest lever found so far.** Same features, same split, 400 rounds: LightGBM 378.99, XGBoost 357.80, CatBoost 353.59, XGBoost+CatBoost 351.69. The paired noise floor is ~5 s | our own measurement | 2026-09-01 | ✅ the model layer is now a port with one adapter per library |
| M27 | **Adding LightGBM to the blend makes it worse** (357.49 for all three against 351.69 for the pair), so it contributes error rather than a different view | our own measurement | 2026-09-01 | ✅ |
| M28 | XGBoost applies **no categorical handling at all** and still beats LightGBM by 21 s, which points at LightGBM's categorical splitting overfitting the 1,899 stands and the hashed operator | our own measurement | 2026-09-01 | ⏳ `lightgbm-nocat` will test it |

## Open questions

| # | Question | How it closes |
|---|------|---------------|
| Q01 | Is there a daily or total submission limit? | Ask on Discord. P04 is indirect evidence: the 2025 winner ran an ablation of ~18 submissions, so there seems to be no tight limit |
| Q02 | ~~How good is `AOBT_3_flt`?~~ | **CLOSED (R08):** 98.52% filled, naive RMSE 384.9 s. A strong feature, not the solution |
| Q03 | ~~Is the leaderboard live?~~ | **CLOSED (B02, B05):** the score lands in the bucket as JSON within ~15 s; the ranking is behind a REST API |
| Q04 | ~~What will the team name be?~~ | **CLOSED:** `vibrant-lollipop` was assigned (T01) |
