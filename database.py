"""
SQLite-база данных для хранения целей и отчётов.
Файл goals.db создаётся автоматически рядом с ботом.
"""

import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, path: str = "goals.db"):
        self.path = path

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        """Создаёт таблицы при первом запуске."""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    baseline    TEXT NOT NULL,
                    target      TEXT NOT NULL,
                    weak_point  TEXT NOT NULL,
                    first_step  TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    done        TEXT NOT NULL,
                    metric      TEXT NOT NULL,
                    stuck       TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── Цели ──────────────────────────────────────

    def save_goal(self, user_id: int, username: str, baseline: str,
                  target: str, weak_point: str, first_step: str):
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO goals (user_id, username, baseline, target, weak_point, first_step, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    baseline=excluded.baseline,
                    target=excluded.target,
                    weak_point=excluded.weak_point,
                    first_step=excluded.first_step,
                    created_at=excluded.created_at
            """, (user_id, username, baseline, target, weak_point, first_step, now))
            conn.commit()

    def get_goal(self, user_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM goals WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_goal(self, user_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
            conn.commit()

    def get_all_goals(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM goals ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    # ── Отчёты ────────────────────────────────────

    def save_report(self, user_id: int, done: str, metric: str, stuck: str):
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO reports (user_id, done, metric, stuck, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, done, metric, stuck, now))
            conn.commit()

    def get_reports(self, user_id: int, limit: int = 10) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM reports
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
