#!/usr/bin/env python3
"""decomposition.csv - the three-way split of forced-outage lost energy.

STUDY_DESIGN.md "Decomposition":

  1. UNWARNED             no same-component warning in the lookback window
  2. SHORT-LEAD           warned, lead <  T_act   (warning too late to act)
  3. ACTIONABLE-UNACTED   warned, lead >= T_act   <- the headline share

T_act primary 6 h, sensitivity {1 h, 24 h}. Lookback primary 72 h, sensitivity
{24 h, 48 h}. Matching rule primary same-component, upper bound any-warning.

Tier naming follows STUDY_DESIGN v1.1(b): the WIDE grid rule (every
`External stop (grid)` service-category message, incl. `Maximum grid frequency`)
is the PRIMARY T1/T2 definition; stage 1 stored it as `T1_wide_grid` /
`T2_wide_grid`. The narrow frozen-list variant (`T1` / `T2`) is retained as a
labelled sensitivity. Nothing in stage 1 is recomputed - only re-tiered.

Control adjustment (STUDY_DESIGN "Control adjustment"):

    excess = (p_event - p_control) / (1 - p_control)

reported for the warned share and for the actionable-unacted share, energy-weighted
and count-weighted. p_control is computed over the SAME events (each control carries
its event's lost energy as weight), so the two rates are matched by construction.

Writes:
    analysis/decomposition.csv          the full tidy grid (headline + sensitivities
                                        + per-farm + manual-stop line)
    analysis/leadtime_stats.csv         lead-time distribution summaries
    analysis/duration_comparison.csv    warned vs unwarned outage duration

    python3 decompose.py
"""
import os

import numpy as np
import pandas as pd
from scipy import stats

import attribute as A
import common as C
import controls as K

T_ACT_H = (1, 6, 24)
T_ACT_PRIMARY = 6
LOOKBACKS = A.LOOKBACKS_H
LOOKBACK_PRIMARY = A.PRIMARY_LOOKBACK_H
RULES = ("same", "any")
RULE_PRIMARY = "same"

# STUDY_DESIGN v1.1(b): wide-grid is primary; the narrow frozen list is the sensitivity.
TIERS = {
    "T0":          ("T0",           "primary"),
    "T1":          ("T1_wide_grid", "primary"),
    "T2":          ("T2_wide_grid", "primary"),
    "T1_narrow":   ("T1",           "sensitivity"),
    "T2_narrow":   ("T2",           "sensitivity"),
}
TIER_PRIMARY = "T2"

DECOMP_CSV = os.path.join(C.SUMMARY_OUT, "decomposition.csv")

# PROFILE §6, quoted verbatim, NOT recomputed (STUDY_DESIGN: naive SCADA is a
# secondary negative result reported from the smoke test).
NAIVE_SCADA_LINE = (
    "Naive SCADA precursor (negative control, PROFILE §6, not recomputed): "
    "temperature-residual max|z| > 3 in the 72 h before a forced outage fires for "
    "4/20 (20%) random forced outages and 3/19 (16%) component-fault outages, "
    "against 6/31 (19%) of matched quiet controls; median z 2.38 / 2.09 vs 2.18. "
    "The power-curve residual fires 0/34 events vs 1/29 controls. Indistinguishable "
    "from control - hence the status log, not a naive SCADA score, is the instrument."
)


# ------------------------------------------------------------------ primitives
def split(warned, lead, t_act, w):
    """Energy- (or count-) weighted three-way split. `w` is the weight vector."""
    tot = float(w.sum())
    if tot <= 0:
        return dict(unwarned=np.nan, short_lead=np.nan, actionable_unacted=np.nan,
                    warned=np.nan, total=0.0)
    warned = np.asarray(warned, dtype=bool)
    lead = np.asarray(lead, dtype=float)
    act = warned & (lead >= t_act)
    shortl = warned & (lead < t_act)
    return dict(
        unwarned=float(w[~warned].sum()) / tot,
        short_lead=float(w[shortl].sum()) / tot,
        actionable_unacted=float(w[act].sum()) / tot,
        warned=float(w[warned].sum()) / tot,
        total=tot,
    )


