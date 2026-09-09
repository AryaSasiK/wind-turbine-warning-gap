#!/usr/bin/env python3
"""merge_predicate_sensitivity.csv - does "overlapping" include "touching"?

The frozen prose describes the event definition as merging overlapping/nested
stop intervals per turbine. The frozen CODE (common.py::merge_intervals) is
slightly more permissive: it starts a new event only when t0 > running max end,
so a stop that begins at the exact instant the previous one ends is ABSORBED
rather than treated as a new event. That is an undisclosed implementation
choice, and this script measures it.

Both predicates are rebuilt here from the raw stop rows, all the way through:

  1. base population   Status == 'Stop' AND IEC category == 'Forced outage'
  2. both timestamps present, end >= start
  3. exact duplicates dropped on (farm, turbine, t0, t1, code)
  4. pre-commissioning rows dropped (Kelmarsh < 2016-04-15, Penmanshiel < 2016-09-01)
  5. MERGE per turbine, under
        overlap_or_touch  new event when t0 >  running max end   (frozen code)
        strict_overlap    new event when t0 >= running max end   (frozen prose)
  6. T2 wide-grid tiering on the merged event (dropped only when every
     constituent message is grid-extended or manual)
  7. lost energy over the merged window, build_events.py's definition
  8. warning attribution at 72 h against warnings.parquet, half-open
     [start - 72 h, start), warnings placed by their start timestamp, the
     same-component rule excluding the external/grid/manual families
  9. long-lead share at T_lead = 6 h, energy-weighted

Reads (read-only):
  $WTWG_DERIVED/status_all.parquet    (frozen pooled status log)
  $WTWG_DERIVED/warnings.parquet      (frozen warning extract)
  $WTWG_DERIVED/events.parquet        (frozen stage-1, used only to VERIFY the
                                       rebuild reproduces it row for row)
  $WTWG_DERIVED/scada_min/*.parquet   (frozen 10-minute SCADA cache)
  analysis/component_map.csv          (frozen component map)

Nothing is imported from the pipeline and no pipeline main() is run, so no
frozen artefact can be disturbed. Writes merge_predicate_sensitivity.csv beside
this file.

Column note: `strict_long_lead_pct` and `permissive_long_lead_pct` are the two
MATCHING rules (same-component and any-warning). They are unrelated to the two
merge predicates, which are the rows.
"""
import os

import numpy as np
import pandas as pd

A = os.path.dirname(os.path.abspath(__file__)) + "/"
D = os.environ.get("WTWG_DERIVED",
                   os.path.join("wind-turbine-warning-gap-data", "derived")) + "/"
OUT = A

# --- study-design constants, reproduced from common.py (not imported) --------
BASE_STATUS = "Stop"
BASE_IEC = "Forced outage"
COD = {"kelmarsh": pd.Timestamp("2016-04-15"),
       "penmanshiel": pd.Timestamp("2016-09-01")}
GRID_MESSAGES = {"Externally stopped", "Grid loss", "Grid error",
                 "Grid disconnection for self-protection"}
GRID_MESSAGES_EXTRA = {"Maximum grid frequency"}          # the WIDE grid rule
MANUAL_MESSAGES = {"Manual stop - remote", "Manual stop - on site"}
NEVER_MATCH = frozenset({"external", "grid", "manual"})   # attribute.py

TS = "Date and time"
POWER = "Power (kW)"
POT = "Cascading potential power (kW)"
BIN_HOURS = 10.0 / 60.0

LOOKBACK_H = 72.0
T_LEAD_H = 6.0


# --------------------------------------------------------------- stop rows
def stop_rows():
    st = pd.read_parquet(D + "status_all.parquet")
    st.columns = [c.strip() for c in st.columns]
    st["Message"] = st["Message"].str.strip()
    for c in ("Timestamp end", "Duration"):
        st[c] = st[c].replace("-", np.nan)
    st["t0"] = pd.to_datetime(st["Timestamp start"], errors="coerce", format="mixed")
    st["t1"] = pd.to_datetime(st["Timestamp end"], errors="coerce", format="mixed")

    fo = st[(st["Status"] == BASE_STATUS) & (st["IEC category"] == BASE_IEC)].copy()
    fo = fo[fo["t0"].notna() & fo["t1"].notna()]
    fo = fo[~(fo["t1"] < fo["t0"])]
    fo = fo[~fo.duplicated(["farm", "turbine_id", "t0", "t1", "Code"], keep="first")]
    pre = pd.Series(False, index=fo.index)
    for farm, cod in COD.items():
        pre |= (fo["farm"] == farm) & (fo["t0"] < cod)
    return fo[~pre].copy()


