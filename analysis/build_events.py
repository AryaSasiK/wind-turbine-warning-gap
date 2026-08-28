#!/usr/bin/env python3
"""events.parquet - merged forced-outage events with lost energy E.

Implements STUDY_DESIGN.md "Event definition" exactly, in the order the spec
states it:

  1. base population  Status == 'Stop' AND IEC category == 'Forced outage'
  2. de-duplicate exact repeats on (farm, turbine, start, end, code)
  3. drop pre-commissioning rows (Kelmarsh < 2016-04-15, Penmanshiel < 2016-09-01)
  4. MERGE overlapping/nested stop intervals per turbine; the merged event
     inherits its constituents' messages
  5. lost energy E = sum((Cascading potential power - Power)+ ) * 10 min over the
     MERGED window, i.e. charged once (PROFILE §5: the WT10 2023-03-24 pair each
     claim ~420 MWh for one physical outage)
  6. tier flags T0 / T1 / T2 as boolean columns on the merged events

Order note: merging happens BEFORE tiering, per the spec's own ordering, so a
merged event can mix grid-side and turbine-side constituents. Tier flags are
therefore defined on the merged event: it survives a tier if *any* constituent
message survives that tier's message filter. checks.md reports how often that
matters and gives the filter-then-merge alternative as a sensitivity.

    python3 build_events.py            # uses the SCADA cache, builds it if absent
"""
import os

import numpy as np
import pandas as pd

import build_scada_cache as SC
import common as C


# --------------------------------------------------------------------- energy
def energy_over_windows(win, scada_cache=None):
    """Per-window lost energy and wind statistics from the 10-minute SCADA grid.

    `win` needs columns farm, turbine_id, t0, t1. Windows are sliced [t0, t1] on
    the bin start-timestamp, the same convention PROFILE §5 validated against
    Greenbyte's own `Lost Production to Downtime` (ratio 1.00040).

    Returns a frame aligned to win.index.
    """
    cache = {} if scada_cache is None else scada_cache
    cols = ["E_mwh", "E_greenbyte_mwh", "curtail_mwh", "scada_rows",
            "pot_coverage", "power_coverage", "mean_potential_kw",
            "median_potential_kw", "mean_power_kw", "mean_wind_ms",
            "max_potential_kw"]
    out = pd.DataFrame(np.nan, index=win.index, columns=cols)
    for (farm, tid), grp in win.groupby(["farm", "turbine_id"], sort=True):
        key = (farm, tid)
        if key not in cache:
            cache.clear()                     # one turbine resident at a time
            cache[key] = SC.load_turbine(farm, tid)
        sc = cache[key]
        for idx, t0, t1 in zip(grp.index, grp["t0"], grp["t1"]):
            w = sc.loc[t0:t1]
            n = len(w)
            if n == 0:
                out.loc[idx, ["E_mwh", "E_greenbyte_mwh", "curtail_mwh",
                              "scada_rows"]] = [0.0, 0.0, 0.0, 0]
                continue
            p = w[C.POT]
            a = w[C.POWER].fillna(0.0).clip(lower=0.0)
            out.loc[idx, "E_mwh"] = float((p - a).clip(lower=0.0).sum()
                                          * C.BIN_HOURS / 1000.0)
            out.loc[idx, "E_greenbyte_mwh"] = float(w[C.GB_DOWNTIME].sum()) / 1000.0
            out.loc[idx, "curtail_mwh"] = float(w[C.GB_CURTAIL].sum()) / 1000.0
            out.loc[idx, "scada_rows"] = n
            out.loc[idx, "pot_coverage"] = float(p.notna().mean())
            out.loc[idx, "power_coverage"] = float(w[C.POWER].notna().mean())
            out.loc[idx, "mean_potential_kw"] = float(p.mean())
            out.loc[idx, "median_potential_kw"] = float(p.median())
            out.loc[idx, "max_potential_kw"] = float(p.max())
            out.loc[idx, "mean_power_kw"] = float(w[C.POWER].mean())
            out.loc[idx, "mean_wind_ms"] = float(w[C.WIND].mean())
    return out


