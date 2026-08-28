#!/usr/bin/env python3
"""ONE pass over every Turbine_Data member in the corpus (the drive is slow, so
we only read it once). Produces:

  scada_coverage.csv  - per turbine-year: rows, grid integrity, per-signal non-null
                        %, annual energy sums, export batch, timezone line
  headers_by_member.csv - the full column list of every member (schema drift)
  fo_alignment.csv    - for every forced-outage STOP: offset between the logged
                        start/end and the SCADA 10-min grid, plus lost energy
                        computed three ways
"""
import io, os, sys, time, zipfile
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wtio

D = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
os.makedirs(D, exist_ok=True)

WANT = [
    "Date and time", "Wind speed (m/s)", "Power (kW)", "Energy Export (kWh)",
    "Potential power default PC (kW)", "Potential power learned PC (kW)",
    "Potential power reference turbines (kW)", "Potential power estimated (kW)",
    "Potential power MPC (kW)", "Potential power met mast anemometer (kW)",
    "Potential power primary reference turbines (kW)",
    "Potential power secondary reference turbines (kW)",
    "Potential power met mast anemometer MPC (kW)",
    "Cascading potential power (kW)", "Cascading potential power for performance (kW)",
    "Manufacturer Potential Power (SCADA) (kW)",
    "Lost Production to Downtime (kWh)", "Lost Production to Performance (kWh)",
    "Lost Production Total (kWh)", "Lost Production to Curtailment (Total) (kWh)",
    "Lost Production to Curtailment (Grid) (kWh)",
    "Lost Production to Curtailment (Technical) (kWh)",
    "Lost Production to Curtailment (Noise) (kWh)",
    "Lost Production to Curtailment (Shadow) (kWh)",
    "Lost Production to Curtailment (Ice) (kWh)",
    "Lost Production to Curtailment (Grid Constraint) (kWh)",
    "Lost Production (Time-based IEC B.2.2) (kWh)",
    "Energy Theoretical (kWh)", "Turbine Power setpoint (kW)",
    "Front bearing temperature (°C)", "Rear bearing temperature (°C)",
    "Gear oil temperature (°C)", "Gear oil inlet temperature (°C)",
    "Generator bearing front temperature (°C)",
    "Generator bearing rear temperature (°C)", "Stator temperature 1 (°C)",
    "Nacelle ambient temperature (°C)", "Transformer temperature (°C)",
    "Rotor speed (RPM)", "Generator RPM (RPM)", "Blade angle (pitch position) A (°)",
    "Nacelle position (°)", "Metal particle count", "Drive train acceleration (mm/ss)",
    "Drive train acceleration (mm/s2)",
    "Time-based System Avail.", "Data Availability",
]
ESUM = [c for c in WANT if c.endswith("(kWh)")]


def load_status():
    st = pd.read_parquet(os.path.join(D, "status_all.parquet"))
    st.columns = [c.strip() for c in st.columns]
    for c in ("Timestamp end", "Duration"):
        st[c] = st[c].replace("-", np.nan)
    st["t0"] = pd.to_datetime(st["Timestamp start"], errors="coerce", format="mixed")
    st["t1"] = pd.to_datetime(st["Timestamp end"], errors="coerce", format="mixed")
    st["year"] = st.t0.dt.year
    fo = st[(st["IEC category"] == "Forced outage") & (st["Status"] == "Stop")
            & st.t0.notna() & st.t1.notna()].copy()
    fo["dur_h"] = (fo.t1 - fo.t0).dt.total_seconds() / 3600
    return fo


def header_and_cols(zpath, member):
    pre, _, cols = wtio.peek(zpath, member, "Date and time")
    return pre, cols


def flush(rows, path):
    """Append rows to a CSV, writing the header only the first time."""
    if not rows:
        return []
    df = pd.DataFrame(rows)
    new = not os.path.exists(path)
    df.to_csv(path, mode="a", header=new, index=False)
    return []


