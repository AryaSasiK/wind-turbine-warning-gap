#!/usr/bin/env python3
"""bootstrap.csv - two-level cluster bootstrap CIs and leave-one-out influence.

STUDY_DESIGN.md "Statistics":

    Energy-weighted shares with two-level cluster bootstrap: resample turbines, then
    events within turbine; 10,000 reps; percentile CIs.
    Influence: leave-one-out over the top-10 energy events; report max headline shift.

The outer level resamples the 20 turbines WITH replacement (they are the clusters
external validity is limited by - PROFILE §7: two sites, one OEM); the inner level
resamples that turbine's events with replacement, keeping its event count fixed. A
turbine drawn twice contributes two independent inner draws, which is what makes the
outer level do any work.

Control rates are recomputed INSIDE each replicate from the same resampled events, so
the control-excess statistic inherits the same clustering rather than being treated
as a fixed constant.

Everything is computed on plain numpy arrays extracted once; a replicate is a single
integer index array, so 10,000 reps over ~4,200 events runs in well under a minute.

    python3 bootstrap.py [--reps 10000] [--seed 20260827]
"""
import argparse
import os

import numpy as np
import pandas as pd

import attribute as A
import common as C
import counterfactual as CF
import decompose as D

BOOT_CSV = os.path.join(C.SUMMARY_OUT, "bootstrap.csv")
BOOT_DRAWS = os.path.join(C.DERIVED, "bootstrap_draws.parquet")
LOO_CSV = os.path.join(C.SUMMARY_OUT, "influence_loo.csv")

DEFAULT_REPS = 10_000
DEFAULT_SEED = 20260827


class Panel:
    """Flat numpy view of one tier's events, ready for index-array statistics."""

    def __init__(self, att, full, tier, rule, L, t_act, ctag="c45"):
        flag = D.TIERS[tier][0]
        m = full[flag].values
        a, f = att[m].reset_index(drop=True), full[m].reset_index(drop=True)
        wcol, lcol = D._cols(rule, L)
        cwcol, clcol = D._cols(rule, L, prefix=f"{ctag}_")

        self.tier, self.rule, self.L, self.t_act, self.ctag = tier, rule, L, t_act, ctag
        self.E = a["E_mwh"].values.astype(float)
        self.warned = a[wcol].values.astype(bool)
        self.lead = a[lcol].values.astype(float)
        self.act = self.warned & (self.lead >= t_act)
        self.short = self.warned & ~self.act
        self.cmatch = f[f"{ctag}_matched"].values.astype(bool)
        self.cwarn = np.nan_to_num(f[cwcol].values.astype(float), nan=0.0).astype(bool)
        self.cact = self.cwarn & (np.nan_to_num(f[clcol].values.astype(float),
                                                nan=-1.0) >= t_act)
        # counterfactual (median planned duration), per event
        pot = np.nan_to_num(a["mean_potential_kw"].values.astype(float), nan=0.0)
        self.rec_med = np.clip(self.E - np.clip(pot, 0, None) * PLANNED["median_h"]
                               / 1000.0, 0, None)
        self.rec_p75 = np.clip(self.E - np.clip(pot, 0, None) * PLANNED["p75_h"]
                               / 1000.0, 0, None)

        # cluster structure
        tk = list(zip(f["farm"].values, f["turbine_id"].values))
        self.turbines = sorted(set(tk))
        idx = {t: [] for t in self.turbines}
        for i, t in enumerate(tk):
            idx[t].append(i)
        self.groups = [np.asarray(idx[t], dtype=np.int64) for t in self.turbines]

    def stats(self, ix):
        """All headline statistics for one index array (a bootstrap replicate)."""
        E = self.E[ix]
        tot_e = E.sum()
        n = len(ix)
        w, ac, sh = self.warned[ix], self.act[ix], self.short[ix]
        cm = self.cmatch[ix]
        cw, ca = self.cwarn[ix] & cm, self.cact[ix] & cm
        Ec = E[cm]
        tot_ec = Ec.sum()

        def sfe(mask):                      # energy share
            return E[mask].sum() / tot_e if tot_e > 0 else np.nan

        def sfc(mask):                      # count share
            return mask.sum() / n if n else np.nan

        pE_w, pE_a = sfe(w), sfe(ac)
        pC_w = (E[cm & cw].sum() / tot_ec) if tot_ec > 0 else np.nan
        pC_a = (E[cm & ca].sum() / tot_ec) if tot_ec > 0 else np.nan
        pN_w, pN_a = sfc(w), sfc(ac)
        nc = cm.sum()
        pCn_w = (cw.sum() / nc) if nc else np.nan
        pCn_a = (ca.sum() / nc) if nc else np.nan

        return {
            "E_unwarned": sfe(~w), "E_short_lead": sfe(sh),
            "E_actionable": pE_a, "E_warned": pE_w,
            "N_unwarned": sfc(~w), "N_short_lead": sfc(sh),
            "N_actionable": pN_a, "N_warned": pN_w,
            "E_control_warned": pC_w, "N_control_warned": pCn_w,
            "E_excess_warned": D.excess(pE_w, pC_w),
            "E_excess_actionable": D.excess(pE_a, pC_a),
            "N_excess_warned": D.excess(pN_w, pCn_w),
            "N_excess_actionable": D.excess(pN_a, pCn_a),
            "E_enrichment_x": pE_w / pC_w if pC_w and pC_w > 0 else np.nan,
            "N_enrichment_x": pN_w / pCn_w if pCn_w and pCn_w > 0 else np.nan,
            "recoverable_mwh_median": self.rec_med[ix][ac].sum(),
            "recoverable_mwh_p75": self.rec_p75[ix][ac].sum(),
            "recoverable_pct_of_tier_E": (self.rec_med[ix][ac].sum() / tot_e * 100
                                          if tot_e > 0 else np.nan),
            "E_total_mwh": tot_e, "n_events": float(n),
        }


