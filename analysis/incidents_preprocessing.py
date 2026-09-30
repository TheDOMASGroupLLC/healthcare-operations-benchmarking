import pandas as pd
import numpy as np
from typing import Optional
from helpers import to_list_cell


def incidents_analysis_prep(df: pd.DataFrame, *, floor_to: Optional[str] = None) -> pd.DataFrame:
    """Standardize incidents to one benchmark row per resident, community, and timestamp."""
    incidents = df.copy()

    dates = pd.to_datetime(incidents["occurred_at"], errors="coerce").dt.tz_localize(None)
    if floor_to:
        dates = dates.dt.floor(floor_to)
    incidents["dates_recorded"] = dates

    incidents["type"] = incidents["type"].apply(to_list_cell)
    if "location" in incidents.columns:
        incidents["location"] = incidents["location"].apply(to_list_cell)

    # Group incident types recorded at the same timestamp into one event.
    def _uniq_sorted_types(series_of_lists):
        flat = []
        for lst in series_of_lists:
            if isinstance(lst, (list, tuple)):
                flat.extend([str(x) for x in lst if pd.notna(x)])
        return sorted(set(flat))

    def _first_non_null(s):
        s = s.dropna()
        return s.iloc[0] if not s.empty else pd.NA

    grp_cols = ["resident_id", "community", "dates_recorded"]
    events = (
        incidents.groupby(grp_cols, dropna=False)
         .agg(
             types=("type", _uniq_sorted_types),
             organization=("organization", _first_non_null) if "organization" in incidents.columns else ("type", lambda _: pd.NA),
             location=("location", _first_non_null) if "location" in incidents.columns else ("type", lambda _: pd.NA),
         )
         .reset_index()
    )

    events = events[events["dates_recorded"].notna()].copy()
    events = events.sort_values(["resident_id", "dates_recorded"]).reset_index(drop=True)
    events["date_diff"] = (
        events.groupby("resident_id")["dates_recorded"]
          .diff()
          .dt.days
          .astype("float")
    )

    # Preserve a pipe-delimited subtype for downstream compatibility.
    events["subtype"] = (
        events["types"]
        .apply(
            lambda lst: "|".join(
                sorted({str(t) for t in lst if pd.notna(t)})
            ) if isinstance(lst, (list, tuple)) else ""
        )
        .astype("string")
    )

    # Create one boolean indicator per incident type.
    all_types = sorted({
        t
        for lst in events["types"]
        if isinstance(lst, (list, tuple))
        for t in lst
        if pd.notna(t)
    })

    def _safe_col_name(t: str) -> str:
        return "type__" + (
            str(t)
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
        )

    type_cols = []
    for t in all_types:
        col = _safe_col_name(t)
        type_cols.append(col)
        events[col] = events["types"].apply(
            lambda lst, val=t: isinstance(lst, (list, tuple)) and (val in lst)
        )

    # Keep the benchmark schema plus raw type indicators.
    result = events.copy()
    result["is_event"]        = True
    result["event_group"]     = "Incident"
    result["threshold_event"] = np.nan
    result["event_direction"] = pd.NA

    result["resident_id"] = result["resident_id"].astype("string")
    result["community"]   = result["community"].astype("string")

    core_cols = [
        "resident_id", "community", "dates_recorded",
        "is_event", "date_diff",
        "event_group", "subtype", "threshold_event", "event_direction",
    ]
    helper_cols = ["types"] + type_cols

    cols = [c for c in core_cols + helper_cols if c in result.columns]
    result = result[cols]

    return result