def weighted_quantiles(v, w, qs):
    """Weighted quantiles of `v` (the count-weighted case reduces to the usual
    linear-interpolation quantile up to the half-weight offset)."""
    v = np.asarray(v, dtype=float)
    w = np.asarray(w, dtype=float)
    ok = np.isfinite(v) & (w > 0)
    if not ok.any():
        return [np.nan] * len(qs)
    v, w = v[ok], w[ok]
    o = np.argsort(v)
    v, w = v[o], w[o]
    cw = (np.cumsum(w) - 0.5 * w) / w.sum()
    return [float(np.interp(q, cw, v)) for q in qs]


def excess(p_event, p_control):
    """(p_e - p_c) / (1 - p_c), the control-excess attributable share."""
    if not np.isfinite(p_event) or not np.isfinite(p_control) or p_control >= 1:
        return np.nan
    return (p_event - p_control) / (1.0 - p_control)


def _cols(rule, L, prefix=""):
    return f"{prefix}{rule}_warn_{L}h", f"{prefix}{rule}_lead_h_{L}h"


def decompose_one(df, ctrl, rule, L, t_act, weight, ctrl_tag):
    """One row of the tidy grid, for an already-subset population."""
    wcol, lcol = _cols(rule, L)
    cwcol, clcol = _cols(rule, L, prefix=f"{ctrl_tag}_")
    w = df["E_mwh"].values if weight == "energy" else np.ones(len(df))

    ev_s = split(df[wcol].values, df[lcol].values, t_act, w)

    # controls: only events whose control matched; weights are the EVENT's,
    # so the event and control rates are directly comparable.
    m = ctrl[f"{ctrl_tag}_matched"].values
    cw = (ctrl.loc[m, "E_mwh"].values if weight == "energy"
          else np.ones(int(m.sum())))
    c_s = split(ctrl.loc[m, cwcol].values, ctrl.loc[m, clcol].values, t_act, cw)

    return {
        "rule": rule, "lookback_h": L, "T_act_h": t_act, "weight": weight,
        "control_offset_d": int(ctrl_tag[1:]),
        "n_events": len(df), "E_mwh": float(df["E_mwh"].sum()),
        "unwarned": ev_s["unwarned"],
        "short_lead": ev_s["short_lead"],
        "actionable_unacted": ev_s["actionable_unacted"],
        "warned": ev_s["warned"],
        "n_controls_matched": int(m.sum()),
        "p_control_warned": c_s["warned"],
        "p_control_actionable": c_s["actionable_unacted"],
        "excess_warned": excess(ev_s["warned"], c_s["warned"]),
        "excess_actionable": excess(ev_s["actionable_unacted"],
                                    c_s["actionable_unacted"]),
        "enrichment_warned_x": (ev_s["warned"] / c_s["warned"]
                                if c_s["warned"] > 0 else np.nan),
    }


# ------------------------------------------------------------------------ main
def load():
    att = pd.read_parquet(A.ATTRIBUTION_PARQUET)
    ctl = pd.read_parquet(K.CONTROLS_PARQUET)
    assert (att["event_id"].values == ctl["event_id"].values).all(), \
        "attribution / controls row order diverged"
    # controls.parquet duplicates the tier flags; keep attribution's copy only
    ctl = ctl.drop(columns=[c for c in ctl.columns
                            if c in att.columns and c != "event_id"])
    return att, att.join(ctl.drop(columns=["event_id"]))


