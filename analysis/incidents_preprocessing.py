# incidents_preprocessing.py
import pandas as pd
import numpy as np
from typing import Optional
from helpers import to_list_cell


def incidents_analysis_prep(df: pd.DataFrame, *, floor_to: Optional[str] = None) -> pd.DataFrame:
    """
    Standardize Incidents to the benchmark schema.
    Rules:
      - One *event* = same (resident_id, community, timestamp). One event may have many types.
      - Compute cadence (date_diff) across events per resident.
      - KEEP ONE ROW per event.
    """
    d = df.copy()

    # Parse datetime and optionally floor (e.g., 'min' to merge same-minute entries)
    dates = pd.to_datetime(d["occurred_at"], errors="coerce").dt.tz_localize(None)
    if floor_to:
        dates = dates.dt.floor(floor_to)
    d["dates_recorded"] = dates

    # Normalize multi-select columns
    d["type"] = d["type"].apply(to_list_cell)
    if "location" in d.columns:
        d["location"] = d["location"].apply(to_list_cell)

    # Collapse to one EVENT per (resident_id, community, dates_recorded)
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
    ev = (
        d.groupby(grp_cols, dropna=False)
         .agg(
             types=("type", _uniq_sorted_types),
             organization=("organization", _first_non_null) if "organization" in d.columns else ("type", lambda _: pd.NA),
             location=("location", _first_non_null) if "location" in d.columns else ("type", lambda _: pd.NA),
         )
         .reset_index()
    )

    # Drop events without a valid timestamp and compute event-level cadence
    ev = ev[ev["dates_recorded"].notna()].copy()
    ev = ev.sort_values(["resident_id", "dates_recorded"]).reset_index(drop=True)
    ev["date_diff"] = (
        ev.groupby("resident_id")["dates_recorded"]
          .diff()
          .dt.days
          .astype("float")
    )

    # Build a pipe-joined `subtype` string for compatibility with add_incident_thresholds()
    ev["subtype"] = (
        ev["types"]
        .apply(
            lambda lst: "|".join(
                sorted({str(t) for t in lst if pd.notna(t)})
            ) if isinstance(lst, (list, tuple)) else ""
        )
        .astype("string")
    )

    # Create one boolean column per distinct type (wide format)
    all_types = sorted({
        t
        for lst in ev["types"]
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
        ev[col] = ev["types"].apply(
            lambda lst, val=t: isinstance(lst, (list, tuple)) and (val in lst)
        )

    # Minimal benchmark schema + compatibility columns
    out = ev.copy()
    out["is_event"]        = True
    out["event_group"]     = "Incident"
    out["threshold_event"] = np.nan   # will be filled by add_incident_thresholds
    out["event_direction"] = pd.NA

    # cast for consistency
    out["resident_id"] = out["resident_id"].astype("string")
    out["community"]   = out["community"].astype("string")

    # Core columns used by the benchmark code
    core_cols = [
        "resident_id", "community", "dates_recorded",
        "is_event", "date_diff",
        "event_group", "subtype", "threshold_event", "event_direction",
    ]
    helper_cols = ["types"] + type_cols  # keep the raw list + flag columns

    cols = [c for c in core_cols + helper_cols if c in out.columns]
    out = out[cols]

    return out
