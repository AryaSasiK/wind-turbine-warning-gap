# RESULTS v1.6 - dynamics eligibility, block bootstrap, merged-event audit, artefact relabel

STUDY_DESIGN v1.6 (2026-09-07, pre-registered before any of these numbers existed;
motivated by the GPT-5.6 round-2 referee report). Frozen definitions unchanged, primary
cell unchanged: **T2 wide-grid, same-component rule, 72 h lookback, T_act = 6 h, -45 d
controls, energy-weighted**.

Provenance is given as **`script.py` -> `artefact` [row selector]**. Nothing frozen was
recomputed or overwritten: `events.parquet`, `warnings.parquet`, `attribution.parquet`,
`controls.parquet` and `component_map.csv` were read only.

```
dynamics_sensitivity.py -> analysis/dynamics_sensitivity.csv     (v1.6 a)
block_bootstrap.py      -> analysis/block_bootstrap.csv          (v1.6 b)
merged_events_audit.py  -> analysis/merged_events_audit.csv      (v1.6 c)
add_tier_variant.py     -> analysis/events_summary.csv, in place (v1.6 d)
```

---

## 0. Validation gate

Every one of the four scripts opens with the same gate and aborts on any mismatch. It
ran clean in all four (console, `=== VALIDATION GATE ===`):

| check | got | want | tol |
|---|---|---|---|
| T2 wide-grid events | 4,213 | 4,213 | 0 |
| T2 wide-grid lost energy | 9,386.5016 MWh | 9,386.5 | 0.05 |
| same-component warned events | 979 | 979 | 0 |
| same-component warned energy | 1,522.7825 MWh | 1,522.8 | 0.05 |
| headline actionable-unacted share | 7.5282 % | 7.53 | 0.005 |
| >=3-row trend subset, events | 799 | 799 | 0 |
| >=3-row trend subset, energy | 840.5459 MWh | 840.5 | 0.05 |

`add_tier_variant.py` gates additionally on the **narrow** cell that
`events_summary.csv` actually reports - 4,238 events / 9,635.6462 MWh - so it cannot
relabel a file whose contents have moved underneath it.

`dynamics_sensitivity.py` also re-verifies the warning join against
`attribution.parquet` before computing anything: `same_n_72h` reproduced exactly
(26,174 rows), `any_n_72h` reproduced exactly (35,628 rows). `merged_events_audit.py`
re-runs the frozen matcher under the union rule on its three events and confirms it
reproduces their frozen `same_warn_72h`, `same_n_72h` and `same_lead_h_72h`, so any
difference it then reports is the alternative rule and not drift.

---

## 1. (a) Dynamics eligibility sensitivity

*(`dynamics_sensitivity.py` -> `dynamics_sensitivity.csv` [`table=="statistics"`].)*

The v1.3(c) trend statistics were computed on warned events with at least 3 matching
warning rows in the 72 h window - a floor fixed at implementation, disclosed at v1.4(b),
never varied. Recomputed here at floors >=1, >=2, >=3 under both rules, with the
pre-registered conventions: rate ratio r = (n_last24 / 24) / (n_prior48 / 48) over
[0, 24) h and [24, 72) h before the event start; a zero prior-48 h count with a positive
final-24 h count is an **infinite** ratio counting as both "r > 1" and "r >= 2"; zero
rows in both windows is **undefined** and excluded.

### 1.1 Same-component (the reported arm)

| floor | events | share of the 979 | MWh | share of the 1,522.8 | infinite r | undefined |
|---|---|---|---|---|---|---|
| >=1 | 979 | 100.00 % | 1,522.8 | 100.00 % | 379 | **0** |
| >=2 | 910 | 92.95 % | 1,247.3 | 81.91 % | 334 | **0** |
| >=3 | 799 | 81.61 % | 840.5 | 55.20 % | 229 | **0** |

| floor | r > 1, count | r > 1, energy | r >= 2, count | r >= 2, energy | median r (count) | Laplace > 0, count / energy |
|---|---|---|---|---|---|---|
| >=1 | 78.14 % | **89.94 %** | 70.28 % | 89.89 % | 5.000 | 84.58 % / 90.42 % |
| >=2 | 79.12 % | **99.44 %** | 70.66 % | 99.38 % | 4.583 | 85.27 % / 99.47 % |
| >=3 | 76.35 % | **99.21 %** | 66.71 % | 99.12 % | 3.333 | 83.35 % / 99.25 % |