# ------------------------------------------------------------------ population
def base_population(st):
    fo = st[(st["Status"] == C.BASE_STATUS)
            & (st["IEC category"] == C.BASE_IEC)].copy()
    return fo


def collapse(series):
    """Ordered unique list of non-null values, as a plain python list."""
    seen, out = set(), []
    for v in series:
        if pd.isna(v):
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def main():
    steps = []

    def step(label, n, note=""):
        steps.append({"step": label, "rows": n, "note": note})
        print(f"{label:<62} {n:>8,}  {note}")

    st, counts = C.load_status()
    step("status rows (pooled log)", counts["status_rows_raw"])
    step("  rows with a trailing-space Message (stripped)",
         counts["status_untrimmed_messages"])

    fo = base_population(st)
    step("Status=='Stop' AND IEC=='Forced outage'", len(fo),
         "PROFILE §3 headline: 6,366")

    n_open = int(fo["t1"].isna().sum())
    fo = fo[fo["t0"].notna() & fo["t1"].notna()].copy()
    step("  ...with both timestamps (open-ended stops dropped)", len(fo),
         f"{n_open} open-ended")

    # PROFILE §3 reports "no negative durations", but that test used
    # pd.to_timedelta on the Duration string, which returns NaT (not a negative)
    # for the two malformed values in the corpus ('-01:00:-19', '-01:-36:-49').
    # Comparing the parsed timestamps finds them: one is a forced-outage stop.
    neg = fo["t1"] < fo["t0"]
    fo = fo[~neg].copy()
    step("  ...with end >= start", len(fo),
         f"{int(neg.sum())} negative-duration row(s) dropped "
         f"(malformed Duration; PROFILE §3 misses these)")

    dup = fo.duplicated(["farm", "turbine_id", "t0", "t1", "Code"], keep="first")
    fo = fo[~dup].copy()
    step("  ...after dropping exact duplicates", len(fo),
         f"{int(dup.sum())} dropped (split Penmanshiel 2023 zips overlap)")
    n_prevalidation = len(fo)

    # ---- cross-check against PROFILE §5 BEFORE the commissioning cut --------
    cache = {}
    print("\ncomputing per-stop lost energy (unmerged, pre-commissioning-cut) "
          "for the PROFILE §5 cross-check ...", flush=True)
    raw_all = energy_over_windows(fo, cache)
    fo_raw = fo.join(raw_all)
    profile_check = {
        "n_stops": len(fo_raw),
        "E_cascading_mwh": float(fo_raw["E_mwh"].sum()),
        "E_greenbyte_mwh": float(fo_raw["E_greenbyte_mwh"].sum()),
        "curtail_mwh": float(fo_raw["curtail_mwh"].sum()),
    }
    profile_check["ratio_casc_over_greenbyte"] = (
        profile_check["E_cascading_mwh"] / profile_check["E_greenbyte_mwh"])
    print(f"  unmerged Sum(casc-power)+  = {profile_check['E_cascading_mwh']:,.1f} MWh "
          f"(PROFILE §5: 14,369.6)")
    print(f"  unmerged Greenbyte downtime = {profile_check['E_greenbyte_mwh']:,.1f} MWh "
          f"(PROFILE §5: 14,363.9)  ratio {profile_check['ratio_casc_over_greenbyte']:.5f}")

    # ---- commissioning exclusion -------------------------------------------
    pre = C.pre_cod_mask(fo)
    pre_e = float(fo_raw.loc[pre, "E_mwh"].sum())
    fo = fo[~pre].copy()
    step("  ...after commissioning exclusion", len(fo),
         f"{int(pre.sum())} pre-COD stops, {pre_e:,.1f} MWh")

    # ---- merge --------------------------------------------------------------
    fo = C.merge_intervals(fo)
    n_groups = fo["group"].nunique()
    step("MERGED events (overlapping/nested intervals per turbine)", n_groups,
         f"{len(fo) - n_groups} stops absorbed into an earlier event")

    fo["fam_msg"] = fo["Message"]
    fo["is_grid"] = fo["Message"].isin(C.GRID_MESSAGES)
    fo["is_grid_ext"] = fo["Message"].isin(C.GRID_MESSAGES | C.GRID_MESSAGES_EXTRA)
    fo["is_manual"] = fo["Message"].isin(C.MANUAL_MESSAGES)
    fo["stop_dur_s"] = (fo["t1"] - fo["t0"]).dt.total_seconds()

    g = fo.groupby("group", sort=True)
    ev = pd.DataFrame({
        "farm": g["farm"].first(),
        "turbine_id": g["turbine_id"].first(),
        "start": g["t0"].min(),
        "end": g["t1"].max(),
        "n_stops": g.size(),
        "messages": g["Message"].apply(collapse),
        "codes": g["Code"].apply(collapse),
        "service_categories": g["Service contract category"].apply(collapse),
        "n_grid_msgs": g["is_grid"].sum(),
        "n_grid_ext_msgs": g["is_grid_ext"].sum(),
        "n_manual_msgs": g["is_manual"].sum(),
        "sum_constituent_dur_h": g["stop_dur_s"].sum() / 3600.0,
    }).reset_index().rename(columns={"group": "event_group"})
    ev.insert(0, "event_id", range(len(ev)))
    gid2eid = ev.set_index("event_group")["event_id"]

    # the longest constituent stop names the event (used for the family label).
    # tail(1) after sorting takes a whole row; groupby().last() would take the
    # last non-null value of each column independently, which can mix rows.
    longest = (fo.sort_values("stop_dur_s").groupby("group").tail(1)
                 .set_index("group"))
    ev["primary_message"] = ev["event_group"].map(longest["Message"]).values
    ev["primary_code"] = ev["event_group"].map(longest["Code"]).values
    ev["messages_joined"] = ev["messages"].apply(" | ".join)
    ev["duration_h"] = (ev["end"] - ev["start"]).dt.total_seconds() / 3600.0
    ev["overlap_h"] = ev["sum_constituent_dur_h"] - ev["duration_h"]
    ev["year"] = ev["start"].dt.year

    # ---- tier flags ---------------------------------------------------------
    # An event survives a tier if ANY constituent message survives that tier's
    # message filter; equivalently it is dropped only when ALL of its messages
    # are excluded. `n_*_msgs` are exported so stage 2 can re-tier without a re-run.
    ev["T0"] = True
    ev["all_grid"] = ev["n_grid_msgs"] == ev["n_stops"]
    ev["T1"] = ~ev["all_grid"]
    ev["all_grid_or_manual"] = (ev["n_grid_msgs"] + ev["n_manual_msgs"]) == ev["n_stops"]
    ev["T2"] = ~ev["all_grid_or_manual"]
    ev["mixed_grid"] = (ev["n_grid_msgs"] > 0) & (ev["n_grid_msgs"] < ev["n_stops"])
    ev["mixed_manual"] = (ev["n_manual_msgs"] > 0) & (ev["n_manual_msgs"] < ev["n_stops"])
    ev["is_manual_only"] = (ev["n_manual_msgs"] == ev["n_stops"])
    # sensitivity flag: T1 with PROFILE §3's wider grid list (adds 'Maximum grid frequency')
    ev["T1_wide_grid"] = ~(ev["n_grid_ext_msgs"] == ev["n_stops"])
    ev["T2_wide_grid"] = ~((ev["n_grid_ext_msgs"] + ev["n_manual_msgs"]) == ev["n_stops"])

    # ---- component family ---------------------------------------------------
    cm = pd.read_csv(os.path.join(C.SUMMARY_OUT, "component_map.csv"))
    fam = cm[cm.role.isin(("stop", "both"))].set_index("message")["family"]
    ev["family"] = ev["primary_message"].map(fam)
    if ev["family"].isna().any():
        raise SystemExit("unmapped stop messages: "
                         + str(sorted(ev.loc[ev.family.isna(), "primary_message"].unique())))
    ev["families_all"] = ev["messages"].apply(
        lambda ms: sorted({fam[m] for m in ms}))

    # ---- energy on merged windows -------------------------------------------
    print("\ncomputing lost energy over MERGED windows ...", flush=True)
    cache.clear()
    ev = ev.join(energy_over_windows(ev.rename(columns={"start": "t0", "end": "t1"})
                                     [["farm", "turbine_id", "t0", "t1"]], cache))

    # constituent (unmerged) energy on the SAME retained population, so the
    # double-count that merging removes is measurable
    print("computing per-constituent lost energy on the retained population ...",
          flush=True)
    cache.clear()
    cons = fo.join(energy_over_windows(fo, cache), rsuffix="_c")
    per_group = cons.groupby("group")["E_mwh"].sum()
    ev["E_unmerged_sum_mwh"] = ev["event_group"].map(per_group).values
    ev["E_double_counted_mwh"] = ev["E_unmerged_sum_mwh"] - ev["E_mwh"]

    ev["scada_rows"] = ev["scada_rows"].astype("Int64")
    cons["event_id"] = cons["group"].map(gid2eid)

    ev.to_parquet(C.EVENTS_PARQUET, index=False)
    cons_out = os.path.join(C.DERIVED, "event_constituents.parquet")
    (cons[["event_id", "farm", "turbine_id", "t0", "t1", "Code", "Message",
           "Service contract category", "stop_dur_s", "E_mwh", "E_greenbyte_mwh"]]
     .rename(columns={"t0": "start", "t1": "end",
                      "Code": "code", "Message": "message",
                      "Service contract category": "service_category"})
     .to_parquet(cons_out, index=False))

    print(f"\nwrote {C.EVENTS_PARQUET}: {len(ev):,} merged events")
    print(f"wrote {cons_out}: {len(cons):,} constituent stops")

    # ---- summary ------------------------------------------------------------
    rows = []
    for tier in ("T0", "T1", "T2"):
        s = ev[ev[tier]]
        rows.append({"tier": tier, "events": len(s),
                     "E_mwh": s["E_mwh"].sum(),
                     "E_greenbyte_mwh": s["E_greenbyte_mwh"].sum(),
                     "downtime_h": s["duration_h"].sum(),
                     "events_ge_6h": int((s["duration_h"] >= 6).sum()),
                     "events_ge_24h": int((s["duration_h"] >= 24).sum()),
                     "E_ge_24h_mwh": s.loc[s["duration_h"] >= 24, "E_mwh"].sum()})
    summ = pd.DataFrame(rows)
    print("\n=== tier summary (merged events) ===")
    print(summ.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    summ.to_csv(os.path.join(C.SUMMARY_OUT, "events_summary.csv"), index=False)
    pd.DataFrame(steps).to_csv(os.path.join(C.SUMMARY_OUT, "events_steps.csv"),
                               index=False)
    pd.Series(profile_check).to_csv(
        os.path.join(C.SUMMARY_OUT, "profile_crosscheck.csv"))
    print("\n=== merge accounting ===")
    print(f"  constituent stops retained      {len(fo):,}")
    print(f"  merged events                   {len(ev):,}")
    print(f"  events with >1 constituent      {int((ev.n_stops > 1).sum()):,}")
    print(f"  Sum of per-stop E (unmerged)    {ev['E_unmerged_sum_mwh'].sum():,.1f} MWh")
    print(f"  Sum of merged-window E          {ev['E_mwh'].sum():,.1f} MWh")
    print(f"  double-count eliminated         {ev['E_double_counted_mwh'].sum():,.1f} MWh")
    return ev


if __name__ == "__main__":
    if not os.path.isdir(C.SCADA_CACHE) or not os.listdir(C.SCADA_CACHE):
        raise SystemExit("SCADA cache missing - run build_scada_cache.py first")
    main()
