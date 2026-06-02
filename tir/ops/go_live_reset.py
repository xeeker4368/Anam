"""Go-live reset for Project Anam.

This is the deliberate, destructive act that defines go-live: it wipes
contaminated pre-live runtime memory/experience and starts the substrate
fresh, while preserving identity, user-mapping/config, schema, governance,
config, code, and backups.

Chroma and the FTS index are emptied to EMPTY (they refill naturally
post-launch); they are NOT rebuilt from the archive, because the archive
messages are wiped too.

--------------------------------------------------------------------------
Table classification principle (apply to EVERY table in both databases):

  PRESERVE  identity, user-mapping/config, and schema/structure:
            working.db -> users, channel_identifiers, schema_versions
            archive.db -> users
            (archive.db has no schema_versions table; its scope is frozen.)

  WIPE      all experiment / memory / activity-derived data:
            conversations, messages, summaries, documents, artifacts,
            open_loops, review_items, tasks, feedback_records,
            diagnostic_issues, overnight_runs,
            behavioral_guidance_proposals, chunks_fts
            archive.db -> messages

  MANAGED   FTS5 internal shadow tables (chunks_fts_*) are owned by
            chunks_fts and cleared via "DELETE FROM chunks_fts"; they are
            never targeted directly.

A future schema addition that is NOT classified here must be flagged, never
silently preserved or wiped: _assert_all_tables_classified() aborts the reset
when it finds an unknown table so the new table gets a deliberate decision.

On preserved rows, only activity/timestamp data is cleared (identity columns
stay): users.last_seen_at is set to NULL. There are no other activity columns
on users or channel_identifiers (created_at is identity provenance;
verified/auth_material are config/credential state).
--------------------------------------------------------------------------
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from tir import config
from tir.memory import chroma
from tir.memory.db import get_connection
from tir.ops.backup import create_backup, verify_backup_restore


GO_LIVE_RESET_PHRASE = "WIPE PRE-LIVE RUNTIME STATE"

# working.db row targets, ordered child-first for FK safety (deletes also run
# under PRAGMA defer_foreign_keys to handle the artifacts self-reference).
WORKING_WIPE_TABLES = (
    "diagnostic_issues",
    "feedback_records",
    "review_items",
    "behavioral_guidance_proposals",
    "open_loops",
    "artifacts",
    "summaries",
    "messages",
    "conversations",
    "documents",
    "tasks",
    "overnight_runs",
)
FTS_WIPE_TABLE = "chunks_fts"
PRESERVE_WORKING_TABLES = ("users", "channel_identifiers", "schema_versions")
# FTS5-managed shadow tables: cleared via DELETE FROM chunks_fts, never directly.
FTS_INTERNAL_TABLES = (
    "chunks_fts_config",
    "chunks_fts_content",
    "chunks_fts_data",
    "chunks_fts_docsize",
    "chunks_fts_idx",
)

ARCHIVE_WIPE_TABLES = ("messages",)
PRESERVE_ARCHIVE_TABLES = ("users",)

# Workspace runtime output dirs whose CONTENTS are cleared while the dir itself
# is kept. source-traces is nested under research; it is recreated empty after
# research is cleared so the structure persists.
WORKSPACE_WIPE_DIRS = ("research", "journals", "uploads", "generated")
WORKSPACE_KEEP_EMPTY_SUBDIRS = ("research/source-traces",)


class GoLiveResetError(RuntimeError):
    """Raised when the go-live reset cannot proceed safely."""


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Classification guard
# ---------------------------------------------------------------------------

def _tables_in(conn, schema: str) -> set[str]:
    rows = conn.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows if not row[0].startswith("sqlite_")}


def _assert_all_tables_classified(conn) -> None:
    """Abort if either database holds a table we have not classified.

    This makes a future migration that adds a table fail loudly here rather
    than letting it silently survive (or get silently wiped).
    """
    known_working = (
        set(WORKING_WIPE_TABLES)
        | {FTS_WIPE_TABLE}
        | set(FTS_INTERNAL_TABLES)
        | set(PRESERVE_WORKING_TABLES)
    )
    known_archive = set(ARCHIVE_WIPE_TABLES) | set(PRESERVE_ARCHIVE_TABLES)

    unknown_working = sorted(_tables_in(conn, "main") - known_working)
    unknown_archive = sorted(_tables_in(conn, "archive") - known_archive)

    problems = []
    if unknown_working:
        problems.append(f"working.db: {', '.join(unknown_working)}")
    if unknown_archive:
        problems.append(f"archive.db: {', '.join(unknown_archive)}")
    if problems:
        raise GoLiveResetError(
            "Unclassified table(s) found; classify them in go_live_reset.py "
            "before running a reset: " + "; ".join(problems)
        )


# ---------------------------------------------------------------------------
# Counting (shared by dry-run, execute, and verify-clean)
# ---------------------------------------------------------------------------

def _count(conn, qualified_table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {qualified_table}").fetchone()[0])


def _db_counts(conn) -> dict:
    working = {table: _count(conn, table) for table in WORKING_WIPE_TABLES}
    working[FTS_WIPE_TABLE] = _count(conn, FTS_WIPE_TABLE)
    archive = {table: _count(conn, f"archive.{table}") for table in ARCHIVE_WIPE_TABLES}
    return {"working_db": working, "archive_db": archive}


def _preserved_snapshot(conn) -> dict:
    users = [
        {"id": row[0], "name": row[1], "role": row[2]}
        for row in conn.execute(
            "SELECT id, name, role FROM users ORDER BY created_at"
        ).fetchall()
    ]
    channels = _count(conn, "channel_identifiers")
    schema_versions = [
        {"version": row[0], "name": row[1]}
        for row in conn.execute(
            "SELECT version, name FROM schema_versions ORDER BY version"
        ).fetchall()
    ]
    archive_users = _count(conn, "archive.users")
    return {
        "working_users": users,
        "working_channel_identifiers_count": channels,
        "working_schema_versions": schema_versions,
        "archive_users_count": archive_users,
    }


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

def _workspace_root() -> Path:
    return Path(config.WORKSPACE_DIR)


def _file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _workspace_counts() -> dict:
    root = _workspace_root()
    per_dir = {name: _file_count(root / name) for name in WORKSPACE_WIPE_DIRS}
    # Reported as a subset of research (not added to the total to avoid
    # double-counting, since it lives inside research/).
    subdir = {
        name: _file_count(root / name) for name in WORKSPACE_KEEP_EMPTY_SUBDIRS
    }
    return {
        "dirs": per_dir,
        "nested_subdirs": subdir,
        "total_files": sum(per_dir.values()),
    }


def _clear_dir_contents(path: Path) -> int:
    removed = 0
    if not path.exists():
        return removed
    for child in path.iterdir():
        if child.is_dir():
            removed += _file_count(child)
            shutil.rmtree(child)
        elif child.is_file() or child.is_symlink():
            removed += 1
            child.unlink()
    return removed


def _wipe_workspace() -> dict:
    root = _workspace_root()
    per_dir = {}
    for name in WORKSPACE_WIPE_DIRS:
        target = root / name
        per_dir[name] = _clear_dir_contents(target)
        target.mkdir(parents=True, exist_ok=True)
    # Recreate kept-but-empty nested subdirs (e.g. research/source-traces).
    for name in WORKSPACE_KEEP_EMPTY_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return {"dirs": per_dir, "total_files_removed": sum(per_dir.values())}


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def plan_go_live_reset() -> dict:
    """Report exactly what WOULD be wiped and preserved. No mutation."""
    with get_connection() as conn:
        _assert_all_tables_classified(conn)
        counts = _db_counts(conn)
        preserved = _preserved_snapshot(conn)
        last_seen_to_clear = _count(
            conn, "users WHERE last_seen_at IS NOT NULL"
        )
    return {
        "ok": True,
        "mode": "dry-run",
        "confirmation_phrase": GO_LIVE_RESET_PHRASE,
        "would_wipe": {
            **counts,
            "chroma_chunks": chroma.get_collection_count(),
            "workspace": _workspace_counts(),
            "users_last_seen_at_to_clear": last_seen_to_clear,
        },
        "would_preserve": preserved,
    }


# ---------------------------------------------------------------------------
# Destructive reset (gated)
# ---------------------------------------------------------------------------

def _reset_audit_dir() -> Path:
    return Path(config.BACKUP_DIR) / "go-live-reset-audit"


def _write_audit(record: dict) -> Path:
    audit_dir = _reset_audit_dir()
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"go-live-reset-{record['timestamp_compact']}.json"
    audit_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit_path


def _wipe_databases(conn) -> dict:
    """Clear all WIPE tables and null preserved activity columns.

    Runs under defer_foreign_keys so cross-table order and the artifacts
    self-reference (revision_of) cannot raise a transient FK violation; the
    graph is consistent at COMMIT because no preserved table points into a
    wiped one.
    """
    before = _db_counts(conn)
    conn.execute("PRAGMA defer_foreign_keys = ON")
    try:
        for table in WORKING_WIPE_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute(f"DELETE FROM {FTS_WIPE_TABLE}")
        last_seen_cleared = conn.execute(
            "UPDATE users SET last_seen_at = NULL WHERE last_seen_at IS NOT NULL"
        ).rowcount
        for table in ARCHIVE_WIPE_TABLES:
            conn.execute(f"DELETE FROM archive.{table}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"wiped_counts": before, "users_last_seen_cleared": int(last_seen_cleared)}


def execute_go_live_reset(
    *,
    confirm: bool,
    typed_confirm: str | None,
    backup_root: Path | None = None,
    verify_target_dir: Path | None = None,
) -> dict:
    """Run the full gated destructive reset.

    Gate order (abort on any failure; no wipe before gate 4):
      0. arm switch: confirm must be True (no backup is created otherwise).
      1. create a fresh backup (the rollback artifact).
      2. verify_backup_restore into an isolated target; abort unless it passes.
      3. typed_confirm must equal the exact phrase.
      4. wipe inside a transaction; empty Chroma/FTS; clear workspace dirs.
      5. write an audit file recording the backup path and per-target counts.
    """
    if not confirm:
        raise GoLiveResetError(
            "Refusing to run: --confirm-go-live-reset is required."
        )

    # Gate 1: fresh backup (rollback artifact; no auto-pruning exists, so it is
    # durable). Recorded in the audit file below.
    backup = create_backup(
        destination_root=Path(backup_root) if backup_root is not None else None
    )
    backup_path = backup["backup_path"]

    # Gate 2: prove the backup is restorable before destroying anything.
    cleanup_target = False
    if verify_target_dir is not None:
        target_dir = Path(verify_target_dir)
    else:
        target_dir = Path(tempfile.mkdtemp(prefix="anam-go-live-verify-"))
        cleanup_target = True
    try:
        verification = verify_backup_restore(
            Path(backup_path), target_dir, overwrite_target=True
        )
    finally:
        if cleanup_target and target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
    if not verification.get("ok"):
        raise GoLiveResetError(
            "Backup restore verification failed; aborting before any wipe. "
            f"backup={backup_path}"
        )

    # Gate 3: typed human confirmation.
    if typed_confirm != GO_LIVE_RESET_PHRASE:
        raise GoLiveResetError(
            "Typed confirmation phrase mismatch; aborting before any wipe. "
            f'Expected exactly: "{GO_LIVE_RESET_PHRASE}"'
        )

    # Gate 4: wipe.
    with get_connection() as conn:
        _assert_all_tables_classified(conn)
        db_result = _wipe_databases(conn)
        preserved = _preserved_snapshot(conn)

    chroma_result = chroma.empty_collection()
    workspace_result = _wipe_workspace()

    # Gate 5: audit.
    stamp_compact = _utc_stamp()
    audit_record = {
        "ok": True,
        "event": "go_live_reset",
        "timestamp": _utc_iso(),
        "timestamp_compact": stamp_compact,
        "confirmation_phrase": GO_LIVE_RESET_PHRASE,
        "backup_path": backup_path,
        "backup_is_rollback_artifact": True,
        "backup_verified": True,
        "backup_verify_target": str(target_dir),
        "wiped": {
            **db_result["wiped_counts"],
            "users_last_seen_cleared": db_result["users_last_seen_cleared"],
            "chroma_chunks": chroma_result["removed"],
            "workspace": workspace_result,
        },
        "preserved": preserved,
    }
    audit_path = _write_audit(audit_record)

    return {
        "ok": True,
        "mode": "destructive",
        "backup_path": backup_path,
        "backup_verified": True,
        "audit_path": str(audit_path),
        "wiped": audit_record["wiped"],
        "preserved": preserved,
    }


# ---------------------------------------------------------------------------
# Post-reset verification
# ---------------------------------------------------------------------------

def verify_clean() -> dict:
    """Assert the substrate is in a clean post-reset state. Reports pass/fail."""
    failures = []
    with get_connection() as conn:
        _assert_all_tables_classified(conn)
        db_counts = _db_counts(conn)
        for table, count in db_counts["working_db"].items():
            if count != 0:
                failures.append(f"working.{table} not empty ({count})")
        for table, count in db_counts["archive_db"].items():
            if count != 0:
                failures.append(f"archive.{table} not empty ({count})")

        users_count = _count(conn, "users")
        if users_count < 1:
            failures.append("working.users is empty (expected preserved users)")
        schema_versions = _count(conn, "schema_versions")
        if schema_versions < 1:
            failures.append("working.schema_versions is empty")
        preserved = _preserved_snapshot(conn)

    chroma_count = chroma.get_collection_count()
    if chroma_count != 0:
        failures.append(f"chroma not empty ({chroma_count})")

    workspace = _workspace_counts()
    if workspace["total_files"] != 0:
        failures.append(f"workspace not empty ({workspace['total_files']} files)")

    return {
        "ok": not failures,
        "mode": "verify-clean",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "db_counts": db_counts,
        "chroma_chunks": chroma_count,
        "workspace": workspace,
        "preserved": preserved,
    }
