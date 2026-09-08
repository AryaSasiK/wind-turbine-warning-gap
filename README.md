# The Actionable-Warning Gap — analysis pipeline

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22653079.svg)](https://doi.org/10.5281/zenodo.22653079)

Code and frozen artefacts behind the paper:

> Arya Sasikumar, "The Actionable-Warning Gap: Measuring Unacted Warnings in
> Wind-Farm Forced-Outage Losses from Operational Event Logs," submitted to
> IEEE PES General Meeting 2027.

The paper measures, from operational status logs rather than a detection model,
how much of two wind farms' forced-outage lost energy was preceded by a
`Warning` row the operator already had, with matched quiet controls and an
energy-weighted decomposition into unwarned / short-lead / actionable-unacted.

## Data

Kelmarsh and Penmanshiel open SCADA + status data, released CC-BY-4.0 by
Cubico Sustainable Investments (author: Charlie Plumley). This study pins the
version DOIs:

- Kelmarsh: [10.5281/zenodo.16807551](https://doi.org/10.5281/zenodo.16807551)
- Penmanshiel: [10.5281/zenodo.16807304](https://doi.org/10.5281/zenodo.16807304)

Raw data is ~11.3 GB of zips; the pipeline streams from the zips and never
fully extracts them. `data/MANIFEST.json` holds the MD5s of every file used.

## Layout

- `STUDY_DESIGN.md` — the pre-registered spec, frozen (v1.1) before any outcome
  was computed; the changelog records the two post-freeze clarifications.
- `data/` — download (`download.py`), zip-streaming readers (`wtio.py`),
  status-log consolidation (`build_status.py`), profiling (`PROFILE.md`,
  557 lines, written before the study design).
- `analysis/` — the pipeline, in run order:
  1. `build_events.py` — merged forced-outage events, exclusion tiers T0/T1/T2
  2. `build_warnings.py` — de-duplicated Warning rows
  3. `build_scada_cache.py` — minimal 10-minute SCADA cache for energy integrals
  4. `attribute.py` — warning attribution (any / same-component, 24/48/72 h)
  5. `controls.py` — matched quiet controls (−45 d primary, −30/−60 d)
  6. `decompose.py` — energy decomposition, `T_act` grid, duration contrasts
  7. `counterfactual.py` — modeled recoverable energy (labelled a model)
  8. `bootstrap.py` — two-level cluster bootstrap (turbines → events, 10,000×)
  9. `cluster_duration.py` — cluster-robust CI on the warned/unwarned
     duration contrast
  10. `figures.py` — the paper's figures
  11. `duration_grounding.py` — outage-duration distribution and the actionable
      share as a curve over T_act (STUDY_DESIGN v1.3a; `duration_grounding.csv`,
      `tact_curve.csv`, `lead_vs_duration.csv`)
  12. `leadtime_box.py` — lead-time distribution by component (v1.3b)
  13. `warning_dynamics.py` — warning-rate profile before failure vs matched
      controls, per-event rate ratio and Laplace trend (v1.3c)
  14. `map_sensitivity.py` — headline under every documented alternative
      component-map assignment, 1,152 variants (v1.4a)
  15. `late_warning_all.py` — all-events late-warning statistic (v1.4b)
  16. `cluster_robustness.py` — farm-stratified bootstrap and leave-one-turbine-out (v1.4c)
  17. `claim_ledger.py` — traces every manuscript-only number to the data (v1.4d)
  18. `map_adjudication.py` — post hoc line-by-line review of map entries behind
      the 23 headline events and the 20 largest events (v1.5, NOT pre-registered)
  19. `warning_rows_by_family.py` — Table I warning-supply column on the
      de-duplicated, post-commissioning basis
  20. `dynamics_sensitivity.py` — dynamics statistics at eligibility floors of
      1, 2 and 3 matching rows, with inclusion flow (v1.6a)
  21. `block_bootstrap.py` — turbine-year block bootstrap on the headline (v1.6b)
  22. `merged_events_audit.py` — constituent-level audit of the three
      multi-constituent events and the displayed-family-only rule (v1.6c)
  23. `add_tier_variant.py` — adds `tier_variant` to `events_summary.csv`
      without rebuilding events (v1.6d)
  24. `warning_rows_by_family.py` (extended) — Table I rates on real
      post-commissioning SCADA exposure, `per_ty_scada_cod` (v1.7a)
  25. `map_adjudication_allfour.py` — explicit headline rows for every
      adjudication scenario in `map_adjudication_summary.csv` (v1.7b)
  26. `greek_log_counts.py` — full warning/alarm count of the SMD10TOWFGR
      workbook (v1.7d; external corpus, not part of the pipeline)
  - `component_map.csv` — the frozen message→family map (do not edit)
  - `RESULTS.md`, `RESULTS_v13.md`, `RESULTS_v14.md`, `RESULTS_v15.md`,
    `RESULTS_v16.md`, `RESULTS_v17.md`, `RESULTS_warning_dedup.md`, `checks.md` — source of truth for every number
    in the paper; `RESULTS.md` carries dated errata
  - `ARTEFACT_KEY.md` — which label in each CSV selects the primary population
    (plain `T2` is the narrow-grid variant in some files; read this first)
  - small summary CSVs — the computed outputs the paper quotes
- `data/DATASET_SCOUT.md` — the search protocol and verdicts for every candidate
  open dataset considered for replication.
- `data/hill-of-towie/` — a public inventory of every alarm code observed in the
  open Hill of Towie dataset (RES, Zenodo 10.5281/zenodo.20204946, CC-BY-4.0),
  built from the open files only by `analysis/hot_alarm_inventory.py` /
  `hot_zipranged.py`; posted as
  https://github.com/resgroup/hill-of-towie-open-source-analysis/discussions/80.

## Versions

- v1.0 (2026-08-28, 10.5281/zenodo.22141125): pipeline at STUDY_DESIGN v1.2, frozen before outcomes.
- v1.1 (2026-09-07, 10.5281/zenodo.22650035): adds the v1.3 analyses (pre-registered 2026-09-03 after
  external feedback, before computation), the v1.4 robustness checks
  (pre-registered 2026-09-03 after a cross-model review, before computation),
  the v1.5 map adjudication (2026-09-06, post hoc, labelled so), the claim
  ledger, the Table I basis correction (RESULTS.md erratum 2026-09-06), the
  dataset scout, and the Hill of Towie code inventory.
- v1.2 (2026-09-07, 10.5281/zenodo.22652197): adds the v1.6 analyses (pre-registered
  2026-09-07 after the second cross-model review, before computation): dynamics
  floor sensitivity, turbine-year block bootstrap, merged-event audit,
  `tier_variant` column; STUDY_DESIGN v1.6 and its dated wording qualifications.
- v1.3 (2026-09-07, 10.5281/zenodo.22653079): adds the v1.7 analyses (prespecified 2026-09-07 after the
  third cross-model review, before computation): Table I rates on real SCADA
  exposure (159.1 turbine-years), explicit adjudication-scenario rows, full
  Greek corpus count, figure class label "long-lead"; STUDY_DESIGN v1.7 and the
  dated note on the v1.6(a) retention rule.

## Reproducing

```bash
pip install -r requirements.txt
python data/download.py          # ~11.3 GB into $WTWG_RAW
python data/build_status.py
python analysis/build_events.py  # then the rest in the order above
```

Paths default to `./wind-turbine-warning-gap-data/{raw,derived}`; override with
the `WTWG_RAW` and `WTWG_DERIVED` environment variables.

## License

Code: MIT (see `LICENSE`). The datasets are CC-BY-4.0, © Cubico Sustainable
Investments — cite the Zenodo records above, not this repository, for the data.
