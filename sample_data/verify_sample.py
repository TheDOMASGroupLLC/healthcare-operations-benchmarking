from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

import benchmark_main
import config
import loader
from adapters import incidents_to_benchmark
from weight_preprocessing import analysis_prep as weights_prep


def assert_close(actual, expected, label, tol=1e-9):
    if not np.isclose(float(actual), float(expected), atol=tol, rtol=0):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def main():
    sample_dir = Path(__file__).resolve().parent
    workbook = sample_dir / "healthcare_operations_synthetic.xlsx"
    expected = pd.read_csv(sample_dir / "expected_metrics.csv").set_index("metric")["expected_value"]

    sheets = pd.read_excel(workbook, sheet_name=None)

    prepared_weights = weights_prep(sheets["Weight"])
    event_count = int(prepared_weights["is_event"].sum())
    assert event_count == int(float(expected["weight_event_rows"]))

    same_day = prepared_weights[
        (prepared_weights["resident_id"] == "W001")
        & (prepared_weights["dates_recorded"].dt.date == pd.Timestamp("2026-04-10").date())
    ]
    assert len(same_day) == 1
    assert_close(
        same_day.iloc[0]["weight_lbs"],
        expected["latest_same_day_weight_W001_2026-04-10"],
        "latest same-day weight",
    )

    incidents = incidents_to_benchmark(sheets["Incidents"])
    falls = incidents[incidents["is_fall"]].copy()
    assert len(falls) == int(float(expected["total_falls"]))
    assert incidents["resident_id"].nunique() == int(float(expected["unique_incident_residents"]))

    gap_by_resident = (
        falls.dropna(subset=["fall_date_diff"])
        .groupby("resident_id")["fall_date_diff"]
        .min()
    )
    repeat_count = int((gap_by_resident <= 30).sum())
    assert repeat_count == int(float(expected["repeat_faller_count"]))

    faller_count = falls["resident_id"].nunique()
    repeat_pct = repeat_count / faller_count * 100
    assert_close(repeat_pct, expected["pct_repeat_fallers_lt30"], "repeat faller percent")

    falls_per_100 = len(falls) / incidents["resident_id"].nunique() * 100
    assert_close(falls_per_100, expected["falls_per_100_residents"], "falls per 100 residents")

    med_gap_by_resident = (
        falls.sort_values(["resident_id", "dates_recorded"])
        .groupby("resident_id")["dates_recorded"]
        .apply(lambda s: s.diff().dt.days.median())
    )
    assert_close(
        med_gap_by_resident.median(),
        expected["median_days_between_falls"],
        "median days between falls",
    )

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        raw_dir = sandbox / "data" / "raw"
        processed_dir = sandbox / "data" / "processed"
        raw_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        shutil.copy2(workbook, raw_dir / workbook.name)

        config.RAW_DIR = raw_dir
        config.PROCESSED_DIR = processed_dir
        loader.RAW_DIR = raw_dir
        loader.PROCESSED_DIR = processed_dir
        benchmark_main.PROCESSED_DIR = processed_dir

        benchmark_main.main()

        validations = list(processed_dir.glob("incident_validation_*.csv"))
        assert len(validations) == 1
        validation = pd.read_csv(validations[0]).iloc[0]
        assert_close(validation["falls_per_100_residents"], expected["falls_per_100_residents"], "validation falls per 100")
        assert_close(validation["pct_repeat_falls_lt30"], expected["pct_repeat_fallers_lt30"], "validation repeat fall percent")
        assert_close(validation["median_days_between_falls"], expected["median_days_between_falls"], "validation median fall interval")

        weight_charts = list((processed_dir / "benchmarks" / "weights_comparisons").glob("*.png"))
        incident_charts = list((processed_dir / "benchmarks" / "incidents_comparisons").glob("*.png"))
        assert len(weight_charts) == 4
        assert len(incident_charts) == 3

    print("Synthetic benchmarking sample passed.")
    print("Verified 5 weight events, 9 falls, 50% repeat fallers, 225 falls/100 residents, median fall interval 52 days, and 7 comparison charts.")


if __name__ == "__main__":
    main()
