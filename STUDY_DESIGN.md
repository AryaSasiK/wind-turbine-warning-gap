# Study design — The Actionable-Warning Gap (v1, 2026-08-27)

Frozen before outcome computation (the smoke test in `data/PROFILE.md` §6 saw coarse
aggregates only; that exposure is disclosed in the paper). Changes after this point get a
dated changelog entry at the bottom with a reason.

## Research question
Of the energy a wind fleet loses to forced outages, how much was preceded by an explicit,
operator-visible warning in the turbine's own event log — and with how much lead time?
That "warned share" with its lead-time distribution is the empirical case for autonomous
monitoring-and-response: it is energy the existing sensing already flagged.

## Primary instrument (changed from energy.md — reason: PROFILE §6)
Status-log `Warning` rows. Model-free, operator-visible by construction, and
control-validated (63.7% precede turbine-side forced outages vs 16.5% in matched quiet
controls). SCADA normal-behaviour modeling is OUT of the primary analysis: the smoke test
showed naive SCADA precursors are indistinguishable from control, and a tuned model on
~200 effective events is a garden of forking paths. The naive-SCADA negative result is
reported briefly as a secondary finding (it usefully contradicts the assumption that SCADA
anomaly scores are self-evidently actionable).

## Event definition (pre-registered)
- Base event: `Status == 'Stop' AND IEC category == 'Forced outage'`, per turbine.
- **Merge overlapping/nested stop intervals per turbine** (PROFILE §3: 26% overlap, 8,680
  duplicates; WT10 2023-03-24 double-charge). A merged event inherits the constituent
  messages; its lost energy is computed once over the merged window.
- Exclusion tiers, all reported, T2 primary:
  - **T0** all forced-outage stops.
  - **T1** minus grid-side messages (`Externally stopped`, `Grid loss`, `Grid error`,
    `Grid disconnection for self-protection` where IEC-tagged forced outage).
  - **T2 (primary)** T1 minus `Manual stop - remote` / `Manual stop - on site`.
    Manual stops are reported as their own line in results (16.8% of energy — a
    human-decision bucket, relevant to the discussion, not a turbine fault).
- Commissioning exclusion: drop pre-COD data (Kelmarsh before 2016-04-15, Penmanshiel
  per-turbine COD 2016-09-01).

## Warning attribution
- Lookback window: 72 h before merged-event start (sensitivity: 24 h, 48 h).
- Two matching rules, both reported:
  - **Any-warning** (upper bound): any `Warning` row on the same turbine in window.
  - **Same-component** (conservative, headline): warning whose component family matches
    the stop's component family. Component families are a fixed mapping of the 83 stop
    messages + 78 warning messages into ~10–15 families (drivetrain, converter, pitch,
    yaw, anemometry, brake, tower, comms, …), drafted from message semantics and
    `Service contract category`, saved as `analysis/component_map.csv`, and frozen after
    orchestrator review BEFORE outcomes are computed. Warnings with no plausible fault
    semantics (e.g. `P output externally reduced`) are mapped to an "external" family that
    never matches turbine-side stops.
- Control adjustment: for each event, a matched control at −45 d on the same turbine,
  verified quiet (no forced-outage stop within ±3 d; re-draw at −44/−46… if not quiet).
  Report raw warned share AND control-excess attributable share
  ((p_event − p_control)/(1 − p_control), energy-weighted analogue). Sensitivity: −30 d,
  −60 d controls.

## Decomposition (energy-weighted, headline result)
Per merged event, lost energy E = Σ(`Cascading potential power` − `Power`)⁺ × 10 min over
the event window (validated vs Greenbyte to ratio 1.0004, PROFILE §5). Three-way split of
T2 lost energy:
1. **Unwarned** — no same-component warning in 72 h.
2. **Short-lead** — warned, lead < T_act (warning too late to act).
3. **Actionable-unacted** — warned, lead ≥ T_act. ← the headline share
T_act primary = 6 h (a realistic dispatch/remote-intervention horizon), sensitivity
{1 h, 24 h}. Lead = event start − earliest same-component warning in window.

