"""SQLite database connection and migration runner."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from license_server.config import get_db_path

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_connection: sqlite3.Connection | None = None


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection in WAL mode.

    Re-uses a module-level connection for the configured path.
    Pass an explicit db_path (e.g. ":memory:") for testing.
    """
    global _connection

    if db_path is not None:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    if _connection is None:
        path = get_db_path()
        _connection = sqlite3.connect(str(path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")

    return _connection


def close_connection() -> None:
    """Close the module-level connection if open."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply pending SQL migrations and return list of applied versions."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  version INTEGER PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    conn.commit()

    applied: set[int] = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    newly_applied: list[int] = []

    for mf in migration_files:
        match = mf.stem.split("_", 1)
        if not match[0].isdigit():
            continue
        version = int(match[0])
        if version in applied:
            continue

        sql = mf.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
        newly_applied.append(version)
        logger.info("Applied migration %03d from %s", version, mf.name)

    return newly_applied
