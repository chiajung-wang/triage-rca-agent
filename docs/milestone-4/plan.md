# Milestone 4: RCA Pipeline + Docker Sandbox

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a confirmed bug + repo, Investigator collects an EvidenceBundle (static memory, dynamic memory, live stack trace via Docker), Reasoner ranks Hypotheses, Verifier confirms top Hypothesis.

**Deliverable Test:** `pytest tests/integration/test_rca_pipeline.py -v` passes with mock Docker + mock Anthropic client; DockerSandbox integration test runs real container.

**Domain refs:** CONTEXT.md: Investigator, Reasoner, Verifier, Evidence Bundle, Static Memory, Dynamic Memory, Docker Sandbox, Hypothesis. ADR 0003 (Docker sandbox).

**Prerequisite:** Milestones 1–3 complete.

**Key invariant:** Reasoner never reads files directly — EvidenceBundle is its sole input.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/triage_rca/docker_sandbox.py` | Spin up container, run pytest, return TestResult |
| Create | `src/triage_rca/memory_manager.py` | build_static_memory(repo_path) → StaticMemory |
| Create | `src/triage_rca/agents/investigator.py` | Builds EvidenceBundle via tools + Docker |
| Create | `src/triage_rca/agents/reasoner.py` | EvidenceBundle → ranked list[Hypothesis] |
| Create | `src/triage_rca/agents/verifier.py` | Top Hypothesis → verified/demoted |
| Create | `src/triage_rca/rca_pipeline.py` | Orchestrates Investigator → Reasoner → Verifier |
| Create | `tests/integration/test_docker_sandbox.py` | Real Docker integration tests (mark: integration) |
| Create | `tests/integration/test_rca_pipeline.py` | RCA pipeline tests with mocks |
| Modify | `tests/fixtures/simple_repo/` | Add bug.py with known defect for RCA test |

---

## Tasks

### T4.1: DockerSandbox

- [ ] Write failing test `tests/integration/test_docker_sandbox.py`:

```python
import pytest
from triage_rca.docker_sandbox import DockerSandbox

@pytest.mark.integration
def test_run_passing_test(tmp_path):
    (tmp_path / "test_pass.py").write_text("def test_ok(): assert 1 == 1\n")
    sandbox = DockerSandbox()
    result = sandbox.run_test(str(tmp_path), "test_pass.py")
    assert result.exit_code == 0
    assert "passed" in result.stdout

@pytest.mark.integration
def test_run_failing_test(tmp_path):
    (tmp_path / "test_fail.py").write_text("def test_bad(): assert 1 == 2\n")
    sandbox = DockerSandbox()
    result = sandbox.run_test(str(tmp_path), "test_fail.py")
    assert result.exit_code != 0

@pytest.mark.integration
def test_timeout_returns_timeout_result(tmp_path):
    (tmp_path / "test_hang.py").write_text("import time\ndef test_hang(): time.sleep(999)\n")
    sandbox = DockerSandbox(timeout_s=5)
    result = sandbox.run_test(str(tmp_path), "test_hang.py")
    assert result.exit_code != 0
    assert result.elapsed_s >= 5
```

- [ ] Run to confirm failure: `pytest tests/integration/test_docker_sandbox.py -v -m integration`

- [ ] Create `src/triage_rca/docker_sandbox.py`:

```python
import subprocess
import time
from triage_rca.schemas import TestResult

class DockerSandbox:
    def __init__(self, image: str = "python:3.11-slim", timeout_s: int = 60):
        self.image = image
        self.timeout_s = timeout_s

    def run_test(self, repo_path: str, test_file: str, commit_sha: str | None = None) -> TestResult:
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "-v", f"{repo_path}:/repo:ro",
            "-w", "/repo",
            self.image,
            "sh", "-c",
            f"pip install pytest -q --no-cache-dir 2>/dev/null && python -m pytest {test_file} -v 2>&1",
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout_s
            )
        except subprocess.TimeoutExpired:
            return TestResult(stdout="", stderr="Timeout", exit_code=1, elapsed_s=self.timeout_s)
        elapsed = time.monotonic() - start
        return TestResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            elapsed_s=elapsed,
        )
