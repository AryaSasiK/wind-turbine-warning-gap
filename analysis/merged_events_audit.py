#!/usr/bin/env python3
"""STUDY_DESIGN v1.6(c) - audit of the merged events with more than one constituent.

build_events.py merges overlapping/nested forced-outage stops per turbine BEFORE
tiering, so a merged event inherits every constituent's message, its tier flags are
"survives if ANY constituent survives", its displayed family is the family of the
LONGEST constituent, and attribute.py matches same-component warnings against
`families_all` - the union over constituents. Exactly 3 of the 6,050 merged events
have more than one constituent stop, so the whole apparatus turns on three rows.
This script lays those three out constituent by constituent and then re-runs the
attribution for them under the alternative rule

    "only the DISPLAYED family (the longest constituent's family) may match"

to show how much of the headline depends on the union reading.

Method for the alternative rule: attribute.attribute() - the frozen matcher, same
half-open [start - 72 h, start) window, same start-timestamp convention, same
never-match families - is re-run for these 3 events ONLY, with fam_set replaced by
the singleton {displayed family}. Every other event's frozen flags are untouched;
the headline is then recomputed over all 4,213 T2 wide-grid events with the three
rows swapped in. Nothing frozen is overwritten.

Writes:
    analysis/merged_events_audit.csv

    python3 merged_events_audit.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import attribute as A
import common as C

TIER_FLAG = "T2_wide_grid"
RULE, LOOKBACK_H, T_ACT_H = "same", 72, 6
OUT_CSV = os.path.join(HERE, "merged_events_audit.csv")
RELEASE_REPO = os.path.join(PROJECT, "release", "wind-turbine-warning-gap")


def klass(warned, lead):
    if not warned:
        return "unwarned"
    return "actionable-unacted" if lead >= T_ACT_H else "short-lead"


def main():
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    ev = pd.read_parquet(C.EVENTS_PARQUET)
    cons = pd.read_parquet(os.path.join(C.DERIVED, "event_constituents.parquet"))

    s = att[att[TIER_FLAG].values].reset_index(drop=True)
    E = s["E_mwh"].values.astype(float)
    warned = s[f"{RULE}_warn_{LOOKBACK_H}h"].values.astype(bool)
    lead = s[f"{RULE}_lead_h_{LOOKBACK_H}h"].values.astype(float)
    act = warned & (lead >= T_ACT_H)
    point = float(E[act].sum() / E.sum())

    # ------------------------------------------------------- validation gate ---
    n3 = int((warned & (s["same_n_72h"].values >= 3)).sum())
    e3 = float(E[warned & (s["same_n_72h"].values >= 3)].sum())
    print("=== VALIDATION GATE ===")
    checks = [("T2 wide events", len(E), 4213, 0),
              ("T2 wide MWh", E.sum(), 9386.5, 0.05),
              ("same-warned n", int(warned.sum()), 979, 0),
              ("same-warned MWh", E[warned].sum(), 1522.8, 0.05),
              ("actionable %", 100 * point, 7.53, 0.005),
              (">=3-row subset n", n3, 799, 0),
              (">=3-row subset MWh", e3, 840.5, 0.05)]
    for name, got, want, tol in checks:
        ok = abs(got - want) <= tol
        print(f"  {name:<20} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
        assert ok, f"VALIDATION GATE FAILED: {name}"

    # ------------------------------------------------------- the three events ---
    mg = ev[ev["n_stops"] > 1].copy()
    assert len(mg) == 3, f"expected 3 merged events with >1 constituent, got {len(mg)}"
    ids = mg["event_id"].tolist()
    print(f"\nmerged events with >1 constituent: {ids}")

    ax = att.set_index("event_id")
    cm = pd.read_csv(os.path.join(C.SUMMARY_OUT, "component_map.csv"))
    fam_stop = cm[cm.role.isin(("stop", "both"))].set_index("message")["family"]

    rows = []
    for _, e in mg.iterrows():
        eid = int(e["event_id"])
        a = ax.loc[eid]
        sw, sl = bool(a["same_warn_72h"]), float(a["same_lead_h_72h"])
        aw, al = bool(a["any_warn_72h"]), float(a["any_lead_h_72h"])
        cc = cons[cons.event_id == eid].sort_values("start")
        for _, c in cc.iterrows():
            rows.append(dict(
                table="constituent", event_id=eid, farm=e["farm"],
                turbine_id=int(e["turbine_id"]),
                event_start=e["start"], event_end=e["end"],
                constituent_start=c["start"], constituent_end=c["end"],
                constituent_code=int(c["code"]), constituent_message=c["message"],
                constituent_family=fam_stop.get(c["message"]),
                constituent_service_category=c["service_category"],
                constituent_duration_h=float(c["stop_dur_s"]) / 3600.0,
                constituent_E_mwh_separable=float(c["E_mwh"]),
                is_longest=bool(float(c["stop_dur_s"])
                                == cc["stop_dur_s"].max()),
                T0=bool(e["T0"]), T1=bool(e["T1"]), T2=bool(e["T2"]),
                T1_wide_grid=bool(e["T1_wide_grid"]),
                T2_wide_grid=bool(e["T2_wide_grid"]),
                displayed_family=e["family"],
                displayed_message=e["primary_message"],
                families_all="|".join(e["families_all"]),
                event_E_mwh=float(e["E_mwh"]),
                event_duration_h=float(e["duration_h"]),
                E_unmerged_sum_mwh=float(e["E_unmerged_sum_mwh"]),
                E_double_counted_mwh=float(e["E_double_counted_mwh"]),
                same_warned=sw, same_lead_h=sl, same_n_72h=int(a["same_n_72h"]),
                any_warned=aw, any_lead_h=al, any_n_72h=int(a["any_n_72h"]),
                headline_class=klass(sw, sl),
                note="constituent lost energies are computed on the OVERLAPPING "
                     "raw stop windows and are NOT additive; the event's E_mwh is "
                     "the merged-window figure charged once"))

    # -------------------------------- alternative rule: displayed family only ---
    sub = ev[ev.event_id.isin(ids)].copy()
    anchors = sub[["farm", "turbine_id"]].copy()
    anchors["anchor"] = sub["start"].values
    anchors["fam_set"] = [frozenset([f]) for f in sub["family"].values]
    wn = A.load_warnings()
    alt = A.attribute(anchors, wn, lookbacks_h=(LOOKBACK_H,))
    alt.index = sub["event_id"].values

    # sanity: the union rule re-run on the SAME machinery reproduces the frozen
    # columns for these three events, so any difference below is the rule, not drift.
    anchors_u = anchors.copy()
    anchors_u["fam_set"] = [frozenset(f) for f in sub["families_all"].values]
    chk = A.attribute(anchors_u, wn, lookbacks_h=(LOOKBACK_H,))
    chk.index = sub["event_id"].values
    for eid in ids:
        assert bool(chk.loc[eid, "same_warn_72h"]) == bool(ax.loc[eid, "same_warn_72h"])
        assert int(chk.loc[eid, "same_n_72h"]) == int(ax.loc[eid, "same_n_72h"])
        both = (float(chk.loc[eid, "same_lead_h_72h"]),
                float(ax.loc[eid, "same_lead_h_72h"]))
        assert (np.isnan(both[0]) and np.isnan(both[1])) or abs(both[0] - both[1]) < 1e-9
    print("  RE-RUN CHECK union rule reproduces the frozen same-component "
          "columns for all 3 events: OK")

    # rebuild the headline with only these three events' flags swapped
    eid_arr = s["event_id"].values
    warned_alt, lead_alt = warned.copy(), lead.copy()
    for eid in ids:
        j = int(np.flatnonzero(eid_arr == eid)[0])
        warned_alt[j] = bool(alt.loc[eid, "same_warn_72h"])
        lead_alt[j] = float(alt.loc[eid, "same_lead_h_72h"])
    act_alt = warned_alt & (lead_alt >= T_ACT_H)
    point_alt = float(E[act_alt].sum() / E.sum())
    n_warn_alt = int(warned_alt.sum())
    e_warn_alt = float(E[warned_alt].sum())

    print("\n=== alternative rule: only the displayed (longest-constituent) "
          "family may match ===")
    for _, e in sub.iterrows():
        eid = int(e["event_id"])
        a = ax.loc[eid]
        sw0, sl0 = bool(a["same_warn_72h"]), float(a["same_lead_h_72h"])
        sw1 = bool(alt.loc[eid, "same_warn_72h"])
        sl1 = float(alt.loc[eid, "same_lead_h_72h"])
        print(f"  event {eid} {e['farm']} WT{int(e['turbine_id']):02d} "
              f"{e['E_mwh']:>8,.1f} MWh  displayed {e['family']:<11} "
              f"families_all {e['families_all']}")
        print(f"      frozen (union)   warned {str(sw0):<5} lead "
              f"{sl0:>8.3f} h  n {int(a['same_n_72h']):>4}  -> {klass(sw0, sl0)}")
        print(f"      alternative      warned {str(sw1):<5} lead "
              f"{sl1:>8.3f} h  n {int(alt.loc[eid, 'same_n_72h']):>4}  -> "
              f"{klass(sw1, sl1)}")
        rows.append(dict(
            table="alternative_rule", event_id=eid, farm=e["farm"],
            turbine_id=int(e["turbine_id"]), event_start=e["start"],
            event_end=e["end"], displayed_family=e["family"],
            displayed_message=e["primary_message"],
            families_all="|".join(e["families_all"]),
            event_E_mwh=float(e["E_mwh"]),
            event_duration_h=float(e["duration_h"]),
            same_warned=sw0, same_lead_h=sl0, same_n_72h=int(a["same_n_72h"]),
            headline_class=klass(sw0, sl0),
            alt_same_warned=sw1, alt_same_lead_h=sl1,
            alt_same_n_72h=int(alt.loc[eid, "same_n_72h"]),
            alt_headline_class=klass(sw1, sl1),
            note="frozen union rule vs displayed-family-only rule, same matcher"))

    print(f"\n  headline, frozen union rule           {100*point:.4f} %  "
          f"({int(warned.sum())} warned / {E[warned].sum():,.1f} MWh)")
    print(f"  headline, displayed-family-only rule  {100*point_alt:.4f} %  "
          f"({n_warn_alt} warned / {e_warn_alt:,.1f} MWh)")
    print(f"  shift {100*(point_alt - point):+.4f} pp")

    rows.append(dict(
        table="headline", event_id=np.nan, scope="all_T2_wide_grid",
        n_events=len(E), event_E_mwh=float(E.sum()),
        headline_pct_frozen=100 * point, headline_pct_alt=100 * point_alt,
        shift_pp=100 * (point_alt - point),
        n_same_warned_frozen=int(warned.sum()), n_same_warned_alt=n_warn_alt,
        E_same_warned_frozen=float(E[warned].sum()), E_same_warned_alt=e_warn_alt,
        note="alternative rule applied to the 3 multi-constituent events only; "
             "every other event's frozen flags unchanged; denominator unchanged"))

    # ---------------------------------------------- when were the rules fixed ---
    prov = []
    for f in ("build_events.py", "common.py", "attribute.py"):
        p = os.path.join(HERE, f)
        prov.append((f"mtime {f}", pd.Timestamp(os.path.getmtime(p), unit="s",
                                                tz="UTC").tz_convert(
            "America/Los_Angeles").strftime("%Y-%m-%d %H:%M:%S")))
    try:
        g = subprocess.run(
            ["git", "log", "--follow", "--format=%ad %H", "--date=iso",
             "--", "analysis/build_events.py"],
            cwd=RELEASE_REPO, capture_output=True, text=True, timeout=60)
        for ln in [l for l in g.stdout.strip().splitlines() if l]:
            prov.append(("git build_events.py", ln))
    except Exception as exc:                                   # pragma: no cover
        prov.append(("git build_events.py", f"unavailable: {exc}"))
    for p in ("analysis/RESULTS.md", "analysis/bootstrap.csv",
              "analysis/attribution_summary.csv"):
        fp = os.path.join(PROJECT, p)
        if os.path.exists(fp):
            prov.append((f"mtime {p}", pd.Timestamp(
                os.path.getmtime(fp), unit="s", tz="UTC").tz_convert(
                "America/Los_Angeles").strftime("%Y-%m-%d %H:%M:%S")))
    print("\n=== provenance: when the merge / tier rules were fixed ===")
    for k, v in prov:
        print(f"  {k:<32} {v}")
        rows.append(dict(table="provenance", scope=k, note=v))

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nwrote {OUT_CSV}: {len(out):,} rows")
    return out


if __name__ == "__main__":
    main()
