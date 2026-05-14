#!/usr/bin/env python3
import os
from triage_rca.db import init_db

DB_PATH = os.getenv("TRIAGE_RCA_DB", "triage_rca.db")

if __name__ == "__main__":
    init_db(DB_PATH)
    print(f"Database initialized: {DB_PATH}")
