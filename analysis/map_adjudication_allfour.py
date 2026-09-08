#!/usr/bin/env python3
"""Put the map-adjudication headline scenarios into an artefact (STUDY_DESIGN v1.7b).

`map_adjudication.py` prints five headline values - the frozen map, each of the four
independent disagreements flipped alone, the two NEW disagreements jointly, and all
four jointly - but writes none of them. `map_adjudication_summary.csv` holds one row
per adjudicated event and nothing else, so the two numbers the manuscript quotes in
section V-E (5.07 % for the two new disagreements, 5.44 % for all four) existed only
as prose in `RESULTS_v15.md`. A referee cannot check a number that is not in a CSV.

This script recomputes them with the same machinery (`map_sensitivity.MapEngine` and
`variant_metrics`, the same objects `map_adjudication.py` uses, so nothing is
re-implemented) and appends them to `map_adjudication_summary.csv` as explicit rows
under a new leading `table` column:

    table == "event"              the existing per-event adjudication rows
    table == "headline_scenario"  the seven scenario rows added here
                                  (frozen + four singles + two joints)

Scenario rows carry `scenario`, `scenario_kind`, `flips`, the decomposition
percentages, warned/actionable counts and the delta from the frozen headline.

Idempotent: any existing `headline_scenario` rows are dropped and rewritten, and the
per-event rows are passed through untouched. `map_adjudication.py` calls this at the
end of its own run, so re-running the adjudication cannot leave the summary without
its scenario rows.

    python3 map_adjudication_allfour.py
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import map_adjudication as MA
import map_sensitivity as MS

OUT_SUMMARY = MA.OUT_SUMMARY

# `never_match` is not a family in the frozen map. Realise it as `manual`, which is
# in MS.NEVER_MATCH, so the message can never satisfy the same-component rule -
# exactly how the published sweep realises `WEC shut down` -> manual.
NEVER_AS = "manual"

# Frozen values this script must reproduce before it writes anything.
GATE = [("T2 events", 4213, 0), ("T2 MWh", 9386.5, 0.05),
        ("frozen headline %", 7.528, 0.001),
        ("two new disagreements jointly %", 5.071, 0.001),
        ("all four jointly %", 5.441, 0.001)]


def disagreements(cm):
    """The independent disagreements behind the adjudication, in a stable order.

    A disagreement is a (role, message) whose `map_adjudication.JUDGMENT` family
    differs from the frozen `component_map.csv` family. `slot` is non-empty when the
    entry is one of `map_sensitivity.SLOTS`' nine documented-ambiguous slots, i.e.
    when the 1,152-variant sweep already covered it; the other entries are the NEW
    ones the adjudication turned up.
    """
    frozen = {}
    for _, r in cm.iterrows():
        for role in (("stop", "warning") if r.role == "both" else (r.role,)):
            frozen[(role, r.message)] = r.family
    slots = MA.slot_index()
    out = []
    for (role, msg), (my_fam, conf, _reason) in MA.JUDGMENT.items():
        fam = frozen.get((role, msg))
        if fam is None or my_fam == fam:
            continue
        out.append({"role": role, "message": msg, "frozen_family": fam,
                    "my_family": my_fam, "flip_family": (NEVER_AS
                                                         if my_fam == "never_match"
                                                         else my_fam),
                    "confidence": conf,
                    "slot": slots.get((role, msg), ("", "", ""))[0]})
    return sorted(out, key=lambda d: (d["slot"] == "", d["role"], d["message"]))


def scenario_rows(eng, tier, E, big_pos, fams, cm):
    """One row per headline scenario: frozen, each single flip, and the two joints."""
    dis = disagreements(cm)
    new = [d for d in dis if not d["slot"]]

    def flip_of(d):
        return (d["role"], d["message"], d["flip_family"])

    def label(d):
        return f"{d['role']}:{d['message']} -> {d['flip_family']}"

    scenarios = [("frozen map (published headline)", "frozen", [], "")]
    for d in dis:
        kind = "single_sweep_covered" if d["slot"] else "single_new"
        scenarios.append((label(d), kind, [flip_of(d)],
                          d["slot"] or "not one of the nine sweep slots"))
    scenarios.append(("two NEW disagreements jointly", "joint_new",
                      [flip_of(d) for d in new],
                      " + ".join(label(d) for d in new)))
    scenarios.append(("all four disagreements jointly", "joint_all",
                      [flip_of(d) for d in dis],
                      " + ".join(label(d) for d in dis)))

    base = MS.variant_metrics(eng, [], tier, E, big_pos, fams)
    rows = []
    for name, kind, flips, note in scenarios:
        m = MS.variant_metrics(eng, flips, tier, E, big_pos, fams)
        rows.append({
            "table": "headline_scenario",
            "scenario": name,
            "scenario_kind": kind,
            "n_flips": len(flips),
            "flips": "; ".join(f"{r}:{msg} -> {fam}" for r, msg, fam in flips),
            "n_events": m["n_events"],
            "E_mwh": round(m["E_mwh"], 4),
            "unwarned_pct_E": round(m["unwarned_pct_E"], 4),
            "short_lead_pct_E": round(m["short_lead_pct_E"], 4),
            "actionable_unacted_pct_E": round(m["actionable_unacted_pct_E"], 4),
            "delta_pp_vs_frozen": round(m["actionable_unacted_pct_E"]
                                        - base["actionable_unacted_pct_E"], 4),
            "warned_n_events": m["warned_n_events"],
            "warned_E_mwh": round(m["warned_E_mwh"], 4),
            "actionable_n_events": m["actionable_n_events"],
            "actionable_E_mwh": round(m["actionable_E_mwh"], 4),
            "converter_same_warned_n": m["converter_same_warned_n"],
            "big_event_bucket": m["big_event_bucket"],
            "note": note,
        })
    return pd.DataFrame(rows)


def append_scenarios(scen, path=OUT_SUMMARY):
    """Rewrite the summary CSV as per-event rows + the scenario rows.

    Done at the text level rather than with `pd.concat`, so that every existing
    per-event row survives byte for byte: a round trip through pandas would upcast
    the integer columns (the scenario rows leave them empty) and re-print floats
    from their parsed doubles, e.g. `250.80027777777778` -> `250.80027777777775`.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header, body = rows[0], rows[1:]
    if header and header[0] == "table":
        body = [r for r in body if r[0] != "headline_scenario"]
    else:
        header = ["table"] + header
        body = [["event"] + r for r in body]

    extra = [c for c in scen.columns if c not in header]
    out_header = header + extra
    width = len(out_header)

    def cell(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return ""
        if isinstance(v, (int, np.integer)):
            return str(int(v))
        if isinstance(v, (float, np.floating)):
            return repr(float(v))
        return str(v)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(out_header)
        for r in body:
            w.writerow(r + [""] * (width - len(r)))
        for _, r in scen.iterrows():
            w.writerow([cell(r[c]) if c in scen.columns else "" for c in out_header])
    print(f"wrote {path}: {len(body)} event rows + {len(scen)} scenario rows")


def main():
    cm, stop_fam, warn_fam = MS.load_map()
    ev, wn, att = MS.load_frames()
    eng = MS.MapEngine(ev, wn, stop_fam, warn_fam, MS.build_candidates(ev, wn))

    tier = att[MA.TIER_FLAG].values.astype(bool)
    E = att["E_mwh"].values.astype(float)
    big_pos = int(np.flatnonzero(att["event_id"].values == MS.BIG_EVENT_ID)[0])

    scen = scenario_rows(eng, tier, E, big_pos, eng.fams, cm)
    idx = scen.set_index("scenario_kind")["actionable_unacted_pct_E"]
    got = {"T2 events": float(scen.n_events.iloc[0]),
           "T2 MWh": float(scen.E_mwh.iloc[0]),
           "frozen headline %": float(idx["frozen"]),
           "two new disagreements jointly %": float(idx["joint_new"]),
           "all four jointly %": float(idx["joint_all"])}

    print("=== VALIDATION GATE ===")
    ok_all = True
    for name, want, tol in GATE:
        ok = abs(got[name] - want) <= tol
        ok_all &= ok
        print(f"  {name:<32} got {got[name]:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
    assert ok_all, "VALIDATION GATE FAILED - frozen adjudication values not reproduced"

    print()
    print(scen[["scenario", "scenario_kind", "actionable_unacted_pct_E",
                "delta_pp_vs_frozen", "warned_n_events",
                "actionable_n_events"]].to_string(index=False))
    print()
    append_scenarios(scen)
    return scen


if __name__ == "__main__":
    main()
