# cadybara-benchmark

Local benchmark CLI for running Cadybara Agent API experiments, collecting STL outputs, analyzing runs, and publishing selected results.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set `CADYBARA_API_KEY`. To use a local Cadybara API server, also set `CADYBARA_API_BASE_URL`, for example:

```text
CADYBARA_API_BASE_URL=http://localhost:8008
```

The API request timeout is controlled by:

```text
CADYBARA_REQUEST_TIMEOUT_SECONDS=180
```

## Storage Model

Experiment definitions are YAML files:

```text
workspace/experiments/EXP001.yaml
```

Each experiment run executes all query lines and is stored on disk:

```text
workspace/artifacts/{experiment_id}/{run_id}/summary.json
workspace/artifacts/{experiment_id}/{run_id}/{query_id}/model.stl
workspace/artifacts/{experiment_id}/{run_id}/{query_id}/response.json
```

Published run files are written under:

```text
published/runs/
```

## Experiment YAML Format

Each query line may specify a model. If `model` is empty, the query uses `setup.model`.

```yaml
id: "EXP001"
name: "Three-Tier Cubic Snowman Model Comparison"
description: "Compare three models on a three-tier cubic snowman query."
type: "query_comparison"
status: "draft"
setup:
  model: "default"
  response_mode: "json"
  linear_deflection: 0.1
  angular_deflection: 0.1
created_at: "2026-06-07T19:40:47Z"
updated_at: "2026-06-07T19:40:47Z"
queries:
  - id: "Q001"
    text: "design a three-tier cubic snowman with slightly soft edges"
    model: "google/gemini-3-flash-preview"
    category: ""
    metadata: {}
```

Runs are associated with the experiment. Each run executes all query lines in that experiment and stores per-query snapshots (text, model) in `summary.json` plus detail artifacts in query subfolders.

## Common Workflow

Create an experiment:

```bash
cadybara-benchmark create-experiment \
  --name "Three-Tier Cubic Snowman Model Comparison" \
  --description "Compare three models on a three-tier cubic snowman query."
```

Add query lines, one per model:

```bash
cadybara-benchmark add-query EXP001 \
  --text "design a three-tier cubic snowman with slightly soft edges" \
  --model "google/gemini-3-flash-preview"

cadybara-benchmark add-query EXP001 \
  --text "design a three-tier cubic snowman with slightly soft edges" \
  --model "gpt-5.4-mini"

cadybara-benchmark add-query EXP001 \
  --text "design a three-tier cubic snowman with slightly soft edges" \
  --model "gpt-5.5"
```

Generate an experiment from `cadgenbench-data`:

```bash
import-cadgenbench --series both
```

For 100-series folders, query text and attached images come from
`description.yaml`; every file listed under `input_files` is attached to that
query line. Generated experiments reference the source image paths directly.

Import only the 100-series, 200-series, or specific folders:

```bash
import-cadgenbench --series 100
import-cadgenbench --series 200 --folder 201 --folder 229
```

Override experiment setup defaults when generating the experiment:

```bash
import-cadgenbench \
  --series 100 \
  --folder 104 \
  --model "gpt-5.5" \
  --response-mode json \
  --return-format code \
  --linear-deflection 0.1 \
  --angular-deflection 0.1
```

Export a completed run into the CADGenBench submission package layout:

```bash
export-cadgenbench EXP005 RUN001 ./cadgenbench-submission \
  --series 100 \
  --submitter-name "Your Name" \
  --submission-name "Gemini Flash 100 Series" \
  --agent-url "https://example.com/agent" \
  --notes "Generated with cadybara-benchmark." \
  --render-step
```

The package folder contains top-level `meta.json` and one folder per sample.
Each successful sample contains `output.step`; failed or missing samples are
left as empty sample folders so CADGenBench scores them as missing. Use
`--render-step` to render `output.step` from a run artifact's
`generated_code.py` with CadQuery when available.

Inspect the experiment:

```bash
cadybara-benchmark show-experiment EXP001
cadybara-benchmark list-queries EXP001
```

Run the experiment:

```bash
cadybara-benchmark run EXP001
```

Analyze completed results:

```bash
cadybara-benchmark analyze EXP001
```

Publish completed runs:

```bash
cadybara-benchmark publish EXP001
```

Publish one completed run:

```bash
cadybara-benchmark publish EXP001 --run-id RUN001
```

## Webapp

Start the local experiment management webapp:

```bash
cadybara-benchmark web
```

Then open:

```text
http://127.0.0.1:8000/experiments
```

The webapp provides the MVP pages from `DESIGN.md`: experiment listing and creation, experiment detail with setup/query/run organization, light/dark theme switching, and the published runs page.

## One-Off Query

Submit a query without creating an experiment:

```bash
cadybara-benchmark submit-query \
  --text "Create a 20mm cube with a 5mm through-hole."
```

Select a model for a one-off query:

```bash
cadybara-benchmark submit-query \
  --text "A three tier cubic snowman with soft edges" \
  --model "google/gemini-3-flash-preview"
```

## Useful Commands

```bash
cadybara-benchmark list-experiments
cadybara-benchmark show-experiment EXP001
cadybara-benchmark list-queries EXP001
cadybara-benchmark run EXP001
cadybara-benchmark analyze EXP001
cadybara-benchmark publish EXP001
```
