#!/usr/bin/env python3
"""STUDY_DESIGN v1.3(c) - warning dynamics in the 72 h before failure.

attribution.parquet keeps only the EARLIEST matching warning per event, which is
all the lead-time statistic needs but throws away the shape of the run-up. This
script goes back to warnings.parquet and counts every matching row, reproducing
the frozen attribution window exactly: half-open [start - 72 h, start), warnings
placed by their START timestamp, same-component matching against the event's own
`families_all` with external/grid/manual never matching (attribute.py (a), (b)).
The join is verified against attribution.parquet's `any_n_72h` / `same_n_72h`
before anything is computed from it.

Two questions:

  1. Does the warning rate rise as the outage approaches, or is it flat? Pooled
     hourly profile of warnings per anchor-hour, for warned events and for their
     own matched -45 d controls (and, as context, for the whole T2 population and
     all its controls).
  2. Does an individual event show acceleration? Per-event rate ratio
     (rate in the last 24 h / rate in the prior 48 h) and the Laplace trend
     statistic, among warned events carrying at least 3 matching warning rows.

Writes:
    analysis/dynamics_profile.csv
    analysis/dynamics_trend.csv
    paper/figures/fig7.pdf

    python3 warning_dynamics.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import common as C
import figures as F
import matplotlib.pyplot as plt

LOOKBACK = 72
TIER_FLAG = "T2_wide_grid"
NEVER_MATCH = frozenset({"external", "grid", "manual"})
MIN_ROWS_FOR_TREND = 3
LAST_H, PRIOR_H = 24, 72          # last 24 h vs the prior 48 h ([24, 72))

PROFILE_CSV = os.path.join(C.SUMMARY_OUT, "dynamics_profile.csv")
TREND_CSV = os.path.join(C.SUMMARY_OUT, "dynamics_trend.csv")
NS_PER_H = 3.6e12


# ------------------------------------------------------------------- the join
class WarnIndex:
    """Per-turbine sorted warning starts, for half-open window slicing."""

    def __init__(self, wn):
        wn = wn.sort_values("start")
        self.by = {}
        for k, g in wn.groupby(["farm", "turbine_id"]):
            self.by[k] = (g["start"].values.astype("datetime64[ns]").astype("int64"),
                          g["family"].values)

    def hours_before(self, farm, tid, anchor, famset, rule):
        """Hours before `anchor` of every matching warning in [anchor-72h, anchor)."""
        a = self.by.get((farm, tid))
        if a is None or pd.isna(anchor):
            return np.empty(0)
        ns, fam = a
        a_ns = np.datetime64(anchor, "ns").astype("int64")
        lo = a_ns - int(LOOKBACK * 3600 * 1e9)
        s = np.searchsorted(ns, lo, "left")
        e = np.searchsorted(ns, a_ns, "left")
        if s == e:
            return np.empty(0)
        sub_ns, sub_fam = ns[s:e], fam[s:e]
        if rule == "same":
            keep = np.array([(f in famset) and (f not in NEVER_MATCH)
                             for f in sub_fam], dtype=bool)
            sub_ns = sub_ns[keep]
        return (a_ns - sub_ns) / NS_PER_H


def verify_join(idx, s):
    """The reconstructed counts must equal attribution.parquet's frozen columns."""
    for rule in ("same", "any"):
        got = np.array([len(idx.hours_before(f, t, a, frozenset(fs), rule))
                        for f, t, a, fs in zip(s.farm, s.turbine_id, s.start,
                                               s.families_all)])
        want = s[f"{rule}_n_{LOOKBACK}h"].values
        ok = bool((got == want).all())
        print(f"  JOIN CHECK {rule}_n_{LOOKBACK}h reproduced: "
              f"{'OK' if ok else 'FAIL'} ({got.sum():,} rows)")
        assert ok, "warning join does not reproduce attribution.parquet"


# ------------------------------------------------------------------- profiles
def profile(idx, anchors, rule):
    """(hourly warning counts, n_anchors) over the 72 h window."""
    bins = np.zeros(LOOKBACK, dtype=np.int64)
    for f, t, a, fs in anchors:
        hb = idx.hours_before(f, t, a, fs, rule)
        if len(hb):
            k = np.floor(hb).astype(int)
            k = k[(k >= 0) & (k < LOOKBACK)]
            np.add.at(bins, k, 1)
    return bins, len(anchors)


