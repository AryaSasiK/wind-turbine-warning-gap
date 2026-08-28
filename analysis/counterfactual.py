#!/usr/bin/env python3
"""counterfactual.csv - modelled recoverable energy (SECONDARY, clearly labelled).

STUDY_DESIGN.md "Counterfactual value":

    For actionable-unacted events: recoverable energy if the warning had triggered a
    planned intervention = E_event - E_planned, where E_planned uses the corpus's own
    `Scheduled Maintenance` stop durations (median, and 75th pct as conservative)
    placed at the event's own wind conditions. Reported in MWh and % of gross
    generation; no monetary conversion.

"Placed at the event's own wind conditions" is implemented as the event's own mean
potential power over its window (`mean_potential_kw`, the same
`Cascading potential power` series whose integral reproduces Greenbyte's downtime
accounting to ratio 1.0004). So

    E_planned = mean_potential_kw * D_planned / 1000      [MWh]
    recoverable = max(E_event - E_planned, 0)

The clip at zero matters: an actionable-unacted event shorter than the planned
intervention would otherwise be credited with NEGATIVE recoverable energy, which is
not a saving - it is a case where intervening costs more downtime than the fault did.
Those events are counted and reported separately rather than silently netted off.

Scheduled-Maintenance durations are taken from the corpus's own status log on the
same footing as the event population (both timestamps present, end >= start,
de-duplicated, post-commissioning).

Gross generation is PROFILE §4's `Energy Export` over 171 turbine-years,
865,526 MWh - a Greenbyte-derived column, quoted, not recomputed here.

    python3 counterfactual.py
"""
import os

import numpy as np
import pandas as pd

import attribute as A
import common as C
import controls as K
import decompose as D

GROSS_MWH = 865_526.0           # PROFILE §4 `Energy Export`, 171 turbine-years
GROSS_SOURCE = "data/PROFILE.md §4 (`Energy Export`, 171 turbine-years)"

CF_CSV = os.path.join(C.SUMMARY_OUT, "counterfactual.csv")
CF_EVENTS_PARQUET = os.path.join(C.DERIVED, "counterfactual_events.parquet")


def scheduled_maintenance_durations():
    """Median and 75th-pct `Scheduled Maintenance` stop duration, in hours.

    Filtered exactly as build_events.py filters the forced-outage population, so
    the planned-intervention duration and the event durations are measured the
    same way.
    """
    st, _ = C.load_status()
    sm = st[(st["Status"] == C.BASE_STATUS)
            & (st["IEC category"] == "Scheduled Maintenance")].copy()
    n_raw = len(sm)
    sm = sm[sm["t0"].notna() & sm["t1"].notna()]
    sm = sm[sm["t1"] >= sm["t0"]]
    sm = sm[~sm.duplicated(["farm", "turbine_id", "t0", "t1", "Code"], keep="first")]
    sm = sm[~C.pre_cod_mask(sm)]
    d = ((sm["t1"] - sm["t0"]).dt.total_seconds() / 3600.0)
    return {
        "n_raw": n_raw, "n_used": len(sm),
        "median_h": float(d.median()), "p75_h": float(d.quantile(0.75)),
        "mean_h": float(d.mean()), "p90_h": float(d.quantile(0.90)),
        "by_message": sm.groupby("Message").size().to_dict(),
    }


def recoverable(df, d_planned_h):
    """Per-event modelled recoverable energy, MWh."""
    pot = df["mean_potential_kw"].fillna(0.0).clip(lower=0.0).values
    e_planned = pot * d_planned_h / 1000.0
    raw = df["E_mwh"].values - e_planned
    return np.clip(raw, 0.0, None), e_planned, raw


