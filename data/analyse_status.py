#!/usr/bin/env python3
"""Profile the pooled status/event log.

Note: '-' is the sentinel for "no end / no duration" (instantaneous event),
not NaN. Treat it before parsing anything.
"""
import os, sys
import numpy as np
import pandas as pd
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 400)
pd.set_option("display.max_colwidth", 60)

D = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
st = pd.read_parquet(os.path.join(D, "status_all.parquet"))
st.columns = [c.strip() for c in st.columns]

print("### shape", st.shape)
print("### columns", list(st.columns))
print("### column presence by source zip (schema drift)")
for c in ("Global contract category", "Custom contract category"):
    if c in st.columns:
        pres = st.groupby("src_zip")[c].apply(lambda s: s.notna().any())
        print(f"  {c}: present in {int(pres.sum())} of {len(pres)} zips ->",
              sorted(pres[pres].index.tolist()))
print()

# ---------------------------------------------------------------- sentinels
for c in ("Timestamp end", "Duration"):
    st[c] = st[c].replace("-", np.nan)
st["t0"] = pd.to_datetime(st["Timestamp start"], errors="coerce", format="mixed")
st["t1"] = pd.to_datetime(st["Timestamp end"], errors="coerce", format="mixed")
st["dur_s"] = pd.to_timedelta(st["Duration"], errors="coerce").dt.total_seconds()
st["year"] = st["t0"].dt.year
st["is_interval"] = st["t1"].notna()

print("### timestamp/duration integrity")
print("  rows:", len(st))
print("  '-' sentinel rows (instantaneous, no end/duration):",
      int((~st.is_interval).sum()), f"({(~st.is_interval).mean()*100:.1f}%)")
print("  unparsed start ts:", int(st.t0.isna().sum()))
print("  instantaneous rows by Status:",
      st.loc[~st.is_interval, "Status"].value_counts().to_dict())
print("  span:", st.t0.min(), "->", st.t0.max())
iv = st[st.is_interval].copy()
iv["resid"] = (iv.t1 - iv.t0).dt.total_seconds() - iv.dur_s
print("  Duration vs (end-start) residual seconds: max|resid| =",
      float(iv.resid.abs().max()), "| rows >1s off:", int((iv.resid.abs() > 1).sum()),
      "of", len(iv))
print("  negative durations:", int((iv.dur_s < 0).sum()))
print("  zero durations:", int((iv.dur_s == 0).sum()))
print()

# ------------------------------------------------------------ vocabularies
for col in ("Status", "IEC category", "Service contract category",
            "Global contract category"):
    if col in st.columns and st[col].notna().any():
        vc = st[col].fillna("<blank>").value_counts()
        print(f"### {col}  ({len(vc)} distinct)")
        print(vc.to_string())
        print()

print("### Status x IEC category")
print(pd.crosstab(st["Status"].fillna("<blank>"),
                  st["IEC category"].fillna("<blank>")).to_string())
print()

# --------------------------------------------------------- message content
msg = st["Message"].fillna("<blank>")
print("### Message cardinality:", msg.nunique(), "distinct of", len(msg), "rows")
print("### Code cardinality:", st["Code"].nunique())
print("### Message x Code pairs:", st.groupby(["Code", "Message"]).ngroups)
print("### Comment field: non-null =", int(st["Comment"].notna().sum()),
      "-> the free-text comment column is empty in the public release"
      if st["Comment"].notna().sum() == 0 else "")
print()
print("### top 30 messages (all rows)")
print(msg.value_counts().head(30).to_string())
print()

# --------------------------------------------------------- forced outages
# IEC 'Forced outage' is attached to Warning rows too; a *stop* needs Status=='Stop'.
st["fo_any"] = st["IEC category"] == "Forced outage"
st["fo_stop"] = st.fo_any & (st["Status"] == "Stop")
st["any_stop"] = st["Status"] == "Stop"

FO = st[st.fo_stop].copy()
print("### FORCED-OUTAGE STOPS (Status=='Stop' & IEC=='Forced outage'):", len(FO))
print("###   ...vs IEC=='Forced outage' on any Status:", int(st.fo_any.sum()),
      "(the difference is Warning rows carrying the category)")
