"""
Tír Database Layer

Three storage layers:
- Archive (archive.db): append-only, sacred. Two tables: users, messages. Never changes shape.
- Working (working.db): operational. Same conversation data + metadata, processing state, FTS5.
- ChromaDB: vector store. Handled separately in chroma.py.

Every message writes to both SQLite databases atomically via ATTACH.
Both databases use DELETE journaling (not WAL) because WAL breaks
cross-database atomicity per SQLite docs.

The entity never reads from either SQLite database directly.
These serve the UI, developer, and overnight processes.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

from tir.config import ARCHIVE_DB, WORKING_DB, DATA_DIR


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _connect_working() -> sqlite3.Connection:
    """Open a connection to working.db with archive.db attached."""
    conn = sqlite3.connect(str(WORKING_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"ATTACH DATABASE '{ARCHIVE_DB}' AS archive")
    return conn


def _connect_archive_only() -> sqlite3.Connection:
    """Open a direct connection to archive.db. Used only for init."""
    conn = sqlite3.connect(str(ARCHIVE_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection():
    """Context manager for working+archive connection."""
    conn = _connect_working()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def init_databases():
    """Create both databases and all tables if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _init_archive()
    _init_working()


def _init_archive():
    """Archive schema: two tables, scope frozen forever."""
    with _connect_archive_only() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_trace TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_archive_conversation
                ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_archive_timestamp
                ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_archive_user
                ON messages(user_id);
        """)


def _init_working():
    """Working store schema: operational tables + FTS5."""
    conn = sqlite3.connect(str(WORKING_DB), timeout=10)
    conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL,
            last_seen_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

        CREATE TABLE IF NOT EXISTS channel_identifiers (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            identifier TEXT NOT NULL,
            auth_material TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (channel, identifier)
        );

        CREATE INDEX IF NOT EXISTS idx_channel_identifiers_user
            ON channel_identifiers(user_id);
        CREATE INDEX IF NOT EXISTS idx_channel_identifiers_lookup
            ON channel_identifiers(channel, identifier);

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            message_count INTEGER DEFAULT 0,
            chunked INTEGER DEFAULT 0,
            consolidated INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_started
            ON conversations(started_at);
        CREATE INDEX IF NOT EXISTS idx_conversations_ended
            ON conversations(ended_at);

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_trace TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_working_conversation
            ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_working_timestamp
            ON messages(timestamp);

        CREATE TABLE IF NOT EXISTS summaries (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT,
            source_type TEXT NOT NULL DEFAULT 'article',
            source_trust TEXT NOT NULL DEFAULT 'thirdhand',
            chunk_count INTEGER DEFAULT 0,
            summarized INTEGER DEFAULT 0,
            summary TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS overnight_runs (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_seconds REAL,
            conversations_closed INTEGER DEFAULT 0,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user',
            source_user_id TEXT,
            priority INTEGER DEFAULT 5,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result_document_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            path TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            revision_of TEXT,
            metadata_json TEXT,
            FOREIGN KEY (revision_of) REFERENCES artifacts(artifact_id)
        );

        CREATE INDEX IF NOT EXISTS idx_artifacts_type
            ON artifacts(artifact_type);
        CREATE INDEX IF NOT EXISTS idx_artifacts_status
            ON artifacts(status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_path
            ON artifacts(path);
        CREATE INDEX IF NOT EXISTS idx_artifacts_created_at
            ON artifacts(created_at);

        CREATE TABLE IF NOT EXISTS open_loops (
            open_loop_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            loop_type TEXT NOT NULL DEFAULT 'generic',
            priority TEXT NOT NULL DEFAULT 'normal',
            related_artifact_id TEXT,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            next_action TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (related_artifact_id) REFERENCES artifacts(artifact_id)
        );

        CREATE INDEX IF NOT EXISTS idx_open_loops_status
            ON open_loops(status);
        CREATE INDEX IF NOT EXISTS idx_open_loops_type
            ON open_loops(loop_type);
        CREATE INDEX IF NOT EXISTS idx_open_loops_priority
            ON open_loops(priority);
        CREATE INDEX IF NOT EXISTS idx_open_loops_artifact
            ON open_loops(related_artifact_id);
        CREATE INDEX IF NOT EXISTS idx_open_loops_conversation
            ON open_loops(source_conversation_id);
        CREATE INDEX IF NOT EXISTS idx_open_loops_created_at
            ON open_loops(created_at);

        CREATE TABLE IF NOT EXISTS feedback_records (
            feedback_id TEXT PRIMARY KEY,
            feedback_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            title TEXT NOT NULL,
            description TEXT,
            user_feedback TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            source TEXT,
            source_conversation_id TEXT,
            source_message_id TEXT,
            source_tool_name TEXT,
            related_artifact_id TEXT,
            related_open_loop_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            metadata_json TEXT,
            FOREIGN KEY (related_artifact_id) REFERENCES artifacts(artifact_id),
            FOREIGN KEY (related_open_loop_id) REFERENCES open_loops(open_loop_id)
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_records_type
            ON feedback_records(feedback_type);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_status
            ON feedback_records(status);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_target
            ON feedback_records(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_conversation
            ON feedback_records(source_conversation_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_artifact
            ON feedback_records(related_artifact_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_open_loop
            ON feedback_records(related_open_loop_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_records_created_at
            ON feedback_records(created_at);
    """)

    # FTS5 virtual table — separate because executescript can't mix
    # DDL for virtual tables with regular DDL reliably
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                text,
                conversation_id UNINDEXED,
                user_id UNINDEXED,
                source_type UNINDEXED,
                source_trust UNINDEXED,
                created_at UNINDEXED,
                tokenize = 'unicode61 remove_diacritics 2'
            )
        """)
    except sqlite3.OperationalError:
        # Already exists
        pass

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(name: str, role: str = "user") -> dict:
    """Create a user in both databases. Returns the user dict."""
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute("BEGIN")
        try:
            # Archive gets minimal user record
            conn.execute(
                "INSERT INTO archive.users (id, name, created_at) VALUES (?, ?, ?)",
                (user_id, name, now),
            )
            # Working gets full user record
            conn.execute(
                "INSERT INTO main.users (id, name, role, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, role, now),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return {"id": user_id, "name": name, "role": role, "created_at": now}


def get_user(user_id: str) -> dict | None:
    """Get a user by ID from working store."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_name(name: str) -> dict | None:
    """Get a user by name from working store."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.users WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None


def get_all_users() -> list[dict]:
    """Get all users from working store."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM main.users ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


