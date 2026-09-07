# Stage-4 results - STUDY_DESIGN v1.4 robustness analyses

Four analyses added by STUDY_DESIGN v1.4 (2026-09-03), motivated by a cross-model
adversarial review (GPT-5.6 referee pass on the full artefact bundle) and pre-registered
before computation. Nothing frozen was changed: `component_map.csv` remains the primary
map, the event/attribution/control definitions and the primary cell are untouched, and
every existing script and CSV is left exactly as it was.

Every number below is read back out of an artefact one of these scripts wrote; nothing
is hand-computed. Provenance is given as **`script.py` -> `artefact` [row selector]**.

```
map_sensitivity.py    -> analysis/map_sensitivity.csv
late_warning_all.py   -> analysis/late_warning_all.csv
cluster_robustness.py -> analysis/cluster_robustness.csv
claim_ledger.py       -> analysis/claim_ledger.csv
```

Primary cell throughout, unchanged: **T2 wide-grid**, **same-component** matching,
**72 h** lookback, **T_act = 6 h**, **-45 d** controls, **energy-weighted**.

### Validation gate (run inside every script before anything else)

T2 wide-grid population **4,213 events / 9,386.5 MWh**; energy-weighted decomposition at
T_act = 6 h, same-component 72 h **83.78 / 8.69 / 7.53 %**; same-component warned
numerator **979 events / 1,522.8 MWh**; converter family **977 events, 1,741.3 MWh,
0.0 % same-component warned**. All reproduced exactly, as an assertion, in
`map_sensitivity.py`, `cluster_robustness.py` and `claim_ledger.py`
*(console `VALIDATION GATE` blocks)*.

`map_sensitivity.py` and `late_warning_all.py` additionally rebuild the warning join
from `warnings.parquet` and must reproduce the frozen attribution columns **exactly**
before any variant is computed - `any_n_72h` (44,353 rows), `same_n_72h` /
`same_warn_72h` / `same_lead_h_72h` (26,174 rows), plus the `family` and `families_all`
labels on all 6,050 events *(console `JOIN CHECK` lines; the construction is
`warning_dynamics.py`'s, extended to the family labels because a flipped map changes
them)*.

---

## A. Component-map sensitivity (v1.4(a))

### A.0 What moves and what does not

`map_sensitivity.py` perturbs **family matching only**. Under a modified map it
re-derives each event's `families_all` from its constituent stop messages and its
`family` from `primary_message`, re-derives each warning row's family from its message,
and re-runs the same-component rule (warning family in the event's family set, and not
one of external/grid/manual).

**Tier membership is never touched, and the script asserts it.** `T2_wide_grid` is a
message-level *service-category* filter fixed in stage 1 (`build_events.py`'s
`n_grid_ext_msgs` / `n_manual_msgs` off `common.GRID_MESSAGES`,
`GRID_MESSAGES_EXTRA`, `MANUAL_MESSAGES`); it is not a function of the component map.
So flipping `WEC shut down` from `control` to `manual` gives that event the family set
{manual}, which can never same-match - the event moves from the warned bucket to
**unwarned** - but it **stays in T2 and stays in the denominator**. Likewise
`High yaw load` -> `external` cannot drop an event from T1/T2. The denominator is
4,213 events / 9,386.5 MWh in all 1,152 variants; `map_sensitivity.py` asserts
`n_events` and `E_mwh` are single-valued across the whole CSV.

The any-warning rule ignores families entirely and is therefore invariant to every
flip; it is not varied.

### A.1 The flip set, and the rationale text that authorises each alternative

Nine map entries (or deliberately-paired sets of entries) whose own `rationale` column
in the frozen `component_map.csv` names an alternative family. Quotes are verbatim from
that column and are carried in `map_sensitivity.csv` [`rationale_quotes`].

