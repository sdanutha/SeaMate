import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "seamate.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(title: str = "New session") -> dict:
    sid = str(uuid.uuid4())
    now = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title, now, now),
        )
        conn.commit()
    return {"id": sid, "title": title, "created_at": now, "updated_at": now}


def list_sessions() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_title(session_id: str, title: str) -> dict | None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
            (title, now, session_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def touch_session(session_id: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?",
            (_now(), session_id),
        )
        conn.commit()


def delete_session(session_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
