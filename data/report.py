#!/usr/bin/env python3
"""Turn the derived CSVs into the numbers that go into PROFILE.md."""
import os, sys
import numpy as np
import pandas as pd
pd.set_option("display.width", 260, "display.max_rows", 500, "display.max_colwidth", 55)

D = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")


def sec(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


# ---------------------------------------------------------------- inventory
sec("1. ZIP INVENTORY / DISK")
inv = pd.read_csv(os.path.join(D, "zip_inventory.csv"))
print(inv.groupby(["farm", "kind"]).agg(
    members=("member", "size"),
    uncompressed_GB=("uncompressed_bytes", lambda s: round(s.sum() / 1e9, 2)),
    compressed_GB=("compressed_bytes", lambda s: round(s.sum() / 1e9, 2))).to_string())
print("\nTOTAL uncompressed if fully extracted: %.2f GB   (zips on disk: %.2f GB)"
      % (inv.uncompressed_bytes.sum() / 1e9, inv.compressed_bytes.sum() / 1e9))
print("median Turbine_Data member size: %.1f MB"
      % (inv[inv.kind == "scada"].uncompressed_bytes.median() / 1e6))

# ---------------------------------------------------------------- coverage
sec("2. SCADA COVERAGE PER TURBINE-YEAR")
cv = pd.read_csv(os.path.join(D, "scada_coverage.csv"), parse_dates=["first_ts", "last_ts"])
print("turbine-years:", len(cv), "| turbines:", cv.groupby(["farm", "turbine"]).ngroups)
print("timezone lines seen:", cv.tz_line.value_counts().to_dict())
print("\nexport batches (Greenbyte export DATE -> members, farms, years, column count):")
cv["export_date"] = cv.export_line.str.extract(r"at (\d{4}-\d\d-\d\d)")[0]
print(cv.groupby("export_date").agg(
    n=("member", "size"),
    farms=("farm", lambda s: sorted(s.unique())),
    years=("year", lambda s: sorted(s.unique())),
    n_cols=("n_cols", lambda s: sorted(s.unique()))).to_string())
print("\ngrid integrity: rows with dt != 600 s:", int(cv.dt_not_600s.sum()),
      "| duplicate timestamps:", int(cv.dup_ts.sum()),
      "| modal dt values:", cv.modal_dt_s.value_counts().to_dict())
print("\nn_cols per year (schema drift):")
print(cv.groupby(["farm", "year"]).n_cols.agg(["min", "max"]).to_string())

key = ["nn_Power (kW)", "nn_Wind speed (m/s)", "nn_Cascading potential power (kW)",
       "nn_Potential power default PC (kW)", "nn_Lost Production to Downtime (kWh)",
       "nn_Front bearing temperature (°C)", "nn_Gear oil temperature (°C)",
       "nn_Generator bearing front temperature (°C)",
       "nn_Nacelle ambient temperature (°C)", "nn_Metal particle count"]
print("\nnon-null %% of key signals, by farm-year (mean over turbines):")
print(cv.groupby(["farm", "year"])[[c for c in key if c in cv.columns]]
        .mean().round(1).to_string())
print("\nper-turbine-year Power(kW) non-null %% distribution:")
print(cv["nn_Power (kW)"].describe(percentiles=[.05, .25, .5, .75, .95]).to_string())
print("worst 12 turbine-years by Power coverage:")
print(cv.nsmallest(12, "nn_Power (kW)")[
    ["farm", "turbine", "year", "n_rows", "first_ts", "last_ts",
     "nn_Power (kW)", "nn_Cascading potential power (kW)"]].to_string(index=False))

print("\ncoverage of the potential-power family (mean non-null %% over all turbine-years):")
pp = [c for c in cv.columns if c.startswith("nn_") and
      ("otential power" in c or "Cascading" in c or "Potential Power" in c)]
print(cv[pp].mean().round(1).sort_values(ascending=False).to_string())

sec("3. ENERGY ACCOUNTING (corpus totals from the SCADA columns)")
es = [c for c in cv.columns if c.startswith("sumMWh_")]
tot = cv[es].sum().sort_values(ascending=False)
print(tot.round(1).to_string())
if "sumMWh_Energy Export (kWh)" in cv.columns:
    gen = cv["sumMWh_Energy Export (kWh)"].sum()
    dwn = cv.get("sumMWh_Lost Production to Downtime (kWh)", pd.Series([np.nan])).sum()
    cur = cv.get("sumMWh_Lost Production to Curtailment (Total) (kWh)", pd.Series([np.nan])).sum()
    print("\nGenerated %.0f MWh | lost to downtime %.0f MWh (%.2f%% of gross) | "
          "curtailment %.0f MWh" % (gen, dwn, 100 * dwn / (gen + dwn), cur))
print("\ncurtailment by farm-year (MWh):")
cc = [c for c in cv.columns if "Curtailment" in c and c.startswith("sumMWh_")]
print(cv.groupby(["farm", "year"])[cc].sum().round(1).to_string())

# ---------------------------------------------------------------- headers
sec("4. SIGNAL AVAILABILITY / SCHEMA DRIFT")
h = pd.read_csv(os.path.join(D, "headers_by_member.csv"))
print("distinct column names across the corpus:", h.column.nunique())
piv = h.assign(v=1).pivot_table(index="column", columns=["farm", "year"],
                                values="v", aggfunc="max").fillna(0)
always = piv.index[(piv == 1).all(axis=1)]
never = piv.index[(piv == 1).sum(axis=1) < len(piv.columns)]
print("columns present in EVERY farm-year:", len(always))
print("columns NOT present in every farm-year:", len(never))
print("\nthose that vary (first 60):")
sub = piv.loc[never]
print(sub.astype(int).to_string()[:6000])

# ---------------------------------------------------------------- alignment
sec("5. STATUS-LOG <-> SCADA ALIGNMENT (forced-outage stops)")
al = pd.read_csv(os.path.join(D, "fo_alignment.csv"), parse_dates=["t0"])
print("alignment records:", len(al))
print("\nstart_offset_min (logged start -> first SCADA row with turbine down):")
print(al.start_offset_min.describe(percentiles=[.05, .25, .5, .75, .9, .95]).to_string())
print("  <=10 min: %.1f%%  <=20 min: %.1f%%  not down within 6 h: %d (%.1f%%)"
      % ((al.start_offset_min <= 10).mean() * 100, (al.start_offset_min <= 20).mean() * 100,
         int(al.start_offset_min.isna().sum()), al.start_offset_min.isna().mean() * 100))
print("\nend_offset_min (logged end -> first SCADA row producing >50 kW):")
print(al.end_offset_min.describe(percentiles=[.05, .25, .5, .75, .9, .95]).to_string())
print("\nsub-bin phase of logged start (seconds into the 10-min bin):")
print(al.sec_into_bin.describe().to_string())
print("  exactly on a 10-min boundary: %.2f%%" % ((al.sec_into_bin == 0).mean() * 100))
print("\nfraction of SCADA rows inside the logged window showing the turbine down:")
print(al.frac_rows_down.describe().to_string())
print("  events where <50%% of rows show the turbine down: %d of %d (%.1f%%)"
      % (int((al.frac_rows_down < 0.5).sum()), len(al),
         (al.frac_rows_down < 0.5).mean() * 100))

sec("6. LOST ENERGY OVER FORCED-OUTAGE STOPS (whole corpus)")
for c in ("lost_casc_MWh", "lost_defaultPC_MWh", "lost_gb_MWh", "curtail_MWh"):
    if c in al.columns:
        print(f"  total {c:22s} = {al[c].sum():10.1f} MWh")
print("\nper-event lost MWh (cascading):")
print(al.lost_casc_MWh.describe(percentiles=[.5, .75, .9, .99]).to_string())
if {"lost_casc_MWh", "lost_gb_MWh"} <= set(al.columns):
    ok = al.dropna(subset=["lost_casc_MWh", "lost_gb_MWh"])
    d = (ok.lost_casc_MWh - ok.lost_gb_MWh)
    print("\ncascading vs Greenbyte per event: mean abs diff %.4f MWh, "
          "corr %.5f, ratio of totals %.4f"
          % (d.abs().mean(), ok.lost_casc_MWh.corr(ok.lost_gb_MWh),
             ok.lost_casc_MWh.sum() / ok.lost_gb_MWh.sum()))
    print("events where defaultPC understates cascading by >1 MWh:",
          int(((al.lost_casc_MWh - al.lost_defaultPC_MWh) > 1).sum()))
print("\ntop 15 forced outages by lost energy:")
print(al.nlargest(15, "lost_casc_MWh")[
    ["farm", "turbine", "t0", "dur_h", "lost_casc_MWh", "lost_gb_MWh",
     "message"]].to_string(index=False))
print("\nlost energy by message (top 20 by total MWh):")
print(al.groupby("message").agg(n=("dur_h", "size"), hours=("dur_h", "sum"),
                                MWh=("lost_casc_MWh", "sum"))
        .sort_values("MWh", ascending=False).head(20).round(1).to_string())