## Counterfactual value (secondary, clearly labeled as modeled)
For actionable-unacted events: recoverable energy if the warning had triggered a planned
intervention = E_event − E_planned, where E_planned uses the corpus's own
`Scheduled Maintenance` stop durations (median, and 75th pct as conservative) placed at
the event's own wind conditions. Reported in MWh and % of gross generation; no monetary
conversion in the results (a £/MWh illustration may appear in Discussion only).

## Statistics
- Energy-weighted shares with two-level cluster bootstrap: resample turbines, then events
  within turbine; 10,000 reps; percentile CIs.
- Influence: leave-one-out over the top-10 energy events; report max headline shift.
- Per-farm splits (Kelmarsh vs Penmanshiel) as heterogeneity check.
- Event-count-weighted decomposition also reported (secondary) so the concentration issue
  (top 200 events = 77% of energy, PROFILE §7 risk 1) is visible, not hidden.
- Descriptives: lead-time distribution (median, IQR, ECDF figure); warned-vs-unwarned
  outage duration comparison.

## Known limitations to state in the paper (from PROFILE §7)
Two UK sites, one OEM (Senvion MM82/92), one operator/platform — external validity
limited. Effective N a few hundred energy-material events; wide CIs expected and shown.
Warning→outage is control-adjusted association, not proven causation; "unacted" does not
imply operator negligence (acting has costs; warnings have false-positive burden — the
control base rate quantifies this and is reported). Derived Greenbyte columns are
undocumented; mitigated by the §5 validation. Jan 2023 hole (Penmanshiel WT01–10) and
2024 coverage (WT11–15 only) stated in Data section.

## Figures (target 4, 5-page budget)
1. Decomposition stacked bar (energy-weighted, T2, with CIs; T0/T1 as thin companions).
2. Lead-time ECDF for warned events, with T_act markers.
3. Warned-share: events vs matched controls, by duration bucket (the 3.9× enrichment).
4. Per-event scatter: lost energy vs lead time (log-log), colored by component family.

## Pipeline outputs (analysis/)
`events.parquet` (merged, tiered, with E), `component_map.csv` (frozen), `warnings.parquet`,
`attribution.parquet`, `decomposition.csv` (+bootstrap draws), `figures/*.pdf`, `RESULTS.md`.

## Changelog
- v1 2026-08-27: initial freeze.
- v1.1 2026-08-27 (before any outcome computation): (a) `component_map.csv` FROZEN as
  reviewed — 162 messages, 13 families + external/grid/manual; the five flagged ambiguous
  calls accepted as drafted (BP-repeat pair → control; brake resistor CHP → pitch;
  time-sync → external; CMS drivetrain msgs → comms; current asymmetry → converter).
  (b) T1/T2 grid exclusion clarified to the semantic rule (all `External stop (grid)`
  service-category messages incl. `Maximum grid frequency`), i.e. stage 1's "wide_grid"
  variant becomes the primary definition; the narrow frozen-list variant is retained as a
  sensitivity. (c) Noted: manual-stop energy share is 19.2% of merged T0 (16.8% was the
  unmerged profile figure); unmerged corpus total corrected to 14,755 MWh (PROFILE §5's
  14,370 truncated 5 member-straddling events).
- v1.2 2026-08-28 (post-draft, independent-review fix; no frozen definition changed):
  the duration-contrast inference (RESULTS §0.2) is reported in the paper as a
  two-level cluster bootstrap 95% CI on the median difference instead of the
  Mann–Whitney p-values, which assumed event independence across the 20-turbine
  cluster structure. Point estimates unchanged; `analysis/cluster_duration.py`.
