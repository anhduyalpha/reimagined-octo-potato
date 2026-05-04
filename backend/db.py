"""SQLite database layer for the dotfiles manager backend."""

import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "dotfiles.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dotfiles (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL UNIQUE,
                source_path  TEXT NOT NULL,
                target_path  TEXT NOT NULL,
                status  TEXT    NOT NULL DEFAULT 'pending',
                synced_at    REAL,
                created_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Dotfiles CRUD
# ---------------------------------------------------------------------------


def list_dotfiles() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM dotfiles ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_dotfile(name: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dotfiles WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None


def add_dotfile(
    name: str, source_path: str, target_path: str
) -> dict[str, Any]:
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO dotfiles (name, source_path, target_path, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (name, source_path, target_path, now),
        )
        conn.commit()
    return get_dotfile(name)  # type: ignore[return-value]


def update_dotfile_status(name: str, status: str) -> None:
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE dotfiles
            SET status = ?, synced_at = ?
            WHERE name = ?
            """,
            (status, now, name),
        )
        conn.commit()


def remove_dotfile(name: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM dotfiles WHERE name = ?", (name,))
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Config CRUD
# ---------------------------------------------------------------------------


def get_config(key: str, default: str | None = None) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def list_config() -> dict[str, str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {r["key"]: r["value"] for r in rows}
