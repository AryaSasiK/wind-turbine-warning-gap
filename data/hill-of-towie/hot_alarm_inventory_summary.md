# Hill of Towie observed alarm code inventory

Built 2026-09-07 from the open Zenodo record [10.5281/zenodo.20204946](https://doi.org/10.5281/zenodo.20204946), version 2.0.0 (published 2026-05-18), licence CC-BY-4.0.

## What this file is

`hot_alarm_code_inventory.csv` lists every distinct `Alarmcode` value that actually appears in the Hill of Towie alarm log, with how often it occurs, on how many turbines, when it was first and last seen, and how long its events typically last. It is derived only from the published open data, so anyone with the Zenodo record can reproduce it line for line.

It is an inventory of what occurs, not a code book. The open dataset ships descriptions for 12 alarm codes only. Every other code in this file has a blank description because no public description exists.

## How it was built

The Zenodo record ships one zip per calendar year. Each year zip contains 12 monthly files named `tblAlarmLog_YYYY_MM.csv`, with columns `TimeOn`, `TimeOff`, `StationNr`, `Alarmcode`.

The year archives are about 1.4 GB each, so rather than downloading them we read each zip's central directory over HTTP range requests, located the `tblAlarmLog` members, and range-read and inflated only those. The alarm logs are a small fraction of each archive. Requests were sequential, with backoff on rate limiting, and every inflated member was cached locally so re-runs do not re-fetch. Code: `analysis/hot_zipranged.py` (range reader) and `analysis/hot_alarm_inventory.py` (driver).

Rows read per year:

| Year | tblAlarmLog files | Rows | Distinct codes |
| --- | --- | --- | --- |
| 2016 | 12 | 1,111,700 | 319 |
| 2017 | 12 | 754,708 | 305 |
| 2018 | 12 | 809,473 | 381 |
| 2019 | 12 | 657,395 | 327 |
| 2020 | 12 | 664,325 | 351 |
| 2021 | 12 | 799,369 | 360 |
| 2022 | 12 | 416,835 | 353 |
| 2023 | 12 | 346,946 | 350 |
| 2024 | 12 | 329,726 | 353 |
| 2025 | 12 | 399,054 | 318 |
| 2026 | 4 | 113,063 | 224 |
| **Total** | **124** | **6,402,594** | **589** |

Note that the per-year distinct-code counts do not add up to the total: most codes occur in several years.

## Totals

- Distinct alarm codes observed: **589**
- Alarm log rows: **6,402,594**
- Period covered: 2016-01-01 02:19:48 to 2026-04-30 23:59:59 (by `TimeOn`)
- Turbines (distinct `StationNr`): 22
- Codes with a shipped description: 8 of 12
- Share of all rows covered by those documented codes: **78.9%** (5,052,587 rows) - but see the caveat immediately below
- Rows carrying a `TimeOff` value at all: 8.6%
- Documented codes that never occur in the data: 8210, 8234, 8235, 8236

That headline share is misleading on its own and should not be quoted without the next number. Two documented codes, 20 (Large generator Cut-in) and 25 (Fast cut-out of generator), account for 5,010,639 rows on their own, or 78.3% of the whole log. They are routine generator switching, logged on every cut-in and cut-out, not faults. Strip those two out and the remaining 10 documented codes cover just 3.0% of the 1,391,955 remaining rows.

So the practical position is that 581 of the 589 observed codes have no public description, and once routine generator switching is set aside, essentially all alarm activity in this dataset is carried by codes whose meaning is not published.

## Top 30 codes by row count

| Rank | Code | Rows | Share | Turbines | Years | Median duration (s) | Rows with TimeOff | Shipped description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 20 | 2,505,325 | 39.13% | 21 | 2016-2026 | - | 0% | Large generator Cut-in |
| 2 | 25 | 2,505,314 | 39.13% | 21 | 2016-2026 | - | 0% | Fast cut-out of generator |
| 3 | 55 | 451,524 | 7.05% | 21 | 2016-2026 | - | 0% | - |
| 4 | 50346 | 325,160 | 5.08% | 21 | 2016-2022 | 9 | 100% | - |
| 5 | 115 | 69,445 | 1.08% | 21 | 2016-2026 | - | 0% | - |
| 6 | 127 | 62,818 | 0.98% | 21 | 2016-2026 | - | 0% | - |
| 7 | 111 | 45,395 | 0.71% | 21 | 2016-2026 | - | 0% | - |
| 8 | 27 | 22,865 | 0.36% | 21 | 2016-2026 | - | 0% | - |
| 9 | 1005 | 17,172 | 0.27% | 21 | 2016-2026 | 116 | 100% | Availability - low wind |
| 10 | 3130 | 15,079 | 0.24% | 21 | 2016-2026 | 197 | 100% | Pitch lubrication |
| 11 | 7111 | 13,129 | 0.21% | 21 | 2016-2026 | 39 | 100% | - |
| 12 | 67 | 12,332 | 0.19% | 21 | 2016-2026 | - | 0% | - |
| 13 | 68 | 12,332 | 0.19% | 21 | 2016-2026 | - | 0% | - |
| 14 | 69 | 12,332 | 0.19% | 21 | 2016-2026 | - | 0% | - |
| 15 | 168 | 11,775 | 0.18% | 21 | 2017-2026 | - | 0% | - |
| 16 | 191 | 11,056 | 0.17% | 21 | 2024-2026 | - | 0% | - |
| 17 | 50954 | 10,998 | 0.17% | 21 | 2016;2017;2018;2020;2021;2022;2023;2024;2025;2026 | 263 | 100% | - |
| 18 | 5122 | 10,952 | 0.17% | 21 | 2016-2026 | 0 | 100% | - |
| 19 | 50200 | 10,000 | 0.16% | 21 | 2016-2026 | - | 0% | - |
| 20 | 15 | 8,733 | 0.14% | 21 | 2016;2017;2018;2022;2023;2024;2025;2026 | - | 0% | - |
| 21 | 16 | 8,733 | 0.14% | 21 | 2016;2017;2018;2022;2023;2024;2025;2026 | - | 0% | - |
| 22 | 29 | 6,691 | 0.10% | 21 | 2016-2026 | - | 0% | - |
| 23 | 10105 | 6,690 | 0.10% | 21 | 2016-2026 | 555 | 100% | Stopped, untwisting cables |
| 24 | 73033 | 6,550 | 0.10% | 21 | 2022-2026 | 5,250 | 100% | - |
| 25 | 50201 | 6,541 | 0.10% | 21 | 2016-2026 | - | 0% | - |
| 26 | 50000 | 6,180 | 0.10% | 21 | 2016-2026 | 3,175 | 100% | - |
| 27 | 1001 | 6,100 | 0.10% | 21 | 2016-2026 | 3,931 | 100% | - |
| 28 | 59 | 5,919 | 0.09% | 21 | 2016-2026 | - | 0% | - |
| 29 | 13902 | 5,898 | 0.09% | 21 | 2016-2026 | 62 | 100% | - |
| 30 | 159 | 5,875 | 0.09% | 21 | 2017-2026 | - | 0% | - |

## Column meanings

- `code` - the `Alarmcode` value as it appears in the data.
- `n_rows_total` - alarm log rows carrying that code, all years.
- `n_turbines_seen` - distinct `StationNr` values that ever raised it.
- `first_seen` / `last_seen` - earliest and latest `TimeOn`.
- `years_seen` - a range like `2016-2026` when the code occurs in every year between its first and last, otherwise a semicolon separated list.
- `y2016` .. `y2026` - row count in that calendar year's archive.
- `median_duration_s` - median of `TimeOff` minus `TimeOn` in seconds, over rows where `TimeOff` is present and not earlier than `TimeOn`.
- `share_rows_with_TimeOff` - fraction of that code's rows that have a `TimeOff` value at all.
- `is_documented` - 1 for the 12 codes described in the shipped `Hill_of_Towie_alarms_description.csv`, 0 otherwise.
- `description` / `stopping` - copied verbatim from that shipped file; blank for every other code.

## Caveats

**No message text exists in the open data.** The alarm log carries a numeric code and nothing else. There is no alarm message, severity, or component field anywhere in the published record. Descriptions exist for 12 codes, in a separate shipped file. Any mapping from the other codes to components or failure modes has to come from outside this dataset, and should be labelled as such.

**Turbine mapping.** 21 of 22 observed `StationNr` values resolve to a turbine in `Hill_of_Towie_turbine_metadata.csv` (`Station ID` column). Unresolved: 91. Those may be met masts, substation or site-level entries rather than turbines, so `n_turbines_seen` is best read as 'distinct stations'.

**Missing `TimeOff` semantics.** A blank `TimeOff` means the record carries no clear time in the published extract. It does not necessarily mean the alarm was still active. Reasons include alarms open at the end of an extract window, instantaneous events, and logging gaps. `median_duration_s` is therefore computed only over rows that do have a `TimeOff`, and `share_rows_with_TimeOff` tells you how much of the code's activity that median actually represents. Treat a median duration with a low `share_rows_with_TimeOff` as weak evidence.

This matters a lot here: only 8.6% of all rows carry a `TimeOff` at all. The pattern is close to bimodal. Of the 589 codes, 85 never have a `TimeOff` and 460 have one on at least 99% of their rows, leaving only 44 genuinely mixed. The codes that never have one include the three highest-volume codes in the dataset (20, 25 and 55), which together are 85% of all rows and are consistent with marking instants rather than intervals. So `median_duration_s` is blank for most of the log's row volume by design, not by accident, and the overall 8.6% figure should not be read as missing data.

**Month boundaries.** Rows are assigned to the year of the archive they were read from, not by re-parsing `TimeOn`. An alarm that opens in late December and clears in January appears in the December file. The per-year counts are therefore counts of rows per archive.

**Codes are not stable labels.** Nothing in the open data guarantees that a given numeric code means the same thing across the whole 2016 to 2026 window, across controller software upgrades. The `first_seen` and `last_seen` columns are the honest way to spot codes that only exist in part of the record.

## Reproducing this

```
python analysis/hot_alarm_inventory.py
```

It needs only network access to Zenodo and about 35 MB of cache space. No year archive is downloaded in full.

## Suggested citation

For a GitHub discussion post:

> Observed alarm code inventory for the Hill of Towie open dataset, derived from Zenodo record 10.5281/zenodo.20204946 (version 2.0.0, CC-BY-4.0), accessed 2026-09-07. Covers 6,402,594 `tblAlarmLog` rows across 11 year archives (2016 to 2026) and 589 distinct alarm codes. Built by range-reading only the `tblAlarmLog_YYYY_MM.csv` members from the published zips; no non-public code list was used.
