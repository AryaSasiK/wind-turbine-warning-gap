#!/usr/bin/env python3
"""controls.parquet - matched quiet controls, one per merged event, plus their
warning attribution.

STUDY_DESIGN.md "Control adjustment":

    for each event, a matched control at -45 d on the same turbine, verified quiet
    (no forced-outage stop within +/-3 d; re-draw at -44/-46... if not quiet).
    ... Sensitivity: -30 d, -60 d controls.

The control answers "how often would the same-component rule have fired at a random
quiet moment on this turbine?", so the component family set is inherited from the
EVENT, not re-derived - a control has no stop and therefore no family of its own.
That is what makes the control matched rather than merely contemporaneous.

Readings fixed here (alternatives carried as sensitivities in RESULTS.md):

  (a) "no forced-outage stop within +/-3 d" is tested on the stop START timestamp,
      strictly inside the open interval (c - 3 d, c + 3 d), against the full retained
      T0 constituent-stop population (all messages, grid and manual included). This
      is verbatim what `data/smoke_precursors.py` did to produce the 16.5 % control
      rate the study quotes, so the two remain comparable.
  (b) The re-draw walk is 45, 44, 46, 43, 47, ... i.e. alternating outward in 1-day
      steps, and is capped at MAX_DEVIATION_D days from the anchor. The spec gives
      the first three terms and no cap; without one, a turbine in a dense fault
      cluster would walk arbitrarily far and stop being a *matched* control.
  (c) Controls are NOT required to lie inside the turbine's log coverage. A
      `in_coverage` flag is recorded (control lookback window fully inside the
      turbine's status-log span) and the restricted variant is reported as a
      sensitivity, because an out-of-coverage control is a structural zero that
      would bias the control rate downwards and the excess upwards.

    python3 controls.py
"""
import os

import numpy as np
import pandas as pd

import attribute as A
import common as C

ANCHOR_DAYS = (45, 30, 60)          # 45 is primary (STUDY_DESIGN); 30/60 sensitivity
PRIMARY_ANCHOR_D = 45
QUIET_HALFWIDTH_D = 3
MAX_DEVIATION_D = 10                # cap on the re-draw walk (see docstring (b))

CONTROLS_PARQUET = os.path.join(C.DERIVED, "controls.parquet")
CONSTITUENTS_PARQUET = os.path.join(C.DERIVED, "event_constituents.parquet")


def walk_offsets(anchor_d, max_dev=MAX_DEVIATION_D):
    """45, 44, 46, 43, 47, ... in days, as the spec's re-draw sequence."""
    yield anchor_d
    for k in range(1, max_dev + 1):
        yield anchor_d - k
        yield anchor_d + k


def find_quiet_controls(ev, fo_starts, anchor_d):
    """One quiet control timestamp per event, or NaT if the walk exhausts.

    `fo_starts` maps (farm, turbine_id) -> sorted int64 ns array of forced-outage
    stop start timestamps (the full retained T0 constituent population).
    """
    n = len(ev)
    ctrl = np.full(n, np.iinfo(np.int64).min, dtype=np.int64)   # min == NaT in ns
    used = np.full(n, np.nan)
    tries = np.zeros(n, dtype=np.int16)
    half = int(QUIET_HALFWIDTH_D * 86400 * 1e9)

    pos = {ix: i for i, ix in enumerate(ev.index)}
    for (farm, tid), grp in ev.groupby(["farm", "turbine_id"], sort=False):
        arr = fo_starts.get((farm, tid))
        if arr is None:
            arr = np.array([], dtype="int64")
        for ix, start in zip(grp.index, grp["start"]):
            i = pos[ix]
            s_ns = np.datetime64(start, "ns").astype("int64")
            for j, off in enumerate(walk_offsets(anchor_d)):
                c = s_ns - int(off * 86400 * 1e9)
                # quiet iff no stop START strictly inside (c - 3 d, c + 3 d)
                lo = np.searchsorted(arr, c - half, side="right")
                hi = np.searchsorted(arr, c + half, side="left")
                if lo >= hi:
                    ctrl[i] = c
                    used[i] = off
                    tries[i] = j + 1
                    break
            else:
                tries[i] = 2 * MAX_DEVIATION_D + 1
    return ctrl.view("datetime64[ns]"), used, tries


def coverage_span(warns):
    """(farm, turbine_id) -> (first, last) status-log warning timestamp.

    Used only for the `in_coverage` diagnostic flag; the warning log is the
    instrument, so its own span is the right coverage proxy.
    """
    g = warns.groupby(["farm", "turbine_id"])["start"]
    return g.min().to_dict(), g.max().to_dict()