The `>=3` row reproduces the frozen `dynamics_trend.csv` exactly in every statistic it
shares (76.35 / 99.21 / 66.71 / 99.12 %, median 3.3333, Laplace 83.35 / 99.25 %), for
both rules - so the floor is the only thing that moves between these rows.

The count-weighted median r is finite at every floor (5.000 / 4.583 / 3.333); the
energy-weighted median is **infinite at all three**, which is the same fact RESULTS_v13
§C.2 reports - the median warned MWh sits in an event with no same-component warning at
all before the final 24 h.

**Zero undefined events at every floor, as pre-registered.** Confirmed rather than
assumed: a warned event has at least one row inside [0, 72), and every such row falls in
exactly one of the two sub-windows, so both counts cannot be zero. The `n_undefined`
column is 0 in all six rows of the artefact.

### 1.2 Any-warning (second block)

| floor | events | share of the 2,652 | MWh | share of the 4,420.8 | infinite r | undefined |
|---|---|---|---|---|---|---|
| >=1 | 2,652 | 100.00 % | 4,420.8 | 100.00 % | 1,160 | 0 |
| >=2 | 2,139 | 80.66 % | 3,211.8 | 72.65 % | 783 | 0 |
| >=3 | 1,752 | 66.06 % | 2,350.2 | 53.16 % | 553 | 0 |

| floor | r > 1, count | r > 1, energy | r >= 2, count | r >= 2, energy | median r (count) | Laplace > 0, count / energy |
|---|---|---|---|---|---|---|
| >=1 | 74.36 % | 60.59 % | 69.12 % | 59.50 % | 6.000 | 79.30 % / 85.61 % |
| >=2 | 74.57 % | 65.10 % | 68.07 % | 63.61 % | 4.000 | 79.06 % / 86.51 % |
| >=3 | 72.77 % | 77.65 % | 64.84 % | 75.60 % | 4.000 | 78.31 % / 84.07 % |

The any-warning arm never reaches the >99 % energy figure at any floor, which is the
already-published position: RESULTS_v13 §C.2 reports 77.65 % there, and the paper scopes
the acceleration claim to the same-component arm.

### 1.3 Inclusion flow

*(`dynamics_sensitivity.csv` [`table=="inclusion_flow"`].)*

| rule | step | events | MWh | dropped at this step (events / MWh) |
|---|---|---|---|---|
| same | warned, no floor | 979 | 1,522.8 | - |
| same | floor >=1 | 979 | 1,522.8 | 0 / 0.0 |
| same | floor >=2 | 910 | 1,247.3 | 69 / 275.5 |
| same | floor >=3 | 799 | 840.5 | 111 / 406.8 |
| any | warned, no floor | 2,652 | 4,420.8 | - |
| any | floor >=1 | 2,652 | 4,420.8 | 0 / 0.0 |
| any | floor >=2 | 2,139 | 3,211.8 | 513 / 1,209.0 |
| any | floor >=3 | 1,752 | 2,350.2 | 387 / 861.6 |

Floor >=1 drops nothing, by construction: `same_warn_72h` is true exactly when
`same_n_72h >= 1`. The >=3 floor costs the same-component arm 180 events and 682.2 MWh
of the warned population - 18.4 % of events but 44.8 % of the energy.

### 1.4 Does the direction hold at every floor?

Direction, as stated in the task: **a majority of events and more than 99 % of energy
with r > 1.**

- **Majority of events: holds everywhere.** 78.14 / 79.12 / 76.35 % same-component,
  74.36 / 74.57 / 72.77 % any-warning.
- **More than 99 % of energy: holds at >=2 (99.44 %) and >=3 (99.21 %), and FAILS at
  >=1 (89.94 %)** for the same-component rule. It fails at every floor for any-warning,
  as it already did in the published >=3 cell.

The failure at >=1 is explainable and worth stating rather than burying. Of the 69
single-row events that floor >=1 admits and floor >=2 excludes, 24 - carrying
**146.2 MWh** - have their one matching row in the prior 48 h, so r = 0 exactly. With a
single row the rate ratio is not a trend statistic at all: it is a binary indicator of
which sub-window the row landed in, either infinite or zero. The 111 two-row events are
almost all accelerating (110 of 111, 406.5 of 406.8 MWh), which is why >=2 recovers.

