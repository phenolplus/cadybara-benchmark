# cadybara-benchmark

Bootstrap CLI for running local benchmark experiments against the Cadybara Agent API.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set `CADYBARA_API_KEY`.

## First Run

```bash
cadybara-benchmark init-db
cadybara-benchmark create-experiment --name "Bracket Query Comparison"
cadybara-benchmark add-query EXP001 --text "Create a 20mm cube with a 5mm through-hole."
cadybara-benchmark run EXP001
cadybara-benchmark analyze EXP001
cadybara-benchmark publish EXP001
```

To submit a one-off query without creating an experiment:

```bash
cadybara-benchmark submit-query --text "Create a 20mm cube with a 5mm through-hole."
```

Select a model for a one-off query:

```bash
cadybara-benchmark submit-query \
  --text "A three tier cubic snowman with soft edges" \
  --model google/gemini-3-flash-preview
```

Generated workspace state is stored under `workspace/` and ignored by git. Published runs are written under `published/runs/`.
