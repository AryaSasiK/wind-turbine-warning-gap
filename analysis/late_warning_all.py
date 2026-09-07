#!/usr/bin/env python3
"""STUDY_DESIGN v1.4(b) - the late-warning statistic on ALL warned events.

v1.3(c)'s per-event trend statistics carried a >= 3-matching-warning-row eligibility
rule (a rate ratio is undefined on fewer rows). That was an implementation reading,
not pre-registered, and it means the "silent until the last day" reading was supported
only on a subset (799 of 979 same-component-warned events; 840.5 of 1,522.8 MWh).
v1.4(b) replaces it with the unrestricted statistic:

    of the 979 same-component-warned T2 events, what share of the warned lost energy
    (and of the warned events) comes from events whose EVERY in-window same-component
    warning lies inside the final 24 h before the event start?

AN IDENTITY, NOT A COINCIDENCE
------------------------------
"every in-window warning is inside the final 24 h" and "the EARLIEST in-window warning
is inside the final 24 h" are the SAME event: the earliest warning is by construction
the one with the largest hours-before, so all rows lie inside 24 h exactly when the
maximum does, i.e. exactly when lead < 24 h. The two are computed here by independent
routes - one by testing every matching row, one from the lead - and asserted equal.
That also makes the companion statistic a direct cross-check against
`leadtime_stats.csv`: the earliest-inside-24 h ENERGY share must be 1 - frac_ge_24h.

Warning sets are re-derived from `warnings.parquet` under the FROZEN component map
using attribute.py's window conventions (half-open [start - 72 h, start), warnings
placed by START timestamp, never-match families external/grid/manual); the rebuild is
verified against the frozen attribution columns before anything is computed
(map_sensitivity.build_candidates / MapEngine, which carry that JOIN CHECK).

Writes:
    analysis/late_warning_all.csv

    python3 late_warning_all.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import map_sensitivity as MS

OUT_CSV = os.path.join(HERE, "late_warning_all.csv")
LATE_H = 24.0
MIN_ROWS_FOR_TREND = 3          # the v1.3(c) eligibility rule, quantified here


def main():
    cm, stop_fam, warn_fam = MS.load_map()
    ev, wn, att = MS.load_frames()
    cand = MS.build_candidates(ev, wn)
    eng = MS.MapEngine(ev, wn, stop_fam, warn_fam, cand)

    # ---- JOIN CHECK: the rebuild must reproduce the frozen columns exactly ----
    ev_pos, warn_pos, hb = cand
    any_n = np.bincount(ev_pos, minlength=len(ev)).astype(np.int64)
    assert (any_n == att["any_n_72h"].values).all()
    warn_s, n_s, lead_s, _ = eng.match([])
    assert (n_s == att["same_n_72h"].values).all()
    assert (warn_s == att["same_warn_72h"].values).all()
    print(f"  JOIN CHECK any_n_72h {any_n.sum():,} / same_n_72h {n_s.sum():,} "
          f"reproduced: OK")

    tier = att[MS.TIER_FLAG].values.astype(bool)
    E = att["E_mwh"].values.astype(float)
    assert tier.sum() == 4213 and abs(E[tier].sum() - 9386.5) < 0.05
    print(f"T2 wide-grid: {int(tier.sum()):,} events / {E[tier].sum():,.1f} MWh")

    # ---- per-event maxima of hours-before, per rule ---------------------------
    # `same` uses the frozen-map match mask; `any` uses every candidate row.
    sc0, wc0 = eng.codes([])
    wcode = wc0[eng.cand_warn_msg_id]
    bits = (np.int64(1) << sc0[eng.pair_msg])
    ev_mask = np.bitwise_or.reduceat(bits, eng.pair_starts)
    ok_same = (((ev_mask[ev_pos] >> wcode) & 1) == 1) & (~eng.never[wcode])

    rows = []
    for rule, ok in (("same", ok_same), ("any", np.ones(len(ev_pos), dtype=bool))):
        n_rows = np.bincount(ev_pos[ok], minlength=len(ev)).astype(np.int64)
        # route 1: test EVERY matching row directly
        max_hb = np.full(len(ev), -np.inf)
        min_hb = np.full(len(ev), np.inf)
        np.maximum.at(max_hb, ev_pos[ok], hb[ok])
        np.minimum.at(min_hb, ev_pos[ok], hb[ok])
        warned = n_rows > 0
        all_inside = warned & (max_hb < LATE_H)         # every row inside final 24 h
        # route 2: via the lead (earliest matching warning)
        lead = att[f"{rule}_lead_h_72h"].values.astype(float)
        assert (np.isfinite(lead) == warned).all(), f"{rule}: warned flag mismatch"
        assert np.allclose(max_hb[warned], lead[warned], atol=1e-9), \
            f"{rule}: max hours-before != frozen lead"
        earliest_inside = warned & (lead < LATE_H)
        assert (all_inside == earliest_inside).all(), \
            f"{rule}: the two routes disagree - the identity is broken"

        m = tier & warned
        Ew = E[m]
        tot_e, tot_n = Ew.sum(), int(m.sum())
        sub3 = m & (n_rows >= MIN_ROWS_FOR_TREND)

        def add(metric, sel, note=""):
            rows.append(dict(
                rule=rule, population="T2_wide_grid_warned", metric=metric,
                n_events=int(sel.sum()), E_mwh=float(E[sel].sum()),
                pct_of_warned_events=100 * int(sel.sum()) / tot_n,
                pct_of_warned_energy=100 * float(E[sel].sum()) / tot_e,
                denom_n_events=tot_n, denom_E_mwh=float(tot_e), note=note))

        add("warned_total", m, "denominator")
        add("every_warning_inside_final_24h", m & all_inside,
            "v1.4(b) headline: no in-window warning earlier than 24 h before the stop")
        add("earliest_warning_inside_final_24h", m & earliest_inside,
            "identical set to the row above, computed from the lead (lead < 24 h)")
        add("lead_ge_24h", m & warned & (lead >= LATE_H),
            "complement; cross-checks leadtime_stats.csv frac_ge_24h")
        add("every_warning_inside_final_6h", m & warned & (lead < 6.0),
            "companion at T_act = 6 h")
        add(f"trend_eligible_subset_ge{MIN_ROWS_FOR_TREND}rows", sub3,
            "coverage of the v1.3(c) >=3-row subset, for the v1.4(b) disclosure")
        add(f"trend_eligible_and_every_warning_inside_final_24h", sub3 & all_inside,
            "the v1.3(c) 'zero rows before the last 24 h' events, subset only")

        # cross-check against the frozen artefact
        ls = pd.read_csv(os.path.join(HERE, "leadtime_stats.csv"))
        r = ls[(ls.tier == "T2") & (ls.rule == rule)]
        want_e = 100 * (1 - float(r[r.weight == "energy"].frac_ge_24h.iloc[0]))
        want_n = 100 * (1 - float(r[r.weight == "count"].frac_ge_24h.iloc[0]))
        got_e = rows[-6]["pct_of_warned_energy"]
        got_n = rows[-6]["pct_of_warned_events"]
        print(f"  CROSS-CHECK {rule:>4}: earliest-inside-24h energy "
              f"{got_e:.4f}% vs leadtime_stats 1-frac_ge_24h {want_e:.4f}%  "
              f"{'OK' if abs(got_e - want_e) < 1e-6 else 'FAIL'}; "
              f"count {got_n:.4f}% vs {want_n:.4f}%  "
              f"{'OK' if abs(got_n - want_n) < 1e-6 else 'FAIL'}")
        assert abs(got_e - want_e) < 1e-6 and abs(got_n - want_n) < 1e-6

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}: {len(out):,} rows")
    print("\n=== late-warning statistic, ALL warned T2 events ===")
    print(out[["rule", "metric", "n_events", "E_mwh", "pct_of_warned_events",
               "pct_of_warned_energy"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    return out


if __name__ == "__main__":
    main()