def merge(df, predicate):
    """Assign merge-group ids per turbine under one of the two predicates."""
    df = df.sort_values(["farm", "turbine_id", "t0", "t1"]).copy()
    g = df.groupby(["farm", "turbine_id"], sort=False)
    run_end = g["t1"].cummax().shift(1)
    first = g.cumcount() == 0
    if predicate == "overlap_or_touch":          # frozen code: merge if t0 <= end
        starts_new = first | (df["t0"] > run_end)
    elif predicate == "strict_overlap":          # frozen prose: merge if t0 < end
        starts_new = first | (df["t0"] >= run_end)
    else:
        raise ValueError(predicate)
    df["group"] = starts_new.cumsum() - 1
    df["run_end_before"] = run_end
    return df


def collapse(series):
    seen, out = set(), []
    for v in series:
        if pd.isna(v):
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def build_events(f, fam_stop):
    f = f.copy()
    f["is_grid_ext"] = f["Message"].isin(GRID_MESSAGES | GRID_MESSAGES_EXTRA)
    f["is_manual"] = f["Message"].isin(MANUAL_MESSAGES)
    g = f.groupby("group", sort=True)
    ev = pd.DataFrame({
        "farm": g["farm"].first(),
        "turbine_id": g["turbine_id"].first(),
        "start": g["t0"].min(),
        "end": g["t1"].max(),
        "n_stops": g.size(),
        "messages": g["Message"].apply(collapse),
        "n_grid_ext_msgs": g["is_grid_ext"].sum(),
        "n_manual_msgs": g["is_manual"].sum(),
    }).reset_index()
    ev["duration_h"] = (ev["end"] - ev["start"]).dt.total_seconds() / 3600.0
    ev["T2_wide_grid"] = ~((ev["n_grid_ext_msgs"] + ev["n_manual_msgs"])
                           == ev["n_stops"])
    ev["fam_set"] = ev["messages"].apply(lambda ms: frozenset(fam_stop[m] for m in ms))
    return ev


def add_energy(ev):
    """build_events.py's energy: window sliced [start, end] on the bin START."""
    E = np.zeros(len(ev))
    for (farm, tid), grp in ev.groupby(["farm", "turbine_id"], sort=True):
        sc = (pd.read_parquet(os.path.join(D, "scada_min",
                                           f"{farm}_WT{int(tid):02d}.parquet"))
              .set_index(TS).sort_index())
        for i, t0, t1 in zip(grp.index, grp["start"], grp["end"]):
            w = sc.loc[t0:t1]
            if len(w) == 0:
                continue
            p = w[POT]
            a = w[POWER].fillna(0.0).clip(lower=0.0)
            E[i] = float((p - a).clip(lower=0.0).sum() * BIN_HOURS / 1000.0)
    ev = ev.copy()
    ev["E_mwh"] = E
    return ev


def attribute(ev, warns):
    """attribute.py's rule at one lookback: half-open [anchor - L, anchor)."""
    n = len(ev)
    out = dict(any_warn=np.zeros(n, bool), any_lead=np.full(n, np.nan),
               same_warn=np.zeros(n, bool), same_lead=np.full(n, np.nan))
    for (farm, tid), grp in ev.groupby(["farm", "turbine_id"], sort=False):
        wt = warns[(warns["farm"] == farm) & (warns["turbine_id"] == tid)]
        if len(wt) == 0:
            continue
        wt = wt.sort_values("start")
        w_ns = wt["start"].values.astype("datetime64[ns]").astype("int64")
        w_fam = wt["family"].values
        for i, anchor, famset in zip(grp.index, grp["start"], grp["fam_set"]):
            a_ns = np.datetime64(anchor, "ns").astype("int64")
            lo = a_ns - int(LOOKBACK_H * 3600 * 1e9)
            s = np.searchsorted(w_ns, lo, side="left")
            e = np.searchsorted(w_ns, a_ns, side="left")
            if s == e:
                continue
            out["any_warn"][i] = True
            out["any_lead"][i] = (a_ns - w_ns[s]) / 3.6e12
            ok = np.array([(f in famset) and (f not in NEVER_MATCH)
                           for f in w_fam[s:e]], dtype=bool)
            if ok.any():
                j = s + int(np.flatnonzero(ok)[0])
                out["same_warn"][i] = True
                out["same_lead"][i] = (a_ns - w_ns[j]) / 3.6e12
    return out


