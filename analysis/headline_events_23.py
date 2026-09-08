#!/usr/bin/env python3
"""Build the 23-event disclosure table from FROZEN artefacts only.

Reads (read-only):
  $WTWG_DERIVED/attribution.parquet   (frozen stage-2)
  analysis/component_map.csv                                  (frozen map)
  analysis/map_adjudication.csv                               (frozen, v1.5 post hoc)
  analysis/map_sensitivity.csv                                (frozen, 1,152 variants)

Writes headline_events_23.csv beside this file. Runs no analysis script and
imports none of them, so it cannot disturb any frozen artefact.
"""
import os
import numpy as np
import pandas as pd

A = os.path.dirname(os.path.abspath(__file__)) + "/"
D = os.environ.get("WTWG_DERIVED",
                   os.path.join("wind-turbine-warning-gap-data", "derived")) + "/"
OUT = A

T_ACT_H = 6.0
DUR_H = 6.0
LOOKBACK = "72h"

# ---------------------------------------------------------------- load frozen
att = pd.read_parquet(D + "attribution.parquet")
cm = pd.read_csv(A + "component_map.csv")
adj = pd.read_csv(A + "map_adjudication.csv")

code_of = {(r.role, r.message): r.code for _, r in cm.iterrows()}
fam_of = {(r.role, r.message): r.family for _, r in cm.iterrows()}

# ------------------------------------------------------- reproduce the 23 set
tier = att["T2_wide_grid"].astype(bool).values
warned = att["same_warn_72h"].astype(bool).values
lead = att["same_lead_h_72h"].astype(float).values
dur = att["duration_h"].astype(float).values
E = att["E_mwh"].astype(float).values

mask = tier & warned & (lead >= T_ACT_H) & (dur >= DUR_H)
assert mask.sum() == 23, mask.sum()
assert abs(E[mask].sum() - 654.6) < 0.05, E[mask].sum()
# population gates
assert tier.sum() == 4213
assert abs(E[tier].sum() - 9386.5) < 0.05
assert (tier & warned).sum() == 979
assert abs(E[tier & warned].sum() - 1522.8) < 0.05

sub = att.loc[mask].copy().sort_values("E_mwh", ascending=False).reset_index(drop=True)

# ----------------------------------------------- slot / disagreement flagging
h = adj[adj.in_headline_23 == True].copy()
h["ambiguous_slot"] = h["ambiguous_slot"].fillna("")
assert set(h.event_id) == set(sub.event_id), "adjudication headline-23 != parquet 23"

# the four post hoc disagreements (whole file, not just the 23)
four = (adj[adj.adjudication == "DISAGREE"]
        .groupby(["role", "message"])
        .agg(frozen=("frozen_family", "first"), mine=("my_family", "first"),
             slot=("ambiguous_slot", "first"), conf=("my_confidence", "first"))
        .reset_index())
assert len(four) == 4, four
DISPUTED = {(r.role, r.message): (r.frozen, r.mine) for _, r in four.iterrows()}

# the nine swept slots, as recorded on the adjudication rows
SLOT_OF = {(r.role, r.message): r.ambiguous_slot
           for _, r in adj.iterrows()
           if isinstance(r.ambiguous_slot, str) and r.ambiguous_slot}

ms = pd.read_csv(A + "map_sensitivity.csv")
assert len(ms) == 1152, len(ms)

