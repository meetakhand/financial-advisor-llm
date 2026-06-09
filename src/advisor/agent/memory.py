"""SQLite-backed user profile + conversation log."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("data/profile.db")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute(
        """CREATE TABLE IF NOT EXISTS profile (
            user_id TEXT PRIMARY KEY,
            data    TEXT NOT NULL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS conversation (
            user_id TEXT NOT NULL,
            ts      REAL NOT NULL,
            role    TEXT NOT NULL,
            content TEXT NOT NULL
        )"""
    )
    return c


def load_profile(user_id: str) -> dict:
    with _conn() as c:
        row = c.execute("SELECT data FROM profile WHERE user_id=?", (user_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def save_profile(user_id: str, data: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO profile (user_id, data) VALUES (?, ?)",
            (user_id, json.dumps(data)),
        )


def log_message(user_id: str, role: str, content: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO conversation (user_id, ts, role, content) VALUES (?, ?, ?, ?)",
            (user_id, time.time(), role, content),
        )


def recent_messages(user_id: str, limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM conversation WHERE user_id=? ORDER BY ts DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r, "content": ct} for r, ct in reversed(rows)]
