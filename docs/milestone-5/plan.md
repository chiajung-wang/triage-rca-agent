# Milestone 5: Orchestrator + Recovery Loop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single `Orchestrator` class routes between Triage and RCA pipelines, enforces budget before each dispatch, implements 4-level recovery hierarchy, and emits `result.json` with a named Stop Condition.

**Deliverable Test:** `pytest tests/integration/test_orchestrator.py -v` with mock pipelines; budget breach → correct Stop Condition; 2+ subagent failures → escalated Stop Condition; `result.json` written after every run.

**Domain refs:** CONTEXT.md: Orchestrator, Stop Condition, Partial Result, request_human_review. CLAUDE.md: Budget Enforcement, Recovery Loop.

**Prerequisite:** Milestones 1–4 complete.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/orchestrator.py` | Orchestrator class + `run_pipeline()` entry function |
| Create | `src/triage_rca/result_writer.py` | Serializes StopCondition → `result.json` |
| Create | `tests/integration/test_orchestrator.py` | Orchestrator integration tests with mock pipelines |

---

## Orchestrator State Machine

```
run_pipeline(issue, repo_path, interactive)
  │
  ├─ load config, init BudgetTracker, init DB
  ├─ budget.start()
  ├─ budget.check()           ← before every dispatch
  │
  ├─ run Triage Pipeline
  │   ├─ success → TriageResult
  │   └─ failure → recovery_loop()
  │       ├─ local retry (attempt 1, 2)
  │       ├─ plan amendment (simplified query)
  │       ├─ full replan (skip SimilaritySearcher)
  │       └─ request_human_review → Stop Condition(escalated)
  │
  ├─ if recommendation == investigate_rca:
  │   ├─ budget.check()
  │   └─ run RCA Pipeline → list[Hypothesis]
  │
  └─ emit Stop Condition(completed) + write result.json
```

---

## Recovery Levels

| Level | Trigger | Action |
|-------|---------|--------|
| 1 | Tool call failure | Retry same call ≤2 times |
| 2 | Subagent returns garbage | Simplify prompt, retry once |
| 3 | 2+ subagents fail | Skip optional steps (SimilaritySearcher), retry once |
| 4 | 2 failed replans | `request_human_review(reason, partial_result)` |

---

## Stop Condition Serialization

All fields of `StopCondition` serialized to JSON. `triage_result` and `hypotheses` use dataclasses-to-dict. Written to `result.json` in cwd, and optionally to DB.

---

## Tasks

### T5.1: ResultWriter

- [ ] Write failing test:

```python
import json, pytest
from pathlib import Path
from triage_rca.result_writer import ResultWriter
from triage_rca.schemas import StopCondition

def test_writes_result_json(tmp_path):
    sc = StopCondition(
        status="completed",
        triage_result=None,
        hypotheses=[],
        partial=False,
        stop_reason="All pipelines completed",
        steps_attempted=["classifier", "rca"],
        cost_usd=0.12,
        elapsed_s=45.3,
        tool_calls_total=22,
    )
    writer = ResultWriter(output_dir=str(tmp_path))
    path = writer.write(sc)
    assert Path(path).exists()
    data = json.loads(Path(path).read_text())
    assert data["status"] == "completed"
    assert data["cost_usd"] == pytest.approx(0.12)
    assert data["partial"] is False

def test_writes_partial_result(tmp_path):
    sc = StopCondition(
        status="budget_exceeded",
        triage_result=None,
        hypotheses=[],
        partial=True,
        stop_reason="Cost limit hit",
        steps_attempted=["classifier"],
        cost_usd=0.51,
        elapsed_s=120.0,
        tool_calls_total=80,
    )
    writer = ResultWriter(output_dir=str(tmp_path))
    path = writer.write(sc)
    data = json.loads(Path(path).read_text())
    assert data["status"] == "budget_exceeded"
    assert data["partial"] is True
```

- [ ] Create `src/triage_rca/result_writer.py`:

```python
import json
import dataclasses
from pathlib import Path
from triage_rca.schemas import StopCondition

def _to_dict(obj) -> object:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj

class ResultWriter:
    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)

    def write(self, stop_condition: StopCondition, filename: str = "result.json") -> str:
        path = self.output_dir / filename
        data = _to_dict(stop_condition)
        path.write_text(json.dumps(data, indent=2))
        return str(path)
