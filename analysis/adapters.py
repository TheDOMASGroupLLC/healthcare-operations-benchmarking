import numpy as np
import pandas as pd

from incidents_preprocessing import incidents_analysis_prep
from weight_preprocessing import analysis_prep as weights_prep


def weights_to_benchmark(df_weight: pd.DataFrame) -> pd.DataFrame:
    weights = weights_prep(df_weight).copy()
    out = pd.DataFrame({
        "resident_id":    weights["resident_id"],
        "community":      weights["community"],
        "dates_recorded": weights["dates_recorded"],
        "is_event":       weights["is_event"],
        "date_diff":      weights["date_diff"],
        "event_group":    "Weight",
        "subtype":        pd.NA,
        "threshold_event": pd.to_numeric(weights["threshold_event"], errors="coerce"),
        "event_direction": weights.get("event_direction", pd.NA),
    })
    return out
def incidents_to_benchmark(df_inc: pd.DataFrame) -> pd.DataFrame:
    """Standardize incident records for benchmarking and assign fall severity scores."""
    incidents = incidents_analysis_prep(df_inc, floor_to="D").copy()

    # Limit incident events to falls and on-floor events.
    fall_flag = np.zeros(len(incidents), dtype=bool)

    if "type__INCIDENT_TYPE_FALL" in incidents.columns:
        fall_flag |= incidents["type__INCIDENT_TYPE_FALL"].astype(bool)
    if "type__INCIDENT_TYPE_ON_FLOOR" in incidents.columns:
        fall_flag |= incidents["type__INCIDENT_TYPE_ON_FLOOR"].astype(bool)

    incidents["is_fall"] = fall_flag


    # Calculate per-resident gaps between fall events.
    falls = incidents[incidents["is_fall"]].copy()
    falls = falls.sort_values(["resident_id", "dates_recorded"])

    falls["fall_date_diff"] = (
        falls.groupby("resident_id")["dates_recorded"]
            .diff()
            .dt.days
            .astype("float")
    )

    incidents["fall_date_diff"] = np.nan
    incidents["fall_date_diff"] = incidents["fall_date_diff"].astype("float64")
    incidents.loc[falls.index, "fall_date_diff"] = falls["fall_date_diff"]

    # Severity score: 1 for fall/on-floor, +2 for injury, +3 for hospitalization or medical emergency.

    injury_flag = np.zeros(len(incidents), dtype=bool)
    if "type__INCIDENT_TYPE_INJURY" in incidents.columns:
        injury_flag |= incidents["type__INCIDENT_TYPE_INJURY"].astype(bool)
    else:
        injury_flag |= incidents["subtype"].fillna("").str.contains("INCIDENT_TYPE_INJURY")

    hosp_flag = np.zeros(len(incidents), dtype=bool)
    for col in ["type__INCIDENT_TYPE_HOSPITALIZATION", "type__INCIDENT_TYPE_MEDICAL_EMERGENCY"]:
        if col in incidents.columns:
            hosp_flag |= incidents[col].astype(bool)

    severity_score = np.zeros(len(incidents), dtype="float64")

    severity_score += np.where(incidents["is_fall"], 1.0, 0.0)
    severity_score += np.where(incidents["is_fall"] & injury_flag, 2.0, 0.0)
    severity_score += np.where(incidents["is_fall"] & hosp_flag, 3.0, 0.0)

    # Downstream incident metrics use fall events only.
    incidents["threshold_event"] = np.where(incidents["is_fall"], severity_score, np.nan)
    incidents["is_event"] = incidents["is_fall"]

    return incidents
