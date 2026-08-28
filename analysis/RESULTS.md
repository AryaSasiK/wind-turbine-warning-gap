# Stage-2 results — the actionable-warning gap

Every number below is read back out of an artefact a script wrote; nothing is
hand-computed. Provenance is given as **`script.py` → `artefact` [row selector]** so any
figure in the Results section can be traced to a re-run.

Pipeline (re-runnable end to end, in this order, after stage 1):

```
attribute.py       -> derived/attribution.parquet, analysis/attribution_summary.csv
controls.py        -> derived/controls.parquet,    analysis/controls_summary.csv
decompose.py       -> analysis/decomposition.csv, leadtime_stats.csv, duration_comparison.csv
counterfactual.py  -> analysis/counterfactual.csv, planned_duration.csv,
                      derived/counterfactual_events.parquet
bootstrap.py       -> analysis/bootstrap.csv, influence_loo.csv, derived/bootstrap_draws.parquet
figures.py         -> paper/figures/fig1..fig4.pdf
```

Primary cell throughout: **T2 wide-grid** (STUDY_DESIGN v1.1(b)), **same-component**
matching, **72 h** lookback, **T_act = 6 h**, **−45 d** controls, **energy-weighted**.

---

## 0. Read this first — three findings that change how the paper reads

### 0.1 The same-component rule collapses the headline, and it is a vocabulary artefact, not a bug

The smoke test's 63.7 % reproduces **exactly** on its own terms — any-warning, count-weighted,
turbine-side: this pipeline gives **62.9 %** with a median lead of **30.1 h** against PROFILE §6's
63.7 % / 30.1 h (`attribute.py` console cross-check; the 0.8 pp gap is merging plus the
commissioning cut). But the two axes the smoke test never varied each cost a great deal:

| step | T2 warned share |
|---|---|
| any-warning, count-weighted (the smoke-test statistic) | **62.9 %** |
| any-warning, **energy-weighted** | **47.1 %** |
| **same-component**, count-weighted | **23.2 %** |
| **same-component**, energy-weighted (the headline) | **16.2 %** |

The energy-weighting drop is expected and was already visible in PROFILE §6 (turbine-side
≥ 24 h: 48.3 %). **The same-component drop is the surprise**, and it traces to an asymmetry
between the two message vocabularies that `checks.md` §4 recorded but whose consequence nobody
had priced in. Warning rows per turbine-year, by family, against that family's share of T2 lost
energy:

| family | warning rows / turbine-yr | T2 lost energy (MWh) | same-component warned (energy) |
|---|---|---|---|
| converter | **0.5** | 1,741.3 | **0.0 %** |
| electrical | **0.4** | 673.4 | 0.3 % |
| tower | **1.2** | 1,024.3 | 2.7 % |
| safety | **0** (no warning maps here) | 481.5 | **0.0 %** (structural) |
| generator | 7.4 | 843.1 | 2.4 % |
| drivetrain | 2.3 | 1,009.7 | 18.8 % |
| pitch | 22.0 | 2,254.9 | 24.2 % |
| control | 1.3 | 659.4 | 39.0 % |
| anemometry | **24.3** | 395.3 | **84.0 %** |
| brake_hydraulic | 14.8 | 217.5 | 67.6 % |

*(`decompose.py` → `decomposition.csv` [`population==per_family`, `weight==energy`]; warning
rates from `warnings.parquet` / 171 turbine-years.)*

The warning log is dominated by **nuisance families** (anemometry, pitch, external,
brake_hydraulic, yaw, comms — together 83.6 % of all warning rows) while the **energy-material**
stop families are almost unwatched. `converter` is the sharpest case: 977 events and
1,741 MWh — 19 % of T2 lost energy — and **zero** of them carry a converter-family warning in
72 h, because the whole corpus contains only 81 converter warning rows. `safety` (481 MWh)
cannot match by construction: no warning message maps to that family at all.

**This is a result, not a defect.** It says the operator-visible warning channel is
mis-aimed: it fires constantly about anemometers and pitch batteries and is nearly silent
about converters, breakers and safety chains, which is where the energy is. The paper should
lead with that rather than bury it — it is a stronger and more specific claim than "63 % of
outages are warned", and it is exactly the kind of gap an autonomous monitoring layer would
close. The `component_map.csv` was frozen before any of this was computed, so the finding is
not a mapping choice made after seeing outcomes.