| slot | messages flipped | frozen -> alternative(s) | authorising rationale text (abridged) |
|---|---|---|---|
| `bp_repeat` | stop `Repeating error BP52` **+** warning `Repeating error BP 0` | control -> **pitch** | "'BP' also prefixes pitch messages ('Pitch too slow BP180'), so a pitch reading is possible. ... Alternative: pitch." / "both are assigned to `control` so that they can match each other ... Alternative: pitch." - the pair is flipped together because the frozen rationale assigns them together |
| `brake_resistor_chp` | warning `Error brake resistor CHP` | pitch -> **converter**, **brake_hydraulic** | "A converter DC-link chopper reading is equally defensible. Alternatives: converter, brake_hydraulic. FLAGGED for orchestrator review." |
| `time_sync` | warnings `Check time synchronization` **+** `Time sync. failed (SNTP error)` | external -> **control** | "Putting it in `control` would let 526 clock-drift notices match controller stops. Alternative: control." (the SNTP row reads "As above") |
| `cms_drivetrain` | warnings `Comm.err. IEC server <- CMS drive tr.`, `Comm.err. IEC client -> CMS drive tr.`, `CMS drive train system error` | comms -> **drivetrain** | "Assigned to `comms` because the message reports the monitoring channel failing, not a drivetrain fault - the conservative reading. Alternative: drivetrain." |
| `current_asymmetry` | stop `Current asymmetry` | converter -> **generator** | "service category 'Generator and Converter errors (20)' does not separate the two ... Alternative: generator." |
| `wec_shut_down` | stop `WEC shut down` | control -> **manual** | "Assigned to `control` rather than `manual` because nothing in the message implies a human action. Alternative: manual." |
| `no_speed_development` | stop `No speed development` | control -> **pitch**, **brake_hydraulic** | "the physical cause could be pitch, brake or drivetrain ... Alternatives: pitch, brake_hydraulic." |
| `high_yaw_load` | stop `High yaw load` | yaw -> **external** | "service category is 'External stop (climate) (6)', which would argue for `external` ... Alternative: external." |
| `cable_overload` | warning `Cable overload` | converter -> **electrical** | "read as the converter output cabling. Alternative: electrical." |

The first six are the v1.4(a) required set (the five ambiguous calls flagged at the v1.1
freeze, plus `WEC shut down`); the last three are the remaining entries whose rationale
also names an alternative, added for completeness. Options within a slot are mutually
exclusive, so the full space is 2x3x2x2x2x2x3x2x2 = **1,152 variants**, all of which are
enumerated and written to `map_sensitivity.csv` (one row each, tagged
`variant_type` = frozen / single_flip / joint).

### A.2 Single flips

*(`map_sensitivity.py` -> `map_sensitivity.csv` [`n_slots_flipped<=1`], sorted by
`delta_actionable_pp`. Headline = energy-weighted actionable-unacted share of T2 lost
energy at T_act = 6 h.)*

| variant | headline | delta | unwarned | short-lead | warned n / MWh | converter same-comp warned (E) | big event bucket |
|---|---|---|---|---|---|---|---|
| `wec_shut_down` control -> **manual** | **5.237 %** | **-2.291 pp** | 86.068 % | 8.695 % | 977 / 1,307.7 | 0.0 % | **unwarned** |
| `brake_resistor_chp` pitch -> **brake_hydraulic** | 7.388 % | -0.140 pp | 84.417 % | 8.196 % | 975 / 1,462.7 | 0.0 % | actionable-unacted |
| **frozen map (primary)** | **7.528 %** | - | 83.777 % | 8.695 % | **979 / 1,522.8** | **0.0 %** | actionable-unacted |
| `cable_overload` converter -> electrical | 7.528 % | 0.000 pp | 83.777 % | 8.695 % | 979 / 1,522.8 | 0.0 % | actionable-unacted |
| `high_yaw_load` yaw -> external | 7.528 % | 0.000 pp | 83.777 % | 8.695 % | 979 / 1,522.8 | 0.0 % | actionable-unacted |
| `current_asymmetry` converter -> generator | 7.528 % | 0.000 pp | 83.777 % | 8.695 % | 979 / 1,522.8 | 0.0 % (over 946 / 1,696.3) | actionable-unacted |
| `time_sync` external -> **control** | 7.559 % | +0.031 pp | 83.746 % | 8.695 % | 990 / 1,525.7 | 0.0 % | actionable-unacted |
| `cms_drivetrain` comms -> **drivetrain** | 7.562 % | +0.034 pp | 83.742 % | 8.696 % | 993 / 1,526.0 | 0.0 % | actionable-unacted |
| `no_speed_development` control -> pitch | 7.613 % | +0.085 pp | 83.692 % | 8.695 % | 980 / 1,530.8 | 0.0 % | actionable-unacted |
| `no_speed_development` control -> brake_hydraulic | 7.616 % | +0.088 pp | 83.687 % | 8.696 % | 982 / 1,531.2 | 0.0 % | actionable-unacted |
| `brake_resistor_chp` pitch -> **converter** | 7.951 % | +0.422 pp | 83.614 % | 8.436 % | 1,003 / 1,538.1 | **4.328 %** | actionable-unacted |
| `bp_repeat` control -> **pitch** | **8.377 %** | **+0.849 pp** | 82.722 % | 8.901 % | 1,079 / 1,621.8 | 0.0 % | actionable-unacted |

