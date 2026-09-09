#!/usr/bin/env python3
"""zero_energy_audit.csv - why each zero-energy T2 event carries E = 0.

A referee asked for the mechanism behind the 1,745 primary-population events
whose measured lost energy is exactly zero. There are two, and only two:

  no_bin_start                    the merged window [start, end] contains no
                                  10-minute SCADA bin start at all, so there is
                                  nothing to integrate (every such window is
                                  shorter than one bin).
  potential_never_exceeds_measured  the window does contain bin starts, but the
                                  positive part of (potential power - measured
                                  power) is zero in every one of them.

Population: the manuscript's PRIMARY one - the `T2_wide_grid` flag on
events.parquet, 4,213 events / 9,386.5 MWh (see ARTEFACT_KEY.md; plain `T2` on
that parquet is the NARROW grid variant and is the wrong population).

Reads (read-only):
  $WTWG_DERIVED/events.parquet        (frozen stage-1)
  $WTWG_DERIVED/scada_min/*.parquet   (frozen 10-minute SCADA cache)

The energy definition is REPRODUCED here from build_events.py rather than
imported, so this script runs no pipeline code and cannot disturb any frozen
artefact:

    window  = scada.loc[start:end]          sliced on the bin START timestamp
    E_mwh   = ((potential - measured)+).sum() * (10/60) / 1000

with measured power NaN-filled to 0 and clipped at 0, exactly as the frozen
builder does. Writes zero_energy_audit.csv beside this file.
"""
import os

import numpy as np
import pandas as pd

A = os.path.dirname(os.path.abspath(__file__)) + "/"
D = os.environ.get("WTWG_DERIVED",
                   os.path.join("wind-turbine-warning-gap-data", "derived")) + "/"
OUT = A

TIER_FLAG = "T2_wide_grid"

# --- reproduced verbatim from common.py / build_events.py (not imported) -----
TS = "Date and time"
POWER = "Power (kW)"
POT = "Cascading potential power (kW)"           # the coalesced potential series
BIN_HOURS = 10.0 / 60.0                          # 10-minute SCADA grid


def load_turbine(farm, tid):
    """Timestamp-indexed minimal SCADA for one turbine, from the frozen cache."""
    sc = pd.read_parquet(os.path.join(D, "scada_min", f"{farm}_WT{tid:02d}.parquet"))
    return sc.set_index(TS).sort_index()


def window_energy(sc, t0, t1):
    """(n_bin_starts, E_mwh) for one window, build_events.py's definition."""
    w = sc.loc[t0:t1]
    n = len(w)
    if n == 0:
        return 0, 0.0
    p = w[POT]
    a = w[POWER].fillna(0.0).clip(lower=0.0)
    return n, float((p - a).clip(lower=0.0).sum() * BIN_HOURS / 1000.0)


# ------------------------------------------------------------------ population
ev = pd.read_parquet(D + "events.parquet")
tier = ev[TIER_FLAG].astype(bool)
assert int(tier.sum()) == 4213, int(tier.sum())
assert abs(float(ev.loc[tier, "E_mwh"].sum()) - 9386.5) < 0.05, \
    float(ev.loc[tier, "E_mwh"].sum())

z = ev[tier & (ev["E_mwh"] == 0.0)].copy()

# ------------------------------------------------------------------- the audit
rows = []
for (farm, tid), grp in z.groupby(["farm", "turbine_id"], sort=True):
    sc = load_turbine(farm, int(tid))
    for _, e in grp.iterrows():
        n, recomputed = window_energy(sc, e["start"], e["end"])
        # the frozen value is exactly zero; the reproduction must agree
        assert abs(recomputed) < 1e-12, (int(e.event_id), recomputed)
        rows.append(dict(
            event_id=int(e.event_id),
            farm=farm,
            turbine=("K" if farm == "kelmarsh" else "P") + f"{int(tid):02d}",
            start=pd.Timestamp(e["start"]).strftime("%Y-%m-%d %H:%M:%S"),
            end=pd.Timestamp(e["end"]).strftime("%Y-%m-%d %H:%M:%S"),
            duration_h=round(float(e["duration_h"]), 6),
            n_bin_starts_in_window=int(n),
            lost_energy_mwh=0.0,
            reason=("no_bin_start" if n == 0
                    else "potential_never_exceeds_measured"),
        ))

t = pd.DataFrame(rows).sort_values("event_id").reset_index(drop=True)
t.to_csv(OUT + "zero_energy_audit.csv", index=False)

# ------------------------------------------------------------------- CHECKS
n_none = int((t.reason == "no_bin_start").sum())
n_flat = int((t.reason == "potential_never_exceeds_measured").sum())
print("=== CHECK 1: row counts ===")
print(f"  zero-energy T2 (wide-grid) events   {len(t):>6}   (expected 1,745)")
print(f"  no_bin_start                        {n_none:>6}   (expected 1,369)")
print(f"  potential_never_exceeds_measured    {n_flat:>6}   (expected   376)")
print(f"  parts sum to total?                 {n_none + n_flat == len(t)}")

print("\n=== CHECK 2: every no_bin_start window is shorter than one bin ===")
d = t.loc[t.reason == "no_bin_start", "duration_h"]
print(f"  max duration_h  {d.max():.4f} h  (expected 0.1633; one bin = "
      f"{BIN_HOURS:.4f} h)")
print(f"  all < 10 minutes? {bool((d < BIN_HOURS).all())}")

print("\n=== CHECK 3: the other arm does have bins ===")
b = t.loc[t.reason == "potential_never_exceeds_measured", "n_bin_starts_in_window"]
print(f"  n_bin_starts min {int(b.min())}  median {b.median():.0f}  "
      f"max {int(b.max())}")
print(f"  duration_h  min {t.loc[t.reason != 'no_bin_start', 'duration_h'].min():.4f}"
      f"  max {t.loc[t.reason != 'no_bin_start', 'duration_h'].max():.4f} h")

print("\n=== CHECK 4: lost energy is exactly zero on every row ===")
print(f"  max |lost_energy_mwh| = {t.lost_energy_mwh.abs().max():.1f}")

print("\nwrote " + OUT + "zero_energy_audit.csv")
