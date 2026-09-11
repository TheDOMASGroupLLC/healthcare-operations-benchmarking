# adapters.py
import pandas as pd
from weight_preprocessing import analysis_prep as weights_prep
from incidents_preprocessing import incidents_analysis_prep
import numpy as np


def weights_to_benchmark(df_weight: pd.DataFrame) -> pd.DataFrame:
    w = weights_prep(df_weight).copy()  # this creates `threshold_event`
    out = pd.DataFrame({
        "resident_id":    w["resident_id"],
        "community":      w["community"],
        "dates_recorded": w["dates_recorded"],
        "is_event":       w["is_event"],
        "date_diff":      w["date_diff"],
        "event_group":    "Weight",
        "subtype":        pd.NA,
        "threshold_event": pd.to_numeric(w["threshold_event"], errors="coerce"),
        "event_direction": w.get("event_direction", pd.NA),
    })
    return out
def incidents_to_benchmark(df_inc: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize incidents to the benchmark schema and add a fall-focused severity score.

    Event inclusion:
      - Only incidents with type__INCIDENT_TYPE_FALL or type__INCIDENT_TYPE_ON_FLOOR
        are counted as events (is_event = True).

    Severity:
      - Baseline fall/on-floor: 1
      - +2 if injury is present
      - +3 if hospitalization or medical emergency is present

    Also adds:
      - is_fall: boolean
      - fall_date_diff: days between successive falls per resident
    """
    # Confirm one row per event, type__* flags, subtype, date_diff, etc.
    d = incidents_analysis_prep(df_inc, floor_to="D").copy()

    # FALL INCLUSION FLAG (only these count as events)
    fall_flag = np.zeros(len(d), dtype=bool)

    if "type__INCIDENT_TYPE_FALL" in d.columns:
        fall_flag |= d["type__INCIDENT_TYPE_FALL"].astype(bool)
    if "type__INCIDENT_TYPE_ON_FLOOR" in d.columns:
        fall_flag |= d["type__INCIDENT_TYPE_ON_FLOOR"].astype(bool)

    d["is_fall"] = fall_flag


    # DAYS BETWEEN FALLS (for repeat-fall metrics)
    fall = d[d["is_fall"]].copy()
    fall = fall.sort_values(["resident_id", "dates_recorded"])

    fall["fall_date_diff"] = (
        fall.groupby("resident_id")["dates_recorded"]
            .diff()
            .dt.days
            .astype("float")
    )

    d["fall_date_diff"] = np.nan
    d["fall_date_diff"] = d["fall_date_diff"].astype("float64")
    d.loc[fall.index, "fall_date_diff"] = fall["fall_date_diff"]

    #  SEVERITY SCORE - baseline fall or on floor = 1, +2 if injury, +3 if hospitalization or medical emergency

    injury_flag = np.zeros(len(d), dtype=bool)
    if "type__INCIDENT_TYPE_INJURY" in d.columns:
        injury_flag |= d["type__INCIDENT_TYPE_INJURY"].astype(bool)
    else:
        injury_flag |= d["subtype"].fillna("").str.contains("INCIDENT_TYPE_INJURY")

    hosp_flag = np.zeros(len(d), dtype=bool)
    for col in ["type__INCIDENT_TYPE_HOSPITALIZATION", "type__INCIDENT_TYPE_MEDICAL_EMERGENCY"]:
        if col in d.columns:
            hosp_flag |= d[col].astype(bool)

    # start with zeros
    score = np.zeros(len(d), dtype="float64")

    # 1 for any fall/on-floor
    score += np.where(d["is_fall"], 1.0, 0.0)
    # +2 if injury
    score += np.where(d["is_fall"] & injury_flag, 2.0, 0.0)
    # +3 if hospitalization or medical emergency
    score += np.where(d["is_fall"] & hosp_flag, 3.0, 0.0)

    # Only fall-related incidents are "events" in downstream analysis
    d["threshold_event"] = np.where(d["is_fall"], score, np.nan)
    d["is_event"] = d["is_fall"]

    return d
