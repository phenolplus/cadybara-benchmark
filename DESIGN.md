# Design: Cadybara API Experiment Research Framework (Bootstrap Version)

Version: 0.1  
Status: Bootstrap / MVP  
Target audience: Coding agents and developers  
Goal: Define the minimum architecture necessary to run Cadybara API experiments, collect outputs, analyze results, and publish selected experiment data.

---

# 1. Purpose

This project provides a research workspace for running query-based benchmark experiments against the Cadybara API and studying the generated STL outputs.

Terminology note: this document uses `query` as the standard term for text submitted to the Cadybara API. In this project, `prompt` and `query` are interchangeable words.

The system supports three core activities:

1. Experiment setup

An experimenter defines an experiment, identifies a list of queries, chooses one or more Cadybara models and parameter sets, and chooses the analysis metrics that should be applied to the collected outputs.

2. Output collection and analysis

The backend executes each query against the Cadybara API for the configured model and parameter combinations, stores the raw response and returned STL files, and invokes reusable analysis modules to compute scores, metrics, statistics, and reports.

3. Publication of selected experiments

The experimenter selects useful runs to publish. Published runs are exported from the active workspace into explicit, stable files that are checked into source control.

This bootstrap version focuses on creating:

- experiment setup workflow
- query datasets
- experiment run execution
- query, parameter, STL, score, and artifact storage
- analysis modules
- visualization workspace
- published experiment files

External production concerns are intentionally out of scope.

---

# 1.1 Target Workflow

The intended workflow is:

1. The experimenter identifies a list of queries. Each query may specify a model, or omit it to use the experiment default model.

2. The experimenter submits those queries to the Cadybara API using the model associated with each query and the configured parameter set. One run executes all query lines in the experiment.

3. Cadybara returns one or more STL files for each query in the run.

4. The returned STLs are scored. The query, model, parameters, STL file paths, raw response, and score are stored locally.

5. The experimenter selects specific runs to publish. Each selected run is saved explicitly into this project as files under `published/runs/`.

6. The website frontend displays a list of published runs on the `/published` page.

---

# 2. High-Level Architecture

```text
Frontend UI
    ↓

Backend API / Experiment Runner
    ↓

Cadybara API Client
    ↓

Python Analysis Modules
    ↓

Experiment YAML Files + Run File Store
    ↓

Published Experiment Files
```

---

# 3. Components

## Frontend

Purpose:

Research workspace UI.

Responsibilities:

- list experiments
- create experiments
- configure experiment setup
- inspect queries
- view raw outputs and returned STLs
- view metrics, reports, and comparisons
- publish selected runs

Suggested implementation:

```text
React + TypeScript
```

Minimum pages:

```text
/experiments

/experiment/:id

/published
```

The `/published` page displays the list of published runs.

---

## Backend

Purpose:

Experiment orchestration and API layer.

Responsibilities:

- experiment CRUD
- query dataset management
- experiment execution
- Cadybara API invocation across configured models and parameters
- experiment YAML file access
- run/result file access
- STL and artifact storage
- invoke analysis modules
- publish selected runs

Suggested implementation:

```text
FastAPI
```

---

## Cadybara API Client

Purpose:

Provide a small, testable integration layer for calls to the Cadybara API.

Responsibilities:

- accept a query, model, and parameter snapshot
- call the Cadybara API
- normalize response metadata
- persist raw response payloads
- record returned STL and generated artifact references
- surface API errors in a stable format

Must NOT depend on frontend.

---

## Analysis Modules

Purpose:

Reusable Python modules for analysis and calculations.

Must support:

1. Backend use

```python
from analysis.metrics import score
```

2. CLI use

```bash
cadybara-benchmark score experiment_001
```

Responsibilities:

- output parsing
- STL inspection
- artifact inspection
- scoring
- statistics
- reporting
- publication summaries

Must NOT depend on frontend.

---

## CLI Wrapper

Purpose:

Provide command line access to experiment setup, execution, analysis modules, YAML experiment definitions, and run/result file operations.

Suggested implementation:

```text
Typer
```

Examples:

