# Milestone 3: Triage Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `triage-rca run --issue "..." --repo .` produces a complete TriageResult: issue_type, bug_type, severity, component, similar_issues, recommendation.

**Deliverable Test:** `pytest tests/integration/test_triage_pipeline.py -v` passes with mock Anthropic client; triage pipeline correctly gates non-bugs before CodeExplorer + SimilaritySearcher.

**Domain refs:** CONTEXT.md: Classifier, CodeExplorer, SimilaritySearcher, TriageResult, Issue Type, Bug Type, recommendation. ADR 0001 (direct SDK).

**Prerequisite:** Milestones 1–2 complete.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/schemas.py` | All dataclasses: TriageResult, Hypothesis, StopCondition, EvidenceBundle, CodeSnippet |
| Create | `src/triage_rca/agents/__init__.py` | Empty |
| Create | `src/triage_rca/agents/classifier.py` | Pure LLM: issue_type + bug_type + severity |
| Create | `src/triage_rca/agents/code_explorer.py` | File read + grep → component path |
| Create | `src/triage_rca/agents/similarity_searcher.py` | Wraps IssueStore.search |
| Create | `src/triage_rca/triage_pipeline.py` | Classifier → (CodeExplorer ‖ SimilaritySearcher) → TriageResult |
| Create | `tests/integration/__init__.py` | Empty |
| Create | `tests/integration/test_triage_pipeline.py` | Integration tests with mock client |
| Create | `tests/fixtures/simple_repo/` | Minimal Python repo with one obvious bug |

---

## TriageResult Schema (`src/triage_rca/schemas.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
from triage_rca.issue_store import SimilarIssue

IssueType = Literal["confirmed_bug", "feature_request", "question", "documentation", "security", "enhancement"]
BugType = Literal["logic_error", "type_error", "null_handling", "off_by_one", "regression",
                  "concurrency", "api_misuse", "config_error", "performance", "import_error"]
Severity = Literal["critical", "high", "medium", "low"]
Recommendation = Literal["investigate_rca", "needs_repro", "close_duplicate", "needs_more_info"]

@dataclass
class TriageResult:
    issue_type: IssueType
    bug_type: BugType | None
    severity: Severity
    component: str | None
    similar_issues: list[SimilarIssue]
    recommendation: Recommendation

@dataclass
class Hypothesis:
    file: str
    start_line: int
    end_line: int
    confidence: float
    reasoning: str
    verified: bool = False

@dataclass
class CodeSnippet:
    file: str
    start_line: int
    end_line: int
    content: str

@dataclass
class StaticMemory:
    file_tree: list[str]
    module_index: dict[str, str]
    test_file: str

@dataclass
class DynamicMemory:
    relevant_files: list[str] = field(default_factory=list)
    stack_frames: list[str] = field(default_factory=list)
    call_path: list[str] = field(default_factory=list)
    ruled_out: list[str] = field(default_factory=list)

@dataclass
class TestResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed_s: float

@dataclass
class EvidenceBundle:
    static_memory: StaticMemory
    dynamic_memory: DynamicMemory
    code_snippets: list[CodeSnippet]
    test_result: TestResult

@dataclass
class StopCondition:
    status: Literal["completed", "low_confidence", "no_hypothesis", "budget_exceeded", "timeout", "escalated"]
    triage_result: TriageResult | None
    hypotheses: list[Hypothesis]
    partial: bool
    stop_reason: str
    steps_attempted: list[str]
    cost_usd: float
    elapsed_s: float
    tool_calls_total: int
```

---

## Classifier System Prompt

```
You are a bug triage classifier. Given a bug report, output a JSON object with exactly these fields:
- issue_type: one of confirmed_bug | feature_request | question | documentation | security | enhancement
- bug_type: one of logic_error | type_error | null_handling | off_by_one | regression | concurrency | api_misuse | config_error | performance | import_error — set to null if issue_type is not confirmed_bug or security
- severity: one of critical | high | medium | low
- reasoning: one sentence

