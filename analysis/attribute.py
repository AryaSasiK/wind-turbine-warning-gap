#!/usr/bin/env python3
"""attribution.parquet - warning attribution for every merged forced-outage event.

STUDY_DESIGN.md "Warning attribution":

  - lookback window 72 h before the merged-event start (sensitivities 24 h, 48 h)
  - ANY-WARNING rule (upper bound): any `Warning` row on the same turbine in window
  - SAME-COMPONENT rule (conservative, headline): the warning's component family is
    one of the families carried by the event's constituent stop messages
  - families `external`, `grid`, `manual` never produce a same-component match

Two readings the spec leaves implicit; both are fixed here and the alternative is
carried as a labelled sensitivity in RESULTS.md:

  (a) The window is half-open, [start - L, start): a warning stamped exactly at the
      stop start is NOT a precursor (lead 0 carries no information and would inflate
      the "short-lead" bucket). This matches `data/smoke_precursors.py`, whose 63.7 %
      / 16.5 % figures the study quotes, so the smoke test stays comparable.
  (b) A warning is placed by its START timestamp only. Warning intervals are often
      open-ended or run into the outage itself; using the end would make a warning
      that is still open at the stop trivially "coincident".

Also fixed: the event's component set is `families_all` (every constituent stop
message's family), not just the family of the longest constituent. The spec says
"families of its constituent stop messages" - plural - and only 3 of 6,050 events
have more than one constituent, so this is nearly a no-op but is the literal rule.

    python3 attribute.py
"""
import os

import numpy as np
import pandas as pd

import common as C

# families that can never produce a same-component match (STUDY_DESIGN)
NEVER_MATCH = frozenset({"external", "grid", "manual"})
LOOKBACKS_H = (24, 48, 72)
PRIMARY_LOOKBACK_H = 72

ATTRIBUTION_PARQUET = os.path.join(C.DERIVED, "attribution.parquet")


def _searchsorted_window(w_start_ns, lo_ns, hi_ns):
    """Half-open [lo, hi) index range into a sorted array of warning starts."""
    a = np.searchsorted(w_start_ns, lo_ns, side="left")
    b = np.searchsorted(w_start_ns, hi_ns, side="left")
    return a, b


def attribute(anchors, warns, lookbacks_h=LOOKBACKS_H, prefix=""):
    """Warning attribution at a set of anchor timestamps.

    `anchors` needs columns: farm, turbine_id, anchor (timestamp), fam_set
    (a python set/list/frozenset of component families for that anchor).
    `warns` needs: farm, turbine_id, start, family, message, code.

    Returns a frame aligned to anchors.index with, for each lookback L:
        {prefix}any_warn_{L}h        bool   - any Warning row in [anchor-L, anchor)
        {prefix}any_n_{L}h           int    - how many
        {prefix}any_lead_h_{L}h      float  - anchor - earliest such warning, hours
        {prefix}any_first_msg_{L}h   str
        {prefix}any_first_fam_{L}h   str
        {prefix}same_warn_{L}h       bool   - ...whose family is in fam_set and is
                                              not one of external/grid/manual
        {prefix}same_n_{L}h          int
        {prefix}same_lead_h_{L}h     float
        {prefix}same_first_msg_{L}h  str
        {prefix}same_first_fam_{L}h  str
    """
    cols = {}
    for L in lookbacks_h:
        cols[f"{prefix}any_warn_{L}h"] = np.zeros(len(anchors), dtype=bool)
        cols[f"{prefix}any_n_{L}h"] = np.zeros(len(anchors), dtype=np.int32)
        cols[f"{prefix}any_lead_h_{L}h"] = np.full(len(anchors), np.nan)
        cols[f"{prefix}any_first_msg_{L}h"] = np.full(len(anchors), None, dtype=object)
        cols[f"{prefix}any_first_fam_{L}h"] = np.full(len(anchors), None, dtype=object)
        cols[f"{prefix}same_warn_{L}h"] = np.zeros(len(anchors), dtype=bool)
        cols[f"{prefix}same_n_{L}h"] = np.zeros(len(anchors), dtype=np.int32)
        cols[f"{prefix}same_lead_h_{L}h"] = np.full(len(anchors), np.nan)
        cols[f"{prefix}same_first_msg_{L}h"] = np.full(len(anchors), None, dtype=object)
        cols[f"{prefix}same_first_fam_{L}h"] = np.full(len(anchors), None, dtype=object)

    pos = {ix: i for i, ix in enumerate(anchors.index)}
    maxL = max(lookbacks_h)

    for (farm, tid), grp in anchors.groupby(["farm", "turbine_id"], sort=False):
        wt = warns[(warns["farm"] == farm) & (warns["turbine_id"] == tid)]
        if len(wt) == 0:
            continue
        wt = wt.sort_values("start")
        w_ns = wt["start"].values.astype("datetime64[ns]").astype("int64")
        w_fam = wt["family"].values
        w_msg = wt["message"].values

        for ix, anchor, famset in zip(grp.index, grp["anchor"], grp["fam_set"]):
            if pd.isna(anchor):
                continue
            i = pos[ix]
            a_ns = np.datetime64(anchor, "ns").astype("int64")
            lo_max = a_ns - int(maxL * 3600 * 1e9)
            s, e = _searchsorted_window(w_ns, lo_max, a_ns)
            if s == e:
                continue                      # nothing in the widest window
            sub_ns, sub_fam, sub_msg = w_ns[s:e], w_fam[s:e], w_msg[s:e]
            # same-component mask over the widest window, reused for each L
            ok = np.array([(f in famset) and (f not in NEVER_MATCH) for f in sub_fam],
                          dtype=bool)
            for L in lookbacks_h:
                lo = a_ns - int(L * 3600 * 1e9)
                k = sub_ns >= lo                       # sub_ns is sorted ascending
                if not k.any():
                    continue
                idx = np.flatnonzero(k)
                j0 = idx[0]                            # earliest in window
                cols[f"{prefix}any_warn_{L}h"][i] = True
                cols[f"{prefix}any_n_{L}h"][i] = len(idx)
                cols[f"{prefix}any_lead_h_{L}h"][i] = (a_ns - sub_ns[j0]) / 3.6e12
                cols[f"{prefix}any_first_msg_{L}h"][i] = sub_msg[j0]
                cols[f"{prefix}any_first_fam_{L}h"][i] = sub_fam[j0]
                sidx = idx[ok[idx]]
                if len(sidx):
                    j1 = sidx[0]
                    cols[f"{prefix}same_warn_{L}h"][i] = True
                    cols[f"{prefix}same_n_{L}h"][i] = len(sidx)
                    cols[f"{prefix}same_lead_h_{L}h"][i] = (a_ns - sub_ns[j1]) / 3.6e12
                    cols[f"{prefix}same_first_msg_{L}h"][i] = sub_msg[j1]
                    cols[f"{prefix}same_first_fam_{L}h"][i] = sub_fam[j1]

    return pd.DataFrame(cols, index=anchors.index)


