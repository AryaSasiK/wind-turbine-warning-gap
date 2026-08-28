#!/usr/bin/env python3
"""Emit analysis/component_map.csv - the frozen message -> component family map.

STUDY_DESIGN.md "Warning attribution": the same-component matching rule needs a
fixed mapping of the 83 forced-outage stop messages and the 78 Warning messages
into ~10-15 component families plus external / grid / manual. This file *is* that
judgment call; the CSV is a rendering of it, regenerated here so that coverage is
proved against the log rather than asserted.

The map is deliberately conservative in the sense STUDY_DESIGN asks for: a
message with no plausible turbine-side fault semantics (telemetry housekeeping,
weather, externally commanded power reduction) goes to `external`, which by
construction never matches a turbine-side stop.

Two structural facts, both verified by this script:
  * the stop vocabulary and the warning vocabulary are DISJOINT (0 shared
    strings), so no message takes role='both';
  * `comms` and `auxiliary` are warning-only families - no forced-outage stop
    message maps to them - so warnings there can never produce a same-component
    match. That is intentional, not an oversight.

Evidence used per message: the message text, the `Service contract category`,
and the Senvion status-code block the code falls in (codes cluster by subsystem:
5xx-7xx pitch, 8xx rotor speed, 1xxx-19xx gearbox/drivetrain, 2xxx generator and
mechanical brake, 3xxx converter/transformer/switchgear, 4xxx tower and boxes,
5xxx-57xx hydraulics/lights, 6xxx yaw and wind sensors, 7xxx controller,
8xxx comms, 9xxx external).
"""
import os

import pandas as pd

import common as C

FAMILIES = [
    "pitch", "converter", "generator", "drivetrain", "brake_hydraulic", "yaw",
    "anemometry", "tower", "electrical", "control", "comms", "safety",
    "auxiliary", "external", "grid", "manual",
]