Respond ONLY with valid JSON. No prose. No markdown fences.
```

---

## Triage Pipeline Logic

```
Classifier.classify(issue_text)
  → if issue_type not in (confirmed_bug, security):
      return TriageResult(recommendation=needs_repro or close_duplicate or needs_more_info)
  → else:
      run CodeExplorer.find_component(issue_text, repo_path) in parallel with
          SimilaritySearcher.search(issue_text)
      → merge into TriageResult(recommendation=investigate_rca)
```

---

## Tasks

### T3.1: Schemas

- [ ] Create `src/triage_rca/schemas.py` with all dataclasses as shown above.

- [ ] Write minimal test:

```python
from triage_rca.schemas import TriageResult, Hypothesis, StopCondition

def test_schemas_instantiate():
    from triage_rca.issue_store import SimilarIssue
    r = TriageResult(
        issue_type="confirmed_bug", bug_type="type_error", severity="high",
        component=None, similar_issues=[], recommendation="investigate_rca"
    )
    assert r.issue_type == "confirmed_bug"
```

- [ ] Run: `pytest -k test_schemas_instantiate -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/schemas.py
git commit -m "feat(m3): shared dataclass schemas (TriageResult, Hypothesis, StopCondition, EvidenceBundle)"
```

---

### T3.2: Classifier

- [ ] Write failing test in `tests/integration/test_triage_pipeline.py`:

```python
import json, pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.create.return_value.content = [MagicMock()]
    return client

def test_classifier_confirmed_bug(mock_client):
    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "issue_type": "confirmed_bug", "bug_type": "type_error",
        "severity": "high", "reasoning": "Stack trace shows TypeError"
    })
    from triage_rca.agents.classifier import Classifier
    clf = Classifier(client=mock_client)
    result = clf.classify("TypeError in DataFrame.merge")
    assert result["issue_type"] == "confirmed_bug"
    assert result["bug_type"] == "type_error"

def test_classifier_feature_request(mock_client):
    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "issue_type": "feature_request", "bug_type": None,
        "severity": "low", "reasoning": "User wants new feature"
    })
    from triage_rca.agents.classifier import Classifier
    clf = Classifier(client=mock_client)
    result = clf.classify("Add dark mode support")
    assert result["issue_type"] == "feature_request"
    assert result["bug_type"] is None
```

- [ ] Create `src/triage_rca/agents/__init__.py` (empty)

- [ ] Create `src/triage_rca/agents/classifier.py`:

```python
import json
import anthropic

SYSTEM_PROMPT = (
    "You are a bug triage classifier. Given a bug report, output a JSON object with exactly these fields:\n"
    "- issue_type: one of confirmed_bug | feature_request | question | documentation | security | enhancement\n"
    "- bug_type: one of logic_error | type_error | null_handling | off_by_one | regression | concurrency | "
    "api_misuse | config_error | performance | import_error — set to null if issue_type is not confirmed_bug or security\n"
    "- severity: one of critical | high | medium | low\n"
    "- reasoning: one sentence\n\n"
    "Respond ONLY with valid JSON. No prose. No markdown fences."
)

class Classifier:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def classify(self, issue_text: str) -> dict:
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": issue_text}],
        )
        return json.loads(response.content[0].text)
```

- [ ] Run: `pytest tests/integration/test_triage_pipeline.py::test_classifier_confirmed_bug tests/integration/test_triage_pipeline.py::test_classifier_feature_request -v` → 2 PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/ tests/integration/
git commit -m "feat(m3): Classifier subagent with pure LLM classification"
```

---

### T3.3: CodeExplorer

- [ ] Create `tests/fixtures/simple_repo/` with:

```
tests/fixtures/simple_repo/
├── mypackage/
│   ├── __init__.py
│   └── utils.py        ← contains a type error
└── tests/
    └── test_utils.py   ← failing test
```

`tests/fixtures/simple_repo/mypackage/utils.py`:
```python
def add(a, b):
    return a + b  # will fail if called with None

def divide(a, b):
    return a / b  # ZeroDivisionError when b=0
```

`tests/fixtures/simple_repo/tests/test_utils.py`:
```python
def test_divide_by_zero():
    from mypackage.utils import divide
    divide(1, 0)  # expected to raise ZeroDivisionError
```

