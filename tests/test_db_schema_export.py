import sqlite3

from scripts.export_db_schema import main, render_schema_doc


def _make_fixture_dbs(tmp_path):
    working_db = tmp_path / "working.db"
    archive_db = tmp_path / "archive.db"

    with sqlite3.connect(working_db) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_versions (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_versions (version, name, applied_at)
            VALUES (1, 'baseline_current_schema', '2026-05-09T00:00:00+00:00');

            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE artifacts (
                artifact_id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                title TEXT NOT NULL,
                path TEXT,
                metadata_json TEXT,
                revision_of TEXT,
                FOREIGN KEY (revision_of) REFERENCES artifacts(artifact_id)
            );
            CREATE INDEX idx_artifacts_path ON artifacts(path);

            CREATE TABLE behavioral_guidance_proposals (
                proposal_id TEXT PRIMARY KEY,
                proposal_text TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                text,
                source_type UNINDEXED
            );
            """
        )

    with sqlite3.connect(archive_db) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX idx_archive_conversation ON messages(conversation_id);
            """
        )

    return working_db, archive_db


def test_schema_exporter_runs_and_creates_markdown(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)
    output = tmp_path / "DB_SCHEMA.md"

    code = main([
        "--working-db",
        str(working_db),
        "--archive-db",
        str(archive_db),
        "--output",
        str(output),
        "--no-timestamp",
    ])

    assert code == 0
    report = output.read_text(encoding="utf-8")
    assert "# Database Schema" in report
    assert "Generated: omitted" in report


def test_schema_exporter_output_is_deterministic_with_no_timestamp(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)

    first = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )
    second = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )

    assert first == second


def test_schema_doc_includes_overview_tables_columns_and_primary_keys(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)

    report = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )

    assert "## Overview" in report
    assert "Mutable operational/control-plane database." in report
    assert "Durable minimal archive / ground truth database." in report
    assert "#### `artifacts`" in report
    assert "Primary key: `artifact_id`" in report
    assert "| artifact_id | TEXT | no |  | 1 |" in report
    assert "`artifacts` primary key is `artifact_id`, not `id`" in report
    assert "#### `behavioral_guidance_proposals`" in report


def test_schema_doc_includes_indexes_and_foreign_keys(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)

    report = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )

    assert "`idx_artifacts_path`" in report
    assert "path" in report
    assert "`revision_of` -> `artifacts`.`artifact_id`" in report
    assert "`idx_archive_conversation`" in report


def test_schema_doc_marks_virtual_and_fts_shadow_tables(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)

    report = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )

    assert "#### `chunks_fts`" in report
    assert "Type: virtual table" in report
    assert "FTS shadow table" in report


def test_schema_versions_shown_for_working_and_absent_from_archive(tmp_path):
    working_db, archive_db = _make_fixture_dbs(tmp_path)

    report = render_schema_doc(
        working_db=working_db,
        archive_db=archive_db,
        include_timestamp=False,
    )

    working_section = report.split("\n## working.db\n", 1)[1].split("\n## archive.db\n", 1)[0]
    archive_section = report.split("\n## archive.db\n", 1)[1]
    assert "### Schema Versions" in working_section
    assert "baseline_current_schema" in working_section
    assert "schema_versions" not in archive_section