print("### FO stops by farm:", FO.groupby("farm").size().to_dict())
print("### FO stop message cardinality:", FO["Message"].nunique())
print(FO["Message"].fillna("<blank>").value_counts().head(30).to_string())
print()
print("### FO stop duration (hours)")
print((FO.dur_s / 3600).describe(percentiles=[.25, .5, .75, .9, .95, .99]).to_string())
print("### FO stop total downtime hours by farm:",
      (FO.groupby("farm").dur_s.sum() / 3600).round(0).to_dict())
print()

# ------------------------------------------------- per turbine-year table
g = st.groupby(["farm", "turbine_id", "year"])
tab = g.agg(events=("Status", "size"),
            interval_events=("is_interval", "sum"),
            stops=("any_stop", "sum"),
            fo_stops=("fo_stop", "sum"),
            fo_any=("fo_any", "sum"),
            distinct_messages=("Message", "nunique")).reset_index()
fo_h = (FO.groupby(["farm", "turbine_id", "year"]).dur_s.sum() / 3600).rename("fo_stop_hours")
tab = tab.merge(fo_h, on=["farm", "turbine_id", "year"], how="left")
tab["fo_stop_hours"] = tab["fo_stop_hours"].fillna(0).round(1)
tab.to_csv(os.path.join(D, "events_per_turbine_year.csv"), index=False)
print("### per turbine-year")
print(tab.to_string(index=False))
print()
print("### farm-year totals")
print(tab.groupby(["farm", "year"])[["events", "stops", "fo_stops", "fo_stop_hours"]]
        .sum().to_string())
print()
print("### per-turbine-year FO-stop count distribution")
print(tab.fo_stops.describe().to_string())
print()
print("### GRAND TOTALS  events=%d  stops=%d  fo_stops=%d  turbine-years=%d  turbines=%d"
      % (tab.events.sum(), tab.stops.sum(), tab.fo_stops.sum(), len(tab),
         st.groupby(["farm", "turbine_id"]).ngroups))
print("### turbine ids by farm:")
for f, gg in st.groupby("farm"):
    print("   ", f, sorted(gg.turbine_id.unique()))
print()

# -------------------------------------------------------- overlap analysis
print("### overlapping / duplicate intervals (per turbine)")
rows = []
for (f, t), gg in iv.groupby(["farm", "turbine_id"]):
    gg = gg.sort_values("t0")
    prev_end = gg.t1.cummax().shift(1)
    rows.append({"farm": f, "turbine": t, "interval_events": len(gg),
                 "overlaps_prior": int((gg.t0 < prev_end).sum()),
                 "exact_dups": int(gg.duplicated(["t0", "t1", "Code"]).sum())})
ov = pd.DataFrame(rows)
print(ov.to_string(index=False))
print("### TOTAL overlapping %d / %d (%.1f%%) | exact dups %d"
      % (ov.overlaps_prior.sum(), ov.interval_events.sum(),
         100 * ov.overlaps_prior.sum() / ov.interval_events.sum(), ov.exact_dups.sum()))

# concurrency depth on stops only
print()
print("### max concurrent OPEN stop-intervals per turbine (first 6 turbines)")
stops_iv = iv[iv["Status"] == "Stop"]
for (f, t), gg in list(stops_iv.groupby(["farm", "turbine_id"]))[:6]:
    ev = pd.concat([pd.Series(1, index=gg.t0.values),
                    pd.Series(-1, index=gg.t1.values)]).sort_index()
    print(f"   {f} WT{t}: n={len(gg)} max concurrent = {ev.cumsum().max()}")

# ---------------------------------------------- curtailment vs fault in log
print()
print("### curtailment / grid-related messages")
pat = r"curtail|derat|grid|setpoint|set point|power limit|reduc|noise|shadow|bat|mains|external"
sel = st[msg.str.contains(pat, case=False, na=False)]
print(sel.groupby([sel["Message"], sel["Status"].fillna("<b>"),
                   sel["IEC category"].fillna("<b>"),
                   sel["Service contract category"].fillna("<b>")])
      .size().sort_values(ascending=False).head(30).to_string())

# ------------------------------------------------- commissioning / coverage
print()
print("### first/last event timestamp per turbine (commissioning proxy)")
print(st.groupby(["farm", "turbine_id"]).t0.agg(["min", "max", "size"]).to_string())
