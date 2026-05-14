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
