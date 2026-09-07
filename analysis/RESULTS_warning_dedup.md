# Stage-5 results - warning-row de-duplication basis

Added 2026-09-06 in response to a referee point on Table I (`tab:families` in
`paper/main.tex`). Nothing frozen was changed: no parquet, no `component_map.csv`,
no existing script or CSV was touched. One new script and one new artefact:

```
warning_rows_by_family.py -> analysis/warning_rows_by_family.csv
```

## A. The referee point

Table I's `Warn. rows / turb.-yr` column was computed on the **de-duplicated**
warning population (19,150 rows), but the only per-family warning counts published
in the repo were `checks.md` section 4's `warning_log_rows`, which are **raw**
log-row counts (19,948 rows total, sourced from `component_map.csv`'s `n_rows`).
The two bases could not be reconciled from any artefact: pitch reads 3,920 raw,
and 3,920 / 171 = 22.9, against Table I's 22.0. The paper also never defined the
de-duplication anywhere.

## B. The de-duplication rule

The rule is applied once, in `build_warnings.py`, and is the only row-removal step
between the raw `Warning` population and `derived/warnings.parquet`:

```python
dup = w.duplicated(["farm", "turbine_id", "t0", "t1", "Code"], keep="first")
w = w[~dup]
```

Stated for the paper's Methods, in plain English:

> Two status-log warning rows are treated as the same warning when they agree on
> all five of farm, turbine, start timestamp, end timestamp and status code; the
> first such row is kept and the rest are dropped. This removes 798 exactly
> repeated rows and leaves 19,150 of the 19,948 warning rows in the analysed span.

The duplicates are an artefact of the vendor export, not of turbine behaviour:
`data/PROFILE.md` section 3 records 8,680 exactly duplicated rows across the whole
status log, concentrated pathologically on Penmanshiel WT01. Note that the
de-duplication key does **not** include `Message`, so it is code-level, not
message-level; in this corpus code and message are in practice one-to-one within a
farm, so no cross-message collapse occurs.

Two upstream filters in `build_warnings.py` are inert for warnings and remove
nothing: the parseable-start filter and the negative-duration filter both leave
19,948 rows (`checks.md` section 4 steps).

## C. Per-family counts on both bases

Written to `analysis/warning_rows_by_family.csv`. Rates are over the same 171
turbine-years used by Table I (`data/PROFILE.md` section 4).

| family | rows_raw | rows_dedup | per_ty_raw | per_ty_dedup |
|---|---|---|---|---|
| anemometry | 4,278 | 4,148 | 25.02 | 24.26 |
| auxiliary | 921 | 895 | 5.39 | 5.23 |
| brake_hydraulic | 2,614 | 2,529 | 15.29 | 14.79 |
| comms | 1,397 | 1,262 | 8.17 | 7.38 |
| control | 229 | 218 | 1.34 | 1.27 |
| converter | 81 | 80 | 0.47 | 0.47 |
| drivetrain | 404 | 393 | 2.36 | 2.30 |
| electrical | 76 | 75 | 0.44 | 0.44 |
| external | 3,009 | 2,808 | 17.60 | 16.42 |
| generator | 1,310 | 1,268 | 7.66 | 7.42 |
| pitch | 3,920 | 3,770 | 22.92 | 22.05 |
| tower | 210 | 208 | 1.23 | 1.22 |
| yaw | 1,499 | 1,496 | 8.77 | 8.75 |
| **total** | **19,948** | **19,150** | | |

`grid`, `manual` and `safety` take no warning message at all and so appear in
neither basis; Table I's `safety` row of 0 is structural.

The script asserts both totals (19,948 and 19,150) and fails loudly if either
moves.

## D. Table I basis, confirmed

All ten families printed in `tab:families` reproduce on the **de-duplicated**
basis and none reproduces on the raw basis where the two differ:

| family | Table I | per_ty_dedup | per_ty_raw | verdict |
|---|---|---|---|---|
| pitch | 22.0 | 22.05 | 22.92 | MATCH |
| converter | 0.5 | 0.47 | 0.47 | MATCH |
| tower | 1.2 | 1.22 | 1.23 | MATCH |
| drivetrain | 2.3 | 2.30 | 2.36 | MATCH |
| generator | 7.4 | 7.42 | 7.66 | MATCH |
| electrical | 0.4 | 0.44 | 0.44 | MATCH |
| control | 1.3 | 1.27 | 1.34 | MATCH |
| safety | 0 | 0.00 | 0.00 | MATCH |
| anemometry | 24.3 | 24.26 | 25.02 | MATCH |
| brake_hydraulic | 14.8 | 14.79 | 15.29 | MATCH |

10 / 10 MATCH. Table I is therefore internally consistent; what was missing was
the definition and the supporting artefact, both now supplied.

## E. One residual inconsistency in the prose

`main.tex` (near "only 81 converter warning rows", in the same subsection as
Table I) quotes the **raw** converter count. On the de-duplicated basis the
converter family holds **80** rows. The per-turbine-year rate is 0.47 on both
bases and so rounds to 0.5 either way, and the same-component warned share of
0.0% is unaffected, but the sentence and the table currently sit on different
bases within one paragraph. Either quote 80 to match Table I, or say explicitly
that 81 is the raw count before de-duplication. Not changed here:
`paper/main.tex` is out of scope for this pass.

## F. Ledger note

`analysis/claim_ledger.csv` is regenerated wholesale by `claim_ledger.py`
(`led.to_csv(OUT_CSV)`), so a hand-appended row there would be silently destroyed
on the next run. This section is the durable record instead. If these checks
should become standing ledger claims, they need to be added to `claim_ledger.py`
itself rather than to the CSV.

---

# Addendum 2026-09-06 - the commissioning cut is applied to events but not to warnings

A second referee point, checked after section F was written. It is correct, and it
is a real basis mismatch, not a rounding quibble.

## G. The rule as the paper states it

`paper/main.tex` section Data: "pre-commercial-operation data is excluded (before
2016-04-15 at Kelmarsh, 2016-09-01 at Penmanshiel)". `STUDY_DESIGN.md` says the
same: "Commissioning exclusion: drop pre-COD data". `data/PROFILE.md` section 2
records both dates as whole-farm CODs (all 6 Kelmarsh turbines 2016-04-15, all 14
Penmanshiel turbines 2016-09-01), so the rule is per farm, not per turbine, and
`common.py` implements it that way in `pre_cod_mask`.