def main():
    ev = A.load_events()
    wn = A.load_warnings()
    cons = pd.read_parquet(CONSTITUENTS_PARQUET)

    fo_starts = {}
    for k, g in cons.groupby(["farm", "turbine_id"]):
        fo_starts[k] = np.sort(g["start"].values.astype("datetime64[ns]")
                               .astype("int64"))
    print(f"quiet test against {len(cons):,} retained forced-outage stops "
          f"on {len(fo_starts)} turbines")

    cov_lo, cov_hi = coverage_span(wn)

    out = ev[["event_id", "farm", "turbine_id", "start", "duration_h", "E_mwh",
              "family", "families_all", "T0", "T1", "T2",
              "T1_wide_grid", "T2_wide_grid", "is_manual_only"]].copy()
    report = []

    for anchor_d in ANCHOR_DAYS:
        tag = f"c{anchor_d}"
        ctrl, used, tries = find_quiet_controls(ev, fo_starts, anchor_d)
        out[f"{tag}_ts"] = pd.to_datetime(ctrl)
        out[f"{tag}_offset_d"] = used
        out[f"{tag}_tries"] = tries
        matched = out[f"{tag}_ts"].notna()
        out[f"{tag}_matched"] = matched

        lo = pd.Series([cov_lo.get((f, t), pd.NaT) for f, t in
                        zip(out["farm"], out["turbine_id"])], index=out.index)
        hi = pd.Series([cov_hi.get((f, t), pd.NaT) for f, t in
                        zip(out["farm"], out["turbine_id"])], index=out.index)
        out[f"{tag}_in_coverage"] = (
            matched
            & (out[f"{tag}_ts"] - pd.Timedelta(hours=A.PRIMARY_LOOKBACK_H) >= lo)
            & (out[f"{tag}_ts"] <= hi))

        anchors = out[["farm", "turbine_id"]].copy()
        anchors["anchor"] = out[f"{tag}_ts"]
        anchors["fam_set"] = ev["fam_set"].values      # inherited from the EVENT
        att = A.attribute(anchors, wn, prefix=f"{tag}_")
        # an unmatched control has no attribution at all
        for col in att.columns:
            if att[col].dtype == bool:
                att.loc[~matched, col] = False
            else:
                att.loc[~matched, col] = np.nan
        out = pd.concat([out, att], axis=1)

        n_m = int(matched.sum())
        report.append({
            "anchor_d": anchor_d,
            "events": len(out),
            "matched": n_m,
            "match_rate_pct": 100 * n_m / len(out),
            "exact_anchor_pct": 100 * (out[f"{tag}_offset_d"] == anchor_d).mean(),
            "median_abs_dev_d": float(np.nanmedian(
                np.abs(out[f"{tag}_offset_d"] - anchor_d))),
            "in_coverage_pct": 100 * out[f"{tag}_in_coverage"].mean(),
            "ctrl_any72_pct": 100 * out.loc[matched, f"{tag}_any_warn_72h"].mean(),
            "ctrl_same72_pct": 100 * out.loc[matched, f"{tag}_same_warn_72h"].mean(),
            "ctrl_any72_pct_E": 100 * (out.loc[matched, f"{tag}_any_warn_72h"]
                                       * out.loc[matched, "E_mwh"]).sum()
                                / out.loc[matched, "E_mwh"].sum(),
            "ctrl_same72_pct_E": 100 * (out.loc[matched, f"{tag}_same_warn_72h"]
                                        * out.loc[matched, "E_mwh"]).sum()
                                 / out.loc[matched, "E_mwh"].sum(),
        })
        print(f"  -{anchor_d}d: matched {n_m:,}/{len(out):,} "
              f"({100*n_m/len(out):.1f}%), control any-warning 72 h "
              f"{report[-1]['ctrl_any72_pct']:.1f}%")

    out.to_parquet(CONTROLS_PARQUET, index=False)
    print(f"\nwrote {CONTROLS_PARQUET}: {len(out):,} rows")

    rep = pd.DataFrame(report)
    rep.to_csv(os.path.join(C.SUMMARY_OUT, "controls_summary.csv"), index=False)
    print("\n=== control match + base rates (all merged events) ===")
    print(rep.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    # PROFILE §6 quotes 16.5 % on the turbine-side population; reproduce that view
    m = out[f"c{PRIMARY_ANCHOR_D}_matched"]
    ts = out[out["T2_wide_grid"] & m]
    print(f"\nPROFILE §6 cross-check (turbine-side, -45 d, any-warning 72 h): "
          f"{100 * ts[f'c{PRIMARY_ANCHOR_D}_any_warn_72h'].mean():.1f}%  "
          f"(PROFILE: 16.5%)")
    return out


if __name__ == "__main__":
    main()
