#!/usr/bin/env python3
"""STUDY_DESIGN v1.4(a) - component-map sensitivity.

The frozen `component_map.csv` REMAINS THE PRIMARY MAP. This script asks what the
headline would have been under each map entry whose own recorded rationale documents
a plausible alternative family, one flip at a time and jointly.

WHAT IS AND IS NOT PERTURBED
----------------------------
Only FAMILY MATCHING moves. Concretely:

  * an event's `families_all` is re-derived from its constituent stop messages under
    the modified map (and its `family` label from `primary_message`);
  * a warning row's `family` is re-derived from its message under the modified map;
  * the same-component rule is then re-run: a warning matches if its family is in the
    event's family set and is not one of {external, grid, manual}.

TIER MEMBERSHIP IS NEVER TOUCHED. `T2_wide_grid` is a MESSAGE-LEVEL service-category
filter computed in stage 1 (build_events.py: `n_grid_ext_msgs`, `n_manual_msgs` from
`common.GRID_MESSAGES` / `GRID_MESSAGES_EXTRA` / `MANUAL_MESSAGES`), not a function of
the component map. So flipping `WEC shut down` from the `control` family to the
`manual` family makes that event's family set {manual}, which can never same-match -
it moves the event from the warned bucket to UNWARNED - but the event STAYS IN T2 and
stays in the denominator. Likewise `High yaw load` -> `external` cannot drop the event
from T1/T2. The denominator (4,213 events / 9,386.5 MWh) is identical in every variant
by construction, and the script asserts that.

The any-warning rule is invariant to the map (it ignores families entirely), so it is
not varied here.

WINDOW CONVENTIONS - identical to attribute.py, re-derived not re-used
---------------------------------------------------------------------
`attribution.parquet`'s `same_*` columns were computed under the frozen map, so they
cannot be reused for a flipped map. The warning sets are rebuilt from
`warnings.parquet`: half-open window [start - 72 h, start), warnings placed by their
START timestamp, earliest matching warning gives the lead. Before any variant is
computed the rebuild must reproduce the frozen `same_warn_72h`, `same_n_72h`,
`same_lead_h_72h` and `any_n_72h` columns EXACTLY on all 6,050 events (the JOIN CHECK
approach of warning_dynamics.py).

Writes:
    analysis/map_sensitivity.csv

    python3 map_sensitivity.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

DERIVED = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
MAP_CSV = os.path.join(HERE, "component_map.csv")
OUT_CSV = os.path.join(HERE, "map_sensitivity.csv")

LOOKBACK_H = 72
T_ACT_H = 6
TIER_FLAG = "T2_wide_grid"
NEVER_MATCH = frozenset({"external", "grid", "manual"})

# the 210.1 MWh Penmanshiel WT04 2023-06-23 event (RESULTS §7)
BIG_EVENT_ID = 2178

# ------------------------------------------------------------------ the flips
# Every option below is quoted from the `rationale` column of the FROZEN
# component_map.csv. `None` = keep the frozen family (the primary map).
# A "slot" is one map entry (or one deliberately-paired set of entries); the
# options within a slot are mutually exclusive.
SLOTS = [
    dict(
        slot="bp_repeat",
        frozen_family="control",
        messages=[("stop", "Repeating error BP52"), ("warning", "Repeating error BP 0")],
        rationale=("stop `Repeating error BP52`: \"AMBIGUOUS and high-volume (251 stops). "
                   "Service category 'Repeated error (25)' names a trip-count supervisor, "
                   "not a component; 'BP' also prefixes pitch messages ('Pitch too slow "
                   "BP180'), so a pitch reading is possible. ... Alternative: pitch.\"  "
                   "warning `Repeating error BP 0`: \"AMBIGUOUS. Pairs with the stop message "
                   "'Repeating error BP52'; both are assigned to `control` so that they can "
                   "match each other ... Alternative: pitch.\"  The pair is flipped together "
                   "because the frozen rationale assigns them together."),
        options=[None, "pitch"],
    ),
    dict(
        slot="brake_resistor_chp",
        frozen_family="pitch",
        messages=[("warning", "Error brake resistor CHP")],
        rationale=("\"AMBIGUOUS and high-volume (235 warnings). 'CHP' = chopper brake "
                   "resistor. Code 785 sits between the pitch battery block (700-735) and "
                   "the pitch lubrication pump (850), and the MM82/92 pitch drives have "
                   "their own braking chopper, so assigned to `pitch`. A converter DC-link "
                   "chopper reading is equally defensible. Alternatives: converter, "
                   "brake_hydraulic. FLAGGED for orchestrator review.\""),
        options=[None, "converter", "brake_hydraulic"],
    ),
    dict(
        slot="time_sync",
        frozen_family="external",
        messages=[("warning", "Check time synchronization"),
                  ("warning", "Time sync. failed (SNTP error)")],
        rationale=("`Check time synchronization`: \"AMBIGUOUS but high-volume (526 "
                   "warnings). Pure housekeeping telemetry (NTP drift) with no fault "
                   "semantics, so `external` per the STUDY_DESIGN rule. Putting it in "
                   "`control` would let 526 clock-drift notices match controller stops. "
                   "Alternative: control.\"  `Time sync. failed (SNTP error)`: \"As above.\" "
                   "- so the two are flipped together."),
        options=[None, "control"],
    ),
    dict(
        slot="cms_drivetrain",
        frozen_family="comms",
        messages=[("warning", "Comm.err. IEC server <- CMS drive tr."),
                  ("warning", "Comm.err. IEC client -> CMS drive tr."),
                  ("warning", "CMS drive train system error")],
        rationale=("\"AMBIGUOUS: the condition-monitoring (CMS) link for the drivetrain. "
                   "Assigned to `comms` because the message reports the monitoring channel "
                   "failing, not a drivetrain fault - the conservative reading. Alternative: "
                   "drivetrain.\"  The other two rows read \"As above. Alternative: "
                   "drivetrain.\" / \"As above - the CMS itself errors. Alternative: "
                   "drivetrain.\""),
        options=[None, "drivetrain"],
    ),
    dict(
        slot="current_asymmetry",
        frozen_family="converter",
        messages=[("stop", "Current asymmetry")],
        rationale=("\"AMBIGUOUS: service category 'Generator and Converter errors (20)' "
                   "does not separate the two. Code 3555 sits in the 3xxx "
                   "converter/switchgear block (generator faults are 2xxx), so assigned to "
                   "converter. Alternative: generator.\""),
        options=[None, "generator"],
    ),
    dict(
        slot="wec_shut_down",
        frozen_family="control",
        messages=[("stop", "WEC shut down")],
        rationale=("\"AMBIGUOUS: generic supervisory shutdown, service category 'WEC "
                   "Shutdown (1)', no component named. Assigned to `control` rather than "
                   "`manual` because nothing in the message implies a human action. "
                   "Alternative: manual.\"  NOTE: `manual` is a never-match family, so this "
                   "flip forces every `WEC shut down` event to UNWARNED. It does NOT change "
                   "tier membership (see module docstring)."),
        options=[None, "manual"],
    ),
    dict(
        slot="no_speed_development",
        frozen_family="control",
        messages=[("stop", "No speed development")],
        rationale=("\"AMBIGUOUS: rotor fails to spin up on start; the physical cause could "
                   "be pitch, brake or drivetrain. Assigned to `control` (start-up "
                   "supervisor) precisely because it does not identify a component; n=4. "
                   "Alternatives: pitch, brake_hydraulic.\""),
        options=[None, "pitch", "brake_hydraulic"],
    ),
    dict(
        slot="high_yaw_load",
        frozen_family="yaw",
        messages=[("stop", "High yaw load")],
        rationale=("\"AMBIGUOUS: service category is 'External stop (climate) (6)', which "
                   "would argue for `external`, but the message and code block (60xx) are "
                   "yaw. Assigned to yaw; n=1 so the choice is immaterial. Alternative: "
                   "external.\""),
        options=[None, "external"],
    ),
    dict(
        slot="cable_overload",
        frozen_family="converter",
        messages=[("warning", "Cable overload")],
        rationale=("\"Code 3160 sits in the converter block (3151-3265); read as the "
                   "converter output cabling. Alternative: electrical.\""),
        options=[None, "electrical"],
    ),
]


# --------------------------------------------------------------------- loading
def load_map():
    cm = pd.read_csv(MAP_CSV)
    stop_fam = (cm[cm.role.isin(("stop", "both"))]
                .set_index("message")["family"].to_dict())
    warn_fam = (cm[cm.role.isin(("warning", "both"))]
                .set_index("message")["family"].to_dict())
    return cm, stop_fam, warn_fam


def load_frames():
    ev = pd.read_parquet(os.path.join(DERIVED, "events.parquet"))
    wn = pd.read_parquet(os.path.join(DERIVED, "warnings.parquet"))
    att = pd.read_parquet(os.path.join(DERIVED, "attribution.parquet"))
    assert (ev["event_id"].values == att["event_id"].values).all()
    return ev, wn, att


# ------------------------------------------------- the map-independent windows
def build_candidates(ev, wn, lookback_h=LOOKBACK_H):
    """Every warning row inside [event.start - L, event.start), per event.

    Returns (ev_pos, warn_pos, hours_before), flat arrays sorted by event and, within
    an event, by DESCENDING hours_before (i.e. ascending warning start), so the first
    matching entry for an event is the earliest matching warning = the lead.

    This is `attribute.py`'s window verbatim - half-open, warnings placed by their
    START timestamp - and it does not depend on the component map, so it is built
    once and reused by every variant.
    """
    wn = wn.reset_index(drop=True)                  # index == positional warning id
    order = np.argsort(wn["start"].values.astype("datetime64[ns]").astype("int64"),
                       kind="stable")
    wsorted = wn.iloc[order]                        # groupby below keeps this order,
    by = {}                                         # so each group's starts are sorted
    for k, g in wsorted.groupby(["farm", "turbine_id"], sort=False):
        by[k] = (g["start"].values.astype("datetime64[ns]").astype("int64"),
                 g.index.values)                    # original positional warning ids

    ev_pos_l, warn_pos_l, hb_l = [], [], []
    L_ns = int(lookback_h * 3600 * 1e9)
    starts = ev["start"].values.astype("datetime64[ns]").astype("int64")
    farms = ev["farm"].values
    tids = ev["turbine_id"].values
    for i in range(len(ev)):
        a = by.get((farms[i], tids[i]))
        if a is None:
            continue
        ns, wids = a
        a_ns = starts[i]
        s = np.searchsorted(ns, a_ns - L_ns, "left")
        e = np.searchsorted(ns, a_ns, "left")
        if s == e:
            continue
        ev_pos_l.append(np.full(e - s, i, dtype=np.int64))
        warn_pos_l.append(wids[s:e])
        hb_l.append((a_ns - ns[s:e]) / 3.6e12)
    ev_pos = np.concatenate(ev_pos_l)
    warn_pos = np.concatenate(warn_pos_l).astype(np.int64)
    hb = np.concatenate(hb_l)
    o = np.argsort(ev_pos, kind="stable")           # hb already descending in-event
    return ev_pos[o], warn_pos[o], hb[o]


# ------------------------------------------------------------- family plumbing
class MapEngine:
    """Vectorised same-component matching under an arbitrary family assignment."""

    def __init__(self, ev, wn, stop_fam, warn_fam, cand):
        self.n_ev = len(ev)
        self.ev_pos, self.warn_pos, self.hb = cand

        fams = sorted(set(stop_fam.values()) | set(warn_fam.values()))
        assert len(fams) <= 62, "family bitmask would overflow int64"
        self.fam_code = {f: i for i, f in enumerate(fams)}
        self.fams = fams
        self.never = np.array([f in NEVER_MATCH for f in fams], dtype=bool)

        # --- stop side: flat (event, constituent-message) pairs -----------------
        msgs = ev["messages"].values
        self.stop_msgs = sorted({m for ms in msgs for m in ms})
        smid = {m: i for i, m in enumerate(self.stop_msgs)}
        ev_of_pair, msg_of_pair = [], []
        for i, ms in enumerate(msgs):
            for m in ms:
                ev_of_pair.append(i)
                msg_of_pair.append(smid[m])
        self.pair_ev = np.asarray(ev_of_pair, dtype=np.int64)
        self.pair_msg = np.asarray(msg_of_pair, dtype=np.int64)
        # reduceat boundaries (pair_ev is non-decreasing by construction)
        first = np.searchsorted(self.pair_ev, np.arange(self.n_ev), "left")
        self.pair_starts = first
        self.primary_msg = np.asarray([smid[m] for m in ev["primary_message"].values],
                                      dtype=np.int64)
        self.base_stop_code = np.asarray([self.fam_code[stop_fam[m]]
                                          for m in self.stop_msgs], dtype=np.int64)

        # --- warning side -------------------------------------------------------
        self.warn_msgs = sorted(set(wn["message"].unique()))
        wmid = {m: i for i, m in enumerate(self.warn_msgs)}
        self.warn_msg_id = np.asarray([wmid[m] for m in wn["message"].values],
                                      dtype=np.int64)
        self.base_warn_code = np.asarray([self.fam_code[warn_fam[m]]
                                          for m in self.warn_msgs], dtype=np.int64)
        self.cand_warn_msg_id = self.warn_msg_id[self.warn_pos]

        self.smid, self.wmid = smid, wmid

    # ---- one variant ---------------------------------------------------------
    def codes(self, flips):
        """(stop-message family codes, warning-message family codes) under `flips`.

        `flips` is a list of (role, message, new_family).
        """
        sc = self.base_stop_code.copy()
        wc = self.base_warn_code.copy()
        for role, msg, fam in flips:
            code = self.fam_code[fam]
            if role == "stop":
                sc[self.smid[msg]] = code
            elif role == "warning":
                wc[self.wmid[msg]] = code
            else:
                raise ValueError(role)
        return sc, wc

    def match(self, flips):
        """Per-event (same_warn, same_n, same_lead_h, primary_family_code)."""
        sc, wc = self.codes(flips)
        bits = (np.int64(1) << sc[self.pair_msg])
        ev_mask = np.bitwise_or.reduceat(bits, self.pair_starts)
        wcode = wc[self.cand_warn_msg_id]
        ok = (((ev_mask[self.ev_pos] >> wcode) & 1) == 1) & (~self.never[wcode])

        n = np.bincount(self.ev_pos[ok], minlength=self.n_ev).astype(np.int64)
        lead = np.full(self.n_ev, np.nan)
        idx = np.flatnonzero(ok)
        if len(idx):
            evs = self.ev_pos[idx]
            firsts = np.unique(evs, return_index=True)[1]   # evs is sorted ascending
            lead[evs[firsts]] = self.hb[idx[firsts]]
        return n > 0, n, lead, sc[self.primary_msg]


# --------------------------------------------------------------------- metrics
def variant_metrics(eng, flips, tier_mask, E, big_pos, fams):
    warn, n, lead, pfam = eng.match(flips)
    w = warn[tier_mask]
    ld = lead[tier_mask]
    e = E[tier_mask]
    tot = e.sum()
    act = w & (ld >= T_ACT_H)
    short = w & ~act

    conv = fams.index("converter")
    cm = tier_mask & (pfam == conv)
    ce = E[cm]
    cw = warn[cm]
    conv_tot = ce.sum()

    if warn[big_pos]:
        bucket = ("actionable_unacted" if lead[big_pos] >= T_ACT_H else "short_lead")
    else:
        bucket = "unwarned"

    return dict(
        n_events=int(tier_mask.sum()), E_mwh=float(tot),
        unwarned_pct_E=100 * float(e[~w].sum()) / tot,
        short_lead_pct_E=100 * float(e[short].sum()) / tot,
        actionable_unacted_pct_E=100 * float(e[act].sum()) / tot,
        warned_pct_E=100 * float(e[w].sum()) / tot,
        warned_n_events=int(w.sum()), warned_E_mwh=float(e[w].sum()),
        actionable_n_events=int(act.sum()), actionable_E_mwh=float(e[act].sum()),
        converter_n_events=int(cm.sum()), converter_E_mwh=float(conv_tot),
        converter_same_warned_pct_E=(100 * float(ce[cw].sum()) / conv_tot
                                     if conv_tot > 0 else np.nan),
        converter_same_warned_n=int(cw.sum()),
        big_event_bucket=bucket,
        big_event_same_warn=bool(warn[big_pos]),
        big_event_lead_h=float(lead[big_pos]) if warn[big_pos] else np.nan,
        big_event_same_n=int(n[big_pos]),
    )


# ------------------------------------------------------------------------ main
def main():
    cm, stop_fam, warn_fam = load_map()
    ev, wn, att = load_frames()
    print(f"events {len(ev):,}   warnings {len(wn):,}   map rows {len(cm):,}")

    cand = build_candidates(ev, wn)
    eng = MapEngine(ev, wn, stop_fam, warn_fam, cand)

    # ---------------------------------------------------------- JOIN CHECK ----
    # the rebuild must reproduce the FROZEN attribution columns exactly, on all
    # 6,050 events, before any flip is applied (warning_dynamics.py's approach).
    any_n = np.bincount(eng.ev_pos, minlength=len(ev)).astype(np.int64)
    assert (any_n == att["any_n_72h"].values).all(), "any_n_72h not reproduced"
    print(f"  JOIN CHECK any_n_72h reproduced: OK ({any_n.sum():,} rows)")

    warn0, n0, lead0, pfam0 = eng.match([])
    assert (n0 == att["same_n_72h"].values).all(), "same_n_72h not reproduced"
    assert (warn0 == att["same_warn_72h"].values).all(), "same_warn_72h not reproduced"
    l_ref = att["same_lead_h_72h"].values
    both = np.isfinite(lead0) & np.isfinite(l_ref)
    assert (np.isfinite(lead0) == np.isfinite(l_ref)).all()
    assert np.allclose(lead0[both], l_ref[both], atol=1e-9), "same_lead_h_72h differs"
    print(f"  JOIN CHECK same_n_72h / same_warn_72h / same_lead_h_72h reproduced: "
          f"OK ({n0.sum():,} rows)")
    base_fam = np.asarray([eng.fams[c] for c in pfam0])
    assert (base_fam == ev["family"].values).all(), "family label not reproduced"
    fa = ev["families_all"].apply(lambda x: frozenset(x)).values
    sc0, _ = eng.codes([])
    bits = (np.int64(1) << sc0[eng.pair_msg])
    m0 = np.bitwise_or.reduceat(bits, eng.pair_starts)
    want = np.asarray([sum(np.int64(1) << eng.fam_code[f] for f in s) for s in fa])
    assert (m0 == want).all(), "families_all not reproduced"
    print("  JOIN CHECK family / families_all reproduced: OK")

    # ------------------------------------------------------- validation gate ---
    tier = att[TIER_FLAG].values.astype(bool)
    E = att["E_mwh"].values.astype(float)
    big_pos = int(np.flatnonzero(att["event_id"].values == BIG_EVENT_ID)[0])
    base = variant_metrics(eng, [], tier, E, big_pos, eng.fams)
    gate = [
        ("T2 events", base["n_events"], 4213, 0),
        ("T2 MWh", base["E_mwh"], 9386.5, 0.05),
        ("unwarned %", base["unwarned_pct_E"], 83.78, 0.005),
        ("short-lead %", base["short_lead_pct_E"], 8.69, 0.005),
        ("actionable %", base["actionable_unacted_pct_E"], 7.53, 0.005),
        ("warned n", base["warned_n_events"], 979, 0),
        ("warned MWh", base["warned_E_mwh"], 1522.8, 0.05),
        ("converter n", base["converter_n_events"], 977, 0),
        ("converter MWh", base["converter_E_mwh"], 1741.3, 0.05),
        ("converter same-warned %", base["converter_same_warned_pct_E"], 0.0, 1e-9),
    ]
    print("\n=== VALIDATION GATE ===")
    okall = True
    for name, got, wantv, tol in gate:
        ok = abs(got - wantv) <= tol
        okall &= ok
        print(f"  {name:<26} got {got:>12,.4f}  want {wantv:>10,.4f}  "
              f"{'OK' if ok else 'FAIL'}")
    assert okall, "VALIDATION GATE FAILED"
    assert base["big_event_bucket"] == "actionable_unacted"
    print(f"  {'big event bucket':<26} {base['big_event_bucket']} "
          f"(lead {base['big_event_lead_h']:.2f} h)  OK")

    # ------------------------------------------------------- enumerate variants
    rows = []
    slot_names = [s["slot"] for s in SLOTS]
    combos = list(itertools.product(*[s["options"] for s in SLOTS]))
    print(f"\nenumerating {len(combos):,} map variants "
          f"({' x '.join(str(len(s['options'])) for s in SLOTS)}) ...")

    for combo in combos:
        flips, labels, quotes = [], [], []
        for slot, choice in zip(SLOTS, combo):
            if choice is None:
                continue
            for role, msg in slot["messages"]:
                flips.append((role, msg, choice))
            labels.append(f"{slot['slot']}:{slot['frozen_family']}->{choice}")
            quotes.append(f"[{slot['slot']}] {slot['rationale']}")
        n_slots = len(labels)
        m = variant_metrics(eng, flips, tier, E, big_pos, eng.fams)
        rows.append(dict(
            variant_id=("frozen" if n_slots == 0
                        else "+".join(labels) if n_slots <= 2
                        else f"joint_{n_slots}slots"),
            variant_type=("frozen" if n_slots == 0
                          else "single_flip" if n_slots == 1 else "joint"),
            n_slots_flipped=n_slots,
            flips_applied="|".join(labels),
            messages_flipped="|".join(f"{r}:{msg}->{f}" for r, msg, f in flips),
            **m,
            delta_actionable_pp=m["actionable_unacted_pct_E"]
            - base["actionable_unacted_pct_E"],
            rationale_quotes=" || ".join(quotes),
        ))

    df = pd.DataFrame(rows)
    df["is_frozen"] = df.n_slots_flipped == 0
    hi = int(df.actionable_unacted_pct_E.idxmax())
    lo = int(df.actionable_unacted_pct_E.idxmin())
    df["is_adverse_joint"] = False
    df["is_max_joint"] = False
    df.loc[lo, "is_adverse_joint"] = True
    df.loc[hi, "is_max_joint"] = True
    # the authorising rationale is identical for every variant that uses a slot, so
    # keep it only where it is read: the single flips and the two extreme joints.
    keep_quotes = (df.n_slots_flipped <= 1) | df.is_adverse_joint | df.is_max_joint
    df.loc[~keep_quotes, "rationale_quotes"] = ""

    # the denominator must be identical everywhere (tier membership untouched)
    assert df.n_events.nunique() == 1 and df.E_mwh.nunique() == 1, \
        "a flip changed the T2 denominator - tier membership must not move"

    # v1.4(a) asks explicitly whether any variant escapes the frozen 95 % CI on the
    # headline, [1.95, 16.72] (bootstrap.csv, tier T2 / rule same / T_act 6 h).
    CI_LO, CI_HI = 1.9, 16.7
    lo_v = float(df.actionable_unacted_pct_E.min())
    hi_v = float(df.actionable_unacted_pct_E.max())
    inside = (lo_v > CI_LO) and (hi_v < CI_HI)
    print(f"\nCI CHECK: all {len(df):,} variants inside the frozen 95% CI "
          f"[{CI_LO}, {CI_HI}]: {'OK' if inside else 'FAIL'} "
          f"(variant range [{lo_v:.3f}, {hi_v:.3f}] %)")
    assert inside, "a map variant escapes the frozen 95% CI - report it, do not bury it"

    df.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}: {len(df):,} rows")

    # -------------------------------------------------------------- reporting
    show = ["variant_id", "actionable_unacted_pct_E", "delta_actionable_pp",
            "unwarned_pct_E", "short_lead_pct_E", "warned_n_events", "warned_E_mwh",
            "converter_same_warned_pct_E", "big_event_bucket"]
    print("\n=== FROZEN MAP (primary) ===")
    print(df.loc[df.is_frozen, show].to_string(index=False,
                                               float_format=lambda x: f"{x:,.3f}"))
    print("\n=== SINGLE FLIPS ===")
    sg = df[df.n_slots_flipped == 1].sort_values("delta_actionable_pp")
    print(sg[show].to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    print("\n=== MOST-ADVERSE JOINT (minimum headline over all "
          f"{len(combos):,} variants) ===")
    print(df.loc[[lo], show + ["flips_applied"]].to_string(
        index=False, float_format=lambda x: f"{x:,.3f}"))
    print("\n=== MAXIMUM-HEADLINE JOINT ===")
    print(df.loc[[hi], show + ["flips_applied"]].to_string(
        index=False, float_format=lambda x: f"{x:,.3f}"))
    print(f"\nHEADLINE RANGE over all variants: "
          f"[{df.actionable_unacted_pct_E.min():.3f}, "
          f"{df.actionable_unacted_pct_E.max():.3f}] % "
          f"(frozen {base['actionable_unacted_pct_E']:.3f} %)")
    print(f"SINGLE-FLIP RANGE: [{sg.actionable_unacted_pct_E.min():.3f}, "
          f"{sg.actionable_unacted_pct_E.max():.3f}] %")
    print("converter same-component coverage, max over all variants: "
          f"{df.converter_same_warned_pct_E.max():.4f} % "
          f"(variants with nonzero coverage: "
          f"{int((df.converter_same_warned_pct_E > 0).sum()):,})")
    print("big-event bucket by variant: "
          + str(df.big_event_bucket.value_counts().to_dict()))
    return df


if __name__ == "__main__":
    main()
