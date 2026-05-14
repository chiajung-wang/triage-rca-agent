"""IssueStore: persistent store for bug reports with sqlite-vec nearest-neighbor search."""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass

import sqlite_vec


@dataclass
class SimilarIssue:
    bug_id: str
    project: str
    description: str
    similarity: float  # 0.0–1.0, higher = more similar


class IssueStore:
    """SQLite-backed store for bug report embeddings with KNN search via sqlite-vec."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            self._conn = conn
        return self._conn

    def init_vec_table(self, dimensions: int = 1024) -> None:
        """Create the issue_meta and issue_embeddings tables if they do not exist."""
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_meta (
                bug_id      TEXT PRIMARY KEY,
                project     TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS issue_embeddings
            USING vec0(bug_id TEXT PRIMARY KEY, embedding float[{dimensions}])
            """
        )
        conn.commit()

    def insert(
        self,
        bug_id: str,
        project: str,
        description: str,
        embedding: list[float],
    ) -> None:
        """Upsert a bug report and its embedding. Idempotent on bug_id."""
        conn = self._get_conn()
        packed = struct.pack(f"{len(embedding)}f", *embedding)
        conn.execute(
            "INSERT OR REPLACE INTO issue_meta(bug_id, project, description) VALUES (?, ?, ?)",
            (bug_id, project, description),
        )
        # vec0 virtual tables do not support INSERT OR REPLACE; use DELETE + INSERT for upsert.
        conn.execute("DELETE FROM issue_embeddings WHERE bug_id = ?", (bug_id,))
        conn.execute(
            "INSERT INTO issue_embeddings(bug_id, embedding) VALUES (?, ?)",
            (bug_id, packed),
        )
        conn.commit()

    def search(
        self,
        query_embedding: list[float],
        k: int = 5,
    ) -> list[SimilarIssue]:
        """Return up to k nearest issues ordered by descending similarity."""
        conn = self._get_conn()
        packed = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        rows = conn.execute(
            """
            SELECT m.bug_id, m.project, m.description, e.distance
            FROM issue_embeddings AS e
            JOIN issue_meta AS m ON m.bug_id = e.bug_id
            WHERE e.embedding MATCH ? AND k = ?
            ORDER BY e.distance
            """,
            (packed, k),
        ).fetchall()
        return [
            SimilarIssue(
                bug_id=row["bug_id"],
                project=row["project"],
                description=row["description"],
                similarity=max(0.0, 1.0 - row["distance"]),
            )
            for row in rows
        ]

    def count(self) -> int:
        """Return the number of stored issues."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM issue_meta").fetchone()
        return row[0]
