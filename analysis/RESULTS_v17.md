# RESULTS v1.7 - real exposure denominator, all-four adjudication rows, figure relabel, Greek corpus count

STUDY_DESIGN v1.7 (2026-09-07, prespecified before any of these numbers existed;
motivated by the GPT-5.6 round-3 referee report). Frozen definitions unchanged, primary
cell unchanged: **T2 wide-grid, same-component rule, 72 h lookback, T_act = 6 h, -45 d
controls, energy-weighted**. `paper/main.tex` was NOT edited in this pass.

Provenance is given as **`script.py` -> `artefact`**. Nothing frozen was recomputed or
overwritten: `events.parquet`, `warnings.parquet`, `attribution.parquet`,
`status_all.parquet`, the `scada_min` caches and `component_map.csv` were read only, and
the derived volume was never written to.

```
warning_rows_by_family.py     -> analysis/warning_rows_by_family.csv   (v1.7 a, new column)
map_adjudication_allfour.py   -> analysis/map_adjudication_summary.csv (v1.7 b, new rows)
figures.py, duration_grounding.py -> paper/figures/fig1.pdf, fig5.pdf  (v1.7 c, labels)
(openpyxl read-only pass)     -> data/DATASET_SCOUT.md UPDATE 2026-09-07 (v1.7 d)
```

---

## 0. Validation gate

Run before anything was edited, and re-run inside each script that writes.

| check | got | want | verdict |
|---|---|---|---|
| T2 wide-grid events (`events.parquet`, `T2_wide_grid`) | 4,213 | 4,213 | PASS |
| T2 wide-grid lost energy | 9,386.5016 MWh | 9,386.5 | PASS |
| de-duplicated post-COD warning rows (`warnings.parquet`, `~pre_cod`) | 17,793 | 17,793 | PASS |
| Table I family rows, `warning_rows_by_family.csv` `rows_dedup_cod` | all 13 families | unchanged | PASS |
| frozen headline (`map_adjudication_allfour.py`) | 7.5282 % | 7.528 | PASS |

The 13 `rows_dedup_cod` values reproduced byte for byte (anemometry 3,792; auxiliary 854;
brake_hydraulic 2,415; comms 1,052; control 217; converter 44; drivetrain 345;
electrical 37; external 2,559; generator 1,218; pitch 3,572; tower 193; yaw 1,495), and
the six columns that existed before this pass are byte-identical in the rewritten CSV.

---

## A. Table I exposure denominator: a real one

### A.1 What was wrong

`turbine_years_cod()` returned **166.93** turbine-years. That is not an exposure. It is
PROFILE section 4's **171 file-years** - one count per (turbine, calendar year) file, so
a turbine first logged in late January 2016 contributes a whole year - rescaled by
159.91/163.81, the post-COD fraction of the sum of first-to-last status-log spans. Both
factors are nominal: the file count never asks whether the turbine was observed, and the
span ratio treats a gap in the middle of a span as exposure.

### A.2 The replacement

`warning_rows_by_family.py::scada_exposure_by_turbine()` counts exposure instead of
assuming it. For each turbine, the number of 10-minute SCADA grid bins that

1. fall at or after the farm's commercial-operation date (`common.COD`: Kelmarsh
   2016-04-15, Penmanshiel 2016-09-01), and
2. lie inside that turbine's own status-log span [first `t0`, last `t0`],

converted as `bins x 10 min / 365.25 d`.

**Source choice.** `derived/scada_min/*.parquet` (one file per turbine), not
`derived/scada_coverage.csv`. The coverage CSV is one row per zip member and carries
`n_rows` next to `expected_rows_in_span`, so it would have to be de-duplicated across the
four irregular Penmanshiel 2023 zips before it could be summed, and its `n_rows` is a
file row count rather than a distinct-timestamp count. The caches are already the right
object: `build_scada_cache.py` drops the all-NaN Greenbyte padding rows and
de-duplicates on timestamp. Profiled before use - across all 20 caches there are **0
duplicate timestamps, 0 off-grid timestamps, 0 all-NaN rows**, every gap is a whole
number of 10-minute steps, and the only departures from a strict 600 s step are 3-40
internal holes per turbine. Counting rows therefore counts bins the farm really
reported, and internal holes are excluded rather than interpolated over.

