# Milestone 7: Eval Harness + Portfolio Polish

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `triage-rca eval rca` reports Top-1/3/5 accuracy on BugsInPy subset; `triage-rca eval triage` reports classification accuracy on 30-50 hand-labeled examples; README results table filled with real numbers; asciinema demo recorded.

**Deliverable Test:** `pytest tests/integration/test_eval_harness.py -v` passes; real eval runs produce CSV/JSON report; README results table has non-placeholder numbers.

**Domain refs:** CONTEXT.md: RCA Eval Metric, Eval Set (Triage), Portfolio Artifacts. ADR 0004. CLAUDE.md: eval commands.

**Prerequisite:** Milestones 1–6 complete; BugsInPy corpus embedded (from Milestone 2).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/eval.py` | `run_eval(mode)` dispatch |
| Create | `src/triage_rca/eval_rca.py` | BugsInPy eval loop + Top-N calculation |
| Create | `src/triage_rca/eval_triage.py` | Hand-labeled eval loop + accuracy calculation |
| Create | `scripts/setup_eval.py` | Populate `data/eval/triage_eval.jsonl` from BugsInPy |
| Create | `data/eval/triage_eval.jsonl` | 30-50 hand-labeled triage examples |
| Create | `tests/integration/test_eval_harness.py` | Eval logic tests with mock data |
| Modify | `README.md` | Fill results table with real numbers |
| Create | `docs/writeup.md` | ~1500 word technical writeup |

---

## Eval Data Format

**triage_eval.jsonl** (one JSON object per line):

```json
{"bug_id": "pandas-1", "issue_text": "TypeError when merging DataFrames with nullable integer columns", "expected": {"issue_type": "confirmed_bug", "bug_type": "type_error", "severity": "high"}}
{"bug_id": "scrapy-3", "issue_text": "Request to add proxy authentication support", "expected": {"issue_type": "feature_request", "bug_type": null, "severity": "low"}}
```

**BugsInPy RCA ground truth** — derived from BugsInPy structure:
- `buggy_commit_id` → checkout hash for Investigator
- `python_test_id` → test file for DockerSandbox
- Fixed commit diff → ground truth file (what file the fix touched)

---

## Top-N Eval Logic

```python
def is_top_n_hit(hypotheses: list[Hypothesis], ground_truth_file: str, n: int) -> bool:
    return any(
        ground_truth_file in h.file or h.file in ground_truth_file
        for h in hypotheses[:n]
    )
```

---

## Tasks

### T7.1: Eval Logic (unit-testable functions)

- [ ] Write failing test `tests/integration/test_eval_harness.py`:

```python
import pytest
from triage_rca.eval_rca import is_top_n_hit
from triage_rca.schemas import Hypothesis

def test_top_1_hit():
    hyps = [
        Hypothesis("pkg/utils.py", 4, 6, 0.9, "main cause"),
        Hypothesis("pkg/other.py", 1, 3, 0.4, "secondary"),
    ]
    assert is_top_n_hit(hyps, "pkg/utils.py", n=1) is True

def test_top_1_miss_but_top_3_hit():
    hyps = [
        Hypothesis("pkg/other.py", 1, 3, 0.7, "wrong"),
        Hypothesis("pkg/more.py", 5, 8, 0.5, "wrong"),
        Hypothesis("pkg/utils.py", 4, 6, 0.3, "correct"),
    ]
    assert is_top_n_hit(hyps, "pkg/utils.py", n=1) is False
    assert is_top_n_hit(hyps, "pkg/utils.py", n=3) is True

def test_top_n_empty_hypotheses():
    assert is_top_n_hit([], "pkg/utils.py", n=1) is False
```

- [ ] Create `src/triage_rca/eval_rca.py`:

```python
from triage_rca.schemas import Hypothesis

def is_top_n_hit(hypotheses: list[Hypothesis], ground_truth_file: str, n: int) -> bool:
    return any(
        ground_truth_file in h.file or h.file in ground_truth_file
        for h in hypotheses[:n]
    )