def update_user_last_seen(user_id: str):
    """Update last_seen_at for a user."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE main.users SET last_seen_at = ? WHERE id = ?",
            (now, user_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Channel identifiers
# ---------------------------------------------------------------------------

def add_channel_identifier(
    user_id: str,
    channel: str,
    identifier: str,
    auth_material: str | None = None,
    verified: bool = False,
) -> dict:
    """Add a channel identifier for a user."""
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO main.channel_identifiers
               (id, user_id, channel, identifier, auth_material, verified, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cid, user_id, channel, identifier, auth_material, int(verified), now),
        )
        conn.commit()

    return {
        "id": cid, "user_id": user_id, "channel": channel,
        "identifier": identifier, "verified": verified,
    }


def resolve_user_by_channel(channel: str, identifier: str) -> dict | None:
    """Look up a user by channel + identifier. Returns user dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT u.* FROM main.users u
               JOIN main.channel_identifiers ci ON u.id = ci.user_id
               WHERE ci.channel = ? AND ci.identifier = ?""",
            (channel, identifier),
        ).fetchone()
        return dict(row) if row else None


def set_channel_auth(channel: str, identifier: str, auth_material: str):
    """Set or update auth material for a channel identifier."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE main.channel_identifiers
               SET auth_material = ? WHERE channel = ? AND identifier = ?""",
            (auth_material, channel, identifier),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def start_conversation(user_id: str) -> str:
    """Start a new conversation. Returns conversation_id."""
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO main.conversations
               (id, user_id, started_at) VALUES (?, ?, ?)""",
            (conversation_id, user_id, now),
        )
        conn.commit()

    return conversation_id


def end_conversation(conversation_id: str):
    """Mark a conversation as ended."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE main.conversations SET ended_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()


def get_conversation(conversation_id: str) -> dict | None:
    """Get conversation metadata."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None


def get_active_conversations(user_id: str | None = None) -> list[dict]:
    """Get conversations that haven't ended. Optionally filter by user."""
    with get_connection() as conn:
        if user_id:
            rows = conn.execute(
                """SELECT * FROM main.conversations
                   WHERE ended_at IS NULL AND user_id = ?
                   ORDER BY started_at DESC""",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM main.conversations
                   WHERE ended_at IS NULL ORDER BY started_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]