- v1.3 2026-09-03 (pre-computation; motivated by external reviewer feedback (call with an
  LBNL researcher, 2026-09-03) — NOT by any outcome seen). Three descriptive analyses added; the frozen event/attribution/control
  definitions are unchanged and T_act = 6 h remains the primary cell so all v1.1
  numbers stay comparable:
  (a) **Downtime-duration grounding.** Distribution of T2 outage durations
      (count- and energy-weighted quantiles; histogram, overall and per family).
      The actionable-unacted share is additionally reported as a continuous curve
      in T_act over 0.5–72 h with cluster-bootstrap band, read at data-derived
      reference points = the energy-weighted p25/p50/p75 of T2 outage duration.
      Per-event lead-vs-duration comparison: share of warned lost energy whose
      lead exceeds the outage's own eventual duration.
  (b) **Lead-time dispersion.** Box-whisker of lead-time distributions (both
      rules; per component family for same-component), complementing the ECDF.
  (c) **Warning dynamics before failure.** Pooled profile of warning-row rate vs
      time-to-event over the 72 h window (events vs matched controls), plus a
      per-event trend statistic (Laplace/rate-ratio test of last-24 h vs prior
      48 h) reporting the fraction of warned events with accelerating warnings.
  Decision rule stated in advance for (a): if the duration evidence shows 6 h is
  indefensible as a conservative floor (e.g. the majority of warned lost energy
  sits in outages resolved faster than 6 h), the paper re-anchors its headline on
  the data-derived p50 threshold and says so; otherwise 6 h stays primary with
  the curve as the general result.
- v1.6 2026-09-07 (pre-computation; motivated by the GPT-5.6 round-2 referee report,
  received 2026-09-07 - NOT by any outcome seen). Frozen definitions unchanged; primary
  cell unchanged. Additions, each a robustness or audit artefact the report asked for:
  (a) **Dynamics eligibility sensitivity.** The per-event rate-ratio and Laplace
      statistics of v1.3(c) were computed on events with >=3 matching warning rows,
      a floor fixed at implementation. Recompute at floors >=1, >=2, >=3 and report
      an inclusion flow (events, MWh at each floor) with a declared convention: a
      zero prior-48h count with a positive final-24h count is an infinite ratio and
      counts as "ratio > 1" and "ratio >= 2"; events with zero rows in both windows
      are undefined and excluded at every floor. The >=3 cell stays the reported one
      only if the direction of the result holds at >=1 and >=2.
  (b) **Turbine-year block bootstrap.** Variant of the two-level bootstrap that
      resamples turbines, then turbine-years within turbine as blocks (events inside
      a block kept together), for the headline actionable-unacted share; 10,000
      reps, seed 20260907. Answers the within-turbine temporal-exchangeability
      objection; reported next to the unstratified and farm-stratified intervals.
  (c) **Merged-event audit.** For the 3 merged events with more than one
      constituent: constituents, tier survival, displayed family, same-component
      matches, energy, headline class, and the headline under the alternative rule
      "displayed family only may match".
  (d) **Artefact relabel.** `events_summary.csv` gains a `tier_variant` column
      (narrow vs wide_grid) so plain T1/T2 rows cannot be misread as the primary cell.
  Also appended below the changelog: dated qualifications (not rewrites) of the frozen
  text's "operator-visible" and "realistic" wording, per the report.
- v1.7 2026-09-07 (prespecified before computation; motivated by the GPT-5.6 round-3
  report). Frozen definitions unchanged; primary cell unchanged. Four artefact-level
  additions, each an exposure/labelling fix the report asked for:
  (a) **Real Table I exposure denominator.** Replace the nominal 166.93 turbine-years
      (171 file-years rescaled by 159.91/163.81) with elapsed post-COD SCADA exposure -
      per turbine, the count of 10-minute SCADA grid bins at or after the farm COD that
      lie within the turbine's status-log span - added as `turbine_years_scada_cod()` and
      a `per_ty_scada_cod` column in `warning_rows_by_family.py/.csv` (existing columns
      untouched); per-family rates reported in `analysis/RESULTS_v17.md`.
  (b) **All-four map adjudication in an artefact.** `map_adjudication_summary.csv` gains
      explicit rows for the frozen headline (7.528%), the two new disagreements jointly
      (5.071%), all four jointly (5.441%), and each single disagreement alone, so the
      5.441% quoted in the paper stops living only as prose in RESULTS_v15.md.
  (c) **Figure label rename.** Display labels only in `figures.py`: "Actionable-unacted"
      -> "Long-lead" (and any axis/legend "actionable" text), CSV keys unchanged;
      affected figures regenerated and their printed numbers verified unchanged;
      `ARTEFACT_KEY.md` records `actionable_unacted` = paper class "long-lead".
  (d) **Greek corpus warning count.** Replace the "roughly 300 warnings fleet-wide"
      extrapolation (from three sheets) with a full count of Warning-log (W) and
      Alarm-log (A) rows across WT01-WT10 in the SMD10TOWFGR workbook
      (10.5281/zenodo.14546480); recorded in `data/DATASET_SCOUT.md` and RESULTS_v17.md.
