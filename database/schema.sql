CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    type TEXT,
    status TEXT,
    setup TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    id TEXT PRIMARY KEY,
    experiment_id TEXT,
    text TEXT,
    category TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS runs (
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

CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    response_metadata TEXT,
    score REAL,
    metrics TEXT,
    raw_output TEXT,
    stl_paths TEXT,
    artifact_paths TEXT
);