**Reading for the paper.** The pre-registered rule was that the >=3 cell stays reported
only if the direction holds at >=1 and >=2. Under the strict two-part reading it holds at
>=2 but not at >=1. The honest statement is the one this table supports: the
count-weighted direction is stable across all three floors, and the energy-weighted
">99 %" figure is a property of events carrying at least two matching rows and should be
quoted with that eligibility attached, not as a property of all 979 warned events. The
paper already scopes the 99.2 % to the 840.5 MWh subpopulation (RESULTS_v13 §C.2, applied
in the 2026-09-04 revision); this sensitivity says that scoping was necessary, and that
the figure is 89.9 % if the subpopulation restriction is dropped altogether.

---

## 2. (b) Turbine-year block bootstrap

*(`block_bootstrap.py` -> `block_bootstrap.csv`
[`analysis=="bootstrap_turbine_year_block"`].)*

`bootstrap.py`'s frozen interval resamples turbines, then that turbine's **events**
independently within turbine - which assumes events are exchangeable within a turbine
across the whole 2016-2024 record. The objection: a bad component-year produces a run of
correlated outages, so the inner level may break up real serial dependence and understate
the variance. This variant keeps the outer level (20 turbines with replacement) and makes
the inner unit a **turbine-year block** (calendar year of the event start), resampled with
replacement, every event in a drawn block kept together.

**Block structure**: 170 turbine-year blocks over 20 turbines and 9 calendar years
(2016-2024); 8 to 9 blocks per turbine (median 8, mean 8.50). Events per block: min 2,
p25 11, median 18, p75 28, max 183, mean 24.78 - the 170 blocks partition all 4,213
events. Energy per block: min 0.00, median 24.69, mean 55.21, max 706.5 MWh
(penmanshiel WT11 2022). The largest block by count is kelmarsh WT05 2023 (183 events,
222.0 MWh).

| interval | point | 95 % CI | bootstrap sd | reps | seed | source |
|---|---|---|---|---|---|---|
| **turbine-year block** | 7.528 % | **[2.064, 16.147]** | 3.748 pp | 10,000 | 20260907 | computed here |
| unstratified (frozen) | 7.528 % | [1.947, 16.717] | 3.880 pp | 10,000 | 20260827 | quoted from `bootstrap.csv` |
| farm-stratified | 7.528 % | [1.979, 16.388] | 3.819 pp | 10,000 | 20260904 | quoted from `cluster_robustness.csv` |

All 10,000 replicates were finite. The two comparison rows are copied verbatim from
their artefacts, not recomputed, and both scripts assert that the artefact's point
estimate equals the recomputed headline to 1e-9 before quoting it.

**Reading.** Blocking on turbine-year does not widen the interval: it is marginally
*narrower* than both the frozen unstratified interval (sd 3.748 vs 3.880 pp) and the
farm-stratified one, and the three intervals overlap almost completely. The
within-turbine temporal-exchangeability objection therefore does not change the
inference - the headline's uncertainty is dominated by the outer, turbine-level
resampling with 20 clusters, not by how events are drawn inside a turbine. Rounded for
the paper: **7.5 % [2.1, 16.1]** block, against 7.5 % [1.9, 16.7] unstratified and
7.5 % [2.0, 16.4] farm-stratified.

---

## 3. (c) Merged-event audit

*(`merged_events_audit.py` -> `merged_events_audit.csv`.)*

Exactly **3** of the 6,050 merged events have more than one constituent stop
(`build_events.py` merge accounting; the script asserts the count). All three survive
every tier - T0, T1, T2, T1_wide_grid, T2_wide_grid all true - so all three are in the
4,213-event primary population.

### 3.1 Event 1185 - kelmarsh WT06, 2024-04-15 03:49:27 to 2024-04-23 18:39:22

150.2 MWh, 206.83 h. Three constituents, all the **same** message:

| constituent | family | duration h | separable MWh |
|---|---|---|---|
| Pitch current asymmetry (code 550) | pitch | 4.18 | 7.16 |
| Pitch current asymmetry (code 550) | pitch | 24.00 | 36.35 |
| Pitch current asymmetry (code 550) - **longest** | pitch | 178.66 | 106.99 |

Displayed family `pitch`; `families_all` = `[pitch]`. The constituents abut rather than
overlap (overlap 0.00 h; the merged window equals the constituent sum), so merging here
only joins three consecutive log rows for one physical outage. Same-component warned:
**no** (0 matching rows). Any-warning warned: **no** (0 rows). Class: **unwarned**. The
alternative rule is a no-op - the union and the displayed family are the same set.

### 3.2 Event 4004 - penmanshiel WT10, 2023-03-24 01:43:36 to 2023-05-24 09:13:50

