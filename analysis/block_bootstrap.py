#!/usr/bin/env python3
"""STUDY_DESIGN v1.6(b) - turbine-year block bootstrap of the headline.

bootstrap.py's frozen two-level bootstrap resamples turbines, then that turbine's
EVENTS independently within turbine. That inner level assumes events are
exchangeable within a turbine over the whole 2016-2024 record. A referee objection:
a turbine's events are serially dependent (a bad converter year produces a run of
correlated outages), so the inner level may understate the variance.

This variant keeps the same outer level - 20 turbines drawn with replacement - but
makes the inner unit a TURBINE-YEAR BLOCK (calendar year of the event start): for a
drawn turbine, its turbine-years are resampled with replacement, keeping every event
inside a drawn block together. Serial dependence within a year is therefore carried
into the replicate rather than broken up.

  headline = energy-weighted actionable-unacted share of T2 wide-grid lost energy,
             same-component rule, 72 h lookback, T_act = 6 h
  10,000 reps, seed 20260907, percentile 95 % CI, bootstrap sd.

The frozen unstratified CI (bootstrap.csv, seed 20260827) and the farm-stratified CI
(cluster_robustness.csv, seed 20260904) are QUOTED from their artefacts, not
recomputed, so those numbers keep a single source.

Writes:
    analysis/block_bootstrap.csv

    python3 block_bootstrap.py [--reps 10000] [--seed 20260907]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

DERIVED = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
OUT_CSV = os.path.join(HERE, "block_bootstrap.csv")
BOOT_CSV = os.path.join(HERE, "bootstrap.csv")
CLUST_CSV = os.path.join(HERE, "cluster_robustness.csv")

TIER_FLAG = "T2_wide_grid"
RULE, LOOKBACK_H, T_ACT_H = "same", 72, 6
DEFAULT_REPS, DEFAULT_SEED = 10_000, 20260907


def headline(E, act, ix):
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

    # -------------------------------------------------- turbine-year blocks ---
    year = s["start"].dt.year.values
    tkey = list(zip(s["farm"].values, s["turbine_id"].values))
    bkey = list(zip(s["farm"].values, s["turbine_id"].values, year))

    turbines = sorted(set(tkey))
    assert len(turbines) == 20, f"expected 20 turbines, got {len(turbines)}"
    blocks = {}
    for i, b in enumerate(bkey):
        blocks.setdefault(b, []).append(i)
    blocks = {b: np.asarray(v, dtype=np.int64) for b, v in blocks.items()}
    by_turbine = {t: [] for t in turbines}
    for b, v in blocks.items():
        by_turbine[(b[0], b[1])].append(v)

    sizes = np.array([len(v) for v in blocks.values()])
    ener = np.array([float(E[v].sum()) for v in blocks.values()])
    per_t = np.array([len(by_turbine[t]) for t in turbines])
    print(f"\nturbine-year blocks: {len(blocks):,} over {len(turbines)} turbines "
          f"and {len(set(year))} calendar years ({year.min()}-{year.max()})")
    print(f"  blocks per turbine: min {per_t.min()}, median {np.median(per_t):.0f}, "
          f"max {per_t.max()}, mean {per_t.mean():.2f}")
    print(f"  events per block:   min {sizes.min()}, p25 {np.percentile(sizes,25):.0f}, "
          f"median {np.median(sizes):.0f}, p75 {np.percentile(sizes,75):.0f}, "
          f"max {sizes.max()}, mean {sizes.mean():.2f}")
    print(f"  MWh per block:      min {ener.min():.2f}, median {np.median(ener):.2f}, "
          f"max {ener.max():.1f}, mean {ener.mean():.2f}")
    assert sizes.sum() == len(E)

    # ------------------------------------------ block bootstrap (10,000 reps) ---
    rng = np.random.default_rng(a.seed)
    blists = [by_turbine[t] for t in turbines]
    k = len(blists)
    draws = np.empty(a.reps)
    for r in range(a.reps):
        parts = []
        for g in rng.integers(0, k, size=k):       # outer: turbines w/ replacement
            bl = blists[g]
            nb = len(bl)
            for j in rng.integers(0, nb, size=nb):  # inner: turbine-YEAR blocks
                parts.append(bl[j])                 # whole block kept together
        draws[r] = headline(E, act, np.concatenate(parts))
    v = draws[np.isfinite(draws)]
    ci_lo, ci_hi = float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))
    print(f"\n(block) turbine-year block bootstrap: {100*point:.3f} % "
          f"[{100*ci_lo:.3f}, {100*ci_hi:.3f}]  (sd {100*v.std(ddof=1):.3f} pp, "
          f"{a.reps:,} reps, seed {a.seed}, {len(v):,} finite)")

    # ---------------------------------------------------- quoted comparisons ---
    b = pd.read_csv(BOOT_CSV)
    q = b[(b.tier == "T2") & (b.rule == "same") & (b.T_act_h == 6)
          & (b.statistic == "E_actionable")].iloc[0]
    assert abs(float(q["point"]) - point) < 1e-9, \
        "bootstrap.csv point differs from the recomputed headline"
    c = pd.read_csv(CLUST_CSV)
    cs = c[c.analysis == "bootstrap_farm_stratified"].iloc[0]
    assert abs(float(cs["point_pct"]) / 100 - point) < 1e-9, \
        "cluster_robustness.csv point differs from the recomputed headline"
    print(f"(quoted) unstratified   seed {int(q['seed'])}: {100*float(q['point']):.3f} % "
          f"[{100*float(q['ci_lo']):.3f}, {100*float(q['ci_hi']):.3f}] "
          f"(sd {100*float(q['boot_sd']):.3f} pp)")
    print(f"(quoted) farm-stratified seed {int(cs['seed'])}: {float(cs['point_pct']):.3f} % "
          f"[{float(cs['ci_lo_pct']):.3f}, {float(cs['ci_hi_pct']):.3f}] "
          f"(sd {float(cs['boot_sd_pp']):.3f} pp)")

    # ------------------------------------------------------------------ write ---
    rows = [dict(
        analysis="bootstrap_turbine_year_block", scope="all",
        n_events=len(E), E_mwh=float(E.sum()), n_turbines=len(turbines),
        n_blocks=len(blocks), point_pct=100 * point, ci_lo_pct=100 * ci_lo,
        ci_hi_pct=100 * ci_hi, boot_mean_pct=100 * float(v.mean()),
        boot_sd_pp=100 * float(v.std(ddof=1)), reps=a.reps, seed=a.seed,
        n_finite_reps=int(len(v)),
        note="outer: 20 turbines with replacement; inner: that turbine's "
             "turbine-year blocks with replacement, all events in a drawn block "
             "kept together; percentile 95% CI"),
        dict(analysis="bootstrap_unstratified_quoted", scope="all",
             n_events=int(q["n_events"]), E_mwh=float(E.sum()),
             n_turbines=len(turbines), n_blocks=np.nan,
             point_pct=100 * float(q["point"]), ci_lo_pct=100 * float(q["ci_lo"]),
             ci_hi_pct=100 * float(q["ci_hi"]),
             boot_mean_pct=100 * float(q["boot_mean"]),
             boot_sd_pp=100 * float(q["boot_sd"]), reps=int(q["reps"]),
             seed=int(q["seed"]), n_finite_reps=int(q["n_finite_reps"]),
             note="QUOTED verbatim from bootstrap.csv, not recomputed"),
        dict(analysis="bootstrap_farm_stratified_quoted", scope="all",
             n_events=int(cs["n_events"]), E_mwh=float(E.sum()),
             n_turbines=len(turbines), n_blocks=np.nan,
             point_pct=float(cs["point_pct"]), ci_lo_pct=float(cs["ci_lo_pct"]),
             ci_hi_pct=float(cs["ci_hi_pct"]),
             boot_mean_pct=float(cs["boot_mean_pct"]),
             boot_sd_pp=float(cs["boot_sd_pp"]), reps=int(cs["reps"]),
             seed=int(cs["seed"]), n_finite_reps=int(cs["n_finite_reps"]),
             note="QUOTED verbatim from cluster_robustness.csv, not recomputed"),
        dict(analysis="block_structure", scope="turbine_year_blocks",
             n_events=len(E), E_mwh=float(E.sum()), n_turbines=len(turbines),
             n_blocks=len(blocks), point_pct=np.nan, ci_lo_pct=np.nan,
             ci_hi_pct=np.nan, boot_mean_pct=np.nan, boot_sd_pp=np.nan,
             reps=np.nan, seed=np.nan, n_finite_reps=np.nan,
             note=f"events per block min {sizes.min()} / median "
                  f"{np.median(sizes):.0f} / mean {sizes.mean():.2f} / max "
                  f"{sizes.max()}; blocks per turbine min {per_t.min()} / median "
                  f"{np.median(per_t):.0f} / max {per_t.max()}; MWh per block "
                  f"median {np.median(ener):.2f} / max {ener.max():.1f}")]

    # per-block detail rows, so the block structure is auditable
    for (farm, tid, yr), v_ix in sorted(blocks.items()):
        rows.append(dict(
            analysis="block_detail", scope=f"{farm}_WT{int(tid):02d}_{int(yr)}",
            n_events=len(v_ix), E_mwh=float(E[v_ix].sum()), n_turbines=np.nan,
            n_blocks=np.nan, point_pct=np.nan, ci_lo_pct=np.nan, ci_hi_pct=np.nan,
            boot_mean_pct=np.nan, boot_sd_pp=np.nan, reps=np.nan, seed=np.nan,
            n_finite_reps=np.nan,
            note=f"{int(act[v_ix].sum())} actionable events / "
                 f"{E[v_ix][act[v_ix]].sum():,.1f} MWh actionable"))

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nwrote {OUT_CSV}: {len(out):,} rows")
    return out


if __name__ == "__main__":
    main()
