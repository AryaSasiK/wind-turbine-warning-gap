#!/usr/bin/env python3
"""STUDY_DESIGN v1.3(b) - lead-time dispersion, per component family.

The ECDF (fig2) shows the pooled lead-time distribution but hides how differently
the families behave: the pooled curve is essentially the anemometry curve, because
anemometry supplies 851 of the 979 same-component-warned events while carrying
almost none of the energy. This script draws the dispersion family by family.

Boxes: line = median, box = IQR (p25-p75), whiskers = 5th/95th percentile. Every
box is a count-weighted distribution over warned events; the energy-weighted
median is overlaid as a separate marker, because the two answer different
questions ("the typical warned event" vs "the typical warned MWh") and they
disagree by an order of magnitude at the pooled level.

Families are shown when they carry at least 10 same-component-warned events, and
are ordered by their share of T2 lost energy (the ordering used everywhere else
in the paper), not by the number of warned events.

Writes:
    analysis/leadtime_box.csv     the box statistics behind every box
    paper/figures/fig6.pdf

    python3 leadtime_box.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import common as C
import decompose as D
import figures as F
import matplotlib.pyplot as plt

LOOKBACK = 72
TIER_FLAG = "T2_wide_grid"
MIN_WARNED_EVENTS = 10
BOX_CSV = os.path.join(C.SUMMARY_OUT, "leadtime_box.csv")


def t2():
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    s = att[att[TIER_FLAG].values].reset_index(drop=True)
    assert len(s) == 4213 and abs(s["E_mwh"].sum() - 9386.5) < 0.05
    return s


def stats_for(lead, E, group, kind, rule, fam_E):
    """One row of box statistics."""
    lead = np.asarray(lead, dtype=float)
    E = np.asarray(E, dtype=float)
    p5, p25, med, p75, p95 = np.percentile(lead, [5, 25, 50, 75, 95])
    ew_med = D.weighted_quantiles(lead, E, (0.5,))[0]
    tot = E.sum()
    return dict(
        group=group, kind=kind, rule=rule,
        n_warned=len(lead), E_warned_mwh=float(tot), E_family_T2_mwh=float(fam_E),
        lead_p5_h=float(p5), lead_p25_h=float(p25), lead_median_h=float(med),
        lead_p75_h=float(p75), lead_p95_h=float(p95),
        lead_ew_median_h=float(ew_med), lead_mean_h=float(lead.mean()),
        frac_ge_6h_count=float((lead >= 6).mean()),
        frac_ge_6h_energy=float(E[lead >= 6].sum() / tot) if tot > 0 else np.nan,
    )


def build(s):
    fam_E = s.groupby("family")["E_mwh"].sum()
    rows = []

    wcol, lcol = D._cols("same", LOOKBACK)
    w = s[s[wcol].values]
    order = [f for f in fam_E.sort_values(ascending=False).index
             if (w["family"] == f).sum() >= MIN_WARNED_EVENTS]
    for fam in order:
        g = w[w["family"] == fam]
        rows.append(stats_for(g[lcol].values, g["E_mwh"].values, fam, "family",
                              "same", fam_E[fam]))
    for rule, lbl in (("same", "All same-component"), ("any", "All any-warning")):
        wc, lc = D._cols(rule, LOOKBACK)
        g = s[s[wc].values]
        rows.append(stats_for(g[lc].values, g["E_mwh"].values, lbl, "overall",
                              rule, s["E_mwh"].sum()))

    out = pd.DataFrame(rows)
    out.to_csv(BOX_CSV, index=False)
    print(f"wrote {BOX_CSV}: {len(out):,} rows")
    # sanity: the two overall rows must reproduce leadtime_stats.csv
    ls = pd.read_csv(os.path.join(C.SUMMARY_OUT, "leadtime_stats.csv"))
    for rule, lbl in (("same", "All same-component"), ("any", "All any-warning")):
        a = out[out.group == lbl].iloc[0]
        b = ls[(ls.tier == "T2") & (ls.rule == rule) & (ls.weight == "count")].iloc[0]
        c = ls[(ls.tier == "T2") & (ls.rule == rule) & (ls.weight == "energy")].iloc[0]
        ok = (int(a.n_warned) == int(b.n_warned)
              and abs(a.lead_median_h - b.lead_median_h) < 0.02
              and abs(a.lead_ew_median_h - c.lead_median_h) < 0.02)
        print(f"  SANITY {lbl}: n {int(a.n_warned)} vs {int(b.n_warned)}, "
              f"median {a.lead_median_h:.2f} vs {b.lead_median_h:.2f}, "
              f"E-median {a.lead_ew_median_h:.2f} vs {c.lead_median_h:.2f}  "
              f"{'OK' if ok else 'FAIL'}")
    return out


def fig6(box):
    F.style()
    OI = F.OI
    fig, ax = plt.subplots(figsize=(F.COL_W, 2.7))

    bxp = []
    for _, r in box.iterrows():
        bxp.append(dict(med=r.lead_median_h, q1=r.lead_p25_h, q3=r.lead_p75_h,
                        whislo=r.lead_p5_h, whishi=r.lead_p95_h, fliers=[],
                        label=r.group))
    art = ax.bxp(bxp, showfliers=False, widths=0.6, patch_artist=True,
                 medianprops=dict(color=OI["black"], lw=1.0),
                 whiskerprops=dict(color=OI["grey"], lw=0.7),
                 capprops=dict(color=OI["grey"], lw=0.7),
                 boxprops=dict(edgecolor=OI["grey"], lw=0.5))
    for patch, (_, r) in zip(art["boxes"], box.iterrows()):
        patch.set_facecolor(OI["vermil"] if r.kind == "family"
                            else (OI["blue"] if r.rule == "any" else OI["orange"]))
        patch.set_alpha(0.55)

    x = np.arange(1, len(box) + 1)
    ax.plot(x, box.lead_ew_median_h.values, ls="none", marker="D", ms=3.4,
            mfc=OI["black"], mec="white", mew=0.5, zorder=6,
            label="Energy-weighted median")
    ax.axhline(6, color=OI["black"], lw=0.7, ls=(0, (3, 1.4)), zorder=1)
    ax.text(len(box) + 0.55, 6, "$T_{act}$\n6 h", fontsize=6.0, ha="left",
            va="center", linespacing=1.2)

    ax.set_yscale("log")
    ax.set_ylim(5e-4, 160)
    ax.set_yticks([1e-3, 1e-2, 0.1, 1, 6, 24, 72])
    ax.set_yticklabels(["0.001", "0.01", "0.1", "1", "6", "24", "72"])
    ax.set_ylabel("Warning lead time (h)")
    ax.set_xticklabels(
        [f"{r.group.replace('All ', '')}\n(n={int(r.n_warned):,})"
         for _, r in box.iterrows()], fontsize=6.0, rotation=32, ha="right",
        rotation_mode="anchor")
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=OI["grey"], alpha=0.25)
    ax.set_axisbelow(True)
    nfam = int((box.kind == "family").sum())
    ax.axvline(nfam + 0.5, color=OI["grey"], lw=0.6, ls=":", alpha=0.8)
    ax.legend(loc="lower left", handlelength=1.0, handletextpad=0.3, fontsize=6.2)
    fig.tight_layout()
    return F.save(fig, "fig6.pdf")


def main():
    s = t2()
    box = build(s)
    fig6(box)
    print("\n=== lead-time box statistics (72 h window, T2 wide-grid) ===")
    print(box[["group", "n_warned", "E_warned_mwh", "lead_p5_h", "lead_p25_h",
               "lead_median_h", "lead_p75_h", "lead_p95_h", "lead_ew_median_h"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))


if __name__ == "__main__":
    main()