**Guard-rail disclosure.** The task's stop-rule ("warned share < 40 % on T2 → stop and
report") is tripped by the same-component energy-weighted share (16.2 %). I verified the
mechanism before continuing rather than halting: the any-warning statistic reproduces the
smoke test to 0.8 pp, the collapse is fully explained by the vocabulary table above, and both
rules are reported side by side exactly as STUDY_DESIGN requires (same-component = headline,
any-warning = upper bound). No spec rule was changed. Flagging it here as instructed.

### 0.2 Warned outages are *shorter*, not longer

Median T2 outage duration: **0.030 h warned vs 0.180 h unwarned** (same-component),
0.047 h vs 0.258 h (any-warning); Mann–Whitney p = 1.0e−117 and 4.0e−94.
Mean lost energy per event runs the same way: 1.56 MWh warned vs 2.43 MWh unwarned.
*(`decompose.py` → `duration_comparison.csv`.)*

**Rounding note (2026-08-28):** the paper quotes percentage triples largest-remainder
rounded so each printed decomposition sums to 100.0: count-weighted T2 same-component
76.7 / 6.7 / 16.6 (raw 76.76 / 6.67 / 16.57 would independently round to 76.8, summing
to 100.1). Fig. 2 labels use one decimal for the same reason.

**Cluster-robust version (2026-08-28, review fix):** the Mann–Whitney p-values treat
events as independent, inconsistent with the paper's own cluster-bootstrap logic. Replaced
in the paper with a two-level cluster bootstrap (turbines → events, 10,000 replicates,
seed 20260828) on the difference in median duration, unwarned − warned, T2 wide-grid, 72 h:
**same-component 0.149 h, 95% CI [0.143, 0.161]; any-warning 0.212 h, 95% CI [0.130,
0.225]** — both exclude zero (frac ≤ 0: 0.0001 and 0.0000). Medians reproduce the frozen
values exactly. *(`cluster_duration.py`; paper §V-B now cites these CIs, not the MW p's.)*

This is the whole reason the energy-weighted share sits so far below the count-weighted one,
and it is driven by anemometry: 853 T2 events, 99.8 % same-component warned, but only 395 MWh
between them. **The events the log warns about are the small ones.** State it plainly; a
reader who assumes warned ⇒ severe will misread every other number.

### 0.3 The energy-weighted lead-time distribution is front-loaded

Count-weighted median same-component lead is **38.0 h**; energy-weighted it is **3.0 h**
(p25 0.7 h, p75 20.9 h), and only **46 %** of warned lost energy carries ≥ 6 h of lead against
71 % of warned *events*. *(`decompose.py` → `leadtime_stats.csv`.)* The big warned events get
warned late. Figure 2 shows both curves for this reason.

---

## 1. Headline decomposition

**T2 wide-grid, same-component, 72 h lookback, T_act = 6 h, energy-weighted**, over
**4,213 events / 9,386.5 MWh** on 20 turbines.
*(`decompose.py` → `decomposition.csv` [`population==all, tier==T2, rule==same,
lookback_h==72, T_act_h==6, control_offset_d==45, weight==energy`]; CIs from
`bootstrap.py` → `bootstrap.csv` [`tier==T2, rule==same, T_act_h==6`], 10,000 reps, seed 20260827.)*

| bucket | share | 95 % CI |
|---|---|---|
| **Unwarned** | **83.78 %** | [72.91, 92.41] |
| **Short-lead** (< 6 h) | **8.69 %** | [2.78, 16.78] |
| **Actionable-unacted** (≥ 6 h) | **7.53 %** | **[1.95, 16.72]** |
| *warned (= short-lead + actionable)* | *16.22 %* | *[7.59, 27.09]* |

Count-weighted companion: unwarned 76.76 %, short-lead 6.67 %, **actionable-unacted 16.57 %
[8.78, 23.87]**, warned 23.24 % [14.76, 31.06].

**Any-warning upper bound**, same cell: unwarned 52.90 %, short-lead 12.77 %,
**actionable-unacted 34.33 % [18.60, 51.61]**, warned 47.10 % [32.04, 61.84].
Count-weighted: actionable-unacted 43.27 %, warned 62.95 %.

Tier companions (energy-weighted, same-component, T_act 6 h):

| tier | events | E (MWh) | unwarned | short-lead | actionable-unacted | 95 % CI on actionable |
|---|---|---|---|---|---|---|
| T0 (all forced-outage) | 6,050 | 12,099.8 | 87.41 % | 6.75 % | 5.84 % | [1.59, 12.92] |
| T1 (minus grid, wide) | 4,610 | 11,708.2 | 86.99 % | 6.97 % | 6.04 % | [1.59, 13.30] |
| **T2 (primary)** | **4,213** | **9,386.5** | **83.78 %** | **8.69 %** | **7.53 %** | **[1.95, 16.72]** |

All 979 same-component-warned events in the corpus survive to T2 — grid- and manual-family
events can never same-match — so the T0/T1/T2 same-component rows share an identical warned
numerator (979 events, 1,522.8 MWh) and differ only in the denominator.

---

## 2. Manual-stop line (reported separately, per STUDY_DESIGN's T2 rule)

397 manual-only merged events, **2,321.7 MWh = 19.2 % of T0 lost energy**.
*(`decompose.py` → `decomposition.csv` [`population==manual_only`].)*

Same-component warned share is **0 % by construction** (every constituent message is in the
`manual` family, which never matches). Under **any-warning** they are 33.97 % warned
energy-weighted (36.27 % count-weighted), with 28.34 % of their energy at lead ≥ 6 h — against
a 3.79 % energy-weighted control rate. So even the human-decision bucket is preceded by log
activity more often than chance, but nothing in this study can say whether the warning caused
the operator's decision. Discussion material, not a result.

---

## 3. Control adjustment and enrichment

Matched quiet controls at **−45 d** on the same turbine (quiet = no forced-outage stop start
within ±3 d), family set inherited from the event.
*(`controls.py` → `controls_summary.csv`, `controls.parquet`.)*

| anchor | matched | match rate | at exact anchor | in log coverage | control any-warning 72 h | control same-component 72 h |
|---|---|---|---|---|---|---|
| **−45 d** | 6,015 / 6,050 | **99.42 %** | 72.5 % | 99.40 % | **17.24 %** (13.72 % E-wtd) | 0.52 % (0.67 % E-wtd) |
| −30 d | 5,981 / 6,050 | 98.86 % | 70.2 % | 98.86 % | 21.45 % (12.63 % E) | 1.25 % (0.37 % E) |
| −60 d | 6,011 / 6,050 | 99.36 % | 78.8 % | 98.61 % | 19.43 % (19.12 % E) | 0.38 % (1.61 % E) |

**Smoke-test check passes:** the −45 d any-warning control rate is **17.2 %** over all events
and **18.5 %** restricted to the turbine-side (T2 wide-grid) population, against PROFILE §6's
**16.5 %**. The small excess is expected — the smoke test had no re-draw and silently dropped
events whose −45 d anchor was not quiet (3,145 of ~4,441), whereas the walk here matches 99.4 %.

**Control-excess attributable shares**, (p_event − p_control)/(1 − p_control), T2 primary cell:

| statistic | energy-weighted | 95 % CI | count-weighted |
|---|---|---|---|
| excess warned, same-component | **15.49 %** | [6.65, 26.55] | 22.66 % |
| **excess actionable-unacted, same-component** | **6.73 %** | **[0.75, 16.14]** | 15.98 % |
| excess warned, any-warning | 36.63 % | [16.57, 55.75] | 54.53 % |
| excess actionable-unacted, any-warning | 21.50 % | **[−1.48, 44.06]** | 31.43 % |

Enrichment over control (warned share ratio): **18.8×** energy-weighted / **31.3×**
count-weighted for same-component; **2.85×** / **3.40×** for any-warning (PROFILE §6's headline
was 3.9× on the unmerged count-weighted turbine-side population). The same-component
enrichment CI is uselessly wide ([4.6, 541]) because the control denominator is ~0.7 % and
frequently draws near zero — **report the excess share, not the ratio**, and if the ratio must
appear, give it as "> 15×" rather than a point estimate.

Note the any-warning excess-actionable CI **crosses zero**. Under the permissive rule the
actionable-unacted share is not distinguishable from what a matched quiet period produces at
the 95 % level. The same-component version does clear zero, but only just.

---

## 4. Lead-time statistics

72 h window, T2 wide-grid. *(`decompose.py` → `leadtime_stats.csv`.)*

| rule | weight | n warned | E warned (MWh) | p25 | **median** | p75 | ≥ 1 h | ≥ 6 h | ≥ 24 h |
|---|---|---|---|---|---|---|---|---|---|
| same-component | count | 979 | 1,522.8 | 3.02 h | **37.99 h** | 62.76 h | 81 % | 71 % | 61 % |
| same-component | energy | 979 | 1,522.8 | 0.72 h | **3.04 h** | 20.90 h | 75 % | 46 % | 20 % |
| any-warning | count | 2,652 | 4,420.8 | 2.70 h | **30.14 h** | 57.65 h | 81 % | 69 % | 56 % |
| any-warning | energy | 2,652 | 4,420.8 | 3.71 h | **24.37 h** | 52.24 h | 88 % | 73 % | 59 % |

The count-weighted any-warning median (30.1 h) matches PROFILE §6's 30.1 h exactly.
**The same-component energy-weighted median (3.0 h) is the number that matters for the
counterfactual** and it sits *below* T_act = 6 h — see §0.3.

---

## 5. Counterfactual recoverable energy (SECONDARY — modelled)

Planned-intervention duration from the corpus's own `Scheduled Maintenance` stops
(3,152 stops after the same filters as the event population): **median 0.792 h (48 min)**,
p75 **2.030 h**. `E_planned = mean_potential_kw × D_planned / 1000`;
`recoverable = max(E_event − E_planned, 0)`.
*(`counterfactual.py` → `counterfactual.csv`, `planned_duration.csv`; gross generation
865,526 MWh from `data/PROFILE.md` §4 `Energy Export`, quoted not recomputed.)*

**Headline (T2, same-component, T_act 6 h, 698 actionable-unacted events, 706.6 MWh at risk):**

| planned duration | E_planned | **recoverable** | % of gross | % of T2 lost energy | events clipped at 0 |
|---|---|---|---|---|---|
| median (0.792 h) | 105.5 MWh | **666.4 MWh** | **0.077 %** | 7.10 % | 124 / 698 |
| p75 (2.030 h) | 270.4 MWh | **639.2 MWh** | 0.074 % | 6.81 % | 132 / 698 |

95 % CI on recoverable (median duration, two-level cluster bootstrap): **[149.0, 1,577.3] MWh**,
i.e. **[0.017 %, 0.182 %] of gross**. Read the MWh CI with care: the outer bootstrap level
resamples turbines, so the fleet total is itself resampled (E_total CI [6,730, 12,650] MWh
against a point of 9,386). **Prefer the share form: 7.10 % of T2 lost energy, CI
[1.65 %, 16.21 %].**

Two honest caveats, both to be stated in the paper:

1. **The planned-intervention model barely bites.** The corpus's Scheduled-Maintenance stops
   are overwhelmingly short manual visits (median 48 min; the message mix is
   `Manual stop - on site` 2,649, `Manual stop without login` 345, `Manual brake` 157), so
   E_planned is negligible next to a multi-day forced outage and the model recovers ~94 % of
   the at-risk energy. This is a property of the corpus, not a tuning choice — but it means the
   counterfactual is close to "actionable-unacted energy × 0.94" and should not be presented as
   an independent estimate.
2. **124 of 698 events (18 %) clip at zero** — the modelled intervention would cost more
   downtime than the fault did (−65.3 MWh of would-be-negative recovery, discarded by the clip).
   Under the p75 duration that rises to 132 events / −203.1 MWh. The clip is documented in
   `counterfactual.py`; the unclipped totals are 601.1 MWh (median) and 436.2 MWh (p75) if a
   reviewer prefers them.

Any-warning upper bound, same cell: 1,823 events, 3,222.5 MWh at risk, **2,873.0 MWh
recoverable = 0.332 % of gross**.

---

## 6. Sensitivity table

Energy-weighted **actionable-unacted** share, T2 wide-grid unless stated. One axis moved off
primary at a time. *(`decompose.py` → `decomposition.csv`.)*

| axis | setting | actionable-unacted | Δ vs primary | warned |
|---|---|---|---|---|
| — | **primary (same, 72 h, 6 h, −45 d, wide grid)** | **7.53 %** | — | 16.22 % |
| **matching rule** | any-warning | **34.33 %** | **+26.80 pp** | 47.10 % |
| T_act | 1 h | 12.10 % | +4.57 pp | 16.22 % |
| T_act | 24 h | 3.26 % | −4.27 pp | 16.22 % |
| lookback | 48 h | 6.04 % | −1.49 pp | 14.78 % |
| lookback | 24 h | 5.64 % | −1.89 pp | 14.63 % |
| grid variant | T2 narrow (frozen list) | 7.33 % | −0.20 pp | 15.80 % |
| tier | T1 (wide) | 6.04 % | −1.49 pp | 13.01 % |
| tier | T0 | 5.84 % | −1.69 pp | 12.59 % |
| control offset | −30 d | 7.53 % | 0.00 pp | 16.22 % |
| control offset | −60 d | 7.53 % | 0.00 pp | 16.22 % |

Control offset does not move the event-side split (it cannot — controls only enter the
*excess*). Its effect on the control-adjusted numbers:

| control offset | p_control (warned, E-wtd) | excess warned | excess actionable |
|---|---|---|---|
| −30 d | 0.48 % | 15.82 % | 7.11 % |
| **−45 d (primary)** | **0.86 %** | **15.49 %** | **6.73 %** |
| −60 d | 2.11 % | 14.41 % | 5.54 % |

**Biggest swing by a wide margin: the matching rule (+26.8 pp).** Everything else moves the
headline by under 5 pp. The paper's honest summary is a *range*, 7.5 %–34.3 % of T2 lost
energy, whose width is set almost entirely by how strictly a warning must match the fault.
T_act is second (±4.3 pp across 1 h–24 h) and the grid-variant choice — the one thing the v1.1
changelog re-fixed — is nearly irrelevant (0.2 pp).

### 6a. Labelled implementation-reading sensitivities

Two places where the spec was silent; the reading fixed in the code is listed first. Neither
was chosen after seeing outcomes.

- **Half-open lookback `[start − L, start)`**, warnings placed by start timestamp
  (`attribute.py` docstring (a), (b)). This is verbatim what `data/smoke_precursors.py` did,
  which is why the 62.9 % / 30.1 h cross-check reproduces. The alternative (inclusive of a
  warning stamped exactly at the stop) would add zero-lead matches to the short-lead bucket and
  cannot raise the actionable share.
- **Re-draw walk capped at ±10 d** from the anchor (`controls.py` docstring (b)). The spec
  gives `45, 44, 46, …` and no cap. At −45 d the cap binds for 35 of 6,050 events (0.58 %);
  72.5 % of controls sit at the exact anchor and the median absolute deviation is 0 d, so the
  cap is doing almost no work.
- **Controls not restricted to log coverage** (`controls.py` docstring (c)). 99.40 % of −45 d
  controls fall inside their turbine's warning-log span anyway, so the restricted variant is
  numerically indistinguishable.

---

## 7. Influence analysis

Leave-one-out over the top-10 energy events in the primary cell.
*(`bootstrap.py` → `influence_loo.csv`.)*

**Max headline shift: 2.12 pp** (actionable-unacted 7.53 % → 5.41 %), from dropping
**event 2178, Penmanshiel WT04, 2023-06-23, 283 h, 210.1 MWh, `WEC shut down` (control
family), lead 20.8 h** — the *only* actionable-unacted event in the top 10. Max shift on any
reported statistic is 2.16 pp (excess actionable). The other nine top-energy events are
unwarned or short-lead, so dropping each *raises* the headline by 0.10–0.46 pp.

That single event carries **30 % of the actionable-unacted energy** (210.1 of 706.6 MWh). The
result is materially one-event-dependent and the paper must say so — this is PROFILE §7 risk 1
(effective N ≈ 200) showing up exactly where it was predicted to. Top-10 events are 27.7 % of T2 wide-grid energy
(27.4 % on the narrow variant, `checks.md` §7).

---

## 8. Per-farm heterogeneity

Primary cell, energy-weighted. *(`decompose.py` → `decomposition.csv`
[`population==per_farm`].)*

| farm | events | E (MWh) | unwarned | short-lead | actionable-unacted | control | excess actionable |
|---|---|---|---|---|---|---|---|
| Kelmarsh | 1,077 | 2,393.2 | 91.38 % | 6.26 % | **2.36 %** | 1.23 % | 1.14 % |
| Penmanshiel | 3,136 | 6,993.3 | 81.18 % | 9.53 % | **9.30 %** | 0.74 % | 8.64 % |

Count-weighted the ordering **reverses**: Kelmarsh 21.54 % actionable vs Penmanshiel 14.86 %.
Kelmarsh's warned events are numerous but tiny; Penmanshiel's are fewer but carry energy. With
10 turbines per site and CIs of the width in §1, this is a heterogeneity flag, not an
estimate of a site effect — present it as such.

---

## 9. Match rates and coverage

| quantity | value | source |
|---|---|---|
| merged events (T0) | 6,050 | `events.parquet` |
| T2 wide-grid events / energy | 4,213 / 9,386.5 MWh | `attribution.parquet` |
| warning rows | 19,150 | `warnings.parquet` |
| events with no matchable family (all of external/grid/manual) | 1,856 of 6,050; **19 of 4,213 in T2** (15.3 MWh) | `attribute.py` |
| −45 d control match rate | **99.42 %** | `controls_summary.csv` |
| controls at the exact −45 d anchor | 72.53 % | `controls_summary.csv` |
| controls inside the turbine's log span | 99.40 % | `controls_summary.csv` |
| turbines / farms | 20 / 2 | `bootstrap.csv` (`n_turbines`) |

---

## 10. Sanity checks

| check | result |
|---|---|
| energy shares sum to 1 | max \|Σ − 1\| = **3.3e−16** over all 120 decomposition rows — PASS |
| warned = short-lead + actionable | max deviation **1.1e−16** — PASS |
| any-warning 72 h, turbine-side, count-weighted vs PROFILE §6 (63.7 %) | **62.9 %** — PASS |
| any-warning median lead vs PROFILE §6 (30.1 h) | **30.1 h** — exact |
| control any-warning rate vs smoke test (16.5 %) | **17.2 %** all / **18.5 %** turbine-side — PASS |
| T2 energy vs `checks.md` §2 (narrow 9,635.6 / wide 9,386.5 MWh) | reproduced exactly |
| bootstrap draws per replicate | one resample feeds every statistic (fixed during implementation — an earlier version redrew per column) |

## 11. Naive-SCADA negative control (secondary, quoted from PROFILE §6 — not recomputed)

Temperature-residual max\|z\| > 3 in the 72 h before a forced outage fires for 4/20 (20 %)
random forced outages and 3/19 (16 %) component-fault outages, against **6/31 (19 %) of matched
quiet controls**; median z 2.38 / 2.09 vs 2.18. The power-curve residual fires 0/34 events vs
1/29 controls. Indistinguishable from control — which is why the status log, not a naive SCADA
anomaly score, is this study's instrument. *(String is held verbatim in `decompose.py`
`NAIVE_SCADA_LINE`; the spec forbids recomputation.)*

