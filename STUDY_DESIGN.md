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
