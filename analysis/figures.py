#!/usr/bin/env python3
"""paper/figures/fig1..fig4.pdf - the four figures STUDY_DESIGN.md asks for.

    1. Decomposition stacked bar (energy-weighted, T2, with CIs; T0/T1 thin companions).
    2. Lead-time ECDF for warned events, with T_act markers.
    3. Warned-share: events vs matched controls, by duration bucket (the enrichment).
    4. Per-event scatter: lost energy vs lead time (log-log), coloured by component family.

House style: IEEE single-column width (3.5 in), vector PDF, Type-42/TrueType-free
(PDF Type 3 fonts disabled so the IEEE PDF-express check passes), 8 pt base type so
axis labels stay legible at print size, and a colourblind-safe palette (Okabe-Ito,
which is safe for deuteranopia, protanopia and tritanopia). No titles - captions live
in the LaTeX source.

    python3 figures.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import attribute as A
import common as C
import decompose as D

FIGDIR = os.path.join(C.PROJECT, "paper", "figures")
COL_W = 3.5                     # IEEE column width, inches
DPI = 600

# Okabe-Ito, colourblind-safe
OI = {
    "black":  "#000000", "orange": "#E69F00", "skyblue": "#56B4E9",
    "green":  "#009E73", "yellow": "#F0E442", "blue":    "#0072B2",
    "vermil": "#D55E00", "purple": "#CC79A7", "grey":    "#999999",
}
# the three decomposition buckets, dark -> light so the stack reads top-down
BUCKET_C = {"unwarned": OI["grey"], "short_lead": OI["skyblue"],
            "actionable_unacted": OI["vermil"]}
# Display labels only. The CSV keys are frozen: `actionable_unacted` is the key,
# "Long-lead" is what the paper calls the class from the 2026-09-07 revision
# (neutral wording about a logged row, see analysis/ARTEFACT_KEY.md).
BUCKET_LBL = {"unwarned": "Unwarned", "short_lead": "Short-lead",
              "actionable_unacted": "Long-lead"}


def style():
    plt.rcParams.update({
        "figure.dpi": DPI, "savefig.dpi": DPI,
        "pdf.fonttype": 42, "ps.fonttype": 42,      # embed TrueType, no Type 3
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.6, "grid.linewidth": 0.4,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "lines.linewidth": 1.1, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def save(fig, name):
    os.makedirs(FIGDIR, exist_ok=True)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, format="pdf")
    plt.close(fig)
    print(f"wrote {p}")
    return p


# --------------------------------------------------------------------- fig 1
def fig1(dec, boot):
    """Stacked decomposition bars, T2 primary thick, T0/T1 thin companions."""
    fig, ax = plt.subplots(figsize=(COL_W, 2.35))
    rows = [("T2", "T2 (primary)", 0.52), ("T1", "T1", 0.26), ("T0", "T0", 0.26)]
    ypos = [0.0, -0.62, -1.06]

    for (tier, label, h), y in zip(rows, ypos):
        r = dec[(dec.population == "all") & (dec.tier == tier)
                & (dec.rule == "same") & (dec.lookback_h == 72)
                & (dec.T_act_h == 6) & (dec.control_offset_d == 45)
                & (dec.weight == "energy")].iloc[0]
        left = 0.0
        for b in ("unwarned", "short_lead", "actionable_unacted"):
            ax.barh(y, r[b], height=h, left=left, color=BUCKET_C[b],
                    edgecolor="white", linewidth=0.5)
            if r[b] > 0.055:
                # one decimal so the printed shares sum to 100.0, not 101
                ax.text(left + r[b] / 2, y, f"{100*r[b]:.1f}", ha="center",
                        va="center", fontsize=6.5,
                        color="white" if b != "short_lead" else "black")
            left += r[b]
        ax.text(-0.015, y, label, ha="right", va="center", fontsize=7.5)

        # 95 % CI on the headline (actionable-unacted) share. The bucket is the
        # rightmost segment, so its width uncertainty is drawn as movement of its
        # LEFT boundary at 1 - share; a whisker on the right edge would sit at
        # 100 % and read as uncertainty about the total, which it is not.
        if tier == "T2":
            b = boot[(boot.tier == "T2") & (boot.rule == "same")
                     & (boot.T_act_h == 6)
                     & (boot.statistic == "E_actionable")].iloc[0]
            yy = y + h / 2 + 0.17
            ax.errorbar([1 - b["point"]], [yy],
                        xerr=[[b["ci_hi"] - b["point"]], [b["point"] - b["ci_lo"]]],
                        fmt="none", ecolor=OI["black"], elinewidth=0.8, capsize=2,
                        capthick=0.8, clip_on=False, zorder=5)
            ax.plot([1 - b["point"]], [yy], marker="o", ms=2.4,
                    color=OI["black"], clip_on=False, zorder=6)
            ax.text(1 - b["ci_hi"] - 0.02, yy, "95% CI", ha="right", va="center",
                    fontsize=6.2)

    # any-warning upper bound on T2: where the unwarned block would end under the
    # permissive rule, i.e. how much of the gap is a component-matching artefact.
    ra = dec[(dec.population == "all") & (dec.tier == "T2") & (dec.rule == "any")
             & (dec.lookback_h == 72) & (dec.T_act_h == 6)
             & (dec.control_offset_d == 45) & (dec.weight == "energy")].iloc[0]
    ax.plot([ra["unwarned"]] * 2, [ypos[2] - 0.16, ypos[0] + 0.30], color=OI["black"],
            lw=0.9, ls=(0, (2.4, 1.4)), zorder=4)
    ax.text(ra["unwarned"], ypos[2] - 0.22, "any-warning\nwarned share",
            fontsize=6.2, ha="center", va="top", color=OI["black"], linespacing=1.2)

    ax.set_xlim(0, 1)
    ax.set_ylim(-1.62, 0.62)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xticks(np.arange(0, 1.01, 0.25))
    ax.set_xticklabels([f"{int(100*t)}" for t in np.arange(0, 1.01, 0.25)])
    ax.set_xlabel("Share of forced-outage lost energy (%)")
    ax.legend(handles=[Patch(facecolor=BUCKET_C[b], label=BUCKET_LBL[b])
                       for b in ("unwarned", "short_lead", "actionable_unacted")],
              loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3,
              handlelength=1.1, handleheight=0.85, columnspacing=0.9,
              handletextpad=0.4)
    fig.tight_layout()
    return save(fig, "fig1.pdf")


# --------------------------------------------------------------------- fig 2
def fig2(att, full):
    """Lead-time ECDF for warned events, T_act markers, count and energy weighted."""
    fig, ax = plt.subplots(figsize=(COL_W, 2.25))
    m = full["T2_wide_grid"].values
    sub = att[m]

    specs = [("same", "count", OI["vermil"], "-", "Same-component"),
             ("same", "energy", OI["vermil"], (0, (3, 1.3)), "Same-component, MWh-wtd"),
             ("any", "count", OI["blue"], "-", "Any-warning"),
             ("any", "energy", OI["blue"], (0, (3, 1.3)), "Any-warning, MWh-wtd")]
    for rule, weight, c, ls, lbl in specs:
        wcol, lcol = D._cols(rule, 72)
        s = sub[sub[wcol]]
        v = s[lcol].values
        w = np.ones(len(s)) if weight == "count" else s["E_mwh"].values
        o = np.argsort(v)
        v, w = v[o], w[o]
        if w.sum() <= 0:
            continue
        y = np.cumsum(w) / w.sum()
        ax.step(np.concatenate([[0.01], v]), np.concatenate([[0.0], y]),
                where="post", color=c, ls=ls, label=lbl,
                lw=1.1 if weight == "count" else 0.95)

    for t, lbl in ((1, r"$T_{act}$ 1 h"), (6, "6 h"), (24, "24 h")):
        ax.axvline(t, color=OI["grey"], lw=0.6, ymax=0.925,
                   ls="-" if t == 6 else (0, (1.2, 1.6)))
        ax.text(t, 0.945, lbl, ha="center", va="bottom", fontsize=6.2,
                color=OI["black"] if t == 6 else OI["grey"],
                fontweight="bold" if t == 6 else "normal")

    ax.set_xscale("log")
    ax.set_xlim(0.01, 72)
    ax.set_ylim(0, 1.02)
    ax.set_xticks([0.01, 0.1, 1, 6, 24, 72])
    ax.set_xticklabels(["0.01", "0.1", "1", "6", "24", "72"])
    ax.set_xlabel("Warning lead time before outage start (h)")
    # two lines: at 8 pt a single-line version is longer than the axes is tall and
    # overruns the tight bounding box
    ax.set_ylabel("Cumulative share\nof warned events", linespacing=1.25)
    ax.grid(axis="y", color=OI["grey"], alpha=0.25)
    ax.legend(loc="upper left", handlelength=1.7, borderpad=0.2,
              labelspacing=0.25)
    fig.tight_layout()
    return save(fig, "fig2.pdf")


# --------------------------------------------------------------------- fig 3
def fig3(att, full):
    """Warned share, events vs matched -45 d controls, by outage-duration bucket."""
    EDGES = [0, 1 / 6, 1, 6, 24, np.inf]
    LBL = ["<10 min", "10 min-1 h", "1-6 h", "6-24 h", "≥24 h"]

    m = full["T2_wide_grid"].values
    sub, csub = att[m].reset_index(drop=True), full[m].reset_index(drop=True)
    b = np.digitize(sub["duration_h"].values, EDGES[1:-1], right=False)

    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 3.3), sharex=True,
                             gridspec_kw={"hspace": 0.16})
    for ax, rule, title in zip(axes, ("any", "same"),
                               ("Any-warning", "Same-component")):
        ev_p, ct_p, ns = [], [], []
        wcol, _ = D._cols(rule, 72)
        cwcol, _ = D._cols(rule, 72, prefix="c45_")
        for k in range(len(LBL)):
            sel = b == k
            mm = sel & csub["c45_matched"].values
            ev_p.append(100 * sub.loc[sel, wcol].mean() if sel.any() else np.nan)
            ct_p.append(100 * csub.loc[mm, cwcol].mean() if mm.any() else np.nan)
            ns.append(int(sel.sum()))
        x = np.arange(len(LBL))
        ax.bar(x - 0.19, ev_p, 0.36, color=OI["vermil"], label="Forced outages")
        ax.bar(x + 0.19, ct_p, 0.36, color=OI["skyblue"],
               label="Quiet controls (−45 d)")
        for xi, (e, c) in enumerate(zip(ev_p, ct_p)):
            if np.isfinite(e) and np.isfinite(c) and c > 0:
                ax.text(xi, max(e, c) + 3.5, f"{e/c:.0f}×", ha="center",
                        va="bottom", fontsize=6.2, color=OI["black"])
        ax.set_ylim(0, 108)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_ylabel("Warned (%)")
        ax.grid(axis="y", color=OI["grey"], alpha=0.25)
        ax.set_axisbelow(True)
        ax.text(0.985, 0.93, title, transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, fontweight="bold")
    axes[0].legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
                   handlelength=1.1, handleheight=0.85, columnspacing=1.0,
                   handletextpad=0.4)
    axes[1].set_xticks(np.arange(len(LBL)))
    axes[1].set_xticklabels([f"{l}\n(n={n:,})" for l, n in zip(LBL, ns)], fontsize=6.4)
    axes[1].set_xlabel("Outage duration")
    fig.tight_layout()
    return save(fig, "fig3.pdf")


# --------------------------------------------------------------------- fig 4
def fig4(att, full):
    """Per-event lost energy vs lead time, log-log, coloured by component family."""
    m = full["T2_wide_grid"].values
    sub = att[m]
    wcol, lcol = D._cols("same", 72)
    s = sub[sub[wcol] & (sub["E_mwh"] > 0)].copy()

    top = (s.groupby("family")["E_mwh"].sum().sort_values(ascending=False)
           .head(6).index.tolist())
    pal = [OI["vermil"], OI["blue"], OI["green"], OI["orange"],
           OI["purple"], OI["skyblue"]]
    cmap = dict(zip(top, pal))

    fig, ax = plt.subplots(figsize=(COL_W, 2.5))
    # NOT clipped to a floor: leads run down to a few seconds and piling them onto
    # one x value would manufacture a vertical stripe that is an artefact of the
    # clip, not of the data. The axis is extended instead.
    other = s[~s["family"].isin(top)]
    ax.scatter(other[lcol], other["E_mwh"], s=5,
               facecolor="none", edgecolor=OI["grey"], linewidths=0.35,
               alpha=0.55, label="other", zorder=2)
    for fam in top:
        g = s[s["family"] == fam]
        ax.scatter(g[lcol], g["E_mwh"], s=8,
                   facecolor=cmap[fam], edgecolor="none", alpha=0.78,
                   label=fam, zorder=3)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(3e-4, 110)
    ax.set_ylim(bottom=max(s["E_mwh"].min() * 0.6, 1e-5))
    ax.axvline(6, color=OI["black"], lw=0.8, ls=(0, (3, 1.4)), zorder=1)
    ax.text(5.2, ax.get_ylim()[1] * 0.72, "$T_{act}$ = 6 h", fontsize=6.4,
            ha="right", va="top")
    ax.set_xticks([0.001, 0.01, 0.1, 1, 6, 24, 72])
    ax.set_xticklabels(["0.001", "0.01", "0.1", "1", "6", "24", "72"])
    ax.set_xlabel("Same-component warning lead time (h)")
    ax.set_ylabel("Event lost energy (MWh)")
    ax.grid(color=OI["grey"], alpha=0.2, which="major")
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4,
              handlelength=0.9, columnspacing=0.8, handletextpad=0.25,
              markerscale=1.4, fontsize=6.2)
    fig.tight_layout()
    return save(fig, "fig4.pdf")


def main():
    style()
    dec = pd.read_csv(D.DECOMP_CSV)
    boot = pd.read_csv(os.path.join(C.SUMMARY_OUT, "bootstrap.csv"))
    att, full = D.load()
    fig1(dec, boot)
    fig2(att, full)
    fig3(att, full)
    fig4(att, full)


if __name__ == "__main__":
    main()
