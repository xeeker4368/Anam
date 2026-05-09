#!/usr/bin/env python3
"""Export Project Anam SQLite schema documentation.

This script is intentionally standalone: it imports no application modules,
reads schema only, and never mutates the inspected databases.
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


FTS_SHADOW_SUFFIXES = {
    "_data",
    "_idx",
    "_content",
    "_docsize",
    "_config",
}


TABLE_PURPOSES = {
    "users": "User records for resolving conversations and operator/admin ownership.",
    "conversations": "Mutable chat conversation metadata.",
    "messages": "Conversation messages and optional tool trace JSON.",
    "artifacts": "Workspace artifact registry. Primary key is artifact_id, not id.",
    "review_items": "Operator review queue items.",
    "open_loops": "Unresolved follow-ups and unfinished threads.",
    "behavioral_guidance_proposals": "AI-proposed behavioral guidance candidates for admin review.",
    "schema_versions": "Applied working.db schema migration versions.",
    "chunks_fts": "FTS5 lexical retrieval index for memory chunks.",
}


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _sqlite_master(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        """SELECT type, name, tbl_name, sql
           FROM sqlite_master
           WHERE name NOT LIKE 'sqlite_%'
           ORDER BY type, name""",
    )


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = _rows(
        conn,
        """SELECT name FROM sqlite_master
           WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
           ORDER BY name""",
    )
    return [row["name"] for row in rows]


def _virtual_table_names(conn: sqlite3.Connection) -> set[str]:
    virtual = set()
    for item in _sqlite_master(conn):
        sql = item.get("sql") or ""
        if item["type"] == "table" and "CREATE VIRTUAL TABLE" in sql.upper():
            virtual.add(item["name"])
    return virtual


def _is_fts_shadow(table: str, virtual_tables: set[str]) -> bool:
    return any(table == f"{name}{suffix}" for name in virtual_tables for suffix in FTS_SHADOW_SUFFIXES)


def _table_info(conn: sqlite3.Connection, table: str) -> list[dict]:
    return _rows(conn, f"PRAGMA table_info({table!r})")


def _index_list(conn: sqlite3.Connection, table: str) -> list[dict]:
    indexes = _rows(conn, f"PRAGMA index_list({table!r})")
    for index in indexes:
        index["columns"] = [
            row["name"]
            for row in _rows(conn, f"PRAGMA index_info({index['name']!r})")
        ]
    return sorted(indexes, key=lambda item: item["name"])


def _foreign_keys(conn: sqlite3.Connection, table: str) -> list[dict]:
    return _rows(conn, f"PRAGMA foreign_key_list({table!r})")


def _schema_versions(conn: sqlite3.Connection) -> list[dict]:
    if "schema_versions" not in _table_names(conn):
        return []
    return _rows(conn, "SELECT version, name, applied_at FROM schema_versions ORDER BY version")


def _create_sql(conn: sqlite3.Connection, name: str, object_type: str = "table") -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = ? AND type = ?",
        (name, object_type),
    ).fetchone()
    return row["sql"] if row and row["sql"] else None


def _append_columns(lines: list[str], columns: list[dict]) -> None:
    if not columns:
        lines.append("_No columns reported by PRAGMA table_info._")
        return
    lines.append("| Column | Type | Not Null | Default | Primary Key |")
    lines.append("| --- | --- | --- | --- | --- |")
    for column in columns:
        lines.append(
            "| {name} | {type} | {notnull} | {default} | {pk} |".format(
                name=column["name"],
                type=column["type"] or "",
                notnull="yes" if column["notnull"] else "no",
                default="" if column["dflt_value"] is None else f"`{column['dflt_value']}`",
                pk=column["pk"] or "",
            )
        )


def _append_indexes(lines: list[str], indexes: list[dict]) -> None:
    lines.append("**Indexes**")
    if not indexes:
        lines.append("- None")
        return
    for index in indexes:
        unique = "unique" if index.get("unique") else "non-unique"
        origin = index.get("origin") or "unknown"
        columns = ", ".join(index.get("columns") or []) or "n/a"
        lines.append(f"- `{index['name']}` ({unique}, origin={origin}): {columns}")


def _append_foreign_keys(lines: list[str], foreign_keys: list[dict]) -> None:
    lines.append("**Foreign Keys**")
    if not foreign_keys:
        lines.append("- None")
        return
    for fk in foreign_keys:
        lines.append(
            "- `{from_col}` -> `{table}`.`{to_col}` on_update={on_update} on_delete={on_delete}".format(
                from_col=fk["from"],
                table=fk["table"],
                to_col=fk["to"],
                on_update=fk["on_update"],
                on_delete=fk["on_delete"],
            )
        )


def _append_create_sql(lines: list[str], sql: str | None) -> None:
    if not sql:
        return
    lines.extend(
        [
            "<details>",
            "<summary>CREATE SQL</summary>",
            "",
            "```sql",
            sql.strip(),
            "```",
            "",
            "</details>",
        ]
    )


def _render_database(name: str, path: Path) -> list[str]:
    lines = [f"## {name}", ""]
    if not path.exists():
        lines.extend([f"_Database file not found: `{path}`_", ""])
        return lines

    with _connect(path) as conn:
        virtual_tables = _virtual_table_names(conn)
        schema_versions = _schema_versions(conn)
        if schema_versions:
            lines.extend(["### Schema Versions", ""])
            lines.append("| Version | Name | Applied At |")
            lines.append("| --- | --- | --- |")
            for row in schema_versions:
                lines.append(f"| {row['version']} | `{row['name']}` | {row['applied_at']} |")
            lines.append("")
        elif name == "working.db":
            lines.extend(["### Schema Versions", "", "_No schema_versions rows found._", ""])

        lines.extend(["### Tables", ""])
        for table in _table_names(conn):
            table_type = "virtual table" if table in virtual_tables else "table"
            if _is_fts_shadow(table, virtual_tables):
                table_type = "FTS shadow table"
            lines.extend([f"#### `{table}`", "", f"Type: {table_type}", ""])
            purpose = TABLE_PURPOSES.get(table)
            if purpose:
                lines.extend([f"Purpose: {purpose}", ""])

            columns = _table_info(conn, table)
            pk = [column["name"] for column in columns if column["pk"]]
            if pk:
                lines.extend([f"Primary key: `{', '.join(pk)}`", ""])

            _append_columns(lines, columns)
            lines.append("")
            _append_indexes(lines, _index_list(conn, table))
            lines.append("")
            _append_foreign_keys(lines, _foreign_keys(conn, table))
            lines.append("")
            _append_create_sql(lines, _create_sql(conn, table))
            lines.append("")

        views = [item for item in _sqlite_master(conn) if item["type"] == "view"]
        triggers = [item for item in _sqlite_master(conn) if item["type"] == "trigger"]
        if views:
            lines.extend(["### Views", ""])
            for view in views:
                lines.extend([f"- `{view['name']}`", ""])
                _append_create_sql(lines, view.get("sql"))
                lines.append("")
        if triggers:
            lines.extend(["### Triggers", ""])
            for trigger in triggers:
                lines.extend([f"- `{trigger['name']}` on `{trigger['tbl_name']}`", ""])
                _append_create_sql(lines, trigger.get("sql"))
                lines.append("")
    return lines


def render_schema_doc(
    *,
    working_db: Path,
    archive_db: Path,
    include_timestamp: bool = True,
) -> str:
    generated = datetime.now(timezone.utc).isoformat() if include_timestamp else "omitted"
    lines = [
        "# Database Schema",
        "",
        f"Generated: {generated}",
        "",
        "## Overview",
        "",
        "### working.db",
        "",
        "Mutable operational/control-plane database.",
        "",
        "### archive.db",
        "",
        "Durable minimal archive / ground truth database.",
        "",
        "### Chroma",
        "",
        "Vector index storage. Chroma is not fully documented as SQLite schema here.",
        "",
        "## Schema Ownership Notes",
        "",
        "- `working.db` owns mutable operational state.",
        "- `archive.db` owns minimal durable conversation/message/user archive.",
        "- Chroma owns vector retrieval indexes.",
        "- Governance files are files, not DB tables.",
        "- `artifacts` primary key is `artifact_id`, not `id`.",
        "- `metadata_json` stores extensible metadata.",
        "- `behavioral_guidance_proposals` lives in `working.db`.",
        "- `review_items`, `open_loops`, artifacts, and journals live in `working.db`.",
        "- Journal artifacts use `artifact_type=journal` and `metadata_json.source_type=journal`.",
        "- `schema_versions` exists only in `working.db`.",
        "- `BEHAVIORAL_GUIDANCE.md` is a governance file, not a database table.",
        "- `archive.db` remains minimal and frozen-scope.",
        "",
    ]
    lines.extend(_render_database("working.db", working_db))
    lines.extend(_render_database("archive.db", archive_db))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Project Anam SQLite schema documentation")
    parser.add_argument("--working-db", required=True, type=Path)
    parser.add_argument("--archive-db", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-timestamp", action="store_true")
    args = parser.parse_args(argv)

    doc = render_schema_doc(
        working_db=args.working_db,
        archive_db=args.archive_db,
        include_timestamp=not args.no_timestamp,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