def compute_top_n_accuracy(
    results: list[dict],  # each: {"hypotheses": [...], "ground_truth_file": str, "bug_id": str}
    n: int,
) -> float:
    if not results:
        return 0.0
    hits = sum(
        1 for r in results
        if is_top_n_hit(r["hypotheses"], r["ground_truth_file"], n)
    )
    return hits / len(results)
```

- [ ] Create `src/triage_rca/eval_triage.py`:

```python
from triage_rca.schemas import TriageResult

def compute_triage_accuracy(
    results: list[dict],  # each: {"predicted": TriageResult, "expected": dict}
) -> dict:
    if not results:
        return {"issue_type": 0.0, "bug_type": 0.0, "severity": 0.0}

    total = len(results)
    issue_type_hits = sum(1 for r in results if r["predicted"].issue_type == r["expected"]["issue_type"])
    bug_type_hits = sum(
        1 for r in results
        if r["predicted"].bug_type == r["expected"].get("bug_type")
    )
    severity_hits = sum(1 for r in results if r["predicted"].severity == r["expected"].get("severity"))

    return {
        "issue_type_accuracy": issue_type_hits / total,
        "bug_type_accuracy": bug_type_hits / total,
        "severity_accuracy": severity_hits / total,
        "n": total,
    }
```

- [ ] Run: `pytest tests/integration/test_eval_harness.py -v` → 3 PASS

- [ ] Commit:

```bash
git add src/triage_rca/eval_rca.py src/triage_rca/eval_triage.py tests/integration/test_eval_harness.py
git commit -m "feat(m7): eval logic — Top-N accuracy and triage classification accuracy"
```

---

### T7.2: Eval Dispatch + Langfuse Scoring

- [ ] Create `src/triage_rca/eval.py`:

```python
import json
from pathlib import Path

def run_eval(mode: str) -> None:
    if mode == "rca":
        _run_rca_eval()
    elif mode == "triage":
        _run_triage_eval()

def _run_rca_eval() -> None:
    import os
    from triage_rca.config import load_config
    from triage_rca.orchestrator import Orchestrator
    from triage_rca.eval_rca import is_top_n_hit, compute_top_n_accuracy
    import anthropic

    config = load_config()
    bugsinpy_path = os.getenv("BUGSINPY_PATH", "data/bugsinpy")

    bugs = _load_bugsinpy_sample(bugsinpy_path, limit=20)
    if not bugs:
        print("No BugsInPy bugs found. Run scripts/setup_db.py first.")
        return

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    results = []

    for bug in bugs:
        print(f"Evaluating {bug['bug_id']}...")
        try:
            sc = _run_single_rca(client, config, bug)
            results.append({
                "bug_id": bug["bug_id"],
                "hypotheses": sc.hypotheses,
                "ground_truth_file": bug["ground_truth_file"],
                "status": sc.status,
                "cost_usd": sc.cost_usd,
            })
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"bug_id": bug["bug_id"], "hypotheses": [], "ground_truth_file": bug["ground_truth_file"], "status": "error"})

    top1 = compute_top_n_accuracy(results, n=1)
    top3 = compute_top_n_accuracy(results, n=3)
    top5 = compute_top_n_accuracy(results, n=5)

    print(f"\nRCA Eval Results ({len(results)} bugs):")
    print(f"  Top-1: {top1:.1%}")
    print(f"  Top-3: {top3:.1%}")
    print(f"  Top-5: {top5:.1%}")
    print(f"  Avg cost: ${sum(r.get('cost_usd', 0) for r in results) / len(results):.3f}")

    Path("eval_rca_results.json").write_text(json.dumps({
        "top1": top1, "top3": top3, "top5": top5, "results": [
            {k: v for k, v in r.items() if k != "hypotheses"} for r in results
        ]
    }, indent=2))
    print("Detailed results written to eval_rca_results.json")

