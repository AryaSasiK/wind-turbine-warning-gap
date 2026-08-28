#!/usr/bin/env python3
"""Cache the six SCADA columns the study needs, one parquet per turbine.

The corpus is 11.33 GB of zips and would be 107.7 GB extracted, so nothing is
extracted; `wtio.read_member` streams each member out of its zip in 20k-row
chunks and drops the ~41x all-NaN padding rows that the 2023-2024 Greenbyte
exports carry (PROFILE §7 risk 7). Reducing 385 columns to 6 turns the whole
corpus into ~9 M rows that fit comfortably in memory, which makes every later
step of the pipeline cheap and re-runnable.

Idempotent: a turbine whose parquet already exists is skipped unless --rebuild.

    python3 build_scada_cache.py [--rebuild] [--farm kelmarsh]
"""
import argparse
import os
import zipfile

import pandas as pd

import common as C
import wtio


def scada_index():
    """(farm, turbine, year) -> [(zip_path, member_name), ...]

    Penmanshiel 2023 WT01-10 is split across four irregular zips, so a key can
    map to more than one member (PROFILE §2).
    """
    idx = {}
    for farm in ("kelmarsh", "penmanshiel"):
        for zpath in wtio.scada_zips(farm):
            with zipfile.ZipFile(zpath) as z:
                for info in z.infolist():
                    kind, tid, yr = wtio.parse_member_name(info.filename)
                    if kind == "scada":
                        idx.setdefault((farm, tid, yr), []).append((zpath, info.filename))
    return idx


def turbine_path(farm, tid):
    return os.path.join(C.SCADA_CACHE, f"{farm}_WT{tid:02d}.parquet")


def build(rebuild=False, only_farm=None):
    os.makedirs(C.SCADA_CACHE, exist_ok=True)
    idx = scada_index()
    turbines = sorted({(f, t) for (f, t, _) in idx})
    manifest = []
    for farm, tid in turbines:
        if only_farm and farm != only_farm:
            continue
        out = turbine_path(farm, tid)
        if os.path.exists(out) and not rebuild:
            n = len(pd.read_parquet(out, columns=[C.TS]))
            print(f"skip {farm} WT{tid:02d} (cached, {n:,} rows)", flush=True)
            manifest.append({"farm": farm, "turbine_id": tid, "rows": n, "cached": True})
            continue
        years = sorted(y for (f, t, y) in idx if (f, t) == (farm, tid))
        frames = []
        for yr in years:
            for zpath, member in idx[(farm, tid, yr)]:
                _, _, cols = wtio.peek(zpath, member, C.TS)
                use = [c for c in C.SCADA_COLS if c in cols]
                missing = [c for c in C.SCADA_COLS if c not in cols]
                if missing:
                    print(f"  !! {os.path.basename(member)} missing {missing}")
                df = wtio.read_scada(zpath, member, usecols=use)
                for c in missing:
                    df[c] = pd.NA
                df[C.TS] = pd.to_datetime(df[C.TS], errors="coerce")
                frames.append(df[C.SCADA_COLS])
        sc = pd.concat(frames, ignore_index=True)
        sc = (sc.dropna(subset=[C.TS])
                .sort_values(C.TS)
                .drop_duplicates(subset=[C.TS], keep="first")
                .reset_index(drop=True))
        for c in C.SCADA_COLS[1:]:
            sc[c] = pd.to_numeric(sc[c], errors="coerce")
        sc.to_parquet(out, index=False)
        print(f"{farm} WT{tid:02d}: years {years[0]}-{years[-1]} -> {len(sc):,} rows "
              f"({sc[C.TS].min()} .. {sc[C.TS].max()})", flush=True)
        manifest.append({"farm": farm, "turbine_id": tid, "rows": len(sc),
                         "cached": False, "t_min": sc[C.TS].min(), "t_max": sc[C.TS].max()})
    return pd.DataFrame(manifest)


def load_turbine(farm, tid):
    """Timestamp-indexed minimal SCADA for one turbine (from the cache)."""
    sc = pd.read_parquet(turbine_path(farm, tid))
    return sc.set_index(C.TS).sort_index()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--farm", default=None)
    a = ap.parse_args()
    m = build(rebuild=a.rebuild, only_farm=a.farm)
    print("\ncached turbines:", len(m), " total rows:", f"{int(m.rows.sum()):,}")