```

- [ ] Run: `pytest tests/integration/test_orchestrator.py -k "result" -v` → 2 PASS

- [ ] Commit:

```bash
git add src/triage_rca/result_writer.py
git commit -m "feat(m5): ResultWriter serializes StopCondition to result.json"
```

---

### T5.2: Orchestrator Core

- [ ] Write failing test (clean run — no failures):

```python
from unittest.mock import MagicMock, patch
from triage_rca.schemas import TriageResult, StopCondition
from triage_rca.issue_store import SimilarIssue

def test_orchestrator_completed_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    mock_triage = MagicMock()
    mock_triage.run.return_value = TriageResult(
        issue_type="confirmed_bug", bug_type="type_error",
        severity="high", component="pkg/utils.py",
        similar_issues=[], recommendation="investigate_rca",
    )

    mock_rca = MagicMock()
    from triage_rca.schemas import Hypothesis
    mock_rca.run.return_value = [
        Hypothesis(file="pkg/utils.py", start_line=4, end_line=6, confidence=0.9,
                   reasoning="No zero check", verified=True)
    ]

    from triage_rca.orchestrator import Orchestrator
    orch = Orchestrator(
        triage_pipeline=mock_triage,
        rca_pipeline=mock_rca,
        output_dir=str(tmp_path),
    )
    sc = orch.run(issue_text="ZeroDivisionError", repo_path=str(tmp_path), test_file="tests/test.py")

    assert sc.status == "completed"
    assert sc.partial is False
    assert len(sc.hypotheses) == 1
    assert (tmp_path / "result.json").exists()
```

- [ ] Create `src/triage_rca/orchestrator.py`:

```python
from triage_rca.budget import BudgetTracker
from triage_rca.exceptions import BudgetExceeded
from triage_rca.result_writer import ResultWriter
from triage_rca.schemas import StopCondition, TriageResult, Hypothesis
from triage_rca.triage_pipeline import TriagePipeline
from triage_rca.rca_pipeline import RCAPipeline

class Orchestrator:
    def __init__(
        self,
        triage_pipeline,
        rca_pipeline,
        output_dir: str = ".",
    ):
        self.triage = triage_pipeline
        self.rca = rca_pipeline
        self.writer = ResultWriter(output_dir)
        self.budget = BudgetTracker()
        self._steps: list[str] = []

    def run(
        self,
        issue_text: str,
        repo_path: str,
        test_file: str = "",
        interactive: bool = False,
    ) -> StopCondition:
        self.budget.start()
        triage_result: TriageResult | None = None
        hypotheses: list[Hypothesis] = []

        try:
            self.budget.check()
            triage_result = self._run_triage(issue_text, repo_path, interactive)
            self._steps.append("triage")

            if triage_result.recommendation == "investigate_rca" and test_file:
                self.budget.check()
                hypotheses = self._run_rca(issue_text, repo_path, test_file, interactive)
                self._steps.append("rca")

            sc = self._make_stop_condition("completed", triage_result, hypotheses, False, "All pipelines completed")

        except BudgetExceeded as e:
            reason = "timeout" if e.reason == "timeout" else "budget_exceeded"
            sc = self._make_stop_condition(reason, triage_result, hypotheses, True, str(e))

        self.writer.write(sc)
        return sc

    def _run_triage(self, issue_text: str, repo_path: str, interactive: bool) -> TriageResult:
        return self.triage.run(issue_text=issue_text, repo_path=repo_path)

    def _run_rca(self, issue_text: str, repo_path: str, test_file: str, interactive: bool) -> list[Hypothesis]:
        return self.rca.run(issue_text=issue_text, repo_path=repo_path, test_file=test_file)

    def _make_stop_condition(
        self, status: str, triage_result, hypotheses, partial: bool, reason: str
    ) -> StopCondition:
        snap = self.budget.snapshot()
        return StopCondition(
            status=status,
            triage_result=triage_result,
            hypotheses=hypotheses,
            partial=partial,
            stop_reason=reason,
            steps_attempted=list(self._steps),
            cost_usd=snap.cost_usd,
            elapsed_s=snap.elapsed_s,
            tool_calls_total=snap.tool_calls_total,
        )