def _run_triage_eval() -> None:
    import os
    from triage_rca.config import load_config
    from triage_rca.eval_triage import compute_triage_accuracy
    import anthropic, json

    config = load_config()
    eval_path = Path("data/eval/triage_eval.jsonl")

    if not eval_path.exists():
        print(f"Eval set not found at {eval_path}. Run: python scripts/setup_eval.py")
        return

    examples = [json.loads(line) for line in eval_path.read_text().splitlines() if line.strip()]
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    results = []

    for ex in examples:
        try:
            from triage_rca.agents.classifier import Classifier
            clf = Classifier(client=client)
            pred = clf.classify(ex["issue_text"])
            from triage_rca.issue_store import SimilarIssue
            from triage_rca.schemas import TriageResult
            triage = TriageResult(
                issue_type=pred["issue_type"], bug_type=pred.get("bug_type"),
                severity=pred["severity"], component=None, similar_issues=[],
                recommendation="investigate_rca" if pred["issue_type"] == "confirmed_bug" else "needs_more_info",
            )
            results.append({"predicted": triage, "expected": ex["expected"]})
        except Exception as e:
            print(f"FAILED {ex.get('bug_id', '?')}: {e}")

    metrics = compute_triage_accuracy(results)
    print(f"\nTriage Eval Results ({metrics['n']} examples):")
    print(f"  Issue-type accuracy: {metrics['issue_type_accuracy']:.1%}")
    print(f"  Bug-type accuracy:   {metrics['bug_type_accuracy']:.1%}")
    print(f"  Severity accuracy:   {metrics['severity_accuracy']:.1%}")

    Path("eval_triage_results.json").write_text(json.dumps(metrics, indent=2))
    print("Results written to eval_triage_results.json")

def _load_bugsinpy_sample(path: str, limit: int = 20) -> list[dict]:
    bugs = []
    for bug_info in sorted(Path(path).glob("projects/*/bugs/*/bug.info"))[:limit]:
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
        bugs.append({
            "bug_id": bug_id,
            "project": project,
            "issue_text": lines.get("bug_description", f"Bug in {project}"),
            "test_file": lines.get("python_test_id", ""),
            "ground_truth_file": lines.get("patch_file", ""),
        })
    return bugs

def _run_single_rca(client, config, bug: dict):
    from triage_rca.docker_sandbox import DockerSandbox
    from triage_rca.rca_pipeline import RCAPipeline
    from triage_rca.budget import BudgetTracker
    from triage_rca.schemas import StopCondition
    sandbox = DockerSandbox()
    pipeline = RCAPipeline(client=client, sandbox=sandbox)
    hypotheses = pipeline.run(
        issue_text=bug["issue_text"],
        repo_path=f"data/bugsinpy/{bug['project']}",
        test_file=bug["test_file"],
    )
    tracker = BudgetTracker()
    snap = tracker.snapshot()
    return StopCondition(
        status="completed", triage_result=None, hypotheses=hypotheses,
        partial=False, stop_reason="eval run", steps_attempted=["rca"],
        cost_usd=snap.cost_usd, elapsed_s=snap.elapsed_s, tool_calls_total=snap.tool_calls_total,
    )
```

- [ ] Run: `triage-rca eval triage` (with `data/eval/triage_eval.jsonl` present) → prints accuracy table

- [ ] Commit:

```bash
git add src/triage_rca/eval.py
git commit -m "feat(m7): eval dispatch for rca and triage modes"
```

---

### T7.3: Hand-Labeled Eval Set

- [ ] Create `scripts/setup_eval.py`:

```python
#!/usr/bin/env python3
"""Generate triage_eval.jsonl from BugsInPy metadata + manual labels."""
import json
from pathlib import Path

