#!/usr/bin/env python3
"""Feasibility smoke test (NOT the analysis).

For a sample of forced-outage stops:
  (a) lost energy over the outage from the potential-power columns, cross-checked
      against Greenbyte's own 'Lost Production to Downtime';
  (b) precursor signatures in the preceding 72 h --
        * SCADA: temperature residual drift (component temp minus nacelle ambient,
          producing rows only), scored as max |z| of a 6 h rolling mean against a
          28 d baseline that ends where the 72 h window begins;
        * SCADA: power-curve deviation (potential vs actual while producing);
        * LOG: does the status log itself carry a Warning / non-Full-Performance
          row for this turbine inside the 72 h?

Two panels are scored: a RANDOM sample of forced-outage stops (what the corpus
actually looks like) and a COMPONENT-FAULT sample (excluding manual/remote/grid
stops) which gives the precursor hypothesis its best shot.
"""
import io, os, re, sys, zipfile
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wtio

D = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
PRE_H, BASE_D, MIN_OUTAGE_H, N = 72, 28, 6, 20

TEMPS = ["Front bearing temperature (°C)", "Rear bearing temperature (°C)",
         "Gear oil temperature (°C)", "Generator bearing front temperature (°C)",
         "Generator bearing rear temperature (°C)", "Stator temperature 1 (°C)",
         "Transformer temperature (°C)", "Gear oil inlet temperature (°C)"]
BASE_COLS = ["Date and time", "Wind speed (m/s)", "Power (kW)",
             "Nacelle ambient temperature (°C)",
             "Potential power default PC (kW)", "Cascading potential power (kW)",
             "Lost Production to Downtime (kWh)", "Lost Production Total (kWh)",
             "Lost Production to Curtailment (Total) (kWh)"]
AMB = "Nacelle ambient temperature (°C)"

# messages with no plausible turbine-side physical precursor: human actions,
# grid events, and weather. Everything else is a candidate component fault.
NON_PHYSICAL = re.compile(
    r"manual stop|remote stop|externally stopped|external stop|"
    r"grid loss|grid error|grid constraint|grid disconnection|mains failure|"
    r"maximum grid frequency|minimum grid frequency|"
    r"wind <|max\. wind|absence of wind|storm|ice |icing|shadow|noise|curtail|"
    r"emergency stop|maintenance|autounwind", re.I)

_index = None
_cache = {}


def build_index():
    """member index: (farm, turbine, year) -> [(zip, member)]"""
    global _index
    if _index is not None:
        return _index
    _index = {}
    for farm in ("kelmarsh", "penmanshiel"):
        for zpath in wtio.scada_zips(farm):
            with zipfile.ZipFile(zpath) as z:
                for i in z.infolist():
                    kind, tid, yr = wtio.parse_member_name(i.filename)
                    if kind == "scada":
                        _index.setdefault((farm, tid, yr), []).append((zpath, i.filename))
    return _index


def load_year(farm, turbine, year):
    key = (farm, turbine, year)
    if key in _cache:
        return _cache[key]
    frames = []
    for zpath, m in build_index().get(key, []):
        _, _, cols = wtio.peek(zpath, m, "Date and time")
        use = [c for c in BASE_COLS + TEMPS if c in cols]
        df = wtio.read_scada(zpath, m, usecols=use)
        df["Date and time"] = pd.to_datetime(df["Date and time"], errors="coerce")
        frames.append(df.set_index("Date and time").sort_index())
    out = pd.concat(frames).sort_index() if frames else None
    if len(_cache) > 8:
        _cache.clear()
    _cache[key] = out
    return out


