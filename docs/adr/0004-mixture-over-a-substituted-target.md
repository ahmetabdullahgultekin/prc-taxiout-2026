# ADR-0004: Predict a mixture, because part of the target is a column we already hold

Date: 2026-09-07 · Status: accepted

## Context

The metric is RMSE over 344,841 departures. On the holdout that mirrors it, 149 rows out of
344,419 have a taxi-out above two hours, and those 0.04% of the rows carry roughly two thirds
of the squared error. Nothing built for the other 99.96% moves the score much: a plain
gradient boosted model scores 474.91, and one model per airport, a global tail transform, a
cap at EUROCONTROL's own two-hour threshold and a physical bound from stand occupancy were all
measured and all failed.

Looking at those rows one at a time rather than in aggregate showed that seventeen of the
twenty-four above six hours had a taxi-out equal to `MVT_TIME - SCHED_TIME` to within six
seconds. Since the target is `MVT_TIME - BLOCK_TIME`, the airport feed's block time on those
rows *is* the scheduled time. Counting it properly: 4.86% of all training rows, 18.4% at Rome
against 1.1% at Zurich, 53.8% at Rome among flights the Network Manager never matched. 333 of
the 435 training rows above two hours are rows of this kind.

Searching every other timestamp in the file found one more identity (`AOBT_3_flt`, 8.25% of
rows, none of them monsters) and, with shifts of half an hour to a day applied, nothing else.

Two things then had to be decided: whether to believe it for 2026, and how to use it.

## Decision

**Believe it, on evidence from 2026 rather than from the mechanism.** The rule cannot be
checked on the ranking set's departures, whose block times are blanked. It can be checked on
its arrivals, which keep every column: an arrival whose in-block time equals its scheduled time
is the same failure at the other end of the turn. That runs at 2.31% in January and July 2025
and 2.42% in the same months of 2026, with the same shape across airports (Rome 8.81 then 9.74,
Frankfurt 0.88 then 0.79). The behaviour belongs to the feed and not to the year.

**Use it as a mixture, not as a rule.** Under a squared loss the conditional mean is

    E[y|x] = P(substituted|x) * sched_offset + (1 - P(substituted|x)) * E[y | x, not]

so the ordinary learner is fitted on the rows that are not substituted and the two are
combined by weight. A hard switch on a threshold was measured and is worse everywhere except
one threshold, and it is worse than the mixture there too.

**Fit the weight rather than classify the identity.** A classifier for "the offset is the
answer" is answering a question one step away from the one that matters, which is "how much of
the offset should this prediction be". The evidence for the difference is that scaling the
classifier's probability above one kept helping, up to a factor of two, while widening the
tolerance that defines the identity made things worse at every scale. So for every training row
the weight that would have minimised the squared error is computed directly,

    w = (y - rest) / (offset - rest),  clipped,

and fitted, with the rows weighted by `(offset - rest)^2`, which is what a wrong weight
actually costs there. The ordinary model's opinion of the training rows must come from out of
fold, or the target collapses to zero and the class silently becomes its inner learner.

## Consequences

On the holdout: 474.91 plain, 393.99 with a classifier weight, 368.52 with that probability
scaled by the best factor it was given, **362.38 with the weight fitted** and no tuned
parameter. An oracle told exactly which rows are substituted scores 413.19, which is worse than
the fitted weight, because the exact identity is narrower than the population that benefits: a
flight landing within a few minutes of its schedule offset is not a match under a ten-second
rule and the offset is still its better prediction.

The fitted model predicts a mean about five percent above the truth's mean, on the holdout and
on the ranking set alike. That is the shape a one-sided clip of the weight target would
produce, and `weight_clip` exists to test it.

This is the second architectural decision in this project driven by where the squared error
lives rather than by where the rows are. The first, one model per segment of the Network
Manager match, is subsumed: those rows overlap heavily with these, and the mixture may take a
segmented learner as its inner model when that is worth its cost.

## Alternatives rejected, with the measurement

| alternative | holdout | why it was dropped |
|---|---:|---|
| one model per airport | 484.10 | worse overall and worse at Rome, the airport it was for |
| cap predictions at 7,200 s | 522.28 | also worse on the board, 411.23 to 488.84 |
| a global tail transform | 472.35 | 2.56 s, inside the paired noise floor |
| the stand occupancy bound | not built | violated on 10% of rows and 70% of the monsters |
| a wider identity tolerance | 393.57 at best | worse than ten seconds at every scale |
| a year-on-year correction from arrival taxi-in | not built | pooled correlation -0.11, sign flips per airport |
