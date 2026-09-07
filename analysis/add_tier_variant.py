#!/usr/bin/env python3
"""STUDY_DESIGN v1.6(d) - label the grid-exclusion variant in events_summary.csv.

`events_summary.csv` is written by `build_events.py` (its tier-summary block, which
loops over the literal column names T0/T1/T2). Its `T1`/`T2` rows are the NARROW
grid variant - only the four messages named verbatim in STUDY_DESIGN's T1 list - so
its `T2` row reads 4,238 events / 9,635.6 MWh, not the manuscript's primary 4,213 /
9,386.5. ARTEFACT_KEY.md calls this the outright trap. v1.6(d) adds a `tier_variant`
column so the rows cannot be misread.

Why this is a POST-PROCESSOR and not an edit to `build_events.py`:
re-running that writer is not cheap - it rebuilds every merged event's lost energy
from the 10-minute SCADA cache for 6,050 merged windows plus 6,053 constituent
windows, and it would rewrite the frozen `events.parquet` and `event_constituents.parquet`
on the read-only derived volume. STUDY_DESIGN v1.6(d) asks for a relabel, not a
recomputation, so this script adds the column in place and leaves every existing
value byte-identical. The frozen numbers are re-read from `events.parquet` and
checked against the CSV before it is touched.

No row is added: the file still has no primary (wide-grid) cell, exactly as
ARTEFACT_KEY.md documents. `tier_variant` is `n/a` for T0 (no grid rule applies -
T0 is every forced-outage event), `narrow` for T1/T2, and `wide_grid` for
T1_wide_grid/T2_wide_grid rows should a future re-run emit them.

Writes:
    analysis/events_summary.csv  (in place, one column added)

    python3 add_tier_variant.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import common as C

CSV = os.path.join(HERE, "events_summary.csv")

VARIANT = {"T0": "n/a", "T1": "narrow", "T2": "narrow",
           "T1_wide_grid": "wide_grid", "T2_wide_grid": "wide_grid"}


def main():
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    ev = pd.read_parquet(C.EVENTS_PARQUET)
    s = att[att["T2_wide_grid"].values]
    E = s["E_mwh"].values.astype(float)
    warned = s["same_warn_72h"].values.astype(bool)
    lead = s["same_lead_h_72h"].values.astype(float)
    act = warned & (lead >= 6.0)
    n3 = int((warned & (s["same_n_72h"].values >= 3)).sum())
    e3 = float(E[warned & (s["same_n_72h"].values >= 3)].sum())

    print("=== VALIDATION GATE ===")
    checks = [("T2 wide events", len(E), 4213, 0),
              ("T2 wide MWh", E.sum(), 9386.5, 0.05),
              ("same-warned n", int(warned.sum()), 979, 0),
              ("same-warned MWh", E[warned].sum(), 1522.8, 0.05),
              ("actionable %", 100 * float(E[act].sum() / E.sum()), 7.53, 0.005),
              (">=3-row subset n", n3, 799, 0),
              (">=3-row subset MWh", e3, 840.5, 0.05),
              # the narrow cell this file actually reports
              ("T2 narrow events", int(ev["T2"].sum()), 4238, 0),
              ("T2 narrow MWh", float(ev.loc[ev["T2"], "E_mwh"].sum()),
               9635.6, 0.05)]
    for name, got, want, tol in checks:
        ok = abs(got - want) <= tol
        print(f"  {name:<20} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
        assert ok, f"VALIDATION GATE FAILED: {name}"

    d = pd.read_csv(CSV)
    before = d.copy()
    if "tier_variant" in d.columns:
        print("\ntier_variant already present; nothing to do")
        return d
    unknown = sorted(set(d["tier"]) - set(VARIANT))
    assert not unknown, f"unmapped tier label(s) in {CSV}: {unknown}"

    # the CSV's own T2 row must be the NARROW variant - that is the whole point
    r = d[d.tier == "T2"].iloc[0]
    assert int(r["events"]) == 4238 and abs(float(r["E_mwh"]) - 9635.6) < 0.05, \
        "events_summary.csv T2 row is not the narrow variant; do not relabel blindly"

    d.insert(1, "tier_variant", d["tier"].map(VARIANT))
    # every pre-existing value must be untouched
    for c in before.columns:
        assert d[c].equals(before[c]), f"column {c} changed"
    d.to_csv(CSV, index=False)
    print(f"\nwrote {CSV} (tier_variant added, {len(d)} rows, "
          f"no existing value changed)")
    print(d.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    return d


if __name__ == "__main__":
    main()
