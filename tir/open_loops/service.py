"""Internal open-loop registry service.

Open loops are metadata markers for unfinished, interrupted, unresolved, or
worth-revisiting threads. They are not tasks, memory chunks, tools, API routes,
or UI behavior.
"""

import json
import uuid
from datetime import datetime, timezone


ALLOWED_OPEN_LOOP_STATUSES = {
    "open",
    "in_progress",
    "blocked",
    "closed",
    "archived",
}

ALLOWED_OPEN_LOOP_TYPES = {
    "unfinished_artifact",
    "interrupted_research",
    "unresolved_question",
    "tool_failure_followup",
    "approval_needed",
    "self_mod_followup",
    "journal_followup",
    "generic",
}

ALLOWED_OPEN_LOOP_PRIORITIES = {
    "low",
    "normal",
    "high",
}

CLOSED_STATUSES = {"closed", "archived"}


class OpenLoopValidationError(ValueError):
    """Raised when open-loop metadata is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_status(status: str) -> None:
    if status not in ALLOWED_OPEN_LOOP_STATUSES:
        raise OpenLoopValidationError(f"Invalid open-loop status: {status}")


def _validate_loop_type(loop_type: str) -> None:
    if loop_type not in ALLOWED_OPEN_LOOP_TYPES:
        raise OpenLoopValidationError(f"Invalid open-loop type: {loop_type}")


def _validate_priority(priority: str) -> None:
    if priority not in ALLOWED_OPEN_LOOP_PRIORITIES:
        raise OpenLoopValidationError(f"Invalid open-loop priority: {priority}")


def _validate_title(title: str) -> str:
    if not title or not title.strip():
        raise OpenLoopValidationError("title is required")
    return title.strip()


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise OpenLoopValidationError("metadata must be JSON serializable") from exc


def open_loop_to_dict(row) -> dict | None:
    """Convert an open-loop DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    metadata = json.loads(metadata_json) if metadata_json else None
    return {
        "open_loop_id": data["open_loop_id"],
        "title": data["title"],
        "description": data.get("description"),
        "status": data["status"],
        "loop_type": data["loop_type"],
        "priority": data["priority"],
        "related_artifact_id": data.get("related_artifact_id"),
        "source": data.get("source"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_tool_name": data.get("source_tool_name"),
        "next_action": data.get("next_action"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "closed_at": data.get("closed_at"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }


def create_open_loop(
    *,
    title: str,
    description: str | None = None,
    status: str = "open",
    loop_type: str = "generic",
    priority: str = "normal",
    related_artifact_id: str | None = None,
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    next_action: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create an internal open-loop metadata record in working.db."""
    normalized_title = _validate_title(title)
    _validate_status(status)
    _validate_loop_type(loop_type)
    _validate_priority(priority)
    metadata_json = _metadata_to_json(metadata)

    open_loop_id = str(uuid.uuid4())
    now = _now()
    closed_at = now if status in CLOSED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.open_loops
               (open_loop_id, title, description, status, loop_type, priority,
                related_artifact_id, source, source_conversation_id,
                source_message_id, source_tool_name, next_action, created_at,
                updated_at, closed_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                open_loop_id,
                normalized_title,
                description,
                status,
                loop_type,
                priority,
                related_artifact_id,
                source,
                source_conversation_id,
                source_message_id,
                source_tool_name,
                next_action,
                now,
                now,
                closed_at,
                metadata_json,
            ),
        )
        conn.commit()

    return get_open_loop(open_loop_id)


def get_open_loop(open_loop_id: str) -> dict | None:
    """Fetch an open loop by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.open_loops WHERE open_loop_id = ?",
            (open_loop_id,),
        ).fetchone()
    return open_loop_to_dict(row)


def list_open_loops(
    *,
    status: str | None = None,
    loop_type: str | None = None,
    priority: str | None = None,
    related_artifact_id: str | None = None,
    source_conversation_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List open loops with optional metadata filters."""
    clauses = []
    params = []

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if loop_type is not None:
        _validate_loop_type(loop_type)
        clauses.append("loop_type = ?")
        params.append(loop_type)

    if priority is not None:
        _validate_priority(priority)
        clauses.append("priority = ?")
        params.append(priority)

    if related_artifact_id is not None:
        clauses.append("related_artifact_id = ?")
        params.append(related_artifact_id)

    if source_conversation_id is not None:
        clauses.append("source_conversation_id = ?")
        params.append(source_conversation_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.open_loops
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [open_loop_to_dict(row) for row in rows]


def update_open_loop_status(open_loop_id: str, status: str) -> dict | None:
    """Update only an open loop's status and closed_at lifecycle fields."""
    _validate_status(status)
    updated_at = _now()
    closed_at = updated_at if status in CLOSED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.open_loops
               SET status = ?, updated_at = ?, closed_at = ?
               WHERE open_loop_id = ?""",
            (status, updated_at, closed_at, open_loop_id),
        )
        conn.commit()

    return get_open_loop(open_loop_id)