```bash
cadybara-benchmark create-experiment

cadybara-benchmark add-query EXP001

cadybara-benchmark add-query EXP001 --model google/gemini-3-flash-preview

cadybara-benchmark run EXP001

cadybara-benchmark analyze EXP001

cadybara-benchmark publish EXP001
```

---

## Experiment Definition Files

Purpose:

Store experiment definitions as human-readable files.

Implementation:

```text
YAML
```

Default path:

```text
workspace/experiments/{experiment_id}.yaml
```

Notes:

- local only
- one file per experiment
- source of truth for experiment metadata, setup, and queries
- editable by hand when useful
- no database required for experiment setup or query dataset management

---

## Run File Store

Purpose:

Store execution bookkeeping and analysis results for active local runs.

Implementation:

```text
JSON files under workspace/artifacts/
```

Default path:

```text
workspace/artifacts/{experiment_id}/{run_id}/summary.json
```

Notes:

- local only
- one summary file per run plus per-query detail subfolders
- stores run status, API result metadata, scores, and artifact references
- does not store experiment definitions or query text beyond run snapshots
- can be regenerated by rerunning experiments from YAML definitions

---

## Published Experiment Data

Purpose:

Store selected experiment outputs permanently.

Requirements:

- checked into source control
- human-readable
- stable format
- independent of active workspace run files
- include enough metadata to reproduce the experiment setup

Suggested format:

```text
JSON
```

Directory:

```text
published/
```

Example:

```text
published/

    hole_pattern_baseline.json

    bracket_query_comparison.json
```

---

# 4. Repository Structure

```text
./

├── frontend/

├── backend/

├── analysis/
│
│   ├── artifacts/
│   │
│   ├── metrics/
│   │
│   ├── scoring/
│   │
│   └── reporting/

├── cli/

├── workspace/
│
│   ├── experiments/
│   │
│   │   └── EXP001.yaml
│   │
│   ├── responses/
│   │
│   ├── generated/
│   │
│   ├── reports/
│   │
│   └── artifacts/

├── published/

├── scripts/

└── tests/
```

---

# 5. Core Data Model

---

## Experiment

Represents a research study. Each experiment is stored as one YAML file under `workspace/experiments/`.

Fields:

```text
id

name

description

type

status

setup

created_at

updated_at

queries
```

Example:

```yaml
id: "EXP001"
name: "Bracket Query Comparison"
description: ""
type: "query_comparison"
status: "draft"
setup:
  model: "default"
  response_mode: "json"
  linear_deflection: 0.1
  angular_deflection: 0.1
created_at: "2026-06-05T12:00:00Z"
updated_at: "2026-06-05T12:00:00Z"
queries:
  - id: "Q001"
    text: "Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes."
    model: "google/gemini-3-flash-preview"
    category: "mechanical"
    metadata: {}
```

`setup.model` is the experiment default. A query with an empty `model` value uses that default; a query with a non-empty `model` value uses its own model for execution.

---

## Query

Represents a user-identified query line within an experiment. Queries are nested in the experiment YAML file and remain independent from model and parameter choices so the same query can be run against multiple configurations.

Runs store per-query snapshots in `summary.json` and detail artifacts in query subfolders.

Fields:

```text
id

text

model

category

metadata
```

Example:

```yaml
- id: "Q001"
  text: "Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes."
  model: "google/gemini-3-flash-preview"
  category: "mechanical"
  metadata: {}
```

---

## Run

Represents one execution of all query lines within an experiment against the Cadybara API with a specific parameter snapshot.

Fields:

```text
id

experiment_id

status

started_at

finished_at

parameters

queries

summary
```

Each entry in `queries` stores:

```text
query_id

text

model

status

error

artifact_dir

response_metadata

score

metrics
```

`response_metadata.latency_ms` records benchmark-client HTTP round-trip time in milliseconds: from when the request is sent to the Cadybara API until the full HTTP response body is received. This is distinct from API-reported `metrics.latency` (agent latency in seconds from the Cadybara server).

---

## Result

Per-query output from a run is stored in the run summary and in query subfolders under the run directory.

Detail files per query:

```text
model.stl

response.json

generated_code.py

error.json
```

Example summary excerpt:

