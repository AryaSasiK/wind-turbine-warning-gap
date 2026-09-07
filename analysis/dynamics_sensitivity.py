#!/usr/bin/env python3
"""STUDY_DESIGN v1.6(a) - dynamics eligibility sensitivity.

v1.3(c)'s per-event trend statistics (rate ratio, Laplace) were computed on warned
events carrying at least 3 matching warning rows in the 72 h window - a floor fixed
at implementation, disclosed but never varied. This script recomputes them at floors
>=1, >=2, >=3 for both matching rules and writes an inclusion flow, so the reported
>=3 cell can be checked against the two weaker eligibility rules.

Declared conventions (STUDY_DESIGN v1.6(a), pre-registered):
  - rate ratio r = (n_last24 / 24) / (n_prior48 / 48), windows [0,24) and [24,72)
    hours before the event start;
  - n_prior48 == 0 with n_last24 > 0 is an INFINITE ratio and counts as both
    "ratio > 1" and "ratio >= 2";
  - an event with zero rows in BOTH windows is UNDEFINED and excluded at every
    floor (it cannot occur at floor >=1 by construction - confirmed below);
  - the count-weighted median is reported as `inf` when the median element is
    infinite.

The warning join is the same object warning_dynamics.py uses (WarnIndex), and it is
re-verified against attribution.parquet's frozen any_n_72h / same_n_72h before
anything is computed.

Writes:
    analysis/dynamics_sensitivity.csv

    python3 dynamics_sensitivity.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import common as C
from warning_dynamics import (LOOKBACK, TIER_FLAG, LAST_H, PRIOR_H, WarnIndex,
                              verify_join)

FLOORS = (1, 2, 3)
OUT_CSV = os.path.join(HERE, "dynamics_sensitivity.csv")


# ------------------------------------------------------------- validation gate
def validation_gate(att):
    s = att[att[TIER_FLAG].values].reset_index(drop=True)
    E = s["E_mwh"].values.astype(float)
    warned = s["same_warn_72h"].values.astype(bool)
    lead = s["same_lead_h_72h"].values.astype(float)
    act = warned & (lead >= 6.0)
    n3 = s["same_n_72h"].values >= 3
    sub = warned & n3

    print("=== VALIDATION GATE ===")
    checks = [
        ("T2 wide events", len(s), 4213, 0),
        ("T2 wide MWh", E.sum(), 9386.5, 0.05),
        ("same-warned n", int(warned.sum()), 979, 0),
        ("same-warned MWh", E[warned].sum(), 1522.8, 0.05),
        ("actionable %", 100 * E[act].sum() / E.sum(), 7.53, 0.005),
        (">=3-row subset n", int(sub.sum()), 799, 0),
        (">=3-row subset MWh", E[sub].sum(), 840.5, 0.05),
    ]
    for name, got, want, tol in checks:
        ok = abs(got - want) <= tol
        print(f"  {name:<20} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
        assert ok, f"VALIDATION GATE FAILED: {name}"
    return s


# ----------------------------------------------------------------- statistics
def weighted_median_with_inf(v, w):
    v = np.asarray(v, dtype=float)
    w = np.asarray(w, dtype=float)
    o = np.argsort(v, kind="stable")
    v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cw, 0.5, "left")])


def per_event(idx, sub, rule):
    """Rate ratio, Laplace statistic and window counts for each event in `sub`."""
    rr, lap, nl, npr = [], [], [], []
    for f, t, a, fs in zip(sub.farm, sub.turbine_id, sub.start, sub.families_all):
        hb = idx.hours_before(f, t, a, frozenset(fs), rule)
        n_last = int((hb < LAST_H).sum())
        n_prior = int(((hb >= LAST_H) & (hb < PRIOR_H)).sum())
        nl.append(n_last)
        npr.append(n_prior)
        if n_prior == 0 and n_last == 0:
            rr.append(np.nan)                      # undefined: no rows either side
        elif n_prior == 0:
            rr.append(np.inf)                      # declared convention
        else:
            rr.append((n_last / LAST_H) / (n_prior / (PRIOR_H - LAST_H)))
        N = len(hb)
        if N == 0:
            lap.append(np.nan)
        else:
            tt = LOOKBACK - hb                     # time forward from window start
            lap.append((tt.mean() - LOOKBACK / 2.0)
                       / (LOOKBACK / np.sqrt(12.0 * N)))
    return (np.asarray(rr, float), np.asarray(lap, float),
            np.asarray(nl, int), np.asarray(npr, int))


def main():
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    s = validation_gate(att)

    wn = pd.read_parquet(os.path.join(C.DERIVED, "warnings.parquet"))
    idx = WarnIndex(wn)
    print("\n=== JOIN VERIFICATION (against attribution.parquet) ===")
    verify_join(idx, s)

    rows, flow = [], []
    for rule in ("same", "any"):
        wcol, ncol = f"{rule}_warn_{LOOKBACK}h", f"{rule}_n_{LOOKBACK}h"
        warned = s[s[wcol].values]
        n_warned, E_warned = len(warned), float(warned["E_mwh"].sum())
        print(f"\n=== rule = {rule}: {n_warned:,} warned events / "
              f"{E_warned:,.1f} MWh ===")

        prev_n, prev_e = n_warned, E_warned
        for floor in FLOORS:
            sub = warned[warned[ncol].values >= floor]
            E = sub["E_mwh"].values.astype(float)
            tot = float(E.sum())
            rr, lap, nl, npr = per_event(idx, sub, rule)

            undef = np.isnan(rr)
            defined = ~undef
            rrd, lapd, Ed = rr[defined], lap[defined], E[defined]
            totd = float(Ed.sum())

            def sh(m):
                return float(m.mean()), float(Ed[m].sum() / totd)

            f_gt1_n, f_gt1_e = sh(rrd > 1)         # inf satisfies both by convention
            f_ge2_n, f_ge2_e = sh(rrd >= 2)
            lap_ok = ~np.isnan(lapd)
            f_lap_n = float((lapd[lap_ok] > 0).mean())
            f_lap_e = float(Ed[lap_ok][lapd[lap_ok] > 0].sum()
                            / Ed[lap_ok].sum())
            med_c = float(np.median(rrd))
            med_e = weighted_median_with_inf(rrd, Ed)

            rows.append(dict(
                rule=rule, min_warning_rows=floor,
                n_events=len(sub), E_mwh=tot,
                share_of_warned_events=len(sub) / n_warned,
                share_of_warned_energy=tot / E_warned,
                n_warned_events_rule=n_warned, E_warned_mwh_rule=E_warned,
                n_infinite_ratio=int(np.isinf(rrd).sum()),
                n_undefined=int(undef.sum()),
                frac_rr_gt1_count=f_gt1_n, frac_rr_gt1_energy=f_gt1_e,
                frac_rr_ge2_count=f_ge2_n, frac_rr_ge2_energy=f_ge2_e,
                median_rr_count=med_c, median_rr_energy=med_e,
                frac_laplace_gt0_count=f_lap_n, frac_laplace_gt0_energy=f_lap_e,
                median_laplace_count=float(np.median(lapd[lap_ok])),
                n_defined=int(defined.sum()),
                direction_holds=bool((f_gt1_n > 0.5) and (f_gt1_e > 0.99)),
            ))
            flow.append(dict(
                rule=rule, step=f"floor>={floor}",
                n_events=len(sub), E_mwh=tot,
                n_dropped=prev_n - len(sub), E_dropped_mwh=prev_e - tot,
                n_cum_dropped=n_warned - len(sub),
                E_cum_dropped_mwh=E_warned - tot))
            prev_n, prev_e = len(sub), tot

            print(f"  floor >={floor}: n {len(sub):>5,} ({100*len(sub)/n_warned:5.1f} % "
                  f"of warned)  E {tot:>8,.1f} MWh "
                  f"({100*tot/E_warned:5.1f} %)  inf {int(np.isinf(rrd).sum()):>4,}  "
                  f"undef {int(undef.sum())}  "
                  f"r>1 {100*f_gt1_n:5.2f} % / {100*f_gt1_e:6.3f} % E  "
                  f"r>=2 {100*f_ge2_n:5.2f} % / {100*f_ge2_e:6.3f} % E  "
                  f"med r {med_c:.3f}  Laplace>0 {100*f_lap_n:5.2f} %")

        # inclusion flow header row (the warned population itself)
        flow.insert(len(flow) - len(FLOORS),
                    dict(rule=rule, step="warned (no floor)", n_events=n_warned,
                         E_mwh=E_warned, n_dropped=0, E_dropped_mwh=0.0,
                         n_cum_dropped=0, E_cum_dropped_mwh=0.0))

    out = pd.DataFrame(rows)
    fl = pd.DataFrame(flow)
    fl = fl.assign(**{c: np.nan for c in out.columns if c not in fl.columns})
    out = out.assign(table="statistics")
    fl = fl.assign(table="inclusion_flow")
    both = pd.concat([out, fl], ignore_index=True, sort=False)
    both.to_csv(OUT_CSV, index=False)
    print(f"\nwrote {OUT_CSV}: {len(both):,} rows")

    print("\n=== inclusion flow ===")
    print(fl[["rule", "step", "n_events", "E_mwh", "n_dropped", "E_dropped_mwh"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    print("\n=== direction check (majority of events and >99 % of energy with r > 1) ===")
    for _, r in out.iterrows():
        print(f"  {r['rule']:>4} floor >={int(r['min_warning_rows'])}: "
              f"count {100*r['frac_rr_gt1_count']:.2f} % (>50 % "
              f"{'YES' if r['frac_rr_gt1_count'] > 0.5 else 'NO'})  "
              f"energy {100*r['frac_rr_gt1_energy']:.3f} % (>99 % "
              f"{'YES' if r['frac_rr_gt1_energy'] > 0.99 else 'NO'})")
    return both


if __name__ == "__main__":
    main()