# ---------------------------------------------------------------------------
# STOP messages (Status == 'Stop' AND IEC category == 'Forced outage'), n = 83
# (family, rationale-if-not-obvious)
# ---------------------------------------------------------------------------
STOP_MAP = {
    "Externally stopped": ("grid", "Service category 'External stop (grid) (4)'. IEC calls it a forced outage but it is grid-side, not a turbine fault (PROFILE §3 'the trap'); this is the T1 exclusion."),
    "Maximum grid frequency": ("grid", "Service category 'External stop (grid) (4)'. Grid-side. NOTE: not named in STUDY_DESIGN's frozen T1 message list, so the T1/T2 flags do NOT drop it; reported as a sensitivity in checks.md."),
    "Manual stop - remote": ("manual", "Human decision, no turbine-side physical precursor. The T2 exclusion."),
    "Manual stop - on site": ("manual", "Spec-listed T2 exclusion; in this corpus it is IEC 'Scheduled Maintenance' so it never enters the forced-outage base population."),

    # --- pitch -------------------------------------------------------------
    "Pitch controller communication error": ("pitch", "A comms fault *inside* the pitch system; service category is 'Pitch errors (18)', so it is a pitch failure, not a SCADA/network comms failure."),
    "Charging circuit pitch": ("pitch", ""),
    "Pitch run-away (hub box v.>=4)": ("pitch", "Service category says 'Controller error of the WP3100' but the message names the pitch hub box explicitly; message semantics win."),
    "Pitch current asymmetry": ("pitch", ""),
    "Set point><actual value axis 1": ("pitch", "'axis n' = pitch axis n (three blades)."),
    "Set point><actual value axis 2": ("pitch", "'axis n' = pitch axis n."),
    "Set point><actual value axis 3": ("pitch", "'axis n' = pitch axis n."),
    "Pitch angle deviation": ("pitch", ""),
    "Pitch too slow BP180": ("pitch", ""),
    "Pitch error": ("pitch", ""),
    "Battery voltage axis 3": ("pitch", "Pitch back-up batteries (code block 700-735, service category 'Pitch errors')."),
    "Batt. undervoltage/overvoltage": ("pitch", "Pitch back-up batteries."),
    "Battery voltage axis 1": ("pitch", "Pitch back-up batteries."),
    "Error pitch converter 1": ("pitch", ""),
    "Error pitch converter 2": ("pitch", ""),
    "Error pitch converter 3": ("pitch", ""),
    "Pitch limit switch 2": ("pitch", ""),
    "Bladeangle implausible": ("pitch", ""),
    "Timeout bridging limit switches": ("pitch", "Code 513 sits in the pitch limit-switch block; service category 'Pitch errors'."),
    "Max. pitch speed encoder A": ("pitch", ""),
    "Max. pitch speed encoder B": ("pitch", ""),
    "Overload fan pitch motor": ("pitch", ""),

    # --- converter ---------------------------------------------------------
    "Frequency converter not ready": ("converter", ""),
    "Frequency converter error": ("converter", ""),
    "Frequency converter load rejection": ("converter", ""),
    "Max.temp.conv.inl.>perm.out.t.": ("converter", "Converter inlet coolant over-temperature."),
    "Current asymmetry": ("converter", "AMBIGUOUS: service category 'Generator and Converter errors (20)' does not separate the two. Code 3555 sits in the 3xxx converter/switchgear block (generator faults are 2xxx), so assigned to converter. Alternative: generator."),

    # --- generator ---------------------------------------------------------
    "Service generator brushes": ("generator", ""),
    "Max. temp. gen. bearing 1": ("generator", ""),
    "Thermistor generator": ("generator", "Generator winding thermistor trip."),

    # --- drivetrain (gearbox, main shaft, rotor speed) ---------------------
    "Missing gear oil (high rpm)": ("drivetrain", ""),
    "Low gearbox oil pressure": ("drivetrain", ""),
    "Implausible gear speed": ("drivetrain", "Service category 'Sensor error (21)', but the sensed quantity is the gearbox/rotor speed - the affected subsystem is the drivetrain."),
    "Particle Gear Alarm 24h": ("drivetrain", "Gearbox oil-debris (metal particle) sensor."),
    "Overload gear oil pump": ("drivetrain", "Service category 'Electrical error (24)' describes the failure mode (motor overload); the component is the gearbox lubrication system."),
    "Overload fan oil cooler gear": ("drivetrain", "As above - gearbox oil-cooler fan."),
    "Disc filter adaption implausible": ("drivetrain", "Gearbox oil disc filter (code block 16xx); service category 'Sensor error' describes the detection, not the component."),
    "High rotor speed nacelle": ("drivetrain", "Rotor overspeed - drivetrain rotational subsystem."),
    "Rotor overspeed nacelle": ("drivetrain", ""),
    "Rotor sensor A defective": ("drivetrain", "Rotor speed sensor."),
    "Max. drivetrain oscillations": ("drivetrain", "Service category 'Repeated error (25)' is a trip-count property, not a component; the message names the drivetrain."),

    # --- brake / hydraulics ------------------------------------------------
    "Feedback brake 1": ("brake_hydraulic", ""),
    "Feedback brake 2": ("brake_hydraulic", ""),
    "Brake control": ("brake_hydraulic", ""),
    "Low hydraulic pressure": ("brake_hydraulic", "The hydraulic system on the MM82/92 serves the mechanical brake; merged into one family."),
    "Overload hydraulic pump": ("brake_hydraulic", ""),

    # --- yaw ---------------------------------------------------------------
    "Uncontrolled yaw movement": ("yaw", ""),
    "Yaw error": ("yaw", ""),
    "Yaw speed high": ("yaw", ""),
    "Yaw velocity too low": ("yaw", ""),
    "Overload yaw motor 1&3": ("yaw", ""),
    "Overload yaw motor 2&4": ("yaw", ""),
    "Max. cable twistangle": ("yaw", "Cable twist is a consequence of yaw travel; the cable-untwist function belongs to the yaw system."),
    "High yaw load": ("yaw", "AMBIGUOUS: service category is 'External stop (climate) (6)', which would argue for `external`, but the message and code block (60xx) are yaw. Assigned to yaw; n=1 so the choice is immaterial. Alternative: external."),

    # --- anemometry --------------------------------------------------------
    "Anemometer defect": ("anemometry", ""),
    "Vane defect": ("anemometry", ""),

    # --- tower -------------------------------------------------------------
    "Tower oscillation Y level 1": ("tower", ""),
    "Tower oscillation Y level 2": ("tower", ""),
    "Tower oscillation X level 1": ("tower", ""),
    "Tower oscillation X level 2": ("tower", ""),
    "Tower resonance": ("tower", ""),
    "Oscillation encoder tower": ("tower", "Tower accelerometer; service category 'Sensor error' describes the detection, the component is the tower monitoring chain."),

    # --- electrical (LV/MV switchgear, transformer, UPS, lightning) --------
    "Supply circuit breaker off-state": ("electrical", ""),
    "Circuit breaker": ("electrical", ""),
    "UPS error": ("electrical", ""),
    "UPS buffer time too short": ("electrical", ""),
    "Max. transformer temp.": ("electrical", ""),

    # --- control (turbine controller / firmware / configuration) -----------
    "mconfig.ini check failed": ("control", "WP3100 controller configuration file."),
    "Task runtime failure 10 ms": ("control", "WP3100 controller task scheduler."),
    "PLC hardware error": ("control", ""),
    "Repeating error BP52": ("control", "AMBIGUOUS and high-volume (251 stops). Service category 'Repeated error (25)' names a trip-count supervisor, not a component; 'BP' also prefixes pitch messages ('Pitch too slow BP180'), so a pitch reading is possible. Assigned to `control` as the conservative choice - `control` is a thin family, so a wrong call here creates few spurious same-component matches. Pairs with the warning 'Repeating error BP 0'. Alternative: pitch."),
    "WEC shut down": ("control", "AMBIGUOUS: generic supervisory shutdown, service category 'WEC Shutdown (1)', no component named. Assigned to `control` rather than `manual` because nothing in the message implies a human action. Alternative: manual."),
    "No speed development": ("control", "AMBIGUOUS: rotor fails to spin up on start; the physical cause could be pitch, brake or drivetrain. Assigned to `control` (start-up supervisor) precisely because it does not identify a component; n=4. Alternatives: pitch, brake_hydraulic."),

    # --- safety ------------------------------------------------------------
    "Safety chain open": ("safety", ""),
    "Emergency stop base box": ("safety", ""),
    "Emergency stop top box": ("safety", ""),
    "Emergency stop nacelle": ("safety", ""),
    "Smoke warning nacelle stop": ("safety", ""),

    # --- external (weather / no fault semantics) ---------------------------
    "Wind < power": ("external", "Wind-versus-power plausibility stop driven by the wind resource, not a component failure."),
    "Wind > power": ("external", "As above."),
}