def build_profiles(idx, s, ctl):
    rows = []
    for rule in ("same", "any"):
        wcol = f"{rule}_warn_{LOOKBACK}h"
        cwcol = f"c45_{rule}_warn_{LOOKBACK}h"
        warned = s[wcol].values
        matched = ctl["c45_matched"].values

        pops = {
            "events_warned": [(f, t, a, frozenset(fs)) for f, t, a, fs in
                              zip(s.farm[warned], s.turbine_id[warned],
                                  s.start[warned], s.families_all[warned])],
            "controls_of_warned": [(f, t, a, frozenset(fs)) for f, t, a, fs in
                                   zip(s.farm[warned & matched],
                                       s.turbine_id[warned & matched],
                                       ctl.c45_ts.values[warned & matched],
                                       s.families_all[warned & matched])],
            "events_all": [(f, t, a, frozenset(fs)) for f, t, a, fs in
                           zip(s.farm, s.turbine_id, s.start, s.families_all)],
            "controls_all": [(f, t, a, frozenset(fs)) for f, t, a, fs in
                             zip(s.farm[matched], s.turbine_id[matched],
                                 ctl.c45_ts.values[matched],
                                 s.families_all[matched])],
        }
        for pop, anchors in pops.items():
            bins, n = profile(idx, anchors, rule)
            for k in range(LOOKBACK):
                rows.append(dict(population=pop, rule=rule,
                                 hours_before_lo=k, hours_before_hi=k + 1,
                                 n_warnings=int(bins[k]), n_anchors=n,
                                 rate_per_anchor_hour=float(bins[k] / n) if n else np.nan))
            print(f"  {rule:>4} {pop:<19} n_anchors {n:>5,}  "
                  f"warnings {bins.sum():>7,}  "
                  f"mean rate {bins.sum()/(n*LOOKBACK):.4f}/anchor-h")
        # cross-check against the frozen column
        want = int(s.loc[warned, f"{rule}_n_{LOOKBACK}h"].sum())
        got = int(sum(r["n_warnings"] for r in rows
                      if r["rule"] == rule and r["population"] == "events_warned"))
        print(f"  SANITY {rule} events_warned total {got:,} vs frozen "
              f"{want:,}  {'OK' if got == want else 'FAIL'}")
        assert got == want
    out = pd.DataFrame(rows)
    out.to_csv(PROFILE_CSV, index=False)
    print(f"wrote {PROFILE_CSV}: {len(out):,} rows")
    return out


# ---------------------------------------------------------------- trend stats
def weighted_median_with_inf(v, w):
    """Weighted median that keeps +inf (a zero prior-window rate) in the order."""
    v = np.asarray(v, dtype=float)
    w = np.asarray(w, dtype=float)
    o = np.argsort(v, kind="stable")
    v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(cw, 0.5, "left")])


def build_trend(idx, s):
    rows = []
    for rule in ("same", "any"):
        wcol = f"{rule}_warn_{LOOKBACK}h"
        sub = s[s[wcol].values & (s[f"{rule}_n_{LOOKBACK}h"].values
                                  >= MIN_ROWS_FOR_TREND)]
        rr, lap, E = [], [], sub["E_mwh"].values.astype(float)
        for f, t, a, fs in zip(sub.farm, sub.turbine_id, sub.start,
                               sub.families_all):
            hb = idx.hours_before(f, t, a, frozenset(fs), rule)
            n_last = int((hb < LAST_H).sum())
            n_prior = int(((hb >= LAST_H) & (hb < PRIOR_H)).sum())
            rr.append(np.inf if n_prior == 0
                      else (n_last / LAST_H) / (n_prior / (PRIOR_H - LAST_H)))
            # Laplace trend on time measured FORWARD from the window start
            tt = LOOKBACK - hb
            N = len(tt)
            lap.append((tt.mean() - LOOKBACK / 2.0)
                       / (LOOKBACK / np.sqrt(12.0 * N)))
        rr, lap = np.asarray(rr, dtype=float), np.asarray(lap, dtype=float)
        tot = E.sum()

        def sh(m):
            return float(m.mean()), float(E[m].sum() / tot)

        f_gt1_n, f_gt1_e = sh(rr > 1)
        f_ge2_n, f_ge2_e = sh(rr >= 2)
        f_lap_n, f_lap_e = sh(lap > 0)
        f_lap95_n, f_lap95_e = sh(lap > 1.645)
        rows.append(dict(
            rule=rule, min_warning_rows=MIN_ROWS_FOR_TREND,
            n_events=len(sub), E_mwh=float(tot),
            n_prior48_zero=int(np.isinf(rr).sum()),
            frac_rr_gt1_count=f_gt1_n, frac_rr_gt1_energy=f_gt1_e,
            frac_rr_ge2_count=f_ge2_n, frac_rr_ge2_energy=f_ge2_e,
            median_rr_count=float(np.median(rr)),
            median_rr_energy=weighted_median_with_inf(rr, E),
            frac_laplace_gt0_count=f_lap_n, frac_laplace_gt0_energy=f_lap_e,
            frac_laplace_gt1645_count=f_lap95_n, frac_laplace_gt1645_energy=f_lap95_e,
            median_laplace_count=float(np.median(lap)),
            median_laplace_energy=weighted_median_with_inf(lap, E),
        ))
    out = pd.DataFrame(rows)
    out.to_csv(TREND_CSV, index=False)
    print(f"wrote {TREND_CSV}: {len(out):,} rows")
    return out


