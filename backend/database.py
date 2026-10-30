"""SQLite chat log (stdlib only)."""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent.parent / "data" / "trekmate.db"))


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, ts TEXT DEFAULT CURRENT_TIMESTAMP, question TEXT, answer TEXT, mode TEXT)")


def log_chat(question: str, answer: str, mode: str):
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("INSERT INTO chats (question, answer, mode) VALUES (?,?,?)", (question, answer, mode))
    except sqlite3.Error:
        pass  # logging must never break chat


def recent_chats(limit: int = 20) -> list:
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("SELECT ts, question, answer, mode FROM chats ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(zip(("ts", "question", "answer", "mode"), r)) for r in rows]