def score_event(ev, log):
    farm, t, t0, t1 = ev.farm, ev.turbine_id, ev.t0, ev.t1
    years = {t0.year, (t0 - pd.Timedelta(days=BASE_D + 4)).year}
    parts = [p for p in (load_year(farm, t, y) for y in years) if p is not None]
    if not parts:
        return None
    sc = pd.concat(parts).sort_index()
    sc = sc[~sc.index.duplicated()]

    pre = sc.loc[t0 - pd.Timedelta(hours=PRE_H): t0]
    base = sc.loc[t0 - pd.Timedelta(days=BASE_D) - pd.Timedelta(hours=PRE_H):
                  t0 - pd.Timedelta(hours=PRE_H)]
    out = sc.loc[t0:t1]
    if len(pre) < 100 or len(base) < 1000:
        return None

    r = {"farm": farm, "turbine": t, "start": t0, "dur_h": round(ev.dur_h, 2),
         "code": ev.Code, "message": ev.Message,
         "n_pre": len(pre), "n_out": len(out)}

    # ---- lost energy -----------------------------------------------------
    act = out["Power (kW)"].fillna(0).clip(lower=0)
    for label, col in (("cascading", "Cascading potential power (kW)"),
                       ("defaultPC", "Potential power default PC (kW)")):
        if col in out.columns:
            r[f"lostMWh_{label}"] = round(
                float((out[col] - act).clip(lower=0).sum() * (10 / 60) / 1000), 3)
            r[f"cov_{label}_pct"] = round(100 * out[col].notna().mean(), 1)
    if "Lost Production to Downtime (kWh)" in out.columns:
        r["lostMWh_greenbyte"] = round(
            float(out["Lost Production to Downtime (kWh)"].sum()) / 1000, 3)
    if "Lost Production to Curtailment (Total) (kWh)" in out.columns:
        r["curtailMWh_in_window"] = round(
            float(out["Lost Production to Curtailment (Total) (kWh)"].sum()) / 1000, 3)
    r["mean_ws_outage"] = round(float(out["Wind speed (m/s)"].mean()), 2)

    # ---- SCADA precursors ------------------------------------------------
    prod = lambda d: d[(d["Power (kW)"] > 100) & d["Power (kW)"].notna()]
    bp, pp = prod(base), prod(pre)
    r["n_pre_producing"] = len(pp)

    best, bestname = 0.0, None
    for c in TEMPS:
        if c not in sc.columns or AMB not in sc.columns:
            continue
        b = (bp[c] - bp[AMB]).dropna()
        p = (pp[c] - pp[AMB]).dropna()
        if len(b) < 300 or len(p) < 20 or b.std() == 0:
            continue
        roll = p.rolling(36, min_periods=12).mean().dropna()   # 6 h of 10-min rows
        if roll.empty:
            continue
        z = float(((roll - b.mean()) / b.std()).abs().max())
        sgn = np.sign(((roll - b.mean()) / b.std()).iloc[
            int(np.argmax(np.abs((roll - b.mean()) / b.std())))])
        r["z_" + c.split(" (")[0]] = round(z * sgn, 2)
        if z > abs(best):
            best, bestname = z, c.split(" (")[0]
    r["max_temp_z"] = round(best, 2)
    r["max_temp_channel"] = bestname

    col = "Cascading potential power (kW)"
    if col in sc.columns:
        def resid(d):
            p = d[col]
            ok = p > 100
            return ((p[ok] - d["Power (kW)"][ok]) / p[ok]).dropna()
        b, p = resid(bp), resid(pp)
        if len(b) > 300 and len(p) > 20 and b.std() > 0:
            roll = p.rolling(36, min_periods=12).mean().dropna()
            if not roll.empty:
                r["pc_resid_base"] = round(float(b.mean()), 4)
                r["pc_resid_pre"] = round(float(p.mean()), 4)
                r["z_power_curve"] = round(
                    float(((roll - b.mean()) / b.std()).abs().max()), 2)

    # ---- LOG precursors: warnings on this turbine in the 72 h ------------
    w = log[(log.farm == farm) & (log.turbine_id == t) &
            (log.t0 >= t0 - pd.Timedelta(hours=PRE_H)) & (log.t0 < t0)]
    r["log_rows_72h"] = len(w)
    r["log_warnings_72h"] = int((w["Status"] == "Warning").sum())
    r["log_stops_72h"] = int((w["Status"] == "Stop").sum())
    r["log_same_code_72h"] = int((w["Code"] == ev.Code).sum())
    prior = w[w["Status"] == "Warning"]
    r["log_first_warning_lead_h"] = (
        round(float((t0 - prior.t0.min()).total_seconds() / 3600), 2)
        if len(prior) else np.nan)
    r["log_warning_msgs"] = " | ".join(prior["Message"].dropna().unique()[:4])
    return r


def run_panel(name, sample, log):
    print(f"\n===================== PANEL: {name}  (n={len(sample)}) ==================")
    recs = []
    for ev in sample.itertuples():
        try:
            r = score_event(ev, log)
        except Exception as e:
            print("  ERR", ev.farm, ev.turbine_id, ev.t0, repr(e)[:110]); r = None
        if r:
            recs.append(r)
            print(f"  {r['farm'][:4]} WT{r['turbine']:<2} {r['start']} {r['dur_h']:7.1f}h "
                  f"lost={r.get('lostMWh_cascading'):8.2f}MWh tempZ={r['max_temp_z']:5.2f}"
                  f"({str(r['max_temp_channel'])[:22]:22s}) pcZ={str(r.get('z_power_curve')):>5s} "
                  f"warn72h={r['log_warnings_72h']:>3d} lead={str(r['log_first_warning_lead_h']):>6s} "
                  f"| {str(r['message'])[:34]}", flush=True)
    res = pd.DataFrame(recs)
    if res.empty:
        return res
    res.to_csv(os.path.join(D, f"smoke_{name}.csv"), index=False)
    pcz = res.get("z_power_curve", pd.Series(np.nan, index=res.index))
    print(f"  -- {name}: scored {len(res)}")
    print(f"     temp z>3: {int((res.max_temp_z>3).sum())}   temp z>2: {int((res.max_temp_z>2).sum())}")
    print(f"     power-curve z>3: {int((pcz>3).sum())}  z>2: {int((pcz>2).sum())} (of {int(pcz.notna().sum())})")
    print(f"     SCADA precursor (tempZ>3 or pcZ>3): {int(((res.max_temp_z>3)|(pcz>3)).sum())}/{len(res)}")
    print(f"     LOG warning in 72h: {int((res.log_warnings_72h>0).sum())}/{len(res)}"
          f"   median lead {res.log_first_warning_lead_h.median():.1f} h")
    print(f"     lost MWh: total {res.lostMWh_cascading.sum():.1f}  "
          f"median {res.lostMWh_cascading.median():.2f}  max {res.lostMWh_cascading.max():.1f}")
    print(f"     greenbyte cross-check total {res.lostMWh_greenbyte.sum():.1f} MWh "
          f"(cascading {res.lostMWh_cascading.sum():.1f})")
    print(f"     curtailment inside outage windows: {res.curtailMWh_in_window.sum():.3f} MWh")
    return res


