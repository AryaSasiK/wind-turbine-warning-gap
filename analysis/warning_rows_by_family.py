#!/usr/bin/env python3
"""warning_rows_by_family.csv - per-family warning rows on BOTH bases.

Referee point (2026-09-06): Table I in paper/main.tex reports warning rows per
turbine-year on the DE-DUPLICATED basis (19,150 rows total), while checks.md
section 4 only exports the RAW per-family log-row counts (19,948 total). No
artefact exposed the de-duplicated per-family split, so the two numbers could
not be reconciled from the repo (e.g. pitch raw 3,920/171 = 22.9 vs Table I
22.0).

De-duplication rule (build_warnings.py): within the pooled status log, two
`Warning` rows are duplicates when they agree on all of farm, turbine, start
timestamp, end timestamp and code; the first is kept and the rest dropped.

This script recomputes both bases from the frozen artefacts:
  raw    - every `Warning` row in derived/status_all.parquet, family-mapped
  dedup  - derived/warnings.parquet, which build_warnings.py already de-duped

    python3 warning_rows_by_family.py
"""
import os
import re

import pandas as pd

import common as C

TURBINE_YEARS = 171.0            # PROFILE section 4, same denominator as Table I
RAW_TOTAL = 19_948
DEDUP_TOTAL = 19_150
DEDUP_COD_TOTAL = 17_793         # de-duplicated AND post-commercial-operation
PRE_COD_TOTAL = 1_357            # dropped by the commissioning cut

OUT_CSV = os.path.join(C.SUMMARY_OUT, "warning_rows_by_family.csv")
MAIN_TEX = os.path.join(C.PROJECT, "paper", "main.tex")

# Table I prints "brake/hydraulic"; the pipeline family is "brake_hydraulic".
TEX_TO_FAMILY = {"brake/hydraulic": "brake_hydraulic"}


def family_map():
    """message -> family, for messages that can appear as a warning."""
    cm = pd.read_csv(os.path.join(C.SUMMARY_OUT, "component_map.csv"))
    return cm[cm.role.isin(("warning", "both"))].set_index("message")["family"]


def raw_counts():
    """Per-family counts over every `Warning` row, no de-duplication."""
    st, _ = C.load_status()
    st["Message"] = st["Message"].str.strip()
    w = st[st["Status"] == "Warning"].copy()
    w["family"] = w["Message"].map(family_map())
    unmapped = int(w["family"].isna().sum())
    if unmapped:
        raise SystemExit(f"{unmapped} raw warning rows have no component family: "
                         f"{sorted(w.loc[w.family.isna(), 'Message'].unique())}")
    return w["family"].value_counts()


def dedup_counts():
    """Per-family counts over the frozen, de-duplicated warning rows.

    Returns (all rows, post-commercial-operation rows only). `build_warnings.py`
    FLAGS pre-COD rows in the `pre_cod` column but does not drop them, whereas
    `build_events.py` DROPS them, so the two populations are on different bases
    until this filter is applied.
    """
    w = pd.read_parquet(C.WARNINGS_PARQUET)
    return w["family"].value_counts(), w.loc[~w["pre_cod"], "family"].value_counts()


def turbine_years_cod():
    """171 turbine-years rescaled to the post-commercial-operation exposure.

    PROFILE section 4's 171 is a file count (turbine x calendar year) covering
    the full observed status-log span, pre-COD months included. Dropping pre-COD
    warning rows from the numerator without shrinking the denominator would put
    the rate on two bases at once, so scale 171 by the fraction of observed
    turbine-span that is post-COD.
    """
    st, _ = C.load_status()
    st = st[st["t0"].notna()]
    raw = cod = 0.0
    for (farm, _tid), g in st.groupby(["farm", "turbine_id"]):
        lo, hi = g["t0"].min(), g["t0"].max()
        raw += (hi - lo).total_seconds()
        cod += (hi - max(lo, C.COD[farm])).total_seconds()
    return TURBINE_YEARS * cod / raw


def parse_table_i():
    """Read the warning-rows-per-turbine-year column out of Table I."""
    tex = open(MAIN_TEX, encoding="utf-8").read()
    block = re.search(r"\\label\{tab:families\}(.*?)\\end\{table\}", tex, re.S)
    if block is None:
        raise SystemExit("could not locate tab:families in main.tex")
    got = {}
    for line in block.group(1).splitlines():
        if "&" not in line or "\\\\" not in line:
            continue
        cells = [c.strip() for c in line.split("\\\\")[0].split("&")]
        if len(cells) != 5:
            continue
        name = cells[0].strip()
        if not re.fullmatch(r"[a-z/]+", name):        # skip the header rows
            continue
        val = re.sub(r"\\textbf\{|\}|\{|,", "", cells[3]).strip()
        got[TEX_TO_FAMILY.get(name, name)] = float(val)
    return got


