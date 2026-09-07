#!/usr/bin/env python3
"""STUDY_DESIGN v1.4(d) - claim ledger.

Every number the manuscript states that is NOT already read back out of a summary CSV
(decomposition.csv, leadtime_stats.csv, bootstrap.csv, controls_summary.csv,
counterfactual.csv, duration_grounding.csv, ...) is recomputed here from the frozen
stage-1/stage-2 parquets and compared with the value printed in `paper/main.tex`.
Each row records the claim, the paper's printed value, the recomputed value, the
tolerance implied by the printed precision, and a REPRODUCES / MISMATCH verdict.

Nothing is redefined: tier flags, energies, warned flags, leads and control anchors
are read as-is; the only arithmetic here is counting and summing.

Writes:
    analysis/claim_ledger.csv

    python3 claim_ledger.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

DERIVED = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
OUT_CSV = os.path.join(HERE, "claim_ledger.csv")

TIER_FLAG = "T2_wide_grid"
RULE, LOOKBACK_H, T_ACT_H = "same", 72, 6

# fig3's duration bucket edges, verbatim from figures.py::fig3
FIG3_EDGES = [0, 1 / 6, 1, 6, 24, np.inf]
FIG3_LABELS = ["<10 min", "10 min-1 h", "1-6 h", "6-24 h", ">=24 h"]


def main():
    att = pd.read_parquet(os.path.join(DERIVED, "attribution.parquet"))
    ctl = pd.read_parquet(os.path.join(DERIVED, "controls.parquet"))
    assert (att["event_id"].values == ctl["event_id"].values).all()

    tier = att[TIER_FLAG].values.astype(bool)
    s = att[tier].reset_index(drop=True)
    c = ctl[tier].reset_index(drop=True)
    E = s["E_mwh"].values.astype(float)
    warned = s[f"{RULE}_warn_{LOOKBACK_H}h"].values.astype(bool)
    lead = s[f"{RULE}_lead_h_{LOOKBACK_H}h"].values.astype(float)
    act = warned & (lead >= T_ACT_H)

    # ---------------------------------------------------------- validation gate
    print("=== VALIDATION GATE ===")
    gate = [("T2 events", len(s), 4213, 0), ("T2 MWh", E.sum(), 9386.5, 0.05),
            ("unwarned %", 100 * E[~warned].sum() / E.sum(), 83.78, 0.005),
            ("short-lead %", 100 * E[warned & ~act].sum() / E.sum(), 8.69, 0.005),
            ("actionable %", 100 * E[act].sum() / E.sum(), 7.53, 0.005),
            ("warned n", int(warned.sum()), 979, 0),
            ("warned MWh", E[warned].sum(), 1522.8, 0.05)]
    for name, got, want, tol in gate:
        ok = abs(got - want) <= tol
        print(f"  {name:<16} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
        assert ok, f"VALIDATION GATE FAILED: {name}"

    rows = []

    def claim(cid, text, where, printed, computed, tol, unit="", note=""):
        rows.append(dict(
            claim_id=cid, claim=text, paper_location=where,
            paper_value=printed, computed_value=computed, unit=unit,
            abs_diff=abs(computed - printed), tolerance=tol,
            verdict="REPRODUCES" if abs(computed - printed) <= tol else "MISMATCH",
            note=note))

    # --- 1. concentration: top-200 T2 events -------------------------------
    top200 = float(np.sort(E)[::-1][:200].sum() / E.sum() * 100)
    claim("C1", "the 200 largest T2 events carry 83.3% of T2 lost energy",
          "main.tex L301 (Methods, concentration)", 83.3, top200, 0.05, "% of T2 MWh",
          "top-200 by E_mwh within T2 wide-grid; ties are immaterial (201st = "
          f"{np.sort(E)[::-1][200]:.3f} MWh)")

    # --- 2. zero-measured-energy T2 events ---------------------------------
    nz = int((E == 0).sum())
    claim("C2a", "1,745 of the 4,213 T2 events carry zero measured energy",
          "main.tex L281 (measurement grid)", 1745, nz, 0, "events",
          "E_mwh exactly 0.0 - the merged window contains no 10-min bin start")
    claim("C2b", "...which is 41.4% of T2 events", "main.tex L281 (derived)",
          41.4, 100 * nz / len(E), 0.05, "% of T2 events", "")

    # --- 3. control match rate ON T2 ---------------------------------------
    mrate = 100 * float(c["c45_matched"].mean())
    exact = 100 * float((c["c45_offset_d"].abs() == 45).mean())
    claim("C3a", "controls match for 99.2% of T2 events",
          "main.tex L330", 99.2, mrate, 0.05, "% of T2 events",
          "NOTE: controls_summary.csv's 99.42% is over all 6,050 T0 events; the "
          "paper's figure is the T2 wide-grid subset, which is what is recomputed here")
    claim("C3b", "70.8% of T2 controls sit at the exact -45 d anchor",
          "main.tex L330", 70.8, exact, 0.05, "% of T2 events",
          "denominator is all 4,213 T2 events (unmatched count as not-at-anchor), "
          "matching controls_summary.csv's convention; 33 T2 events are unmatched")

    # --- 4. fig3 shortest-duration bucket ----------------------------------
    b = np.digitize(s["duration_h"].values, FIG3_EDGES[1:-1], right=False)
    counts = np.bincount(b, minlength=len(FIG3_LABELS))
    claim("C4", "n = 1,870 T2 outages shorter than ten minutes (fig. 3 bucket 1)",
          "main.tex L359 / fig3", 1870, int(counts[0]), 0, "events",
          "figures.py::fig3 EDGES [0, 1/6, 1, 6, 24, inf], np.digitize right=False; "
          "full bucket vector " + ", ".join(f"{l}={n:,}" for l, n
                                            in zip(FIG3_LABELS, counts)))

    # --- 5. actionable-unacted composition ---------------------------------
    n_act = int(act.sum())
    claim("C5a", "698 actionable-unacted T2 events",
          "main.tex L491/L599", 698, n_act, 0, "events", "")
    claim("C5b", "532 of the 698 actionable events carry zero measured energy",
          "main.tex L491", 532, int((E[act] == 0).sum()), 0, "events",
          "this is the count-weighted/energy-weighted divergence at its source")
    claim("C5c", "166 of the 698 carry the 706.6 MWh at risk",
          "main.tex L599", 166, int((E[act] > 0).sum()), 0, "events",
          "complement of C5b: 698 - 532 = 166")
    claim("C5d", "the actionable-unacted energy at risk is 706.6 MWh",
          "main.tex L599", 706.6, float(E[act].sum()), 0.05, "MWh",
          "also in counterfactual.csv; recomputed here as the anchor for C5b/C5c")

    # --- 6. manual-stop line -----------------------------------------------
    mm = att["is_manual_only"].values.astype(bool)
    E_manual = float(att.loc[mm, "E_mwh"].sum())
    E_t0 = float(att.loc[att["T0"].values.astype(bool), "E_mwh"].sum())
    claim("C6a", "397 manual-only merged events", "main.tex L329", 397,
          int(mm.sum()), 0, "events", "")
    claim("C6b", "manual-only events carry 2,321.7 MWh", "main.tex L329",
          2321.7, E_manual, 0.05, "MWh", "")
    claim("C6c", "manual-only energy is 19.2% of T0 lost energy", "main.tex L329",
          19.2, 100 * E_manual / E_t0, 0.05, "% of T0 MWh",
          f"T0 denominator {E_t0:,.1f} MWh")

    # --- 7. the adjacent count-weighted claim in the same paragraph as C5b ---
    keep = E > 0
    cw_ex0 = 100 * float(act[keep].sum()) / int(keep.sum())
    claim("C7", "excluding zero-energy events the count-weighted actionable share "
                "falls to 6.7%", "main.tex L492", 6.7, cw_ex0, 0.05,
          "% of nonzero-E T2 events",
          f"{int(keep.sum()):,} T2 events carry nonzero measured energy")

    led = pd.DataFrame(rows)
    led.to_csv(OUT_CSV, index=False)
    print(f"\nwrote {OUT_CSV}: {len(led):,} rows")
    print("\n=== CLAIM LEDGER ===")
    print(led[["claim_id", "claim", "paper_value", "computed_value", "abs_diff",
               "verdict"]].to_string(index=False,
                                     float_format=lambda x: f"{x:,.4f}"))
    bad = led[led.verdict == "MISMATCH"]
    print(f"\n{len(led) - len(bad)} of {len(led)} claims REPRODUCE; "
          f"{len(bad)} MISMATCH" + (":" if len(bad) else "."))
    for _, r in bad.iterrows():
        print(f"  MISMATCH {r.claim_id}: paper {r.paper_value} vs computed "
              f"{r.computed_value} ({r.claim})")
    return led


if __name__ == "__main__":
    main()