**Single-flip range: 5.237 % to 8.377 %.** Three flips (`cable_overload`,
`high_yaw_load`, `current_asymmetry`) leave the headline bit-identical; the last of
these does shrink the converter family from 977 events / 1,741.3 MWh to 946 / 1,696.3
(the 31 `Current asymmetry`-primary events move to `generator`) without changing its
zero coverage.

### A.3 Joint combinations

*(same artefact, [`is_adverse_joint`] and [`is_max_joint`].)*

| | headline | delta | flips |
|---|---|---|---|
| **most adverse (minimum over all 1,152)** | **5.097 %** | **-2.431 pp** | `brake_resistor_chp` pitch->brake_hydraulic **+** `wec_shut_down` control->manual |
| maximum over all 1,152 | 8.921 % | +1.393 pp | `bp_repeat` control->pitch **+** `brake_resistor_chp` pitch->converter **+** `cms_drivetrain` comms->drivetrain **+** `no_speed_development` control->brake_hydraulic |

Eight variants tie at each extreme, because the three headline-inert slots
(`current_asymmetry`, `high_yaw_load`, `cable_overload`) can each be set either way -
2x2x2 = 8. The rows above give the minimal flip set at each extreme.

The flips are **not additive**. The two adverse flips sum to -2.431 pp against
-2.291 - 0.140 = -2.431 pp (additive here, coincidentally), but on the favourable side
`time_sync` contributes +0.031 pp alone and **exactly zero** on top of the maximising
combination: once `bp_repeat` and `no_speed_development` leave the `control` family, the
clock-drift warnings have almost no control-family stop energy left to match.

**Full range across all 1,152 variants: 5.097 % - 8.921 %** (frozen 7.528 %).

### A.4 The three questions v1.4(a) asks by name

**(i) Does any variant move the headline outside its existing 95 % CI [1.9, 16.7]?**
**No.** The extremes of the whole 1,152-variant space, 5.097 % and 8.921 %, both sit
well inside [1.95, 16.72] *(`bootstrap.csv` [`tier==T2, rule==same, T_act_h==6,
statistic==E_actionable`])*, and so does every variant in between - the script asserts
`min > 1.9` and `max < 16.7`. The map ambiguity is a **second-order** source of
uncertainty next to sampling: the full map-flip range is 3.8 pp wide, the 95 % CI is
14.8 pp wide. This is the honest answer to the reviewer's map-perturbation request: the
frozen map is not doing the work.

