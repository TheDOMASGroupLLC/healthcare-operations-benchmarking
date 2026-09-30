# Healthcare Operations Benchmarking

A Python analysis workflow for standardizing operational weight and incident data, calculating community benchmarks, and comparing reporting periods.

## Overview

The analysis covers two operational areas:

- weight monitoring and clinically meaningful weight-change events;
- fall-related incidents and repeat-fall patterns.

The workflow standardizes source records, applies defined event rules, calculates community and overall metrics, and writes benchmark tables and comparison charts.

## Repository layout

```text
analysis/
case-study/
data/
requirements.txt
README.md
```

## Input data

Place the source workbook in:

```text
data/raw/
```

The workbook is expected to contain `Weight` and `Incidents` sheets with the fields referenced by the preprocessing modules.

Raw resident-level data are not included in this repository.

## Weight processing

Weight records are normalized before benchmark calculation. The workflow:

- converts recorded values to a consistent long format;
- keeps one weight per resident per day;
- limits weights to the configured valid range;
- calculates measurement intervals and percent change;
- identifies threshold events using prior observations within the configured time windows; and
- creates a single event signal for downstream benchmarking.

## Incident processing

Incident records are grouped to one event per resident, community, and timestamp. Fall and on-floor incident types are treated as fall events for the benchmark analysis.

The pipeline also calculates time between fall events and a severity score based on injury, hospitalization, and medical-emergency indicators.

## Benchmarks

Weight metrics include:

- percent of residents with at least one weight-change event;
- events per 100 residents;
- median days between weigh-ins;
- percent of residents with monitoring intervals greater than 30 days.

Fall metrics include:

- percent of fallers with a repeat fall within 30 days;
- falls per 100 residents;
- median days between falls.

## Running

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python analysis/benchmark_main.py
```

On Windows, activate with `.venv\Scripts\activate`.

Outputs are written to:

```text
data/processed/
```

## Case study materials

Supporting materials are available in `case-study/`:

- `Healthcare_Operations_Benchmarking_One_Page_Summary.pdf`
- `Healthcare_Operations_Benchmarking_Case_Study.pdf`

## Notes

The runnable pipeline implements the weight and fall benchmark measures described above. The accompanying case study also discusses exploratory analytic extensions that are not part of the public pipeline.

No raw resident-level or personally identifiable data are included. This repository documents an analytics workflow and is not clinical guidance.