# ------------------------------------------------------------------ figure 7
def fig7(prof):
    F.style()
    OI = F.OI
    fig, ax = plt.subplots(figsize=(F.COL_W, 2.5))
    x = prof.hours_before_lo.unique() + 0.5

    specs = [("same", "events_warned", OI["vermil"], "-", "Same-component, events"),
             ("same", "controls_of_warned", OI["vermil"], (0, (3, 1.3)),
              "Same-component, controls"),
             ("any", "events_warned", OI["blue"], "-", "Any-warning, events"),
             ("any", "controls_of_warned", OI["blue"], (0, (3, 1.3)),
              "Any-warning, controls")]
    for rule, pop, c, ls, lbl in specs:
        g = prof[(prof.rule == rule) & (prof.population == pop)].sort_values(
            "hours_before_lo")
        ax.step(x, g.rate_per_anchor_hour.values, where="mid", color=c, ls=ls,
                lw=1.0, label=lbl)

    ax.set_yscale("log")
    ax.set_ylim(2e-4, 6)
    cs = prof[(prof.rule == "same") & (prof.population == "controls_of_warned")]
    ax.text(0.02, 0.97,
            "control traces break at hours with no warnings;\nsame-component "
            f"controls carry {int(cs.n_warnings.sum())} rows across "
            f"{int(cs.n_anchors.iloc[0]):,} windows",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.7,
            color=OI["grey"], linespacing=1.3)
    ax.set_xlim(LOOKBACK, 0)                      # time runs toward the outage
    ax.set_xticks([72, 48, 24, 6, 0])
    ax.set_xticklabels(["72", "48", "24", "6", "0"])
    ax.axvline(6, color=OI["black"], lw=0.6, ls=(0, (1.2, 1.6)), zorder=1)
    ax.set_xlabel("Hours before outage start (0 = outage)")
    ax.set_ylabel("Warnings per anchor-hour", linespacing=1.25)
    ax.grid(color=OI["grey"], alpha=0.22)
    ax.set_axisbelow(True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              handlelength=1.6, columnspacing=0.9, handletextpad=0.4, fontsize=6.2)
    fig.tight_layout()
    return F.save(fig, "fig7.pdf")


def main():
    att = pd.read_parquet(os.path.join(C.DERIVED, "attribution.parquet"))
    ctl = pd.read_parquet(os.path.join(C.DERIVED, "controls.parquet"))
    assert (att["event_id"].values == ctl["event_id"].values).all()
    m = att[TIER_FLAG].values
    s = att[m].reset_index(drop=True)
    ctl = ctl[m].reset_index(drop=True)
    assert len(s) == 4213 and abs(s["E_mwh"].sum() - 9386.5) < 0.05
    print(f"T2 wide-grid: {len(s):,} events / {s['E_mwh'].sum():,.1f} MWh; "
          f"matched -45 d controls {int(ctl['c45_matched'].sum()):,}")

    wn = pd.read_parquet(os.path.join(C.DERIVED, "warnings.parquet"))
    idx = WarnIndex(wn)
    verify_join(idx, s)

    prof = build_profiles(idx, s, ctl)
    trend = build_trend(idx, s)
    fig7(prof)

    print("\n=== warning rate, first vs last 6 h of the window "
          "(warnings per anchor-hour) ===")
    for rule in ("same", "any"):
        for pop in ("events_warned", "controls_of_warned"):
            g = prof[(prof.rule == rule) & (prof.population == pop)]
            far = g[g.hours_before_lo >= 66].rate_per_anchor_hour.mean()
            near = g[g.hours_before_lo < 6].rate_per_anchor_hour.mean()
            print(f"  {rule:>4} {pop:<19} 72-66 h {far:.4f}  0-6 h {near:.4f}  "
                  f"ratio {near/far if far else np.nan:.2f}x")
    print("\n=== per-event trend (>=3 matching warning rows) ===")
    print(trend.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))


if __name__ == "__main__":
    main()