**(ii) Does any flip give `converter` nonzero same-component coverage?**
**Yes - exactly one, and only one.** `Error brake resistor CHP` -> `converter` raises
converter same-component warned coverage from **0.0 %** to **4.33 %** of converter lost
energy (28 of 977 events, **75.4 of 1,741.3 MWh**). Combined with
`current_asymmetry` -> `generator` it reads 2.47 % (16 of 946 events, 42.0 of 1,696.3
MWh) on the smaller converter denominator. No other flip, alone or jointly, moves it off
zero: the converter coverage column takes exactly three values across the 1,152
variants - 0 %, 2.474 %, 4.328 % - and both nonzero values require that one flip
*(`map_sensitivity.csv` [`converter_same_warned_pct_E`])*.

That is a real qualification on RESULTS §0.1's sharpest sentence. The claim "converter
carries 19 % of T2 lost energy and **zero** same-component warnings" is robust to eight
of the nine documented map ambiguities, but under one defensible reading of a single
high-volume warning message (235 rows, and the map's own rationale calls the converter
reading "equally defensible") it becomes 4.3 %, not 0 %. **The paper should state the
finding as "essentially unwatched - 0 % under the frozen map, at most 4.3 % under any
documented alternative reading", not as an unqualified zero.** The structural
observation is unchanged either way: 4.3 % coverage of the second-largest energy family
is still an order of magnitude below anemometry's 84 %.

**(iii) Does the 210.1 MWh Penmanshiel WT04 2023-06-23 event change bucket?**
**Only under `WEC shut down` -> `manual`, and then it goes to `unwarned`.** Across the
1,152 variants the event is actionable-unacted in 576 and unwarned in 576, and the split
is exactly the `wec_shut_down` slot *(`map_sensitivity.csv` [`big_event_bucket`] grouped
on `flips_applied`)*. It is never short-lead.

The mechanism is worth stating because it is not the obvious one. That event's two
same-component warnings are both `Parameter outside limits` (control family, 20.79 h and
19.77 h before the stop), **not** `Repeating error BP 0` - so the BP-repeat flip, the
other `control`-family ambiguity, leaves it untouched. The `manual` flip removes it not
by removing warnings but by making the event's own family set unmatchable. Under
`time_sync` -> `control` the event stays actionable-unacted but its lead **lengthens to
46.39 h**, because a `Check time synchronization` warning 46.4 h before the stop then
counts as same-component *(`map_sensitivity.csv` [`big_event_lead_h`])*.

`WEC shut down` is 4 T2 events / 252.0 MWh, of which **2 events / 215.0 MWh are
actionable-unacted** (event 2178, 210.1 MWh, lead 20.79 h; event 3665, 4.9 MWh, lead
8.79 h). Those 215.0 MWh are 30.4 % of the 706.6 MWh actionable-unacted total, which is
why this one 7-row message is the single most consequential entry in the map.

---

## B. All-warned-events late-warning statistic (v1.4(b))

*(`late_warning_all.py` -> `late_warning_all.csv`; all 979 same-component-warned T2
events, no eligibility restriction, warning sets re-derived under the FROZEN map.)*

### B.1 The identity

"Every in-window same-component warning lies inside the final 24 h" and "the **earliest**
in-window warning lies inside the final 24 h" are the **same event**, not two statistics:
the earliest warning is by construction the one with the largest hours-before, so all
rows are inside 24 h exactly when the maximum is, i.e. exactly when **lead < 24 h**. The
script computes both by independent routes - one by testing every matching row against
the 24 h boundary, one from the frozen lead column - and asserts the two masks are
identical *(console; `assert (all_inside == earliest_inside).all()`)*. Report it as one
number with two readings, not as a coincidence.

### B.2 The numbers

| rule | metric | events | MWh | % of warned events | % of warned energy |
|---|---|---|---|---|---|
| same-component | warned total (denominator) | 979 | 1,522.8 | 100 % | 100 % |
| same-component | **every warning inside the final 24 h** | **379** | **1,217.1** | **38.71 %** | **79.93 %** |
| same-component | (identical set, via lead < 24 h) | 379 | 1,217.1 | 38.71 % | 79.93 % |
| same-component | lead >= 24 h (complement) | 600 | 305.6 | 61.29 % | 20.07 % |
| same-component | every warning inside the final 6 h | 281 | 816.1 | 28.70 % | 53.60 % |
| any-warning | warned total | 2,652 | 4,420.8 | 100 % | 100 % |
| any-warning | **every warning inside the final 24 h** | **1,160** | **1,825.5** | **43.74 %** | **41.29 %** |
| any-warning | lead >= 24 h | 1,492 | 2,595.3 | 56.26 % | 58.71 % |
| any-warning | every warning inside the final 6 h | 829 | 1,198.3 | 31.26 % | 27.11 % |