```

- [ ] Run: `pytest tests/integration/test_docker_sandbox.py -v -m integration` → 3 PASS

- [ ] Commit:

```bash
git add src/triage_rca/docker_sandbox.py tests/integration/test_docker_sandbox.py
git commit -m "feat(m4): DockerSandbox for isolated test execution"
```

---

### T4.2: MemoryManager

- [ ] Write failing test in `tests/integration/test_rca_pipeline.py`:

```python
import pytest
from pathlib import Path
from triage_rca.memory_manager import build_static_memory

def test_build_static_memory(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "utils.py").write_text("def foo(): pass\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_utils.py").write_text("def test_foo(): pass\n")

    mem = build_static_memory(str(tmp_path), test_file="tests/test_utils.py")
    assert "pkg/utils.py" in mem.file_tree
    assert "tests/test_utils.py" in mem.file_tree
    assert mem.test_file == "tests/test_utils.py"
    assert "pkg.utils" in mem.module_index
```

- [ ] Create `src/triage_rca/memory_manager.py`:

```python
from pathlib import Path
from triage_rca.schemas import StaticMemory

def build_static_memory(repo_path: str, test_file: str) -> StaticMemory:
    root = Path(repo_path)
    file_tree = sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if ".git" not in str(p)
    )
    module_index = {}
    for f in file_tree:
        if "__init__" not in f:
            module_name = f.replace("/", ".").removesuffix(".py")
            module_index[module_name] = f
    return StaticMemory(
        file_tree=file_tree,
        module_index=module_index,
        test_file=test_file,
    )
```

- [ ] Run: `pytest tests/integration/test_rca_pipeline.py::test_build_static_memory -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/memory_manager.py
git commit -m "feat(m4): MemoryManager building StaticMemory from repo file tree"
```

---

### T4.3: Investigator Subagent

The Investigator:
1. Calls `build_static_memory(repo_path, test_file)`
2. Runs `DockerSandbox.run_test(repo_path, test_file)` to get live stack trace
3. Uses LLM with file-read context to identify relevant code snippets
4. Accumulates DynamicMemory
5. Returns EvidenceBundle

- [ ] Write failing test:

```python
from unittest.mock import MagicMock, patch
import json

def test_investigator_builds_evidence_bundle(tmp_path):
    import shutil
    from pathlib import Path
    shutil.copytree(Path("tests/fixtures/simple_repo"), tmp_path / "repo")

    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock()]
    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "relevant_files": ["mypackage/utils.py"],
        "stack_frames": ["mypackage/utils.py:5 in divide"],
        "call_path": ["test_utils.py:4 -> divide"],
        "ruled_out": [],
        "code_snippets": [{"file": "mypackage/utils.py", "start_line": 4, "end_line": 6, "content": "def divide(a, b):\n    return a / b\n"}]
    })

    mock_sandbox = MagicMock()
    from triage_rca.schemas import TestResult
    mock_sandbox.run_test.return_value = TestResult(
        stdout="FAILED tests/test_utils.py::test_divide_by_zero\nZeroDivisionError: division by zero",
        stderr="",
        exit_code=1,
        elapsed_s=2.1,
    )

    from triage_rca.agents.investigator import Investigator
    inv = Investigator(client=mock_client, sandbox=mock_sandbox)
    bundle = inv.investigate(
        issue_text="ZeroDivisionError in divide",
        repo_path=str(tmp_path / "repo"),
        test_file="tests/test_utils.py",
    )

    assert bundle.test_result.exit_code == 1
    assert "ZeroDivisionError" in bundle.test_result.stdout
    assert len(bundle.dynamic_memory.relevant_files) > 0
    assert len(bundle.code_snippets) > 0
```

- [ ] Create `src/triage_rca/agents/investigator.py`:

```python
import json
import anthropic
from triage_rca.docker_sandbox import DockerSandbox
from triage_rca.memory_manager import build_static_memory
from triage_rca.schemas import EvidenceBundle, DynamicMemory, CodeSnippet

