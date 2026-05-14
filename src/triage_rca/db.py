import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    issue_text TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'completed', 'low_confidence', 'no_hypothesis',
        'budget_exceeded', 'timeout', 'escalated'
    )),
    cost_usd REAL,
    elapsed_s REAL,
    tool_calls_total INTEGER,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS triage_results (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'confirmed_bug', 'feature_request', 'question',
        'documentation', 'security', 'enhancement'
    )),
    bug_type TEXT CHECK (bug_type IN (
        'logic_error', 'type_error', 'null_handling', 'off_by_one',
        'regression', 'concurrency', 'api_misuse', 'config_error',
        'performance', 'import_error'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    component TEXT,
    recommendation TEXT NOT NULL CHECK (recommendation IN (
        'investigate_rca', 'needs_repro', 'close_duplicate', 'needs_more_info'
    )),
    similar_issues TEXT
);
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    rank INTEGER NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    reasoning TEXT NOT NULL,
    verified_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        verified_status IN ('pending', 'confirmed', 'demoted')
    ),
    UNIQUE (run_id, rank)
);
"""


def init_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_connection(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn
