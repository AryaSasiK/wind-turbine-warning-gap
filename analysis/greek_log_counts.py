#!/usr/bin/env python3
"""Full Warning/Alarm-log row count for the Greek SMD10TOWFGR corpus (v1.7d).

`data/DATASET_SCOUT.md` row 2 reported "roughly 300 warnings and 600 alarms
fleet-wide". That was an EXTRAPOLATION from three of the ten turbine sheets
(WT01 20 W / 74 A, WT05 45 W / 66 A, WT10 24 W / 49 A, Jan-Jun 2020), scaled by
10/3. This script replaces it with the real count over all ten sheets.

Source: Zenodo 10.5281/zenodo.14546480, "Six-Month Monitoring Dataset from a
10-Turbine Onshore Wind Farm in Greece" (Ntafalias, Visvardi, Weissenfeld / AIT),
CC-BY-4.0, one 180.7 MB workbook `SCADA__monitoring_dataset_2020.xlsx`. Nothing in
this repo depends on it; the count exists to state the corpus size honestly.

Method: openpyxl in read_only mode, one sheet at a time (`wb.close()` between
sheets), streaming rows. The workbook is far too large to load whole. On each
`WTxx_logs` sheet the header row is located by content - the sheet carries
`Code, Description, Detected, Device ack., Reset/Run, Duration, Event type,
Severity` - and rows are counted by the exact `Event type` string.

    python3 greek_log_counts.py [--xlsx PATH]

Requires openpyxl (see requirements.txt). This script imports nothing from the
pipeline, so its environment does not affect any frozen number.

The default path is the external volume; pass --xlsx if the workbook lives
elsewhere. Nothing is written: the counts are printed and transcribed by hand into
`data/DATASET_SCOUT.md` and `analysis/RESULTS_v17.md`.
"""
import argparse
import os
import re
from collections import Counter

from openpyxl import load_workbook

DEFAULT_XLSX = os.environ.get(
    "WTWG_GREEK_XLSX",
    os.path.join("wind-turbine-warning-gap-data", "greek",
                 "SCADA__monitoring_dataset_2020.xlsx"),
)

WARNING = "Warning log (W)"
ALARM = "Alarm log (A)"
# the workbook's sheets are literally named `WT01_logs.csv` ... `WT10_logs.csv`
# (the `.csv` suffix is part of the sheet name, not a file extension)
SHEET_RE = re.compile(r"^WT(\d{2})_logs(\.csv)?$", re.I)


def header_index(row):
    """Column index of `Event type` in a candidate header row, or None."""
    for i, v in enumerate(row):
        if isinstance(v, str) and v.strip().lower() == "event type":
            return i
    return None


def count_sheet(ws):
    """(counter over Event type values, data rows seen, header row number)."""
    col = None
    hdr_row = None
    counts = Counter()
    n_rows = 0
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if col is None:
            col = header_index(row)
            if col is not None:
                hdr_row = r
            continue
        if col >= len(row):
            continue
        v = row[col]
        if v is None and all(c is None for c in row):
            continue
        n_rows += 1
        counts[str(v).strip() if v is not None else "(blank)"] += 1
    return counts, n_rows, hdr_row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=DEFAULT_XLSX)
    a = ap.parse_args()
    print(f"workbook {a.xlsx} ({os.path.getsize(a.xlsx):,} bytes)")

    wb = load_workbook(a.xlsx, read_only=True, data_only=True)
    sheets = wb.sheetnames
    wb.close()
    log_sheets = sorted(s for s in sheets if SHEET_RE.match(s))
    print(f"{len(sheets)} sheets, {len(log_sheets)} log sheets: "
          f"{', '.join(log_sheets)}\n")

    total = Counter()
    per_turbine = {}
    print(f"{'sheet':<12} {'rows':>8} {'Warning (W)':>12} {'Alarm (A)':>10} "
          f"{'Operation (O)':>14} {'System (S)':>11} {'other':>7}")
    for name in log_sheets:
        # reopen per sheet: read_only mode keeps one worksheet's cells in memory
        wb = load_workbook(a.xlsx, read_only=True, data_only=True)
        c, n_rows, hdr = count_sheet(wb[name])
        wb.close()
        total.update(c)
        per_turbine[name] = c
        known = {WARNING, ALARM, "Operation log (O)", "System log (S)"}
        other = sum(v for k, v in c.items() if k not in known)
        print(f"{name:<12} {n_rows:>8,} {c[WARNING]:>12,} {c[ALARM]:>10,} "
              f"{c['Operation log (O)']:>14,} {c['System log (S)']:>11,} "
              f"{other:>7,}")

    print(f"\n{'FLEET':<12} {sum(total.values()):>8,} {total[WARNING]:>12,} "
          f"{total[ALARM]:>10,} {total['Operation log (O)']:>14,} "
          f"{total['System log (S)']:>11,}")
    print("\nevery distinct Event type value seen:")
    for k, v in total.most_common():
        print(f"  {k!r:<24} {v:,}")

    scout = {"WT01_logs.csv": (20, 74), "WT05_logs.csv": (45, 66),
             "WT10_logs.csv": (24, 49)}
    print("\nDATASET_SCOUT.md's three sampled sheets, checked:")
    for name, (w, al) in scout.items():
        c = per_turbine.get(name, Counter())
        print(f"  {name}: scout W {w} / A {al}   counted W {c[WARNING]} / "
              f"A {c[ALARM]}   {'MATCH' if (c[WARNING], c[ALARM]) == (w, al) else 'DIFFERS'}")
    print(f"\nextrapolation check: scout said 'roughly 300 warnings and 600 alarms "
          f"fleet-wide'; the real counts are {total[WARNING]:,} and {total[ALARM]:,}.")


if __name__ == "__main__":
    main()