PLANNED = {}


def two_level_draw(panel, rng):
    """Resample turbines with replacement, then that turbine's events likewise."""
    k = len(panel.groups)
    pick = rng.integers(0, k, size=k)
    parts = []
    for g in pick:
        grp = panel.groups[g]
        parts.append(grp[rng.integers(0, len(grp), size=len(grp))])
    return np.concatenate(parts)


def run(panel, reps, seed):
    rng = np.random.default_rng(seed)
    point = panel.stats(np.arange(len(panel.E)))
    keys = list(point.keys())
    draws = np.full((reps, len(keys)), np.nan)
    for r in range(reps):
        # ONE draw per replicate, then read every statistic off that same draw -
        # otherwise each column would come from a different resample and the
        # joint structure (e.g. warned == short + actionable) would break.
        s = panel.stats(two_level_draw(panel, rng))
        draws[r] = [s[k] for k in keys]
    return point, pd.DataFrame(draws, columns=keys)


def summarise(point, draws, **meta):
    rows = []
    for k in draws.columns:
        v = draws[k].values
        v = v[np.isfinite(v)]
        rows.append(dict(
            statistic=k, point=point[k],
            ci_lo=float(np.percentile(v, 2.5)) if len(v) else np.nan,
            ci_hi=float(np.percentile(v, 97.5)) if len(v) else np.nan,
            boot_mean=float(v.mean()) if len(v) else np.nan,
            boot_sd=float(v.std(ddof=1)) if len(v) > 1 else np.nan,
            n_finite_reps=len(v), **meta))
    return rows


