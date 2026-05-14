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
