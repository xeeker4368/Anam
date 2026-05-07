"""Operator-controlled review queue service.

Review items are human-attention records. They are not autonomous tasks,
model tools, memory chunks, or background work.
"""

import json
import uuid
from datetime import datetime, timezone


ALLOWED_REVIEW_CATEGORIES = {
    "research",
    "follow_up",
    "contradiction",
    "correction",
    "artifact",
    "tool_failure",
    "memory",
    "decision",
    "safety",
    "other",
}

ALLOWED_REVIEW_STATUSES = {
    "open",
    "reviewed",
    "dismissed",
    "resolved",
}

ALLOWED_REVIEW_PRIORITIES = {
    "low",
    "normal",
    "high",
}

REVIEWED_STATUSES = {"reviewed", "dismissed", "resolved"}


class ReviewValidationError(ValueError):
    """Raised when review item metadata is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_title(title: str) -> str:
    if not title or not title.strip():
        raise ReviewValidationError("title is required")
    return title.strip()


def _validate_category(category: str) -> None:
    if category not in ALLOWED_REVIEW_CATEGORIES:
        raise ReviewValidationError(f"Invalid review category: {category}")


def _validate_status(status: str) -> None:
    if status not in ALLOWED_REVIEW_STATUSES:
        raise ReviewValidationError(f"Invalid review status: {status}")


def _validate_priority(priority: str) -> None:
    if priority not in ALLOWED_REVIEW_PRIORITIES:
        raise ReviewValidationError(f"Invalid review priority: {priority}")


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise ReviewValidationError("metadata must be JSON serializable") from exc


def review_item_to_dict(row) -> dict | None:
    """Convert a review item DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    metadata = json.loads(metadata_json) if metadata_json else None
    return {
        "item_id": data["item_id"],
        "title": data["title"],
        "description": data.get("description"),
        "category": data["category"],
        "status": data["status"],
        "priority": data["priority"],
        "source_type": data.get("source_type"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_artifact_id": data.get("source_artifact_id"),
        "source_tool_name": data.get("source_tool_name"),
        "created_by": data["created_by"],
        "owner": data.get("owner"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "reviewed_at": data.get("reviewed_at"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }


def create_review_item(
    *,
    title: str,
    description: str | None = None,
    category: str = "other",
    status: str = "open",
    priority: str = "normal",
    source_type: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_artifact_id: str | None = None,
    source_tool_name: str | None = None,
    created_by: str = "operator",
    owner: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create an operator-controlled review item in working.db."""
    normalized_title = _validate_title(title)
    _validate_category(category)
    _validate_status(status)
    _validate_priority(priority)
    metadata_json = _metadata_to_json(metadata)

    created_by = (created_by or "operator").strip() or "operator"
    item_id = str(uuid.uuid4())
    now = _now()
    reviewed_at = now if status in REVIEWED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.review_items
               (item_id, title, description, category, status, priority,
                source_type, source_conversation_id, source_message_id,
                source_artifact_id, source_tool_name, created_by, owner,
                created_at, updated_at, reviewed_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_id,
                normalized_title,
                description,
                category,
                status,
                priority,
                source_type,
                source_conversation_id,
                source_message_id,
                source_artifact_id,
                source_tool_name,
                created_by,
                owner,
                now,
                now,
                reviewed_at,
                metadata_json,
            ),
        )
        conn.commit()

    return get_review_item(item_id)


def get_review_item(item_id: str) -> dict | None:
    """Fetch a review item by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.review_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
    return review_item_to_dict(row)


def list_review_items(
    *,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List review items with optional filters."""
    clauses = []
    params = []

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if category is not None:
        _validate_category(category)
        clauses.append("category = ?")
        params.append(category)

    if priority is not None:
        _validate_priority(priority)
        clauses.append("priority = ?")
        params.append(priority)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.review_items
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [review_item_to_dict(row) for row in rows]


def update_review_item_status(item_id: str, status: str) -> dict | None:
    """Update a review item's status and reviewed_at lifecycle fields."""
    _validate_status(status)
    updated_at = _now()
    reviewed_at = updated_at if status in REVIEWED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.review_items
               SET status = ?, updated_at = ?, reviewed_at = ?
               WHERE item_id = ?""",
            (status, updated_at, reviewed_at, item_id),
        )
        conn.commit()

    return get_review_item(item_id)
