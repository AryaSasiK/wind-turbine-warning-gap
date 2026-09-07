# ARTEFACT_KEY - which cell in which CSV is the manuscript's primary population

Added 2026-09-06 in response to a referee point: the label `T2` does not mean the
same thing in every artefact, so a reader who filters on `tier == "T2"` can silently
pick up the wrong event population. Read this before quoting any number out of
`analysis/*.csv`. No artefact was changed to produce this file.

## The two populations

`build_events.py` writes both grid-exclusion variants as separate boolean columns on
`events.parquet`. Counts below are read directly from that frozen parquet.

| flag on `events.parquet` | grid rule | events | lost energy |
|---|---|---|---|
| `T2` | **narrow** - only the four messages named verbatim in STUDY_DESIGN's T1 list | 4,238 | 9,635.6 MWh |
| `T2_wide_grid` | **wide** - every `External stop (grid)` service-category message, adding `Maximum grid frequency` | **4,213** | **9,386.5 MWh** |

For reference: `T0` = 6,050 / 12,099.8 MWh, `T1` = 4,635 / 11,957.3 MWh,
`T1_wide_grid` = 4,610 / 11,708.2 MWh.

**The manuscript's primary population is the WIDE one: 4,213 events, 9,386.5 MWh.**
STUDY_DESIGN v1.1(b) makes wide primary and keeps narrow as a labelled sensitivity.

## Why the label is unstable

Two naming conventions are in play, and they are opposites:

- **Raw-column convention** (`build_events.py`, `common.py`, and the two summaries
  written straight off the parquet): `T2` is the *column name*, so `T2` = narrow.
- **Re-tiered convention** (`decompose.py` and everything downstream of it): the
  script remaps the labels on the way out -
  `TIERS = {"T2": ("T2_wide_grid", "primary"), "T2_narrow": ("T2", "sensitivity")}` -
  so in those files `T2` = **wide** and the narrow variant is spelled `T2_narrow`.

Every other script hard-codes `TIER_FLAG = "T2_wide_grid"` and emits no tier column
at all, so those files are single-population by construction.

## The key

| file | column/label that selects the primary cell | events in that row | plain `T2` a trap here? |
|---|---|---|---|
| `decomposition.csv` | `tier=="T2"` and `tier_variant=="primary"` (headline row also needs `population=="all"`, `rule=="same"`, `lookback_h==72`, `T_act_h==6`, `control_offset_d==45`) | 4,213 | No - `T2` is wide; narrow is `T2_narrow` |
| `bootstrap.csv` | `tier=="T2"` (with `rule=="same"`, `T_act_h==6`) | 4,213 | No - only the wide variant is present |
| `leadtime_stats.csv` | `tier=="T2"` (with `rule=="same"`) | 979 warned of 4,213 | No - only the wide variant is present |
| `duration_comparison.csv` | `tier=="T2"` (with `rule=="same"`) | 979 + 3,234 = 4,213 | No - only the wide variant is present |
| `counterfactual.csv` | `tier=="T2"`; every row already carries `tier_variant=="primary"` | 698 actionable of 4,213 | No - self-labelled |
| `tact_curve.csv` | no tier column; single population | 4,213 (constant) | n/a |
| `duration_grounding.csv` | no tier column; `scope=="overall"` | 4,213 | n/a |
| `dynamics_profile.csv` | no tier column; `population` names the anchor set, not a tier; `population=="events_all"` | 4,213 | n/a |
| `dynamics_trend.csv` | no tier column; rows split by `rule` | warned subsets of 4,213 | n/a |
| `leadtime_box.csv` | no tier column; the column *name* `E_family_T2_mwh` is the primary denominator | 979 warned of 4,213 | n/a |
| `lead_vs_duration.csv` | no tier column | 979 warned of 4,213 | n/a |
| `influence_loo.csv` | no tier column; leave-one-out within the primary population | top 10 of 4,213 | n/a |
| `cluster_robustness.csv` | no tier column; `analysis=="bootstrap_farm_stratified"` and `scope=="all"` | 4,213 | n/a |
| `map_sensitivity.csv` | no tier column; tier membership is never re-derived, so the denominator is invariant across all 1,152 variant rows | 4,213 (constant) | n/a |
| `late_warning_all.csv` | `population=="T2_wide_grid_warned"` | 979 warned of 4,213 | No - explicitly named |
| `claim_ledger.csv` | no tier column; free-text `claim` strings only | text quotes 4,213 throughout | No |
| `events_summary.csv` | **no primary row exists in this file** | - | **YES - see below** |
| `attribution_summary.csv` | `tier=="T2_wide_grid"` | 4,213 | **YES - see below** |
| `controls_summary.csv` | no tier column; this file is **T0**, not T2 | 6,050 | **YES - see below** |

## Warnings

**`events_summary.csv` - the outright trap.** Its `tier=="T2"` row reports
**4,238 events / 9,635.6 MWh**, the narrow variant. The manuscript's 4,213 / 9,386.5
population appears nowhere in the file, so there is nothing in it to cross-check
against. Any headline event count or lost-energy total quoted from this file is the
wrong population. Same for its `T1` row (4,635, narrow).

**`attribution_summary.csv` - a trap with an escape hatch.** It carries four tiers:
`T0`, `T1`, `T2` and `T2_wide_grid`. `tier=="T2"` is the **narrow** variant
(n = 4,238); the primary row is the separately spelled `tier=="T2_wide_grid"`
(n = 4,213). Filtering on `"T2"` here gives 23.10% same-component warned at 72 h
instead of the manuscript's 23.24%. Its `T1` is likewise narrow, with no
`T1_wide_grid` row at all.

**`controls_summary.csv` - a different trap.** It has no tier column and is not a T2
file: its `events` count is 6,050, the full T0 forced-outage population. The 99.42%
match rate is over all 6,050 T0 events, not over the 4,213 primary events.
`claim_ledger.py` already notes this; nothing in the CSV itself says so.

## Rule of thumb

- If the file came from `decompose.py`, `T2` means wide/primary. Confirm with
  `tier_variant == "primary"` where that column exists.
- If the file was written straight off `events.parquet` (`events_summary.csv`,
  `attribution_summary.csv`), `T2` means narrow. Ask for `T2_wide_grid` instead, and
  if there is no such row the file has no primary cell.
- If the file has no tier column at all, it is the primary population - except
  `controls_summary.csv`, which is T0.
- The safest single check: the primary cell should read 4,213 events or 9,386.5 MWh
  (or 979 same-component-warned events / 1,522.8 MWh for the warned subset). If a row
  says 4,238 or 9,635.6, it is the narrow variant.