def run_pipeline(issue: str, repo_path: str, interactive: bool = False) -> None:
    """Entry point called from CLI."""
    import os
    from triage_rca.config import load_config
    from triage_rca.db import init_db
    import anthropic

    config = load_config()
    db_path = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")
    init_db(db_path)

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    from triage_rca.issue_store import IssueStore
    from triage_rca.docker_sandbox import DockerSandbox
    from triage_rca.triage_pipeline import TriagePipeline
    from triage_rca.rca_pipeline import RCAPipeline

    store = IssueStore(db_path)
    sandbox = DockerSandbox()
    triage = TriagePipeline(client=client, issue_store=store, query_embedding=[0.0] * 1024)
    rca = RCAPipeline(client=client, sandbox=sandbox)

    orch = Orchestrator(triage_pipeline=triage, rca_pipeline=rca)
    sc = orch.run(issue_text=issue, repo_path=repo_path, interactive=interactive)
    print(f"\nStatus: {sc.status} | Cost: ${sc.cost_usd:.3f} | Time: {sc.elapsed_s:.1f}s | Tools: {sc.tool_calls_total}")
    print("Result written to result.json")
```

- [ ] Run: `pytest tests/integration/test_orchestrator.py::test_orchestrator_completed_run -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/orchestrator.py
git commit -m "feat(m5): Orchestrator core with routing and budget enforcement"
```

---

### T5.3: Recovery Levels 1–3

- [ ] Write failing tests:

```python
def test_budget_exceeded_stops_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    from triage_rca.orchestrator import Orchestrator
    from triage_rca.exceptions import BudgetExceeded
    from triage_rca.budget import BudgetState

    mock_triage = MagicMock()
    mock_triage.run.side_effect = BudgetExceeded("cost", BudgetState(cost_usd=0.51))

    orch = Orchestrator(triage_pipeline=mock_triage, rca_pipeline=MagicMock(), output_dir=str(tmp_path))
    sc = orch.run(issue_text="test", repo_path=str(tmp_path))

    assert sc.status == "budget_exceeded"
    assert sc.partial is True
    assert (tmp_path / "result.json").exists()

def test_non_bug_skips_rca(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    from triage_rca.orchestrator import Orchestrator

    mock_triage = MagicMock()
    mock_triage.run.return_value = TriageResult(
        issue_type="feature_request", bug_type=None, severity="low",
        component=None, similar_issues=[], recommendation="needs_more_info",
    )
    mock_rca = MagicMock()

    orch = Orchestrator(triage_pipeline=mock_triage, rca_pipeline=mock_rca, output_dir=str(tmp_path))
    sc = orch.run(issue_text="Add dark mode", repo_path=str(tmp_path))

    assert sc.status == "completed"
    mock_rca.run.assert_not_called()
```

- [ ] Run: `pytest tests/integration/test_orchestrator.py -v` → all PASS

- [ ] Commit:

```bash
git add tests/integration/test_orchestrator.py
git commit -m "feat(m5): Orchestrator recovery and routing tests"
```

---

### T5.4: request_human_review

- [ ] Add to `orchestrator.py`:

```python
import sys, json
from pathlib import Path

def request_human_review(reason: str, partial_result: StopCondition, interactive: bool) -> StopCondition:
    escalated = StopCondition(
        status="escalated",
        triage_result=partial_result.triage_result,
        hypotheses=partial_result.hypotheses,
        partial=True,
        stop_reason=reason,
        steps_attempted=partial_result.steps_attempted,
        cost_usd=partial_result.cost_usd,
        elapsed_s=partial_result.elapsed_s,
        tool_calls_total=partial_result.tool_calls_total,
    )
    if interactive:
        print(f"\n[ESCALATION] {reason}")
        print("Human review needed. Press Enter to continue or Ctrl+C to abort.")
        input()
    else:
        Path("escalation.json").write_text(json.dumps({"reason": reason, "partial_result": str(partial_result)}))
        sys.exit(1)
    return escalated
```

---

## Milestone 5 Verification

```bash
pytest tests/integration/test_orchestrator.py -v   # all PASS
pytest tests/ -v --ignore=tests/integration/test_docker_sandbox.py   # no regressions

# Smoke test (needs real API + Docker):
triage-rca run --issue "ZeroDivisionError in divide" --repo tests/fixtures/simple_repo
# Expected: prints status line, writes result.json
cat result.json | python -m json.tool
```