## H. Events and warnings are NOT on the same basis

| population | script | pre-COD handling |
|---|---|---|
| stops -> events.parquet | `build_events.py` line 156 | `pre = C.pre_cod_mask(fo)` and the rows are **dropped** |
| warnings -> warnings.parquet | `build_warnings.py` line 48 | `w["pre_cod"] = C.pre_cod_mask(w)`, "flagged, **NOT dropped**" |

Confirmed against the frozen parquets: `events.parquet` holds 0 pre-COD events and
starts 2016-04-21, whereas `warnings.parquet` holds **1,357** pre-COD rows out of
19,150 (Kelmarsh 281, Penmanshiel 1,076) spanning 2016-01-14 to 2016-08-31. The
referee's 1,357 is exact. No downstream script filters on `pre_cod`; the only other
uses of `pre_cod_mask` are in `counterfactual.py` and `make_checks.py`, both on
stop rows. `attribute.py` consumes the warnings parquet whole.

## I. Effect on matching is nil; effect on Table I is not

Of the 1,357 pre-COD warning rows, only **10** fall inside the 72 h lookback of any
event, touching **7** of the 4,213 T2 wide-grid events (the same 10 and 7 at T0 and
at narrow-grid T2). All 7 sit in the first two days after Penmanshiel's COD. Every
one already has post-COD warnings in the same window, and in the only case where
the pre-COD row is same-family as the stop (ev4009, pitch, 0.05 MWh) a post-COD
pitch warning is present in the window anyway. So no warned share, lead time or
energy figure moves. The exposure is confined to Table I's supply column and to two
prose numbers.

