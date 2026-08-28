#!/usr/bin/env python3
"""Extract every Status_*.csv from every SCADA zip into one tidy parquet.

Status logs are tiny relative to the SCADA; we read them straight out of the zips
so nothing has to be extracted to disk.
"""
import os, sys, zipfile
import pandas as pd
import wtio

OUT = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
os.makedirs(OUT, exist_ok=True)


def main():
    frames, inventory = [], []
    for farm in ("kelmarsh", "penmanshiel"):
        for zpath in wtio.scada_zips(farm):
            zname = os.path.basename(zpath)
            with zipfile.ZipFile(zpath) as z:
                members = z.infolist()
            for info in members:
                base = os.path.basename(info.filename)
                kind, tid, yr = wtio.parse_member_name(info.filename)
                inventory.append({"farm": farm, "zip": zname, "member": info.filename,
                                  "kind": kind, "turbine": tid, "year": yr,
                                  "uncompressed_bytes": info.file_size,
                                  "compressed_bytes": info.compress_size})
                if kind != "status":
                    continue
                df = wtio.read_status(zpath, info.filename)
                df["farm"] = farm
                df["turbine_id"] = tid
                df["src_zip"] = zname
                df["src_member"] = base
                frames.append(df)
                print(f"{zname} :: {base} -> {len(df)} rows", flush=True)

    inv = pd.DataFrame(inventory)
    inv.to_csv(os.path.join(OUT, "zip_inventory.csv"), index=False)
    print("inventory rows:", len(inv))

    st = pd.concat(frames, ignore_index=True)
    print("total status rows:", len(st))
    print("columns:", list(st.columns))
    st.to_parquet(os.path.join(OUT, "status_all.parquet"), index=False)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
