#!/usr/bin/env python3
"""Per-event line-by-line adjudication of the frozen component map.

An external referee asked, as a minimum, for an independent review of the frozen
`component_map.csv` entries that actually carry the headline - not another sweep.
`map_sensitivity.py` already answers "what if the nine documented-ambiguous slots
had been called the other way" (1,152 variants). This script answers a different
question: for the specific events the headline rests on, WHICH map entries are load
bearing, is each one's recorded rationale adequate, and does an independent reading
of the raw message text agree with the frozen family?

TWO EVENT SETS
--------------
(A) the HEADLINE 23. `main.tex` L481-483 / `RESULTS_v13.md` E.3: of the 979
    same-component-warned T2 wide-grid events, those with lead >= 6 h AND outage
    duration >= 6 h. That is the `lead>=6h & dur>=6h` quadrant of
    `duration_grounding.py::lead_vs_duration` (`lead_vs_duration.csv`), n = 23,
    holding 43.0 % of same-component-warned lost energy.

    DEFINITION NOTE - two "23"-adjacent definitions exist in the artefacts and this
    script uses the quadrant one, because it is the one the manuscript's "23 events
    set the strict-rule headline" sentence points at:
      * quadrant   warned & lead >= 6 h & duration >= 6 h  -> n = 23   <- USED HERE
      * ledger C5c warned & lead >= 6 h & E_mwh > 0        -> n = 166  (claim_ledger)
    The second is the actionable-unacted set with measured energy; it is a superset
    and is not what "the headline turns on 23 events" refers to. "Energy-material"
    in the manuscript sentence is the duration >= 6 h leg of the quadrant, i.e. the
    events long enough for the 6 h horizon to be meaningful; the 23 carry 654.6 MWh
    against 706.6 MWh for all 698 actionable-unacted events, so the quadrant set is
    also where the energy is. Both counts are asserted in the validation gate.

(B) the TOP 20 T2 wide-grid events by `E_mwh`. Two events are in both sets.

WHAT IS ADJUDICATED
-------------------
Every constituent stop message of each selected event, and every distinct warning
message that same-component-matches it inside the frozen 72 h half-open lookback.
For each such message the script records the frozen family, whether the entry is one
of `map_sensitivity.SLOTS`' nine documented-ambiguous slots, how thin its recorded
rationale is, and an INDEPENDENT family judgment (`JUDGMENT` below) written from the
message text, its code and its service-contract category.

Honesty disclosure about the independent column: the judgments in `JUDGMENT` were
written by an LLM agent (Claude) reading the message strings, codes and service
categories. The frozen map had been read in the same session before they were
written, so this is an independent RE-READING, not a blind one; it cannot claim the
statistical independence of a second human coder. It is recorded as such rather than
overstated. Every judgment carries an explicit confidence and a one-line reason.

WHAT IS NOT TOUCHED
-------------------
Nothing frozen is recomputed or redefined. Events, tiers, energies, the 72 h window
and the warning rows are read from the stage-1/stage-2 parquets; the matching engine
is `map_sensitivity.MapEngine`, whose own JOIN CHECK proves it reproduces the frozen
attribution columns exactly before anything else runs.

Writes:
    analysis/map_adjudication.csv           one row per event-message pair
    analysis/map_adjudication_summary.csv   one row per event

    python3 map_adjudication.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

import map_sensitivity as MS

OUT_PAIRS = os.path.join(HERE, "map_adjudication.csv")
OUT_SUMMARY = os.path.join(HERE, "map_adjudication_summary.csv")

TIER_FLAG = MS.TIER_FLAG          # "T2_wide_grid"
LOOKBACK_H = MS.LOOKBACK_H        # 72
T_ACT_H = MS.T_ACT_H              # 6
DUR_H = 6.0                       # the quadrant's duration leg
TOP_N_ENERGY = 20

# a rationale this short, with no "Alternative" clause, is treated as thin
THIN_WORDS = 8


# ===========================================================================
# The independent judgments.
#
# key   (role, message)
# value (my_family, confidence, reason)
#
# `my_family` is the family I would defend from the message text + code +
# service-contract category alone. `never_match` is not a family in the frozen
# map; it is used where I judge that the message names no component at all and
# so should not be allowed to satisfy a "same component" test in either
# direction. Where I use it I say so in the reason and treat it as a
# disagreement.
# ===========================================================================
JUDGMENT = {
    # ---------------------------------------------------------------- stops
    ("stop", "Anemometer defect"):
        ("anemometry", "high", "Names the anemometer outright."),
    ("stop", "Vane defect"):
        ("anemometry", "high", "Wind vane; same met-sensing chain as the anemometer."),
    ("stop", "Battery voltage axis 3"):
        ("pitch", "high", "'axis n' is a pitch axis; code 735 in the pitch battery "
                          "block; service category 'Pitch errors (18)'."),
    ("stop", "Charging circuit pitch"):
        ("pitch", "high", "Names pitch."),
    ("stop", "Error pitch converter 3"):
        ("pitch", "high", "The per-axis pitch drive, not the main converter; "
                          "service category 'Pitch errors (18)' settles it."),
    ("stop", "Overload fan pitch motor"):
        ("pitch", "high", "Pitch motor cooling fan."),
    ("stop", "Pitch angle deviation"):
        ("pitch", "high", "Names pitch."),
    ("stop", "Pitch current asymmetry"):
        ("pitch", "high", "Names pitch."),
    ("stop", "Pitch controller communication error"):
        ("pitch", "moderate", "A communication fault INSIDE the pitch system. "
                              "'comms' is a real alternative and the frozen "
                              "rationale names it, but service category 'Pitch "
                              "errors (18)' makes pitch the better call. NOTE: this "
                              "entry documents an alternative family yet is not one "
                              "of the nine sweep slots."),
    ("stop", "Circuit breaker"):
        ("electrical", "high", "Switchgear; 38xx block is the LV/transformer side, "
                               "not the 31xx-32xx converter block."),
    ("stop", "UPS error"):
        ("electrical", "high", "Uninterruptible supply; 34xx electrical block."),
    ("stop", "Feedback brake 1"):
        ("brake_hydraulic", "high", "Mechanical brake position feedback."),
    ("stop", "Low hydraulic pressure"):
        ("brake_hydraulic", "moderate",
         "The message names the hydraulic supply, NOT the brake. On the MM82/92 the "
         "hydraulic power unit serves the mechanical brake, so folding hydraulics "
         "into brake_hydraulic is defensible and I concur - but it is a family-"
         "MERGE judgment, and a separate 'hydraulic' family would also be "
         "defensible. Not one of the nine sweep slots."),
    ("stop", "Frequency converter error"):
        ("converter", "high", "Names the converter."),
    ("stop", "Frequency converter load rejection"):
        ("converter", "high", "Names the converter."),
    ("stop", "Low gearbox oil pressure"):
        ("drivetrain", "high", "Gearbox lubrication."),
    ("stop", "Overload fan oil cooler gear"):
        ("drivetrain", "high", "Gearbox oil-cooler fan; the served component is the "
                               "gearbox."),
    ("stop", "Particle Gear Alarm 24h"):
        ("drivetrain", "high", "Gearbox oil-debris sensor."),
    ("stop", "Service generator brushes"):
        ("generator", "high", "Names the generator."),
    ("stop", "Safety chain open"):
        ("safety", "high", "Names the safety chain."),
    ("stop", "Manual stop - remote"):
        ("manual", "high", "Human action, stated."),
    ("stop", "Repeating error BP52"):
        ("control", "moderate", "Names no component; 'Repeated error (25)' is a "
                                "trip-count supervisor. The 'BP' pitch reading is "
                                "real but weaker. Concur with the frozen call; "
                                "covered by the bp_repeat sweep slot."),
    ("stop", "WEC shut down"):
        ("never_match", "moderate",
         "A bare supervisory shutdown record: it names no component and no actor. "
         "The frozen map puts it in `control`, which then lets it same-match other "
         "content-free controller messages. I would put a message carrying zero "
         "component information into a family that cannot satisfy a same-component "
         "test at all. DISAGREE. Effect direction is the same as the sweep's "
         "wec_shut_down: control -> manual (a never-match family)."),

    # ------------------------------------------------------------- warnings
    ("warning", "4-20mA anemometer 1"):
        ("anemometry", "high", "Anemometer signal-loop fault."),
    ("warning", "4-20mA anemometer 2"):
        ("anemometry", "high", "Anemometer signal-loop fault."),
    ("warning", "4-20 mA vane 2"):
        ("anemometry", "high", "Vane signal-loop fault."),
    ("warning", "Vane 2 defect"):
        ("anemometry", "high", "Names the vane."),
    ("warning", "Battery charge cycle axis 1 error"):
        ("pitch", "high", "Pitch back-up battery charge cycle; 'axis n' is a pitch "
                          "axis."),
    ("warning", "Battery charge cycle axis 2 error"):
        ("pitch", "high", "As above."),
    ("warning", "Battery charge cycle axis 3 error"):
        ("pitch", "high", "As above."),
    ("warning", "Battery monitoring axis 2"):
        ("pitch", "high", "Pitch back-up battery monitoring."),
    ("warning", "Pitch batteries charging cycle"):
        ("pitch", "high", "Names pitch."),
    ("warning", "Pitch measuring system 1><2"):
        ("pitch", "high", "Pitch position measurement disagreement."),
    ("warning", "Error lubrication pump pitch"):
        ("pitch", "high", "Names pitch."),
    ("warning", "Error brake resistor CHP"):
        ("converter", "moderate",
         "DISAGREE with the frozen `pitch`. 'CHP' = chopper. In standard drive "
         "terminology a chopper brake resistor is the DC-link braking chopper, i.e. "
         "a CONVERTER component; that is the plain reading of the words. The frozen "
         "call rests on the code-block argument (785 sits between the pitch battery "
         "block 700-735 and the pitch lubrication pump 850), which is suggestive but "
         "is an inference about numbering, not about the message. The frozen "
         "rationale itself says a converter reading is 'equally defensible' and "
         "FLAGS the entry. Covered by the brake_resistor_chp sweep slot."),
    ("warning", "Brake accumulator defect"):
        ("brake_hydraulic", "high", "Hydraulic accumulator of the mechanical brake."),
    ("warning", "Brake pads worn"):
        ("brake_hydraulic", "high", "Names the brake."),
    ("warning", "Timeout brake closed"):
        ("brake_hydraulic", "high", "Brake failed to report closed in time."),
    ("warning", "Particle Gear Alarm 10min"):
        ("drivetrain", "high", "Gearbox oil-debris sensor."),
    ("warning", "Overload generator heating"):
        ("auxiliary", "low",
         "DISAGREE with the frozen `generator`, with low confidence and on construct "
         "grounds rather than coding grounds. Code 2674 is the generator "
         "anti-condensation HEATER circuit - an ancillary that runs mainly when the "
         "machine is stopped. The frozen map is internally consistent (it sends "
         "'Overload gear heating' to drivetrain on the same served-component rule), "
         "and cabinet heaters go to `auxiliary`, so either convention can be "
         "defended. My objection is that a heater-circuit overload carries no "
         "information about the generator fault it is credited with anticipating "
         "here (carbon-brush service). NOT one of the nine sweep slots; its "
         "rationale field is EMPTY."),
    ("warning", "Parameter outside limits"):
        ("never_match", "moderate",
         "DISAGREE on matchability, not on the family label: `control` is the right "
         "literal reading of a controller parameter-set integrity notice, but the "
         "message names no component, so allowing it to satisfy a same-component "
         "test against another content-free controller message is a match on the "
         "residual bucket, not on a component. NOT one of the nine sweep slots and "
         "its recorded rationale is four words ('Controller parameter-set "
         "integrity.'). This entry and the `WEC shut down` stop are the two halves "
         "of the single largest headline event."),
    ("warning", "Repeating error BP 0"):
        ("control", "moderate", "Pairs with the 'Repeating error BP52' stop; same "
                                "reasoning. Concur; covered by the bp_repeat sweep "
                                "slot."),
}


# --------------------------------------------------------------------- helpers
def slot_index():
    """(role, message) -> (slot name, frozen family, alternatives)."""
    idx = {}
    for s in MS.SLOTS:
        for role, msg in s["messages"]:
            idx[(role, msg)] = (s["slot"], s["frozen_family"],
                                "|".join(o for o in s["options"] if o))
    return idx


def rationale_class(text):
    """missing / thin / documented, plus the word count."""
    t = "" if (text is None or (isinstance(text, float) and np.isnan(text))) else str(text)
    t = t.strip()
    n = len(t.split())
    if n == 0:
        return "missing", 0
    if "alternative" in t.lower():
        return "documented", n
    if n <= THIN_WORDS:
        return "thin", n
    return "documented", n


def main():
    # ------------------------------------------------------------ load + engine
    cm, stop_fam, warn_fam = MS.load_map()
    ev, wn, att = MS.load_frames()
    cand = MS.build_candidates(ev, wn)
    eng = MS.MapEngine(ev, wn, stop_fam, warn_fam, cand)

    # map metadata for the message-level columns
    meta = {}
    for _, r in cm.iterrows():
        roles = ("stop", "warning") if r.role == "both" else (r.role,)
        for role in roles:
            meta[(role, r.message)] = dict(
                code=r.code, n_rows_corpus=r.n_rows,
                service_category=r.service_contract_category,
                frozen_family=r.family, rationale=r.rationale)

    # ------------------------------------------------------- JOIN CHECK (frozen)
    print("=== JOIN CHECK (frozen attribution columns must be reproduced) ===")
    any_n = np.bincount(eng.ev_pos, minlength=len(ev)).astype(np.int64)
    assert (any_n == att["any_n_72h"].values).all(), "any_n_72h not reproduced"
    warn0, n0, lead0, pfam0 = eng.match([])
    assert (n0 == att["same_n_72h"].values).all(), "same_n_72h not reproduced"
    assert (warn0 == att["same_warn_72h"].values).all(), "same_warn_72h not reproduced"
    lref = att["same_lead_h_72h"].values.astype(float)
    fin = np.isfinite(lead0)
    assert (fin == np.isfinite(lref)).all()
    assert np.allclose(lead0[fin], lref[fin], atol=1e-9), "same_lead_h_72h differs"
    assert (np.asarray([eng.fams[c] for c in pfam0]) == ev["family"].values).all()
    print(f"  same_n / same_warn / same_lead / family reproduced on all "
          f"{len(ev):,} events: OK")

    # -------------------------------------------------------- VALIDATION GATE
    tier = att[TIER_FLAG].values.astype(bool)
    E = att["E_mwh"].values.astype(float)
    dur = att["duration_h"].values.astype(float)
    lead = lref
    warned = warn0

    Et = E[tier]
    act_t = (warned & (lead >= T_ACT_H))[tier]
    head_mask = tier & warned & (lead >= T_ACT_H) & (dur >= DUR_H)
    ledger_mask = tier & warned & (lead >= T_ACT_H) & (E > 0)

    print("\n=== VALIDATION GATE ===")
    gate = [
        ("T2 events", float(tier.sum()), 4213, 0),
        ("T2 MWh", float(Et.sum()), 9386.5, 0.05),
        ("warned n", float((warned & tier).sum()), 979, 0),
        ("warned MWh", float(E[tier & warned].sum()), 1522.8, 0.05),
        ("actionable % (headline)", 100 * float(Et[act_t].sum()) / Et.sum(),
         7.53, 0.005),
        ("unwarned %", 100 * float(Et[~(warned[tier])].sum()) / Et.sum(),
         83.78, 0.005),
        ("short-lead %",
         100 * float(Et[(warned & ~(warned & (lead >= T_ACT_H)))[tier]].sum())
         / Et.sum(), 8.69, 0.005),
        ("headline-23 count (quadrant)", float(head_mask.sum()), 23, 0),
        ("headline-23 MWh", float(E[head_mask].sum()), 654.6, 0.05),
        ("headline-23 share of warned E",
         100 * float(E[head_mask].sum()) / float(E[tier & warned].sum()),
         42.99, 0.01),
        ("ledger C5c count (lead>=6h & E>0)", float(ledger_mask.sum()), 166, 0),
    ]
    ok_all = True
    for name, got, want, tol in gate:
        ok = abs(got - want) <= tol
        ok_all &= ok
        print(f"  {name:<34} got {got:>12,.4f}  want {want:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
    assert ok_all, ("VALIDATION GATE FAILED - the frozen headline / 23-event count "
                    "was not reproduced from the parquets; adjudication aborted")

    # ------------------------------------------------------------ event sets
    head_pos = np.flatnonzero(head_mask)
    tier_pos = np.flatnonzero(tier)
    top_pos = tier_pos[np.argsort(E[tier_pos], kind="stable")[::-1][:TOP_N_ENERGY]]
    sel = sorted(set(head_pos.tolist()) | set(top_pos.tolist()))
    head_set, top_set = set(head_pos.tolist()), set(top_pos.tolist())
    print(f"\nselected {len(sel)} events: {len(head_set)} headline-23, "
          f"{len(top_set)} top-{TOP_N_ENERGY} energy, "
          f"{len(head_set & top_set)} in both")

    # matched (event, warning-row) pairs under the frozen map
    sc0, wc0 = eng.codes([])
    bits = np.int64(1) << sc0[eng.pair_msg]
    evmask = np.bitwise_or.reduceat(bits, eng.pair_starts)
    wcode = wc0[eng.cand_warn_msg_id]
    ok_pair = (((evmask[eng.ev_pos] >> wcode) & 1) == 1) & (~eng.never[wcode])

    slots = slot_index()
    ev_msgs = ev["messages"].values
    ev_codes = ev["codes"].values
    rows = []

    def add(pos, role, msg, **extra):
        m = meta.get((role, msg), dict(code=None, n_rows_corpus=None,
                                       service_category=None,
                                       frozen_family=None, rationale=""))
        rc, rw = rationale_class(m["rationale"])
        sl = slots.get((role, msg))
        mine = JUDGMENT.get((role, msg))
        if mine is None:
            my_fam, conf, reason = "", "", "NO INDEPENDENT JUDGMENT RECORDED"
        else:
            my_fam, conf, reason = mine
        frozen = m["frozen_family"]
        agree = "" if not my_fam else ("agree" if my_fam == frozen else "DISAGREE")
        rows.append(dict(
            event_id=int(att["event_id"].values[pos]),
            in_headline_23=pos in head_set,
            in_top20_energy=pos in top_set,
            farm=att["farm"].values[pos],
            turbine_id=int(att["turbine_id"].values[pos]),
            event_start=pd.Timestamp(att["start"].values[pos]),
            duration_h=float(dur[pos]),
            E_mwh=float(E[pos]),
            event_family=att["family"].values[pos],
            families_all="|".join(sorted(att["families_all"].values[pos])),
            event_lead_h=float(lead[pos]) if np.isfinite(lead[pos]) else np.nan,
            role=role, message=msg,
            code=m["code"], service_category=m["service_category"],
            corpus_n_rows=m["n_rows_corpus"],
            frozen_family=frozen,
            ambiguous_slot=(sl[0] if sl else ""),
            slot_alternatives=(sl[2] if sl else ""),
            rationale_class=rc, rationale_words=rw,
            frozen_rationale=(m["rationale"] if isinstance(m["rationale"], str)
                              else ""),
            my_family=my_fam, my_confidence=conf, adjudication=agree,
            my_reason=reason,
            **extra))

    for pos in sel:
        # ---- stop side: every constituent stop message of the merged event ----
        msgs = list(ev_msgs[pos])
        codes = list(ev_codes[pos])
        primary = att["primary_message"].values[pos]
        for m, c in zip(msgs, codes):
            add(pos, "stop", m, is_primary_stop_message=(m == primary),
                warning_n_rows_in_window=np.nan, warning_lead_h=np.nan,
                is_earliest_qualifying_warning=False, event_stop_code=int(c))

        # ---- warning side: distinct matching messages, earliest occurrence ----
        j = np.flatnonzero(ok_pair & (eng.ev_pos == pos))
        if len(j):
            wmsgs = np.asarray(eng.warn_msgs)[eng.cand_warn_msg_id[j]]
            hb = eng.hb[j]
            agg = (pd.DataFrame(dict(message=wmsgs, hb=hb))
                   .groupby("message")["hb"].agg(["size", "max"])
                   .sort_values("max", ascending=False))
            best = float(agg["max"].max())
            for m, r in agg.iterrows():
                add(pos, "warning", m,
                    is_primary_stop_message=False,
                    warning_n_rows_in_window=int(r["size"]),
                    warning_lead_h=float(r["max"]),
                    is_earliest_qualifying_warning=bool(
                        abs(float(r["max"]) - best) < 1e-9),
                    event_stop_code=np.nan)

    pairs = pd.DataFrame(rows)
    pairs.to_csv(OUT_PAIRS, index=False)
    print(f"wrote {OUT_PAIRS}: {len(pairs):,} rows")

    # the per-event lead must equal the best qualifying warning's lead
    chk = pairs[pairs.is_earliest_qualifying_warning]
    for _, r in chk.iterrows():
        assert abs(r.warning_lead_h - r.event_lead_h) < 1e-6, \
            f"lead mismatch on event {r.event_id}"

    # --------------------------------------------------------------- summary
    g = pairs.groupby("event_id")
    summary = pd.DataFrame(dict(
        in_headline_23=g["in_headline_23"].first(),
        in_top20_energy=g["in_top20_energy"].first(),
        farm=g["farm"].first(), turbine_id=g["turbine_id"].first(),
        event_start=g["event_start"].first(),
        duration_h=g["duration_h"].first(),
        energy_MWh=g["E_mwh"].first(),
        lead_h=g["event_lead_h"].first(),
        primary_family=g["event_family"].first(),
        n_messages=g.size(),
        n_stop_messages=g["role"].apply(lambda s: int((s == "stop").sum())),
        n_warning_messages=g["role"].apply(lambda s: int((s == "warning").sum())),
        n_ambiguous_slot=g["ambiguous_slot"].apply(lambda s: int((s != "").sum())),
        n_thin_rationale=g["rationale_class"].apply(
            lambda s: int(s.isin(("thin", "missing")).sum())),
        n_disagreements=g["adjudication"].apply(lambda s: int((s == "DISAGREE").sum())),
    )).reset_index().sort_values("energy_MWh", ascending=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    print(f"wrote {OUT_SUMMARY}: {len(summary):,} rows")

    # ================================================================ report
    def block(title, mask_col, e_all):
        sub = summary[summary[mask_col]]
        ids = set(sub.event_id)
        p = pairs[pairs.event_id.isin(ids)]
        # an event is "affected" if any message on it is in a slot / disagreed
        aff_slot = set(p.loc[p.ambiguous_slot != "", "event_id"])
        aff_dis = set(p.loc[p.adjudication == "DISAGREE", "event_id"])
        aff_thin = set(p.loc[p.rationale_class.isin(("thin", "missing")), "event_id"])
        # a bare rationale on an entry I read as obvious ("Anemometer defect") is not
        # a finding; the reportable subset is thin AND not-obvious on re-reading.
        aff_thin_hard = set(p.loc[p.rationale_class.isin(("thin", "missing"))
                                  & (p.my_confidence != "high"), "event_id"])
        aff_any = aff_slot | aff_dis
        eE = sub.set_index("event_id")["energy_MWh"]
        tot = float(eE.sum())
        print(f"\n--- {title} (n={len(sub)}, {tot:,.1f} MWh) ---")
        for label, s in (("ambiguous-slot entry", aff_slot),
                         ("independent DISAGREEMENT", aff_dis),
                         ("thin/missing rationale (any)", aff_thin),
                         ("thin rationale on a non-obvious call", aff_thin_hard),
                         ("EITHER slot or disagreement", aff_any)):
            e = float(eE.loc[sorted(s)].sum()) if s else 0.0
            print(f"  events touching a {label:<28} {len(s):>3} of {len(sub):<3} "
                  f"({e:>8,.1f} MWh = {100*e/tot:5.1f}% of the set, "
                  f"{100*e/e_all:5.2f}% of T2 lost energy)")
        return sub, p

    E_T2 = float(Et.sum())
    print("\n" + "=" * 78)
    print("=== DEPENDENCE ON AMBIGUOUS OR DISAGREED MAP ENTRIES ===")
    block("HEADLINE 23", "in_headline_23", E_T2)
    block(f"TOP {TOP_N_ENERGY} BY ENERGY", "in_top20_energy", E_T2)

    # ------------------------------------------------------- disagreement list
    print("\n" + "=" * 78)
    print("=== EVERY DISAGREEMENT FOUND ===")
    dis = pairs[pairs.adjudication == "DISAGREE"]
    entries = (dis.groupby(["role", "message"])
               .agg(frozen_family=("frozen_family", "first"),
                    my_family=("my_family", "first"),
                    my_confidence=("my_confidence", "first"),
                    ambiguous_slot=("ambiguous_slot", "first"),
                    rationale_class=("rationale_class", "first"),
                    n_events=("event_id", "nunique"),
                    reason=("my_reason", "first")).reset_index())
    for _, r in entries.iterrows():
        ids = sorted(set(dis.loc[(dis.role == r.role) & (dis.message == r.message),
                                 "event_id"]))
        sube = summary[summary.event_id.isin(ids)]
        cov = ("COVERED by sweep slot '%s'" % r.ambiguous_slot if r.ambiguous_slot
               else "NEW - not one of the nine sweep slots")
        print(f"\n  [{r.role}] {r.message!r}")
        print(f"    frozen family : {r.frozen_family}")
        print(f"    my family     : {r.my_family}  (confidence {r.my_confidence})")
        print(f"    sweep coverage: {cov}   (rationale: {r.rationale_class})")
        print(f"    events touched: {len(ids)}  "
              f"({float(sube.energy_MWh.sum()):,.1f} MWh; headline-23 "
              f"{int(sube.in_headline_23.sum())}, top20 "
              f"{int(sube.in_top20_energy.sum())})")
        print(f"      ids {ids}")
        print(f"    reason        : {r.reason}")

    # -------------------------------------------- recompute for NEW disagreements
    print("\n" + "=" * 78)
    print("=== HEADLINE UNDER MY DISAGREEMENTS (map_sensitivity machinery) ===")
    big_pos = int(np.flatnonzero(att["event_id"].values == MS.BIG_EVENT_ID)[0])
    base = MS.variant_metrics(eng, [], tier, E, big_pos, eng.fams)
    print(f"  frozen map                                        "
          f"{base['actionable_unacted_pct_E']:.3f} %")

    # `never_match` is not a family in the frozen map; realise it as `manual`,
    # which is in NEVER_MATCH, so the message can never satisfy the rule. This is
    # exactly how the sweep realises wec_shut_down -> manual.
    NEVER_AS = "manual"
    flips_all = []
    for _, r in entries.iterrows():
        fam = NEVER_AS if r.my_family == "never_match" else r.my_family
        flips_all.append((r.role, r.message, fam))

    for _, r in entries.iterrows():
        fam = NEVER_AS if r.my_family == "never_match" else r.my_family
        m = MS.variant_metrics(eng, [(r.role, r.message, fam)], tier, E, big_pos,
                               eng.fams)
        tag = "sweep-covered" if r.ambiguous_slot else "NEW"
        print(f"  [{tag:>13}] {r.role}:{r.message} -> {fam:<12} "
              f"{m['actionable_unacted_pct_E']:.3f} %   "
              f"(delta {m['actionable_unacted_pct_E'] - base['actionable_unacted_pct_E']:+.3f} pp, "
              f"warned n {m['warned_n_events']})")

    new_flips = [(r.role, r.message,
                  NEVER_AS if r.my_family == "never_match" else r.my_family)
                 for _, r in entries.iterrows() if not r.ambiguous_slot]
    if new_flips:
        m = MS.variant_metrics(eng, new_flips, tier, E, big_pos, eng.fams)
        print(f"\n  ALL NEW disagreements jointly                     "
              f"{m['actionable_unacted_pct_E']:.3f} %  "
              f"(delta {m['actionable_unacted_pct_E'] - base['actionable_unacted_pct_E']:+.3f} pp)")
    m = MS.variant_metrics(eng, flips_all, tier, E, big_pos, eng.fams)
    print(f"  ALL my disagreements jointly (new + sweep-covered) "
          f"{m['actionable_unacted_pct_E']:.3f} %  "
          f"(delta {m['actionable_unacted_pct_E'] - base['actionable_unacted_pct_E']:+.3f} pp)")

    # is the joint result still inside the published sweep range / the frozen CI?
    try:
        sw = pd.read_csv(os.path.join(HERE, "map_sensitivity.csv"))
        lo_s, hi_s = (float(sw.actionable_unacted_pct_E.min()),
                      float(sw.actionable_unacted_pct_E.max()))
        v = m["actionable_unacted_pct_E"]
        print(f"  published 1,152-variant sweep range [{lo_s:.3f}, {hi_s:.3f}] % - "
              f"joint adjudication value {v:.3f} % is "
              f"{'INSIDE' if lo_s <= v <= hi_s else 'OUTSIDE'}")
        print(f"  frozen 95% CI [1.95, 16.72] % - joint value is "
              f"{'INSIDE' if 1.95 <= v <= 16.72 else 'OUTSIDE'}")
    except FileNotFoundError:
        print("  (map_sensitivity.csv absent; sweep-range comparison skipped)")

    # ----------------------------------------------------------- thin entries
    print("\n" + "=" * 78)
    print("=== LOAD-BEARING ENTRIES WITH THIN OR MISSING RATIONALE ===")
    thin = (pairs[pairs.rationale_class.isin(("thin", "missing"))]
            .groupby(["role", "message"])
            .agg(frozen_family=("frozen_family", "first"),
                 rationale_class=("rationale_class", "first"),
                 rationale_words=("rationale_words", "first"),
                 adjudication=("adjudication", "first"),
                 n_events=("event_id", "nunique")).reset_index()
            .sort_values("n_events", ascending=False))
    print(thin.to_string(index=False))
    n_no_judgment = int((pairs.my_family == "").sum())
    print(f"\nmessages with no independent judgment recorded: {n_no_judgment} "
          f"(must be 0)")
    assert n_no_judgment == 0, "a selected message has no JUDGMENT entry"

    # ------------------------------------------- v1.7(b) headline scenario rows
    # The five headline values printed above are appended to the summary CSV as
    # explicit rows (imported late to keep the module import one-directional).
    print("\n" + "=" * 78)
    print("=== HEADLINE SCENARIOS WRITTEN TO THE SUMMARY CSV (v1.7b) ===")
    import map_adjudication_allfour as AF
    scen = AF.scenario_rows(eng, tier, E, big_pos, eng.fams, cm)
    print(scen[["scenario", "scenario_kind", "actionable_unacted_pct_E",
                "delta_pp_vs_frozen"]].to_string(index=False))
    AF.append_scenarios(scen)

    return pairs, summary


if __name__ == "__main__":
    main()
