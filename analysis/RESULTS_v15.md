# RESULTS v1.5 - post hoc map adjudication (2026-09-06)

STUDY_DESIGN.md changelog v1.5. NOT pre-registered: run after computation, at a referee's request, to review every frozen-map entry behind the 23 headline events (lead>=6h & duration>=6h quadrant) and the top-20 energy events. Frozen map unchanged. Script: `map_adjudication.py` -> `map_adjudication.csv` (109 event-message rows), `map_adjudication_summary.csv` (41 events). Validation gate reproduces every frozen number before adjudication.

Headline numbers used in the paper (Sec. V-E): four disagreements; two already in the v1.4 sweep; the two NEW ones (Parameter outside limits -> never-match; Overload generator heating -> auxiliary) jointly give 5.071% vs frozen 7.528% (see "ALL NEW disagreements jointly" below); 7 of 23 events (383.5 MWh, 58.6% of the set) touch a swept or disputed entry. Companion: RESULTS_warning_dedup.md (Table I warning-row basis).

## Script output (verbatim)

```
=== JOIN CHECK (frozen attribution columns must be reproduced) ===
  same_n / same_warn / same_lead / family reproduced on all 6,050 events: OK

=== VALIDATION GATE ===
  T2 events                          got   4,213.0000  want 4,213.0000  OK
  T2 MWh                             got   9,386.5016  want 9,386.5000  OK
  warned n                           got     979.0000  want   979.0000  OK
  warned MWh                         got   1,522.7825  want 1,522.8000  OK
  actionable % (headline)            got       7.5282  want     7.5300  OK
  unwarned %                         got      83.7769  want    83.7800  OK
  short-lead %                       got       8.6949  want     8.6900  OK
  headline-23 count (quadrant)       got      23.0000  want    23.0000  OK
  headline-23 MWh                    got     654.5988  want   654.6000  OK
  headline-23 share of warned E      got      42.9870  want    42.9900  OK
  ledger C5c count (lead>=6h & E>0)  got     166.0000  want   166.0000  OK

selected 41 events: 23 headline-23, 20 top-20 energy, 2 in both
wrote analysis/map_adjudication.csv: 109 rows
wrote analysis/map_adjudication_summary.csv: 41 rows

==============================================================================
=== DEPENDENCE ON AMBIGUOUS OR DISAGREED MAP ENTRIES ===

--- HEADLINE 23 (n=23, 654.6 MWh) ---
  events touching a ambiguous-slot entry           6 of 23  (   363.0 MWh =  55.4% of the set,  3.87% of T2 lost energy)
  events touching a independent DISAGREEMENT       6 of 23  (   341.1 MWh =  52.1% of the set,  3.63% of T2 lost energy)
  events touching a thin/missing rationale (any)  21 of 23  (   607.3 MWh =  92.8% of the set,  6.47% of T2 lost energy)
  events touching a thin rationale on a non-obvious call   2 of 23  (   230.7 MWh =  35.2% of the set,  2.46% of T2 lost energy)
  events touching a EITHER slot or disagreement    7 of 23  (   383.5 MWh =  58.6% of the set,  4.09% of T2 lost energy)

--- TOP 20 BY ENERGY (n=20, 3,560.1 MWh) ---
  events touching a ambiguous-slot entry           3 of 20  (   819.1 MWh =  23.0% of the set,  8.73% of T2 lost energy)
  events touching a independent DISAGREEMENT       1 of 20  (   210.1 MWh =   5.9% of the set,  2.24% of T2 lost energy)
  events touching a thin/missing rationale (any)  19 of 20  ( 3,456.7 MWh =  97.1% of the set, 36.83% of T2 lost energy)
  events touching a thin rationale on a non-obvious call   1 of 20  (   210.1 MWh =   5.9% of the set,  2.24% of T2 lost energy)
  events touching a EITHER slot or disagreement    3 of 20  (   819.1 MWh =  23.0% of the set,  8.73% of T2 lost energy)

==============================================================================
=== EVERY DISAGREEMENT FOUND ===

  [stop] 'WEC shut down'
    frozen family : control
    my family     : never_match  (confidence moderate)
    sweep coverage: COVERED by sweep slot 'wec_shut_down'   (rationale: documented)
    events touched: 2  (215.0 MWh; headline-23 2, top20 1)
      ids [2178, 3665]
    reason        : A bare supervisory shutdown record: it names no component and no actor. The frozen map puts it in `control`, which then lets it same-match other content-free controller messages. I would put a message carrying zero component information into a family that cannot satisfy a same-component test at all. DISAGREE. Effect direction is the same as the sweep's wec_shut_down: control -> manual (a never-match family).

  [warning] 'Error brake resistor CHP'
    frozen family : pitch
    my family     : converter  (confidence moderate)
    sweep coverage: COVERED by sweep slot 'brake_resistor_chp'   (rationale: documented)
    events touched: 3  (105.5 MWh; headline-23 3, top20 0)
      ids [2975, 5949, 6025]
    reason        : DISAGREE with the frozen `pitch`. 'CHP' = chopper. In standard drive terminology a chopper brake resistor is the DC-link braking chopper, i.e. a CONVERTER component; that is the plain reading of the words. The frozen call rests on the code-block argument (785 sits between the pitch battery block 700-735 and the pitch lubrication pump 850), which is suggestive but is an inference about numbering, not about the message. The frozen rationale itself says a converter reading is 'equally defensible' and FLAGS the entry. Covered by the brake_resistor_chp sweep slot.

  [warning] 'Overload generator heating'
    frozen family : generator
    my family     : auxiliary  (confidence low)
    sweep coverage: NEW - not one of the nine sweep slots   (rationale: missing)
    events touched: 1  (20.5 MWh; headline-23 1, top20 0)
      ids [4452]
    reason        : DISAGREE with the frozen `generator`, with low confidence and on construct grounds rather than coding grounds. Code 2674 is the generator anti-condensation HEATER circuit - an ancillary that runs mainly when the machine is stopped. The frozen map is internally consistent (it sends 'Overload gear heating' to drivetrain on the same served-component rule), and cabinet heaters go to `auxiliary`, so either convention can be defended. My objection is that a heater-circuit overload carries no information about the generator fault it is credited with anticipating here (carbon-brush service). NOT one of the nine sweep slots; its rationale field is EMPTY.

  [warning] 'Parameter outside limits'
    frozen family : control
    my family     : never_match  (confidence moderate)
    sweep coverage: NEW - not one of the nine sweep slots   (rationale: thin)
    events touched: 1  (210.1 MWh; headline-23 1, top20 1)
      ids [2178]
    reason        : DISAGREE on matchability, not on the family label: `control` is the right literal reading of a controller parameter-set integrity notice, but the message names no component, so allowing it to satisfy a same-component test against another content-free controller message is a match on the residual bucket, not on a component. NOT one of the nine sweep slots and its recorded rationale is four words ('Controller parameter-set integrity.'). This entry and the `WEC shut down` stop are the two halves of the single largest headline event.

==============================================================================
=== HEADLINE UNDER MY DISAGREEMENTS (map_sensitivity machinery) ===
  frozen map                                        7.528 %
  [sweep-covered] stop:WEC shut down -> manual       5.237 %   (delta -2.291 pp, warned n 977)
  [sweep-covered] warning:Error brake resistor CHP -> converter    7.951 %   (delta +0.422 pp, warned n 1003)
  [          NEW] warning:Overload generator heating -> auxiliary    7.310 %   (delta -0.219 pp, warned n 978)
  [          NEW] warning:Parameter outside limits -> manual       5.289 %   (delta -2.239 pp, warned n 978)

  ALL NEW disagreements jointly                     5.071 %  (delta -2.457 pp)
  ALL my disagreements jointly (new + sweep-covered) 5.441 %  (delta -2.087 pp)
  published 1,152-variant sweep range [5.097, 8.921] % - joint adjudication value 5.441 % is INSIDE
  frozen 95% CI [1.95, 16.72] % - joint value is INSIDE

==============================================================================
=== LOAD-BEARING ENTRIES WITH THIN OR MISSING RATIONALE ===
   role                            message   frozen_family rationale_class  rationale_words adjudication  n_events
warning                4-20mA anemometer 2      anemometry         missing                0        agree        11
warning                     4-20 mA vane 2      anemometry         missing                0        agree        11
   stop                  Anemometer defect      anemometry         missing                0        agree        10
warning  Battery charge cycle axis 3 error           pitch         missing                0        agree         7
warning  Battery charge cycle axis 2 error           pitch         missing                0        agree         7
warning  Battery charge cycle axis 1 error           pitch            thin                3        agree         7
   stop             Charging circuit pitch           pitch         missing                0        agree         6
   stop          Frequency converter error       converter         missing                0        agree         4
warning               Timeout brake closed brake_hydraulic         missing                0        agree         2
warning       Error lubrication pump pitch           pitch         missing                0        agree         2
warning     Pitch batteries charging cycle           pitch         missing                0        agree         2
   stop            Pitch current asymmetry           pitch         missing                0        agree         2
   stop                  Safety chain open          safety         missing                0        agree         2
   stop          Service generator brushes       generator         missing                0        agree         2
warning        Pitch measuring system 1><2           pitch         missing                0        agree         1
warning          Battery monitoring axis 2           pitch         missing                0        agree         1
warning                    Brake pads worn brake_hydraulic         missing                0        agree         1
warning         Overload generator heating       generator         missing                0     DISAGREE         1
warning           Parameter outside limits         control            thin                3     DISAGREE         1
warning           Brake accumulator defect brake_hydraulic            thin                6        agree         1
   stop                        Vane defect      anemometry         missing                0        agree         1
warning                4-20mA anemometer 1      anemometry            thin                8        agree         1
   stop                          UPS error      electrical         missing                0        agree         1
   stop              Pitch angle deviation           pitch         missing                0        agree         1
   stop            Particle Gear Alarm 24h      drivetrain            thin                5        agree         1
   stop           Overload fan pitch motor           pitch         missing                0        agree         1
   stop       Overload fan oil cooler gear      drivetrain            thin                6        agree         1
   stop           Low gearbox oil pressure      drivetrain         missing                0        agree         1
   stop Frequency converter load rejection       converter         missing                0        agree         1
   stop                   Feedback brake 1 brake_hydraulic         missing                0        agree         1
   stop            Error pitch converter 3           pitch         missing                0        agree         1
   stop                    Circuit breaker      electrical         missing                0        agree         1
warning                      Vane 2 defect      anemometry         missing                0        agree         1

messages with no independent judgment recorded: 0 (must be 0)
```