505.6 MWh, 1,471.50 h - the double-charge case PROFILE §5 flagged. Four constituents:

| constituent | family | duration h | separable MWh |
|---|---|---|---|
| Frequency converter load rejection (3210) | converter | 1,425.90 | 494.72 |
| Circuit breaker (3800) - **longest** | electrical | 1,471.19 | 505.37 |
| Repeating error BP52 (455) | control | 2.02 | 0.09 |
| Manual stop - remote (21) | manual | 45.12 | 10.76 |

The separable energies are computed on the raw, **overlapping** stop windows and are not
additive: they sum to 1,010.9 MWh against the merged-window 505.6 MWh, so merging removes
505.3 MWh of double-count on this one event. Displayed family `electrical`;
`families_all` = `[control, converter, electrical, manual]`. Same-component warned:
**no** (0 matching rows). Any-warning warned: **no** (0 rows in the 72 h window at all).
Class: **unwarned**. This is the single largest event in the primary population, and it
is unwarned under every rule considered - the alternative rule cannot move it.

### 3.3 Event 6025 - penmanshiel WT15, 2024-04-17 08:00:00 to 2024-04-22 08:40:43

53.0 MWh, 120.68 h. Four constituents:

| constituent | family | duration h | separable MWh |
|---|---|---|---|
| Safety chain open (100) | safety | 48.00 | 37.75 |
| Safety chain open (100) | safety | 54.07 | 14.97 |
| Overload fan pitch motor (630) | pitch | 54.34 | 14.97 |
| Anemometer defect (6530) - **longest** | anemometry | 72.68 | 15.54 |

Overlap 108.41 h; unmerged sum 83.2 MWh against 53.0 merged, 30.2 MWh of double-count
removed. Displayed family `anemometry`; `families_all` = `[anemometry, pitch, safety]`.

- Frozen union rule: same-component **warned**, 11 matching rows, lead **19.1119 h**,
  earliest match `Error brake resistor CHP` (family `pitch`). Class:
  **actionable-unacted**.
- Any-warning: warned, 17 rows, lead 19.1131 h, earliest `Brake accumulator defect`.
- Displayed-family-only rule: same-component **warned**, 3 matching rows, lead
  **19.1114 h**. Class: **actionable-unacted**, unchanged.

This is the only one of the three where the union rule does any work at all, and it does
not change the classification: an anemometry warning arrives 0.0006 h (2 seconds) after
the pitch warning that the union rule matched first, so the event is actionable-unacted
either way.

### 3.4 Headline under the alternative rule

*(`merged_events_audit.csv` [`table=="alternative_rule"`, `table=="headline"`].)*

**Method.** The alternative rule "only the displayed (longest-constituent) family may
match" was applied by re-running `attribute.attribute()` - the frozen matcher, same
half-open [start - 72 h, start) window, same start-timestamp placement, same
external/grid/manual never-match set - for **these 3 events only**, with `fam_set`
replaced by the singleton `{displayed family}`. Every other event's frozen flags were
left untouched; the headline was then recomputed over all 4,213 T2 wide-grid events with
the three rows swapped in. The denominator (9,386.5 MWh) is unchanged, since the rule
changes matching, not tier membership or energy. Before the swap the script re-ran the
same matcher under the **union** rule on the same three events and confirmed it
reproduces their frozen columns exactly, so the difference reported is the rule and not
machinery drift.

| | headline | same-component warned | warned MWh |
|---|---|---|---|
| frozen union rule | **7.5282 %** | 979 | 1,522.78 |
| displayed-family-only rule | **7.5282 %** | 979 | 1,522.78 |
| shift | **+0.0000 pp** | 0 | 0.00 |

**The headline is exactly invariant to the family-union reading.** Two of the three
multi-constituent events carry no warning rows at all in their lookback windows, and the
third is actionable-unacted under both rules. `attribute.py`'s own docstring already
called this "nearly a no-op"; it is exactly a no-op for the headline, and now measured
rather than asserted.

### 3.5 When the merge and tier rules were fixed

*(`merged_events_audit.csv` [`table=="provenance"`]; file mtimes and
`git log --follow` in `release/wind-turbine-warning-gap`.)*