def load_events():
    ev = pd.read_parquet(C.EVENTS_PARQUET)
    ev["fam_set"] = ev["families_all"].apply(frozenset)
    return ev


def load_warnings():
    return pd.read_parquet(C.WARNINGS_PARQUET)


def main():
    ev = load_events()
    wn = load_warnings()
    print(f"events {len(ev):,}   warnings {len(wn):,}")

    anchors = ev[["farm", "turbine_id", "fam_set"]].copy()
    anchors["anchor"] = ev["start"]
    att = attribute(anchors, wn)

    out = pd.concat([ev[["event_id", "farm", "turbine_id", "start", "end",
                         "duration_h", "E_mwh", "family", "families_all",
                         "primary_message", "n_stops",
                         "T0", "T1", "T2", "T1_wide_grid", "T2_wide_grid",
                         "is_manual_only", "mean_potential_kw",
                         "median_potential_kw", "mean_wind_ms", "year"]],
                     att], axis=1)
    out["fam_set_size"] = ev["fam_set"].apply(len).values
    out["matchable"] = ev["fam_set"].apply(
        lambda s: len(set(s) - NEVER_MATCH) > 0).values
    out.to_parquet(ATTRIBUTION_PARQUET, index=False)
    print(f"wrote {ATTRIBUTION_PARQUET}: {len(out):,} rows")

    # -------------------------------------------------------------- summary
    print("\n=== attribution rates (count-weighted) ===")
    rows = []
    for tier, mask in (("T0", out["T0"]), ("T1", out["T1"]), ("T2", out["T2"]),
                       ("T2_wide_grid", out["T2_wide_grid"])):
        s = out[mask]
        for L in LOOKBACKS_H:
            rows.append({
                "tier": tier, "lookback_h": L, "n": len(s),
                "any_pct": 100 * s[f"any_warn_{L}h"].mean(),
                "same_pct": 100 * s[f"same_warn_{L}h"].mean(),
                "any_pct_E": 100 * (s[f"any_warn_{L}h"] * s["E_mwh"]).sum() / s["E_mwh"].sum(),
                "same_pct_E": 100 * (s[f"same_warn_{L}h"] * s["E_mwh"]).sum() / s["E_mwh"].sum(),
                "med_lead_any": s.loc[s[f"any_warn_{L}h"], f"any_lead_h_{L}h"].median(),
                "med_lead_same": s.loc[s[f"same_warn_{L}h"], f"same_lead_h_{L}h"].median(),
            })
    summ = pd.DataFrame(rows)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    summ.to_csv(os.path.join(C.SUMMARY_OUT, "attribution_summary.csv"), index=False)

    # the PROFILE §6 comparison point: turbine-side stops, any-warning, 72 h = 63.7 %
    ts = out[out["T2_wide_grid"]]
    print(f"\nPROFILE §6 cross-check: turbine-side any-warning 72 h = "
          f"{100 * ts['any_warn_72h'].mean():.1f}%  (PROFILE, unmerged: 63.7%)")
    print(f"  median lead {ts.loc[ts['any_warn_72h'], 'any_lead_h_72h'].median():.1f} h "
          f"(PROFILE: 30.1 h)")
    print(f"  events with no matchable family at all: {int((~out['matchable']).sum()):,}")
    return out


if __name__ == "__main__":
    main()