def main():
    import gc
    fo = load_status()
    print("forced-outage stops to align:", len(fo))
    P_COV = os.path.join(D, "scada_coverage.csv")
    P_HDR = os.path.join(D, "headers_by_member.csv")
    P_ALI = os.path.join(D, "fo_alignment.csv")
    done = set()
    if os.path.exists(P_COV):
        prev = pd.read_csv(P_COV)
        done = set(prev.member)
        print("resuming; already profiled:", len(done), "members")
    cov, hdr, align = [], [], []
    t_start = time.time()
    for farm in ("kelmarsh", "penmanshiel"):
        for zpath in wtio.scada_zips(farm):
            zname = os.path.basename(zpath)
            with zipfile.ZipFile(zpath) as z:
                members = [i.filename for i in z.infolist()]
            for m in members:
                kind, tid, yr = wtio.parse_member_name(m)
                if kind != "scada" or os.path.basename(m) in done:
                    continue
                pre, cols = header_and_cols(zpath, m)
                for c in cols:
                    hdr.append({"farm": farm, "zip": zname, "member": os.path.basename(m),
                                "turbine": tid, "year": yr, "column": c})
                use = [c for c in WANT if c in cols]
                df = wtio.read_scada(zpath, m, usecols=use)
                df["Date and time"] = pd.to_datetime(df["Date and time"], errors="coerce")
                df = df.set_index("Date and time").sort_index()
                ts = pd.Series(df.index)
                dts = ts.diff().dt.total_seconds().dropna()
                span0, span1 = df.index.min(), df.index.max()
                exp = int((span1 - span0).total_seconds() // 600) + 1 if pd.notna(span0) else 0
                rec = {"farm": farm, "turbine": tid, "year": yr, "zip": zname,
                       "member": os.path.basename(m), "n_cols": len(cols),
                       "n_rows": len(df), "first_ts": span0, "last_ts": span1,
                       "modal_dt_s": float(dts.mode().iloc[0]) if len(dts) else np.nan,
                       "dt_not_600s": int((dts != 600).sum()),
                       "dup_ts": int(df.index.duplicated().sum()),
                       "expected_rows_in_span": exp,
                       "rows_vs_span_pct": round(100 * len(df) / exp, 2) if exp else np.nan,
                       "tz_line": next((l for l in pre if "Time zone" in l), "").strip("# \r"),
                       "export_line": next((l for l in pre if "exported by" in l), "").strip("# \r"),
                       "interval_line": next((l for l in pre if "Time interval" in l), "").strip("# \r")}
                # completeness is measured against the full 10-minute grid implied
                # by the member's own span, not against the rows that survive the
                # all-NaN padding filter
                den = exp if exp else len(df)
                for c in WANT[1:]:
                    rec["nn_" + c] = round(100 * df[c].notna().sum() / den, 2) if c in use else np.nan
                for c in ESUM:
                    if c in use:
                        rec["sumMWh_" + c] = round(float(df[c].sum()) / 1000, 3)
                cov.append(rec)

                # ---- alignment for this turbine-year -------------------------
                sub = fo[(fo.farm == farm) & (fo.turbine_id == tid) & (fo.year == yr)]
                if len(sub) and "Power (kW)" in df.columns:
                    pw = df["Power (kW)"]
                    down = pw.isna() | (pw <= 0)
                    up = pw > 50
                    has_c = "Cascading potential power (kW)" in df.columns
                    has_g = "Lost Production to Downtime (kWh)" in df.columns
                    has_cur = "Lost Production to Curtailment (Total) (kWh)" in df.columns
                    for ev in sub.itertuples():
                        w = down.loc[ev.t0: ev.t0 + pd.Timedelta(hours=6)]
                        fd = w[w].index.min() if w.any() else pd.NaT
                        u = up.loc[ev.t1: ev.t1 + pd.Timedelta(hours=6)]
                        fu = u[u].index.min() if u.any() else pd.NaT
                        win = df.loc[ev.t0: ev.t1]
                        a = {"farm": farm, "turbine": tid, "year": yr, "t0": ev.t0,
                             "dur_h": round(ev.dur_h, 3), "code": ev.Code,
                             "message": ev.Message,
                             "start_offset_min": np.nan if pd.isna(fd) else (fd - ev.t0).total_seconds() / 60,
                             "end_offset_min": np.nan if pd.isna(fu) else (fu - ev.t1).total_seconds() / 60,
                             "sec_into_bin": (ev.t0.minute % 10) * 60 + ev.t0.second,
                             "n_rows_in_window": len(win)}
                        if len(win):
                            a["frac_rows_down"] = round(float(
                                (win["Power (kW)"].isna() | (win["Power (kW)"] <= 0)).mean()), 3)
                            act = win["Power (kW)"].fillna(0).clip(lower=0)
                            if has_c:
                                a["casc_cov"] = round(float(win["Cascading potential power (kW)"].notna().mean()), 3)
                                a["lost_casc_MWh"] = round(float(
                                    (win["Cascading potential power (kW)"] - act).clip(lower=0).sum() * (10/60) / 1000), 4)
                            if "Potential power default PC (kW)" in df.columns:
                                a["lost_defaultPC_MWh"] = round(float(
                                    (win["Potential power default PC (kW)"] - act).clip(lower=0).sum() * (10/60) / 1000), 4)
                            if has_g:
                                a["lost_gb_MWh"] = round(float(win["Lost Production to Downtime (kWh)"].sum()) / 1000, 4)
                            if has_cur:
                                a["curtail_MWh"] = round(float(win["Lost Production to Curtailment (Total) (kWh)"].sum()) / 1000, 4)
                        align.append(a)
                print(f"[{time.time()-t_start:6.0f}s] {zname[:38]:38s} {os.path.basename(m)[:46]:46s} "
                      f"rows={len(df):6d} cols={len(cols)} fo={len(sub)}", flush=True)
                del df
                cov = flush(cov, P_COV)
                hdr = flush(hdr, P_HDR)
                align = flush(align, P_ALI)
                gc.collect()

    print("elapsed %.0f s" % (time.time() - t_start))
    for p in (P_COV, P_HDR, P_ALI):
        print(p, len(pd.read_csv(p)), "rows")


if __name__ == "__main__":
    main()