def is_conversation_ended(conversation_id: str) -> bool:
    """Check if a conversation has been marked ended."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ended_at FROM main.conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return row is not None and row["ended_at"] is not None


def list_conversations(limit: int = 50, offset: int = 0) -> list[dict]:
    """List conversations, most recent first, with summary if available.

    Returns dicts with: id, user_id, user_name, started_at, ended_at,
    message_count, summary.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.user_id, u.name as user_name,
                      c.started_at, c.ended_at, c.message_count,
                      s.content as summary
               FROM main.conversations c
               JOIN main.users u ON c.user_id = u.id
               LEFT JOIN main.summaries s ON c.id = s.conversation_id
               ORDER BY c.started_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Messages — the atomic dual-write
# ---------------------------------------------------------------------------

def save_message(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    tool_trace: str | None = None,
) -> dict:
    """
    Save a message to BOTH databases in a single atomic transaction.

    Uses ATTACH to open both databases on one connection.
    DELETE journaling on both databases ensures cross-database atomicity.
    If either write fails, both roll back.
    """
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute("BEGIN")
        try:
            # Archive — sacred, append-only
            conn.execute(
                """INSERT INTO archive.messages
                   (id, conversation_id, user_id, role, content, tool_trace, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (message_id, conversation_id, user_id, role, content, tool_trace, now),
            )

            # Working — same data, FK to conversations
            conn.execute(
                """INSERT INTO main.messages
                   (id, conversation_id, role, content, tool_trace, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, conversation_id, role, content, tool_trace, now),
            )

            # Increment message count
            conn.execute(
                "UPDATE main.conversations SET message_count = message_count + 1 WHERE id = ?",
                (conversation_id,),
            )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "tool_trace": tool_trace,
        "timestamp": now,
    }


def get_conversation_messages(conversation_id: str) -> list[dict]:
    """Get all messages in a conversation, ordered by timestamp."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.messages
               WHERE conversation_id = ?
               ORDER BY timestamp ASC""",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_turn_count(conversation_id: str) -> int:
    """Count completed turns (assistant messages) in a conversation."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM main.messages
               WHERE conversation_id = ? AND role = 'assistant'""",
            (conversation_id,),
        ).fetchone()
        return row["cnt"] if row else 0