- v1.5 2026-09-06 (POST HOC - logged after computation, not pre-registered; run
  because the GPT-5.6 referee asked "at minimum" for an independent review of the
  map entries behind the 23 headline events and the top energy events, which v1.4(a)
  did not do). `analysis/map_adjudication.py` -> `map_adjudication.csv`,
  `map_adjudication_summary.csv`. Reads every stop/warning message behind the 23
  (lead>=6h & duration>=6h quadrant) and the top-20 energy events, records whether
  each sits in a v1.4 sweep slot or a thin-rationale entry, and an independent
  family call from message text. Result: four disagreements (`WEC shut down`
  control->never-match; `Error brake resistor CHP` pitch->converter; `Overload
  generator heating` generator->auxiliary; `Parameter outside limits`
  control->never-match); first two already swept; the two new ones jointly give
  5.07% vs 7.53% (0.03 pp below the v1.4 sweep floor, inside the frozen CI). Frozen
  map unchanged; reported in the paper as a post hoc audit.
- v1.4 2026-09-03 (pre-computation; motivated by cross-model adversarial review —
  GPT-5.6 referee pass on the full artefact bundle — NOT by any outcome seen).
  Frozen definitions unchanged; primary cell unchanged. Additions:
  (a) **Component-map sensitivity.** The frozen map stays the primary map. For every
      map entry whose recorded rationale documents a plausible alternative family
      (the five ambiguous calls flagged at the v1.1 freeze, plus `WEC shut down`
      control-vs-manual and `Error brake resistor CHP` pitch-vs-converter/brake),
      recompute the primary decomposition, the converter same-component coverage,
      and the classification of the top-10 energy events under each single flip and
      under the most-adverse joint combination. Report the range next to the
      headline.
  (b) **All-warned-events late-warning statistic.** Share of same-component-warned
      T2 lost energy (all 979 events, no eligibility restriction) from events whose
      every in-window same-component warning lies inside the final 24 h. Replaces
      the subset-only support for the "silent until the last day" reading.
      Disclosure: the >=3-matching-rows eligibility rule in v1.3(c)'s per-event
      trend statistics was an implementation reading (a rate ratio is undefined on
      fewer rows), not pre-registered; it is now documented, and the paper must
      state the subset's coverage (799 of 979 events; 840.5 of 1,522.8 MWh).
  (c) **Small-cluster inference robustness.** Farm-stratified variant of the
      two-level bootstrap (resample turbines within farm) and leave-one-turbine-out
      range for the headline actionable-unacted share.
  (d) **Claim ledger.** Export an artefact tracing every manuscript number not
      already in a summary CSV (top-200 energy share, zero-energy event counts,
      exact-anchor control rate, duration-bucket counts, at-risk event counts).


## Dated qualifications of frozen wording (appended 2026-09-07; frozen text above unchanged)

- Lines describing Warning rows as "operator-visible" / "operator-visible by construction"
  and the study as measuring what "existing sensing already flagged" were design
  ASSUMPTIONS about the Greenbyte platform, not observed properties. The export shows
  that a row was recorded; it does not show presentation, delivery, acknowledgement or
  use. The paper (from the 2026-09-07 revision) says "logged" throughout and defines
  actionable-unacted as a timing classification of logged rows.
- The v1 text calling T_act = 6 h "realistic" was a scenario choice. Post-failure outage
  duration (v1.3a) benchmarks the horizon against how long outages last; it does not
  validate that six pre-failure hours suffice to diagnose, dispatch and prevent.

## Dated note on the v1.6(a) retention rule (2026-09-07, after the GPT-5.6 round-3 report)