# ---------------------------------------------------------------------------
# WARNING messages (Status == 'Warning'), n = 78
# ---------------------------------------------------------------------------
WARN_MAP = {
    # --- external: telemetry / weather / commanded, no fault semantics -----
    "P output externally reduced": ("external", "Named in STUDY_DESIGN as the archetype: an externally commanded set-point, not a fault."),
    "Icing (dev. electr. power)": ("external", "Weather; service category 'External stop (climate) (6)'."),
    "Check time synchronization": ("external", "AMBIGUOUS but high-volume (526 warnings). Pure housekeeping telemetry (NTP drift) with no fault semantics, so `external` per the STUDY_DESIGN rule. Putting it in `control` would let 526 clock-drift notices match controller stops. Alternative: control."),
    "Time sync. failed (SNTP error)": ("external", "As above."),

    # --- anemometry --------------------------------------------------------
    "4-20mA anemometer 1": ("anemometry", "4-20 mA loop fault on the anemometer signal."),
    "4-20mA anemometer 2": ("anemometry", ""),
    "4-20 mA vane 1": ("anemometry", ""),
    "4-20 mA vane 2": ("anemometry", ""),
    "Vane 1 defect": ("anemometry", ""),
    "Vane 2 defect": ("anemometry", ""),

    # --- brake / hydraulics ------------------------------------------------
    "Timeout brake closed": ("brake_hydraulic", ""),
    "Brake accumulator defect": ("brake_hydraulic", "Hydraulic accumulator of the mechanical brake."),
    "Brake pads worn": ("brake_hydraulic", ""),
    "Pressure drop hydraulic sys.": ("brake_hydraulic", ""),

    # --- comms (warning-only family: no forced-outage stop maps here) ------
    "Comm. failure FPM": ("comms", "Farm/park-management communication link."),
    "No assignment to a PMU": ("comms", "Park-management unit association."),
    "IP duplicate in WF network": ("comms", "Wind-farm network addressing."),
    "Comm.err. IEC server <- CMS drive tr.": ("comms", "AMBIGUOUS: the condition-monitoring (CMS) link for the drivetrain. Assigned to `comms` because the message reports the monitoring channel failing, not a drivetrain fault - the conservative reading. Alternative: drivetrain."),
    "Comm.err. IEC client -> CMS drive tr.": ("comms", "As above. Alternative: drivetrain."),
    "CMS drive train system error": ("comms", "As above - the CMS itself errors. Alternative: drivetrain."),

    # --- yaw ---------------------------------------------------------------
    "High yaw motor current": ("yaw", ""),
    "Easy yaw": ("yaw", "Yaw-control operating mode fault."),
    "Check nacelle position!": ("yaw", "Nacelle position is the yaw system's controlled variable."),
    "4-20mA yaw current sensor": ("yaw", ""),

    # --- pitch -------------------------------------------------------------
    "Battery charge cycle axis 1 error": ("pitch", "Pitch back-up batteries."),
    "Battery charge cycle axis 2 error": ("pitch", ""),
    "Battery charge cycle axis 3 error": ("pitch", ""),
    "Pitch batteries charging cycle": ("pitch", ""),
    "Battery monitoring axis 1": ("pitch", ""),
    "Battery monitoring axis 2": ("pitch", ""),
    "Battery monitoring axis 3": ("pitch", ""),
    "Battery monitoring test interval": ("pitch", ""),
    "Pitch measuring system 1><2": ("pitch", ""),
    "Limit switch error 95° axis 1": ("pitch", "95 deg = feathered blade position."),
    "Limit switch error 95° axis 2": ("pitch", ""),
    "Limit switch error 95° axis 3": ("pitch", ""),
    "Timeout B sensor active": ("pitch", "Code 697 sits inside the pitch block (650-697); 'B sensor' is the pitch limit sensor."),
    "Error lubrication pump pitch": ("pitch", ""),
    "Error brake resistor CHP": ("pitch", "AMBIGUOUS and high-volume (235 warnings). 'CHP' = chopper brake resistor. Code 785 sits between the pitch battery block (700-735) and the pitch lubrication pump (850), and the MM82/92 pitch drives have their own braking chopper, so assigned to `pitch`. A converter DC-link chopper reading is equally defensible. Alternatives: converter, brake_hydraulic. FLAGGED for orchestrator review."),

    # --- converter ---------------------------------------------------------
    "Reduced power converter": ("converter", ""),
    "PT100 converter inlet temperature defect": ("converter", ""),
    "Converter torque <> setpoint": ("converter", ""),
    "Converter power too low": ("converter", ""),
    "Cable overload": ("converter", "Code 3160 sits in the converter block (3151-3265); read as the converter output cabling. Alternative: electrical."),

    # --- generator ---------------------------------------------------------
    "Overload generator fan 1": ("generator", ""),
    "Overload generator fan 2": ("generator", ""),
    "Overload generator fan 3": ("generator", ""),
    "Overload generator heating": ("generator", ""),
    "High temp. gen. bearing 1": ("generator", ""),

    # --- drivetrain --------------------------------------------------------
    "Overload gear heating": ("drivetrain", "Service category 'Electrical error (24)' is the failure mode; the component is the gearbox heater."),
    "Particle Gear Alarm 10min": ("drivetrain", "Gearbox oil-debris sensor - the 10-min companion of the 24h stop message."),
    "Particle sensor defect": ("drivetrain", "Gearbox oil-debris sensor."),
    "Oil filter gear choked": ("drivetrain", ""),
    "Overload gear bypass filter": ("drivetrain", ""),
    "Drivetrain oscillations": ("drivetrain", ""),
    "High temp. gear bearing 1": ("drivetrain", ""),
    "High temp. gear bearing 2": ("drivetrain", ""),
    "PT100 inlet gear defect": ("drivetrain", ""),
    "Reduced power gearbox": ("drivetrain", "Gearbox-driven derate."),

    # --- tower -------------------------------------------------------------
    "Nat. tower freq. implausible": ("tower", ""),
    "Max. acceleration": ("tower", "Nacelle/tower acceleration limit - the warning counterpart of the tower-oscillation stops."),

    # --- electrical --------------------------------------------------------
    "Overload transformer fan outlet air": ("electrical", ""),
    "Overload transf. fan inlet air": ("electrical", ""),
    "Reduced power transformer": ("electrical", ""),
    "UPS warning": ("electrical", ""),
    "Lightning protection defect": ("electrical", ""),
    "Maintenance LV HRC fuse": ("electrical", "LV high-rupture-capacity fuse in the tower-base switchgear."),

    # --- control -----------------------------------------------------------
    "Parameter outside limits": ("control", "Controller parameter-set integrity."),
    "Repeating error BP 0": ("control", "AMBIGUOUS. Pairs with the stop message 'Repeating error BP52'; both are assigned to `control` so that they can match each other, and so that a wrong reading of 'BP' does not inject 204 warnings into the large `pitch` family. Alternative: pitch."),

    # --- auxiliary (warning-only family: obstruction lights, box climate) --
    "Breakdown obstacle light": ("auxiliary", "Aviation obstruction light - no effect on the drivetrain."),
    "Service obstacle light": ("auxiliary", ""),
    "Heating/fan base box faulty": ("auxiliary", "Tower-base control-cabinet climate."),
    "Heating/fan top box faulty": ("auxiliary", "Nacelle control-cabinet climate."),
    "PT100 base box temp. defect": ("auxiliary", ""),
    "PT100 top box defect": ("auxiliary", ""),
    "Top box temperature high": ("auxiliary", ""),
    "High temperature nacelle": ("auxiliary", ""),
    "PT100 nacelle temp. defect": ("auxiliary", ""),
}


