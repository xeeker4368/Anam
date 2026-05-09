"""Conversation review path for AI-proposed behavioral guidance candidates.

This module reviews one selected chat conversation and may create proposed
behavioral guidance records for admin review. It does not read or mutate
BEHAVIORAL_GUIDANCE.md, does not approve proposals, and does not use tools.
"""

import json
import re

from tir.behavioral_guidance.service import (
    ALLOWED_PROPOSAL_TYPES,
    create_behavioral_guidance_proposal,
)
from tir.config import CHAT_MODEL, OLLAMA_HOST
from tir.engine.ollama import chat_completion_json
from tir.memory.db import get_conversation, get_conversation_messages, get_user


MAX_REVIEW_PROPOSALS = 3
DEFAULT_REVIEW_PROPOSALS = 1


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
        "You review one selected Project Anam chat conversation for possible "
        "AI-proposed behavioral guidance candidates. Return only a strict JSON "
        "object. Do not approve, reject, apply, or mutate guidance. Do not write "
        "user-authored rules. Do not propose broad personality traits. Do not "
        "turn every correction into durable guidance. One proposal must contain "
        "one atomic addition, removal, or revision. Zero proposals is acceptable."
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
    model: str = CHAT_MODEL,
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
    model = model or CHAT_MODEL
    loaded = load_conversation_for_guidance_review(conversation_id)
    messages = build_behavioral_guidance_review_messages(
        conversation=loaded["conversation"],
        messages=loaded["messages"],
        user=loaded["user"],
        max_proposals=max_proposals,
    )
    raw = chat_completion_json(messages, model=model, ollama_host=ollama_host)
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