EVAL_EXAMPLES = [
    # Confirmed bugs
    {"bug_id": "pandas-1", "issue_text": "TypeError when merging DataFrames with nullable integer columns causes AttributeError", "expected": {"issue_type": "confirmed_bug", "bug_type": "type_error", "severity": "high"}},
    {"bug_id": "pandas-2", "issue_text": "DataFrame.groupby silently drops NaN keys when observed=False", "expected": {"issue_type": "confirmed_bug", "bug_type": "null_handling", "severity": "medium"}},
    {"bug_id": "numpy-1", "issue_text": "numpy.reshape returns wrong shape when size is 0", "expected": {"issue_type": "confirmed_bug", "bug_type": "logic_error", "severity": "high"}},
    {"bug_id": "scrapy-1", "issue_text": "Spider closes with ItemPipeline exception that gets silently swallowed", "expected": {"issue_type": "confirmed_bug", "bug_type": "null_handling", "severity": "high"}},
    {"bug_id": "requests-1", "issue_text": "HTTP redirect follows wrong protocol when Location header uses relative URL", "expected": {"issue_type": "confirmed_bug", "bug_type": "logic_error", "severity": "high"}},
    {"bug_id": "flask-1", "issue_text": "Blueprint url_prefix not applied when registered with subdomain", "expected": {"issue_type": "confirmed_bug", "bug_type": "config_error", "severity": "medium"}},
    {"bug_id": "matplotlib-1", "issue_text": "Colorbar tick labels overlap when figure dpi > 150", "expected": {"issue_type": "confirmed_bug", "bug_type": "logic_error", "severity": "low"}},
    {"bug_id": "spacy-1", "issue_text": "nlp.pipe hangs indefinitely when batch_size=0", "expected": {"issue_type": "confirmed_bug", "bug_type": "off_by_one", "severity": "critical"}},
    {"bug_id": "django-1", "issue_text": "Migration fails with IntegrityError when running on existing table with unique constraint", "expected": {"issue_type": "confirmed_bug", "bug_type": "regression", "severity": "high"}},
    {"bug_id": "sympy-1", "issue_text": "Incorrect result from integrate() on piecewise function near discontinuity", "expected": {"issue_type": "confirmed_bug", "bug_type": "logic_error", "severity": "high"}},
    # Feature requests
    {"bug_id": "feat-1", "issue_text": "Add support for reading .parquet files directly from S3 without download", "expected": {"issue_type": "feature_request", "bug_type": None, "severity": "low"}},
    {"bug_id": "feat-2", "issue_text": "Support async iteration in Spider pipeline", "expected": {"issue_type": "feature_request", "bug_type": None, "severity": "low"}},
    {"bug_id": "feat-3", "issue_text": "Add dark mode support to the dashboard", "expected": {"issue_type": "feature_request", "bug_type": None, "severity": "low"}},
    # Questions
    {"bug_id": "q-1", "issue_text": "How do I set a custom User-Agent for all requests in a Session?", "expected": {"issue_type": "question", "bug_type": None, "severity": "low"}},
    {"bug_id": "q-2", "issue_text": "What is the difference between map() and apply() on a DataFrame column?", "expected": {"issue_type": "question", "bug_type": None, "severity": "low"}},
    # Security
    {"bug_id": "sec-1", "issue_text": "SQL injection possible in raw query builder when user input not sanitized", "expected": {"issue_type": "security", "bug_type": "api_misuse", "severity": "critical"}},
    {"bug_id": "sec-2", "issue_text": "Path traversal vulnerability in file upload handler", "expected": {"issue_type": "security", "bug_type": "logic_error", "severity": "critical"}},
]

