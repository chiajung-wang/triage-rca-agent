# Milestone 1: Foundation + Project Scaffold

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working pip-installable package with CLI entry point, DB schema, validated config, and tested BudgetTracker.

**Deliverable Test:** `pip install -e .` succeeds; `triage-rca --help` prints usage; `pytest tests/unit/` all pass; `python scripts/setup_db.py` creates triage_rca.db with correct tables.

**Domain refs:** CONTEXT.md: Budget, Stop Condition. ADR 0002 (SQLite-only).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `pyproject.toml` | Package metadata, entry point `triage-rca` |
| Create | `requirements.txt` | Pinned deps |
| Create | `src/triage_rca/__init__.py` | Package init (empty) |
| Create | `src/triage_rca/__main__.py` | `python -m triage_rca` entry |
| Create | `src/triage_rca/cli.py` | argparse: `run`, `eval` subcommands |
| Create | `src/triage_rca/config.py` | Load + validate .env |
| Create | `src/triage_rca/db.py` | DB init, schema creation, connection factory |
| Create | `src/triage_rca/budget.py` | BudgetTracker class |
| Create | `src/triage_rca/exceptions.py` | BudgetExceeded, ConfigError |
| Create | `scripts/setup_db.py` | Creates triage_rca.db, applies schema |
| Create | `tests/__init__.py` | (empty) |
| Create | `tests/unit/__init__.py` | (empty) |
| Create | `tests/unit/test_budget_tracker.py` | BudgetTracker unit tests |
| Create | `tests/unit/test_config.py` | Config loading unit tests |
| Create | `tests/unit/test_db.py` | DB schema unit tests |

---

## DB Schema (triage_rca.db)

```sql
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    issue_text TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    status TEXT NOT NULL,
    cost_usd REAL,
    elapsed_s REAL,
    tool_calls_total INTEGER,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS triage_results (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    issue_type TEXT NOT NULL,
    bug_type TEXT,
    severity TEXT NOT NULL,
    component TEXT,
    recommendation TEXT NOT NULL,
    similar_issues TEXT
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    rank INTEGER NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);
```

---

## BudgetTracker Interface

```python
@dataclass
class BudgetState:
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    tool_calls_total: int = 0
    tool_calls_by_subagent: dict[str, int] = field(default_factory=dict)

class BudgetTracker:
    COST_LIMIT = 0.50
    WALL_CLOCK_LIMIT = 300.0
    TOOL_CALLS_PER_SUBAGENT = 50
    TOOL_CALLS_TOTAL = 200

    def start(self) -> None: ...          # records wall-clock start
    def add_cost(self, usd: float) -> None: ...
    def add_tool_call(self, subagent: str) -> None: ...
    def check(self) -> None: ...          # raises BudgetExceeded if any limit hit
    def snapshot(self) -> BudgetState: ...
```

---

## Tasks

### T1.1: Package Scaffold + Config

- [ ] Write failing test `tests/unit/test_config.py`:

```python
import os, pytest
from triage_rca.config import load_config, ConfigError

def test_load_config_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_config()

def test_load_config_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    config = load_config()
    assert config.anthropic_api_key == "sk-test"
    assert config.langfuse_public_key == "pk-test"
```

- [ ] Run test to confirm it fails:

```bash
pytest tests/unit/test_config.py -v
# Expected: ModuleNotFoundError: No module named 'triage_rca'
```

- [ ] Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "triage-rca"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "rich>=13.0.0",
    "langfuse>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
triage-rca = "triage_rca.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] Create `requirements.txt`:

```
anthropic>=0.40.0
rich>=13.0.0
langfuse>=2.0.0
python-dotenv>=1.0.0
sqlite-vec>=0.1.0
pytest>=8.0.0
pytest-mock>=3.0.0
```

- [ ] Create `src/triage_rca/__init__.py` (empty file)

- [ ] Create `src/triage_rca/exceptions.py`:

