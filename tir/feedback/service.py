"""Internal feedback records service.

Feedback records are structured learning signals for later diagnostics and
substrate-level review. They do not update model weights, modify guidance,
index memory, expose tools, API routes, or UI behavior.
"""

import json
import uuid
from datetime import datetime, timezone


ALLOWED_FEEDBACK_TYPES = {
    "user_correction",
    "tool_result_inaccurate",
    "memory_inaccurate",
    "bad_assumption",
    "missed_context",
    "preference_update",
    "project_decision_update",
    "tool_behavior_feedback",
    "approval",
    "rejection",
    "generic",
}

ALLOWED_FEEDBACK_STATUSES = {
    "open",
    "accepted",
    "disputed",
    "resolved",
    "archived",
}

RESOLVED_STATUSES = {"resolved", "archived"}


class FeedbackValidationError(ValueError):
    """Raised when feedback record metadata is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_feedback_type(feedback_type: str) -> None:
    if feedback_type not in ALLOWED_FEEDBACK_TYPES:
        raise FeedbackValidationError(f"Invalid feedback_type: {feedback_type}")


def _validate_status(status: str) -> None:
    if status not in ALLOWED_FEEDBACK_STATUSES:
        raise FeedbackValidationError(f"Invalid feedback status: {status}")


def _validate_required_text(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise FeedbackValidationError(f"{field_name} is required")
    return value.strip()


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise FeedbackValidationError("metadata must be JSON serializable") from exc


def feedback_to_dict(row) -> dict | None:
    """Convert a feedback DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    metadata = json.loads(metadata_json) if metadata_json else None
    return {
        "feedback_id": data["feedback_id"],
        "feedback_type": data["feedback_type"],
        "status": data["status"],
        "title": data["title"],
        "description": data.get("description"),
        "user_feedback": data["user_feedback"],
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "source": data.get("source"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_tool_name": data.get("source_tool_name"),
        "related_artifact_id": data.get("related_artifact_id"),
        "related_open_loop_id": data.get("related_open_loop_id"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "resolved_at": data.get("resolved_at"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }


def create_feedback_record(
    *,
    feedback_type: str,
    title: str,
    user_feedback: str,
    status: str = "open",
    description: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    related_artifact_id: str | None = None,
    related_open_loop_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create an internal feedback metadata record in working.db."""
    _validate_feedback_type(feedback_type)
    _validate_status(status)
    normalized_title = _validate_required_text(title, "title")
    normalized_user_feedback = _validate_required_text(user_feedback, "user_feedback")
    metadata_json = _metadata_to_json(metadata)

    feedback_id = str(uuid.uuid4())
    now = _now()
    resolved_at = now if status in RESOLVED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.feedback_records
               (feedback_id, feedback_type, status, title, description,
                user_feedback, target_type, target_id, source,
                source_conversation_id, source_message_id, source_tool_name,
                related_artifact_id, related_open_loop_id, created_at,
                updated_at, resolved_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feedback_id,
                feedback_type,
                status,
                normalized_title,
                description,
                normalized_user_feedback,
                target_type,
                target_id,
                source,
                source_conversation_id,
                source_message_id,
                source_tool_name,
                related_artifact_id,
                related_open_loop_id,
                now,
                now,
                resolved_at,
                metadata_json,
            ),
        )
        conn.commit()

    return get_feedback_record(feedback_id)


def get_feedback_record(feedback_id: str) -> dict | None:
    """Fetch a feedback record by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.feedback_records WHERE feedback_id = ?",
            (feedback_id,),
        ).fetchone()
    return feedback_to_dict(row)


def list_feedback_records(
    *,
    feedback_type: str | None = None,
    status: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    source_conversation_id: str | None = None,
    related_artifact_id: str | None = None,
    related_open_loop_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List feedback records with optional metadata filters."""
    clauses = []
    params = []

    if feedback_type is not None:
        _validate_feedback_type(feedback_type)
        clauses.append("feedback_type = ?")
        params.append(feedback_type)

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if target_type is not None:
        clauses.append("target_type = ?")
        params.append(target_type)

    if target_id is not None:
        clauses.append("target_id = ?")
        params.append(target_id)

    if source_conversation_id is not None:
        clauses.append("source_conversation_id = ?")
        params.append(source_conversation_id)

    if related_artifact_id is not None:
        clauses.append("related_artifact_id = ?")
        params.append(related_artifact_id)

    if related_open_loop_id is not None:
        clauses.append("related_open_loop_id = ?")
        params.append(related_open_loop_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.feedback_records
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [feedback_to_dict(row) for row in rows]


def update_feedback_status(feedback_id: str, status: str) -> dict | None:
    """Update only a feedback record's status and resolved_at lifecycle field."""
    _validate_status(status)
    updated_at = _now()
    resolved_at = updated_at if status in RESOLVED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.feedback_records
               SET status = ?, updated_at = ?, resolved_at = ?
               WHERE feedback_id = ?""",
            (status, updated_at, resolved_at, feedback_id),
        )
        conn.commit()

    return get_feedback_record(feedback_id)
