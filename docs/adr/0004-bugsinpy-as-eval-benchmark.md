# ADR 0004: BugsInPy as Eval Benchmark

## Status
Accepted

## Context
RCA accuracy needs to be measured against ground truth. Options considered: BugsInPy (Python bug benchmark with ground truth), real OSS GitHub issues (no ground truth), synthetic dataset (full control, low credibility), SWE-bench (contaminated or requires multi-language setup).

## Decision
Use BugsInPy as the RCA eval benchmark. Build a hand-labeled triage eval set (30-50 entries) derived from BugsInPy bugs.

## Consequences
- BugsInPy provides buggy commit + fixed commit + triggering test per bug — exact ground truth needed for Top-1/3/5 accuracy measurement
- Python-only aligns with the stack (no Java tooling required unlike Defects4J)
- Hand-labeled triage eval reuses the same bugs — consistent domain, one setup
- Tradeoff: BugsInPy is a research benchmark, not fresh production issues; results may not fully generalize
- Enables direct comparison to AGENTFL and MemFL baselines (both use Defects4J; BugsInPy is the Python equivalent)
