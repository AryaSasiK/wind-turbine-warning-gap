#!/usr/bin/env python3
"""STUDY_DESIGN v1.3(a) - downtime-duration grounding for T_act.

The external reviewer's question (2026-09-03) is whether T_act = 6 h is a
defensible conservative floor. That is a question about the outages themselves:
a 6 h action horizon only makes sense if the outages that carry the lost energy
last appreciably longer than 6 h. So this script grounds T_act in the observed
T2 outage-duration distribution and then reports the headline share as a
continuous function of T_act rather than at a single frozen point.

Three artefacts + one figure:

  duration_grounding.csv   T2 outage-duration quantiles (count- and
                           energy-weighted, overall and per component family)
                           and the share of T2 lost energy sitting in outages
                           of at least {1, 6, 24, 72, 168} h.
  tact_curve.csv           actionable-unacted share vs T_act on a log grid
                           0.5-72 h, both matching rules, energy- and
                           count-weighted, with a two-level cluster-bootstrap
                           95 % band. Read at 6 h and at the data-derived
                           reference points (energy-weighted duration
                           p25/p50/p75).
  lead_vs_duration.csv     per-event lead vs the outage's own eventual
                           duration, among warned events: share of warned lost
                           energy whose lead >= duration, and the 2x2 quadrant
                           split at lead >= 6 h by duration >= 6 h.
  paper/figures/fig5.pdf   top: duration histogram (log x, count share per bin
                           with the energy share overlaid); bottom: the T_act
                           curve with its band and the reference markers.

Nothing frozen is recomputed: the event population, the attribution columns and
the control anchors are read from stage-2 artefacts exactly as decompose.py
reads them, and the curve at T_act = 6 h reproduces the frozen 7.53 % / 34.33 %.

    python3 duration_grounding.py [--reps 2000] [--seed 20260903]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import common as C
import decompose as D
import figures as F                       # house style: 3.5 in column, 8 pt, Okabe-Ito
import matplotlib.pyplot as plt           # figures.py has already selected Agg

REPS = 2000
SEED = 20260903
QS = (0.10, 0.25, 0.50, 0.75, 0.90)
DUR_THRESH_H = (1, 6, 24, 72, 168)
LOOKBACK = 72
TIER_FLAG = "T2_wide_grid"

DUR_CSV = os.path.join(C.SUMMARY_OUT, "duration_grounding.csv")
TACT_CSV = os.path.join(C.SUMMARY_OUT, "tact_curve.csv")
LVD_CSV = os.path.join(C.SUMMARY_OUT, "lead_vs_duration.csv")


# --------------------------------------------------------------- population
def t2():
    """The frozen primary population: T2 wide-grid events, attribution columns."""
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    s = att[att[TIER_FLAG].values].reset_index(drop=True)
    assert len(s) == 4213, f"T2 population changed: {len(s)}"
    assert abs(s["E_mwh"].sum() - 9386.5) < 0.05, "T2 lost energy changed"
    return s


# ------------------------------------------------------------ (1) durations
def duration_table(s):
    rows = []

    def block(scope, g):
        for weight in ("count", "energy"):
            w = np.ones(len(g)) if weight == "count" else g["E_mwh"].values
            q = D.weighted_quantiles(g["duration_h"].values, w, QS)
            for name, v in zip(("p10", "p25", "p50", "p75", "p90"), q):
                rows.append(dict(metric="duration_quantile", scope=scope,
                                 weight=weight, stat=name, value=v,
                                 n_events=len(g),
                                 E_mwh=float(g["E_mwh"].sum())))
            tot = w.sum()
            for th in DUR_THRESH_H:
                m = g["duration_h"].values >= th
                rows.append(dict(
                    metric="share_duration_ge", scope=scope, weight=weight,
                    stat=f"ge_{th}h", value=float(w[m].sum() / tot) if tot else np.nan,
                    n_events=int(m.sum()), E_mwh=float(g.loc[m, "E_mwh"].sum())))

    block("overall", s)
    for fam, g in s.groupby("family"):
        block(f"family:{fam}", g)
    # the same view restricted to the warned population, since the decision rule
    # is stated about *warned* lost energy
    for rule in ("same", "any"):
        wcol, _ = D._cols(rule, LOOKBACK)
        block(f"warned:{rule}", s[s[wcol].values])

    out = pd.DataFrame(rows)
    out.to_csv(DUR_CSV, index=False)
    print(f"wrote {DUR_CSV}: {len(out):,} rows")
    return out


# ------------------------------------------------------------ (2) T_act curve
def cluster_draws(s, reps, seed):
    """`reps` two-level cluster-bootstrap index arrays (turbines, then events).

    Same construction as bootstrap.py: the 20 (farm, turbine) clusters are
    resampled with replacement, then each drawn turbine's events are resampled
    with replacement keeping its event count fixed.
    """
    tk = list(zip(s["farm"].values, s["turbine_id"].values))
    turbines = sorted(set(tk))
    idx = {t: [] for t in turbines}
    for i, t in enumerate(tk):
        idx[t].append(i)
    groups = [np.asarray(idx[t], dtype=np.int64) for t in turbines]
    k = len(groups)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(reps):
        pick = rng.integers(0, k, size=k)
        draws.append(np.concatenate(
            [groups[g][rng.integers(0, len(groups[g]), size=len(groups[g]))]
             for g in pick]))
    return draws, len(turbines)


def tact_curve(s, reps, seed):
    ew_q = D.weighted_quantiles(s["duration_h"].values, s["E_mwh"].values,
                                (0.25, 0.50, 0.75))
    refs = {"T_act primary": 6.0,
            "duration p25 (E)": ew_q[0],
            "duration p50 (E)": ew_q[1],
            "duration p75 (E)": ew_q[2]}
    grid = np.logspace(np.log10(0.5), np.log10(72.0), 40)
    grid = np.unique(np.round(np.concatenate([grid, list(refs.values())]), 10))
    # a reference beyond the 72 h lookback is kept but flagged: no lead can
    # exceed the window, so the share there is 0 by construction, not by fact.
    ref_of = {}
    for lbl, v in refs.items():
        ref_of[round(v, 10)] = lbl

    draws, n_turb = cluster_draws(s, reps, seed)
    E = s["E_mwh"].values.astype(float)
    n = len(s)
    rows = []
    for rule in ("same", "any"):
        wcol, lcol = D._cols(rule, LOOKBACK)
        warned = s[wcol].values.astype(bool)
        lead = s[lcol].values.astype(float)
        # M[i, j] = event i is actionable at grid point j
        M = (warned[:, None] & (np.nan_to_num(lead, nan=-1.0)[:, None] >= grid[None, :]))
        Mf = M.astype(float)
        pt_e = (E @ Mf) / E.sum()
        pt_n = Mf.sum(axis=0) / n
        pt_w_e = E[warned].sum() / E.sum()
        pt_w_n = warned.sum() / n

        be = np.empty((reps, len(grid)))
        bn = np.empty((reps, len(grid)))
        for r, ix in enumerate(draws):
            Ei = E[ix]
            Mi = Mf[ix]
            be[r] = (Ei @ Mi) / Ei.sum()
            bn[r] = Mi.sum(axis=0) / len(ix)
        for j, t in enumerate(grid):
            for weight, pt, bs, warn_pt in (("energy", pt_e[j], be[:, j], pt_w_e),
                                            ("count", pt_n[j], bn[:, j], pt_w_n)):
                rows.append(dict(
                    rule=rule, weight=weight, T_act_h=float(t),
                    actionable_unacted=float(pt),
                    short_lead=float(warn_pt - pt),
                    unwarned=float(1.0 - warn_pt),
                    ci_lo=float(np.percentile(bs, 2.5)),
                    ci_hi=float(np.percentile(bs, 97.5)),
                    is_reference=round(float(t), 10) in ref_of,
                    ref_label=ref_of.get(round(float(t), 10), ""),
                    beyond_lookback=bool(t > LOOKBACK),
                    reps=reps, seed=seed, n_turbines=n_turb, n_events=n))
    out = pd.DataFrame(rows).sort_values(["rule", "weight", "T_act_h"])
    out.to_csv(TACT_CSV, index=False)
    print(f"wrote {TACT_CSV}: {len(out):,} rows "
          f"({len(grid)} grid points, {reps} reps, seed {seed})")

    # ---- gate: the curve must pass exactly through the frozen numbers -------
    def at(rule, weight, t):
        r = out[(out.rule == rule) & (out.weight == weight)
                & (np.isclose(out.T_act_h, t))]
        return float(r["actionable_unacted"].iloc[0])

    for rule, weight, want in (("same", "energy", 0.0753), ("same", "count", 0.1657),
                               ("any", "energy", 0.3433)):
        got = at(rule, weight, 6.0)
        ok = abs(got - want) < 5e-5
        print(f"  GATE {rule:>4}/{weight:<6} T_act=6 h: {100*got:.2f}% "
              f"vs frozen {100*want:.2f}%  {'OK' if ok else 'FAIL'}")
        assert ok, "T_act curve does not reproduce the frozen decomposition"
    return out, refs


# ----------------------------------------------------- (3) lead vs duration
def lead_vs_duration(s):
    rows = []
    for rule in ("same", "any"):
        wcol, lcol = D._cols(rule, LOOKBACK)
        w = s[s[wcol].values]
        lead = w[lcol].values.astype(float)
        dur = w["duration_h"].values.astype(float)
        E = w["E_mwh"].values.astype(float)
        n, tot = len(w), E.sum()

        m = lead >= dur
        rows.append(dict(rule=rule, metric="lead_ge_own_duration", cell="lead>=duration",
                         n_events=int(m.sum()), E_mwh=float(E[m].sum()),
                         share_count=float(m.mean()), share_energy=float(E[m].sum() / tot),
                         n_warned=n, E_warned_mwh=float(tot)))
        rows.append(dict(rule=rule, metric="lead_ge_own_duration", cell="lead<duration",
                         n_events=int((~m).sum()), E_mwh=float(E[~m].sum()),
                         share_count=float((~m).mean()),
                         share_energy=float(E[~m].sum() / tot),
                         n_warned=n, E_warned_mwh=float(tot)))
        for lo, dn, cell in ((True, True, "lead>=6h & dur>=6h"),
                             (True, False, "lead>=6h & dur<6h"),
                             (False, True, "lead<6h & dur>=6h"),
                             (False, False, "lead<6h & dur<6h")):
            q = ((lead >= 6) == lo) & ((dur >= 6) == dn)
            rows.append(dict(rule=rule, metric="quadrant_6h", cell=cell,
                             n_events=int(q.sum()), E_mwh=float(E[q].sum()),
                             share_count=float(q.mean()),
                             share_energy=float(E[q].sum() / tot),
                             n_warned=n, E_warned_mwh=float(tot)))
    out = pd.DataFrame(rows)
    out.to_csv(LVD_CSV, index=False)
    print(f"wrote {LVD_CSV}: {len(out):,} rows")
    for rule in ("same", "any"):
        q = out[(out.rule == rule) & (out.metric == "quadrant_6h")]
        print(f"  SANITY quadrants sum, {rule}: count {q.share_count.sum():.6f}, "
              f"energy {q.share_energy.sum():.6f}")
    return out


# ------------------------------------------------------------------ figure 5
def fig5(s, curve, refs):
    F.style()
    OI = F.OI
    fig, axes = plt.subplots(2, 1, figsize=(F.COL_W, 3.9),
                             gridspec_kw={"hspace": 0.62})

    # ---- top: duration histogram ------------------------------------------
    ax = axes[0]
    edges = np.logspace(np.log10(5e-4), np.log10(2e3), 44)
    dur, E = s["duration_h"].values, s["E_mwh"].values
    cnt, _ = np.histogram(dur, bins=edges)
    eng, _ = np.histogram(dur, bins=edges, weights=E)
    cnt_sh, eng_sh = 100 * cnt / cnt.sum(), 100 * eng / eng.sum()
    ctr = np.sqrt(edges[:-1] * edges[1:])
    ax.bar(ctr, cnt_sh, width=np.diff(edges), color=OI["grey"], alpha=0.85,
           edgecolor="white", linewidth=0.2, label="Events", zorder=2)
    ax.step(np.concatenate([[edges[0]], ctr, [edges[-1]]]),
            np.concatenate([[0], eng_sh, [0]]), where="mid",
            color=OI["vermil"], lw=1.1, label="Lost energy", zorder=3)
    ax.axvline(6, color=OI["black"], lw=0.8, ls=(0, (3, 1.4)), zorder=4)
    ax.text(6 * 1.25, ax.get_ylim()[1] * 0.96, "$T_{lead}$ = 6 h", fontsize=6.4,
            ha="left", va="top")
    ax.set_xscale("log")
    ax.set_xlim(edges[0], edges[-1])
    ax.set_xticks([1e-3, 1e-2, 1e-1, 1, 6, 24, 168, 1000])
    ax.set_xticklabels(["0.001", "0.01", "0.1", "1", "6", "24", "168", "1000"])
    ax.set_xlabel("Outage duration (h)")
    ax.set_ylabel("Share per bin (%)")
    ax.grid(axis="y", color=OI["grey"], alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", handlelength=1.3, borderpad=0.2, labelspacing=0.25)

    # ---- bottom: actionable-unacted share vs T_act -------------------------
    ax = axes[1]
    inb = curve[(curve.weight == "energy") & (~curve.beyond_lookback)]
    for rule, c, ls, lbl in (("same", OI["vermil"], "-", "Same-component"),
                             ("any", OI["blue"], (0, (3, 1.3)), "Any-warning")):
        g = inb[inb.rule == rule].sort_values("T_act_h")
        ax.fill_between(g.T_act_h, 100 * g.ci_lo, 100 * g.ci_hi, color=c,
                        alpha=0.16, linewidth=0, zorder=1)
        ax.plot(g.T_act_h, 100 * g.actionable_unacted, color=c, ls=ls, lw=1.1,
                label=lbl, zorder=3)

    marks = [("6 h", refs["T_act primary"], OI["black"], "-"),
             ("p25", refs["duration p25 (E)"], OI["green"], (0, (1.2, 1.6))),
             ("p50", refs["duration p50 (E)"], OI["green"], (0, (1.2, 1.6)))]
    for lbl, t, col, ls in marks:
        if t > LOOKBACK:
            continue
        ax.axvline(t, color=col, lw=0.6, ls=ls, zorder=2)
        for rule, c in (("same", OI["vermil"]), ("any", OI["blue"])):
            r = inb[(inb.rule == rule) & np.isclose(inb.T_act_h, t)]
            if len(r):
                ax.plot([t], [100 * float(r.actionable_unacted.iloc[0])], marker="o",
                        ms=3.0, color=c, zorder=5, clip_on=False)
    ax.text(0.02, 0.97,
            "dotted: energy-weighted outage\nduration p25 (17 h), p50 (53 h)",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.9,
            color=OI["green"], linespacing=1.3)

    ax.set_xscale("log")
    ax.set_xlim(0.5, 72)
    ax.set_ylim(0, 70)
    ax.set_xticks([0.5, 1, 6, 17.4, 24, 52.9, 72])
    ax.set_xticklabels(["0.5", "1", "6", "17", "24", "53", "72"], fontsize=6.3)
    for tick, col in zip(ax.get_xticklabels(),
                         [OI["black"]] * 2 + [OI["black"], OI["green"],
                                              OI["black"], OI["green"], OI["black"]]):
        tick.set_color(col)
    ax.set_xlabel("Lead-time threshold $T_{lead}$ (h)")
    # display label only; the CSV key stays `actionable_unacted` (ARTEFACT_KEY.md)
    ax.set_ylabel("Long-lead share\nof lost energy (%)", linespacing=1.25)
    ax.grid(color=OI["grey"], alpha=0.22)
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              handlelength=1.7, columnspacing=1.0, handletextpad=0.4)
    return F.save(fig, "fig5.pdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    print(f"seed {a.seed}, reps {a.reps}")

    s = t2()
    print(f"T2 wide-grid: {len(s):,} events / {s['E_mwh'].sum():,.1f} MWh")
    dur = duration_table(s)
    curve, refs = tact_curve(s, a.reps, a.seed)
    lead_vs_duration(s)
    fig5(s, curve, refs)

    print("\n=== energy-weighted T2 outage-duration quantiles (h) ===")
    print(dur[(dur.scope == "overall") & (dur.metric == "duration_quantile")]
          .pivot(index="weight", columns="stat", values="value")
          .to_string(float_format=lambda x: f"{x:,.3f}"))
    print("\n=== share of T2 lost energy in outages of at least ... ===")
    print(dur[(dur.scope == "overall") & (dur.metric == "share_duration_ge")
              & (dur.weight == "energy")][["stat", "value", "n_events"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("\n=== actionable-unacted share at the reference thresholds ===")
    print(curve[curve.is_reference][["rule", "weight", "ref_label", "T_act_h",
                                     "actionable_unacted", "ci_lo", "ci_hi",
                                     "beyond_lookback"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))


if __name__ == "__main__":
    main()