# ------------------------------------------------------------------- rebuild
cm = pd.read_csv(A + "component_map.csv")
fam_stop = cm[cm.role.isin(("stop", "both"))].set_index("message")["family"]
warns = pd.read_parquet(D + "warnings.parquet")
fo = stop_rows()

res = {}
for predicate in ("overlap_or_touch", "strict_overlap"):
    f = merge(fo, predicate)
    ev = add_energy(build_events(f, fam_stop))
    att = attribute(ev, warns)
    m = ev["T2_wide_grid"].values
    E = ev["E_mwh"].values
    tot = float(E[m].sum())
    ll_same = float(E[m & att["same_warn"] & (att["same_lead"] >= T_LEAD_H)].sum())
    ll_any = float(E[m & att["any_warn"] & (att["any_lead"] >= T_LEAD_H)].sum())
    res[predicate] = dict(stops=f, events=ev, att=att, n=int(m.sum()), E=tot,
                          ll_same=ll_same, ll_any=ll_any,
                          same_pct=100 * ll_same / tot, any_pct=100 * ll_any / tot)

# --- the rebuild must reproduce the frozen stage-1 parquet row for row -------
froz = pd.read_parquet(D + "events.parquet")
rb = res["overlap_or_touch"]["events"]
assert len(rb) == len(froz), (len(rb), len(froz))
assert (rb["start"].values == froz["start"].values).all()
assert (rb["end"].values == froz["end"].values).all()
assert (rb["T2_wide_grid"].values == froz["T2_wide_grid"].values).all()
assert np.allclose(rb["E_mwh"].values, froz["E_mwh"].values, rtol=0, atol=1e-9)
# group id == frozen event_id, so frozen ids can be quoted below
assert (rb["group"].values == froz["event_id"].values).all()

# ------------------------------------------------- which absorbed rows abut
fP = res["overlap_or_touch"]["stops"]
gP = fP.groupby(["farm", "turbine_id"], sort=False)
absorbed = fP[~((gP.cumcount() == 0) | (fP["t0"] > fP["run_end_before"]))]
abut = absorbed[absorbed["t0"] == absorbed["run_end_before"]]
n_absorbed_perm = len(absorbed)
n_absorbed_strict = len(res["strict_overlap"]["stops"]) - res["strict_overlap"]["events"].shape[0]
affected = sorted(int(x) for x in abut["group"].unique())          # frozen ids
aff_turbines = sorted({f"{r.farm} WT{int(r.turbine_id):02d}"
                       for _, r in abut.iterrows()})

evP, evS = res["overlap_or_touch"]["events"], res["strict_overlap"]["events"]
pieces = {}
for eid in affected:
    r = evP[evP.group == eid].iloc[0]
    p = evS[(evS.farm == r.farm) & (evS.turbine_id == r.turbine_id)
            & (evS.start >= r.start) & (evS.end <= r.end)]
    pieces[eid] = (r, p)

NOTE_PERM = (
    "frozen code (common.py::merge_intervals): a stop joins the running event "
    "when t0 <= the running max end, so a stop that starts at the exact instant "
    f"the previous one ends is absorbed. {len(abut)} of the {n_absorbed_perm} "
    "absorbed stop rows are absorbed on that abutting condition alone; the other "
    f"{n_absorbed_perm - len(abut)} genuinely overlap. This is the manuscript's "
    "primary population: 4,213 events / 9,386.5 MWh.")
NOTE_STRICT = (
    "frozen prose reading: a stop joins only when t0 < the running max end, so "
    f"the {len(abut)} abutting rows open their own events and 4,213 becomes "
    "4,216. Splitting a window re-charges the shared boundary bin, so measured "
    "energy rises 0.603 MWh. Same-component long-lead falls 0.400 pp and the "
    "whole move is one event: Penmanshiel WT15 2024-04-17 (frozen event 6025, "
    "53.035 MWh) splits into a safety-only piece (37.752 MWh) with no "
    "same-component match and a 15.541 MWh piece that keeps the match, taking "
    "same-component long-lead energy from 706.632 to 669.138 MWh. Any-warning "
    "long-lead RISES 1.140 pp, so the stricter predicate is not uniformly "
    "conservative; that move is Kelmarsh WT06 2024-04-15 (frozen event 1185, "
    "150.153 MWh) splitting three ways (7.158 / 36.354 / 106.986 MWh), whose "
    "106.986 MWh piece gains an any-warning match at 27.157 h lead and supplies "
    "106.986 of the +107.244 MWh.")