def get_messages_since_last_chunk(
    conversation_id: str, last_chunk_turn: int
) -> list[dict]:
    """Get messages after the last chunked turn.

    Uses turn counting: finds the Nth assistant message and returns
    everything after it. If last_chunk_turn is 0, returns all messages.
    """
    with get_connection() as conn:
        if last_chunk_turn == 0:
            rows = conn.execute(
                """SELECT * FROM main.messages
                   WHERE conversation_id = ? ORDER BY timestamp ASC""",
                (conversation_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        # Find the timestamp of the Nth assistant message
        anchor = conn.execute(
            """SELECT timestamp FROM main.messages
               WHERE conversation_id = ? AND role = 'assistant'
               ORDER BY timestamp ASC LIMIT 1 OFFSET ?""",
            (conversation_id, last_chunk_turn - 1),
        ).fetchone()

        if not anchor:
            return []

        rows = conn.execute(
            """SELECT * FROM main.messages
               WHERE conversation_id = ? AND timestamp > ?
               ORDER BY timestamp ASC""",
            (conversation_id, anchor["timestamp"]),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# FTS5 chunks index
# ---------------------------------------------------------------------------

def upsert_chunk_fts(
    chunk_id: str,
    text: str,
    conversation_id: str | None,
    user_id: str | None,
    source_type: str,
    source_trust: str,
    created_at: str,
):
    """Insert or replace a chunk in the FTS5 index."""
    with get_connection() as conn:
        # Delete existing if present (FTS5 doesn't support UPSERT)
        conn.execute(
            "DELETE FROM main.chunks_fts WHERE chunk_id = ?", (chunk_id,)
        )
        conn.execute(
            """INSERT INTO main.chunks_fts
               (chunk_id, text, conversation_id, user_id, source_type, source_trust, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, text, conversation_id, user_id, source_type, source_trust, created_at),
        )
        conn.commit()


def search_bm25(
    query: str,
    n_results: int = 30,
    exclude_conversation_id: str | None = None,
) -> list[dict]:
    """Search chunks via FTS5 BM25. Returns ranked results."""
    with get_connection() as conn:
        if exclude_conversation_id:
            rows = conn.execute(
                """SELECT chunk_id, text, conversation_id, user_id,
                          source_type, source_trust, created_at,
                          rank as bm25_score
                   FROM main.chunks_fts
                   WHERE chunks_fts MATCH ?
                     AND (conversation_id IS NULL OR conversation_id != ?)
                   ORDER BY rank
                   LIMIT ?""",
                (query, exclude_conversation_id, n_results),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT chunk_id, text, conversation_id, user_id,
                          source_type, source_trust, created_at,
                          rank as bm25_score
                   FROM main.chunks_fts
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, n_results),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Summaries (UI only — entity never sees these)
# ---------------------------------------------------------------------------

def save_summary(conversation_id: str, content: str):
    """Save a conversation summary for UI display."""
    summary_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO main.summaries
               (id, conversation_id, content, created_at)
               VALUES (?, ?, ?, ?)""",
            (summary_id, conversation_id, content, now),
        )
        conn.commit()


def get_summary(conversation_id: str) -> str | None:
    """Get the summary for a conversation."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT content FROM main.summaries WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row["content"] if row else None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def save_document(
    title: str,
    source_type: str = "article",
    source_trust: str = "thirdhand",
    url: str | None = None,
) -> str:
    """Save document metadata. Returns document_id."""
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO main.documents
               (id, title, url, source_type, source_trust, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_id, title, url, source_type, source_trust, now),
        )
        conn.commit()

    return doc_id


def update_document_chunk_count(doc_id: str, chunk_count: int):
    """Update the chunk count after ingestion."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE main.documents SET chunk_count = ? WHERE id = ?",
            (chunk_count, doc_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def add_task(
    description: str,
    source: str = "user",
    source_user_id: str | None = None,
    priority: int = 5,
) -> str:
    """Add a task to the queue. Returns task_id."""
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO main.tasks
               (id, description, source, source_user_id, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (task_id, description, source, source_user_id, priority, now),
        )
        conn.commit()

    return task_id


def get_pending_tasks(limit: int = 10) -> list[dict]:
    """Get pending tasks ordered by priority (lower number = higher priority)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.tasks
               WHERE status = 'pending'
               ORDER BY priority ASC, created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_task_status(task_id: str, status: str):
    """Update task status. Valid: pending, running, completed, skipped."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if status == "running":
            conn.execute(
                "UPDATE main.tasks SET status = ?, started_at = ? WHERE id = ?",
                (status, now, task_id),
            )
        elif status in ("completed", "skipped"):
            conn.execute(
                "UPDATE main.tasks SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, task_id),
            )
        else:
            conn.execute(
                "UPDATE main.tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Overnight runs
# ---------------------------------------------------------------------------

def save_overnight_run(run_data: dict):
    """Save an overnight run record."""
    run_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO main.overnight_runs
               (id, started_at, ended_at, duration_seconds,
                conversations_closed, summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                run_data.get("started_at"),
                run_data.get("ended_at"),
                run_data.get("duration_seconds"),
                run_data.get("conversations_closed", 0),
                run_data.get("summary"),
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Conversation closing helpers
# ---------------------------------------------------------------------------

def get_unchunked_ended_conversations() -> list[dict]:
    """Get ended conversations that haven't been chunked yet."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.conversations
               WHERE ended_at IS NOT NULL AND chunked = 0
               ORDER BY started_at ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


def mark_conversation_chunked(conversation_id: str):
    """Mark a conversation as fully chunked."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE main.conversations SET chunked = 1 WHERE id = ?",
            (conversation_id,),
        )
        conn.commit()


def mark_conversation_consolidated(conversation_id: str):
    """Mark a conversation as consolidated (summary generated)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE main.conversations SET consolidated = 1 WHERE id = ?",
            (conversation_id,),
        )
        conn.commit()


def get_unconsolidated_conversations() -> list[dict]:
    """Get ended conversations that haven't been summarized."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.conversations
               WHERE ended_at IS NOT NULL AND consolidated = 0
               ORDER BY started_at ASC"""
        ).fetchall()
        return [dict(r) for r in rows]
