"""Internal diagnostic issue registry service.

Diagnostic issues are evidence-backed records for substrate, tool, retrieval,
memory, workflow, UI, or behavior problems. They are not research ideas, tasks,
tools, API routes, UI behavior, memory chunks, or self-modification proposals.
"""

import json
import uuid
from datetime import datetime, timezone


ALLOWED_DIAGNOSTIC_CATEGORIES = {
    "tool_failure",
    "tool_result_quality",
    "retrieval_quality",
    "memory_quality",
    "context_quality",
    "schema_validation",
    "permission",
    "external_service",
    "performance",
    "ui_visibility",
    "operational_guidance",
    "self_mod_candidate",
    "generic",
}

ALLOWED_DIAGNOSTIC_STATUSES = {
    "open",
    "investigating",
    "blocked",
    "resolved",
    "archived",
}

ALLOWED_DIAGNOSTIC_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}

RESOLVED_STATUSES = {"resolved", "archived"}


class DiagnosticValidationError(ValueError):
    """Raised when diagnostic issue metadata is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_category(category: str) -> None:
    if category not in ALLOWED_DIAGNOSTIC_CATEGORIES:
        raise DiagnosticValidationError(f"Invalid diagnostic category: {category}")


def _validate_status(status: str) -> None:
    if status not in ALLOWED_DIAGNOSTIC_STATUSES:
        raise DiagnosticValidationError(f"Invalid diagnostic status: {status}")


def _validate_severity(severity: str) -> None:
    if severity not in ALLOWED_DIAGNOSTIC_SEVERITIES:
        raise DiagnosticValidationError(f"Invalid diagnostic severity: {severity}")


def _validate_required_text(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise DiagnosticValidationError(f"{field_name} is required")
    return value.strip()


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise DiagnosticValidationError("metadata must be JSON serializable") from exc


def diagnostic_issue_to_dict(row) -> dict | None:
    """Convert a diagnostic issue DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    metadata = json.loads(metadata_json) if metadata_json else None
    return {
        "diagnostic_id": data["diagnostic_id"],
        "title": data["title"],
        "description": data.get("description"),
        "category": data["category"],
        "status": data["status"],
        "severity": data["severity"],
        "evidence_summary": data["evidence_summary"],
        "suspected_component": data.get("suspected_component"),
        "related_feedback_id": data.get("related_feedback_id"),
        "related_open_loop_id": data.get("related_open_loop_id"),
        "related_artifact_id": data.get("related_artifact_id"),
        "source": data.get("source"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_tool_name": data.get("source_tool_name"),
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "next_action": data.get("next_action"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "resolved_at": data.get("resolved_at"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }


def create_diagnostic_issue(
    *,
    title: str,
    evidence_summary: str,
    category: str = "generic",
    status: str = "open",
    severity: str = "medium",
    description: str | None = None,
    suspected_component: str | None = None,
    related_feedback_id: str | None = None,
    related_open_loop_id: str | None = None,
    related_artifact_id: str | None = None,
    source: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_tool_name: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    next_action: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create an internal diagnostic issue metadata record in working.db."""
    normalized_title = _validate_required_text(title, "title")
    normalized_evidence = _validate_required_text(evidence_summary, "evidence_summary")
    _validate_category(category)
    _validate_status(status)
    _validate_severity(severity)
    metadata_json = _metadata_to_json(metadata)

    diagnostic_id = str(uuid.uuid4())
    now = _now()
    resolved_at = now if status in RESOLVED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.diagnostic_issues
               (diagnostic_id, title, description, category, status, severity,
                evidence_summary, suspected_component, related_feedback_id,
                related_open_loop_id, related_artifact_id, source,
                source_conversation_id, source_message_id, source_tool_name,
                target_type, target_id, next_action, created_at, updated_at,
                resolved_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                diagnostic_id,
                normalized_title,
                description,
                category,
                status,
                severity,
                normalized_evidence,
                suspected_component,
                related_feedback_id,
                related_open_loop_id,
                related_artifact_id,
                source,
                source_conversation_id,
                source_message_id,
                source_tool_name,
                target_type,
                target_id,
                next_action,
                now,
                now,
                resolved_at,
                metadata_json,
            ),
        )
        conn.commit()

    return get_diagnostic_issue(diagnostic_id)


def get_diagnostic_issue(diagnostic_id: str) -> dict | None:
    """Fetch a diagnostic issue by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.diagnostic_issues WHERE diagnostic_id = ?",
            (diagnostic_id,),
        ).fetchone()
    return diagnostic_issue_to_dict(row)


def list_diagnostic_issues(
    *,
    category: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    related_feedback_id: str | None = None,
    related_open_loop_id: str | None = None,
    related_artifact_id: str | None = None,
    source_conversation_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List diagnostic issues with optional metadata filters."""
    clauses = []
    params = []

    if category is not None:
        _validate_category(category)
        clauses.append("category = ?")
        params.append(category)

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if severity is not None:
        _validate_severity(severity)
        clauses.append("severity = ?")
        params.append(severity)

    if related_feedback_id is not None:
        clauses.append("related_feedback_id = ?")
        params.append(related_feedback_id)

    if related_open_loop_id is not None:
        clauses.append("related_open_loop_id = ?")
        params.append(related_open_loop_id)

    if related_artifact_id is not None:
        clauses.append("related_artifact_id = ?")
        params.append(related_artifact_id)

    if source_conversation_id is not None:
        clauses.append("source_conversation_id = ?")
        params.append(source_conversation_id)

    if target_type is not None:
        clauses.append("target_type = ?")
        params.append(target_type)

    if target_id is not None:
        clauses.append("target_id = ?")
        params.append(target_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.diagnostic_issues
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [diagnostic_issue_to_dict(row) for row in rows]


def update_diagnostic_status(diagnostic_id: str, status: str) -> dict | None:
    """Update only a diagnostic issue's status and resolved_at lifecycle field."""
    _validate_status(status)
    updated_at = _now()
    resolved_at = updated_at if status in RESOLVED_STATUSES else None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.diagnostic_issues
               SET status = ?, updated_at = ?, resolved_at = ?
               WHERE diagnostic_id = ?""",
            (status, updated_at, resolved_at, diagnostic_id),
        )
        conn.commit()

    return get_diagnostic_issue(diagnostic_id)
