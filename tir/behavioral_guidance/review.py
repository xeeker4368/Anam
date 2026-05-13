"""Conversation review path for AI-proposed behavioral guidance candidates.

This module reviews one selected chat conversation and may create proposed
behavioral guidance records for admin review. It does not read or mutate
BEHAVIORAL_GUIDANCE.md, does not approve proposals, and does not use tools.
"""

import json
import re
from datetime import date, datetime, time, timezone, timedelta

from tir.behavioral_guidance.service import (
    ALLOWED_PROPOSAL_TYPES,
    list_behavioral_guidance_proposals,
    create_behavioral_guidance_proposal,
)
from tir.config import BEHAVIORAL_GUIDANCE_REVIEW_MODEL, OLLAMA_HOST
from tir.engine.ollama import chat_completion_json
from tir.memory.db import (
    get_connection,
    get_conversation,
    get_conversation_messages,
    get_user,
)


MAX_REVIEW_PROPOSALS = 3
DEFAULT_REVIEW_PROPOSALS = 1
DEFAULT_DAILY_MAX_CONVERSATIONS = 10
DEFAULT_DAILY_MAX_TOTAL_PROPOSALS = 5
MIN_REVIEW_MESSAGE_COUNT = 3


class BehavioralGuidanceReviewError(ValueError):
    """Raised when a conversation review cannot produce valid proposals."""


def _normalize_max_proposals(max_proposals: int) -> int:
    try:
        value = int(max_proposals)
    except (TypeError, ValueError) as exc:
        raise BehavioralGuidanceReviewError("max_proposals must be an integer") from exc
    if value < 1:
        raise BehavioralGuidanceReviewError("max_proposals must be at least 1")
    if value > MAX_REVIEW_PROPOSALS:
        raise BehavioralGuidanceReviewError(
            f"max_proposals must be {MAX_REVIEW_PROPOSALS} or less"
        )
    return value


