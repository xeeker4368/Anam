import importlib
import sqlite3

import pytest


@pytest.fixture()
def schema_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")

    import tir.memory.migrations as migrations_mod
    import tir.memory.db as db_mod

    importlib.reload(migrations_mod)
    importlib.reload(db_mod)
    yield db_mod, migrations_mod, tmp_path


def _working_rows(tmp_path, query, params=()):
    conn = sqlite3.connect(tmp_path / "data" / "prod" / "working.db")
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def _archive_rows(tmp_path, query, params=()):
    conn = sqlite3.connect(tmp_path / "data" / "prod" / "archive.db")
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def test_fresh_working_db_gets_baseline_row(schema_env):
    db_mod, _migrations_mod, tmp_path = schema_env

    db_mod.init_databases()

    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [(1, "baseline_current_schema")]


def test_existing_working_db_without_schema_versions_gets_baseline_row(schema_env):
    db_mod, _migrations_mod, tmp_path = schema_env
    working_db = tmp_path / "data" / "prod" / "working.db"
    working_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(working_db)
    try:
        conn.execute("CREATE TABLE preexisting_marker (id TEXT PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    db_mod.init_databases()

    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [(1, "baseline_current_schema")]
    assert _working_rows(
        tmp_path,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='preexisting_marker'",
    )


def test_init_databases_is_idempotent(schema_env):
    db_mod, _migrations_mod, tmp_path = schema_env

    db_mod.init_databases()
    db_mod.init_databases()

    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [(1, "baseline_current_schema")]


def test_schema_versions_exists_only_in_working_db(schema_env):
    db_mod, _migrations_mod, tmp_path = schema_env

    db_mod.init_databases()

    assert _working_rows(
        tmp_path,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'",
    )
    assert not _archive_rows(
        tmp_path,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'",
    )


def test_pending_migrations_apply_in_order(schema_env, monkeypatch):
    db_mod, migrations_mod, tmp_path = schema_env
    applied = []

    def migration_two(conn):
        applied.append(2)
        conn.execute("CREATE TABLE migration_two_marker (id TEXT PRIMARY KEY)")

    def migration_three(conn):
        applied.append(3)
        conn.execute("CREATE TABLE migration_three_marker (id TEXT PRIMARY KEY)")

    monkeypatch.setattr(
        migrations_mod,
        "MIGRATIONS",
        (
            (3, "third", migration_three),
            (2, "second", migration_two),
        ),
    )

    db_mod.init_databases()

    assert applied == [2, 3]
    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [
        (1, "baseline_current_schema"),
        (2, "second"),
        (3, "third"),
    ]


def test_failed_migration_does_not_record_version(schema_env, monkeypatch):
    db_mod, migrations_mod, tmp_path = schema_env

    def failing_migration(conn):
        conn.execute("CREATE TABLE failed_marker (id TEXT PRIMARY KEY)")
        raise RuntimeError("migration failed")

    monkeypatch.setattr(
        migrations_mod,
        "MIGRATIONS",
        ((2, "failing", failing_migration),),
    )

    with pytest.raises(RuntimeError, match="migration failed"):
        db_mod.init_databases()

    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [(1, "baseline_current_schema")]
    assert not _working_rows(
        tmp_path,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='failed_marker'",
    )


def test_migration_runner_skips_already_applied_versions(schema_env, monkeypatch):
    db_mod, migrations_mod, tmp_path = schema_env

    def first_migration(conn):
        conn.execute("CREATE TABLE first_marker (id TEXT PRIMARY KEY)")

    monkeypatch.setattr(
        migrations_mod,
        "MIGRATIONS",
        ((2, "first", first_migration),),
    )
    db_mod.init_databases()

    def should_not_run(_conn):
        raise AssertionError("already applied migration should be skipped")

    monkeypatch.setattr(
        migrations_mod,
        "MIGRATIONS",
        ((2, "first", should_not_run),),
    )
    db_mod.init_databases()

    rows = _working_rows(
        tmp_path,
        "SELECT version, name FROM schema_versions ORDER BY version",
    )
    assert rows == [
        (1, "baseline_current_schema"),
        (2, "first"),
    ]
