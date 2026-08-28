#!/usr/bin/env python3
"""warnings.parquet - every `Warning` row in the pooled status log.

STUDY_DESIGN.md makes status-log `Warning` rows the primary instrument, so this
is deliberately a thin, faithful extract: no filtering by content, no windowing,
no joining to events. The only rows removed are exact duplicates on
(farm, turbine, start, end, code) - PROFILE §3 records 8,680 such duplicates
across the whole log, concentrated pathologically on Penmanshiel WT01.

The `family` column is joined from component_map.csv. That map is frozen only
after orchestrator review, so re-run this script if the map changes.

    python3 build_warnings.py
"""
import os

import pandas as pd

import common as C


def main():
    st, counts = C.load_status()
    log = []

    def step(label, n):
        log.append((label, n))
        print(f"{label:<58} {n:>9,}")

    step("status rows (pooled log)", len(st))
    w = st[st["Status"] == "Warning"].copy()
    step("Status == 'Warning'", len(w))

    w = w[w["t0"].notna()]
    step("  ...with a parseable start timestamp", len(w))

    # same malformed-Duration issue as build_events.py (PROFILE §3 misses these)
    neg = w["t1"].notna() & (w["t1"] < w["t0"])
    print(f"{'  negative-duration rows dropped':<58} {int(neg.sum()):>9,}")
    w = w[~neg]
    step("  ...with end >= start where an end exists", len(w))

    dup = w.duplicated(["farm", "turbine_id", "t0", "t1", "Code"], keep="first")
    print(f"{'  exact duplicates dropped (farm,turbine,t0,t1,code)':<58} {int(dup.sum()):>9,}")
    w = w[~dup]
    step("  ...after de-duplication", len(w))

    w["pre_cod"] = C.pre_cod_mask(w)
    step("  of which pre-commissioning (flagged, NOT dropped)", int(w["pre_cod"].sum()))
    step("  post-commissioning warnings", int((~w["pre_cod"]).sum()))

    cm = pd.read_csv(os.path.join(C.SUMMARY_OUT, "component_map.csv"))
    fam = cm[cm.role.isin(("warning", "both"))].set_index("message")["family"]
    w["family"] = w["Message"].map(fam)
    unmapped = w["family"].isna().sum()
    if unmapped:
        raise SystemExit(f"{unmapped} warning rows have no component family: "
                         f"{sorted(w.loc[w.family.isna(), 'Message'].unique())}")

    out = (w[["farm", "turbine_id", "t0", "t1", "dur_s", "Code", "Message", "family",
              "Service contract category", "IEC category", "pre_cod",
              "src_zip", "src_member"]]
           .rename(columns={"t0": "start", "t1": "end", "Code": "code",
                            "Message": "message",
                            "Service contract category": "service_category",
                            "IEC category": "iec_category"})
           .sort_values(["farm", "turbine_id", "start"])
           .reset_index(drop=True))
    out.insert(0, "warning_id", range(len(out)))
    out.to_parquet(C.WARNINGS_PARQUET, index=False)
    print(f"\nwrote {C.WARNINGS_PARQUET}: {len(out):,} rows, "
          f"{out.message.nunique()} messages, {out.family.nunique()} families")
    print(f"span {out.start.min()} .. {out.start.max()}")
    print("\nrows per family:")
    print(out.family.value_counts().to_string())

    pd.DataFrame(log, columns=["step", "rows"]).to_csv(
        os.path.join(C.SUMMARY_OUT, "warnings_steps.csv"), index=False)


if __name__ == "__main__":
    main()
