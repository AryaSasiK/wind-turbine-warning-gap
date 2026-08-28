"""Shared readers for Kelmarsh/Penmanshiel Zenodo CSVs (read straight out of the zips).

Both file types carry a preamble of metadata lines. In Turbine_Data_*.csv the header row
itself is comment-prefixed ('# Date and time,...'), which silently destroys the columns if
you filter out '#' lines. We locate the header by content instead of by line number.
"""
import io, os, re, zipfile
import pandas as pd

RAW = os.environ.get("WTWG_RAW", "wind-turbine-warning-gap-data/raw")
FARMS = {"kelmarsh": os.path.join(RAW, "kelmarsh"),
         "penmanshiel": os.path.join(RAW, "penmanshiel")}


def scada_zips(farm, verify=True):
    d = FARMS[farm]
    out = sorted(os.path.join(d, f) for f in os.listdir(d)
                 if f.endswith(".zip") and "SCADA" in f)
    if not verify:
        return out
    good = []
    for p in out:
        try:
            with zipfile.ZipFile(p):
                pass
            good.append(p)
        except zipfile.BadZipFile:
            print("SKIP (not a valid zip, incomplete download?):", os.path.basename(p))
    return good


def _decode(b):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", "replace")


def peek(zpath, member, header_token, nbytes=262144):
    """Return (preamble_lines, header_index, column_names) without reading the
    whole member. Turbine_Data headers are themselves '#'-prefixed."""
    with zipfile.ZipFile(zpath) as z, z.open(member) as fh:
        head = _decode(fh.read(nbytes))
    lines = head.split("\n")
    hidx = next((i for i, l in enumerate(lines[:60]) if header_token in l), None)
    if hidx is None:
        raise ValueError(f"header token {header_token!r} not found in {member}")
    cols = pd.read_csv(io.StringIO(lines[hidx].lstrip("#").lstrip()),
                       nrows=0).columns.tolist()
    return lines[:hidx], hidx, cols


CHUNK_ROWS = 20000


def read_member(zpath, member, header_token, nrows=None, usecols=None,
                return_preamble=False, drop_empty_rows=True):
    """Stream one CSV member out of a zip, in row chunks.

    Two traps handled here:
    1. The largest members are ~3 GB of CSV text. Reading them whole (or with
       low_memory=False, which buffers the whole file before type inference)
       gets the process OOM-killed; chunked reads keep peak memory to the size
       of the selected columns.
    2. The 2023+ Greenbyte exports pad each 10-minute timestamp with ~40-80
       extra rows that are entirely NaN, inflating a 52,560-row turbine-year to
       ~2.17 M rows. drop_empty_rows discards them per chunk and coalesces any
       remaining duplicate timestamps, restoring the true 10-minute grid.
    """
    pre, hidx, _ = peek(zpath, member, header_token)
    # Let pandas parse the header row itself (skiprows=hidx, header=0) rather
    # than passing names= -- supplying names while skipping the header makes the
    # C parser mis-split these files and silently invent millions of rows.
    # The header is '#'-prefixed, so match usecols against the stripped name.
    want = None if usecols is None else set(usecols)
    sel = None if want is None else (lambda c: c.lstrip("# ").strip() in want)
    kw = dict(skiprows=hidx, header=0, usecols=sel,
              encoding="utf-8", encoding_errors="replace")

    def clean(chunk):
        chunk.columns = [c.lstrip("# ").strip() for c in chunk.columns]
        if not drop_empty_rows:
            return chunk
        data = [c for c in chunk.columns if c != "Date and time"]
        return chunk.dropna(subset=data, how="all") if data else chunk

    with zipfile.ZipFile(zpath) as z, z.open(member) as fh:
        if nrows is not None:
            df = clean(pd.read_csv(fh, nrows=nrows, **kw))
        else:
            parts = [clean(c) for c in pd.read_csv(fh, chunksize=CHUNK_ROWS, **kw)]
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            del parts
    df.columns = [c.lstrip("# ").strip() for c in df.columns]
    if drop_empty_rows and "Date and time" in df.columns and df["Date and time"].duplicated().any():
        # 2023+ exports repeat each timestamp; coalesce the survivors.
        df = df.groupby("Date and time", as_index=False).first()
    if return_preamble:
        return df, pre
    return df


def read_status(zpath, member, **kw):
    return read_member(zpath, member, "Timestamp start", **kw)


def read_scada(zpath, member, **kw):
    return read_member(zpath, member, "Date and time", **kw)


_TURB = re.compile(r"Turbine[_ ]?(\d+)|WT[_ ]?0*(\d+)|_(\d+)_")


def parse_member_name(name):
    """-> (kind, turbine_id, year) best effort from the member filename."""
    base = os.path.basename(name)
    kind = ("status" if base.startswith("Status_") else
            "scada" if base.startswith("Turbine_Data_") else "other")
    yr = None
    m = re.search(r"(20\d\d)-\d\d-\d\d", base)
    if m:
        yr = int(m.group(1))
    else:
        m = re.search(r"_(20\d\d)_", base)
        if m:
            yr = int(m.group(1))
    tid = None
    m = re.search(r"(?:Status|Turbine_Data)_(?:Kelmarsh|Penmanshiel)_(\d+)_", base)
    if m:
        tid = int(m.group(1))
    return kind, tid, yr
