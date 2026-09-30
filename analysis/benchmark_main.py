from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from adapters import incidents_to_benchmark, weights_to_benchmark
from config import PROCESSED_DIR
from loader import all_sheets
from benchmark_metrics import (
    community_snapshot,
    weekly_event_rates,
    create_quarter_comparison_visuals,
    create_benchmark_summary_and_visuals
)


def validate_incident_metrics(df_std: pd.DataFrame, out_dir: Path, timestamp: str) -> None:
    """Write a validation summary for the fall metrics used by the benchmark pipeline."""
    incidents = df_std.copy()

    if "is_fall" not in incidents.columns:
        raise ValueError("validate_incident_metrics expects an 'is_fall' column in df_std.")

    falls = incidents[incidents["is_fall"]].copy()
    total_falls = len(falls)
    unique_residents = incidents["resident_id"].nunique()

    if total_falls == 0 or unique_residents == 0:
        out = pd.DataFrame([{
            "pct_repeat_falls_lt30": np.nan,
            "falls_per_100_residents": np.nan,
            "median_days_between_falls": np.nan,
            "total_falls": total_falls,
            "unique_residents": unique_residents,
            "repeat_resident_count": 0,
        }])
    else:
        if "fall_date_diff" not in falls.columns:
            raise ValueError("validate_incident_metrics expects 'fall_date_diff' for falls.")

        valid_fall_gaps = falls.dropna(subset=["fall_date_diff"]).copy()

        gap_by_resident = (valid_fall_gaps
                           .groupby("resident_id")["fall_date_diff"]
                           .min())

        fallers = gap_by_resident.index  # residents with ≥1 fall (with a computable gap)
        repeat_residents = gap_by_resident[gap_by_resident <= 30].index

        fallers_with_events = len(fallers)
        repeat_faller_count = len(repeat_residents)

        repeat_fall_pct = (repeat_faller_count / fallers_with_events * 100.0) if fallers_with_events > 0 else np.nan

        falls_per_100 = (total_falls / unique_residents * 100.0) if unique_residents > 0 else np.nan

        falls = falls.sort_values(["resident_id", "dates_recorded"])
        med_gap_by_resident = (falls
                               .groupby("resident_id")["dates_recorded"]
                               .apply(lambda s: s.diff().dt.days.median()))
        median_days_between_falls = med_gap_by_resident.median()

        out = pd.DataFrame([{
            "pct_repeat_falls_lt30": repeat_fall_pct,
            "falls_per_100_residents": falls_per_100,
            "median_days_between_falls": median_days_between_falls,
            "total_falls": total_falls,
            "unique_residents": unique_residents,
            "repeat_resident_count": repeat_faller_count,
        }])

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"incident_validation_{timestamp}.csv"
    out.to_csv(csv_path, index=False)


def run_block(df_std: pd.DataFrame, label: str, ts: str):
    (PROCESSED_DIR / f"{label.lower()}_{ts}.csv").write_text(df_std.to_csv(index=False))

    desc_path = PROCESSED_DIR / f"{label.lower()}_{ts}_describe.csv"

    df_std.describe(include="all").to_csv(desc_path)

    print(f"Wrote descriptive summary: {desc_path}")

    comm = community_snapshot(df_std)
    (PROCESSED_DIR / f"{label.lower()}_comms_kpi_{ts}.csv").write_text(comm.to_csv(index=False))
    weekly = weekly_event_rates(df_std)
    (PROCESSED_DIR / f"{label.lower()}_weekly_rates_{ts}.csv").write_text(weekly.to_csv(index=False))
    quarterly = df_std.assign(quarter=df_std["dates_recorded"].dt.to_period("Q").astype(str))
    quarters = sorted(quarterly["quarter"].dropna().unique())
    if len(quarters) >= 2:
        cmp_cols = ["community", "resident_id", "date_diff", "is_event", "quarter"]

        if "is_fall" in quarterly.columns:
            cmp_cols.append("is_fall")
        if "fall_date_diff" in quarterly.columns:
            cmp_cols.append("fall_date_diff")

        create_benchmark_summary_and_visuals(
            weights_df=df_std,
            out_dir=PROCESSED_DIR / "benchmarks" / label.lower(),
            timestamp=ts,
            timeframe_label=""
        )

        comparison_df = quarterly[cmp_cols]

        if label.lower() == "incidents":
            out_dir = PROCESSED_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            validate_incident_metrics(df_std, out_dir, ts)

        create_quarter_comparison_visuals(
            df_all=comparison_df, qA=quarters[0], qB=quarters[1],
            out_dir=PROCESSED_DIR / "benchmarks" / f"{label}_comparisons",
            timestamp=ts
        )



def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    weight_data = weights_to_benchmark(all_sheets["Weight"])
    incident_data = incidents_to_benchmark(all_sheets["Incidents"])
    run_block(weight_data, "Weights", ts)
    run_block(incident_data, "Incidents", ts)
    combined_data = pd.concat([weight_data, incident_data], ignore_index=True)
    (PROCESSED_DIR / f"combined_{ts}.csv").write_text(combined_data.to_csv(index=False))


if __name__ == "__main__":
    main()
