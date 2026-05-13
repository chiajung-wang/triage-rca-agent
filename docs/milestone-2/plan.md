# Milestone 2: Issue Store + BugsInPy Corpus

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** sqlite-vec vector search working; BugsInPy bug descriptions embedded and queryable; `setup_db.py` fully populates corpus.

**Deliverable Test:** `pytest tests/unit/test_issue_store.py` passes; `python scripts/setup_db.py` embeds 100+ BugsInPy bugs; `IssueStore.search(query, k=3)` returns 3 ranked results.

**Domain refs:** CONTEXT.md: Issue Store, SimilaritySearcher, BugsInPy. ADR 0002, ADR 0004.

**Prerequisite:** Milestone 1 complete (DB schema + package installed).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/issue_store.py` | IssueStore with sqlite-vec nearest-neighbor |
| Create | `src/triage_rca/embedder.py` | Embed text via voyage-3 (Anthropic embeddings) |
| Modify | `scripts/setup_db.py` | Add sqlite-vec table init + BugsInPy embedding step |
| Create | `scripts/embed_corpus.py` | Standalone: embed + insert all BugsInPy bugs |
| Create | `data/bugsinpy/` | Cloned BugsInPy repo (gitignored) |
| Create | `tests/unit/test_issue_store.py` | IssueStore unit tests |

---

## IssueStore Interface

```python
@dataclass
class SimilarIssue:
    bug_id: str
    project: str
    description: str
    similarity: float  # 0.0–1.0, higher = more similar

class IssueStore:
    def __init__(self, db_path: str): ...
    def init_vec_table(self, dimensions: int = 1024) -> None: ...
    def insert(self, bug_id: str, project: str, description: str, embedding: list[float]) -> None: ...
    def search(self, query_embedding: list[float], k: int = 5) -> list[SimilarIssue]: ...
    def count(self) -> int: ...
```

---

## Tasks

### T2.1: IssueStore with sqlite-vec

- [ ] Write failing test `tests/unit/test_issue_store.py`:

```python
import pytest
from triage_rca.issue_store import IssueStore, SimilarIssue

def test_insert_and_search(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)

    store.insert("bug-1", "pandas", "TypeError in merge", [0.1, 0.2, 0.3, 0.4])
    store.insert("bug-2", "numpy", "IndexError in reshape", [0.9, 0.8, 0.7, 0.6])
    store.insert("bug-3", "pandas", "NullPointerError in concat", [0.15, 0.25, 0.35, 0.45])

    results = store.search([0.1, 0.2, 0.3, 0.4], k=2)
    assert len(results) == 2
    assert results[0].bug_id == "bug-1"
    assert results[0].similarity >= results[1].similarity

def test_count_empty(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    assert store.count() == 0

def test_count_after_insert(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "test", [0.1, 0.2, 0.3, 0.4])
    assert store.count() == 1

def test_insert_idempotent(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "first description", [0.1, 0.2, 0.3, 0.4])
    store.insert("bug-1", "pandas", "updated description", [0.1, 0.2, 0.3, 0.4])
    assert store.count() == 1
```

- [ ] Run to confirm failure: `pytest tests/unit/test_issue_store.py -v`

- [ ] Create `src/triage_rca/issue_store.py`:

```python
import sqlite3
import struct
from dataclasses import dataclass
import sqlite_vec

@dataclass
class SimilarIssue:
    bug_id: str
    project: str
    description: str
    similarity: float

class IssueStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS issue_meta (
                    bug_id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    description TEXT NOT NULL
                )
            """)
            self._conn.commit()
        return self._conn

    def init_vec_table(self, dimensions: int = 1024) -> None:
        conn = self._get_conn()
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS issue_embeddings
            USING vec0(bug_id TEXT PRIMARY KEY, embedding float[{dimensions}])
        """)
        conn.commit()

    def insert(self, bug_id: str, project: str, description: str, embedding: list[float]) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO issue_meta (bug_id, project, description) VALUES (?, ?, ?)",
            (bug_id, project, description),
        )
        vec_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        conn.execute(
            "INSERT OR REPLACE INTO issue_embeddings (bug_id, embedding) VALUES (?, ?)",
            (bug_id, vec_bytes),
        )
        conn.commit()

    def search(self, query_embedding: list[float], k: int = 5) -> list[SimilarIssue]:
        conn = self._get_conn()
        vec_bytes = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        rows = conn.execute("""
            SELECT m.bug_id, m.project, m.description, e.distance
            FROM issue_embeddings e
            JOIN issue_meta m ON e.bug_id = m.bug_id
            WHERE e.embedding MATCH ? AND k = ?
            ORDER BY e.distance
        """, (vec_bytes, k)).fetchall()
        return [
            SimilarIssue(
                bug_id=r["bug_id"],
                project=r["project"],
                description=r["description"],
                similarity=max(0.0, 1.0 - r["distance"]),
            )
            for r in rows
        ]

    def count(self) -> int:
        return self._get_conn().execute("SELECT COUNT(*) FROM issue_meta").fetchone()[0]