def main():
    raw = raw_counts()
    ded, ded_cod = dedup_counts()
    ty_cod = turbine_years_cod()

    df = (pd.DataFrame({"rows_raw": raw, "rows_dedup": ded,
                        "rows_dedup_cod": ded_cod})
            .fillna(0).astype(int)
            .rename_axis("family").reset_index()
            .sort_values("family").reset_index(drop=True))
    df["per_ty_raw"] = (df.rows_raw / TURBINE_YEARS).round(4)
    df["per_ty_dedup"] = (df.rows_dedup / TURBINE_YEARS).round(4)
    df["per_ty_dedup_cod"] = (df.rows_dedup_cod / ty_cod).round(4)

    assert df.rows_raw.sum() == RAW_TOTAL, \
        f"raw total {df.rows_raw.sum():,} != {RAW_TOTAL:,}"
    assert df.rows_dedup.sum() == DEDUP_TOTAL, \
        f"dedup total {df.rows_dedup.sum():,} != {DEDUP_TOTAL:,}"
    assert df.rows_dedup_cod.sum() == DEDUP_COD_TOTAL, \
        f"dedup post-COD total {df.rows_dedup_cod.sum():,} != {DEDUP_COD_TOTAL:,}"
    assert df.rows_dedup.sum() - df.rows_dedup_cod.sum() == PRE_COD_TOTAL

    df.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}: {len(df)} families")
    print(f"raw total {df.rows_raw.sum():,}   dedup total {df.rows_dedup.sum():,}   "
          f"dropped {df.rows_raw.sum() - df.rows_dedup.sum():,}")
    print(f"post-COD dedup total {df.rows_dedup_cod.sum():,}   "
          f"pre-COD rows removed {PRE_COD_TOTAL:,}   "
          f"denominator {ty_cod:.2f} turbine-years (vs {TURBINE_YEARS:.0f})\n")
    print(df.to_string(index=False,
                       formatters={"per_ty_raw": "{:.2f}".format,
                                   "per_ty_dedup": "{:.2f}".format,
                                   "per_ty_dedup_cod": "{:.2f}".format}))

    # ------------------------------------------------ Table I reconciliation
    tex = parse_table_i()
    idx = df.set_index("family")
    print(f"\nTable I check (families printed in tab:families, "
          f"{TURBINE_YEARS:.0f} turbine-years):")
    print(f"{'family':<16} {'Table I':>8} {'per_ty_dedup':>13} "
          f"{'per_ty_raw':>11} {'post-COD':>9}  verdict")
    n_bad = n_moved = 0
    for fam, paper_val in tex.items():
        if fam not in idx.index:                       # e.g. safety: 0 warnings
            d = r_ = c_ = 0.0
        else:
            d, r_ = idx.at[fam, "per_ty_dedup"], idx.at[fam, "per_ty_raw"]
            c_ = idx.at[fam, "per_ty_dedup_cod"]
        ok = abs(round(d, 1) - paper_val) < 0.05
        n_bad += not ok
        moved = round(c_, 1) != round(d, 1)
        n_moved += moved
        print(f"{fam:<16} {paper_val:>8.1f} {d:>13.2f} {r_:>11.2f} {c_:>9.2f}  "
              f"{'MATCH' if ok else 'MISMATCH'}"
              f"{'  (post-COD moves the rounded cell)' if moved else ''}")
    print(f"\n{len(tex) - n_bad}/{len(tex)} Table I warning rates reproduce "
          f"on the de-duplicated basis.")
    print(f"{n_moved}/{len(tex)} printed cells change if the commissioning cut "
          f"is applied to the warnings too.")

    conv = idx.loc["converter"]
    print(f"\nconverter warning rows: raw {conv.rows_raw:,}  "
          f"dedup {conv.rows_dedup:,}  post-COD dedup {conv.rows_dedup_cod:,}  "
          f"(main.tex prose says 80 = the dedup count including pre-COD rows)")

    six = ["anemometry", "pitch", "external", "brake_hydraulic", "yaw", "comms"]
    s_d = idx.loc[six, "rows_dedup"].sum()
    s_c = idx.loc[six, "rows_dedup_cod"].sum()
    print(f"six-family supply share: dedup {s_d:,}/{DEDUP_TOTAL:,} = "
          f"{100 * s_d / DEDUP_TOTAL:.1f}%   post-COD {s_c:,}/{DEDUP_COD_TOTAL:,} = "
          f"{100 * s_c / DEDUP_COD_TOTAL:.1f}%")


if __name__ == "__main__":
    main()