- [ ] Write failing test:

```python
def test_code_explorer_finds_component(mock_client, tmp_path):
    import shutil
    from pathlib import Path
    fixture = Path("tests/fixtures/simple_repo")
    shutil.copytree(fixture, tmp_path / "repo")

    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "component": "mypackage/utils.py",
        "reasoning": "ZeroDivisionError originates in divide()"
    })
    from triage_rca.agents.code_explorer import CodeExplorer
    explorer = CodeExplorer(client=mock_client)
    result = explorer.find_component("ZeroDivisionError in divide", str(tmp_path / "repo"))
    assert "utils.py" in result["component"]
```

- [ ] Create `src/triage_rca/agents/code_explorer.py`:

```python
import json, os
from pathlib import Path
import anthropic

SYSTEM_PROMPT = (
    "You are a code explorer. Given a bug description and a file listing, identify the most likely "
    "affected component (file path). Output JSON: {\"component\": \"<relative/path.py>\", \"reasoning\": \"<one sentence>\"}. "
    "Respond ONLY with valid JSON."
)

class CodeExplorer:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def find_component(self, issue_text: str, repo_path: str) -> dict:
        file_listing = self._list_python_files(repo_path)
        prompt = f"Bug description: {issue_text}\n\nPython files in repo:\n{file_listing}"
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.content[0].text)

    def _list_python_files(self, repo_path: str) -> str:
        root = Path(repo_path)
        files = sorted(str(p.relative_to(root)) for p in root.rglob("*.py") if ".git" not in str(p))
        return "\n".join(files[:100])  # cap at 100 files to stay within context
```

- [ ] Run: `pytest tests/integration/test_triage_pipeline.py::test_code_explorer_finds_component -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/code_explorer.py tests/fixtures/
git commit -m "feat(m3): CodeExplorer subagent with file listing + LLM component detection"
```

---

### T3.4: SimilaritySearcher

- [ ] Write failing test:

```python
def test_similarity_searcher_returns_results(mock_client, tmp_path):
    from triage_rca.issue_store import IssueStore
    from triage_rca.agents.similarity_searcher import SimilaritySearcher

    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "TypeError in merge", [0.1, 0.2, 0.3, 0.4])
    store.insert("bug-2", "numpy", "IndexError in reshape", [0.9, 0.8, 0.7, 0.6])

    searcher = SimilaritySearcher(store=store)
    # Use fixed embedding (bypasses real embed call)
    results = searcher.search_by_embedding([0.1, 0.2, 0.3, 0.4], k=1)
    assert len(results) == 1
    assert results[0].bug_id == "bug-1"
```

- [ ] Create `src/triage_rca/agents/similarity_searcher.py`:

```python
from triage_rca.issue_store import IssueStore, SimilarIssue

class SimilaritySearcher:
    def __init__(self, store: IssueStore):
        self.store = store

    def search_by_embedding(self, query_embedding: list[float], k: int = 5) -> list[SimilarIssue]:
        return self.store.search(query_embedding, k=k)
```

- [ ] Run: `pytest tests/integration/test_triage_pipeline.py::test_similarity_searcher_returns_results -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/similarity_searcher.py
git commit -m "feat(m3): SimilaritySearcher wrapping IssueStore"
```

---

### T3.5: Triage Pipeline Coordinator

- [ ] Write failing end-to-end test:

