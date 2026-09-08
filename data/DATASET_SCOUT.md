# Dataset scout - candidates for external-validity replication

Scouted 2026-09-03. Purpose: find OPEN wind-farm datasets that could replicate the
actionable-warning-gap analysis beyond Kelmarsh + Penmanshiel (20 Senvion MM82/92
turbines, 171 turbine-years, one operator/platform - the standing reviewer objection).

**Bar a candidate must clear** (all four):
1. Operator-visible event log with a **warning-or-alarm row type distinct from stop/fault
   rows** - so "was a warning available before the stop?" is answerable. A bare annotated
   failure list fails.
2. Lost energy per outage computable: a potential/expected-power column, or 10-min power +
   wind speed sufficient to fit a power curve, with coverage enough to bound outage windows.
3. Open licence (CC-BY or similar) or at minimum free registered access.
4. Multi-month-to-multi-year span, real operational farm.

**Method note.** Every verdict below marked VERIFIED was checked against the actual shipped
files - data dictionaries, README, or the log files themselves - not against abstracts or
repository listing pages. Where the archive was too large to download (boot disk had 2.1 GB
free), files were inspected in place by reading the ZIP central directory over HTTP range
requests and inflating single members. Claims I could not verify are labelled as such.

---

## Verdict table

| # | Dataset | Farms / turbines / span | Warning channel - the make-or-break column | Lost energy | Licence / access | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Hill of Towie** (RES, Moray, Scotland). Zenodo [10.5281/zenodo.20204946](https://doi.org/10.5281/zenodo.20204946) (v2.0.0), v1 = 14870023 | 1 farm, **21** Siemens SWT-2.3-VS-82, Jan 2016 - Apr 2026 (v2; v1 ends Aug 2024) ⇒ **~215 turbine-years** | **YES, structurally - VERIFIED, but the dictionary is crippled.** `tables_description.csv` states `tblAlarmLog` = *"Log of stopping and non-stopping events/alarms"*, and `alarms_description.csv` carries a **`Stopping`** column (0/1) - e.g. `20,Large generator Cut-in,0` vs `8000,Windspeed too high to operate,1`. That is exactly the warning-vs-stop split. **But**: I extracted `tblAlarmLog_2016_12.csv` and its columns are only `TimeOn,TimeOff,StationNr,Alarmcode` - **no message text**. The shipped dictionary documents **12 codes**; that one month alone contains **167 distinct codes**, and **34.4 % of alarm rows carry an undocumented code**. v2.0.0 (May 2026) still ships the same 12-row dictionary - VERIFIED. | Power-curve fit: `wtc_ActPower_mean` [kW] + three wind-speed channels at 10 min. **No potential-power column.** Outage windows are well served: `ShutdownDuration.csv` gives downtime seconds per turbine per 10 min (VERIFIED header), and `tblSCTurFlag` carries `wtc_ScTurSto_timeon` = "time turbine error active in period". Neither is categorised (no forced vs scheduled vs grid). | **CC-BY-4.0**, Zenodo, no registration | **USABLE WITH CAVEATS** - best external-validity payoff, gated on obtaining the full alarm-code dictionary |
| 2 | **SMD10TOWFGR** - ten-turbine onshore farm, Greece (Ntafalias, Visvardi, Weißenfeld / AIT). Zenodo [10.5281/zenodo.14546480](https://doi.org/10.5281/zenodo.14546480) | 1 farm, **10** turbines, 1 Jan - 30 Jun 2020 ⇒ **5 turbine-years** | **YES - explicit, operator-typed, VERIFIED.** Extracted the `WT01_logs` sheet: columns are `Code, Description, Detected, Device ack., Reset/Run, Duration, Event type, Severity`. `Event type` takes four values - **`Warning log (W)`**, **`Alarm log (A)`**, `Operation log (O)`, `System log (S)` - plus a numeric `Severity`. This is the closest structural analogue to the Greenbyte Warning row found anywhere. **Caveat: it is thin.** Per turbine over 6 months: WT01 = 20 W / 74 A, WT05 = 45 W / 66 A, WT10 = 24 W / 49 A ⇒ roughly **300 warnings and 600 alarms fleet-wide**. | **YES, directly** - `Grid Production PossiblePower Avg. [W]` is a true potential-power column (VERIFIED in the 132-column SCADA header), so `E = Σ(Possible − Actual)` transfers unchanged from the current pipeline. Log also carries `Duration` and `Reset/Run` per event. | **CC-BY-4.0**, Zenodo, no registration | **USABLE WITH CAVEATS** - drop-in method match, but sample is ~34× smaller than the current corpus |
| 3 | **EDP Open Data**, Wind Farm 1, Portugal | 1 farm, 4 turbines (T01/T06/T07/T11), 2016-2017 ⇒ ~8 turbine-years | **NO - VERIFIED by downloading the actual file.** `Wind Turbines Logs 2017.xlsx` has **134,304 rows** and exactly five columns: `Time_Detected, Time_Reset, Turbine_Identifier, Remark, Unit_Title_Destination`. **There is no severity, status, type or category column of any kind** - only free-text `Remark`. `Time_Reset` is populated in **0.5 %** of rows, so it cannot proxy "this was a stop that got cleared"; `Unit_Title_Destination` is null in 134,291 of 134,304 rows. Masking digits leaves **235 message templates**. Separately, `opendata-wind-failures-2017.xlsx` is a **12-row** list (`Turbine_ID, Component, Timestamp, Remarks`) - the bare failure annotation the bar explicitly rejects. | Power + wind speed present (83 SCADA columns); no potential-power column. Fatal separately: ~28 failure events across both years is far too few for an energy-weighted decomposition. | CC BY-SA 4.0, free download, no registration | **FAILS** - no operator-typed warning channel; severity would have to be hand-assigned to 235 templates, which destroys the design's central claim that the warning is operator-visible *by construction* |
| 4 | **CARE to Compare** (Gück, Zhang et al.). Zenodo [10.5281/zenodo.15846963](https://doi.org/10.5281/zenodo.15846963) | 3 farms, **36** turbines, **89 turbine-years** | **NO - VERIFIED from the shipped `README.md`.** The only status channel is `status_type_id`, with six *operating states*: `0 Normal Operation, 1 Derated Operation, 2 Idling, 3 Service, 4 Downtime, 5 Other`. That is an operating-mode flag, not a warning channel - nothing in it means "a warning was raised and shown to an operator". `event_info.csv` is a root-cause annotation list (`Transformer failure`, `Hydraulic group`). | Fails independently: *"The sensor data and time stamps are anonymized"*, and the corpus is chopped into **95 per-event train/test windows**, not continuous per-turbine series - so a fleet outage inventory and annual lost-energy accounting cannot be built. | CC-BY-SA-4.0 | **FAILS** - and note Wind Farm A **is the EDP data**, so it is not an independent source either |
| 5 | **ENGIE La Haute Borne**, Meuse, France | 1 farm, 4 **Senvion MM82**, 2013-2020 | **NO.** SCADA only - 136 columns = 34 measurements × avg/min/max/std. No status, event or alarm log in the release. (Not re-verified at file level; portal reported intermittently offline.) | Power + wind speed present; no potential power | Etalab Open Licence 2.0 | **FAILS** - no event log, and it is the *same OEM* as the current corpus, so it would not answer the reviewer anyway |
| 6 | **Fuhrländer FL2500** (*Scientific Data* 11:255, 2024). Figshare 10.6084/m9.figshare.25201631 | 1 farm, 5 turbines, 2012-2014 ⇒ ~15 turbine-years | **NO - VERIFIED.** Fetched `dataset/wind_plant_data.json`: `alarm_dictionary` has exactly four fields - `alarm_id, alarm_desc, alarm_system, alarm_subsystem` (369 alarms). **No severity or stopping field.** 27 of 369 descriptions merely contain the word "warn" as free text ("Ice warning", "MGB FilterOil Warning") - a text heuristic, not an operator-typed channel. | 5-min SCADA with active power + wind speed; power-curve fittable | CC-BY-4.0 (data); loader code EPL-2.0 | **FAILS as a replication** - but see recommendation 3: its `alarm_system` taxonomy is independently useful |
| 7 | **SMARTEOLE**, France. Zenodo 7342466 | 7 **Senvion MM82**, Feb-May 2020 (3 months) | **NO.** Wake-steering field campaign. Fatal: *"all timesteps when at least one turbine was stopped were removed"* - the outages are deleted from the release. | n/a | Etalab 2.0 | **FAILS** |
| 8 | **Altahullion** (RES/TRIG, N. Ireland). Zenodo 10.5281/zenodo.19948235 | 6 months | **NO** - SCADA + LiDAR only; no alarm/event log in the record | n/a | CC-BY-4.0 | **FAILS** - sibling of Hill of Towie but without the alarm log |
| 9 | **ORE Catapult Levenmouth** (7 MW, Fife) | 1 turbine, 2017- | Alarm log exists, but the documented framing is *"each record in the alarm log is one alarm that shows why a turbine has been stopped"* - no evidence of a warning tier | 1 Hz, 574 sensors | **Not open** - application plus *"a small charge to cover the data retrieval"* | **FAILS** - access terms, single turbine, no warning tier evidenced |
| 10 | **WinJi Gearbox Challenge** (WeDoWind) | 5 turbines, ~2 y | Gearbox-failure annotations; challenge closed, data behind platform signup. **Could not verify** any warning row type | unverified | Platform registration; challenge inactive | **FAILS (unverifiable)** |
| 11 | **Sandia CREW** | 800+ turbines | Per-turbine data never released - *"no individual wind plant, turbine manufacturer, or subcomponent vendor will have its reliability information released"*; aggregate benchmark reports only | n/a | Aggregate only | **FAILS** |
| 12 | **NREL A2e / CART2 / SUMR-D**; **WFIP2 "log"** | research turbines; met campaign | No operator alarm log. WFIP2's "log" is an *instrument* event log from an atmospheric campaign, not a turbine one | n/a | CC-BY-4.0 | **FAILS** - not commercial farms |
| 13 | **Aventa AV-7** (ETH/OST) | 1× 7 kW research turbine | Curated failure-injection case studies (icing, imbalance, pitch coupling), not an operator log | n/a | Open | **FAILS** |
| 14 | **IEA Wind Task 43** | - | Standards/working group, **not a data host**. Its Data User Group discusses alarm-code methodology but publishes no operational dataset | n/a | n/a | **FAILS** |
| 15 | **Ørsted Anholt / Westermost Rough** | 111 / 35 turbines | SCADA only | - | **NDA required** | **FAILS** |
| 16 | SCADA-only group: Norrekaer, Delabole, PCWG, Pedra do Sal + Beberibe (Brazil, NetCDF micromet), Dundalk, Björkö, São Paulo, Loegtved, Kaggle Turkey | 1-41 turbines each | **NO** - no status/alarm/event log of any kind | varies | mixed | **FAILS** as a group |

**Search variants run** (zero results for one phrasing was not treated as absence): "status log", "event log", "alarm log", "fault log", "downtime log", "warning", "SCADA", "10-minute SCADA open data", "Greenbyte", "Cubico wind", across Zenodo (API, since the HTML search is JS-rendered), IEEE DataPort, Figshare, Mendeley Data, Dryad, Harvard Dataverse, *Data in Brief*, *Scientific Data*, Wind Energy Science, Wiley *Wind Energy*, OEDI/A2e, and the `sltzgs/OpenWindSCADA` curated index (which is what surfaced Hill of Towie).

**Notable negative:** no third Cubico/Greenbyte sibling to Kelmarsh and Penmanshiel exists. Their related-identifiers and Zenodo communities (`wedowind`, `openoa`) were checked directly. The nearest analogue is a *different* operator's series - RES/TRIG, which published Hill of Towie and Altahullion.

---

## Ranked recommendation

### 1. Hill of Towie - integrate if, and only if, RES supplies the alarm-code dictionary
The single best answer to the external-validity objection, because it is independent on
**every** axis the reviewer will name: different OEM (Siemens SWT-2.3-82 vs Senvion
MM82/92), different operator (RES vs Cubico), different SCADA stack (raw vendor SCADA
backup vs Greenbyte), different region - at **comparable scale** (21 turbines, ~215
turbine-years vs the current 20 and 171). It would roughly double the corpus and let the
paper claim two operators, two OEMs, two platforms.

The blocker is precise and verified: the alarm log is numeric codes only, and the shipped
dictionary covers 12 of 167+ codes. Without a fuller dictionary you can recover neither the
`Stopping` flag for most rows nor any component family - and component-family matching is
the paper's headline (same-component) rule.

- **Effort if RES supplies the codes: medium** (~1-2 weeks). Outage windows come free from
  `ShutdownDuration` / `wtc_ScTurSto_timeon`; the decomposition logic ports directly. Two
  genuine method changes: fit a power curve because there is no potential-power column, and
  build a forced-vs-scheduled split, since neither the shutdown table nor the alarm codes
  carry an IEC category.
- **Effort if RES does not: do not attempt.** Reconstructing 160 code semantics by
  inference is exactly the researcher-constructed labelling the design exists to avoid.
- **Action now:** email RES. They are an active, willing open-data publisher (v2.0.0 shipped
  May 2026; public analysis repo at `github.com/resgroup/hill-of-towie-open-source-analysis`),
  the ask is small and specific - the full `Alarm Code / Description / Stopping` table. This is the highest-leverage
  single action available. Note the timing risk against the **Nov 10** deadline: unless RES
  replies within roughly two weeks, this lands in the journal version, not PES GM.

### 2. Greek SMD10TOWFGR - integrate now, as a structural replication
The best *methodological* match found. It has both things nothing else has together: an
explicit operator-typed `Warning log (W)` row distinct from `Alarm log (A)`, and a true
`PossiblePower` column that makes the lost-energy formula identical to the one already in
use. The existing pipeline transfers with little more than a column-name map.

Be honest about what it buys. At 5 turbine-years and ~300 fleet-wide warnings it cannot
carry a second headline number - the CIs would be very wide. What it *can* do is answer the
reviewer's actual question: does the warning channel exist, and does it precede stops, in a
second country, OEM and SCADA platform? A short "we replicated the warned-share and
lead-time distribution on an independent Greek farm" subsection, with the caveat stated,
converts the limitation from "we only looked at one operator" into "we checked, and the
mechanism holds elsewhere".

- **Effort: low** (~2-4 days). Feasible before Nov 10. One wrinkle: the whole corpus is a
  single 180 MB `.xlsx` with 20 sheets - parse it to Parquet once (streaming; do not load
  it whole, and mind the 2.1 GB free on the boot disk).

### 3. Fuhrländer - not a replication; use it as an independent component taxonomy
Its 369-alarm dictionary maps every alarm to `alarm_system` / `alarm_subsystem` across nine
published systems (Turbine 150, Rotor 65, Transmission 64, Generator 32, Yaw 26, Converter
17, Transformer 7, Nacelle 5, Tower 3). That is an externally published, peer-reviewed
component taxonomy - useful for showing that `analysis/component_map.csv` is not bespoke to
this paper. Relevant to the converter finding specifically, since "Converter" is a first-class
system there too.

- **Effort: very low** (a few hours), and it is purely additive - a defensive citation for
  the frozen component map, nothing more.

---

## Bottom line

**Nothing found replicates the full analysis as-is, and the honest reading is that the
Kelmarsh/Penmanshiel pairing is close to unique in the open-data landscape** - it is the
only public corpus combining an operator-typed warning row, a potential-power column, IEC
outage categories, and multi-year multi-turbine coverage in one release. That is worth
stating plainly in the Limitations section; it is also, incidentally, part of why the paper
is novel.

Two real options exist, and they are complementary rather than competing:

- **Greek SMD10TOWFGR is achievable before Nov 10** and directly addresses the reviewer.
  It trades statistical weight for independence - a small, clean, second-platform check that
  the warning channel is a general feature of wind SCADA and not a Greenbyte artefact.
- **Hill of Towie is the one that would genuinely settle external validity**, but it is
  gated on a single email to RES. Send it now; treat it as a journal-version asset and a
  PES GM bonus only if they reply quickly.

If neither lands in time, the defensible fallback is not silence: report that an exhaustive
scan of the open landscape found exactly one other dataset with a true operator warning
channel (the Greek farm) and one more that would qualify but ships an incomplete alarm
dictionary (Hill of Towie). That framing turns the external-validity gap into a documented
finding about open wind data, which is a stronger position than conceding the limitation
without evidence.


---

## UPDATE 2026-09-07 - full alarm dictionary not public; public inventory built

The shipped `alarms_description.csv` documents 12 codes. A fuller code table for
the SWT-2.3 alarm log is not publicly available: the dataset's maintainers (RES)
confirmed on request that the OEM documentation they hold is confidential, and
suggested a public, community-correctable inventory built from the open data as
the practical route. That inventory is `data/hill-of-towie/hot_alarm_code_inventory.csv`
(589 distinct codes, 6,402,594 rows, all 124 monthly tblAlarmLog files 2016-01 to
2026-04, read by HTTP range requests via `analysis/hot_zipranged.py` and
`analysis/hot_alarm_inventory.py`, nothing downloaded in full), with
`hot_alarm_inventory_summary.md`; it is posted for correction at
https://github.com/resgroup/hill-of-towie-open-source-analysis/discussions/80.
Key facts: documented codes cover 78.9% of rows, but that is codes 20/25
(generator cut-in/out); 581 of 589 codes have no public meaning; 4 of the 12
documented codes never occur. v2.0.0 extends the record to Jan 2016 - Apr 2026
(~236 turbine-years).

Remaining gaps before integration: (a) a public code dictionary (blocking);
(b) a Stopping flag beyond the 12 shipped codes (ShutdownDuration.csv and
tblSCTurFlag are the fallback for outage windows); (c) no potential-power
column, so a power-curve fit is required; (d) no IEC category, so the
forced-vs-scheduled split must be constructed and frozen pre-outcome.
Status for the paper: Hill of Towie replication is BLOCKED on (a).

## UPDATE 2026-09-07 - Greek SMD10TOWFGR: full count replaces the extrapolation

Row 2 and section 2 above quote "roughly **300** warnings and **600** alarms fleet-wide".
That figure was an extrapolation: three of the ten turbine sheets were read (WT01, WT05,
WT10) and scaled by 10/3. The whole workbook has now been counted
(`analysis/greek_log_counts.py`, openpyxl `read_only` streaming pass, one sheet at a time,
over `SCADA__monitoring_dataset_2020.xlsx`, 180,707,378 bytes, Zenodo
[10.5281/zenodo.14546480](https://doi.org/10.5281/zenodo.14546480), downloaded to the local data volume). The workbook holds 20
sheets - `WT01_data.csv` .. `WT10_data.csv` and `WT01_logs.csv` .. `WT10_logs.csv`; the
`.csv` is part of the sheet name.

| sheet | log rows | Warning log (W) | Alarm log (A) | Operation log (O) | System log (S) |
|---|---:|---:|---:|---:|---:|
| WT01_logs.csv | 16,037 | 20 | 74 | 15,788 | 155 |
| WT02_logs.csv | 25,444 | 60 | 61 | 25,153 | 170 |
| WT03_logs.csv | 23,731 | 129 | 395 | 22,682 | 525 |
| WT04_logs.csv | 19,623 | 18 | 37 | 19,508 | 60 |
| WT05_logs.csv | 22,501 | 45 | 66 | 22,177 | 213 |
| WT06_logs.csv | 25,293 | 128 | 74 | 24,871 | 220 |
| WT07_logs.csv | 25,645 | 62 | 94 | 25,354 | 135 |
| WT08_logs.csv | 24,202 | 120 | 66 | 23,821 | 195 |
| WT09_logs.csv | 24,083 | 82 | 86 | 23,820 | 95 |
| WT10_logs.csv | 24,059 | 24 | 49 | 23,933 | 53 |
| **fleet** | **230,618** | **688** | **1,002** | **227,107** | **1,821** |

`Event type` takes exactly the four documented values and nothing else - no blanks, no
fifth category - across all 230,618 rows.

**So the fleet-wide count is 688 Warning-log rows and 1,002 Alarm-log rows over
1 Jan - 30 Jun 2020, not ~300 and ~600.** The three sheets the original estimate used
reproduce exactly (WT01 20/74, WT05 45/66, WT10 24/49), so the arithmetic was right and
the sample was unlucky: those three are among the quietest turbines. Warnings are
**2.3x** the extrapolation, alarms **1.7x**. Dispersion across turbines is large - WT04
has 18 warnings, WT03 has 129, and WT03 alone carries 39% of the fleet's alarms.

Assessment unchanged in direction, improved in degree: the corpus is still far too small
for a second headline (688 warnings over ~5 turbine-years against 17,793 post-COD warning
rows over 159.06 turbine-years here, a factor of ~26 on warning supply and ~32 on
exposure), but a structural replication of the warned-share and lead-time distribution is
better supported than the earlier number suggested. Any paper sentence saying "roughly 300
warnings" must be corrected to 688.