```python
class BudgetExceeded(Exception):
    def __init__(self, reason: str, state):
        self.reason = reason
        self.state = state
        super().__init__(f"Budget exceeded: {reason}")

class ConfigError(Exception):
    pass
```

- [ ] Create `src/triage_rca/config.py`:

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from .exceptions import ConfigError

@dataclass
class Config:
    anthropic_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = "https://cloud.langfuse.com"

def load_config() -> Config:
    load_dotenv()
    missing = [k for k in ("ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.getenv(k)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")
    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        langfuse_secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
```

- [ ] Run: `pytest tests/unit/test_config.py -v` → 2 PASS

- [ ] Commit:

```bash
git add src/ tests/ pyproject.toml requirements.txt
git commit -m "feat(m1): package scaffold, config loading with validation"
```

---

### T1.2: BudgetTracker

- [ ] Write failing test `tests/unit/test_budget_tracker.py`:

```python
import pytest
from triage_rca.budget import BudgetTracker
from triage_rca.exceptions import BudgetExceeded

def test_cost_limit():
    t = BudgetTracker()
    t.start()
    t.add_cost(0.49)
    t.check()  # OK at 0.49
    t.add_cost(0.02)
    with pytest.raises(BudgetExceeded, match="cost"):
        t.check()

def test_tool_calls_per_subagent():
    t = BudgetTracker()
    t.start()
    for _ in range(50):
        t.add_tool_call("classifier")
    t.check()  # OK at exactly 50
    t.add_tool_call("classifier")
    with pytest.raises(BudgetExceeded, match="tool_calls"):
        t.check()

def test_total_tool_calls():
    t = BudgetTracker()
    t.start()
    for i in range(200):
        t.add_tool_call(f"agent_{i % 5}")
    t.check()  # OK at exactly 200
    t.add_tool_call("any")
    with pytest.raises(BudgetExceeded, match="tool_calls"):
        t.check()

def test_snapshot():
    t = BudgetTracker()
    t.start()
    t.add_cost(0.10)
    t.add_tool_call("investigator")
    s = t.snapshot()
    assert s.cost_usd == pytest.approx(0.10)
    assert s.tool_calls_by_subagent["investigator"] == 1
    assert s.tool_calls_total == 1
```

- [ ] Run to confirm failure: `pytest tests/unit/test_budget_tracker.py -v`

- [ ] Create `src/triage_rca/budget.py`:

```python
import time
from dataclasses import dataclass, field
from .exceptions import BudgetExceeded

@dataclass
class BudgetState:
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    tool_calls_total: int = 0
    tool_calls_by_subagent: dict[str, int] = field(default_factory=dict)

class BudgetTracker:
    COST_LIMIT = 0.50
    WALL_CLOCK_LIMIT = 300.0
    TOOL_CALLS_PER_SUBAGENT = 50
    TOOL_CALLS_TOTAL = 200

    def __init__(self):
        self._state = BudgetState()
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.monotonic()

    def add_cost(self, usd: float) -> None:
        self._state.cost_usd += usd

    def add_tool_call(self, subagent: str) -> None:
        self._state.tool_calls_total += 1
        self._state.tool_calls_by_subagent[subagent] = (
            self._state.tool_calls_by_subagent.get(subagent, 0) + 1
        )

    def check(self) -> None:
        if self._start_time is not None:
            self._state.elapsed_s = time.monotonic() - self._start_time
        if self._state.cost_usd > self.COST_LIMIT:
            raise BudgetExceeded("cost", self._state)
        if self._state.elapsed_s > self.WALL_CLOCK_LIMIT:
            raise BudgetExceeded("timeout", self._state)
        if self._state.tool_calls_total > self.TOOL_CALLS_TOTAL:
            raise BudgetExceeded("tool_calls_total", self._state)
        for agent, count in self._state.tool_calls_by_subagent.items():
            if count > self.TOOL_CALLS_PER_SUBAGENT:
                raise BudgetExceeded(f"tool_calls per subagent ({agent})", self._state)

    def snapshot(self) -> BudgetState:
        if self._start_time is not None:
            self._state.elapsed_s = time.monotonic() - self._start_time
        return BudgetState(
            cost_usd=self._state.cost_usd,
            elapsed_s=self._state.elapsed_s,
            tool_calls_total=self._state.tool_calls_total,
            tool_calls_by_subagent=dict(self._state.tool_calls_by_subagent),
        )
```

- [ ] Run: `pytest tests/unit/test_budget_tracker.py -v` → 4 PASS

- [ ] Commit:

```bash
git add src/triage_rca/budget.py src/triage_rca/exceptions.py tests/unit/test_budget_tracker.py
git commit -m "feat(m1): BudgetTracker with cost/time/tool-call enforcement"
```

---

### T1.3: DB Schema + CLI Entry

- [ ] Write failing test `tests/unit/test_db.py`:

```python
import sqlite3, pytest
from triage_rca.db import init_db, get_connection

def test_init_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"runs", "triage_results", "hypotheses"} <= tables
    conn.close()