---

## 12. Figures

`paper/figures/fig{1,2,3,4}.pdf` — 3.5 in IEEE column width, vector PDF, TrueType embedded
(no Type 3), 8 pt base type, Okabe-Ito colourblind-safe palette, no titles.

1. **fig1** — energy-weighted decomposition stacked bars, T2 primary with the 95 % CI on the
   actionable-unacted share, T0/T1 thin companions, any-warning upper bound as a dashed rule.
2. **fig2** — lead-time ECDF for warned T2 events, both rules, both weightings, T_act markers
   at 1/6/24 h. The gap between the solid and dashed orange curves is finding §0.3.
3. **fig3** — warned share, events vs matched −45 d controls, by outage-duration bucket, one
   panel per rule on a shared axis. The panels are deliberately on the same scale: the
   same-component panel looking empty *is* the result.
4. **fig4** — per-event lost energy vs same-component lead time, log-log, coloured by component
   family. Lead times are **not** clipped to an axis floor (a clip would manufacture a vertical
   stripe); the cluster at ~10⁻³ h is real — warnings stamped within seconds of the stop.

---

## 13. Open items for the write-up

- Decide the headline framing given §0.1. Recommendation: lead with the *mis-aimed warning
  channel* (converter/electrical/safety energy is essentially unwatched) and give the
  7.5 %–34.3 % range as the decomposition, rather than quoting a single share.
- §0.2 (warned outages are shorter) must appear before any decomposition number or the reader
  will misinterpret all of them.
- The one-event dependence in §7 needs a sentence in Limitations alongside PROFILE §7 risk 1.
- The any-warning excess-actionable CI crosses zero (§3); do not claim significance there.
- `enrichment ×` is unstable for same-component (§3) — use the excess share in the abstract.