**Cross-check passes exactly**: the earliest-inside-24 h energy share is
1 - `frac_ge_24h` from `leadtime_stats.csv` to 10 decimal places - 79.9280 % vs
79.9280 % same-component (the "20 %" of RESULTS §4) and 41.2936 % vs 41.2936 %
any-warning; count shares likewise *(console `CROSS-CHECK` lines, asserted at 1e-6)*.

**The headline sentence, now unrestricted: 79.9 % of same-component-warned lost energy
comes from events with no same-component warning at all more than 24 h before the stop,
though those events are only 38.7 % of warned events.** The sign flips with weighting,
as everywhere else in this study.

### B.3 The v1.4(b) disclosure, quantified

*(same artefact, [`metric==trend_eligible_subset_ge3rows`].)*

The v1.3(c) trend statistics required >= 3 matching warning rows (a rate ratio is
undefined on fewer). That subset covers **799 of 979 same-component-warned events
(81.6 %) and 840.5 of 1,522.8 MWh (55.2 %)**, reproducing the figures already written
into the v1.4(b) changelog entry; for any-warning it is 1,752 of 2,652 events (66.1 %)
and 2,350.2 of 4,420.8 MWh (53.2 %). Within that subset, 229 events / 725.7 MWh have
every warning inside the final 24 h - which is exactly RESULTS_v13 §C.2's "229 of the
799 ... have zero matching warning rows before the last 24 h", reproduced here from an
independent rebuild.

So the subset-only reading understated the unrestricted one on events (229 vs 379) and
on energy (725.7 vs 1,217.1 MWh) but pointed the same way. The paper should quote the
unrestricted 379 / 1,217.1 MWh / 79.9 % and state the subset's coverage in the same
sentence.

---

## C. Small-cluster inference robustness (v1.4(c))

*(`cluster_robustness.py` -> `cluster_robustness.csv`; headline = energy-weighted
actionable-unacted share, T2 wide-grid, same-component, 72 h, T_act = 6 h.)*

