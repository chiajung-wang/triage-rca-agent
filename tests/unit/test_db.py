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
                 ("r1", "2026-01-01", "issue", "/repo", "running", 0.1, 10.0, 5, None))
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE id=?", ("r1",)).fetchone()
    assert row["id"] == "r1"
    conn.close()
