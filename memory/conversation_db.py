import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
import sys

DB_LOCK = threading.Lock()


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


DB_PATH = get_base_dir() / "memory" / "conversations.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    return conn


def init_db():
    with DB_LOCK:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
            ON conversations(timestamp DESC)
        """)
        conn.commit()
        conn.close()


def add_entry(role: str, content: str, session_id: str = ""):
    if not content or not content.strip():
        return
    with DB_LOCK:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO conversations (timestamp, role, content, session_id) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), role, content.strip(), session_id),
        )
        conn.commit()
        conn.close()


def search_history(query: str, limit: int = 20) -> list[dict]:
    with DB_LOCK:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp, role, content FROM conversations WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        conn.close()
        return [
            {"timestamp": r[0], "role": r[1], "content": r[2]} for r in reversed(rows)
        ]


def get_recent_history(limit: int = 50) -> list[dict]:
    with DB_LOCK:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp, role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"timestamp": r[0], "role": r[1], "content": r[2]} for r in reversed(rows)
        ]


def get_history_count() -> int:
    with DB_LOCK:
        conn = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        conn.close()
        return count


def export_history(file_path: str = "") -> str:
    with DB_LOCK:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp, role, content FROM conversations ORDER BY id"
        ).fetchall()
        conn.close()

    lines = ["VAYU Conversation History", "=" * 50, ""]
    for ts, role, content in rows:
        time_str = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
        label = "You" if role == "user" else "VAYU"
        lines.append(f"[{time_str}] {label}: {content}")
        lines.append("")

    text = "\n".join(lines)

    if file_path:
        Path(file_path).write_text(text, encoding="utf-8")
    return text
