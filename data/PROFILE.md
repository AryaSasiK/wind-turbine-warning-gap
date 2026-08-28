# Data profile — Kelmarsh & Penmanshiel SCADA + event logs

Profiling pass for the "actionable-warning gap" study (see `../STUDY_DESIGN.md`).
Every number below was computed from the downloaded files, not from the Zenodo landing pages or the
scout notes. Where this contradicts `energy.md`, **this document is correct** — `energy.md` was written
against a superseded Penmanshiel record and a single Kelmarsh turbine-year.

Generated 2026-08-27. Scripts that produce everything here live beside this file
(`download.py`, `build_status.py`, `full_pass.py`, `analyse_status.py`, `smoke_precursors.py`, `report.py`).

---

## 1. What was downloaded

Both concept DOIs were resolved to their **current versioned records** on 2026-08-27; both are the
2025 re-releases, and both now run **2016 → end 2024**.

| | Kelmarsh | Penmanshiel |
|---|---|---|
| Record | [zenodo.org/records/16807551](https://zenodo.org/records/16807551) | [zenodo.org/records/16807304](https://zenodo.org/records/16807304) |
| Version DOI | `10.5281/zenodo.16807551` | `10.5281/zenodo.16807304` |
| Concept DOI | `10.5281/zenodo.5841833` | `10.5281/zenodo.5946807` |
| Published | 2025-08-12 | 2025-08-13 |
| Files / size | 15 / **3.84 GB** | 26 / **7.49 GB** |
| Turbines | 6 × Senvion MM92 (2,050 kW) | 14 × Senvion MM82 (2,050 kW) |
| Licence | CC-BY-4.0 | CC-BY-4.0 |
| Creators | Plumley, Charlie; Takeuchi, Roberta (Cubico Sustainable Investments Ltd) | same |

- **Total downloaded: 11.33 GB, 41 files, all 41 MD5-verified against the Zenodo API.**
- Exact per-file sizes, checksums and verification status: `MANIFEST.json` (written by `download.py`).
- **Penmanshiel record 5946808 (v0.0.2, 2022), cited in `energy.md`, is superseded.** It held
  2016–mid-2021 only. The current record adds 2021–2024 and restructures the 2021+ zips. Any
  analysis built on 5946808 would silently lose ~3.5 turbine-years per turbine.
- Kelmarsh record 16807551 is likewise newer than anything in the scout notes, and also runs to 2024.

### Where the bytes live
The project sits on a laptop with **7 GB free on the boot volume**, so raw data is on the external
volume and symlinked in:

```
data/raw     -> <data-volume>/wind-turbine-warning-gap-data/raw      (11.33 GB, zips)
data/extract -> <data-volume>/wind-turbine-warning-gap-data/extract  (136 MB, one turbine-year)
             <data-volume>/wind-turbine-warning-gap-data/derived     (small CSV/parquet)
```

**Full extraction would be 107.7 GB** (41.5 GB Kelmarsh + 66.0 GB Penmanshiel), far past the ~25 GB
budget, so nothing is extracted wholesale. Per the brief, one turbine-year is extracted as a
reference copy (`Kelmarsh 1, 2018` — 141 MB SCADA + 1 MB status) and everything else is **read
directly out of the zips** by `wtio.read_member`, which streams the decompression handle into pandas
in 20k-row chunks. The whole corpus profiles in one pass at ~300 MB peak RSS.

---

## 2. Corpus shape

| | Kelmarsh | Penmanshiel | total |
|---|---|---|---|
| Turbines | 6 (WT1–6) | 14 (**WT01, WT02, WT04–WT15 — there is no WT03**) | 20 |
| Years | 2016–2024 (9) | 2016–2023 all turbines; **2024 only WT11–WT15** | |
| Turbine-years | 54 | 117 | **171** |
| SCADA members | 54 | 144 | 198 |
| Status members | 54 | 144 | 198 |

`Penmanshiel_WT_static.csv` lists 14 rows, T01→T15 with T03 absent; the Zenodo description confirms
"there is no turbine WT03". The unit that would have been WT03 (serial `82767`) was commissioned as
**WT15** (`MM82/59 82767-15`), so serial order and turbine number diverge — do not infer install
order from the turbine number.

Penmanshiel has more members than turbine-years because the 2023 WT01–10 data is split into four
irregular zips (Feb, Mar, Q2, Q3–Q4).

### Commissioning
- Kelmarsh: all 6 turbines COD **2016-04-15**; SCADA and events start 2016-01-03/2016-01-14, i.e.
  ~3 months of pre-COD commissioning data. 2016 is not a normal operating year.
- Penmanshiel: all 14 turbines COD **2016-09-01**; first events 2016-06-02 → 2016-07-27, staggered
  per turbine by up to 8 weeks. WT08 (2016-07-27) and WT11 (2016-07-19) start latest.
- Kelmarsh hub heights are **not uniform**: WT3 and WT6 are 68.5 m, the other four 78.5 m. Rotor
  92 m throughout. Penmanshiel is uniform (59 m hub, 82 m rotor).

---

## 3. Status / event logs

`Status_*.csv`, one per turbine-year, header at line 10 (**not** comment-prefixed, unlike the SCADA).
Pooled: **1,569,087 rows across 171 turbine-years**, 2016-01-14 → 2024-12-31.

### Columns (exact)
`Timestamp start, Timestamp end, Duration, Status, Code, Message, Comment, Service contract category, IEC category`

Plus, **in 2021+ exports only**, two extra trailing columns: `Global contract category` and
`Custom contract category` (14 of 29 zips). `Custom contract category` is empty everywhere.
A naive `pd.concat` across years therefore yields a ragged frame — align on the 9 base columns.

- `Timestamp start` — second resolution, `YYYY-MM-DD HH:MM:SS`, parses cleanly for **all** 1,569,087 rows.
- `Timestamp end` / `Duration` — **the sentinel for "no end" is the string `-`, not an empty field.**
  1,274,420 rows (81.2%) are instantaneous point events carrying `-` in both columns; 99.996% of
  those are `Informational`. Only 14 `Stop` rows are open-ended. If you `pd.to_datetime(..., errors='coerce')`
  without replacing `-` first you will silently drop four fifths of the log, and if you *don't* coerce
  you get an exception; either way this is the first thing to get right.
- `Duration` — `HH:MM:SS` with hours allowed past 24 (`211:08:29`). `pd.to_timedelta` parses it directly.
  It is **exactly consistent** with `end − start`: max |residual| = **0.0 s** over all 294,667 interval
  rows. No negative durations; 381 zero-length events.
- `Comment` — **1,010 non-null of 1.57 M (0.06%)**. The free-text comment field is effectively empty in
  the public release. Do not plan on it.
- `Code` ↔ `Message` is 1:1 (274 messages, 273 codes, 274 pairs) except code `111`, which carries two
  messages. Message text is a **closed vocabulary of 274 strings**, not free text — no NLP required,
  and no NLP contribution available.

### `Status` (5 values)
| Status | rows |
|---|---|
| Informational | 1,516,777 |
| **Stop** | **28,285** |
| Warning | 19,948 |
| Communication | 2,154 |
| **Curtailment** | **1,923** |

### `IEC category` (IEC 61400-26, 9 values incl. blank)
| IEC category | rows |
|---|---|
| Full Performance | 936,340 |
| Out of Environmental Specification | 367,112 |
| Technical Standby | 234,430 |
| *(blank)* | 14,601 |
| **Forced outage** | **7,607** |
| Partial Performance | 4,322 |
| Scheduled Maintenance | 3,356 |
| Out of Electrical Specification | 933 |
| Requested Shutdown | 386 |

**The IEC category alone does not identify a stop.** Of the 7,607 `Forced outage` rows, only
**6,366 have `Status == 'Stop'`**; 1,241 are `Warning` rows that merely carry the category. Conversely
`Stop` rows spread across seven IEC categories (Technical Standby 12,400; Forced outage 6,366; Out of
Environmental Spec 4,905; Scheduled Maintenance 3,356; Out of Electrical Spec 808; Requested Shutdown
378; blank 72). **The event definition for this study must be `Status == 'Stop' AND IEC category == 'Forced outage'`.**

### Forced-outage stops: the headline counts
- **6,366 forced-outage stops** across 171 turbine-years (Kelmarsh 1,325; Penmanshiel 5,041).
- Per turbine-year: median 30, mean 37.2, IQR 19–44.5, max 190.
  Kelmarsh median 18.5, Penmanshiel median 36 — **Penmanshiel logs roughly twice as many per turbine-year.**
- **83 distinct messages.** Top: `Externally stopped` 1,459 · `Anemometer defect` 813 ·
  `Frequency converter not ready` 795 · `Tower oscillation Y level 1` 514 · `Manual stop - remote` 424 ·
  `Missing gear oil (high rpm)` 354 · `Tower oscillation Y level 2` 315 · `Repeating error BP52` 251.
- Total forced-outage downtime **23,529 h**.

**The duration distribution is the single most important fact for the study design:**

| bucket | events | share of events | hours | share of hours |
|---|---|---|---|---|
| <10 min | 3,448 | 54.2% | 122 | 0.5% |
| 10 min – 1 h | 1,938 | 30.4% | 620 | 2.6% |
| 1 – 6 h | 545 | 8.6% | 1,514 | 6.4% |
| 6 – 24 h | 250 | 3.9% | 3,283 | 14.0% |
| 1 – 7 d | 151 | 2.4% | 8,995 | 38.2% |
| > 7 d | 22 | 0.3% | 8,994 | 38.2% |

Median forced-outage stop = **5.3 minutes**. **76.6% of all forced-outage downtime sits in the 174
events of 24 h or more.** The energy-weighted decomposition is therefore a study of **~170–420
events**, not 6,366 — see §7 risk 1.

(Of the 6,366 forced-outage stops, 6,355 carry an end timestamp; 11 are open-ended. The duration
table above is over those 6,355. Subsequent per-event numbers use 6,352 — the 6,355 minus three whose
turbine-year has no matching SCADA member.)

### Warnings (the "detectable" side, from the log itself)
19,948 `Warning` rows, 78 distinct messages. Top: `P output externally reduced` 2,389 ·
`4-20mA anemometer 2` 1,908 · `4-20 mA vane 2` 1,908 · `Timeout brake closed` 1,345 ·
`Comm. failure FPM` 1,333 · `High yaw motor current` 1,310 · `Brake accumulator defect` 1,209.

### Overlapping and duplicate intervals — a real problem
Of 294,667 interval events, **76,938 (26.1%) start before the running maximum end-time of an earlier
event on the same turbine**, and **8,680 are exact duplicates** on (start, end, code).
Duplicates are wildly uneven: Penmanshiel WT01 alone has 4,190 (48% of all duplicates); most turbines
have 220–550. Restricting to `Stop` intervals, maximum concurrency is **2**, i.e. stop intervals nest
rather than pile up. Any downtime accounting must **merge intervals** rather than sum durations, or it
will double-count.

### Curtailment vs fault — cleanly separable, with one trap
The logs disambiguate curtailment three independent ways:
1. **`Status == 'Curtailment'`** — 1,923 rows, 1,558 h, all `IEC category = Partial Performance`:
   `Technical curtailment` (1,464) and `Grid constraint curtailment` (459).
2. **`Service contract category`** — `Techical Curtailments (just for calculation)` (sic, 1,470),
   `External stop (grid) (4)` (2,061).
3. **`Global contract category`** (2021+ only) — `12 (Int) Technical Curtailment` (1,470),
   `11 (Ext) Requested Curtailment` (453), `09 (Int) Fault` (2,484), `10 (Ext) Environmental` (2,925).

**The trap:** `Externally stopped` — a *grid-side* stop, service category `External stop (grid) (4)` —
is classified by IEC as **`Forced outage`**, and it is the single most common forced-outage message:
**1,459 of 6,366 stops (22.9%)**. Meanwhile `Grid loss` (436), `Grid error` (38) and
`Grid disconnection for self-protection` (12) are classified `Out of Electrical Specification`, *not*
forced outage. So the log treats grid events inconsistently, and a naive "forced outage = turbine
fault" mapping imports 23% grid-caused events into the fault population.

Two exclusion rules are used in this document; both are stated wherever a count appears:

| rule | events | ≥ 6 h | ≥ 24 h |
|---|---|---|---|
| all forced-outage stops | 6,366 | 423 | 174 |
| excluding `Externally stopped` only | 4,907 | 408 | 173 |
| excluding grid **and** manual/remote messages | 4,452 | 313 | 143 |

`Manual stop - remote` (424) and `Manual stop - on site` are also forced outages by IEC but are
human actions with no turbine-side physical precursor — and, per §5, `Manual stop - remote` is the
largest single energy bucket in the whole forced-outage population.

---

## 4. SCADA (`Turbine_Data_*.csv`)

198 members, one per turbine-year except Penmanshiel 2023 WT01–10 (split across four zips).

**Parsing gotcha, confirmed.** The header row is itself comment-prefixed —
line 9 reads `# Date and time,Wind speed (m/s),…`. Filtering out `#` lines deletes the header and
every column name. `wtio.peek()` locates the header by content and strips the prefix.

### Sampling grid — clean
Across **all 198 members**: modal Δt = **600 s**, rows with Δt ≠ 600 s = **0**, duplicate timestamps
after cleaning = **0**, rows present ÷ rows implied by the member's own span = **100.00% for every
member**. `# Time zone: UTC` in all 198 preambles.

**So there are no missing 10-minute rows anywhere in this corpus.** The grid is complete; missingness
is expressed purely as `NaN` *values* (the preamble says so: *"Data that is missing or is erroneous
has been marked with the value NaN"*). "% missing 10-min rows" is therefore the wrong question —
the right one is per-signal NaN rate, below.

Because the grid is UTC and complete, **there are no DST duplicated/skipped hours**. UK local time is
never used. The event logs are UTC too (same preamble). No clock alignment work is needed between the
two files — but see §5 for the sub-bin phase problem, which is a different issue.

### Completeness, per signal, by farm-year (mean over turbines, % of the 10-min grid)

| farm-year | Power | Wind speed | Cascading pot. power | Lost Prod. Downtime | Front bearing T | Gear oil T | Metal particle count |
|---|---|---|---|---|---|---|---|
| K 2016 | 90.8 | 90.8 | 93.5 | 91.9 | 65.2 | 65.2 | **0.0** |
| K 2017 | 98.9 | 98.8 | 99.7 | 99.4 | 98.9 | 98.9 | **55.5** |
| K 2018–2024 | 96.5–99.9 | 96.4–99.9 | 99.9–100 | 99.4–100 | 94.2–99.7 | 94.2–99.7 | 100 |
| P 2016 | 84.2 | 84.2 | 100 | 99.8 | **0.0** | **0.0** | **0.0** |
| P 2017 | 99.7 | 99.7 | 100 | 100 | **0.0** | **0.0** | **0.0** |
| P 2018 | 99.5 | 99.5 | 100 | 99.9 | **66.5** | **66.5** | **74.1** |
| P 2019–2024 | 94.4–99.7 | 94.4–99.6 | 99.8–100 | 99.6–100 | 94.1–99.2 | 94.1–99.7 | 100 |

Per-turbine-year `Power` non-null: mean 97.7%, median 99.5%, 5th pct 89.9%, **min 69.2%**.
The 12 worst turbine-years are all 2016 — Penmanshiel's partial first year (members start at each
turbine's own commissioning date, so the denominator is a short span) and Kelmarsh's pre-COD months.

### Signal list and schema drift
**385 distinct column names across the corpus; only 287 present in every farm-year.** Column count
per member:

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|---|
| Kelmarsh | 299 | 299 | 299 | 299 | 299 | 303 | 303 | 312 | 312 |
| Penmanshiel | 300 | 300 | 300 | 300 | 300 | 363 | 363 | 350 / 372 | 372 |

Three Greenbyte export campaigns, visible in each file's preamble:

| exported | members | farms | years | columns |
|---|---|---|---|---|
| 2022-01-27/28 | 30 | Kelmarsh | 2016–2020 | 299 |
| 2022-02-01/02 | 70 | Penmanshiel | 2016–2020 | 300 |
| 2023-08-15 | 40 | both | 2021–2022 | 303 / 363 |
| 2025-08-11/12/13 | 58 | both | 2023–2024 | 312 / 350 / 372 |

**Documented / detectable changes across those boundaries:**
- **Unit suffix renamed `mm/ss` → `mm/s2` at the 2023 boundary** for all 12 tower- and drive-train
  acceleration columns, on both farms. A naive multi-year `concat` yields 24 columns each ~78% empty
  instead of 12 full ones. This is the nastiest silent trap in the SCADA.
- 2021+ adds `Manufacturer Potential Power (SCADA) (kW)` and `Potential Power Energy Budget (kW)`.
- 2023+ adds `MTBF (Contractual Global) (h)`, `MTTR (Contractual Global) (h)`,
  `Available Capacity for Production (Planning deviation) (kW / %)`,
  `Time-based System Availability (Planning deviation)`, `Sunrise/Sunset Delta (s)`, `Night Time`,
  `Energy Budget (weather adjusted) (kWh)`, `Investment/Operating Performance Ratio`.
- Penmanshiel 2021+ carries `Blade angle (pitch position)` un-suffixed alongside the A/B/C variants;
  Penmanshiel 2016–2020 carries `APE-2 (kW)`, which is dropped from 2021.
- **Sensor commissioning is visible in the data**: Penmanshiel bearing and gear-oil temperatures are
  **entirely absent (0%) in 2016 and 2017** and only 66.5% present in 2018 — they come online through
  2018. `Metal particle count` (the gearbox oil-debris sensor) is 0% at Kelmarsh in 2016, 55.5% in
  2017, 100% from 2018; 0% at Penmanshiel until 2018 (74.1%), 100% from 2019. **Any normal-behaviour
  model using drivetrain temperatures or particle count cannot use Penmanshiel before 2019.**

### The potential-power family — corrects `energy.md`
`energy.md` says "seven `Potential power` variants". The actual 2016 schema has **eleven**
(nine `Potential power *` plus two `Cascading potential power *`), and 2021+ adds a twelfth. Their
corpus-wide non-null rates:

| column | non-null % | note |
|---|---|---|
| `Cascading potential power (kW)` | **99.8** | merged best-available series — **use this one** |
| `Potential power reference turbines (kW)` | 99.6 | |
| `Potential power primary reference turbines (kW)` | 98.0 | |
| `Cascading potential power for performance (kW)` | 97.9 | |
| `Potential power default PC (kW)` | 97.4 | |
| `Potential power MPC (kW)` | 97.4 | numerically identical to default PC |
| `Potential power secondary reference turbines (kW)` | 96.7 | |
| `Potential power learned PC (kW)` | 95.9 | |
| `Potential power estimated (kW)` | **1.1** | populated *only* when `Power` is NaN |
| `Potential power met mast anemometer (kW)` | **0.0** | empty — neither site has a met mast |
| `Potential power met mast anemometer MPC (kW)` | **0.0** | empty |
| `Manufacturer Potential Power (SCADA) (kW)` | **0.0** | column exists 2021+, never populated |

**None of the potential-power or lost-production columns appears in either farm's
`dataSignalMapping` file.** Those files map only raw manufacturer signals (61 rows for Kelmarsh,
78 for Penmanshiel, e.g. `Front bearing temperature ← Axle bearing temperature 1`). The definitions of
the derived columns are **not shipped with the dataset** — they are Greenbyte platform concepts. A
reviewer will ask what "Potential power default PC" is and the honest answer must be inferred
empirically. What is established here empirically:

- **`Potential power default PC` is NaN in exactly the rows where `Power` is NaN** (0.0% available
  when `Power` is NaN, 100% otherwise). It is therefore **unusable on its own for outage lost energy** —
  precisely the rows you need are the rows it is missing.
- **`Potential power estimated` is populated in exactly those rows** (100% when `Power` is NaN,
  0.0% otherwise). It is the gap-filler.
- **`Cascading potential power` is ≥99.7% available in every power state** and is the coalesced series.

### Energy accounting columns
The SCADA ships **30 pre-computed lost-production columns**, including a full IEC 61400-26 set
(`Time-based / Production-based IEC B.2.2, B.2.3, B.2.4, B.3.2`) and, critically, a
**curtailment-cause breakdown**: `Lost Production to Curtailment (Grid, Noise, Shadow, Bats, Birds,
Ice, Sector Management, Technical, Marketing, Boat Action, Grid Constraint, Total)`.
`energy.md` did not know these existed; they remove most of the methodological risk.

Corpus totals over 171 turbine-years:

| quantity | MWh |
|---|---|
| `Energy Theoretical` | 909,118 |
| **`Energy Export` (generated)** | **865,526** |
| `Lost Production Total` | 42,607 |
| **`Lost Production to Downtime`** | **40,809** (4.50% of gross) |
| `Lost Production to Performance` | 1,306 |
| **`Lost Production to Curtailment (Total)`** | **556** (0.06%) |

**Curtailment is negligible at these sites** — 556 MWh in nine years, of which 431 MWh is Kelmarsh
2023 technical curtailment and 51 MWh is grid constraint. `Grid`, `Noise`, `Shadow`, `Ice`, `Bats`,
`Birds` curtailment are **zero everywhere**. This is a genuine simplification for the study: the
curtailment-vs-fault confound that would dominate a modern UK site barely exists here.

Note `Lost Production to Performance` can be **negative** per interval (the turbine outproduces the
learned power curve), so `Total = Downtime + Performance` is not monotone in `Downtime`.

---

## 5. Alignment between the event log and the SCADA grid

Computed for every forced-outage stop with both timestamps (`fo_alignment.csv`, 6,352 after
de-duplicating the split Penmanshiel 2023 members).

- **Logged start times land at a uniform random phase inside the 10-minute bin** — seconds-into-bin
  is uniform on 0–599 (median 305 s), and only **0.30%** fall exactly on a boundary. There is no
  clock snapping. Mapping a second-resolution event onto the 10-min grid costs up to 10 minutes at
  each end, i.e. up to 20 minutes of ambiguity per event. **For the 54% of forced outages shorter
  than 10 minutes this is larger than the event itself.**
- Logged start → first SCADA row showing the turbine down (`Power ≤ 0` or NaN): median **5.4 min**,
  IQR 2.6–9.0 min, 58.4% within 10 min. **29.2% never show the turbine down within 6 h.**
- Logged end → first SCADA row producing > 50 kW: median **8.5 min**, IQR 4.5–32.9 min.
- Fraction of SCADA rows inside the logged window that show the turbine down: median 1.00, but
  **9.1% of events have < 50% of their rows down** — the logged interval and the physical outage
  disagree for roughly one event in eleven.

### Lost energy over forced-outage stops — and a validation
| method | corpus total |
|---|---|
| Σ (`Cascading potential power` − `Power`)⁺ × 10 min | **14,369.6 MWh** |
| Σ Greenbyte `Lost Production to Downtime` | **14,363.9 MWh** |
| Σ (`Potential power default PC` − `Power`)⁺ × 10 min | 10,841.5 MWh |

The first two agree to **ratio 1.00040, correlation 0.999999, mean absolute per-event difference
0.0017 MWh.** Integrating the cascading potential power reproduces the operator's own downtime
accounting essentially exactly — the strongest possible answer to "did you invent your own
counterfactual?". **The `default PC` column understates by 24.6%**, for the reason in §4.

Careful: over a *whole year* the naive `(potential − actual)` integral gives ~505 MWh/turbine against
Greenbyte's 328 MWh, a 54% overstatement, because outside outages it charges normal power-curve
scatter as loss. The agreement above holds **only inside stop intervals**. Do not integrate globally.

Forced-outage lost energy is **14,370 MWh = 1.66% of gross generation** (vs 4.50% for all downtime
causes). Kelmarsh 3,675 MWh / Penmanshiel 10,695 MWh. Excluding grid and manual messages, the
turbine-side subtotal is 4,438 events / 11,563 MWh (**80.5%**).

**Energy is extremely concentrated:**

| | share of forced-outage lost energy |
|---|---|
| top 10 events | 22.9% |
| top 50 | 48.4% |
| top 100 | 62.7% |
| top 200 | 77.4% |
| top 500 | 91.0% |

Largest single events: `Service generator brushes` (Penmanshiel WT11, 703 h, 544 MWh);
`Circuit breaker` (WT10, 1,471 h, 428 MWh); `Frequency converter error` (Kelmarsh WT4, 390 h, 395 MWh).
By message, the largest single bucket is **`Manual stop - remote`: 424 events, 3,746 h, 2,410 MWh
(16.8% of all forced-outage lost energy)** — a human decision, not a fault.

Overlapping stop intervals double-count: Penmanshiel WT10's `Circuit breaker` and
`Frequency converter load rejection` both start 2023-03-24 01:43:36 and are charged 428 and 417 MWh
for the same wall-clock downtime.

---

## 6. Feasibility smoke test — do precursors exist?

**This is a smoke test, not the analysis**, and it is deliberately crude: the point is to find out
whether the decomposition has anything to decompose before any modelling effort is spent.

Method (`smoke_precursors.py`). For each sampled forced-outage stop ≥ 6 h:
- **Temperature precursor** — for 8 component temperatures, take the residual (component − nacelle
  ambient) over producing rows only (`Power > 100 kW`), form 6 h rolling means over the 72 h before
  the stop, and score max |z| against a 28-day baseline ending where the 72 h window begins.
- **Power-curve precursor** — same construction on (`Cascading potential` − `Power`)/potential.
- **Log precursor** — does the status log carry a `Warning` row for that turbine in the 72 h?
- **Lost energy** — as §5.

Three panels: 20 random forced-outage stops; 20 "component-fault" stops (manual/remote/grid/weather
messages excluded); and — **essential, and the reason this smoke test is worth anything** — 31
**controls**: the same turbines at timestamps shifted back 45 days, verified to have no forced-outage
stop within ±3 days.

| panel | n | temp z>3 | temp z>2 | median temp z | power-curve z>3 | **log Warning in 72 h** |
|---|---|---|---|---|---|---|
| random forced outages | 20 | 4 (20%) | 13 (65%) | 2.38 | 0/18 | 8 (40%) |
| component-fault outages | 19 | 3 (16%) | 11 (58%) | 2.09 | 0/16 | **13 (68%)** |
| **control (quiet periods)** | **31** | **6 (19%)** | **17 (55%)** | **2.18** | **1/29** | **8 (26%)** |

### Verdict: mixed, and the honest answer matters for the framing

**(a) The naive SCADA statistic finds nothing.** Temperature-residual drift before real forced
outages is *statistically indistinguishable from quiet control periods* — 16–20% exceed z=3 before an
outage, and **19% of controls do too**. Median z is 2.38/2.09 for events vs 2.18 for controls. The
power-curve residual is worse than useless (0/34 events vs 1/29 controls). Without the control panel
one would have reported "65% of outages show temperature anomalies" and been badly wrong; the max-of-
12-rolling-windows statistic simply exceeds 2 most of the time under the null.
**Conclusion: a real normal-behaviour model is required, and detectability from SCADA cannot be
assumed.** Whether a proper NBM beats this is an open question, not a settled one.

**(b) The event log itself is a strong precursor channel.** Verified corpus-wide, not just on the
sample:

("turbine-side" here = excluding grid **and** manual/remote messages, the strictest rule in §3.)

| population | n | Warning in prior 72 h | median lead |
|---|---|---|---|
| all forced-outage stops | 6,355 | **63.5%** | 22.8 h |
| turbine-side only | 4,441 | **63.7%** | 30.1 h |
| turbine-side, ≥ 6 h | 313 | 54.3% | 29.6 h |
| turbine-side, ≥ 24 h | 143 | 48.3% | 27.2 h |
| **matched control (−45 d, quiet)** | **3,145** | **16.5%** | 32.6 h |

**3.9× enrichment over control** (63.7% vs 16.5%). Nearly half of the long, energy-dominant outages
are preceded by an explicit operator-visible `Warning` a median of ~27 hours earlier. That is the
"actionable-warning gap" measured directly, with no model at all — and it lands squarely on the
novelty claim in `energy.md` that none of the 48 papers citing these datasets uses the operational
status logs.

**Implication for the paper.** The decomposition is feasible, but the *instrument* should be the
status log first and a SCADA normal-behaviour model second — the reverse of the framing in
`energy.md` §3 Idea 1. That is also the safer position on novelty: SCADA anomaly detection is
saturated, log-derived warning-to-stop lead time is not.

Lost-energy magnitudes on the sampled events, for scale: 20 random forced outages ≥6 h totalled
**459 MWh** (median 5.8, max 199.6); the 19 component-fault events **467 MWh** (median 6.8, max 114.6).
Greenbyte cross-check matched to 0.1 MWh on both panels. Curtailment inside all 39 outage windows: **0.000 MWh**.

---

## 7. Risks to the study design

**1. The effective N is ~200, not ~7,000 — and this is the biggest threat.**
`energy.md` §3 estimates "~7,000 forced-outage events" and calls N "adequate". The count is right
(6,366) but it is the wrong statistic for an energy-weighted decomposition. **54% of forced-outage
stops are shorter than 10 minutes and carry 0.5% of the lost energy**; the top 100 events carry
62.7% and the top 200 carry 77.4%. Strip grid (`Externally stopped`, 22.9%) and human
(`Manual stop - remote`, the largest single energy bucket at 16.8%) causes and the population of
turbine-side, energy-material, physically-precursable events is **a few hundred, concentrated in 20
turbines of two Senvion models at two UK sites**. Confidence intervals on the three decomposition
shares will be wide, and a single 544 MWh event moves the headline. Mitigations: report the
decomposition energy-weighted *with bootstrap CIs over events*; pre-register the event-inclusion rule;
add CARE to Compare (per `energy.md`) not as a "generalization check" but as genuinely needed N.

**2. Detectability is not established, and the paper's headline number depends on it entirely.**
The "detectable-but-unacted" share *is* the automation thesis number, and the smoke test says a naive
SCADA statistic cannot separate pre-outage windows from quiet controls. If a proper normal-behaviour
model also fails, the decomposition collapses to "undetectable + response/repair" and the headline
recoverable-value number goes to roughly zero. Two things de-risk this: (i) the log-warning channel
already gives a defensible detectable fraction (63.7% vs 16.5% control) independent of any model, so
build the paper on that and treat the NBM as a secondary, additive instrument; (ii) decide the
detection-model design and its control/null protocol *before* looking at outcomes, because with ~200
events it is easy to tune a detector into significance.

**3. `Externally stopped` and `Manual stop - remote` are IEC "Forced outage" but are not turbine faults.**
Together 1,883 events and ~2,410+ MWh. Grid events are also classified inconsistently — `Externally
stopped` is `Forced outage` while `Grid loss`, `Grid error` and `Grid disconnection for self-protection`
are `Out of Electrical Specification`. Any "forced outage = fault" mapping silently imports 23% grid
events. The event-inclusion rule must be explicit and stated in the paper.

**4. 26.1% of interval events overlap a prior event on the same turbine; 8,680 are exact duplicates.**
Duplicates are concentrated pathologically (Penmanshiel WT01 alone has 4,190, 48% of the total).
Overlapping stops double-charge the same downtime — the two Penmanshiel WT10 events of 2023-03-24
each claim ~420 MWh for one physical outage. Downtime and lost energy must be computed on **merged**
intervals; summing per-event durations or per-event lost MWh over-counts.

**5. Coverage is not the "20 turbines × 9 years" the plan assumes — it is 171 turbine-years with holes.**
Penmanshiel has no WT03 (14 not 15); **Penmanshiel WT01–WT10 stop at the end of 2023** (only WT11–15
have 2024); and **January 2023 is entirely missing** for Penmanshiel WT01–WT10 in both the SCADA
(48,096 rows instead of 52,560) and the event log (6 of 9 turbines have no January events). 2016 is a
commissioning year at both sites. Penmanshiel drivetrain temperatures do not exist before 2018 and
particle count not before 2019, so a temperature-based NBM has **no usable Penmanshiel history before
2019** — which removes the years with the highest forced-outage counts from model training.

**6. Schema drift will silently corrupt a multi-year concatenation.** 385 distinct column names, only
287 in every farm-year; column counts 299→303→312 (Kelmarsh) and 300→363→372 (Penmanshiel); the
`mm/ss`→`mm/s2` acceleration rename at the 2023 boundary; two extra status-log columns from 2021.
None of this raises an error — it produces half-empty columns.

**7. The 2023–2024 exports contain ~41× all-NaN padding rows.** A Kelmarsh 2023 turbine-year parses
as **2,174,760 rows for 52,560 distinct timestamps** (median 41, max 81 rows per timestamp; exactly
one populated). This is why those members are 2.9–3.8 GB. Naively loaded it will exhaust memory,
and any per-year completeness statistic computed on raw row counts will be wrong by a factor of 41
(e.g. "Power is 2.4% complete in 2023" instead of 99.8%). Handled in `wtio.read_member`.

**8. The derived columns the study depends on are undocumented.** The eleven potential-power variants
and thirty lost-production columns appear in neither farm's `dataSignalMapping`. Their semantics are
established here only empirically. This is a reviewer-facing weakness; the mitigation is the §5
validation — showing that the integral of `Cascading potential power` reproduces the operator's own
`Lost Production to Downtime` to a ratio of 1.0004 — plus, if it matters, an email to Charlie Plumley
(the dataset author invites contact).

**9. Two sites, one manufacturer, one country.** Senvion MM82/MM92, both UK, both Cubico-operated,
both exported from the same Greenbyte instance with the same derived-column semantics. External
validity is genuinely limited and the paper should say so rather than be told so.

### Not a risk (resolved by this profiling)
- **Timezone/DST**: all 198 SCADA members and all status members are UTC; the 10-minute grid is
  complete and gap-free; no DST handling needed.
- **Curtailment confound**: 556 MWh in nine years (0.06%), and cleanly labelled three independent ways
  (`Status == 'Curtailment'`, service contract category, and the per-cause curtailment columns).
  Zero curtailment inside any sampled outage window.
- **Counterfactual defensibility**: the operator ships its own lost-production accounting and this
  profiling reproduces it to 0.04%.
- **Log timestamp quality**: `Duration` matches `end − start` to 0.0 s across all 294,667 interval
  events; no negative durations; start timestamps parse for all 1.57 M rows.

---

## 8. Files produced

In this directory (small, git-safe):
- `MANIFEST.json` — record IDs, version DOIs, per-file sizes, MD5s, verification status, download date.
- `PROFILE.md` — this document.
- `wtio.py` · `download.py` · `build_status.py` · `full_pass.py` · `analyse_status.py` ·
  `smoke_precursors.py` · `report.py` — the pipeline.

On the external volume (`…/wind-turbine-warning-gap-data/`), **not** in the project tree:
- `raw/` 11.33 GB of zips · `extract/` 136 MB (Kelmarsh 1, 2018) · `derived/`:
  `status_all.parquet` (1.57 M event rows), `scada_coverage.csv` (198 turbine-years × ~120 metrics),
  `headers_by_member.csv` (64,516 rows), `fo_alignment.csv` / `fo_alignment_dedup.csv` (6,352 events),
  `events_per_turbine_year.csv`, `zip_inventory.csv`, `smoke_*.csv`, and the raw report text.