### A.3 Per-turbine exposure

| farm | turbine | status-log span | post-COD bins | turbine-years | first-to-last span (ty) |
|---|---|---|---|---|---|
| kelmarsh | 1 | 2016-01-14 19:28:03 - 2024-12-29 14:13:47 | 457,397 | 8.6964 | 8.7080 |
| kelmarsh | 2 | 2016-01-21 14:11:59 - 2024-12-31 23:50:45 | 457,739 | 8.7029 | 8.7146 |
| kelmarsh | 3 | 2016-01-27 15:56:48 - 2024-12-28 23:50:47 | 457,311 | 8.6948 | 8.7063 |
| kelmarsh | 4 | 2016-02-04 18:49:54 - 2024-12-31 14:28:14 | 457,684 | 8.7019 | 8.7135 |
| kelmarsh | 5 | 2016-01-24 15:12:45 - 2024-12-31 16:28:37 | 457,697 | 8.7021 | 8.7137 |
| kelmarsh | 6 | 2016-02-05 15:07:06 - 2024-12-29 10:53:27 | 457,375 | 8.6960 | 8.7076 |
| penmanshiel | 1 | 2016-06-06 17:08:40 - 2023-12-31 21:53:43 | 381,076 | 7.2453 | 7.3317 |
| penmanshiel | 2 | 2016-06-03 08:54:48 - 2023-12-31 21:54:16 | 381,076 | 7.2453 | 7.3317 |
| penmanshiel | 4 | 2016-06-13 14:51:51 - 2023-12-31 21:52:38 | 381,076 | 7.2453 | 7.3317 |
| penmanshiel | 5 | 2016-06-15 18:54:11 - 2023-12-31 22:03:47 | 381,077 | 7.2454 | 7.3317 |
| penmanshiel | 6 | 2016-06-02 18:02:26 - 2023-12-31 21:52:59 | 381,076 | 7.2453 | 7.3317 |
| penmanshiel | 7 | 2016-06-02 17:45:07 - 2023-12-31 22:24:20 | 381,079 | 7.2454 | 7.3318 |
| penmanshiel | 8 | 2016-07-27 15:48:14 - 2023-12-31 22:03:26 | 381,077 | 7.2454 | 7.3317 |
| penmanshiel | 9 | 2016-06-24 11:42:46 - 2023-12-31 21:47:31 | 381,075 | 7.2453 | 7.3317 |
| penmanshiel | 10 | 2016-06-27 18:14:23 - 2023-12-31 22:00:09 | 381,077 | 7.2454 | 7.3317 |
| penmanshiel | 11 | 2016-07-19 09:44:20 - 2024-12-31 08:32:03 | 438,164 | 8.3307 | 8.3323 |
| penmanshiel | 12 | 2016-07-02 16:25:34 - 2024-12-31 10:49:16 | 438,177 | 8.3310 | 8.3325 |
| penmanshiel | 13 | 2016-07-01 09:14:36 - 2024-12-31 08:00:20 | 438,161 | 8.3307 | 8.3322 |
| penmanshiel | 14 | 2016-07-09 16:21:50 - 2024-12-31 10:11:50 | 438,174 | 8.3309 | 8.3324 |
| penmanshiel | 15 | 2016-07-14 20:08:08 - 2024-12-31 08:24:11 | 438,163 | 8.3307 | 8.3322 |
| **total** | **20** | | **8,365,731** | **159.0564** | **159.9110** |

Note Penmanshiel has no WT03; the farm's 14 turbines are WT01, WT02 and WT04-WT15.

### A.4 The three denominators side by side

