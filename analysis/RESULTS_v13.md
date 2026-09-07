# Stage-3 results - STUDY_DESIGN v1.3 descriptive analyses

Three descriptive analyses added by STUDY_DESIGN v1.3 (2026-09-03), motivated by
external-reviewer feedback (LBNL) and pre-registered before computation.
Nothing frozen was recomputed: the event population, the attribution columns, the
component map and the control anchors are read from the stage-2 artefacts exactly as
`decompose.py` reads them.

Every number below is read back out of an artefact one of these scripts wrote; nothing
is hand-computed. Provenance is given as **`script.py` -> `artefact` [row selector]**.

```
duration_grounding.py -> analysis/duration_grounding.csv, tact_curve.csv,
                         lead_vs_duration.csv, paper/figures/fig5.pdf
leadtime_box.py       -> analysis/leadtime_box.csv,       paper/figures/fig6.pdf
warning_dynamics.py   -> analysis/dynamics_profile.csv, dynamics_trend.csv,
                         paper/figures/fig7.pdf
```

Primary cell throughout, unchanged: **T2 wide-grid**, **same-component** matching,
**72 h** lookback, **T_act = 6 h**, **-45 d** controls, **energy-weighted**.
Bootstrap seed **20260903**, 2,000 two-level cluster replicates for the T_act band
(turbines resampled with replacement, then events within turbine, percentile CIs -
the same construction as `bootstrap.py`, at a fifth of its replicate count because the
band is drawn at 44 grid points).

### Validation gate (run before anything else)

T2 wide-grid population **4,213 events / 9,386.5 MWh**; energy-weighted decomposition at
T_act = 6 h, same-component 72 h **83.78 / 8.69 / 7.53 %**; count-weighted
**76.76 / 6.67 / 16.57 %**; any-warning energy-weighted **52.90 / 12.77 / 34.33 %**;
same-component warned numerator **979 events / 1,522.8 MWh**. All reproduced exactly.
The T_act curve carries the gate as an assertion: it must pass through 7.53 %, 16.57 %
and 34.33 % at T_act = 6 h or the script aborts.
*(`duration_grounding.py` console, `GATE` lines.)*

---

## A. Downtime-duration grounding (v1.3(a))

### A.1 The duration distribution is extremely bimodal in weight

*(`duration_grounding.py` -> `duration_grounding.csv`
[`metric==duration_quantile, scope==overall`].)*

| weight | p10 | p25 | **p50** | p75 | p90 |
|---|---|---|---|---|---|
| count | 0.030 h | 0.033 h | **0.176 h** | 0.347 h | 2.097 h |
| energy | 2.007 h | 17.396 h | **52.944 h** | 167.288 h | 595.866 h |

The typical T2 forced outage lasts about **10 minutes**; the typical lost **MWh** sits in
an outage lasting about **53 hours**. The two medians differ by a factor of 300. This is
the same concentration that RESULTS §0.2 reported from the other side (warned outages are
shorter) and it is the single most important context for reading T_act.

### A.2 Where the lost energy sits, by outage duration

*(`duration_grounding.py` -> `duration_grounding.csv`
[`metric==share_duration_ge, scope==overall`].)*

| outage duration at least | share of T2 lost energy | share of T2 events | n events |
|---|---|---|---|
| 1 h | **92.74 %** | 14.43 % | 608 |
| **6 h** | **83.69 %** | 6.24 % | **263** |
| 24 h | **68.14 %** | 2.75 % | 116 |
| 72 h | 42.91 % | 0.83 % | 35 |
| 168 h | 24.47 % | 0.21 % | 9 |

**83.69 % of T2 lost energy sits in the 263 outages (6.2 % of events) that last at least
6 hours.** Restricted to the warned population the concentration is sharper still:
**95.28 %** of same-component-warned lost energy is in outages of at least 6 h (45 of the
979 warned events, 1,450.9 of 1,522.8 MWh), and 84.04 % for any-warning.
*(same artefact, [`scope==warned:same`] and [`scope==warned:any`, `weight==energy`].)*

Per family the energy-weighted median duration ranges over three orders of magnitude
(`electrical` 1,099.9 h, `generator` 387.6 h, `converter` 60.3 h, `pitch` 55.3 h,
`anemometry` 64.5 h, `drivetrain` 37.3 h, **`tower` 1.33 h**).
*(same artefact, [`metric==duration_quantile, scope==family:*, weight==energy`].)*
`tower` is the exception that matters: 1,024 MWh of T2 lost energy in outages whose
energy-weighted median is under 90 minutes. A 6 h action horizon is genuinely too long
for that family, and it is the only large-energy family of which that is true.