def leave_one_out(panel, top_n=10):
    """Drop each of the top-N energy events in turn; report the headline shift."""
    base = panel.stats(np.arange(len(panel.E)))
    order = np.argsort(-panel.E)[:top_n]
    keys = ["E_unwarned", "E_short_lead", "E_actionable", "E_warned",
            "E_excess_warned", "E_excess_actionable", "recoverable_mwh_median"]
    rows = []
    for i in order:
        ix = np.delete(np.arange(len(panel.E)), i)
        s = panel.stats(ix)
        row = {"dropped_rank": int((np.argsort(-panel.E) == i).nonzero()[0][0]) + 1,
               "dropped_index": int(i), "dropped_E_mwh": float(panel.E[i]),
               "dropped_warned": bool(panel.warned[i]),
               "dropped_actionable": bool(panel.act[i]),
               "dropped_lead_h": float(panel.lead[i])}
        for k in keys:
            row[f"{k}_loo"] = s[k]
            row[f"{k}_shift"] = s[k] - base[k]
        rows.append(row)
    return base, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args()

    PLANNED.update(CF.scheduled_maintenance_durations())
    print(f"planned intervention: median {PLANNED['median_h']:.3f} h, "
          f"p75 {PLANNED['p75_h']:.3f} h")

    att, full = D.load()

    # cells to bootstrap: the primary cell, its any-warning upper bound, the
    # T0/T1 companions (figure 1's thin bars), and the two T_act sensitivities.
    cells = [("T2", "same", 72, 6), ("T2", "any", 72, 6),
             ("T0", "same", 72, 6), ("T1", "same", 72, 6),
             ("T0", "any", 72, 6), ("T1", "any", 72, 6),
             ("T2", "same", 72, 1), ("T2", "same", 72, 24)]

    all_rows, all_draws = [], []
    for tier, rule, L, t in cells:
        p = Panel(att, full, tier, rule, L, t)
        pt, dr = run(p, a.reps, a.seed)
        meta = dict(tier=tier, rule=rule, lookback_h=L, T_act_h=t,
                    control_offset_d=45, reps=a.reps, seed=a.seed,
                    n_turbines=len(p.turbines), n_events=len(p.E))
        all_rows += summarise(pt, dr, **meta)
        dr = dr.assign(tier=tier, rule=rule, T_act_h=t)
        all_draws.append(dr)
        print(f"  {tier:>3} {rule:>4} T_act={t:<3} "
              f"E_actionable {pt['E_actionable']:.4f} "
              f"[{np.percentile(dr['E_actionable'], 2.5):.4f}, "
              f"{np.percentile(dr['E_actionable'], 97.5):.4f}]")

    boot = pd.DataFrame(all_rows)
    boot.to_csv(BOOT_CSV, index=False)
    pd.concat(all_draws, ignore_index=True).to_parquet(BOOT_DRAWS, index=False)
    print(f"\nwrote {BOOT_CSV}: {len(boot):,} rows")
    print(f"wrote {BOOT_DRAWS}")

    # ---- influence ----------------------------------------------------------
    p = Panel(att, full, D.TIER_PRIMARY, D.RULE_PRIMARY,
              D.LOOKBACK_PRIMARY, D.T_ACT_PRIMARY)
    base, loo = leave_one_out(p, top_n=10)
    loo.to_csv(LOO_CSV, index=False)
    print(f"wrote {LOO_CSV}")

    shift_cols = [c for c in loo.columns if c.endswith("_shift")
                  and not c.startswith("recoverable")]
    mx = loo[shift_cols].abs().max()
    print("\n=== leave-one-out over the top-10 energy events (T2 primary cell) ===")
    print(loo[["dropped_rank", "dropped_E_mwh", "dropped_warned",
               "dropped_actionable", "E_actionable_loo", "E_actionable_shift",
               "E_warned_shift"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("\nmax |shift| per statistic:")
    print(mx.to_string(float_format=lambda x: f"{x:,.4f}"))
    print(f"\nMAX HEADLINE SHIFT (E_actionable) = "
          f"{loo['E_actionable_shift'].abs().max():.4f} "
          f"({100*loo['E_actionable_shift'].abs().max():.2f} pp)")

    h = boot[(boot.tier == "T2") & (boot.rule == "same") & (boot.T_act_h == 6)]
    print("\n=== HEADLINE CIs (T2 wide-grid, same-component, 72 h, T_act 6 h) ===")
    print(h[["statistic", "point", "ci_lo", "ci_hi", "boot_sd"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    return boot


if __name__ == "__main__":
    main()