| evidence | date |
|---|---|
| STUDY_DESIGN.md v1 "initial freeze", which states the merge rule and the T0/T1/T2 tier list | **2026-08-27** |
| `common.py` mtime (`merge_intervals`, `GRID_MESSAGES`, `MANUAL_MESSAGES`) | 2026-08-27 02:38:52 |
| `build_events.py` mtime (merge-before-tier order, "survives if ANY constituent survives", longest-constituent naming) | **2026-08-27 02:48:52** |
| `attribute.py` mtime (`families_all` union matching) | 2026-08-27 02:54:23 |
| first outcome artefacts: `attribution_summary.csv` / `bootstrap.csv` mtimes | 2026-08-27 03:10:00 / 03:10:32 |
| `git log --follow analysis/build_events.py` - single commit 610a04b, the initial repository import | 2026-08-28 00:10:07 -0700 |

`build_events.py` carries no date in its docstring; its dated statement of the rules is
STUDY_DESIGN's own v1 freeze text, which predates any computation by design. The
**earliest date on the rule is 2026-08-27**, and the earliest timestamp is 02:48:52 that
day. The first outcome computation - the stage-2 artefacts, from which RESULTS.md was
written - is 2026-08-27 03:10, about 21 minutes later. **The merge and tier rules
therefore predate the first outcome computation.** The git history adds nothing earlier:
the release repository was created on 2026-08-28 and imported the whole pipeline in one
commit, so it is a lower bound on publication, not on authorship. RESULTS.md's own mtime
(2026-09-06) reflects the later erratum edits, not its creation; the artefacts it reads
carry the 2026-08-27 03:10 stamps.

---

## 4. (d) Artefact relabel

*(`add_tier_variant.py` -> `analysis/events_summary.csv`, in place.)*

`events_summary.csv` now carries a `tier_variant` column immediately after `tier`:

| tier | tier_variant | events | E_mwh |
|---|---|---|---|
| T0 | n/a | 6,050 | 12,099.8 |
| T1 | narrow | 4,635 | 11,957.3 |
| T2 | narrow | 4,238 | 9,635.6 |

`n/a` for T0 because no grid rule applies to it; `narrow` for the two rows the writer
emits; `wide_grid` is defined in the mapping and reserved for `T1_wide_grid` /
`T2_wide_grid` rows should a future re-run emit them.

**Done as a post-processor, not by re-running the writer, and this is the deviation to
declare.** `build_events.py` owns this file, and re-running it is not cheap: it rebuilds
every merged event's lost energy from the 10-minute SCADA cache over 6,050 merged plus
6,053 constituent windows and rewrites the frozen `events.parquet` and
`event_constituents.parquet` on the read-only derived volume. The v1.6(d) ask is a
relabel, not a recomputation. `add_tier_variant.py` therefore adds the column in place,
asserts that every pre-existing column is byte-identical afterwards, and gates on both
the frozen wide-grid numbers and the narrow `T2` cell (4,238 / 9,635.6462) so it cannot
relabel a file whose contents have moved. It is idempotent - a second run reports
"tier_variant already present; nothing to do". `ARTEFACT_KEY.md` records all of this,
including that **the file still has no primary (wide-grid) row**; the column removes the
misreading risk on the rows that are there, it does not add the primary cell.

No row was added, deliberately: adding wide-grid rows was not pre-registered and would
invalidate `ARTEFACT_KEY.md`'s standing statement about this file.

---

## 5. Deviations from the v1.6 text

**None that required an appended line to STUDY_DESIGN.md.** Every pre-registered
convention applied as written:

- the infinite-ratio convention fired (379 / 334 / 229 same-component events at the three
  floors) and was counted as "r > 1" and "r >= 2" as declared;
- the undefined-event exclusion was applicable and vacuous - zero undefined events at
  every floor, confirmed rather than assumed;
- the count-weighted median was finite at every floor, so the "report inf if the median
  is inf" fallback was not needed there; the energy-weighted median is infinite at all
  three same-component floors and is reported as `inf`;
- the block bootstrap ran at the pre-registered 10,000 reps and seed 20260907 with all
  replicates finite;
- the merged-event alternative rule was applied by local re-attribution of the 3 events,
  exactly the fallback the task anticipated, with the method stated in §3.4;
- the `tier_variant` relabel was delivered, by the post-processor route rather than by
  re-running the writer - a route the task itself specifies as the alternative when
  re-running is not cheap, and documented in `ARTEFACT_KEY.md` as required.

One **substantive** result to carry into the manuscript rather than a procedural
deviation: the v1.6(a) rule "the >=3 cell stays the reported one only if the direction of
the result holds at >=1 and >=2" is satisfied on the count-weighted reading at both
floors and on the energy-weighted ">99 %" reading at >=2 only. See §1.4 - the fix is
eligibility-scoped wording, which the paper already uses, not a change of reported cell.
