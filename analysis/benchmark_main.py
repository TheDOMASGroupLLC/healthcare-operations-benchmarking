# benchmarks_main.py
from datetime import datetime
from loader import all_sheets
from config import PROCESSED_DIR
from adapters import weights_to_benchmark, incidents_to_benchmark
from benchmark_metrics import (
    community_snapshot,
    weekly_event_rates,
    create_quarter_comparison_visuals,
    create_benchmark_summary_and_visuals
)

from pathlib import Path
import numpy as np
import pandas as pd

def validate_incident_metrics(df_std: pd.DataFrame, out_dir: Path, timestamp: str) -> None:
    """
    Sanity-check metrics for FALLS ONLY, to line up conceptually with the main
    benchmark pipeline (where is_event == is_fall for incidents).

    Outputs a single-row CSV with:
      - pct_repeat_falls_lt30: % of fallers who have a repeat fall within 30 days
      - falls_per_100_residents: falls per 100 residents (global)
      - median_days_between_falls: resident-median gap, then global median
      - total_falls: total count of falls
      - unique_residents: total number of unique residents in the incidents df
      - repeat_resident_count: number of residents with repeat fall < 30 days
    """
    d = df_std.copy()

    # Restrict strictly to falls
    if "is_fall" not in d.columns:
        raise ValueError("validate_incident_metrics expects an 'is_fall' column in df_std.")

    falls = d[d["is_fall"]].copy()
    total_falls = len(falls)
    unique_residents = d["resident_id"].nunique()

    # Handle degenerate cases gracefully
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
        #  % of fallers with a repeat fall within 30 days
        if "fall_date_diff" not in falls.columns:
            raise ValueError("validate_incident_metrics expects 'fall_date_diff' for falls.")

        valid_gaps = falls.dropna(subset=["fall_date_diff"]).copy()

        # min gap between falls per resident
        gap_by_resident = (valid_gaps
                           .groupby("resident_id")["fall_date_diff"]
                           .min())

        fallers = gap_by_resident.index  # residents with ≥1 fall (with a computable gap)
        repeat_residents = gap_by_resident[gap_by_resident <= 30].index

        num_fallers = len(fallers)
        num_repeat = len(repeat_residents)

        pct_repeat = (num_repeat / num_fallers * 100.0) if num_fallers > 0 else np.nan

        # Falls per 100 residents (global)
        falls_per_100 = (total_falls / unique_residents * 100.0) if unique_residents > 0 else np.nan

        # Median days between falls (resident-median → global median)
        falls = falls.sort_values(["resident_id", "dates_recorded"])
        med_gap_by_resident = (falls
                               .groupby("resident_id")["dates_recorded"]
                               .apply(lambda s: s.diff().dt.days.median()))
        median_days_between_falls = med_gap_by_resident.median()

        out = pd.DataFrame([{
            "pct_repeat_falls_lt30": pct_repeat,
            "falls_per_100_residents": falls_per_100,
            "median_days_between_falls": median_days_between_falls,
            "total_falls": total_falls,
            "unique_residents": unique_residents,
            "repeat_resident_count": num_repeat,
        }])

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"incident_validation_{timestamp}.csv"
    out.to_csv(csv_path, index=False)


def run_block(df_std: pd.DataFrame, label: str, ts: str):
    (PROCESSED_DIR / f"{label.lower()}_{ts}.csv").write_text(df_std.to_csv(index=False))

    desc_path = PROCESSED_DIR / f"{label.lower()}_{ts}_describe.csv"

    # numeric + categorical columns
    df_std.describe(include="all").to_csv(desc_path)

    print(f"[describe] Wrote summary → {desc_path}")

    comm = community_snapshot(df_std)
    (PROCESSED_DIR / f"{label.lower()}_comms_kpi_{ts}.csv").write_text(comm.to_csv(index=False))
    weekly = weekly_event_rates(df_std)
    (PROCESSED_DIR / f"{label.lower()}_weekly_rates_{ts}.csv").write_text(weekly.to_csv(index=False))
    # quarters (optional)
    dfq = df_std.assign(quarter=df_std["dates_recorded"].dt.to_period("Q").astype(str))
    q = sorted(dfq["quarter"].dropna().unique())
    dfq = df_std.assign(quarter=df_std["dates_recorded"].dt.to_period("Q").astype(str))
    q = sorted(dfq["quarter"].dropna().unique())
    if len(q) >= 2:
        # start from the core columns
        cmp_cols = ["community", "resident_id", "date_diff", "is_event", "quarter"]

        # add falls-specific columns if present (Incidents block)
        if "is_fall" in dfq.columns:
            cmp_cols.append("is_fall")
        if "fall_date_diff" in dfq.columns:
            cmp_cols.append("fall_date_diff")

        create_benchmark_summary_and_visuals(
            weights_df=df_std,
            out_dir=PROCESSED_DIR / "benchmarks" / label.lower(),
            timestamp=ts,
            timeframe_label=""
        )

        cmp_df = dfq[cmp_cols]

        if label.lower() == "incidents":
            out_dir = PROCESSED_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            validate_incident_metrics(df_std, out_dir, ts)

        create_quarter_comparison_visuals(
            df_all=cmp_df, qA=q[0], qB=q[1],
            out_dir=PROCESSED_DIR / "benchmarks" / f"{label}_comparisons",
            timestamp=ts
        )



def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    w_std = weights_to_benchmark(all_sheets["Weight"])
    i_std = incidents_to_benchmark(all_sheets["Incidents"])
    run_block(w_std, "Weights", ts)
    run_block(i_std, "Incidents", ts)
    both = pd.concat([w_std, i_std], ignore_index=True)
    (PROCESSED_DIR / f"combined_{ts}.csv").write_text(both.to_csv(index=False))


if __name__ == "__main__":
    main()
