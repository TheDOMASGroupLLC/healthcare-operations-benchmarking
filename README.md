# Healthcare Operations Benchmarking & Risk Monitoring

## Analytics & Decision Support Case Study

A healthcare analytics case study demonstrating how operational event data can be cleaned, standardized, benchmarked, and translated into decision-support insights across multiple communities.

> **Portfolio note:** This work was originally completed as a time-bounded analytics exercise. It is shared to demonstrate DOMAS's approach to data validation, explicit business rules, benchmark design, risk monitoring, and communication of findings. No raw resident-level data are included.

## What this example demonstrates for clients

This case study shows how DOMAS can take operational data that require substantial validation and rule definition, create consistent measures across reporting periods, identify patterns that warrant follow-up, and translate the results into practical decision support.

It is best understood as an **analytics and decision-support example**, distinct from the custom data tool example in the Enrollment & Outpatient Visit Processing repository.

## Portfolio materials

Start with the one-page summary, then open the full case study for benchmark definitions, sanitized visuals, recommendations, and analytic follow-up opportunities.

- [`One-page summary (PDF)`](case-study/Healthcare_Operations_Benchmarking_One_Page_Summary.pdf)
- [`Full case study (PDF)`](case-study/Healthcare_Operations_Benchmarking_Case_Study.pdf)
- [`Presentation (PowerPoint)`](case-study/Healthcare_Operations_Benchmarking_Case_Study.pptx)

The [`case-study/`](case-study/) folder contains the complete set of public portfolio materials.

## Objective

The analysis was designed to:

- provide actionable insights and flag communities needing closer observation;
- establish analytic benchmarks and hypotheses for ongoing risk monitoring and improvement; and
- create consistent business rules for comparing weight-monitoring and fall-related patterns across communities.

## Data analyzed

The case study uses anonymized operational data from two reporting periods across multiple communities, including longitudinal weight-monitoring records and fall/incident records.

Only aggregated results, analysis code, and sanitized presentation materials are included here. Source data are omitted.

## Analytical approach

### 1. Standardize and validate source data

The workflow applies explicit business rules before calculating benchmarks, including:

- treating each valid weight record as one measurement per resident per day;
- excluding clinically implausible weight values;
- retaining the most recent measurement when multiple weights occur on the same day;
- identifying clinically meaningful weight-change events using defined threshold rules across defined time windows;
- collapsing incident records to one event per resident/community/timestamp;
- isolating fall-related events with a standardized fall flag; and
- calculating event intervals at the resident level before aggregation.

### 2. Create normalized operational benchmarks

Weight-monitoring benchmarks include:

- percent of residents with at least one weight-change event;
- weight-change events per standardized resident count;
- median days between weigh-ins; and
- percent of residents exceeding the expected monitoring interval.

Fall-related benchmarks include:

- percent of residents with a repeat fall within a defined follow-up window;
- falls per standardized resident count; and
- median days between falls.

### 3. Compare communities and reporting periods

The analysis generates community-level summaries and reporting-period comparisons to identify changes in monitoring cadence, event frequency, repeat-fall risk, and other patterns that may warrant follow-up.

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
│   ├── Healthcare_Operations_Benchmarking_One_Page_Summary.pdf
│   ├── Healthcare_Operations_Benchmarking_Case_Study.pdf
│   ├── Healthcare_Operations_Benchmarking_Case_Study.pptx
│   └── README.md
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
Period-over-period comparisons
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

The workflow expects a workbook with weight and incident data sheets. Then run:

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

The analysis found evidence of changing monitoring and incident patterns across communities, including longer weigh-in intervals in many communities, increases in weight-change event frequency, and meaningful variation in repeat-fall patterns. The case study presentation documents the benchmark definitions, findings, recommendations, and proposed next analyses.

## Privacy and use

No raw resident-level or personally identifiable data are included. This repository is intended as a professional portfolio sample demonstrating analytics and data-workflow design; the analysis should not be interpreted as clinical guidance.