def test_get_connection_row_factory(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("r1", "2026-01-01", "issue", "/repo", "completed", 0.1, 10.0, 5, None))
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE id=?", ("r1",)).fetchone()
    assert row["id"] == "r1"
    conn.close()
```

- [ ] Create `src/triage_rca/db.py`:

```python
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    issue_text TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    status TEXT NOT NULL,
    cost_usd REAL,
    elapsed_s REAL,
    tool_calls_total INTEGER,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS triage_results (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    issue_type TEXT NOT NULL,
    bug_type TEXT,
    severity TEXT NOT NULL,
    component TEXT,
    recommendation TEXT NOT NULL,
    similar_issues TEXT
);
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    rank INTEGER NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);
"""

def init_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

def get_connection(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
```

- [ ] Create `src/triage_rca/cli.py`:

```python
import argparse

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="triage-rca",
        description="Bug triage and RCA for Python codebases"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Triage a bug report and optionally run RCA")
    run_p.add_argument("--issue", required=True, help="Bug report text")
    run_p.add_argument("--repo", required=True, help="Path to target Python repo")
    run_p.add_argument("--interactive", action="store_true",
                       help="Pause for human input when stuck")

    eval_p = sub.add_parser("eval", help="Run eval harness")
    eval_p.add_argument("mode", choices=["rca", "triage"], help="Eval mode")

    args = parser.parse_args()

    if args.command == "run":
        from triage_rca.orchestrator import run_pipeline
        run_pipeline(issue=args.issue, repo_path=args.repo, interactive=args.interactive)
    elif args.command == "eval":
        from triage_rca.eval import run_eval
        run_eval(mode=args.mode)
```

- [ ] Create `src/triage_rca/__main__.py`:

```python
from triage_rca.cli import main
main()
```

- [ ] Create `scripts/setup_db.py`:

```python
#!/usr/bin/env python3
import os
from triage_rca.db import init_db

DB_PATH = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")

if __name__ == "__main__":
    init_db(DB_PATH)
    print(f"Database initialized: {DB_PATH}")
```

- [ ] Install package and verify CLI:

```bash
pip install -e .
triage-rca --help
# Expected: usage with run and eval subcommands
```

- [ ] Run: `pytest tests/unit/test_db.py -v` → 2 PASS

- [ ] Commit:

```bash
git add src/triage_rca/db.py src/triage_rca/cli.py src/triage_rca/__main__.py
git add scripts/setup_db.py tests/unit/test_db.py tests/__init__.py tests/unit/__init__.py
git commit -m "feat(m1): DB schema, CLI entry point with run/eval subcommands"
```

---

## Milestone 1 Verification

```bash
pip install -e .
triage-rca --help                    # shows usage
pytest tests/unit/ -v               # all pass
python scripts/setup_db.py          # "Database initialized: triage_rca.db"
sqlite3 triage_rca.db ".tables"     # runs  triage_results  hypotheses
```