```

- [ ] Run: `pytest tests/unit/test_issue_store.py -v` → 4 PASS

- [ ] Commit:

```bash
git add src/triage_rca/issue_store.py tests/unit/test_issue_store.py
git commit -m "feat(m2): IssueStore with sqlite-vec nearest-neighbor search"
```

---

### T2.2: Embedder

- [ ] Create `src/triage_rca/embedder.py`:

```python
import anthropic

def embed_text(text: str, client: anthropic.Anthropic) -> list[float]:
    """Embed text using voyage-3 via Anthropic embeddings endpoint."""
    response = client.beta.embeddings.create(
        model="voyage-3",
        input=text,
    )
    return response.data[0].embedding
```

Note: If `client.beta.embeddings` is not available in the installed SDK version, fall back to:

```python
import httpx, os

def embed_text(text: str, client: anthropic.Anthropic) -> list[float]:
    resp = httpx.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
        json={"input": text, "model": "voyage-3"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
```

- [ ] Commit:

```bash
git add src/triage_rca/embedder.py
git commit -m "feat(m2): embedder using voyage-3"
```

---

### T2.3: BugsInPy Corpus Loader

- [ ] Create `scripts/embed_corpus.py`:

```python
#!/usr/bin/env python3
"""Embed BugsInPy bug descriptions and insert into Issue Store. Run once after setup_db.py."""
import os, sys
from pathlib import Path
import anthropic
from triage_rca.issue_store import IssueStore
from triage_rca.embedder import embed_text

DB_PATH = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")
BUGSINPY_PATH = os.getenv("BUGSINPY_PATH", "data/bugsinpy")

def load_bugsinpy_bugs(path: str) -> list[dict]:
    bugs = []
    for bug_info in Path(path).glob("projects/*/bugs/*/bug.info"):
        parts = bug_info.parts
        project = parts[-4]
        bug_num = parts[-2]
        bug_id = f"{project}-{bug_num}"
        content = bug_info.read_text(errors="replace")
        lines = {}
        for line in content.strip().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                lines[k.strip()] = v.strip()
        description = (
            lines.get("bug_description")
            or lines.get("buggy_commit_id", "")
        )
        if description:
            bugs.append({"bug_id": bug_id, "project": project, "description": description})
    return bugs

if __name__ == "__main__":
    if not Path(BUGSINPY_PATH).exists():
        print(f"BugsInPy not found at {BUGSINPY_PATH}. Clone it first:")
        print("  git clone https://github.com/soarsmu/BugsInPy data/bugsinpy")
        sys.exit(1)

    client = anthropic.Anthropic()
    store = IssueStore(DB_PATH)

    bugs = load_bugsinpy_bugs(BUGSINPY_PATH)
    print(f"Found {len(bugs)} bugs. Embedding...")

    for i, bug in enumerate(bugs):
        embedding = embed_text(bug["description"], client)
        store.insert(bug["bug_id"], bug["project"], bug["description"], embedding)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(bugs)} embedded")

    print(f"Done. {store.count()} bugs in Issue Store.")
```

- [ ] Update `scripts/setup_db.py` to init vec table:

```python
#!/usr/bin/env python3
import os
from triage_rca.db import init_db
from triage_rca.issue_store import IssueStore

DB_PATH = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")

if __name__ == "__main__":
    init_db(DB_PATH)
    print(f"Schema initialized: {DB_PATH}")
    store = IssueStore(DB_PATH)
    store.init_vec_table(dimensions=1024)
    print("Vector table ready.")
    print("Run: python scripts/embed_corpus.py  to populate BugsInPy embeddings")
```

- [ ] Run: `python scripts/setup_db.py`

Expected:
```
Schema initialized: triage_rca.db
Vector table ready.
Run: python scripts/embed_corpus.py  to populate BugsInPy embeddings
```

- [ ] Commit:

```bash
git add scripts/embed_corpus.py scripts/setup_db.py
git commit -m "feat(m2): BugsInPy corpus loader, updated setup_db with vec table init"
```

---

## Milestone 2 Verification

```bash
pytest tests/unit/test_issue_store.py -v    # 4 PASS
python scripts/setup_db.py                  # schema + vector table
git clone https://github.com/soarsmu/BugsInPy data/bugsinpy
python scripts/embed_corpus.py              # embeds bugs, prints count
```

After embed, verify:

```python
from triage_rca.issue_store import IssueStore
store = IssueStore("triage_rca.db")
print(store.count())   # > 100
```