```json
{
    "id":"RUN001",
    "experiment_id":"EXP001",
    "status":"completed",
    "parameters":{
        "response_mode":"json",
        "linear_deflection":0.1,
        "angular_deflection":0.1
    },
    "queries":[
        {
            "query_id":"Q001",
            "text":"Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes.",
            "model":"google/gemini-3-flash-preview",
            "status":"completed",
            "artifact_dir":"workspace/artifacts/EXP001/RUN001/Q001",
            "score":0.88,
            "metrics":{
                "dimension_score":0.92,
                "constraint_score":0.81,
                "overall":0.88
            }
        }
    ],
    "summary":{
        "completed":1,
        "failed":0
    }
}
```

---

# 6. Run File Layout

Experiment definitions and queries are stored in YAML files, not run files. The minimum run file layout stores execution records and result data:

```text
workspace/artifacts/{experiment_id}/{run_id}/summary.json
workspace/artifacts/{experiment_id}/{run_id}/{query_id}/model.stl
workspace/artifacts/{experiment_id}/{run_id}/{query_id}/response.json
```

JSON fields stored as text in `summary.json`.

---

# 7. Analysis Module Interfaces

Analysis modules must be importable and CLI-usable.

---

## Output Parsing

```python
parse_output(
    raw_output
) -> dict
```

---

## Artifact Inspection

```python
inspect_artifacts(
    artifact_paths:list[str]
) -> dict
```

---

## Scoring

```python
score_result(
    query,
    output,
    artifacts
)
```

Returns:

```python
{
    "dimension_score":0.95,
    "constraint_score":0.83,
    "overall":0.90
}
```

---

## Reporting

```python
generate_report(
    experiment_id
)
```

Returns:

```python
{
    "summary":{},
    "charts":[],
    "statistics":[]
}
```

---

# 8. Backend API

Minimum endpoints:

---

Experiments

```text
GET /experiments

POST /experiments

GET /experiments/{id}
```

---

Queries

```text
GET /experiments/{id}/queries

POST /experiments/{id}/queries
```

---

Execution

```text
POST /experiments/{id}/run
```

Runs the configured query list against the Cadybara API as one run.

---

Results

```text
GET /experiments/{id}/results
```

---

Analysis

```text
POST /experiments/{id}/analyze
```

---

Publishing

```text
POST /experiments/{id}/publish-runs
```

Writes:

```text
published/runs/{run_id}.json
```

---

# 9. Published File Format

Each published file represents one selected run containing all completed query results. The file should include the query snapshots, models, parameters, returned STL paths or copied STL files, scores, metrics, and enough experiment metadata to understand where the run came from.

Example:

```json
{
    "experiment_id":"EXP001",

    "experiment":"Bracket Query Comparison",

    "run_id":"RUN001",

    "published_at":"2026-05-17T12:00:00Z",

    "parameters":{
        "response_mode":"json",
        "linear_deflection":0.1,
        "angular_deflection":0.1
    },

    "queries":[
        {
            "query_id":"Q001",
            "text":"Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes.",
            "model":"google/gemini-3-flash-preview",
            "stl_paths":[
                "published/runs/RUN001/Q001/model.stl"
            ],
            "score":0.88,
            "metrics":{
                "dimension_score":0.92,
                "constraint_score":0.81,
                "overall":0.88
            }
        }
    ]
}
```

---

# 10. Bootstrap Scope Constraints

Must include:

✓ YAML experiment definition files

✓ run file storage

✓ backend experiment setup and execution

✓ Cadybara API client layer

✓ reusable analysis modules

✓ CLI wrapper

✓ frontend workspace

✓ published experiment files

---

Must NOT include:

✗ distributed systems

✗ authentication

✗ cloud storage

✗ queues

✗ production deployment concerns

---

# 11. First Working Milestone

Success condition:

User can:

1.

```bash
cadybara-benchmark create-experiment
```

2.

```bash
cadybara-benchmark add-query EXP001
```

3.

```bash
cadybara-benchmark run EXP001
```

4.

```bash
cadybara-benchmark analyze EXP001
```

5.

Open UI:

```text
localhost:3000
```

6.

View:

- query list
- raw outputs
- returned STLs
- results
- metrics

7.

```bash
cadybara-benchmark publish EXP001
```

Produces:

```text
published/runs/bracket_query_comparison_run_001.json
```

This is considered the minimum viable implementation.