rows = []
for predicate, note, n_abut in (("overlap_or_touch", NOTE_PERM, len(abut)),
                                ("strict_overlap", NOTE_STRICT, 0)):
    r = res[predicate]
    rows.append(dict(
        predicate=predicate,
        n_events_T2=r["n"],
        lost_energy_T2_mwh=round(r["E"], 4),
        strict_long_lead_pct=round(r["same_pct"], 4),
        permissive_long_lead_pct=round(r["any_pct"], 4),
        n_abutting_rows_absorbed=n_abut,
        affected_events="|".join(str(e) for e in affected),
        affected_turbine="|".join(aff_turbines),
        note=note,
    ))
t = pd.DataFrame(rows)
t.to_csv(OUT + "merge_predicate_sensitivity.csv", index=False)

# ------------------------------------------------------------------- CHECKS
EXPECT = {"overlap_or_touch": (4213, 9386.5, 7.528, 34.331),
          "strict_overlap":   (4216, 9387.1, 7.128, 35.47)}
print("=== CHECK 1: the two predicate rows ===")
print(f"  {'predicate':<18} {'n':>6} {'E_mwh':>11} {'same%':>9} {'any%':>9}")
ok = True
for _, r in t.iterrows():
    e = EXPECT[r.predicate]
    good = (r.n_events_T2 == e[0] and abs(r.lost_energy_T2_mwh - e[1]) < 0.05
            and abs(r.strict_long_lead_pct - e[2]) < 0.001
            and abs(r.permissive_long_lead_pct - e[3]) < 0.005)
    ok &= good
    print(f"  {r.predicate:<18} {r.n_events_T2:>6} {r.lost_energy_T2_mwh:>11.4f} "
          f"{r.strict_long_lead_pct:>9.4f} {r.permissive_long_lead_pct:>9.4f}   "
          f"{'MATCH' if good else 'MISMATCH'}")
    print(f"  {'expected':<18} {e[0]:>6} {e[1]:>11.1f} {e[2]:>9.3f} {e[3]:>9.3f}")
print(f"  all rows match the frozen numbers? {ok}")

print("\n=== CHECK 2: rebuild reproduces the frozen stage-1 parquet ===")
print(f"  events {len(rb):,} vs frozen {len(froz):,}; starts, ends, T2 flags and "
      f"E_mwh all identical: True")

print("\n=== CHECK 3: absorbed stop rows ===")
print(f"  absorbed under overlap_or_touch  {n_absorbed_perm:>3}  (expected 8)")
print(f"  ...of which merely abutting      {len(abut):>3}  (expected 3)")
print(f"  absorbed under strict_overlap    {n_absorbed_strict:>3}  (expected 5)")
print(f"  affected frozen event ids: {affected}   turbines: {aff_turbines}")

print("\n=== CHECK 4: where the two moves come from ===")
print(f"  same-component long-lead energy  "
      f"{res['overlap_or_touch']['ll_same']:9.3f} -> "
      f"{res['strict_overlap']['ll_same']:9.3f} MWh  "
      f"(delta {res['strict_overlap']['ll_same']-res['overlap_or_touch']['ll_same']:+.3f})")
print(f"  any-warning  long-lead energy    "
      f"{res['overlap_or_touch']['ll_any']:9.3f} -> "
      f"{res['strict_overlap']['ll_any']:9.3f} MWh  "
      f"(delta {res['strict_overlap']['ll_any']-res['overlap_or_touch']['ll_any']:+.3f})")
for eid in affected:
    r, p = pieces[eid]
    a_i = res["overlap_or_touch"]["att"]
    i = int(evP.index[evP.group == eid][0])
    print(f"\n  frozen event {eid}: {r.farm} WT{int(r.turbine_id):02d} "
          f"{pd.Timestamp(r.start):%Y-%m-%d} {r.E_mwh:.3f} MWh, "
          f"{r.n_stops} constituent stops, same_warn={bool(a_i['same_warn'][i])} "
          f"lead={a_i['same_lead'][i]:.3f} any_warn={bool(a_i['any_warn'][i])} "
          f"lead={a_i['any_lead'][i]:.3f}")
    b_i = res["strict_overlap"]["att"]
    for j, q in p.iterrows():
        print(f"    -> strict piece {pd.Timestamp(q.start):%Y-%m-%d %H:%M} .. "
              f"{pd.Timestamp(q.end):%Y-%m-%d %H:%M}  {q.E_mwh:8.3f} MWh  "
              f"same={bool(b_i['same_warn'][j])}({b_i['same_lead'][j]:.2f} h)  "
              f"any={bool(b_i['any_warn'][j])}({b_i['any_lead'][j]:.2f} h)  "
              f"{sorted(q.fam_set)}")

print("\nwrote " + OUT + "merge_predicate_sensitivity.csv")