def main():
    smd = scheduled_maintenance_durations()
    print("=== Scheduled Maintenance stop durations (planned-intervention model) ===")
    print(f"  {smd['n_used']:,} stops (of {smd['n_raw']:,} raw), "
          f"median {smd['median_h']:.3f} h, p75 {smd['p75_h']:.3f} h, "
          f"p90 {smd['p90_h']:.3f} h, mean {smd['mean_h']:.3f} h")
    print("  by message:", smd["by_message"])
    print(f"\n  NOTE: the corpus's Scheduled Maintenance stops are overwhelmingly "
          f"short manual\n  visits (median {smd['median_h']*60:.0f} min), so "
          f"E_planned is small next to a\n  multi-day forced outage and the model "
          f"recovers nearly all of E_event.\n  This is a property of the corpus, "
          f"not a tuning choice - see RESULTS.md.")

    att, full = D.load()
    rows = []
    ev_rows = []

    for tier in ("T0", "T1", "T2"):
        flag = D.TIERS[tier][0]
        mask = full[flag].values
        sub = att[mask]
        for rule in D.RULES:
            wcol, lcol = D._cols(rule, D.LOOKBACK_PRIMARY)
            for t_act in D.T_ACT_H:
                act = sub[wcol].values & (sub[lcol].values >= t_act)
                a = sub[act]
                for label, dpl in (("median", smd["median_h"]),
                                   ("p75", smd["p75_h"])):
                    rec, e_pl, raw = recoverable(a, dpl)
                    rows.append({
                        "tier": tier, "tier_variant": D.TIERS[tier][1],
                        "rule": rule, "lookback_h": D.LOOKBACK_PRIMARY,
                        "T_act_h": t_act, "planned_duration": label,
                        "planned_duration_h": dpl,
                        "n_actionable_events": len(a),
                        "E_actionable_mwh": float(a["E_mwh"].sum()),
                        "E_planned_mwh": float(e_pl.sum()),
                        "recoverable_mwh": float(rec.sum()),
                        "recoverable_pct_of_gross": 100 * float(rec.sum()) / GROSS_MWH,
                        "recoverable_pct_of_tier_E": (
                            100 * float(rec.sum()) / float(sub["E_mwh"].sum())),
                        "recoverable_pct_of_actionable_E": (
                            100 * float(rec.sum()) / float(a["E_mwh"].sum())
                            if a["E_mwh"].sum() > 0 else np.nan),
                        "n_events_clipped_at_zero": int((raw < 0).sum()),
                        "mwh_clipped_away": float(np.clip(raw, None, 0).sum()),
                    })
                    if (tier == D.TIER_PRIMARY and rule == D.RULE_PRIMARY
                            and t_act == D.T_ACT_PRIMARY and label == "median"):
                        e = a[["event_id", "farm", "turbine_id", "start",
                               "duration_h", "E_mwh", "family", "primary_message",
                               "mean_potential_kw", "mean_wind_ms"]].copy()
                        e["lead_h"] = a[lcol].values
                        e["E_planned_mwh"] = e_pl
                        e["recoverable_mwh"] = rec
                        ev_rows.append(e)

    cf = pd.DataFrame(rows)
    cf.to_csv(CF_CSV, index=False)
    if ev_rows:
        pd.concat(ev_rows).to_parquet(CF_EVENTS_PARQUET, index=False)
        print(f"\nwrote {CF_EVENTS_PARQUET}")
    print(f"wrote {CF_CSV}: {len(cf):,} rows")

    pd.Series({k: v for k, v in smd.items() if k != "by_message"}).to_csv(
        os.path.join(C.SUMMARY_OUT, "planned_duration.csv"))

    h = cf[(cf.tier == D.TIER_PRIMARY) & (cf.rule == D.RULE_PRIMARY)
           & (cf.T_act_h == D.T_ACT_PRIMARY)]
    print(f"\n=== HEADLINE counterfactual (T2 wide-grid, same-component, "
          f"72 h, T_act 6 h) ===")
    print(h[["planned_duration", "planned_duration_h", "n_actionable_events",
             "E_actionable_mwh", "E_planned_mwh", "recoverable_mwh",
             "recoverable_pct_of_gross", "recoverable_pct_of_tier_E",
             "n_events_clipped_at_zero"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print(f"\ngross generation = {GROSS_MWH:,.0f} MWh  [{GROSS_SOURCE}]")
    print("\n=== full grid ===")
    print(cf[["tier", "rule", "T_act_h", "planned_duration", "n_actionable_events",
              "E_actionable_mwh", "recoverable_mwh", "recoverable_pct_of_gross"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    return cf


if __name__ == "__main__":
    main()
