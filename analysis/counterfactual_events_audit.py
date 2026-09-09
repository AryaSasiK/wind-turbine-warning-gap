#!/usr/bin/env python3
"""counterfactual_events_audit.csv - the 698 long-lead events, one row each.

The modelled recoverable ceiling (666.4 MWh at the median planned-intervention
duration) is quoted as a total. A referee asked to see it event by event: how
much of it is concentrated, how many events are clipped at zero because the
planned intervention would cost more downtime than the fault did, and how many
of the 698 carry no measured energy at all.

Population: the manuscript's PRIMARY one - `T2_wide_grid`, same-component rule,
72 h lookback, T_lead = 6 h, which is exactly what counterfactual.py froze into
counterfactual_events.parquet (698 rows of the 4,213; see ARTEFACT_KEY.md).

Reads (read-only):
  $WTWG_DERIVED/counterfactual_events.parquet   (frozen stage-2, p50 arm)
  $WTWG_DERIVED/events.parquet                  (frozen stage-1, for E_mwh)
  analysis/planned_duration.csv                 (frozen planned-intervention
                                                 durations, median and p75)

The parquet froze only the median (p50) arm, so the p75 arm is reconstructed
here from counterfactual.py's own model, reproduced rather than imported:

    planned_charge = mean_potential_kw(+) * D_planned / 1000     [MWh]
    recoverable    = max(lost_energy - planned_charge, 0)
    clipped        = (lost_energy - planned_charge) < 0

Writes counterfactual_events_audit.csv beside this file. Imports no analysis
script and runs none, so it cannot disturb any frozen artefact.
"""
import os

import numpy as np
import pandas as pd

A = os.path.dirname(os.path.abspath(__file__)) + "/"
D = os.environ.get("WTWG_DERIVED",
                   os.path.join("wind-turbine-warning-gap-data", "derived")) + "/"
OUT = A

# ---------------------------------------------------------------- load frozen
cf = pd.read_parquet(D + "counterfactual_events.parquet")
ev = pd.read_parquet(D + "events.parquet")
pd_dur = pd.read_csv(A + "planned_duration.csv", index_col=0).iloc[:, 0]

D_P50 = float(pd_dur["median_h"])
D_P75 = float(pd_dur["p75_h"])
assert abs(D_P50 - 0.7918055555555555) < 1e-12, D_P50
assert abs(D_P75 - 2.0297916666666667) < 1e-12, D_P75
assert len(cf) == 698, len(cf)

# lost energy is already on the parquet; take it from events.parquet anyway and
# require agreement, so the join is verified rather than assumed.
e_from_events = ev.set_index("event_id")["E_mwh"]
joined = cf["event_id"].map(e_from_events).values
assert np.allclose(joined, cf["E_mwh"].values, rtol=0, atol=1e-12)

# ------------------------------------------------------------- the two arms
pot = cf["mean_potential_kw"].fillna(0.0).clip(lower=0.0).values
E = cf["E_mwh"].values

plan50 = pot * D_P50 / 1000.0
plan75 = pot * D_P75 / 1000.0
raw50, raw75 = E - plan50, E - plan75
rec50, rec75 = np.clip(raw50, 0.0, None), np.clip(raw75, 0.0, None)

# the p50 arm must reproduce the frozen parquet exactly
assert np.allclose(plan50, cf["E_planned_mwh"].values, rtol=0, atol=1e-9)
assert np.allclose(rec50, cf["recoverable_mwh"].values, rtol=0, atol=1e-9)

t = pd.DataFrame(dict(
    event_id=cf["event_id"].astype(int).values,
    farm=cf["farm"].values,
    turbine=[("K" if f == "kelmarsh" else "P") + f"{int(i):02d}"
             for f, i in zip(cf["farm"], cf["turbine_id"])],
    start=[pd.Timestamp(s).strftime("%Y-%m-%d %H:%M:%S") for s in cf["start"]],
    duration_h=np.round(cf["duration_h"].values.astype(float), 6),
    lost_energy_mwh=np.round(E, 6),
    planned_charge_mwh_p50=np.round(plan50, 6),
    planned_charge_mwh_p75=np.round(plan75, 6),
    recoverable_mwh_p50=np.round(rec50, 6),
    recoverable_mwh_p75=np.round(rec75, 6),
    clipped_p50=raw50 < 0,
    clipped_p75=raw75 < 0,
    zero_energy=E == 0.0,
)).sort_values("event_id").reset_index(drop=True)
t.to_csv(OUT + "counterfactual_events_audit.csv", index=False)

# ------------------------------------------------------------------- CHECKS
print("=== CHECK 1: population and totals ===")
print(f"  rows                              {len(t):>10}      (expected 698)")
print(f"  sum recoverable_mwh_p50    {t.recoverable_mwh_p50.sum():>13.3f} MWh "
      f"(expected 666.431)")
print(f"  sum recoverable_mwh_p75    {t.recoverable_mwh_p75.sum():>13.3f} MWh "
      f"(counterfactual.csv: 639.229)")
print(f"  sum lost_energy_mwh        {t.lost_energy_mwh.sum():>13.3f} MWh "
      f"(expected 706.632)")

print("\n=== CHECK 2: clipping and zero-energy events ===")
print(f"  clipped at p50                    {int(t.clipped_p50.sum()):>10}      "
      f"(expected 124)")
print(f"  clipped at p75                    {int(t.clipped_p75.sum()):>10}      "
      f"(expected 132)")
print(f"  zero-energy events                {int(t.zero_energy.sum()):>10}      "
      f"(expected 532)")
nz_clip = int(((t.lost_energy_mwh > 0) & t.clipped_p50).sum())
print(f"  energy > 0 AND clipped at p50     {nz_clip:>10}      (expected 121)")
print(f"  energy > 0                        {int((t.lost_energy_mwh > 0).sum()):>10}"
      f"      (698 - 532 = 166)")

print("\n=== CHECK 3: concentration of the 666.4 MWh ceiling ===")
pos = t[t.recoverable_mwh_p50 > 0].sort_values("recoverable_mwh_p50",
                                               ascending=False)
tot = t.recoverable_mwh_p50.sum()
print(f"  events with recoverable > 0       {len(pos):>10}      (expected 45)")
print(f"  they supply                {pos.recoverable_mwh_p50.sum():>13.3f} MWh "
      f"= {100*pos.recoverable_mwh_p50.sum()/tot:.1f}% of the total")
print(f"  largest single event       {pos.recoverable_mwh_p50.iloc[0]:>13.3f} MWh "
      f"= {100*pos.recoverable_mwh_p50.iloc[0]/tot:.1f}% "
      f"(expected 209.562 = 31.4%)")
print(f"  top five                   {pos.recoverable_mwh_p50.head(5).sum():>13.3f} MWh "
      f"= {100*pos.recoverable_mwh_p50.head(5).sum()/tot:.1f}% (expected 70.9%)")
print(pos.head(5)[["event_id", "farm", "turbine", "start", "duration_h",
                   "lost_energy_mwh", "recoverable_mwh_p50"]].to_string(index=False))

print("\nwrote " + OUT + "counterfactual_events_audit.csv")
