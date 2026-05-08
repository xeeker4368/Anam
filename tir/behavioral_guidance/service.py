"""AI-proposed behavioral guidance proposal service.

Behavioral guidance proposals are candidates for reviewed guidance. They are
AI-proposed by definition; approval, rejection, and application are admin-only
decisions. This module does not modify BEHAVIORAL_GUIDANCE.md.
"""

import json
import uuid
from datetime import datetime, timezone


ALLOWED_PROPOSAL_TYPES = {"addition", "removal", "revision"}
ALLOWED_SOURCE_CHANNELS = {"chat", "imessage", "unknown"}
ALLOWED_STATUSES = {"proposed", "approved", "rejected", "applied", "archived"}
DECISION_STATUSES = {"approved", "rejected", "applied", "archived"}
APPLIED_STATUS = "applied"


class BehavioralGuidanceValidationError(ValueError):
    """Raised when a behavioral guidance proposal is invalid."""


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_text(value: str | None, field: str) -> str:
    if not value or not value.strip():
        raise BehavioralGuidanceValidationError(f"{field} is required")
    return value.strip()


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_proposal_type(proposal_type: str) -> None:
    if proposal_type not in ALLOWED_PROPOSAL_TYPES:
        raise BehavioralGuidanceValidationError(
            f"Invalid behavioral guidance proposal type: {proposal_type}"
        )


def _validate_source_channel(source_channel: str) -> None:
    if source_channel not in ALLOWED_SOURCE_CHANNELS:
        raise BehavioralGuidanceValidationError(
            f"Invalid behavioral guidance source channel: {source_channel}"
        )


def _validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise BehavioralGuidanceValidationError(
            f"Invalid behavioral guidance proposal status: {status}"
        )


def _metadata_to_json(metadata: dict | None) -> str | None:
    if metadata is None:
        return None
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError as exc:
        raise BehavioralGuidanceValidationError(
            "metadata must be JSON serializable"
        ) from exc


def _validate_target(proposal_type: str, target_existing_guidance_id: str | None, target_text: str | None) -> None:
    if proposal_type in {"removal", "revision"} and not (
        target_existing_guidance_id or target_text
    ):
        raise BehavioralGuidanceValidationError(
            "removal and revision proposals require target_existing_guidance_id or target_text"
        )


def _validate_decision(
    *,
    status: str,
    reviewed_by_role: str | None,
    review_decision_reason: str | None,
) -> None:
    if status not in DECISION_STATUSES:
        return
    if reviewed_by_role != "admin":
        raise BehavioralGuidanceValidationError(
            "approved, rejected, applied, and archived proposals require reviewed_by_role=admin"
        )
    if status == "rejected" and not review_decision_reason:
        raise BehavioralGuidanceValidationError(
            "review_decision_reason is required when rejecting a proposal"
        )