def main():
    st = pd.read_parquet(os.path.join(D, "status_all.parquet"))
    st.columns = [c.strip() for c in st.columns]
    for c in ("Timestamp end", "Duration"):
        st[c] = st[c].replace("-", np.nan)
    st["t0"] = pd.to_datetime(st["Timestamp start"], errors="coerce", format="mixed")
    st["t1"] = pd.to_datetime(st["Timestamp end"], errors="coerce", format="mixed")

    fo = st[(st["IEC category"] == "Forced outage") & (st["Status"] == "Stop")
            & st.t0.notna() & st.t1.notna()].copy()
    fo["dur_h"] = (fo.t1 - fo.t0).dt.total_seconds() / 3600
    fo = fo[(fo.dur_h >= MIN_OUTAGE_H) &
            (fo.t0.dt.dayofyear > 40) & (fo.t0.dt.dayofyear < 355)]
    print("forced-outage STOPS >= %dh, away from file edges: %d" % (MIN_OUTAGE_H, len(fo)))
    print("\nmessage mix of that pool (top 15):")
    print(fo["Message"].value_counts().head(15).to_string())

    rng = np.random.default_rng(20260827)

    def pick(pool, n):
        out = []
        for farm in ("kelmarsh", "penmanshiel"):
            sub = pool[pool.farm == farm]
            if len(sub):
                out.extend(rng.choice(sub.index, min(n // 2, len(sub)), replace=False))
        return pool.loc[out].sort_values(["farm", "turbine_id", "t0"])

    p1 = pick(fo, N)
    comp = fo[~fo["Message"].fillna("").str.contains(NON_PHYSICAL)]
    print("\ncomponent-fault pool (manual/grid/env messages removed): %d" % len(comp))
    print(comp["Message"].value_counts().head(15).to_string())
    p2 = pick(comp, N)

    log = st[["farm", "turbine_id", "t0", "Status", "Code", "Message"]]
    r1 = run_panel("random_forced_outages", p1, log)
    r2 = run_panel("component_fault_outages", p2, log)

    # ---- CONTROL: identical statistic at quiet times ---------------------
    # max|z| over a 6 h rolling mean across 12 windows is a maximum statistic;
    # it exceeds 2 often under the null. Without this panel the numbers above
    # are uninterpretable.
    allfo = st[(st["IEC category"] == "Forced outage") & (st["Status"] == "Stop")
               & st.t0.notna()]
    ctrl = []
    for ev in pd.concat([p1, p2]).drop_duplicates().itertuples():
        for shift in (45, 90, 135):
            t0 = ev.t0 - pd.Timedelta(days=shift)
            near = allfo[(allfo.farm == ev.farm) & (allfo.turbine_id == ev.turbine_id) &
                         (allfo.t0 > t0 - pd.Timedelta(days=3)) &
                         (allfo.t0 < t0 + pd.Timedelta(days=3))]
            if len(near):
                continue
            ctrl.append({"farm": ev.farm, "turbine_id": ev.turbine_id, "t0": t0,
                         "t1": t0 + pd.Timedelta(hours=12), "dur_h": 12.0,
                         "Code": -1, "Message": "<control: no forced outage>"})
            break
    cdf = pd.DataFrame(ctrl)
    r3 = run_panel("control_quiet_periods", cdf, log) if len(cdf) else pd.DataFrame()

    print("\n================= VERDICT =================")
    for nm, r in (("random", r1), ("component-fault", r2), ("CONTROL", r3)):
        if r is None or r.empty:
            continue
        pcz = r.get("z_power_curve", pd.Series(np.nan, index=r.index))
        scada = int(((r.max_temp_z > 3) | (pcz > 3)).sum())
        logw = int((r.log_warnings_72h > 0).sum())
        print(f"{nm:16s} n={len(r):2d}  tempZ>3 {int((r.max_temp_z>3).sum()):2d}  "
              f"tempZ>2 {int((r.max_temp_z>2).sum()):2d}  SCADA precursor {scada}/{len(r)}  "
              f"LOG warning in 72h {logw}/{len(r)}  "
              f"median tempZ {r.max_temp_z.median():.2f}  "
              f"lost {r.lostMWh_cascading.sum():.0f} MWh")


if __name__ == "__main__":
    main()
