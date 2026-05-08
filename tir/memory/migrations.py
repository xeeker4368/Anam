"""Lightweight working.db schema migration support.

This module tracks durable working-store schema versions without introducing a
heavy migration framework. Version 1 is the current hand-built schema created
by tir.memory.db._init_working(); future ALTER-style migrations start at 2.
"""

from collections.abc import Callable
from datetime import datetime, timezone
import sqlite3


BASELINE_SCHEMA_VERSION = 1
BASELINE_SCHEMA_NAME = "baseline_current_schema"
MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = ()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema_versions_table(conn: sqlite3.Connection) -> None:
    """Create the working schema version ledger if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)


def get_applied_schema_versions(conn: sqlite3.Connection) -> set[int]:
    """Return applied working schema migration versions."""
    ensure_schema_versions_table(conn)
    rows = conn.execute("SELECT version FROM schema_versions").fetchall()
    return {int(row[0]) for row in rows}


def record_schema_version(conn: sqlite3.Connection, version: int, name: str) -> None:
    """Record one applied schema version."""
    conn.execute(
        """INSERT INTO schema_versions (version, name, applied_at)
           VALUES (?, ?, ?)""",
        (version, name, _now()),
    )


def _record_baseline_if_needed(conn: sqlite3.Connection) -> None:
    applied = get_applied_schema_versions(conn)
    if BASELINE_SCHEMA_VERSION not in applied:
        record_schema_version(conn, BASELINE_SCHEMA_VERSION, BASELINE_SCHEMA_NAME)
        conn.commit()


def _validate_migration_registry() -> list[tuple[int, str, Callable[[sqlite3.Connection], None]]]:
    migrations = sorted(MIGRATIONS, key=lambda migration: migration[0])
    seen = {BASELINE_SCHEMA_VERSION}
    for version, name, migration_func in migrations:
        if version in seen:
            raise RuntimeError(f"Duplicate schema migration version: {version}")
        if version <= BASELINE_SCHEMA_VERSION:
            raise RuntimeError(
                f"Schema migration versions must start after {BASELINE_SCHEMA_VERSION}: {version}"
            )
        if not name:
            raise RuntimeError(f"Schema migration {version} is missing a name")
        if not callable(migration_func):
            raise RuntimeError(f"Schema migration {version} is not callable")
        seen.add(version)
    return migrations


def run_working_migrations(conn: sqlite3.Connection) -> None:
    """Ensure baseline is recorded and apply pending working.db migrations."""
    ensure_schema_versions_table(conn)
    _record_baseline_if_needed(conn)

    for version, name, migration_func in _validate_migration_registry():
        applied = get_applied_schema_versions(conn)
        if version in applied:
            continue

        try:
            conn.execute("BEGIN")
            migration_func(conn)
            record_schema_version(conn, version, name)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