rows = []
for _, ev in sub.iterrows():
    eid = int(ev.event_id)
    g = h[h.event_id == eid]
    stops = g[g.role == "stop"]
    warns = g[g.role == "warning"]

    first_msg = ev["same_first_msg_72h"]
    first_fam = ev["same_first_fam_72h"]

    # co-earliest distinct matching warning messages (ties on the same instant)
    tied = sorted(set(warns.loc[warns.is_earliest_qualifying_warning == True,
                                "message"]) - {first_msg})

    # every flagged map entry on the event (paper's event-level definition)
    swept, disputed = [], []
    for _, r in g.iterrows():
        key = (r.role, r.message)
        if key in SLOT_OF:
            swept.append(f"{r.role}:{r.message} [{SLOT_OF[key]}]")
        if key in DISPUTED:
            fz, mine = DISPUTED[key]
            disputed.append(f"{r.role}:{r.message} [{fz}->{mine}]")

    if swept and disputed:
        flag = "swept+disputed"
    elif swept:
        flag = "swept"
    elif disputed:
        flag = "disputed"
    else:
        flag = "neither"

    # is the flagged entry load-bearing for THIS event's match?
    # load-bearing = the earliest matching warning message, or a constituent stop
    # message whose frozen family equals that warning's family (the stop side of
    # the match).
    lb_keys = {("warning", first_msg)}
    for m in tied:
        lb_keys.add(("warning", m))
    for _, r in stops.iterrows():
        if r.frozen_family == first_fam:
            lb_keys.add(("stop", r.message))
    flagged_keys = {(r.role, r.message) for _, r in g.iterrows()
                    if (r.role, r.message) in SLOT_OF or (r.role, r.message) in DISPUTED}
    match_critical = bool(flagged_keys & lb_keys)

    rows.append(dict(
        event_id=eid,
        farm=ev.farm,
        turbine_id=int(ev.turbine_id),
        turbine=("K" if ev.farm == "kelmarsh" else "P") + f"{int(ev.turbine_id):02d}",
        start_date=pd.Timestamp(ev.start).strftime("%Y-%m-%d"),
        start_datetime=pd.Timestamp(ev.start).strftime("%Y-%m-%d %H:%M:%S"),
        duration_h=round(float(ev.duration_h), 3),
        lost_energy_mwh=round(float(ev.E_mwh), 4),
        stop_message=ev.primary_message,
        stop_code=code_of.get(("stop", ev.primary_message)),
        stop_family_frozen_map=ev.family,
        all_constituent_families="|".join(sorted(ev.families_all)),
        n_stop_constituents=int(ev.n_stops),
        warning_message=first_msg,
        warning_code=code_of.get(("warning", first_msg)),
        warning_family_frozen_map=first_fam,
        warning_message_coearliest_ties="|".join(tied),
        lead_h=round(float(ev.same_lead_h_72h), 3),
        n_matching_warning_rows_72h=int(ev.same_n_72h),
        n_any_warning_rows_72h=int(ev.any_n_72h),
        map_flag=flag,
        swept_slot_entries="; ".join(swept),
        disputed_entries="; ".join(disputed),
        flagged_entry_is_match_critical=match_critical,
    ))

t = pd.DataFrame(rows)
t.insert(0, "rank_by_energy", range(1, len(t) + 1))
t.to_csv(OUT + "event23_table.csv", index=False)

# ------------------------------------------------------------------- CHECKS
print("=== CHECK 1: energy sum ===")
print(f"  n = {len(t)}   sum = {t.lost_energy_mwh.sum():.4f} MWh "
      f"(paper: 654.6)   diff = {t.lost_energy_mwh.sum()-654.6:+.4f}")
print(f"  share of the 1,522.8 MWh same-component-warned total = "
      f"{100*t.lost_energy_mwh.sum()/float(E[tier & warned].sum()):.2f}%")

print("\n=== CHECK 2: swept / disputed ===")
f = t[t.map_flag != "neither"]
print(f"  events on a swept or disputed entry: {len(f)} of 23")
print(f"  their energy: {f.lost_energy_mwh.sum():.4f} MWh = "
      f"{100*f.lost_energy_mwh.sum()/t.lost_energy_mwh.sum():.2f}% of 654.6 "
      f"(paper: seven events, 59%)")
print(f"  all match-critical? {bool(f.flagged_entry_is_match_critical.all())}")
print(t.map_flag.value_counts().to_string())
print(f[["event_id", "turbine", "lost_energy_mwh", "map_flag",
         "flagged_entry_is_match_critical", "swept_slot_entries",
         "disputed_entries"]].to_string(index=False))

print("\n=== CHECK 3: families ===")
fam = (t.groupby("stop_family_frozen_map")
       .agg(n_events=("event_id", "size"), mwh=("lost_energy_mwh", "sum"))
       .sort_values("mwh", ascending=False))
fam["pct_of_654.6"] = 100 * fam.mwh / t.lost_energy_mwh.sum()
print(fam.round(3).to_string())
print(f"  total {int(fam.n_events.sum())} events, {fam.mwh.sum():.3f} MWh")

print("\n=== CHECK 4: largest event ===")
big = t.iloc[0]
for k in ("farm", "turbine", "start_date", "duration_h", "lost_energy_mwh",
          "stop_message", "stop_family_frozen_map", "warning_message", "lead_h"):
    print(f"  {k:<24} {big[k]}")

print("\nwrote " + OUT + "event23_table.csv")
