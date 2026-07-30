from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteFeedbackStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    comment TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(
        self, *, run_id: str, session_id: str, user_id: str, rating: int, comment: str | None
    ) -> None:
        if rating not in range(1, 6):
            raise ValueError("rating must be between 1 and 5")
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO feedback_records(run_id, session_id, user_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
                (run_id, session_id, user_id, rating, comment),
            )

    def count(self) -> int:
        with sqlite3.connect(self.path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM feedback_records").fetchone()[0])