SYSTEM_PROMPT = (
    "You are a code investigator. Given a bug description, file tree, and failing test output, "
    "identify the relevant files, stack frames, call path, and code snippets that explain the bug. "
    "Output JSON with: relevant_files (list of paths), stack_frames (list of strings), "
    "call_path (list of strings), ruled_out (list of paths), "
    "code_snippets (list of {file, start_line, end_line, content}). "
    "Respond ONLY with valid JSON."
)

class Investigator:
    def __init__(self, client: anthropic.Anthropic, sandbox: DockerSandbox):
        self.client = client
        self.sandbox = sandbox

    def investigate(self, issue_text: str, repo_path: str, test_file: str) -> EvidenceBundle:
        static_mem = build_static_memory(repo_path, test_file)
        test_result = self.sandbox.run_test(repo_path, test_file)

        prompt = (
            f"Bug description: {issue_text}\n\n"
            f"File tree:\n{chr(10).join(static_mem.file_tree[:50])}\n\n"
            f"Test output:\n{test_result.stdout[:2000]}\n{test_result.stderr[:500]}"
        )
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text)

        dynamic_mem = DynamicMemory(
            relevant_files=data.get("relevant_files", []),
            stack_frames=data.get("stack_frames", []),
            call_path=data.get("call_path", []),
            ruled_out=data.get("ruled_out", []),
        )
        snippets = [
            CodeSnippet(
                file=s["file"], start_line=s["start_line"],
                end_line=s["end_line"], content=s["content"],
            )
            for s in data.get("code_snippets", [])
        ]
        return EvidenceBundle(
            static_memory=static_mem,
            dynamic_memory=dynamic_mem,
            code_snippets=snippets,
            test_result=test_result,
        )
```

- [ ] Run: `pytest tests/integration/test_rca_pipeline.py::test_investigator_builds_evidence_bundle -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/investigator.py
git commit -m "feat(m4): Investigator subagent building EvidenceBundle with Docker + LLM"
```

---

### T4.4: Reasoner Subagent

Reasoner receives EvidenceBundle as sole input (no file access). Returns ranked `list[Hypothesis]`.

- [ ] Write failing test:

```python
def test_reasoner_returns_ranked_hypotheses(mock_client):
    from triage_rca.schemas import EvidenceBundle, StaticMemory, DynamicMemory, TestResult, CodeSnippet
    from triage_rca.agents.reasoner import Reasoner

    bundle = EvidenceBundle(
        static_memory=StaticMemory(file_tree=["pkg/utils.py"], module_index={}, test_file="tests/test_utils.py"),
        dynamic_memory=DynamicMemory(relevant_files=["pkg/utils.py"], stack_frames=["pkg/utils.py:5"]),
        code_snippets=[CodeSnippet(file="pkg/utils.py", start_line=4, end_line=6, content="def divide(a,b): return a/b")],
        test_result=TestResult(stdout="ZeroDivisionError", stderr="", exit_code=1, elapsed_s=1.0),
    )

    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "hypotheses": [
            {"file": "pkg/utils.py", "start_line": 4, "end_line": 6, "confidence": 0.91, "reasoning": "No zero check"},
        ]
    })

    reasoner = Reasoner(client=mock_client)
    hypotheses = reasoner.reason(bundle)
    assert len(hypotheses) == 1
    assert hypotheses[0].file == "pkg/utils.py"
    assert hypotheses[0].confidence == pytest.approx(0.91)
```

- [ ] Create `src/triage_rca/agents/reasoner.py`:

```python
import json
import anthropic
from triage_rca.schemas import EvidenceBundle, Hypothesis

SYSTEM_PROMPT = (
    "You are a root cause analyst. Given an evidence bundle (code snippets, stack trace, test output), "
    "produce a ranked list of hypotheses for the root cause. "
    "Output JSON: {\"hypotheses\": [{\"file\": \"...\", \"start_line\": N, \"end_line\": N, "
    "\"confidence\": 0.0-1.0, \"reasoning\": \"one sentence\"}]}. "
    "Order by confidence descending. Max 5 hypotheses. Respond ONLY with valid JSON."
)