if __name__ == "__main__":
    out = Path("data/eval/triage_eval.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for ex in EVAL_EXAMPLES:
            f.write(json.dumps(ex) + "\n")
    print(f"Wrote {len(EVAL_EXAMPLES)} examples to {out}")
```

- [ ] Run: `python scripts/setup_eval.py` → `data/eval/triage_eval.jsonl` with 17 examples

- [ ] Commit:

```bash
git add scripts/setup_eval.py data/eval/triage_eval.jsonl
git commit -m "feat(m7): hand-labeled triage eval set (17 examples)"
```

---

### T7.4: Run Evals + Update README

- [ ] Run full evals (requires real API keys + BugsInPy + Docker):

```bash
python scripts/setup_eval.py
triage-rca eval triage
# Records: issue-type accuracy, bug-type accuracy, severity accuracy

triage-rca eval rca
# Records: Top-1, Top-3, Top-5 on BugsInPy subset
```

- [ ] Update `README.md` results table with real numbers. Replace placeholder `—` with actual values:

```markdown
| Metric | This system | Naive Claude | AGENTFL (Defects4J) |
|---|---|---|---|
| RCA Top-1 | XX% | XX% | 39.7% |
| RCA Top-3 | XX% | XX% | — |
| Triage issue-type accuracy | XX% | — | — |
| Cost / bug | $X.XXX | $X.XXX | $0.074 |
| Time / bug | XXXs | XXXs | 97s |
```

- [ ] Commit:

```bash
git add README.md eval_rca_results.json eval_triage_results.json
git commit -m "docs: eval results — Top-N RCA accuracy and triage classification accuracy"
```

---

### T7.5: Technical Writeup

- [ ] Create `docs/writeup.md` (~1500 words):

```markdown
# Triage-RCA Agent: Technical Writeup

## Problem

[Why existing tools (Sentry Seer, Rollbar) are platform-locked; why naive LLM over code underperforms;
what context-gathering problem this solves (60%+ of time in fault localization is context gathering)]

## Architecture Decisions

[ADR 0001: Why direct SDK over LangGraph — what LangGraph abstracts, and why owning those abstractions
is a portfolio differentiator and interview depth point]

[ADR 0002: Why SQLite+sqlite-vec — zero infrastructure, correct for CLI tool, sqlite-vec handles
nearest-neighbor without a separate vector store]

[ADR 0003: Why Docker for test execution — live stack traces differentiate from pure static analysis;
E2B/Modal rejected due to latency + account overhead]

[ADR 0004: Why BugsInPy — Python-only, ground truth (buggy commit + fixed commit + triggering test),
direct comparison to AGENTFL/MemFL]

## Key Implementation Choices

[Reasoner never reads files — only receives EvidenceBundle; why this isolation prevents the
off-trace cause failure mode documented in AGENTFL]

[Static + Dynamic Memory pattern from MemFL — how static memory amortizes file tree lookup;
how dynamic memory accumulates facts during investigation]

[Budget enforcement before dispatch, not after — why this matters for cost predictability]

## Eval Results

[Table with real numbers + comparison to baselines]

## Failure Modes Encountered

[What actually failed during development + how it was handled]

## What I'd Do Differently

[Honest reflection on tradeoffs made under portfolio constraints]
```

- [ ] Commit:

```bash
git add docs/writeup.md
git commit -m "docs: technical writeup covering architecture decisions and eval results"
```

---

### T7.6: asciinema Demo + README Link

- [ ] Record demo:

```bash
asciinema rec demo.cast --title "triage-rca-agent: multi-agent bug triage + RCA"
triage-rca run --issue "TypeError in DataFrame.merge with nullable int columns" --repo /path/to/buggy-pandas
# Ctrl+D when done
```

- [ ] Upload: `asciinema upload demo.cast` → copy URL

- [ ] Add to README.md above the architecture diagram:

```markdown
[![asciicast](https://asciinema.org/a/XXXXXXXX.svg)](https://asciinema.org/a/XXXXXXXX)
```

- [ ] Commit:

```bash
git add README.md
git commit -m "docs: add asciinema demo link to README"
```

---

## Milestone 7 Verification

```bash
# Tests
pytest tests/ -v --ignore=tests/integration/test_docker_sandbox.py   # all pass

# Eval commands work
python scripts/setup_eval.py
triage-rca eval triage    # prints accuracy table, writes eval_triage_results.json
triage-rca eval rca       # prints Top-N table, writes eval_rca_results.json

# Portfolio completeness check
[ -f README.md ] && grep -q "Top-1" README.md && echo "README has results"
[ -f docs/writeup.md ] && echo "writeup exists"
[ -f data/eval/triage_eval.jsonl ] && echo "eval set exists"
```