def _normalize_positive_int(value, field: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise BehavioralGuidanceReviewError(f"{field} must be an integer") from exc
    if normalized < 1:
        raise BehavioralGuidanceReviewError(f"{field} must be at least 1")
    return normalized


def _parse_utc_timestamp(value: str, field: str) -> str:
    if not value or not value.strip():
        raise BehavioralGuidanceReviewError(f"{field} is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BehavioralGuidanceReviewError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise BehavioralGuidanceReviewError(f"{field} must include timezone or Z")
    return parsed.astimezone(timezone.utc).isoformat()


def get_local_timezone():
    """Return the system local timezone object."""
    return datetime.now().astimezone().tzinfo


def _timezone_name(tzinfo) -> str | None:
    return getattr(tzinfo, "key", None) or datetime.now(tzinfo).tzname()


def _format_offset(dt: datetime) -> str | None:
    offset = dt.utcoffset()
    if offset is None:
        return None
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def local_day_window_to_utc(
    date_text: str | None = None,
    *,
    tzinfo=None,
) -> dict:
    """Interpret a local/system date and return its UTC query window."""
    tzinfo = tzinfo or get_local_timezone()
    if date_text:
        try:
            day = date.fromisoformat(date_text)
        except ValueError as exc:
            raise BehavioralGuidanceReviewError("date must use YYYY-MM-DD") from exc
    else:
        day = datetime.now(tzinfo).date()
    local_start = datetime.combine(day, time.min, tzinfo=tzinfo)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    return {
        "local_date": day.isoformat(),
        "timezone": _timezone_name(tzinfo),
        "local_offset": _format_offset(local_start),
        "utc_start": utc_start.isoformat(),
        "utc_end": utc_end.isoformat(),
    }


def load_conversation_for_guidance_review(conversation_id: str) -> dict:
    """Load one working chat conversation and its ordered messages."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise BehavioralGuidanceReviewError(f"Conversation not found: {conversation_id}")

    messages = get_conversation_messages(conversation_id)
    user = get_user(conversation["user_id"]) if conversation.get("user_id") else None
    return {
        "conversation": conversation,
        "messages": messages,
        "user": user,
    }


def _conversation_rows_by_ids(conversation_ids: list[str]) -> list[dict]:
    rows = []
    seen = set()
    for conversation_id in conversation_ids:
        if not conversation_id or conversation_id in seen:
            continue
        seen.add(conversation_id)
        conversation = get_conversation(conversation_id)
        if conversation is None:
            rows.append(
                {
                    "id": conversation_id,
                    "missing": True,
                    "skip_reason": "conversation_not_found",
                    "message_count": 0,
                }
            )
        else:
            rows.append(conversation)
    return rows


def list_conversations_for_guidance_review(
    *,
    date_text: str | None = None,
    since: str | None = None,
    conversation_ids: list[str] | None = None,
    max_conversations: int = DEFAULT_DAILY_MAX_CONVERSATIONS,
    tzinfo=None,
) -> tuple[list[dict], dict]:
    """Select chat conversations for a bounded manual daily review."""
    max_conversations = _normalize_positive_int(max_conversations, "max_conversations")
    if conversation_ids:
        metadata = {
            "selection_mode": "conversation_id",
            "local_date": None,
            "timezone": None,
            "local_offset": None,
            "utc_start": None,
            "utc_end": None,
            "since": None,
        }
        return _conversation_rows_by_ids(conversation_ids)[:max_conversations], metadata
    if date_text and since:
        raise BehavioralGuidanceReviewError("Use either date or since, not both")

    params = []
    if since:
        utc_start = _parse_utc_timestamp(since, "since")
        where = "WHERE m.timestamp >= ?"
        params.append(utc_start)
        metadata = {
            "selection_mode": "since",
            "local_date": None,
            "timezone": None,
            "local_offset": None,
            "utc_start": utc_start,
            "utc_end": None,
            "since": since,
        }
    else:
        metadata = local_day_window_to_utc(date_text, tzinfo=tzinfo)
        metadata["selection_mode"] = "date"
        metadata["since"] = None
        where = "WHERE m.timestamp >= ? AND m.timestamp < ?"
        params.extend([metadata["utc_start"], metadata["utc_end"]])

    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT c.*,
                       MIN(m.timestamp) AS first_activity_at,
                       COUNT(m.id) AS window_message_count
                FROM main.messages m
                JOIN main.conversations c ON c.id = m.conversation_id
                {where}
                GROUP BY c.id
                ORDER BY first_activity_at ASC
                LIMIT ?""",
            (*params, max_conversations),
        ).fetchall()
    return [dict(row) for row in rows], metadata


def has_existing_conversation_review_proposals(conversation_id: str) -> bool:
    """Return true if conversation_review_v1 proposals already exist."""
    proposals = list_behavioral_guidance_proposals(limit=500)
    for proposal in proposals:
        if proposal.get("source_conversation_id") != conversation_id:
            continue
        metadata = proposal.get("metadata") or {}
        if metadata.get("generation_method") == "conversation_review_v1":
            return True
    return False


def _format_transcript(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        message_id = message.get("id") or "unknown"
        role = message.get("role") or "unknown"
        timestamp = message.get("timestamp") or "unknown"
        content = message.get("content") or ""
        lines.append(
            f"[message_id={message_id} role={role} timestamp={timestamp}]\n{content}"
        )
    return "\n\n".join(lines)


def build_behavioral_guidance_review_messages(
    *,
    conversation: dict,
    messages: list[dict],
    user: dict | None = None,
    max_proposals: int = DEFAULT_REVIEW_PROPOSALS,
) -> list[dict]:
    """Build strict JSON review messages for the local model."""
    max_proposals = _normalize_max_proposals(max_proposals)
    user_line = (
        f"source_user_id={conversation.get('user_id')} user_name={user.get('name')}"
        if user
        else f"source_user_id={conversation.get('user_id')}"
    )
    transcript = _format_transcript(messages)

    system = (
        "Review one selected chat conversation for possible AI-proposed "
        "behavioral guidance candidates. Return only a strict JSON object. "
        "This review may propose candidates for admin review, but it does not "
        "approve, reject, apply, or mutate guidance. Prefer narrow, atomic "
        "guidance candidates. Zero proposals is acceptable."
    )
    user_prompt = f"""Review this selected chat conversation only.

Return strict JSON with this shape:
{{
  "proposals": [
    {{
      "proposal_type": "addition",
      "proposal_text": "one atomic proposed change",
      "target_existing_guidance_id": null,
      "target_text": null,
      "rationale": "why this belongs in admin review",
      "source_experience_summary": "brief summary of the source experience",
      "source_message_id": null,
      "risk_if_added": "risk if admin approves it",
      "risk_if_not_added": "risk if admin does not approve it",
      "metadata": {{}}
    }}
  ],
  "no_proposal_reason": null
}}

Rules:
- Generate at most {max_proposals} proposal(s).
- Use proposal_type addition, removal, or revision only.
- For removal or revision, include target_existing_guidance_id or target_text.
- source_message_id may be set only when one specific message is evidence.
- Return an empty proposals list if no good proposal is warranted.
- Only propose when the conversation contains a correction, clarification,
  recurring preference, source-framing issue, or behavioral pattern that may
  affect future behavior.
- Do not use memory outside this transcript.
- Do not read or rely on BEHAVIORAL_GUIDANCE.md.

Conversation:
conversation_id={conversation.get('id')}
{user_line}
started_at={conversation.get('started_at')}
ended_at={conversation.get('ended_at')}

Transcript:
{transcript}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _strip_json_fence(raw: str) -> str:
    text = (raw or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text


def parse_behavioral_guidance_review_json(raw: str) -> dict:
    """Parse strict model JSON and return the decoded object."""
    text = _strip_json_fence(raw)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BehavioralGuidanceReviewError(f"Model returned malformed JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BehavioralGuidanceReviewError("Model JSON root must be an object")
    return parsed


def _optional_text(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BehavioralGuidanceReviewError("Optional text fields must be strings")
    normalized = value.strip()
    return normalized or None


def _required_text(proposal: dict, field: str) -> str:
    value = proposal.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BehavioralGuidanceReviewError(f"{field} is required")
    return value.strip()


def validate_generated_proposals(
    payload: dict,
    *,
    conversation: dict,
    messages: list[dict],
    max_proposals: int = DEFAULT_REVIEW_PROPOSALS,
    model: str = BEHAVIORAL_GUIDANCE_REVIEW_MODEL,
) -> list[dict]:
    """Validate and normalize model proposals before any DB writes."""
    max_proposals = _normalize_max_proposals(max_proposals)
    proposals = payload.get("proposals")
    if proposals is None:
        raise BehavioralGuidanceReviewError("Model JSON must include proposals")
    if not isinstance(proposals, list):
        raise BehavioralGuidanceReviewError("proposals must be a list")
    if len(proposals) > max_proposals:
        raise BehavioralGuidanceReviewError(
            f"Model returned {len(proposals)} proposals; max is {max_proposals}"
        )

    message_ids = {message.get("id") for message in messages if message.get("id")}
    normalized = []
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            raise BehavioralGuidanceReviewError("Each proposal must be an object")

        proposal_type = _required_text(proposal, "proposal_type")
        proposal_text = _required_text(proposal, "proposal_text")
        rationale = _required_text(proposal, "rationale")
        target_existing_guidance_id = _optional_text(
            proposal.get("target_existing_guidance_id")
        )
        target_text = _optional_text(proposal.get("target_text"))
        source_message_id = _optional_text(proposal.get("source_message_id"))
        if source_message_id and source_message_id not in message_ids:
            raise BehavioralGuidanceReviewError(
                f"source_message_id does not belong to selected conversation: {source_message_id}"
            )

        metadata = proposal.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise BehavioralGuidanceReviewError("metadata must be an object when supplied")
        metadata = {
            **metadata,
            "generation_method": "conversation_review_v1",
            "model": model,
            "proposal_index": index,
            "max_proposals": max_proposals,
        }

        candidate = {
            "proposal_type": proposal_type,
            "proposal_text": proposal_text,
            "target_existing_guidance_id": target_existing_guidance_id,
            "target_text": target_text,
            "rationale": rationale,
            "source_experience_summary": _optional_text(
                proposal.get("source_experience_summary")
            ),
            "source_user_id": conversation.get("user_id"),
            "source_conversation_id": conversation.get("id"),
            "source_message_id": source_message_id,
            "source_channel": "chat",
            "risk_if_added": _optional_text(proposal.get("risk_if_added")),
            "risk_if_not_added": _optional_text(proposal.get("risk_if_not_added")),
            "metadata": metadata,
        }

        if candidate["proposal_type"] not in ALLOWED_PROPOSAL_TYPES:
            raise BehavioralGuidanceReviewError(
                f"Invalid behavioral guidance proposal type: {candidate['proposal_type']}"
            )
        if candidate["proposal_type"] in {"removal", "revision"} and not (
            candidate["target_existing_guidance_id"] or candidate["target_text"]
        ):
            raise BehavioralGuidanceReviewError(
                "removal and revision proposals require target_existing_guidance_id or target_text"
            )

        normalized.append(candidate)

    return normalized


def generate_behavioral_guidance_review(
    conversation_id: str,
    *,
    max_proposals: int = DEFAULT_REVIEW_PROPOSALS,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate validated proposal candidates for one conversation."""
    model = model or BEHAVIORAL_GUIDANCE_REVIEW_MODEL
    loaded = load_conversation_for_guidance_review(conversation_id)
    messages = build_behavioral_guidance_review_messages(
        conversation=loaded["conversation"],
        messages=loaded["messages"],
        user=loaded["user"],
        max_proposals=max_proposals,
    )
    raw = chat_completion_json(
        messages,
        model=model,
        ollama_host=ollama_host,
        role="behavioral_guidance_review",
    )
    payload = parse_behavioral_guidance_review_json(raw)
    proposals = validate_generated_proposals(
        payload,
        conversation=loaded["conversation"],
        messages=loaded["messages"],
        max_proposals=max_proposals,
        model=model,
    )
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "source_user_id": loaded["conversation"].get("user_id"),
        "message_count": len(loaded["messages"]),
        "max_proposals": _normalize_max_proposals(max_proposals),
        "model": model,
        "proposals": proposals,
        "no_proposal_reason": _optional_text(payload.get("no_proposal_reason")),
        "raw_response": raw,
    }


def write_behavioral_guidance_review_proposals(review_result: dict) -> list[dict]:
    """Persist already-validated proposal candidates as proposed records."""
    created = []
    for proposal in review_result.get("proposals", []):
        created.append(create_behavioral_guidance_proposal(**proposal))
    return created


def generate_behavioral_guidance_daily_review(
    *,
    date_text: str | None = None,
    since: str | None = None,
    conversation_ids: list[str] | None = None,
    write: bool = False,
    max_conversations: int = DEFAULT_DAILY_MAX_CONVERSATIONS,
    max_proposals_per_conversation: int = DEFAULT_REVIEW_PROPOSALS,
    max_total_proposals: int = DEFAULT_DAILY_MAX_TOTAL_PROPOSALS,
    model: str | None = None,
    allow_duplicates: bool = False,
) -> dict:
    """Run a bounded manual review across recent/selected conversations."""
    max_conversations = _normalize_positive_int(max_conversations, "max_conversations")
    max_total_proposals = _normalize_positive_int(
        max_total_proposals,
        "max_total_proposals",
    )
    max_proposals_per_conversation = _normalize_max_proposals(
        max_proposals_per_conversation
    )

    selected, selection = list_conversations_for_guidance_review(
        date_text=date_text,
        since=since,
        conversation_ids=conversation_ids,
        max_conversations=max_conversations,
    )
    results = []
    total_proposals = 0
    created_count = 0
    stopped_reason = None

    for conversation in selected:
        conversation_id = conversation.get("id")
        if total_proposals >= max_total_proposals:
            stopped_reason = "max_total_proposals_reached"
            break

        if conversation.get("missing"):
            results.append(
                {
                    "conversation_id": conversation_id,
                    "status": "skipped",
                    "message_count": 0,
                    "proposal_count": 0,
                    "skip_reason": conversation.get("skip_reason"),
                    "created_proposal_ids": [],
                }
            )
            continue

        message_count = int(conversation.get("message_count") or 0)
        if message_count < MIN_REVIEW_MESSAGE_COUNT:
            results.append(
                {
                    "conversation_id": conversation_id,
                    "status": "skipped",
                    "message_count": message_count,
                    "proposal_count": 0,
                    "skip_reason": "too_few_messages",
                    "created_proposal_ids": [],
                }
            )
            continue

        if not allow_duplicates and has_existing_conversation_review_proposals(
            conversation_id
        ):
            results.append(
                {
                    "conversation_id": conversation_id,
                    "status": "skipped",
                    "message_count": message_count,
                    "proposal_count": 0,
                    "skip_reason": "duplicate_review_exists",
                    "created_proposal_ids": [],
                }
            )
            continue

        remaining = max_total_proposals - total_proposals
        per_conversation_limit = min(max_proposals_per_conversation, remaining)
        try:
            review = generate_behavioral_guidance_review(
                conversation_id,
                max_proposals=per_conversation_limit,
                model=model,
            )
        except Exception as exc:
            results.append(
                {
                    "conversation_id": conversation_id,
                    "status": "failed",
                    "message_count": message_count,
                    "proposal_count": 0,
                    "error": str(exc),
                    "created_proposal_ids": [],
                }
            )
            continue

        proposals = review.get("proposals", [])
        total_proposals += len(proposals)
        created = []
        if write and proposals:
            try:
                created = write_behavioral_guidance_review_proposals(review)
            except Exception as exc:
                results.append(
                    {
                        "conversation_id": conversation_id,
                        "status": "failed",
                        "message_count": review.get("message_count", message_count),
                        "proposal_count": len(proposals),
                        "error": str(exc),
                        "created_proposal_ids": [],
                    }
                )
                continue
            created_count += len(created)

        results.append(
            {
                "conversation_id": conversation_id,
                "status": "reviewed",
                "message_count": review.get("message_count", message_count),
                "proposal_count": len(proposals),
                "no_proposal_reason": review.get("no_proposal_reason"),
                "proposals": proposals,
                "created_proposal_ids": [
                    proposal["proposal_id"] for proposal in created
                ],
            }
        )

    return {
        "ok": True,
        "mode": "write" if write else "dry-run",
        "selected_conversations": len(selected),
        "reviewed_conversations": len(
            [result for result in results if result["status"] == "reviewed"]
        ),
        "skipped_conversations": len(
            [result for result in results if result["status"] == "skipped"]
        ),
        "failed_conversations": len(
            [result for result in results if result["status"] == "failed"]
        ),
        "proposal_count": total_proposals,
        "created_proposal_count": created_count,
        "max_conversations": max_conversations,
        "max_proposals_per_conversation": max_proposals_per_conversation,
        "max_total_proposals": max_total_proposals,
        "stopped_reason": stopped_reason,
        "selection": selection,
        "results": results,
    }