| denominator | value (turbine-years) | what it is |
|---|---|---|
| 171 | 171 | file count, turbine x calendar year, pre-COD months included |
| `turbine_years_cod()` | **166.9302** | 171 rescaled by 159.9110/163.8097 (the number Table I prints against today) |
| sum of first-to-last post-COD spans | **159.9110** | reproduces the referee's 159.91 exactly |
| `turbine_years_scada_cod()` | **159.0564** | real elapsed post-COD exposure, 8,365,731 SCADA bins |

Raw (pre-COD-inclusive) span sum, for completeness: **163.8097**.

The real exposure is **4.7 % smaller** than the nominal 166.93, and 0.85 turbine-years
(0.5 %) below the first-to-last span sum - the difference being the internal SCADA holes.
Every per-family rate therefore rises by the same factor, **166.9302/159.0564 = 1.0495**.

### A.5 Per-family rates on the real denominator

New column `per_ty_scada_cod` in `analysis/warning_rows_by_family.csv`
(= `rows_dedup_cod` / 159.0564). The six pre-existing columns are unchanged.

| family | rows_dedup_cod | per_ty_dedup_cod (166.93) | **per_ty_scada_cod (159.06)** | in Table I |
|---|---|---|---|---|
| anemometry | 3,792 | 22.7161 | **23.8406** | yes (22.7 -> 23.8) |
| auxiliary | 854 | 5.1159 | **5.3692** | no |
| brake_hydraulic | 2,415 | 14.4671 | **15.1833** | yes, "brake/hydraulic" (14.5 -> 15.2) |
| comms | 1,052 | 6.3020 | **6.6140** | no |
| control | 217 | 1.2999 | **1.3643** | yes (1.3 -> 1.4) |
| converter | 44 | 0.2636 | **0.2766** | yes (0.3 -> 0.3) |
| drivetrain | 345 | 2.0667 | **2.1690** | yes, printed as "drivetrain" (2.1 -> 2.2) |
| electrical | 37 | 0.2216 | **0.2326** | yes (0.2 -> 0.2) |
| external | 2,559 | 15.3298 | **16.0886** | no |
| generator | 1,218 | 7.2965 | **7.6577** | yes (7.3 -> 7.7) |
| pitch | 3,572 | 21.3982 | **22.4574** | yes (21.4 -> 22.5) |
| safety | 0 | 0.0000 | **0.0000** | yes (0.0, unchanged - no warning rows on any basis) |
| tower | 193 | 1.1562 | **1.2134** | yes (1.2 -> 1.2) |
| yaw | 1,495 | 8.9558 | **9.3992** | no |
| **total** | **17,793** | | **111.8659 rows/ty** | |

`safety` has no row in the CSV because it supplies zero warning rows; Table I prints it
as 0.0 and that is right on every basis.

**Printed Table I cells that move if the real denominator is adopted (6 of 10):**
anemometry 22.7 -> 23.8, brake/hydraulic 14.5 -> 15.2, control 1.3 -> 1.4,
drivetrain 2.1 -> 2.2, generator 7.3 -> 7.7, pitch 21.4 -> 22.5. Unchanged at one
decimal: converter 0.3, electrical 0.2, safety 0.0, tower 1.2.

### A.6 What does not move

- **Six-family supply share: 83.7 %** (anemometry + pitch + external + brake_hydraulic +
  yaw + comms = 14,885 of 17,793). A denominator change cannot touch it - it is a ratio
  of row counts.
- **Converter warning rows: 44** on the post-COD de-duplicated basis (81 raw, 80
  de-duplicated including pre-COD rows). Unchanged.
- No event, energy, lead-time, matching or decomposition number depends on this
  denominator; it enters Table I's warning-supply column and nothing else.

---

## B. The all-four adjudication headline, now in a CSV