v1.6(a) said the >=3-row dynamics cell "stays the reported one only if the direction of
the result holds at >=1 and >=2". The script written before computation encoded that test
as: majority of events AND more than 99% of energy with rate ratio > 1. As encoded it
FAILED at floor >=1 (78.1% of events, 89.9% of energy) and passed at >=2 (79.1%, 99.4%).
Consequence, applied in the paper on 2026-09-07: the unrestricted 979-event result is the
reported one; the >99%-of-energy figures are stated as conditional on at least two
matching rows; the >=3 cell is reported beside them, not featured. The prose test
("direction") would have passed at every floor on the majority criterion alone; we do not
rely on that reading, because the encoded test is the one that existed before the numbers.

## Dated global clarification of historical wording (2026-09-07, after the GPT-5.6 round-4 report)

Every use of "pre-registered" / "(pre-registered)" in this file and in RESULTS_v13.md,
RESULTS_v14.md and RESULTS_v16.md means "prespecified in this dated internal log before
the computation it describes". No entry was registered with an external, timestamped
registry, and the paper says so. The historical text is left as written. The class the
frozen text and earlier notes call "actionable-unacted" is, from v1.7 (2026-09-07), called
"long-lead" in the paper and figures; the CSV key `actionable_unacted` is unchanged and is
documented in analysis/ARTEFACT_KEY.md.

## Dated note on implementation conventions absent from the frozen text (2026-09-07, after the GPT-5.6 round-5 report)

Four conventions that the paper relies on were fixed in code, not in this file, and are
therefore non-prespecified implementation choices. None was chosen after an outcome was seen.

- **Control re-draw cap, +-10 d** (controls.py, `MAX_DEVIATION_D = 10`, file dated
  2026-08-27 03:09, the stage-2 run; the stage-2 summary CSVs are dated 03:10, so the mtime
  cannot by itself order the cap against the first computed share). The v1.1 text gives the
  re-draw sequence 45, 44, 46, ... and no cap. Recorded at the time in RESULTS.md section 6a
  ("labelled implementation-reading sensitivities": "neither was chosen after seeing
  outcomes"). Binds for 35 of 6,050 events (0.58%) at -45 d.
- **E_i = 0 for a window containing no 10-minute bin start** (build_events.py, window sliced
  [t0, t1] on the bin start-timestamp; file dated 2026-08-27 02:48, stage 1; the v1.1 freeze
  is dated to the day only, so no ordering against it is claimed; the convention predates
  any warned share). The convention was chosen because it
  reproduces Greenbyte's own `Lost Production to Downtime` to a ratio of 1.0004 (PROFILE
  section 5, checks.md); it is not stated in the frozen text. Affects 1,745 of 4,213 T2 events
  (41.4%), overwhelmingly sub-10-minute stops.
- **Merge predicate: overlap OR touch** (common.py::merge_intervals, `t0 <= running max end`;
  file dated 2026-08-27, stage 1). The frozen text above says "merge overlapping/nested stop
  intervals"; abutting records are neither, so the code is broader than the prose. Found
  2026-09-08 by an independent re-implementation and confirmed by a second. Three of the eight
  absorbed stop rows abut rather than overlap. Under the stricter reading (merge only on
  genuine overlap): 4,216 events, 9,387.1 MWh, strict long-lead share 7.128% (-0.40 pp,
  inside the reported interval), permissive 35.47% (+1.14 pp); essentially all of the strict
  move comes from one Penmanshiel WT15 event that splits into a safety-only piece with no
  same-component match and a smaller matched piece. Note that the stricter reading is not
  uniformly conservative: splitting a running outage lets a warning row logged during it
  precede the later fragment, which is why the permissive share rises. The paper reports the
  frozen code's rule and discloses both.
- **The v1.6(a) ">99% of energy" gate** (see the dated note on the v1.6(a) retention rule
  above): v1.6 prose says only that "the direction" must hold at floors >=1 and >=2; the
  majority-of-events AND >99%-of-energy encoding is code-defined, fixed before computation,
  and is now described in the paper as a code-defined implementation rule, not as
  prespecified.
