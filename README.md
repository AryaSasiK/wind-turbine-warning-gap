# The Actionable-Warning Gap — analysis pipeline

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
  - `component_map.csv` — the frozen message→family map (do not edit)
  - `RESULTS.md` / `checks.md` — source of truth for every number in the paper
  - small summary CSVs — the computed outputs the paper quotes

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