### A.3 Actionable-unacted share as a continuous function of T_act

*(`duration_grounding.py` -> `tact_curve.csv` [`is_reference==True`]; 44 grid points on a
log grid 0.5-72 h with the four reference points inserted, 2,000 reps, seed 20260903.)*

| reference | T_act | same-comp, energy | 95 % band | any-warning, energy | 95 % band | same-comp, count |
|---|---|---|---|---|---|---|
| **T_act primary** | **6.00 h** | **7.53 %** | [1.94, 16.31] | **34.33 %** | [18.38, 52.10] | 16.57 % |
| duration p25 (E) | 17.40 h | 6.62 % | [1.19, 15.42] | 31.36 % | [16.26, 48.57] | 14.76 % |
| duration p50 (E) | 52.94 h | **0.86 %** | [0.07, 2.28] | **10.55 %** | [5.28, 18.94] | 8.24 % |
| duration p75 (E) | 167.29 h | 0.00 % | - | 0.00 % | - | 0.00 % |

The p75 reference (167.29 h) lies **beyond the frozen 72 h lookback**, so no lead can
reach it and the share there is zero by construction, not by evidence. The row is written
to the CSV with `beyond_lookback==True` and must be reported that way or not at all.

The curve is close to flat from 0.5 h to about 6 h (same-component energy-weighted moves
only from 12.80 % at 0.5 h to 7.53 % at 6 h), then falls steeply between 24 h and 53 h.
*(`tact_curve.csv` [`rule==same, weight==energy, T_act_h==0.5`].)*
Fig. 5 (bottom) is the general result; the 6 h point is one reading of it.

### A.4 Lead versus the outage's own eventual duration

*(`duration_grounding.py` -> `lead_vs_duration.csv`.)*

Among the 979 same-component-warned T2 events, the warning arrived at least as early as
the outage would eventually last for **826 events (84.37 %)** but only **14.92 % of warned
lost energy** (227.2 of 1,522.8 MWh). Any-warning: 2,392 of 2,652 events (90.20 %) and
30.22 % of warned lost energy. The sign of the finding flips with the weighting, exactly
as the lead-time medians do.

Joint quadrant split at lead >= 6 h by duration >= 6 h, same-component, share of **warned
lost energy** (share of warned events in brackets):

| | duration >= 6 h | duration < 6 h |
|---|---|---|
| **lead >= 6 h** | **42.99 %** (2.35 %, n=23) | 3.42 % (68.95 %, n=675) |
| **lead < 6 h** | **52.29 %** (2.25 %, n=22) | 1.30 % (26.46 %, n=259) |

Any-warning: 61.91 % / 10.98 % / 22.13 % / 4.97 % by energy. Both quadrant sets sum to
1.000000 by weight *(console `SANITY quadrants sum`)*.

**45 events carry 95.3 % of the warned lost energy, and they split almost evenly on
whether the warning arrived 6 h ahead.** The whole same-component headline turns on 23
events. This is the effective-N problem of PROFILE §7 in its most concrete form and
belongs in the paper's limitations, next to the existing leave-one-out analysis.

---

## B. Lead-time dispersion by component family (v1.3(b))

