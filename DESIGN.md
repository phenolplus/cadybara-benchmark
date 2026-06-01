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

1. The experimenter identifies a list of queries.

2. The experimenter submits those queries to the Cadybara API using either one shared model and parameter set or several model and parameter combinations. Each query plus model plus parameter execution is a run.

3. Cadybara returns one or more STL files for each run.

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

SQLite Database
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
- database access
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

Provide command line access to experiment setup, execution, analysis modules, and database operations.

Suggested implementation:

```text
Typer
```

Examples:

```bash
cadybara-benchmark create-experiment

cadybara-benchmark add-query EXP001

cadybara-benchmark run EXP001

cadybara-benchmark analyze EXP001

cadybara-benchmark publish EXP001
```

---

## Database

Purpose:

Store active experiment state.

Implementation:

```text
SQLite
```

Default path:

```text
workspace/research.db
```

Notes:

- local only
- no distributed behavior required
- no ORM requirement
- SQLAlchemy acceptable

---

## Published Experiment Data

Purpose:

Store selected experiment outputs permanently.

Requirements:

- checked into source control
- human-readable
- stable format
- independent of SQLite DB
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

├── database/

├── workspace/
│
│   ├── research.db
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

Represents a research study.

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
```

Example:

```json
{
    "id":"EXP001",
    "name":"Bracket Query Comparison",
    "type":"query_comparison",
    "status":"running",
    "setup":{
        "model":"default",
        "temperature":0,
        "notes":"Compare bracket-generation queries with different constraints."
    }
}
```

---

## Query

Represents a user-identified query within an experiment. Queries are stored independently from model and parameter choices so the same query can be run against multiple configurations.

Fields:

```text
id

experiment_id

text

category

metadata
```

Example:

```json
{
    "id":"Q001",
    "experiment_id":"EXP001",
    "text":"Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes.",
    "category":"mechanical"
}
```

---

## Run

Represents a single execution of one query against the Cadybara API with a specific model and parameter snapshot.

Fields:

```text
id

experiment_id

model

parameters

query_id

status

started_at

finished_at

error
```

---

## Result

Stores collected output from a Cadybara API run, including returned STL files and computed scores.

Fields:

```text
id

run_id

response_metadata

score

metrics

raw_output

stl_paths

artifact_paths
```

Example:

```json
{
    "response_metadata":{
        "api_version":"v1",
        "latency_ms":1240
    },
    "score":0.88,
    "metrics":{
        "dimension_score":0.92,
        "constraint_score":0.81,
        "overall":0.88
    },
    "stl_paths":[
        "workspace/artifacts/EXP001/RUN001/model_001.stl",
        "workspace/artifacts/EXP001/RUN001/model_002.stl"
    ],
    "artifact_paths":[
        "workspace/artifacts/EXP001/RUN001/metadata.json"
    ]
}
```

---

# 6. SQLite Schema

Minimum schema:

```sql
CREATE TABLE experiments (

    id TEXT PRIMARY KEY,

    name TEXT,

    description TEXT,

    type TEXT,

    status TEXT,

    setup TEXT,

    created_at TEXT,

    updated_at TEXT
);

CREATE TABLE queries (

    id TEXT PRIMARY KEY,

    experiment_id TEXT,

    text TEXT,

    category TEXT,

    metadata TEXT
);

CREATE TABLE runs (

    id TEXT PRIMARY KEY,

    experiment_id TEXT,

    query_id TEXT,

    model TEXT,

    parameters TEXT,

    status TEXT,

    started_at TEXT,

    finished_at TEXT,

    error TEXT
);

CREATE TABLE results (

    id TEXT PRIMARY KEY,

    run_id TEXT,

    response_metadata TEXT,

    score REAL,

    metrics TEXT,

    raw_output TEXT,

    stl_paths TEXT,

    artifact_paths TEXT
);
```

JSON fields stored as text.

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

Runs the configured query list against the Cadybara API for the selected model and parameter combinations.

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

Each published file represents one selected run. The file should include the query, model, parameters, returned STL paths or copied STL files, score, metrics, and enough experiment metadata to understand where the run came from.

Example:

```json
{
    "experiment_id":"EXP001",

    "experiment":"Bracket Query Comparison",

    "run_id":"RUN001",

    "date":"2026-05-17",

    "query":{
        "id":"Q001",
        "text":"Create a 100x50x4 mm symmetric mounting bracket with four equally spaced holes."
    },

    "model":"default",

    "parameters":{
        "temperature":0,
        "output_format":"stl"
    },

    "stl_paths":[
        "published/runs/RUN001/model_001.stl",
        "published/runs/RUN001/model_002.stl"
    ],

    "score":0.88,

    "metrics":{
        "dimension_score":0.92,
        "constraint_score":0.81,
        "overall":0.88
    },

    "conclusions":[
        "Explicit dimensions improve generated output quality",
        "Hole placement constraints require additional validation"
    ]
}
```

---

# 10. Bootstrap Scope Constraints

Must include:

✓ SQLite storage

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