The fleet is **6 Kelmarsh + 14 Penmanshiel** turbines (not 10/10 - RESULTS §8's "10
turbines per site" is wrong and should be corrected in the paper), and the per-farm
headline differs by a factor of four (2.36 % vs 9.30 %, RESULTS §8), so an unstratified
outer resample can draw a replicate with very few Kelmarsh turbines.

### C.1 Farm-stratified bootstrap

| construction | point | 95 % CI | bootstrap sd | reps / seed |
|---|---|---|---|---|
| **farm-stratified** (6 within Kelmarsh, 14 within Penmanshiel, then events within turbine) | **7.528 %** | **[1.979, 16.388]** | 3.819 pp | 10,000 / 20260904 |
| unstratified (**quoted**, not recomputed, from `bootstrap.csv`) | 7.528 % | [1.947, 16.717] | 3.880 pp | 10,000 / 20260827 |

**Stratifying changes nothing that matters**: the interval narrows by 0.36 pp at the top
and 0.03 pp at the bottom, and the bootstrap sd falls by 0.06 pp. The frozen CI is not
an artefact of unbalanced farm draws, and the paper can keep quoting [1.9, 16.7]. The
script asserts that `bootstrap.csv`'s point estimate equals the recomputed one before
quoting its interval.

### C.2 Leave-one-turbine-out

*(same artefact, [`analysis==leave_one_turbine_out`].)*

| | headline | shift |
|---|---|---|
| all 20 turbines | 7.528 % | - |
| **minimum** (drop **Penmanshiel WT04**) | **5.606 %** | **-1.922 pp** |
| second most influential (drop Penmanshiel WT07) | 5.769 % | -1.759 pp |
| maximum (drop Penmanshiel WT02) | 8.048 % | +0.520 pp |

**Range 5.606 % - 8.048 %, width 2.442 pp; most influential turbine Penmanshiel WT04
(-1.922 pp).** WT04 is the turbine that carries the 210.1 MWh event of RESULTS §7 (28
actionable events / 213.9 MWh on that turbine alone); WT07 carries 19 actionable events
/ 194.0 MWh. Two of twenty turbines carry 58 % of the actionable-unacted energy.

This is the cluster-level restatement of the one-event dependence already in RESULTS §7,
and it is reassuring in one respect: dropping the single most influential *turbine* moves
the headline by 1.9 pp, less than dropping the single most influential *event* moved it
in the leave-one-event-out analysis (2.12 pp), and the whole leave-one-turbine-out range
sits inside the 95 % CI.

---

## D. Claim ledger (v1.4(d))

*(`claim_ledger.py` -> `claim_ledger.csv`; each row records the value printed in
`paper/main.tex`, the value recomputed from the frozen parquets, the tolerance implied
by the printed precision, and a verdict.)*

| id | claim (paper location) | paper | computed | verdict |
|---|---|---|---|---|
| C1 | the 200 largest T2 events carry 83.3 % of T2 lost energy (L301) | 83.3 % | **83.277 %** | REPRODUCES |
| C2a | 1,745 of 4,213 T2 events carry zero measured energy (L281) | 1,745 | **1,745** | REPRODUCES |
| C2b | ...which is 41.4 % of T2 events | 41.4 % | **41.419 %** | REPRODUCES |
| C3a | controls match for 99.2 % of T2 events (L330) | 99.2 % | **99.217 %** | REPRODUCES |
| C3b | 70.8 % of T2 controls at the exact -45 d anchor (L330) | 70.8 % | **70.757 %** | REPRODUCES |
| C4 | n = 1,870 T2 outages shorter than ten minutes (L359 / fig. 3) | 1,870 | **1,870** | REPRODUCES |
| C5a | 698 actionable-unacted T2 events (L491/L599) | 698 | **698** | REPRODUCES |
| C5b | 532 of the 698 carry zero measured energy (L491) | 532 | **532** | REPRODUCES |
| C5c | 166 of the 698 carry the at-risk energy (L599) | 166 | **166** | REPRODUCES |
| C5d | actionable-unacted energy at risk 706.6 MWh (L599) | 706.6 | **706.632** | REPRODUCES |
| C6a | 397 manual-only merged events (L329) | 397 | **397** | REPRODUCES |
| C6b | manual-only events carry 2,321.7 MWh (L329) | 2,321.7 | **2,321.687** | REPRODUCES |
| C6c | manual-only energy is 19.2 % of T0 lost energy (L329) | 19.2 % | **19.188 %** | REPRODUCES |
| C7 | excluding zero-energy events the count-weighted actionable share falls to 6.7 % (L492) | 6.7 % | **6.726 %** | REPRODUCES |

**14 of 14 claims reproduce; 0 mismatches.** Two provenance notes the ledger records
and the paper should carry:

1. **C3a/C3b are the T2 subset, not the T0 population.** `controls_summary.csv` reports
   99.42 % / 72.53 % over all 6,050 T0 events; the paper's 99.2 % / 70.8 % are the
   4,213-event T2 wide-grid subset, which is what reproduces. The two are different
   quantities and the sentence should say "of T2 events" (it does).
2. **C3b's denominator is all 4,213 T2 events**, so the 33 unmatched T2 events count as
   not-at-anchor - the same convention `controls_summary.csv` uses.

C7 was not on the v1.4(d) list but sits in the same sentence as C5b and had no summary
CSV behind it, so it is included.

---

## E. Does any of this move the headline?

**No single flip, and no combination of flips, moves the actionable-unacted share
outside its existing 95 % CI [1.9, 16.7].** The full 1,152-variant map-flip range is
**5.10 % - 8.92 %** against a frozen point of 7.53 %; the widest single flip is
`WEC shut down` -> `manual` at **-2.29 pp** (5.24 %), the widest upward is the BP-repeat
pair -> `pitch` at **+0.85 pp** (8.38 %), and the most adverse joint combination
(`Error brake resistor CHP` -> `brake_hydraulic` **+** `WEC shut down` -> `manual`)
gives **5.10 %**. All of that sits inside a CI whose lower bound is 1.95 % and upper
bound 16.72 %, so the map is a second-order uncertainty next to sampling. The
farm-stratified CI [1.98, 16.39] and the leave-one-turbine-out range [5.61, 8.05] tell
the same story from the inference side.

**One flip does give `converter` nonzero same-component coverage:**
`Error brake resistor CHP` -> `converter` takes it from 0.0 % to **4.33 %** (28 events,
75.4 of 1,741.3 MWh), and it is the only flip that does - alone or in any combination.
Because that message is high-volume (235 warning rows) and its own frozen rationale
calls the converter reading "equally defensible", the structural claim in RESULTS §0.1
should be phrased as **"0 % under the frozen map and at most 4.3 % under any documented
alternative"**, not as an unqualified zero. The comparison that carries the argument -
converter at <= 4.3 % against anemometry at 84 % - survives the qualification intact.

---

## F. Data surprises

1. **The single most consequential map entry is a 7-row message.** `WEC shut down`
   appears on 4 T2 events, but 2 of them carry 215.0 MWh of the 706.6 MWh
   actionable-unacted total (30.4 %). Its control-vs-manual reading moves the headline
   more than the 251-stop BP-repeat pair and the 526-warning time-sync entry combined.
2. **The 210 MWh event is not warned by the message you would guess.** Its two
   same-component warnings are `Parameter outside limits`, not `Repeating error BP 0`,
   so the BP-repeat ambiguity - the other `control`-family flag - does not touch it.
3. **The zero-converter-coverage finding has exactly one documented way to become
   nonzero**, and the map's own rationale flagged that message for orchestrator review at
   the v1.1 freeze.
4. **Flips are not additive.** `time_sync` -> `control` is worth +0.031 pp on its own and
   exactly 0.000 pp on top of the maximising combination, because the earlier flips empty
   the `control` family of matchable stop energy.
5. **"Every warning inside the final 24 h" is the lead-time statistic in disguise.** The
   two phrasings are provably the same set; the study already had this number as
   `1 - frac_ge_24h` and did not recognise it.
6. **Farm stratification does essentially nothing** (CI 0.36 pp narrower at the top),
   despite a 4x per-farm difference in the headline and a 6/14 turbine split - the
   interval width is driven by within-turbine event concentration, not by farm balance.

## G. Artefacts written

| file | content |
|---|---|
| `analysis/map_sensitivity.csv` | 1,152 rows, one per map variant: flips applied, the full energy-weighted three-way split, warned/actionable counts and MWh, converter-family coverage, and the 210 MWh event's bucket and lead. `rationale_quotes` carries the verbatim authorising text on the 13 rows where it is read (frozen, the 11 single flips, the two extreme joints); it is identical per slot elsewhere and blanked to keep the file small |
| `analysis/late_warning_all.csv` | 14 rows: the unrestricted late-warning statistic and its complement for both rules, plus the >=3-row subset coverage for the v1.4(b) disclosure |
| `analysis/cluster_robustness.csv` | 23 rows: farm-stratified CI, the quoted unstratified CI, 20 leave-one-turbine-out refits and their summary |
| `analysis/claim_ledger.csv` | 14 rows: paper value vs recomputed value vs tolerance vs verdict for every manuscript number not already in a summary CSV |

No frozen artefact was modified. `component_map.csv`, `attribution.parquet`,
`decomposition.csv`, `bootstrap.csv`, `leadtime_stats.csv` and every stage-1/2/3 script
are byte-identical to their state before this run.
