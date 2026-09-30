# Synthetic Sample Data

This workbook is entirely fictional and is included so the public analysis can be exercised without access to any original project data.

## Files

- `healthcare_operations_synthetic.xlsx` — synthetic `Weight` and `Incidents` sheets
- `expected_metrics.csv` — selected known results used by the automated verifier
- `verify_sample.py` — runs the analysis in a temporary data sandbox and checks the results

The sample intentionally includes two reporting quarters, same-day duplicate weights, 30-day and 180-day weight-change events, fall and non-fall incident types, same-timestamp incident rows, and repeat falls.

## Run the sample

From the repository root:

```bash
python sample_data/verify_sample.py
```

The verifier runs the actual benchmark entry point against temporary `data/raw` and `data/processed` directories. It checks selected known metrics and confirms all expected quarter-comparison charts are produced.

To run the workbook manually, copy `healthcare_operations_synthetic.xlsx` into `data/raw/` as the only `.xlsx` file and run:

```bash
python analysis/benchmark_main.py
```

All identifiers, organizations, communities, and measurements in this directory are synthetic.