def build():
    st, _ = C.load_status()
    stops = st[(st["Status"] == C.BASE_STATUS) & (st["IEC category"] == C.BASE_IEC)]
    warns = st[st["Status"] == "Warning"]

    stop_msgs = set(stops["Message"].dropna())
    warn_msgs = set(warns["Message"].dropna())
    both = stop_msgs & warn_msgs

    problems = []
    for name, observed, mapping in (("stop", stop_msgs, STOP_MAP),
                                    ("warning", warn_msgs, WARN_MAP)):
        missing = observed - set(mapping)
        if missing:
            problems.append(f"{name}: {len(missing)} unmapped -> {sorted(missing)}")
    extra_stop = set(STOP_MAP) - stop_msgs
    if extra_stop:
        # 'Manual stop - on site' is expected here: spec-listed, never forced-outage.
        print("note: mapped-but-not-observed stop messages:", sorted(extra_stop))
    bad_family = {m: f for m, (f, _) in list(STOP_MAP.items()) + list(WARN_MAP.items())
                  if f not in FAMILIES}
    if bad_family:
        problems.append(f"unknown family: {bad_family}")
    if problems:
        raise SystemExit("component map is incomplete:\n  " + "\n  ".join(problems))

    stop_n = stops["Message"].value_counts()
    warn_n = warns["Message"].value_counts()
    stop_code = stops.groupby("Message")["Code"].first()
    warn_code = warns.groupby("Message")["Code"].first()
    stop_svc = stops.groupby("Message")["Service contract category"].agg(
        lambda s: "|".join(sorted(set(s.dropna().astype(str)))))
    warn_svc = warns.groupby("Message")["Service contract category"].agg(
        lambda s: "|".join(sorted(set(s.dropna().astype(str)))))

    rows = []
    for msg, (fam, why) in STOP_MAP.items():
        rows.append({"message": msg, "role": "both" if msg in both else "stop",
                     "family": fam, "code": stop_code.get(msg, ""),
                     "n_rows": int(stop_n.get(msg, 0)),
                     "service_contract_category": stop_svc.get(msg, ""),
                     "rationale": why})
    for msg, (fam, why) in WARN_MAP.items():
        if msg in both:
            continue
        rows.append({"message": msg, "role": "warning", "family": fam,
                     "code": warn_code.get(msg, ""), "n_rows": int(warn_n.get(msg, 0)),
                     "service_contract_category": warn_svc.get(msg, ""),
                     "rationale": why})

    cm = pd.DataFrame(rows).sort_values(
        ["role", "family", "n_rows"], ascending=[True, True, False])
    out = os.path.join(C.SUMMARY_OUT, "component_map.csv")
    cm.to_csv(out, index=False)
    print(f"wrote {out}: {len(cm)} rows "
          f"({(cm.role=='stop').sum()} stop, {(cm.role=='warning').sum()} warning, "
          f"{(cm.role=='both').sum()} both), {cm.family.nunique()} families")
    print()
    piv = cm.pivot_table(index="family", columns="role", values="n_rows",
                         aggfunc="sum", fill_value=0)
    cnt = cm.pivot_table(index="family", columns="role", values="message",
                         aggfunc="count", fill_value=0)
    piv.columns = [f"rows_{c}" for c in piv.columns]
    cnt.columns = [f"msgs_{c}" for c in cnt.columns]
    print(pd.concat([cnt, piv], axis=1).to_string())
    return cm


if __name__ == "__main__":
    build()