def main():
    att, full = load()
    rows = []

    def add(pop, tier, variant, **kw):
        rows.append(dict(population=pop, tier=tier, tier_variant=variant, **kw))

    # ---- the full sensitivity grid, all tiers -------------------------------
    for tier, (flag, variant) in TIERS.items():
        mask = full[flag].values
        sub, csub = att[mask], full[mask]
        for ctag in ("c45", "c30", "c60"):
            for rule in RULES:
                for L in LOOKBACKS:
                    for t in T_ACT_H:
                        for weight in ("energy", "count"):
                            # keep the grid finite: vary one axis off-primary at a time
                            n_off = ((ctag != "c45") + (rule != RULE_PRIMARY)
                                     + (L != LOOKBACK_PRIMARY) + (t != T_ACT_PRIMARY))
                            if n_off > 1:
                                continue
                            r = decompose_one(sub, csub, rule, L, t, weight, ctag)
                            add("all", tier, variant, sub_pop="all", **r)

    # ---- per-farm split, primary cell only ----------------------------------
    for tier in ("T0", "T1", "T2"):
        flag = TIERS[tier][0]
        for farm in ("kelmarsh", "penmanshiel"):
            m = full[flag].values & (full["farm"] == farm).values
            for weight in ("energy", "count"):
                r = decompose_one(att[m], full[m], RULE_PRIMARY, LOOKBACK_PRIMARY,
                                  T_ACT_PRIMARY, weight, "c45")
                add("per_farm", tier, TIERS[tier][1], sub_pop=farm, **r)

    # ---- manual-stop line, reported separately (STUDY_DESIGN T2 rule) -------
    # Both rules are reported here: a manual-only event's every constituent message
    # is in the `manual` family, which NEVER matches, so its same-component warned
    # share is 0 by construction. Only the any-warning row is informative.
    m = full["is_manual_only"].values
    for rule in RULES:
        for weight in ("energy", "count"):
            r = decompose_one(att[m], full[m], rule, LOOKBACK_PRIMARY,
                              T_ACT_PRIMARY, weight, "c45")
            add("manual_only", "manual", "reported_separately",
                sub_pop="manual_only", **r)

    # ---- per-component-family split of the primary cell ---------------------
    flag = TIERS[TIER_PRIMARY][0]
    for fam, g in att[full[flag].values].groupby("family"):
        cg = full[full[flag].values]
        cg = cg[cg["family"] == fam]
        for weight in ("energy", "count"):
            r = decompose_one(g, cg, RULE_PRIMARY, LOOKBACK_PRIMARY,
                              T_ACT_PRIMARY, weight, "c45")
            add("per_family", TIER_PRIMARY, "primary", sub_pop=fam, **r)

    dec = pd.DataFrame(rows)
    dec.to_csv(DECOMP_CSV, index=False)
    print(f"wrote {DECOMP_CSV}: {len(dec):,} rows")

    # ---- sanity: shares sum to 1 -------------------------------------------
    s = (dec["unwarned"] + dec["short_lead"] + dec["actionable_unacted"])
    bad = dec[((s - 1).abs() > 1e-9) & s.notna()]
    worst = float(np.nanmax(np.abs(s - 1)))
    print(f"SANITY shares sum to 1: max |sum-1| = {worst:.2e} "
          f"({'OK' if worst < 1e-9 else 'FAIL'}), {len(bad)} bad rows")
    s2 = (dec["short_lead"] + dec["actionable_unacted"] - dec["warned"]).abs()
    print(f"SANITY warned == short+actionable: max dev = {np.nanmax(s2):.2e}")

    # ---- lead-time descriptives --------------------------------------------
    lead_rows = []
    for tier in ("T0", "T1", "T2"):
        flag = TIERS[tier][0]
        sub = att[full[flag].values]
        for rule in RULES:
            wcol, lcol = _cols(rule, LOOKBACK_PRIMARY)
            wsub = sub[sub[wcol]]
            v = wsub[lcol].values
            for weight in ("count", "energy"):
                # every statistic below is taken under the SAME weight, so the
                # "energy" row answers "per MWh of warned lost energy, what lead?"
                ww = (np.ones(len(wsub)) if weight == "count"
                      else wsub["E_mwh"].values)
                q = weighted_quantiles(v, ww, (.25, .5, .75))
                tot = ww.sum()
                lead_rows.append({
                    "tier": tier, "rule": rule, "weight": weight,
                    "n_warned": len(wsub), "E_warned_mwh": float(wsub["E_mwh"].sum()),
                    "lead_p25_h": q[0], "lead_median_h": q[1], "lead_p75_h": q[2],
                    "lead_mean_h": (float(np.average(v, weights=ww))
                                    if tot > 0 else np.nan),
                    "frac_ge_1h": float(ww[v >= 1].sum() / tot) if tot > 0 else np.nan,
                    "frac_ge_6h": float(ww[v >= 6].sum() / tot) if tot > 0 else np.nan,
                    "frac_ge_24h": float(ww[v >= 24].sum() / tot) if tot > 0 else np.nan,
                })
    lead = pd.DataFrame(lead_rows)
    lead.to_csv(os.path.join(C.SUMMARY_OUT, "leadtime_stats.csv"), index=False)

    # ---- warned vs unwarned duration ---------------------------------------
    dur_rows = []
    for tier in ("T0", "T1", "T2"):
        flag = TIERS[tier][0]
        sub = att[full[flag].values]
        for rule in RULES:
            wcol, _ = _cols(rule, LOOKBACK_PRIMARY)
            a = sub.loc[sub[wcol], "duration_h"].values
            b = sub.loc[~sub[wcol], "duration_h"].values
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            dur_rows.append({
                "tier": tier, "rule": rule,
                "n_warned": len(a), "n_unwarned": len(b),
                "med_dur_warned_h": float(np.median(a)),
                "med_dur_unwarned_h": float(np.median(b)),
                "p25_warned_h": float(np.percentile(a, 25)),
                "p75_warned_h": float(np.percentile(a, 75)),
                "p25_unwarned_h": float(np.percentile(b, 25)),
                "p75_unwarned_h": float(np.percentile(b, 75)),
                "mean_E_warned_mwh": float(sub.loc[sub[wcol], "E_mwh"].mean()),
                "mean_E_unwarned_mwh": float(sub.loc[~sub[wcol], "E_mwh"].mean()),
                "mannwhitney_u": float(u), "mannwhitney_p": float(p),
            })
    durc = pd.DataFrame(dur_rows)
    durc.to_csv(os.path.join(C.SUMMARY_OUT, "duration_comparison.csv"), index=False)

    # ---- console headline ---------------------------------------------------
    h = dec[(dec.population == "all") & (dec.tier == TIER_PRIMARY)
            & (dec.rule == RULE_PRIMARY) & (dec.lookback_h == LOOKBACK_PRIMARY)
            & (dec.T_act_h == T_ACT_PRIMARY) & (dec.control_offset_d == 45)]
    print("\n=== HEADLINE (T2 wide-grid, same-component, 72 h, T_act 6 h) ===")
    print(h[["weight", "n_events", "E_mwh", "unwarned", "short_lead",
             "actionable_unacted", "warned", "p_control_warned",
             "excess_warned", "excess_actionable", "enrichment_warned_x"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    hb = dec[(dec.population == "all") & (dec.tier == TIER_PRIMARY)
             & (dec.rule == "any") & (dec.lookback_h == LOOKBACK_PRIMARY)
             & (dec.T_act_h == T_ACT_PRIMARY) & (dec.control_offset_d == 45)]
    print("\n=== UPPER BOUND (same cell, any-warning) ===")
    print(hb[["weight", "unwarned", "short_lead", "actionable_unacted", "warned",
              "p_control_warned", "excess_warned", "excess_actionable",
              "enrichment_warned_x"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("\n=== lead times (72 h window) ===")
    print(lead.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\n=== warned vs unwarned duration ===")
    print(durc.to_string(index=False, float_format=lambda x: f"{x:,.3g}"))
    print("\n" + NAIVE_SCADA_LINE)
    return dec


if __name__ == "__main__":
    main()