class Reasoner:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def reason(self, bundle: EvidenceBundle) -> list[Hypothesis]:
        snippets_text = "\n\n".join(
            f"File: {s.file} lines {s.start_line}-{s.end_line}\n{s.content}"
            for s in bundle.code_snippets
        )
        prompt = (
            f"Test output:\n{bundle.test_result.stdout[:2000]}\n\n"
            f"Stack frames: {bundle.dynamic_memory.stack_frames}\n\n"
            f"Relevant code:\n{snippets_text}"
        )
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text)
        return [
            Hypothesis(
                file=h["file"], start_line=h["start_line"], end_line=h["end_line"],
                confidence=h["confidence"], reasoning=h["reasoning"],
            )
            for h in data.get("hypotheses", [])
        ]
```

- [ ] Run: `pytest tests/integration/test_rca_pipeline.py::test_reasoner_returns_ranked_hypotheses -v` → PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/reasoner.py
git commit -m "feat(m4): Reasoner subagent — EvidenceBundle to ranked Hypothesis list"
```

---

### T4.5: Verifier Subagent

- [ ] Write failing test:

```python
def test_verifier_confirms_hypothesis(mock_client):
    from triage_rca.schemas import Hypothesis, TestResult
    from triage_rca.agents.verifier import Verifier

    h = Hypothesis(file="pkg/utils.py", start_line=4, end_line=6, confidence=0.91, reasoning="No zero check")
    test_result = TestResult(stdout="ZeroDivisionError at utils.py:5", stderr="", exit_code=1, elapsed_s=1.0)

    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "verified": True, "reasoning": "Stack trace points to line 5 in utils.py"
    })

    verifier = Verifier(client=mock_client)
    verified_h = verifier.verify(h, test_result)
    assert verified_h.verified is True

def test_verifier_demotes_hypothesis(mock_client):
    from triage_rca.schemas import Hypothesis, TestResult
    from triage_rca.agents.verifier import Verifier

    h = Hypothesis(file="pkg/other.py", start_line=1, end_line=5, confidence=0.3, reasoning="Unrelated")
    test_result = TestResult(stdout="ZeroDivisionError at utils.py:5", stderr="", exit_code=1, elapsed_s=1.0)

    mock_client.messages.create.return_value.content[0].text = json.dumps({
        "verified": False, "reasoning": "Stack trace does not mention other.py"
    })

    verifier = Verifier(client=mock_client)
    demoted_h = verifier.verify(h, test_result)
    assert demoted_h.verified is False
    assert demoted_h.confidence < h.confidence
```

- [ ] Create `src/triage_rca/agents/verifier.py`:

```python
import json
import anthropic
from triage_rca.schemas import Hypothesis, TestResult

SYSTEM_PROMPT = (
    "You are a hypothesis verifier. Given a root cause hypothesis and the failing test output, "
    "determine whether the hypothesis is consistent with the evidence. "
    "Output JSON: {\"verified\": true/false, \"reasoning\": \"one sentence\"}. "
    "Respond ONLY with valid JSON."
)

class Verifier:
    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def verify(self, hypothesis: Hypothesis, test_result: TestResult) -> Hypothesis:
        prompt = (
            f"Hypothesis: {hypothesis.file} lines {hypothesis.start_line}-{hypothesis.end_line}\n"
            f"Reasoning: {hypothesis.reasoning}\n\n"
            f"Test output:\n{test_result.stdout[:1500]}\n{test_result.stderr[:300]}"
        )
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text)
        verified = data.get("verified", False)
        return Hypothesis(
            file=hypothesis.file,
            start_line=hypothesis.start_line,
            end_line=hypothesis.end_line,
            confidence=hypothesis.confidence if verified else hypothesis.confidence * 0.3,
            reasoning=hypothesis.reasoning,
            verified=verified,
        )
```