*(`leadtime_box.py` -> `leadtime_box.csv`; 72 h window, T2 wide-grid, families with at
least 10 same-component-warned events, ordered by the family's share of T2 lost energy.)*

| group | n warned | E warned (MWh) | p5 | p25 | **median** | p75 | p95 | **E-wtd median** |
|---|---|---|---|---|---|---|---|---|
| pitch | 46 | 545.2 | 0.33 h | 1.66 h | **7.57 h** | 19.88 h | 35.60 h | **1.75 h** |
| tower | 32 | 27.8 | 0.65 h | 3.61 h | **35.73 h** | 42.03 h | 62.71 h | **36.27 h** |
| drivetrain | 33 | 190.1 | 0.20 h | 1.04 h | **11.31 h** | 39.38 h | 57.85 h | **0.69 h** |
| anemometry | 851 | 331.9 | 0.001 h | 3.43 h | **41.98 h** | 64.34 h | 71.48 h | **3.21 h** |
| all same-component | 979 | 1,522.8 | 0.001 h | 3.04 h | **37.99 h** | 62.74 h | 71.36 h | **3.04 h** |
| all any-warning | 2,652 | 4,420.8 | 0.07 h | 2.70 h | **30.14 h** | 57.64 h | 70.76 h | **24.37 h** |

Only four families clear the 10-warned-event floor, and **anemometry supplies 851 of the
979 warned events while carrying 332 of 9,386 MWh** - the pooled ECDF in fig. 2 is very
nearly the anemometry curve. The two overall rows reproduce `leadtime_stats.csv` exactly
in n, median and energy-weighted median *(console `SANITY` lines)*.

The count-weighted and energy-weighted medians disagree by a factor of 4 to 16 in every
energy-material family (pitch 7.57 h vs 1.75 h; drivetrain 11.31 h vs 0.69 h), and agree
only in `tower`, whose warned events carry almost no energy. Restated: **in the families
where the energy is, the big warned events are warned an order of magnitude later than the
typical warned event.** Share of warned lost energy with lead >= 6 h: pitch 20.39 %,
drivetrain 10.43 %, tower 62.20 %, anemometry 40.45 %, all same-component 46.40 %
*(`leadtime_box.csv` [`frac_ge_6h_energy`])*.

---

## C. Warning dynamics before failure (v1.3(c))

The warning rows were re-joined from `warnings.parquet` because `attribution.parquet`
keeps only the earliest match. The join reproduces the frozen `same_n_72h` and
`any_n_72h` columns **exactly** (26,174 and 35,628 rows) before anything is computed from
it *(`warning_dynamics.py` console, `JOIN CHECK` lines)*; window, timestamp convention and
never-match families are those of `attribute.py`.

### C.1 Pooled rate profile

*(`warning_dynamics.py` -> `dynamics_profile.csv`; hourly bins, warnings per anchor-hour.)*

| rule | population | anchors | warning rows | mean rate | 72-66 h | 0-6 h | ratio |
|---|---|---|---|---|---|---|---|
| same-component | warned events | 979 | 26,174 | 0.3713 | 0.2988 | **1.3590** | **4.55x** |
| same-component | their -45 d controls | 973 | **8** | 0.0001 | 0.0002 | 0.0000 | - |
| any-warning | warned events | 2,652 | 35,628 | 0.1866 | 0.1470 | **0.7207** | **4.90x** |
| any-warning | their -45 d controls | 2,633 | 1,267 | 0.0067 | 0.0054 | 0.0049 | **0.90x** |

Context rows for the whole T2 population are in the same artefact
[`population==events_all`, `controls_all`]: 0.0863 vs 0.0002 (same-component) and
0.1175 vs 0.0066 (any-warning) warnings per anchor-hour.

**The warning rate accelerates about 4.6x into the final 6 hours; the matched control
profile is flat (0.90x).** The acceleration is therefore a property of the run-up to
failure, not of the log's background chatter. Under the same-component rule the control
windows contain 8 warning rows in total across 973 windows, which is why the
same-component enrichment CI in RESULTS §3 is uselessly wide - the same near-empty
denominator, seen as a time series.

### C.2 Per-event trend

*(`warning_dynamics.py` -> `dynamics_trend.csv`; warned T2 events with at least 3 matching
warning rows. Rate ratio = rate in the last 24 h over rate in the prior 48 h; Laplace
statistic on warning start times within the 72 h window, positive = clustering toward the
outage.)*

| statistic | same-component | any-warning |
|---|---|---|
| n events / MWh | 799 / 840.5 | 1,752 / 2,350.2 |
| rate ratio > 1, count-weighted | **76.35 %** | 72.77 % |
| rate ratio > 1, energy-weighted | **99.21 %** | 77.65 % |
| rate ratio >= 2 (doubling), count | 66.71 % | 64.84 % |
| rate ratio >= 2 (doubling), energy | **99.12 %** | 75.60 % |
| median rate ratio, count-weighted | **3.33** | 4.00 |
| median rate ratio, energy-weighted | **infinite** | 8.00 |
| Laplace > 0, count / energy | 83.35 % / 99.25 % | 78.31 % / 84.07 % |
| Laplace > 1.645, count / energy | 70.84 % / 98.63 % | 62.79 % / 57.14 % |
| median Laplace, count | 3.35 | 2.59 |

The energy-weighted median rate ratio is **infinite** and this is a real reading, not a
defect: 229 of the 799 same-component events have **zero** matching warning rows before
the last 24 h, and they carry more than half the energy, so the median MWh sits in an
event whose prior-48 h rate is zero. It is the same fact as the 3.04 h energy-weighted
median lead in RESULTS §4, expressed as a rate. Report it as "the median warned MWh has no
same-component warning at all before the final 24 h", not as a number.

---

## D. Evaluation of the STUDY_DESIGN v1.3(a) decision rule

> *v1.3(a): if the duration evidence shows 6 h is indefensible as a conservative floor
> (e.g. the majority of warned lost energy sits in outages resolved faster than 6 h), the
> paper re-anchors its headline on the data-derived p50 threshold and says so; otherwise
> 6 h stays primary with the curve as the general result.*

**The trigger does not fire, and by a wide margin. T_act = 6 h stays primary.**

The rule's own test is the share of warned lost energy in outages resolved faster than
6 h. That share is **4.72 %** under the same-component rule (100 % - 95.28 %) and
**15.96 %** under any-warning
*(`duration_grounding.py` -> `duration_grounding.csv` [`scope==warned:same` /
`warned:any`, `metric==share_duration_ge`, `stat==ge_6h`, `weight==energy`])*. Over the
whole T2 population the figure is 16.31 % (100 % - 83.69 %). Nowhere near a majority: the
overwhelming bulk of the lost energy sits in outages that last very much longer than the
action horizon, whose energy-weighted median duration is **52.9 h**, nine times T_act.
6 h is not merely defensible as a conservative floor, it is conservative by roughly an
order of magnitude, and the paper can now say so from data rather than from assertion.

Three qualifications go with that verdict, all of which should be written into the paper
rather than left in this file:

1. **Conservative on duration is not conservative on the headline.** A duration-matched
   threshold makes the headline *smaller*, not larger. Reading the curve at the
   energy-weighted duration p50 (52.94 h) gives a same-component actionable-unacted share
   of **0.86 % [0.07, 2.28]** and an any-warning share of **10.55 % [5.28, 18.94]**
   *(`tact_curve.csv` [`ref_label=="duration p50 (E)"`, `weight==energy`])*, against
   7.53 % and 34.33 % at 6 h. So 6 h is the *permissive* end of the defensible range. The
   honest statement is that the headline is 7.5 % at a dispatch-realistic horizon and
   falls below 1 % if one insists the warning must precede the outage by as long as the
   outage itself lasts. The curve, not the point, is the result.

2. **The floor is family-dependent.** `tower` (1,024 MWh, 10.9 % of T2 lost energy) has an
   energy-weighted median duration of 1.33 h, so a 6 h horizon exceeds the whole outage
   for most of that family's energy. Every other energy-material family has an
   energy-weighted median duration above 37 h.

3. **The 72 h lookback, not T_act, is the binding constraint at the long end.** The
   energy-weighted duration p75 is 167.3 h, beyond the attribution window entirely; the
   curve cannot be read there. If a reviewer pushes on duration-matched thresholds, the
   answer is a wider lookback in a future revision, not a different reading of this one.

No frozen definition is changed. `component_map.csv`, the event and control definitions,
the 72 h lookback and T_act = 6 h all stand; v1.3 adds the curve, the dispersion and the
dynamics around them.

---

## E. Data surprises

1. **The count and energy medians of outage duration differ by 300x** (0.176 h vs 52.9 h).
   Anything stated about "a typical outage" must name its weighting.
2. **`tower` breaks the pattern**: large lost energy (1,024 MWh) in short outages
   (energy-weighted median 1.33 h). It is the only energy-material family for which the
   6 h floor is too coarse.
3. **The same-component headline rests on 23 events.** Of the 45 warned events that carry
   95.3 % of warned lost energy, 23 had lead >= 6 h and 22 did not.
4. **Lead >= own duration flips sign with weighting**: 84.4 % of warned events but 14.9 %
   of warned energy.
5. **Same-component control windows are almost empty** (8 warning rows across 973
   windows), so the control-adjusted same-component statistics are denominator-starved by
   construction. Consistent with the wide enrichment CI already reported in RESULTS §3.
6. **The energy-weighted median rate ratio is infinite** (see C.2) - a genuine reading of
   a warning channel that stays silent until the last day before the big events.

## F. Figures

| file | content |
|---|---|
| `paper/figures/fig5.pdf` | top: T2 outage-duration histogram, log x, count share per bin with the lost-energy share overlaid; bottom: actionable-unacted share vs T_act, log x, same-component solid with 95 % band, any-warning dashed, markers at 6 h and at the energy-weighted duration p25 / p50 |
| `paper/figures/fig6.pdf` | lead-time box-whisker by component family and overall, log y, whiskers 5th/95th percentile, box IQR, line median, diamond = energy-weighted median |
| `paper/figures/fig7.pdf` | warning rate vs hours before outage start, log y, events solid and matched -45 d controls dashed, both rules |

House style matches `figures.py`: 3.5 in IEEE column width, 8 pt base type, Okabe-Ito
palette, vector PDF with TrueType (Type 42) fonts and no Type 3, no titles, plain hyphens
only. Verified with `pdffonts`: all three files embed CID TrueType subsets only.

Page budget: the paper is currently 5/5 pages, so these three figures cannot all be
added. Fig. 5 (bottom panel alone) is the one that answers the reviewer; fig. 6 and
fig. 7 are supporting material for a response letter or an extended preprint.