`analysis/map_adjudication_summary.csv` gains a leading `table` column
(`event` for the 41 pre-existing per-event rows, which are preserved byte for byte, and
`headline_scenario` for 7 new rows). Written by `map_adjudication_allfour.py`, which
reuses `map_sensitivity.MapEngine` / `variant_metrics` - the same objects
`map_adjudication.py` uses, so nothing is re-implemented - and which
`map_adjudication.py` now calls at the end of its own run so a re-run cannot drop the
scenario rows. The script gates on 4,213 events / 9,386.5 MWh / 7.528 % / 5.071 % /
5.441 % and aborts if any of them fails to reproduce.

| scenario | kind | long-lead share of T2 lost energy | delta vs frozen | warned events | long-lead events | big event (ev2178) |
|---|---|---|---|---|---|---|
| frozen map (published headline) | frozen | **7.5282 %** | - | 979 | 698 | long-lead |
| stop `WEC shut down` -> manual | single, sweep-covered | 5.2373 % | -2.2909 pp | 977 | 696 | unwarned |
| warning `Error brake resistor CHP` -> converter | single, sweep-covered | 7.9506 % | +0.4225 pp | 1,003 | 707 | long-lead |
| warning `Overload generator heating` -> auxiliary | single, NEW | 7.3096 % | -0.2186 pp | 978 | 697 | long-lead |
| warning `Parameter outside limits` -> manual | single, NEW | 5.2893 % | -2.2389 pp | 978 | 697 | unwarned |
| two NEW disagreements jointly | joint | **5.0707 %** | -2.4574 pp | 977 | 696 | unwarned |
| all four disagreements jointly | joint | **5.4412 %** | -2.0870 pp | 1,000 | 704 | unwarned |

Both quoted values reproduce exactly: **5.071 %** (two new) and **5.441 %** (all four).
`never_match` is realised as `manual`, which is in `map_sensitivity.NEVER_MATCH`, exactly
as the published sweep realises `WEC shut down`.

Two things worth noting from the new rows, neither of which was previously in an
artefact:

- The all-four value is **higher** than the two-new value (5.441 > 5.071) because
  `Error brake resistor CHP -> converter` pushes the share *up* (+0.42 pp; it is also
  the only flip that changes converter same-component coverage, 0 -> 28 events), and it
  is one of the two sweep-covered flips. The joint of all four is therefore not the
  most adverse combination; the most adverse single is `WEC shut down` at 5.237 % and
  the most adverse joint is the two-new pair at 5.071 %.
- The single largest headline event (ev2178, 210.1 MWh) is reclassified from long-lead
  to unwarned in four of the seven scenarios - every one that flips a message to
  `manual`. That is the mechanism behind both joint drops.

---

## C. Figure label: "actionable-unacted" -> "long-lead"

Display labels only; every CSV key and column name still spells it
`actionable_unacted`. Of fig1/fig3/fig5/fig6/fig7, `pdftotext` shows the string appears
in exactly two:

| figure | text before | text after | source |
|---|---|---|---|
| fig1 | legend "Actionable-unacted" | "Long-lead" | `figures.py::BUCKET_LBL` |
| fig5 | y-axis "Actionable-unacted share / of lost energy (%)" | "Long-lead share / of lost energy (%)" | `duration_grounding.py::fig5` |

fig3, fig6 and fig7 contain no "actionable" text and were not regenerated; fig2 and fig4
likewise (both are cut from the paper for the page cap). Byte-compared: fig2, fig3,
fig4, fig6, fig7 are untouched.

**Numbers on the regenerated figures are unchanged.** Every numeric token extracted with
`pdftotext -layout` from the previous PDFs matches the new ones exactly, for both
figures - fig1 still prints 83.8 / 8.7 / 7.5 for T2, 87.0 / 7.0 / 6.0 for T1 and
87.4 / 6.7 / 5.8 for T0; fig5 still prints the 0.5-72 h axis with the 17 h and 53 h
reference ticks. fig5's plain-text layout reflows because the shorter y-axis label
frees width; no drawn value changed. fig5 was redrawn from the frozen
`tact_curve.csv` plus `attribution.parquet` (read-only) rather than by re-running
`duration_grounding.py`, so the frozen `duration_grounding.csv`, `tact_curve.csv` and
`lead_vs_duration.csv` were not rewritten; the reference quantiles recomputed for the
axis marks came back at p25 17.3965 h, p50 52.9438 h, p75 167.2878 h, matching the
frozen values.