## J. The denominator has to move with the numerator

PROFILE section 4's **171** turbine-years is a file count (turbine x calendar year)
over the full observed status-log span, 2016-01-14 to 2024-12-31 - pre-COD months
included. Summing each turbine's observed span gives 163.81 turbine-years raw and
159.91 post-COD, i.e. the cut removes 3.90 turbine-years of exposure (2.4%).
Rescaling 171 by that fraction gives **166.93** turbine-years as the consistent
post-COD denominator. `turbine_years_cod()` in `warning_rows_by_family.py` computes
it from the status log rather than hard-coding it.

## K. Per-family, old against new

New CSV columns: `rows_dedup_cod`, `per_ty_dedup_cod`. Old = 19,150 rows / 171 ty
(what Table I prints today). New = 17,793 rows / 166.93 ty.

| family | old rows | old rate | new rows | new rate | printed cell |
|---|---|---|---|---|---|
| anemometry | 4,148 | 24.26 | 3,792 | 22.72 | 24.3 -> 22.7 |
| auxiliary | 895 | 5.23 | 854 | 5.12 | not printed |
| brake_hydraulic | 2,529 | 14.79 | 2,415 | 14.47 | 14.8 -> 14.5 |
| comms | 1,262 | 7.38 | 1,052 | 6.30 | not printed |
| control | 218 | 1.27 | 217 | 1.30 | 1.3 -> 1.3 (unchanged) |
| converter | 80 | 0.47 | 44 | 0.26 | 0.5 -> 0.3 |
| drivetrain | 393 | 2.30 | 345 | 2.07 | 2.3 -> 2.1 |
| electrical | 75 | 0.44 | 37 | 0.22 | 0.4 -> 0.2 |
| external | 2,808 | 16.42 | 2,559 | 15.33 | not printed |
| generator | 1,268 | 7.42 | 1,218 | 7.30 | 7.4 -> 7.3 |
| pitch | 3,770 | 22.05 | 3,572 | 21.40 | 22.0 -> 21.4 |
| tower | 208 | 1.22 | 193 | 1.16 | 1.2 -> 1.2 (unchanged) |
| yaw | 1,496 | 8.75 | 1,495 | 8.96 | not printed |
| **total** | **19,150** | | **17,793** | | |

**7 of the 10 printed cells change.** `safety` is 0 on every basis. `control` and
`tower` hold because the smaller denominator offsets the smaller numerator - note
`control` and `yaw` actually rise, since they lose almost no rows (1 each) while the
denominator shrinks.

## L. The two prose numbers

- **"only 80 converter warning rows"**: on the post-COD basis this is **44**. 36 of
  the family's 80 rows, 45%, are pre-COD. This is the single largest proportional
  hit of any family, and it strengthens the paper's argument rather than weakening
  it. `electrical` is hit similarly hard: 75 -> 37.
- **"supply 83.6% of the 19,150 de-duplicated warning rows"**: on the post-COD basis
  the six families supply 14,885 of 17,793 = **83.7%**. The claim is basis-robust;
  only the total needs restating.

## M. What to change

`paper/main.tex` is out of scope for this pass, so nothing was edited there. The
minimal fix is one of two choices, and it must be made explicit either way:

1. **Apply the cut** (preferred, since it matches what the events already do):
   rebuild Table I's supply column on 17,793 rows over 166.93 turbine-years, change
   the 7 cells above, change 80 to 44, and restate the total in the 83.6% sentence.
2. **Keep the full span** and say so: change the caption to state that the warning
   supply column deliberately uses the whole logged span including the
   pre-commercial-operation months, and say why the event population does not.

Files touched by this addendum: `analysis/warning_rows_by_family.py` (added
`rows_dedup_cod`, `per_ty_dedup_cod`, `turbine_years_cod()` and three new asserts)
and `analysis/warning_rows_by_family.csv` (regenerated). Nothing frozen was changed.