- [ ] Run: `pytest tests/integration/test_rca_pipeline.py -k "verifier" -v` → 2 PASS

- [ ] Commit:

```bash
git add src/triage_rca/agents/verifier.py
git commit -m "feat(m4): Verifier subagent — confirms or demotes top Hypothesis"
```

---

### T4.6: RCA Pipeline Coordinator

- [ ] Write failing end-to-end test:

```python
def test_rca_pipeline_returns_hypotheses(tmp_path):
    import shutil
    from pathlib import Path
    from unittest.mock import MagicMock
    from triage_rca.rca_pipeline import RCAPipeline
    from triage_rca.schemas import TestResult

    shutil.copytree(Path("tests/fixtures/simple_repo"), tmp_path / "repo")

    mock_client = MagicMock()
    call_seq = [0]

    def side_effect(*args, **kwargs):
        r = MagicMock()
        call_seq[0] += 1
        if call_seq[0] == 1:  # Investigator
            r.content[0].text = json.dumps({
                "relevant_files": ["mypackage/utils.py"],
                "stack_frames": ["mypackage/utils.py:5"],
                "call_path": [], "ruled_out": [],
                "code_snippets": [{"file": "mypackage/utils.py", "start_line": 4, "end_line": 6, "content": "def divide(a,b): return a/b"}]
            })
        elif call_seq[0] == 2:  # Reasoner
            r.content[0].text = json.dumps({
                "hypotheses": [{"file": "mypackage/utils.py", "start_line": 4, "end_line": 6, "confidence": 0.9, "reasoning": "No zero check"}]
            })
        else:  # Verifier
            r.content[0].text = json.dumps({"verified": True, "reasoning": "Confirmed"})
        return r

    mock_client.messages.create.side_effect = side_effect

    mock_sandbox = MagicMock()
    mock_sandbox.run_test.return_value = TestResult(
        stdout="FAILED ZeroDivisionError", stderr="", exit_code=1, elapsed_s=1.5
    )

    pipeline = RCAPipeline(client=mock_client, sandbox=mock_sandbox)
    hypotheses = pipeline.run(
        issue_text="ZeroDivisionError in divide",
        repo_path=str(tmp_path / "repo"),
        test_file="tests/test_utils.py",
    )
    assert len(hypotheses) >= 1
    assert hypotheses[0].file == "mypackage/utils.py"
    assert hypotheses[0].verified is True
```

- [ ] Create `src/triage_rca/rca_pipeline.py`:

```python
import anthropic
from triage_rca.docker_sandbox import DockerSandbox
from triage_rca.agents.investigator import Investigator
from triage_rca.agents.reasoner import Reasoner
from triage_rca.agents.verifier import Verifier
from triage_rca.schemas import Hypothesis

class RCAPipeline:
    def __init__(self, client: anthropic.Anthropic, sandbox: DockerSandbox):
        self.investigator = Investigator(client, sandbox)
        self.reasoner = Reasoner(client)
        self.verifier = Verifier(client)

    def run(self, issue_text: str, repo_path: str, test_file: str) -> list[Hypothesis]:
        bundle = self.investigator.investigate(issue_text, repo_path, test_file)
        hypotheses = self.reasoner.reason(bundle)
        if not hypotheses:
            return []
        verified_top = self.verifier.verify(hypotheses[0], bundle.test_result)
        return [verified_top] + hypotheses[1:]
```

- [ ] Run: `pytest tests/integration/test_rca_pipeline.py -v` → all PASS

- [ ] Commit:

```bash
git add src/triage_rca/rca_pipeline.py tests/integration/test_rca_pipeline.py
git commit -m "feat(m4): RCAPipeline: Investigator → Reasoner → Verifier"
```

---

## Milestone 4 Verification

```bash
pytest tests/integration/test_rca_pipeline.py -v         # all PASS (mock)
pytest tests/integration/test_docker_sandbox.py -v -m integration  # PASS (needs Docker)
pytest tests/ -v --ignore=tests/integration/test_docker_sandbox.py  # no regressions
```
