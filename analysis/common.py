"""Shared config + status-log loading for the analysis pipeline (stage 1).

Everything here is deliberately boring: plain pandas, no hidden state, and every
constant that the study design pins down is a named module-level object so that
`checks.md` can quote it and stage 2 can import it rather than re-typing it.

Traps handled (PROFILE.md section refs):
  §3  'Timestamp end'/'Duration' use the string '-' as the "no end" sentinel.
  §3  status logs gain two trailing columns in 2021+ exports (ragged concat).
  §3  26% of interval events overlap a prior event; 8,680 exact duplicates.
  §4  SCADA header row is itself '#'-prefixed  -> wtio.peek finds it by content.
  §7  2023-2024 SCADA members carry ~41x all-NaN padding rows -> wtio drops them.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
DATA = os.path.join(PROJECT, "data")
DERIVED = os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived")
ANALYSIS_OUT = DERIVED                      # big derived artefacts live off-boot
SUMMARY_OUT = HERE                          # small summaries stay in the repo

sys.path.insert(0, DATA)                    # for `import wtio`

STATUS_PARQUET = os.path.join(DERIVED, "status_all.parquet")
EVENTS_PARQUET = os.path.join(DERIVED, "events.parquet")
WARNINGS_PARQUET = os.path.join(DERIVED, "warnings.parquet")
SCADA_CACHE = os.path.join(DERIVED, "scada_min")

# ---------------------------------------------------------------- study design
# STUDY_DESIGN.md "Event definition"
BASE_STATUS = "Stop"
BASE_IEC = "Forced outage"

# Commissioning exclusion (STUDY_DESIGN "Commissioning exclusion", PROFILE §2).
COD = {"kelmarsh": pd.Timestamp("2016-04-15"),
       "penmanshiel": pd.Timestamp("2016-09-01")}

# T1: grid-side messages, exactly the list frozen in STUDY_DESIGN.md.
# Of these only `Externally stopped` actually occurs with IEC == 'Forced outage'
# (`Grid loss`/`Grid error`/`Grid disconnection for self-protection` are tagged
# 'Out of Electrical Specification' - PROFILE §3 "the trap"), so the other three
# are inert here but kept verbatim so the code matches the frozen spec.
GRID_MESSAGES = {
    "Externally stopped",
    "Grid loss",
    "Grid error",
    "Grid disconnection for self-protection",
}
# Not named in STUDY_DESIGN's T1 list but carries service category
# 'External stop (grid) (4)' and is a forced-outage stop (31 events). PROFILE §3's
# own "excluding grid and manual/remote" row (4,452) does exclude it. Reported as
# a sensitivity, NOT applied to the frozen T1/T2 flags.
GRID_MESSAGES_EXTRA = {"Maximum grid frequency"}

# T2: manual stops. `Manual stop - on site` is IEC 'Scheduled Maintenance', not
# 'Forced outage', so it never reaches the base population; kept for spec fidelity.
MANUAL_MESSAGES = {"Manual stop - remote", "Manual stop - on site"}

# ---------------------------------------------------------------- SCADA columns
TS = "Date and time"
POWER = "Power (kW)"
POT = "Cascading potential power (kW)"          # PROFILE §4: the coalesced series
WIND = "Wind speed (m/s)"
GB_DOWNTIME = "Lost Production to Downtime (kWh)"
GB_CURTAIL = "Lost Production to Curtailment (Total) (kWh)"
SCADA_COLS = [TS, WIND, POWER, POT, GB_DOWNTIME, GB_CURTAIL]

BIN_HOURS = 10.0 / 60.0                          # 10-minute SCADA grid (PROFILE §4)


def load_status():
    """Pooled status log with the '-' sentinel handled and t0/t1 parsed.

    Returns the frame plus a dict of provenance counts for checks.md.
    """
    st = pd.read_parquet(STATUS_PARQUET)
    st.columns = [c.strip() for c in st.columns]
    counts = {"status_rows_raw": len(st)}
    # 25 rows carry 'Parameter outside limits ' with a trailing space. Stripping
    # collapses no other pair (83 stop / 78 warning messages before and after),
    # so the vocabulary is unchanged and joins on Message stop silently failing.
    counts["status_untrimmed_messages"] = int(
        (st["Message"].notna() & (st["Message"] != st["Message"].str.strip())).sum())
    st["Message"] = st["Message"].str.strip()
    for c in ("Timestamp end", "Duration"):
        st[c] = st[c].replace("-", np.nan)
    st["t0"] = pd.to_datetime(st["Timestamp start"], errors="coerce", format="mixed")
    st["t1"] = pd.to_datetime(st["Timestamp end"], errors="coerce", format="mixed")
    st["dur_s"] = pd.to_timedelta(st["Duration"], errors="coerce").dt.total_seconds()
    counts["status_unparsed_start"] = int(st["t0"].isna().sum())
    counts["status_instantaneous"] = int(st["t1"].isna().sum())
    return st, counts


def pre_cod_mask(df):
    """True where the row precedes its farm's commercial operation date."""
    m = pd.Series(False, index=df.index)
    for farm, cod in COD.items():
        m |= (df["farm"] == farm) & (df["t0"] < cod)
    return m


def merge_intervals(df, key=("farm", "turbine_id")):
    """Assign a merge-group id to overlapping/nested intervals per turbine.

    Intervals are merged when they overlap *or touch* (next.t0 <= running max
    end). PROFILE §3 establishes that stop intervals nest rather than pile up
    (max concurrency 2), so a single running-max sweep is sufficient.

    Returns df with a 'group' column (int, unique across the whole frame).
    """
    k = list(key)
    df = df.sort_values(k + ["t0", "t1"]).copy()
    g = df.groupby(k, sort=False)
    run_end = g["t1"].cummax().shift(1)      # max end of everything before this row
    first_in_turbine = g.cumcount() == 0     # ...so the shift never leaks across turbines
    starts_new = first_in_turbine | (df["t0"] > run_end)
    df["group"] = starts_new.cumsum() - 1
    return df


def fmt_mwh(x):
    return f"{x:,.1f}"
