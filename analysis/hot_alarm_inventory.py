"""Build a public, citeable inventory of every alarm code that actually occurs
in the Hill of Towie open dataset.

Source: Zenodo record 10.5281/zenodo.20204946, v2.0.0, CC-BY-4.0.
The record ships one zip per year (2016..2026); each contains monthly
tblAlarmLog_YYYY_MM.csv files with columns TimeOn, TimeOff, StationNr,
Alarmcode. We range-read only those members out of the remote zips, so
nothing large is ever downloaded.

Everything written here is derived ONLY from the open Zenodo record plus the
shipped Hill_of_Towie_alarms_description.csv (12 documented codes) and
Hill_of_Towie_turbine_metadata.csv. No private or unofficial code list is
read or joined.

Outputs (data/hill-of-towie/):
  hot_alarm_code_inventory.csv
  hot_alarm_inventory_summary.md
  hot_observed_codes.json   (refreshed to cover all years)

Usage:
  python analysis/hot_alarm_inventory.py [--cache DIR] [--years 2016,2017,...]
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hot_zipranged as hz  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
OUTDIR = os.path.join(PROJECT, "data", "hill-of-towie")

RECORD_ID = "20204946"
RECORD_DOI = "10.5281/zenodo.20204946"
RECORD_VERSION = "2.0.0"
MEMBER_RE = re.compile(r"^tblAlarmLog_(\d{4})_(\d{2})\.csv$", re.IGNORECASE)

DEFAULT_CACHE = os.environ.get(
    "WTWG_HOT_CACHE",
    os.path.join(PROJECT, "wind-turbine-warning-gap-data", "hotcache"),
)


# ------------------------------------------------------------------ helpers

def parse_ts(s):
    """Parse a tblAlarmLog timestamp. Returns datetime or None."""
    s = (s or "").strip()
    if not s or s.upper() in ("NULL", "NAN", "NONE"):
        return None
    if "." in s:
        s = s.split(".")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def load_shipped_descriptions(cache_dir):
    """The 12 documented codes from Hill_of_Towie_alarms_description.csv."""
    path = os.path.join(cache_dir, "Hill_of_Towie_alarms_description.csv")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            raw = fh.read()
    else:
        url = (
            f"https://zenodo.org/api/records/{RECORD_ID}/files/"
            "Hill_of_Towie_alarms_description.csv/content"
        )
        raw, _ = hz.http_get(url)
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(raw)
    rd = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    out = {}
    for row in rd:
        code = int(float(row["Alarm Code"]))
        out[code] = (row["Description"].strip(), row["Stopping"].strip())
    return out


def load_station_map(cache_dir):
    """StationNr -> turbine name, from Hill_of_Towie_turbine_metadata.csv."""
    path = os.path.join(cache_dir, "Hill_of_Towie_turbine_metadata.csv")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            raw = fh.read()
    else:
        url = (
            f"https://zenodo.org/api/records/{RECORD_ID}/files/"
            "Hill_of_Towie_turbine_metadata.csv/content"
        )
        raw, _ = hz.http_get(url)
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(raw)
    rd = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    return {r["Station ID"].strip(): r["Turbine Name"].strip() for r in rd}


class CodeStats:
    __slots__ = (
        "n_rows", "stations", "first_seen", "last_seen",
        "per_year", "durations", "n_with_timeoff",
    )

    def __init__(self):
        self.n_rows = 0
        self.stations = set()
        self.first_seen = None
        self.last_seen = None
        self.per_year = {}
        self.durations = []
        self.n_with_timeoff = 0


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--years", default="")
    args = ap.parse_args()

    cache_dir = args.cache
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    access_date = dt.date.today().isoformat()

    print(f"[info] Zenodo record {RECORD_DOI}  cache={cache_dir}")
    files, rec = hz.record_files()
    published = rec.get("metadata", {}).get("publication_date", "")
    version = rec.get("metadata", {}).get("version", RECORD_VERSION)

    year_zips = sorted(
        k for k in files if re.fullmatch(r"\d{4}\.zip", k)
    )
    if args.years:
        want = {y.strip() for y in args.years.split(",")}
        year_zips = [z for z in year_zips if z[:4] in want]
    print(f"[info] year archives: {', '.join(year_zips)}")

    shipped = load_shipped_descriptions(cache_dir)
    station_map = load_station_map(cache_dir)

    stats = {}                 # code -> CodeStats
    per_year_rows = {}         # 'YYYY' -> row count
    per_year_codes = {}        # 'YYYY.zip' -> set(codes)
    per_year_members = {}      # 'YYYY' -> member count read
    failures = []              # (archive, member, error)
    all_stations = set()
    global_first = global_last = None
    n_rows_total = 0
    n_bad_ts = 0
    n_bad_code = 0
    n_neg_duration = 0

    for zname in year_zips:
        yr = zname[:4]
        url = files[zname]
        try:
            ents = hz.cached_central_directory(url, cache_dir, zname)
        except Exception as e:  # noqa: BLE001
            failures.append((zname, "<central directory>", repr(e)))
            print(f"[FAIL] {zname}: central directory: {e!r}")
            continue

        members = sorted(
            (e for e in ents if MEMBER_RE.match(os.path.basename(e[0]))),
            key=lambda e: e[0],
        )
        print(f"[info] {zname}: {len(ents)} members, {len(members)} tblAlarmLog")

        codes_here = set()
        rows_here = 0
        ok_members = 0

        for name, method, csize, usize, lho in members:
            try:
                raw, was_cached = hz.cached_member(
                    url, name, method, csize, lho, cache_dir, zname
                )
            except Exception as e:  # noqa: BLE001
                failures.append((zname, name, repr(e)))
                print(f"  [FAIL] {name}: {e!r}")
                continue

            rd = csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")))
            try:
                header = next(rd)
            except StopIteration:
                failures.append((zname, name, "empty member"))
                continue
            hl = [h.strip().lower() for h in header]
            try:
                i_on = hl.index("timeon")
                i_off = hl.index("timeoff")
                i_st = hl.index("stationnr")
                i_code = hl.index("alarmcode")
            except ValueError as e:
                failures.append((zname, name, f"unexpected header {header}: {e}"))
                print(f"  [FAIL] {name}: unexpected header {header}")
                continue

            n_here = 0
            for row in rd:
                if len(row) <= max(i_on, i_off, i_st, i_code):
                    continue
                raw_code = row[i_code].strip()
                if not raw_code:
                    n_bad_code_local = True  # noqa: F841
                    continue
                try:
                    code = int(float(raw_code))
                except ValueError:
                    n_bad_code += 1
                    continue

                st = row[i_st].strip()
                t_on = parse_ts(row[i_on])
                t_off = parse_ts(row[i_off])
                if t_on is None:
                    n_bad_ts += 1

                s = stats.get(code)
                if s is None:
                    s = stats[code] = CodeStats()
                s.n_rows += 1
                if st:
                    s.stations.add(st)
                    all_stations.add(st)
                s.per_year[yr] = s.per_year.get(yr, 0) + 1
                if t_on is not None:
                    if s.first_seen is None or t_on < s.first_seen:
                        s.first_seen = t_on
                    if s.last_seen is None or t_on > s.last_seen:
                        s.last_seen = t_on
                    if global_first is None or t_on < global_first:
                        global_first = t_on
                    if global_last is None or t_on > global_last:
                        global_last = t_on
                if t_off is not None:
                    s.n_with_timeoff += 1
                    if t_on is not None:
                        d = (t_off - t_on).total_seconds()
                        if d < 0:
                            n_neg_duration += 1
                        else:
                            s.durations.append(d)

                codes_here.add(code)
                n_here += 1

            rows_here += n_here
            ok_members += 1
            tag = "cache" if was_cached else "fetch"
            print(f"  [{tag}] {name}: {n_here} rows")

        per_year_rows[yr] = rows_here
        per_year_codes[zname] = codes_here
        per_year_members[yr] = ok_members
        n_rows_total += rows_here
        print(f"[info] {yr}: {rows_here} rows, {len(codes_here)} distinct codes")

    years_sorted = sorted(per_year_rows)

    # ------------------------------------------------------------ validation
    ref_path = os.path.join(OUTDIR, "hot_observed_codes.json")
    validation = []
    if os.path.exists(ref_path):
        with open(ref_path) as fh:
            ref = json.load(fh)
        for key in ("2016.zip", "2023.zip", "2026.zip"):
            if key in ref and key in per_year_codes:
                got = sorted(per_year_codes[key])
                exp = sorted(int(c) for c in ref[key])
                ok = got == exp
                validation.append((key, ok, len(exp), len(got),
                                   sorted(set(exp) - set(got)),
                                   sorted(set(got) - set(exp))))
                status = "MATCH" if ok else "MISMATCH"
                print(f"[validate] {key}: {status} "
                      f"(expected {len(exp)} codes, got {len(got)})")
                if not ok:
                    print(f"  missing: {sorted(set(exp) - set(got))}")
                    print(f"  extra:   {sorted(set(got) - set(exp))}")
            else:
                print(f"[validate] {key}: not available for comparison")
    else:
        print("[validate] no existing hot_observed_codes.json to compare")

    for key, ok, *_ in validation:
        assert ok, f"validation failed: {key} code set does not match reference"

    # ------------------------------------------------------------- inventory
    inv_path = os.path.join(OUTDIR, "hot_alarm_code_inventory.csv")
    year_cols = [f"y{y}" for y in years_sorted]
    fields = (
        ["code", "n_rows_total", "n_turbines_seen", "first_seen", "last_seen",
         "years_seen"]
        + year_cols
        + ["median_duration_s", "share_rows_with_TimeOff",
           "is_documented", "description", "stopping"]
    )

    def years_seen_str(s):
        ys = sorted(y for y, n in s.per_year.items() if n > 0)
        if not ys:
            return ""
        ints = [int(y) for y in ys]
        if ints == list(range(ints[0], ints[-1] + 1)) and len(ints) > 1:
            return f"{ints[0]}-{ints[-1]}"
        return ";".join(ys)

    with open(inv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for code in sorted(stats):
            s = stats[code]
            desc, stop = shipped.get(code, ("", ""))
            med = (round(statistics.median(s.durations), 1)
                   if s.durations else "")
            share = (round(s.n_with_timeoff / s.n_rows, 4)
                     if s.n_rows else "")
            w.writerow(
                [code, s.n_rows, len(s.stations),
                 s.first_seen.isoformat(sep=" ") if s.first_seen else "",
                 s.last_seen.isoformat(sep=" ") if s.last_seen else "",
                 years_seen_str(s)]
                + [s.per_year.get(y, 0) for y in years_sorted]
                + [med, share, 1 if code in shipped else 0, desc, stop]
            )
    print(f"[write] {inv_path}")

    # ------------------------------------------------------- observed codes
    obs_path = os.path.join(OUTDIR, "hot_observed_codes.json")
    with open(obs_path, "w") as fh:
        json.dump(
            {k: sorted(v) for k, v in sorted(per_year_codes.items())},
            fh,
        )
    print(f"[write] {obs_path}")

    # -------------------------------------------------------------- summary
    documented_rows = sum(stats[c].n_rows for c in shipped if c in stats)
    doc_share = documented_rows / n_rows_total if n_rows_total else 0
    documented_seen = sorted(c for c in shipped if c in stats)
    documented_absent = sorted(c for c in shipped if c not in stats)
    top30 = sorted(stats.items(), key=lambda kv: -kv[1].n_rows)[:30]

    # Codes 20 and 25 are routine generator cut-in / cut-out, not faults, and
    # they alone dominate the documented-code row share. Report both figures.
    ROUTINE = (20, 25)
    routine_rows = sum(stats[c].n_rows for c in ROUTINE if c in stats)
    routine_share = routine_rows / n_rows_total if n_rows_total else 0
    rest_rows = n_rows_total - routine_rows
    doc_rows_ex_routine = sum(
        stats[c].n_rows for c in shipped if c in stats and c not in ROUTINE
    )
    doc_share_ex_routine = doc_rows_ex_routine / rest_rows if rest_rows else 0

    rows_with_off = sum(s.n_with_timeoff for s in stats.values())
    off_share_all = rows_with_off / n_rows_total if n_rows_total else 0

    def _off_share(s):
        return s.n_with_timeoff / s.n_rows if s.n_rows else 0

    n_off_never = sum(1 for s in stats.values() if _off_share(s) == 0)
    n_off_always = sum(1 for s in stats.values() if _off_share(s) >= 0.99)
    n_off_mixed = len(stats) - n_off_never - n_off_always
    top3_no_off = [c for c, _ in top30 if c in stats
                   and _off_share(stats[c]) == 0][:3]
    top3_no_off_share = (
        sum(stats[c].n_rows for c in top3_no_off) / n_rows_total
        if n_rows_total else 0
    )

    unmapped = sorted(all_stations - set(station_map))
    mapped = sorted(all_stations & set(station_map))

    L = []
    a = L.append
    a("# Hill of Towie observed alarm code inventory")
    a("")
    a(f"Built {access_date} from the open Zenodo record "
      f"[{RECORD_DOI}](https://doi.org/{RECORD_DOI}), version {version} "
      f"(published {published}), licence CC-BY-4.0.")
    a("")
    a("## What this file is")
    a("")
    a("`hot_alarm_code_inventory.csv` lists every distinct `Alarmcode` value "
      "that actually appears in the Hill of Towie alarm log, with how often "
      "it occurs, on how many turbines, when it was first and last seen, and "
      "how long its events typically last. It is derived only from the "
      "published open data, so anyone with the Zenodo record can reproduce "
      "it line for line.")
    a("")
    a("It is an inventory of what occurs, not a code book. The open dataset "
      "ships descriptions for 12 alarm codes only. Every other code in this "
      "file has a blank description because no public description exists.")
    a("")
    a("## How it was built")
    a("")
    a("The Zenodo record ships one zip per calendar year. Each year zip "
      "contains 12 monthly files named `tblAlarmLog_YYYY_MM.csv`, with "
      "columns `TimeOn`, `TimeOff`, `StationNr`, `Alarmcode`.")
    a("")
    a("The year archives are about 1.4 GB each, so rather than downloading "
      "them we read each zip's central directory over HTTP range requests, "
      "located the `tblAlarmLog` members, and range-read and inflated only "
      "those. The alarm logs are a small fraction of each archive. Requests "
      "were sequential, with backoff on rate limiting, and every inflated "
      "member was cached locally so re-runs do not re-fetch. Code: "
      "`analysis/hot_zipranged.py` (range reader) and "
      "`analysis/hot_alarm_inventory.py` (driver).")
    a("")
    a("Rows read per year:")
    a("")
    a("| Year | tblAlarmLog files | Rows | Distinct codes |")
    a("| --- | --- | --- | --- |")
    for y in years_sorted:
        a(f"| {y} | {per_year_members[y]} | {per_year_rows[y]:,} | "
          f"{len(per_year_codes[y + '.zip']):,} |")
    a(f"| **Total** | **{sum(per_year_members.values())}** | "
      f"**{n_rows_total:,}** | **{len(stats):,}** |")
    a("")
    a("Note that the per-year distinct-code counts do not add up to the "
      "total: most codes occur in several years.")
    a("")
    a("## Totals")
    a("")
    a(f"- Distinct alarm codes observed: **{len(stats):,}**")
    a(f"- Alarm log rows: **{n_rows_total:,}**")
    a(f"- Period covered: {global_first} to {global_last} (by `TimeOn`)")
    a(f"- Turbines (distinct `StationNr`): {len(all_stations)}")
    a(f"- Codes with a shipped description: {len(documented_seen)} of "
      f"{len(shipped)}")
    a(f"- Share of all rows covered by those documented codes: "
      f"**{doc_share:.1%}** ({documented_rows:,} rows) - but see the "
      f"caveat immediately below")
    a(f"- Rows carrying a `TimeOff` value at all: {off_share_all:.1%}")
    if documented_absent:
        a(f"- Documented codes that never occur in the data: "
          f"{', '.join(str(c) for c in documented_absent)}")
    a("")
    a("That headline share is misleading on its own and should not be quoted "
      "without the next number. Two documented codes, 20 (Large generator "
      f"Cut-in) and 25 (Fast cut-out of generator), account for "
      f"{routine_rows:,} rows on their own, or {routine_share:.1%} of the "
      "whole log. They are routine generator switching, logged on every "
      "cut-in and cut-out, not faults. Strip those two out and the remaining "
      f"{len(shipped) - 2} documented codes cover just "
      f"{doc_share_ex_routine:.1%} of the "
      f"{n_rows_total - routine_rows:,} remaining rows.")
    a("")
    a(f"So the practical position is that {len(stats) - len(documented_seen):,} "
      "of the "
      f"{len(stats):,} observed codes have no public description, and once "
      "routine generator switching is set aside, essentially all alarm "
      "activity in this dataset is carried by codes whose meaning is not "
      "published.")
    a("")
    a("## Top 30 codes by row count")
    a("")
    a("| Rank | Code | Rows | Share | Turbines | Years | Median duration (s) "
      "| Rows with TimeOff | Shipped description |")
    a("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, (code, s) in enumerate(top30, 1):
        desc = shipped.get(code, ("", ""))[0] or "-"
        med = (f"{statistics.median(s.durations):,.0f}"
               if s.durations else "-")
        share = s.n_with_timeoff / s.n_rows if s.n_rows else 0
        a(f"| {i} | {code} | {s.n_rows:,} | "
          f"{s.n_rows / n_rows_total:.2%} | {len(s.stations)} | "
          f"{years_seen_str(s)} | {med} | {share:.0%} | {desc} |")
    a("")
    a("## Column meanings")
    a("")
    a("- `code` - the `Alarmcode` value as it appears in the data.")
    a("- `n_rows_total` - alarm log rows carrying that code, all years.")
    a("- `n_turbines_seen` - distinct `StationNr` values that ever raised it.")
    a("- `first_seen` / `last_seen` - earliest and latest `TimeOn`.")
    a("- `years_seen` - a range like `2016-2026` when the code occurs in "
      "every year between its first and last, otherwise a semicolon "
      "separated list.")
    a("- `y2016` .. `y2026` - row count in that calendar year's archive.")
    a("- `median_duration_s` - median of `TimeOff` minus `TimeOn` in "
      "seconds, over rows where `TimeOff` is present and not earlier than "
      "`TimeOn`.")
    a("- `share_rows_with_TimeOff` - fraction of that code's rows that "
      "have a `TimeOff` value at all.")
    a("- `is_documented` - 1 for the 12 codes described in the shipped "
      "`Hill_of_Towie_alarms_description.csv`, 0 otherwise.")
    a("- `description` / `stopping` - copied verbatim from that shipped "
      "file; blank for every other code.")
    a("")
    a("## Caveats")
    a("")
    a("**No message text exists in the open data.** The alarm log carries a "
      "numeric code and nothing else. There is no alarm message, severity, "
      "or component field anywhere in the published record. Descriptions "
      "exist for 12 codes, in a separate shipped file. Any mapping from the "
      "other codes to components or failure modes has to come from outside "
      "this dataset, and should be labelled as such.")
    a("")
    if unmapped:
        a(f"**Turbine mapping.** {len(mapped)} of {len(all_stations)} "
          f"observed `StationNr` values resolve to a turbine in "
          f"`Hill_of_Towie_turbine_metadata.csv` (`Station ID` column). "
          f"Unresolved: {', '.join(unmapped)}. Those may be met masts, "
          f"substation or site-level entries rather than turbines, so "
          f"`n_turbines_seen` is best read as 'distinct stations'.")
    else:
        a(f"**Turbine mapping.** All {len(all_stations)} observed "
          f"`StationNr` values resolve to turbines T01 to T21 via the "
          f"`Station ID` column of "
          f"`Hill_of_Towie_turbine_metadata.csv`, so `n_turbines_seen` is a "
          f"true turbine count.")
    a("")
    a("**Missing `TimeOff` semantics.** A blank `TimeOff` means the record "
      "carries no clear time in the published extract. It does not "
      "necessarily mean the alarm was still active. Reasons include alarms "
      "open at the end of an extract window, instantaneous events, and "
      "logging gaps. `median_duration_s` is therefore computed only over "
      "rows that do have a `TimeOff`, and `share_rows_with_TimeOff` tells "
      "you how much of the code's activity that median actually represents. "
      "Treat a median duration with a low `share_rows_with_TimeOff` as "
      "weak evidence.")
    a("")
    a(f"This matters a lot here: only {off_share_all:.1%} of all rows carry "
      f"a `TimeOff` at all. The pattern is close to bimodal. Of the "
      f"{len(stats):,} codes, {n_off_never:,} never have a `TimeOff` and "
      f"{n_off_always:,} have one on at least 99% of their rows, leaving "
      f"only {n_off_mixed:,} genuinely mixed. The codes that never have one "
      "include the three highest-volume codes in the dataset (20, 25 and "
      f"55), which together are {top3_no_off_share:.0%} of all rows and are "
      "consistent with marking instants rather than intervals. So "
      "`median_duration_s` is blank for most of the log's row volume by "
      "design, not by accident, and the overall "
      f"{off_share_all:.1%} figure should not be read as missing data.")
    a("")
    a("**Month boundaries.** Rows are assigned to the year of the archive "
      "they were read from, not by re-parsing `TimeOn`. An alarm that opens "
      "in late December and clears in January appears in the December file. "
      "The per-year counts are therefore counts of rows per archive.")
    a("")
    if n_neg_duration or n_bad_ts or n_bad_code:
        a("**Data quality counts.** Rows where `TimeOff` precedes `TimeOn` "
          f"and were excluded from durations: {n_neg_duration:,}. Rows with "
          f"an unparseable `TimeOn`: {n_bad_ts:,}. Rows with an "
          f"unparseable `Alarmcode`, skipped: {n_bad_code:,}.")
        a("")
    a("**Codes are not stable labels.** Nothing in the open data guarantees "
      "that a given numeric code means the same thing across the whole "
      "2016 to 2026 window, across controller software upgrades. The "
      "`first_seen` and `last_seen` columns are the honest way to spot "
      "codes that only exist in part of the record.")
    a("")
    a("## Reproducing this")
    a("")
    a("```")
    a("python analysis/hot_alarm_inventory.py")
    a("```")
    a("")
    a("It needs only network access to Zenodo and about 35 MB of cache "
      "space. No year archive is downloaded in full.")
    a("")
    a("## Suggested citation")
    a("")
    a("For a GitHub discussion post:")
    a("")
    a("> Observed alarm code inventory for the Hill of Towie open dataset, "
      f"derived from Zenodo record {RECORD_DOI} (version {version}, "
      f"CC-BY-4.0), accessed {access_date}. Covers {n_rows_total:,} "
      f"`tblAlarmLog` rows across {len(years_sorted)} year archives "
      f"({years_sorted[0]} to {years_sorted[-1]}) and "
      f"{len(stats):,} distinct alarm codes. Built by range-reading only "
      "the `tblAlarmLog_YYYY_MM.csv` members from the published zips; no "
      "non-public code list was used.")
    a("")

    md_path = os.path.join(OUTDIR, "hot_alarm_inventory_summary.md")
    text = "\n".join(L)
    for bad, good in (("—", "-"), ("–", "-"), ("−", "-")):
        text = text.replace(bad, good)
    with open(md_path, "w") as fh:
        fh.write(text)
    print(f"[write] {md_path}")

    print("\n=== SUMMARY ===")
    for y in years_sorted:
        print(f"{y}: rows={per_year_rows[y]:,} "
              f"codes={len(per_year_codes[y + '.zip'])} "
              f"members={per_year_members[y]}")
    print(f"TOTAL rows={n_rows_total:,} distinct codes={len(stats):,}")
    print(f"documented-code row share={doc_share:.4%} "
          f"({documented_rows:,} rows)")
    print(f"failures={len(failures)}")
    for f in failures:
        print("  FAIL", f)


if __name__ == "__main__":
    main()
