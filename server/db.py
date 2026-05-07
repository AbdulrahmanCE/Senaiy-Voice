"""SQLite storage for senaiy-voice calls and transcripts."""

import sqlite3
import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "senaiy.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    transport TEXT NOT NULL,
    from_identifier TEXT,
    to_identifier TEXT,
    recording_path TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcripts_call_id ON transcripts(call_id);
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    transport TEXT NOT NULL DEFAULT 'streamable_http',
    auth_header_name TEXT,
    auth_header_value TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    tools_filter TEXT,
    created_at TEXT NOT NULL,
    last_status TEXT,
    last_checked_at TEXT
);
"""


_MCP_OAUTH_COLUMNS = [
    ("oauth_client_id", "TEXT"),
    ("oauth_client_secret", "TEXT"),
    ("oauth_access_token", "TEXT"),
    ("oauth_refresh_token", "TEXT"),
    ("oauth_token_expires_at", "TEXT"),
    ("oauth_authorization_endpoint", "TEXT"),
    ("oauth_token_endpoint", "TEXT"),
    ("oauth_registration_endpoint", "TEXT"),
    ("oauth_state", "TEXT"),
    ("oauth_code_verifier", "TEXT"),
]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as cx:
        cx.executescript(SCHEMA)
        # Idempotent column migrations for mcp_servers (sqlite doesn't support IF NOT EXISTS on columns)
        existing = {row["name"] for row in cx.execute("PRAGMA table_info(mcp_servers)")}
        for col, typ in _MCP_OAUTH_COLUMNS:
            if col not in existing:
                cx.execute(f"ALTER TABLE mcp_servers ADD COLUMN {col} {typ}")


@contextmanager
def _conn():
    cx = sqlite3.connect(str(DB_PATH))
    cx.row_factory = sqlite3.Row
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def start_call(transport: str, from_identifier: Optional[str] = None, to_identifier: Optional[str] = None) -> int:
    with _conn() as cx:
        cur = cx.execute(
            "INSERT INTO calls (started_at, transport, from_identifier, to_identifier) VALUES (?, ?, ?, ?)",
            (_now(), transport, from_identifier, to_identifier),
        )
        return cur.lastrowid


def end_call(call_id: int, recording_path: Optional[str] = None, summary: Optional[str] = None) -> None:
    with _conn() as cx:
        cx.execute(
            "UPDATE calls SET ended_at = ?, recording_path = COALESCE(?, recording_path), summary = COALESCE(?, summary) WHERE id = ?",
            (_now(), recording_path, summary, call_id),
        )


def add_transcript(call_id: int, role: str, content: str, timestamp: Optional[str] = None) -> None:
    with _conn() as cx:
        cx.execute(
            "INSERT INTO transcripts (call_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            (call_id, timestamp or _now(), role, content),
        )


def list_calls(limit: int = 100):
    with _conn() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)
        )]


def get_transcripts(call_id: int):
    with _conn() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM transcripts WHERE call_id = ? ORDER BY id ASC", (call_id,)
        )]


# --- MCP server management ---

def list_mcp_servers(only_enabled: bool = False):
    with _conn() as cx:
        sql = "SELECT * FROM mcp_servers"
        if only_enabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id ASC"
        return [dict(r) for r in cx.execute(sql)]


def get_mcp_server(server_id: int):
    with _conn() as cx:
        row = cx.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        return dict(row) if row else None


def add_mcp_server(name: str, url: str, transport: str = "streamable_http",
                    auth_header_name: Optional[str] = None,
                    auth_header_value: Optional[str] = None,
                    tools_filter: Optional[str] = None) -> int:
    with _conn() as cx:
        cur = cx.execute(
            """INSERT INTO mcp_servers (name, url, transport, auth_header_name, auth_header_value, tools_filter, enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (name, url, transport, auth_header_name, auth_header_value, tools_filter, _now()),
        )
        return cur.lastrowid


def toggle_mcp_server(server_id: int) -> None:
    with _conn() as cx:
        cx.execute("UPDATE mcp_servers SET enabled = 1 - enabled WHERE id = ?", (server_id,))


def delete_mcp_server(server_id: int) -> None:
    with _conn() as cx:
        cx.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))


def update_mcp_status(server_id: int, status: str) -> None:
    with _conn() as cx:
        cx.execute(
            "UPDATE mcp_servers SET last_status = ?, last_checked_at = ? WHERE id = ?",
            (status, _now(), server_id),
        )


def update_mcp_fields(server_id: int, **fields) -> None:
    """Generic field updater. Whitelisted to mcp_servers columns to avoid injection."""
    if not fields:
        return
    with _conn() as cx:
        cols_info = {row["name"] for row in cx.execute("PRAGMA table_info(mcp_servers)")}
        valid = {k: v for k, v in fields.items() if k in cols_info}
        if not valid:
            return
        sets = ", ".join(f"{k} = ?" for k in valid)
        cx.execute(f"UPDATE mcp_servers SET {sets} WHERE id = ?", (*valid.values(), server_id))
