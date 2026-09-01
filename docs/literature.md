# Literature: taxi-out time prediction

The review was done on 2026-09-01 through OpenAlex (title based, 136 relevant records; the raw
output is in `scratchpad/papers/openalex_taxiout.json`). Every line here rests on an abstract
that was read; the ones that were not read are marked as such.

This file has two jobs: **(1)** to tie the choice of each feature family back to a source, since
the 2025 jury explicitly criticised "insufficient justification for feature selection"; **(2)**
to serve as the draft of the related work section of the JOAS paper.

---

## 1. The queueing school: the physics of the problem

**Idris, Clarke, Bhuva, Kang (2002), "Queuing Model for Taxi-Out Time Estimation",
*Air Traffic Control Quarterly* 10(1). 176 citations.** ([doi](https://doi.org/10.2514/atcq.10.1.1))

Four main causal factors determine taxi-out at Boston Logan: **runway configuration,
airline/terminal, downstream restrictions, and departure queue size.** Of those, **queue size
is the most important**; it is defined as the number of take-offs that occur between an
aircraft's push-back and its own take-off.

The key point: their model has to **predict** the queue size, because it is not known how much
passing an aircraft will experience while taxiing. The comparison baseline is a 14-day moving
average (the production method of ETMS at the time).

> **What it means for us.** This variable is **observable** for us: the take-off time of every
> departure is present in the ranking set. But an exact count requires the push-back time,
> which is our target, so `congestion.py` uses fixed-window (5/10/15/30/60 min) non-circular
> proxies. Three of the four factors are features we implement directly: runway configuration,
> operator/stand, queue intensity.

**Simaiakis & Balakrishnan (2015), "A Queuing Model of the Airport Departure Process",
*Transportation Science*. 108 citations.** ([doi](https://doi.org/10.1287/trsc.2015.0603))

Decomposes taxi-out as **unimpeded taxi-out + departure queue + congestion delay**; models the
runway queue through the transient analysis of a D/Eₖ/1 system.
_(The abstract was read; the full text was not.)_

---

## 2. Unimpeded time: a direct criticism of the PRC's method

**Yin et al. (2017), "Methods for determining unimpeded aircraft taxiing time and evaluating
airport taxiing performance", *Chinese Journal of Aeronautics* 30(2). 43 citations, open
access.** ([doi](https://doi.org/10.1016/j.cja.2017.01.002))

This paper **reviews exactly the kind of methods the PRC uses and proposes regression in their
place**. Its findings:

- It examines the common methods of different ANSPs (percentile-based references) and
  **strongly recommends econometric regression models**: they need less detailed data and are
  sufficient for general performance analysis.
- The proposed model beats the existing ones because it adds **more explanatory variables**: in
  particular **aircraft passing each other (passing / over-passing)** enters the queue length
  calculation, and **runway configuration, the ground delay program and the weather state**
  enter the model.
- Main conclusion: **"queue length in the taxiway system and the interaction between queues are
  the principal contributors to long taxi-out times."**

> **What it means for us, and this is the core of the thesis.** The official PRC indicator
> (ATXOT) defines the reference as the **P10** of the stand-runway combination and deliberately
> leaves aircraft type out (see `atxot-notes.md` M10, M11). The literature says regression is
> superior on exactly that point. Our contribution sits in a gap that **the institution
> documents itself and the literature has named**, not in a speculative one.

---

## 3. Layout-based regression at European airports

**Ravizza, Atkin, Maathuis, Burke (2013), "A combined statistical approach and ground movement
model for improving taxi time estimations at airports", *JORS* 64(9). 74 citations.**
([doi](https://doi.org/10.1057/jors.2012.123))

Multiple linear regression at two large European hubs (**Stockholm-Arlanda and Zurich**):
airport layout plus historical taxi times. The motivation is the mirror image of ours: to
**quantify and remove the airport load effect** in historical data.

**Ravizza, Atkin, Burke (2013), "Aircraft taxi time prediction: Comparisons and insights",
*Applied Soft Computing*. 64 citations.** ([doi](https://doi.org/10.1016/j.asoc.2013.10.004))

A TSK fuzzy rule based system beats SVM regression, M5 model trees and classical regression.
**Accuracy within ±1 minute of 58.21% at ARN and 64.05% at ZRH.** _(Figures from the search;
the full text was not read.)_

**LSZH is in our data set.** That is the only directly comparable ZRH reference we have:
**about 64% within ±1 min**.

**Ravizza et al. (2020), "Aircraft taxi time prediction: Feature importance and their
implications", *Transportation Research Part C* 112. 70 citations.**
([doi](https://doi.org/10.1016/j.trc.2020.102892))

The most important features: **taxi distance, the sum of turning angles, the departure/arrival
distinction, and the amount of traffic around the aircraft while it taxis.** _(The abstract was
not reachable; the finding comes from the search result and the full text was not read, so
verify before citing it in the paper.)_

> **What it means for us.** We do **not** have taxi distance or turning angle (there is no route
> data). But the empirical P10 contains the duration of the route actually used for that
> stand-runway pair, which is a better proxy than the theoretical shortest path. That is why the
> OSM taxiway graph is not core but only a fallback candidate for sparse cells.

---

## 4. Machine learning applications: which features, which error

**Herrema et al. (2018), "Taxi-Out Time Prediction Model at Charles de Gaulle Airport",
*Journal of Aerospace Information Systems*. 37 citations.**
([doi](https://doi.org/10.2514/1.i010502))

**LFPG is in our data set.** They compare a neural network, a regression tree, reinforcement
learning and an MLP, with RMSE as the metric. **The best method is the regression tree, with a
mean error on any given day of about 1.6 minutes (about 96 seconds).**

> That is the **most concrete target magnitude** we have: a published result at one of our
> airports, with the same metric. With 11 heterogeneous airports and no route data, worse is to
> be expected; but it gives the order of magnitude.

**Lee, Malik, Jung (2016), "Taxi-Out Time Prediction for Departures at Charlotte Airport
Using Machine Learning Techniques", AIAA ATIO. 53 citations.**
([doi](https://doi.org/10.2514/6.2016-3910))

The variables selected: **terminal concourse, spot, runway, departure fix and weight class**;
plus different traffic flow and weather conditions. Linear regression and random forest give the
best RMSE.

> **The new feature idea came from here: the departure fix.** Departures heading for the same
> exit point or direction have to be separated further from each other (route and wake vortex
> separation), so an aircraft waits longer when its neighbours are going the same way as it is.
> We have no departure fix, but we do have `ADES_mvt`: the **bearing** from the departure airport
> to the arrival airport can be computed, rounded into a sector, and the number of same-sector
> departures in the window can be counted. `features/routing.py` does this.

**Wang et al. (2018), "Machine Learning Techniques for Taxi-out Time Prediction with a
Macroscopic Network Topology", DASC. 30 citations.**
([doi](https://doi.org/10.1109/dasc.2018.8569664))

Shanghai Pudong. It splits the predictors into **four families**, and we adopt that taxonomy as
it stands and cite it in the paper:

| Family | Expansion | Our equivalent |
|------|--------|-------------------|
| SIFI | surface **instantaneous** flow indices | `apt_dep_prev_5m`, `apt_arr_prev_5m` |
| SCFI | surface **cumulative** flow indices | the 30/60 min windows |
| AQLI | aircraft **queue length** indices | `rwy_dep_prev_*`, `rwy_service_interval_sec` |
| SRDI | **slot resource demand** indices | `sched_offset_sec`, ATFM drift (LOBT - IOBT) |

A random forest trained on a month of samples clearly beats ones trained on a single day, so
sample size is critical. We have a year.

**Diana (2018), "Can machines learn how to forecast taxi-out time? … Seattle/Tacoma",
*Transportation Research Part E* 119. 39 citations.**
([doi](https://doi.org/10.1016/j.tre.2018.10.003)) _(The abstract was not reachable.)_

**Balakrishna, Ganesan, Sherry (2010), "Accuracy of reinforcement learning algorithms
for predicting aircraft taxi-out times: Tampa Bay", *TR-C* 18(6). 116 citations.**
([doi](https://doi.org/10.1016/j.trc.2010.03.003)) _(The abstract was not reachable.)_

---

## 5. The gaps: where our contribution sits

1. **Scale and heterogeneity.** Almost every study above is **a single airport** (Logan, CDG,
   Charlotte, Pudong, Seattle, ZRH+ARN). We found no study that models 11 airports under one
   roof with shared feature definitions. We found **no** published taxi-out study on LTFM or
   LTAI at all.
2. **Retrospective observability.** Idris's queue variable has to be predicted in operation; in
   a post-ops setup it is observable. We saw no study that **measures the information value** of
   that difference. The paper will report two model variants (retrospective / causal); the RMSE
   difference between them is the upper bound of the improvement reachable for real-time
   systems.
3. **De-icing.** In the official indicator the PRC **filters out** flights that de-ice after
   AOBT (ATXOT p.13). Those rows cannot be filtered out when predicting raw taxi-out. In January
   2026 the share of de-icing conditions was LSZH 18% · EHAM 13% · EDDM 11% · LTFM 10% (our own
   METAR analysis, W03). We saw no taxi-out study that models this regime explicitly.

## Citations that need verifying

To be read in full before being used in the paper (currently only at abstract or search level):

- The Ravizza 2020 feature importance ranking (dspace/storre returned 403, institutional access
  needed)
- The Ravizza 2013 accuracy figures within ±1 min (58.21% / 64.05%)
- The full texts of Diana 2018, Balakrishna 2010, Simaiakis 2015
