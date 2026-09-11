# Healthcare Operations Benchmarking & Risk Monitoring

A healthcare analytics case study demonstrating how operational event data can be cleaned, standardized, benchmarked, and translated into decision-support insights across multiple communities.

> **Portfolio note:** This work was originally completed as a time-bounded analytics exercise. It is shared to demonstrate analytical approach, data-processing logic, quality checks, benchmark design, and communication of findings. No raw resident-level data are included in this repository.

## Objective

The analysis was designed to:

- provide actionable insights and flag communities needing closer observation;
- establish analytic benchmarks and hypotheses for ongoing risk monitoring and improvement; and
- create consistent business rules for comparing weight-monitoring and fall-related patterns across communities.

## Data analyzed

The case study covered Q1–Q2 2024 and included:

- **Weights:** 2,108 measurement events across 294 residents and 30 communities
- **Falls/incidents:** 968 events across 295 residents and 30 communities

Only aggregated results and analysis code are included here. Source data are omitted.

## Analytical approach

### 1. Standardize and validate source data

The workflow applies explicit business rules before calculating benchmarks, including:

- treating each valid weight record as one measurement per resident per day;
- excluding implausible weights below 70 lbs or above 450 lbs;
- retaining the most recent measurement when multiple weights occur on the same day;
- identifying clinically meaningful weight-change events using ±5% and ±10% thresholds across defined time windows;
- collapsing incident records to one event per resident/community/timestamp;
- isolating fall-related events with a standardized fall flag; and
- calculating event intervals at the resident level before aggregation.

### 2. Create normalized operational benchmarks

Weight-monitoring benchmarks include:

- percent of residents with at least one weight-change event;
- weight-change events per 100 residents;
- median days between weigh-ins; and
- percent of residents with more than 30 days between weigh-ins.

Fall-related benchmarks include:

- percent of residents with a repeat fall within 30 days;
- falls per 100 residents; and
- median days between falls.

### 3. Compare communities and reporting periods

The analysis generates community-level summaries and Q1-to-Q2 comparisons to identify changes in monitoring cadence, event frequency, repeat-fall risk, and other patterns that may warrant follow-up.

### 4. Translate findings into decision support

The final case study prioritizes communities showing multiple risk signals and proposes additional hypotheses for future analysis, including missingness/under-detection, staffing or process changes, seasonality, and resident case-mix.

## Repository structure

```text
healthcare-operations-benchmarking/
├── analysis/
│   ├── adapters.py
│   ├── benchmark_main.py
│   ├── benchmark_metrics.py
│   ├── config.py
│   ├── helpers.py
│   ├── incidents_preprocessing.py
│   ├── loader.py
│   └── weight_preprocessing.py
├── case-study/
│   └── Healthcare_Operations_Benchmarking_Case_Study.pptx
├── data/
│   ├── README.md
│   ├── raw/
│   └── processed/
├── .gitignore
├── README.md
└── requirements.txt
```

## Technical workflow

```text
Source workbook
      ↓
Input loading and file checks
      ↓
Weight + incident preprocessing
      ↓
Standardized event schemas
      ↓
Business-rule application
      ↓
Community benchmarks
      ↓
Quarter-over-quarter comparisons
      ↓
Validation outputs + visualizations
      ↓
Operational recommendations
```

## Running the analysis

Create and activate a Python virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Place the source Excel workbook in:

```text
data/raw/
```

The workflow expects a workbook with `Weight` and `Incidents` sheets. Then run:

```bash
python analysis/benchmark_main.py
```

Outputs are written to `data/processed/`.

## Tools

- Python
- pandas
- NumPy
- Matplotlib
- Excel/OpenPyXL

## Selected findings

The analysis found evidence of changing monitoring and incident patterns across communities between Q1 and Q2, including longer weigh-in intervals in many communities, increases in weight-change event frequency, and meaningful variation in repeat-fall patterns. The case study presentation documents the benchmark definitions, findings, recommendations, and proposed next analyses.

## Case study presentation

See [`case-study/Healthcare_Operations_Benchmarking_Case_Study.pptx`](case-study/Healthcare_Operations_Benchmarking_Case_Study.pptx) for the full presentation.

## Privacy and use

No raw resident-level or personally identifiable data are included. This repository is intended as a professional portfolio sample demonstrating analytics and data-workflow design; the analysis should not be interpreted as clinical guidance.