def behavioral_guidance_proposal_to_dict(row) -> dict | None:
    """Convert a DB row to a stable service result shape."""
    if row is None:
        return None

    data = dict(row)
    metadata_json = data.get("metadata_json")
    metadata = json.loads(metadata_json) if metadata_json else None
    return {
        "proposal_id": data["proposal_id"],
        "proposal_type": data["proposal_type"],
        "proposal_text": data["proposal_text"],
        "target_existing_guidance_id": data.get("target_existing_guidance_id"),
        "target_text": data.get("target_text"),
        "rationale": data["rationale"],
        "source_experience_summary": data.get("source_experience_summary"),
        "source_user_id": data.get("source_user_id"),
        "source_conversation_id": data.get("source_conversation_id"),
        "source_message_id": data.get("source_message_id"),
        "source_channel": data["source_channel"],
        "risk_if_added": data.get("risk_if_added"),
        "risk_if_not_added": data.get("risk_if_not_added"),
        "status": data["status"],
        "reviewed_by_user_id": data.get("reviewed_by_user_id"),
        "reviewed_by_role": data.get("reviewed_by_role"),
        "review_decision_reason": data.get("review_decision_reason"),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "reviewed_at": data.get("reviewed_at"),
        "applied_by_user_id": data.get("applied_by_user_id"),
        "applied_at": data.get("applied_at"),
        "apply_note": data.get("apply_note"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }


def create_behavioral_guidance_proposal(
    *,
    proposal_type: str,
    proposal_text: str,
    rationale: str,
    target_existing_guidance_id: str | None = None,
    target_text: str | None = None,
    source_experience_summary: str | None = None,
    source_user_id: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_channel: str = "unknown",
    risk_if_added: str | None = None,
    risk_if_not_added: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create an AI-proposed behavioral guidance candidate."""
    _validate_proposal_type(proposal_type)
    _validate_source_channel(source_channel)
    normalized_proposal_text = _require_text(proposal_text, "proposal_text")
    normalized_rationale = _require_text(rationale, "rationale")
    target_existing_guidance_id = _optional_text(target_existing_guidance_id)
    target_text = _optional_text(target_text)
    _validate_target(proposal_type, target_existing_guidance_id, target_text)
    metadata_json = _metadata_to_json(metadata)

    proposal_id = str(uuid.uuid4())
    now = _now()

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """INSERT INTO main.behavioral_guidance_proposals
               (proposal_id, proposal_type, proposal_text, target_existing_guidance_id,
                target_text, rationale, source_experience_summary, source_user_id,
                source_conversation_id, source_message_id, source_channel,
                risk_if_added, risk_if_not_added, status, created_at, updated_at,
                metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                proposal_id,
                proposal_type,
                normalized_proposal_text,
                target_existing_guidance_id,
                target_text,
                normalized_rationale,
                _optional_text(source_experience_summary),
                _optional_text(source_user_id),
                _optional_text(source_conversation_id),
                _optional_text(source_message_id),
                source_channel,
                _optional_text(risk_if_added),
                _optional_text(risk_if_not_added),
                "proposed",
                now,
                now,
                metadata_json,
            ),
        )
        conn.commit()

    return get_behavioral_guidance_proposal(proposal_id)


def get_behavioral_guidance_proposal(proposal_id: str) -> dict | None:
    """Fetch a behavioral guidance proposal by id."""
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM main.behavioral_guidance_proposals
               WHERE proposal_id = ?""",
            (proposal_id,),
        ).fetchone()
    return behavioral_guidance_proposal_to_dict(row)


def list_behavioral_guidance_proposals(
    *,
    status: str | None = None,
    proposal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List behavioral guidance proposals with optional filters."""
    clauses = []
    params = []

    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)

    if proposal_type is not None:
        _validate_proposal_type(proposal_type)
        clauses.append("proposal_type = ?")
        params.append(proposal_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""SELECT * FROM main.behavioral_guidance_proposals
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [behavioral_guidance_proposal_to_dict(row) for row in rows]


def update_behavioral_guidance_proposal_status(
    proposal_id: str,
    status: str,
    *,
    reviewed_by_user_id: str | None = None,
    reviewed_by_role: str | None = None,
    review_decision_reason: str | None = None,
    applied_by_user_id: str | None = None,
    apply_note: str | None = None,
) -> dict | None:
    """Update proposal lifecycle status without applying file changes."""
    _validate_status(status)
    review_decision_reason = _optional_text(review_decision_reason)
    reviewed_by_user_id = _optional_text(reviewed_by_user_id)
    reviewed_by_role = _optional_text(reviewed_by_role)
    applied_by_user_id = _optional_text(applied_by_user_id)
    apply_note = _optional_text(apply_note)
    _validate_decision(
        status=status,
        reviewed_by_role=reviewed_by_role,
        review_decision_reason=review_decision_reason,
    )

    updated_at = _now()
    if status == "proposed":
        reviewed_at = None
        reviewed_by_user_id = None
        reviewed_by_role = None
        review_decision_reason = None
        applied_by_user_id = None
        applied_at = None
        apply_note = None
    else:
        reviewed_at = updated_at if status in DECISION_STATUSES else None
        applied_at = updated_at if status == APPLIED_STATUS else None
        if status == APPLIED_STATUS and applied_by_user_id is None:
            applied_by_user_id = reviewed_by_user_id
        if status != APPLIED_STATUS:
            applied_by_user_id = None
            applied_at = None
            apply_note = None

    db_mod = _db()
    with db_mod.get_connection() as conn:
        conn.execute(
            """UPDATE main.behavioral_guidance_proposals
               SET status = ?, reviewed_by_user_id = ?, reviewed_by_role = ?,
                   review_decision_reason = ?, updated_at = ?, reviewed_at = ?,
                   applied_by_user_id = ?, applied_at = ?, apply_note = ?
               WHERE proposal_id = ?""",
            (
                status,
                reviewed_by_user_id,
                reviewed_by_role,
                review_decision_reason,
                updated_at,
                reviewed_at,
                applied_by_user_id,
                applied_at,
                apply_note,
                proposal_id,
            ),
        )
        conn.commit()

    return get_behavioral_guidance_proposal(proposal_id)