```python
def test_triage_pipeline_confirmed_bug(mock_client, tmp_path):
    import shutil
    from pathlib import Path
    from triage_rca.issue_store import IssueStore
    from triage_rca.triage_pipeline import TriagePipeline

    fixture = Path("tests/fixtures/simple_repo")
    shutil.copytree(fixture, tmp_path / "repo")

    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "ZeroDivisionError", [0.5, 0.5, 0.5, 0.5])

    call_count = [0]
    def side_effect(*args, **kwargs):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:  # Classifier call
            r.content[0].text = json.dumps({
                "issue_type": "confirmed_bug", "bug_type": "logic_error",
                "severity": "high", "reasoning": "Division by zero"
            })
        else:  # CodeExplorer call
            r.content[0].text = json.dumps({
                "component": "mypackage/utils.py", "reasoning": "divide() function"
            })
        return r

    mock_client.messages.create.side_effect = side_effect

    pipeline = TriagePipeline(
        client=mock_client,
        issue_store=store,
        query_embedding=[0.5, 0.5, 0.5, 0.5],
    )
    result = pipeline.run(issue_text="ZeroDivisionError in divide", repo_path=str(tmp_path / "repo"))
    assert result.issue_type == "confirmed_bug"
    assert result.component == "mypackage/utils.py"
    assert len(result.similar_issues) == 1
    assert result.recommendation == "investigate_rca"

def test_triage_pipeline_non_bug_short_circuits(mock_client, tmp_path):
    from triage_rca.issue_store import IssueStore
    from triage_rca.triage_pipeline import TriagePipeline

    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)

    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "issue_type": "feature_request", "bug_type": None,
        "severity": "low", "reasoning": "New feature"
    })

    pipeline = TriagePipeline(client=mock_client, issue_store=store, query_embedding=[0.0])
    result = pipeline.run(issue_text="Add dark mode", repo_path=str(tmp_path))
    assert result.issue_type == "feature_request"
    assert result.component is None
    assert result.recommendation == "needs_more_info"
    assert mock_client.messages.create.call_count == 1  # only Classifier called
```

- [ ] Create `src/triage_rca/triage_pipeline.py`:

```python
import anthropic
from triage_rca.agents.classifier import Classifier
from triage_rca.agents.code_explorer import CodeExplorer
from triage_rca.agents.similarity_searcher import SimilaritySearcher
from triage_rca.issue_store import IssueStore, SimilarIssue
from triage_rca.schemas import TriageResult

NON_BUG_TYPES = {"feature_request", "question", "documentation", "enhancement"}

RECOMMENDATION_MAP = {
    "feature_request": "needs_more_info",
    "question": "needs_more_info",
    "documentation": "needs_more_info",
    "enhancement": "needs_more_info",
}

class TriagePipeline:
    def __init__(
        self,
        client: anthropic.Anthropic,
        issue_store: IssueStore,
        query_embedding: list[float],
    ):
        self.classifier = Classifier(client)
        self.code_explorer = CodeExplorer(client)
        self.similarity_searcher = SimilaritySearcher(issue_store)
        self.query_embedding = query_embedding

    def run(self, issue_text: str, repo_path: str) -> TriageResult:
        classification = self.classifier.classify(issue_text)
        issue_type = classification["issue_type"]

        if issue_type in NON_BUG_TYPES:
            return TriageResult(
                issue_type=issue_type,
                bug_type=None,
                severity=classification["severity"],
                component=None,
                similar_issues=[],
                recommendation=RECOMMENDATION_MAP[issue_type],
            )

        component_result = self.code_explorer.find_component(issue_text, repo_path)
        similar_issues = self.similarity_searcher.search_by_embedding(self.query_embedding, k=5)

        return TriageResult(
            issue_type=issue_type,
            bug_type=classification.get("bug_type"),
            severity=classification["severity"],
            component=component_result.get("component"),
            similar_issues=similar_issues,
            recommendation="investigate_rca",
        )
```

- [ ] Run: `pytest tests/integration/test_triage_pipeline.py -v` → all PASS

- [ ] Commit:

```bash
git add src/triage_rca/triage_pipeline.py tests/integration/test_triage_pipeline.py
git commit -m "feat(m3): TriagePipeline coordinator with classifier gating and parallel subagents"
```

---

## Milestone 3 Verification

```bash
pytest tests/integration/test_triage_pipeline.py -v   # all PASS
pytest tests/unit/ -v                                   # still all PASS
```

Smoke test with real API (requires .env):

```bash
triage-rca run --issue "ZeroDivisionError in divide when b=0" --repo tests/fixtures/simple_repo
# Expected: prints TriageResult with issue_type=confirmed_bug (Orchestrator stub OK to raise NotImplementedError)
```