`analysis/ARTEFACT_KEY.md` gains a "Class names: CSV key vs paper label" section
recording `actionable_unacted` = paper class "long-lead".

---

## D. Greek SMD10TOWFGR corpus: full warning count

The paper's "roughly 300 warnings fleet-wide" was an extrapolation from three of the ten
turbine sheets (WT01 20 W / 74 A, WT05 45 W / 66 A, WT10 24 W / 49 A, `data/DATASET_SCOUT.md`
row 2), scaled by 10/3. The whole workbook has now been counted.

**Provenance.** Zenodo 10.5281/zenodo.14546480, "Six-Month Monitoring Dataset from a
10-Turbine Onshore Wind Farm in Greece", CC-BY-4.0. One file,
`SCADA__monitoring_dataset_2020.xlsx`, **180,707,378 bytes**, matching the record's
declared size exactly; downloaded to the local data volume (`$WTWG_GREEK_XLSX`). Counted by `analysis/greek_log_counts.py` - openpyxl `read_only=True`,
one sheet opened and closed at a time, rows streamed, never loaded whole. The workbook
has 20 sheets: `WT01_data.csv` .. `WT10_data.csv` and `WT01_logs.csv` .. `WT10_logs.csv`
(the `.csv` suffix is part of the sheet name).

| sheet | log rows | Warning log (W) | Alarm log (A) | Operation log (O) | System log (S) |
|---|---:|---:|---:|---:|---:|
| WT01_logs.csv | 16,037 | 20 | 74 | 15,788 | 155 |
| WT02_logs.csv | 25,444 | 60 | 61 | 25,153 | 170 |
| WT03_logs.csv | 23,731 | 129 | 395 | 22,682 | 525 |
| WT04_logs.csv | 19,623 | 18 | 37 | 19,508 | 60 |
| WT05_logs.csv | 22,501 | 45 | 66 | 22,177 | 213 |
| WT06_logs.csv | 25,293 | 128 | 74 | 24,871 | 220 |
| WT07_logs.csv | 25,645 | 62 | 94 | 25,354 | 135 |
| WT08_logs.csv | 24,202 | 120 | 66 | 23,821 | 195 |
| WT09_logs.csv | 24,083 | 82 | 86 | 23,820 | 95 |
| WT10_logs.csv | 24,059 | 24 | 49 | 23,933 | 53 |
| **fleet** | **230,618** | **688** | **1,002** | **227,107** | **1,821** |

**Fleet totals: 688 Warning-log (W) rows and 1,002 Alarm-log (A) rows**, 1 Jan - 30 Jun
2020, ten turbines. `Event type` takes exactly the four documented values across all
230,618 rows - no blanks and no fifth category, so nothing is unclassified.

Self-check: the three sheets behind the original estimate reproduce **exactly** (WT01
20/74, WT05 45/66, WT10 24/49), so the extrapolation's arithmetic was correct and its
sample was unlucky - those three are among the quietest turbines in the fleet. The real
warning count is **2.3x** the extrapolation and the alarm count **1.7x**. Per-turbine
dispersion is wide (18 to 129 warnings; WT03 alone holds 39 % of fleet alarms), which is
why a three-sheet sample missed by that much.

Consequence for the manuscript: "roughly 300 warnings fleet-wide" must become **688**.
The assessment does not change direction - 688 warnings over ~5 turbine-years against
17,793 post-COD warning rows over 159.06 turbine-years here is ~26x less warning supply
on ~32x less exposure, still far too thin for a second headline - but a structural
replication of the warned share and lead-time distribution is better supported than the
old figure implied.
