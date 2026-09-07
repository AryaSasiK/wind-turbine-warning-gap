#!/usr/bin/env python3
"""STUDY_DESIGN v1.4(c) - small-cluster inference robustness for the headline.

The headline is the energy-weighted actionable-unacted share of T2 wide-grid lost
energy under the same-component rule, 72 h lookback, T_act = 6 h. Its frozen 95 % CI
comes from `bootstrap.py`'s two-level cluster bootstrap, whose OUTER level resamples
all 20 turbines with replacement without regard to farm. With 6 Kelmarsh and 14
Penmanshiel turbines and a large per-farm difference in the headline (RESULTS §8:
2.36 % vs 9.30 %), a replicate can draw very few - or zero - Kelmarsh turbines. Two
robustness reads are added here:

  (i)  FARM-STRATIFIED two-level bootstrap. The outer level resamples turbines WITHIN
       each farm (6 draws from Kelmarsh, 14 from Penmanshiel), so every replicate has
       the observed farm composition; the inner level resamples that turbine's events
       with replacement keeping its event count fixed - identical to bootstrap.py's
       inner level. 10,000 reps, seed 20260904, percentile 95 % CI.
  (ii) LEAVE-ONE-TURBINE-OUT. Recompute the headline dropping each of the 20 turbines
       in turn (both numerator and denominator move); report min / max / range and the
       most influential turbine. This is the cluster-level analogue of RESULTS §7's
       leave-one-EVENT-out over the top-10 energy events.
  (iii) The UNSTRATIFIED CI is QUOTED from `bootstrap.csv`, not recomputed, so the
       frozen artefact stays the single source of that number.

Nothing frozen is recomputed: the warned flags, leads, tier flags and energies are
read from `attribution.parquet` exactly as decompose.py and bootstrap.py read them.

Writes:
    analysis/cluster_robustness.csv

    python3 cluster_robustness.py [--reps 10000] [--seed 20260904]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

DERIVED = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
OUT_CSV = os.path.join(HERE, "cluster_robustness.csv")
BOOT_CSV = os.path.join(HERE, "bootstrap.csv")

TIER_FLAG = "T2_wide_grid"
RULE, LOOKBACK_H, T_ACT_H = "same", 72, 6
DEFAULT_REPS, DEFAULT_SEED = 10_000, 20260904


def headline(E, act, ix):
    """Energy-weighted actionable-unacted share over the events indexed by `ix`."""
    e = E[ix]
    tot = e.sum()
    return float(e[act[ix]].sum() / tot) if tot > 0 else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args()

    att = pd.read_parquet(os.path.join(DERIVED, "attribution.parquet"))
    s = att[att[TIER_FLAG].values].reset_index(drop=True)
    E = s["E_mwh"].values.astype(float)
    warned = s[f"{RULE}_warn_{LOOKBACK_H}h"].values.astype(bool)
    lead = s[f"{RULE}_lead_h_{LOOKBACK_H}h"].values.astype(float)
    act = warned & (lead >= T_ACT_H)

    # ------------------------------------------------------- validation gate ---
    point = headline(E, act, np.arange(len(E)))
    unw = float(E[~warned].sum() / E.sum())
    shl = float(E[warned & ~act].sum() / E.sum())
    print("=== VALIDATION GATE ===")
    checks = [("T2 events", len(E), 4213, 0), ("T2 MWh", E.sum(), 9386.5, 0.05),
              ("unwarned %", 100 * unw, 83.78, 0.005),
              ("short-lead %", 100 * shl, 8.69, 0.005),
              ("actionable %", 100 * point, 7.53, 0.005),
              ("warned n", int(warned.sum()), 979, 0),
              ("warned MWh", E[warned].sum(), 1522.8, 0.05)]
    for name, got, want, tol in checks:
        ok = abs(got - want) <= tol
        print(f"  {name:<16} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
        assert ok, f"VALIDATION GATE FAILED: {name}"

    # ------------------------------------------------------ cluster structure ---
    key = list(zip(s["farm"].values, s["turbine_id"].values))
    turbines = sorted(set(key))
    groups = {t: [] for t in turbines}
    for i, t in enumerate(key):
        groups[t].append(i)
    groups = {t: np.asarray(v, dtype=np.int64) for t, v in groups.items()}
    farms = sorted({t[0] for t in turbines})
    by_farm = {f: [t for t in turbines if t[0] == f] for f in farms}
    print("\nclusters: " + ", ".join(f"{f} {len(by_farm[f])}" for f in farms)
          + f"  (total {len(turbines)})")
    assert len(turbines) == 20

    # ------------------------------------- (i) farm-stratified two-level boot ---
    rng = np.random.default_rng(a.seed)
    glists = {f: [groups[t] for t in by_farm[f]] for f in farms}
    draws = np.empty(a.reps)
    for r in range(a.reps):
        parts = []
        for f in farms:                       # resample turbines WITHIN each farm
            gl = glists[f]
            k = len(gl)
            for g in rng.integers(0, k, size=k):
                grp = gl[g]
                parts.append(grp[rng.integers(0, len(grp), size=len(grp))])
        draws[r] = headline(E, act, np.concatenate(parts))
    v = draws[np.isfinite(draws)]
    strat = dict(point=point, ci_lo=float(np.percentile(v, 2.5)),
                 ci_hi=float(np.percentile(v, 97.5)),
                 boot_mean=float(v.mean()), boot_sd=float(v.std(ddof=1)),
                 n_finite_reps=int(len(v)))
    print(f"\n(i) farm-stratified: {100*point:.3f} % "
          f"[{100*strat['ci_lo']:.3f}, {100*strat['ci_hi']:.3f}]  "
          f"(sd {100*strat['boot_sd']:.3f} pp, {a.reps:,} reps, seed {a.seed})")

    # ---------------------------------------------- (iii) unstratified, QUOTED ---
    b = pd.read_csv(BOOT_CSV)
    q = b[(b.tier == "T2") & (b.rule == "same") & (b.T_act_h == 6)
          & (b.statistic == "E_actionable")].iloc[0]
    assert abs(float(q["point"]) - point) < 1e-9, \
        "bootstrap.csv point differs from the recomputed headline"
    print(f"(iii) unstratified (quoted from bootstrap.csv, seed {int(q['seed'])}): "
          f"{100*float(q['point']):.3f} % "
          f"[{100*float(q['ci_lo']):.3f}, {100*float(q['ci_hi']):.3f}]")

    # -------------------------------------------- (ii) leave-one-turbine-out ---
    loo = []
    allix = np.arange(len(E))
    for t in turbines:
        keep = np.setdiff1d(allix, groups[t], assume_unique=True)
        h = headline(E, act, keep)
        loo.append(dict(farm=t[0], turbine_id=t[1], n_events=len(groups[t]),
                        E_mwh=float(E[groups[t]].sum()),
                        n_actionable=int(act[groups[t]].sum()),
                        E_actionable_mwh=float(E[groups[t]][act[groups[t]]].sum()),
                        headline_loo=h, shift_pp=100 * (h - point)))
    loo = pd.DataFrame(loo).sort_values("shift_pp")
    worst = loo.iloc[int(loo.shift_pp.abs().values.argmax())]
    print(f"\n(ii) leave-one-turbine-out: headline range "
          f"[{100*loo.headline_loo.min():.3f}, {100*loo.headline_loo.max():.3f}] % "
          f"(width {100*(loo.headline_loo.max()-loo.headline_loo.min()):.3f} pp); "
          f"most influential {worst.farm} WT{int(worst.turbine_id):02d} "
          f"({worst.shift_pp:+.3f} pp)")
    print(loo.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # ------------------------------------------------------------------- write ---
    rows = []
    rows.append(dict(analysis="bootstrap_farm_stratified", scope="all",
                     farm="", turbine_id=np.nan, n_events=len(E), E_mwh=float(E.sum()),
                     point_pct=100 * point, ci_lo_pct=100 * strat["ci_lo"],
                     ci_hi_pct=100 * strat["ci_hi"],
                     boot_mean_pct=100 * strat["boot_mean"],
                     boot_sd_pp=100 * strat["boot_sd"], reps=a.reps, seed=a.seed,
                     n_finite_reps=strat["n_finite_reps"], shift_pp=np.nan,
                     note="turbines resampled within farm (6 Kelmarsh, 14 Penmanshiel), "
                          "then events within turbine; percentile 95% CI"))
    rows.append(dict(analysis="bootstrap_unstratified_quoted", scope="all",
                     farm="", turbine_id=np.nan, n_events=int(q["n_events"]),
                     E_mwh=float(E.sum()), point_pct=100 * float(q["point"]),
                     ci_lo_pct=100 * float(q["ci_lo"]),
                     ci_hi_pct=100 * float(q["ci_hi"]),
                     boot_mean_pct=100 * float(q["boot_mean"]),
                     boot_sd_pp=100 * float(q["boot_sd"]), reps=int(q["reps"]),
                     seed=int(q["seed"]), n_finite_reps=int(q["n_finite_reps"]),
                     shift_pp=np.nan,
                     note="QUOTED verbatim from bootstrap.csv, not recomputed"))
    for _, r in loo.iterrows():
        rows.append(dict(analysis="leave_one_turbine_out", scope="drop_turbine",
                         farm=r.farm, turbine_id=int(r.turbine_id),
                         n_events=int(r.n_events), E_mwh=float(r.E_mwh),
                         point_pct=100 * float(r.headline_loo), ci_lo_pct=np.nan,
                         ci_hi_pct=np.nan, boot_mean_pct=np.nan, boot_sd_pp=np.nan,
                         reps=np.nan, seed=np.nan, n_finite_reps=np.nan,
                         shift_pp=float(r.shift_pp),
                         note=f"dropped turbine carried {int(r.n_actionable)} "
                              f"actionable events / {r.E_actionable_mwh:,.1f} MWh"))
    rows.append(dict(analysis="leave_one_turbine_out_summary", scope="all", farm="",
                     turbine_id=np.nan, n_events=len(E), E_mwh=float(E.sum()),
                     point_pct=100 * point,
                     ci_lo_pct=100 * float(loo.headline_loo.min()),
                     ci_hi_pct=100 * float(loo.headline_loo.max()),
                     boot_mean_pct=np.nan, boot_sd_pp=np.nan, reps=np.nan,
                     seed=np.nan, n_finite_reps=np.nan,
                     shift_pp=float(loo.shift_pp.abs().max()),
                     note=f"min/max over the 20 leave-one-turbine-out refits; "
                          f"most influential {worst.farm} "
                          f"WT{int(worst.turbine_id):02d} ({worst.shift_pp:+.3f} pp)"))
    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nwrote {OUT_CSV}: {len(out):,} rows")
    return out


if __name__ == "__main__":
    main()
