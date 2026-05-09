"""Apply approved behavioral guidance proposals to BEHAVIORAL_GUIDANCE.md.

This module is intentionally CLI/operator oriented. It only supports approved
addition proposals in v1 and does not load guidance into runtime context.
"""

from datetime import datetime, timezone
from pathlib import Path

from tir.behavioral_guidance.service import (
    BehavioralGuidanceValidationError,
    get_behavioral_guidance_proposal,
    update_behavioral_guidance_proposal_status,
)
from tir.config import PROJECT_ROOT


ACTIVE_GUIDANCE_HEADING = "## Active Guidance"
DEFAULT_GUIDANCE_PATH = PROJECT_ROOT / "BEHAVIORAL_GUIDANCE.md"


class BehavioralGuidanceApplyError(ValueError):
    """Raised when an approved proposal cannot be applied to the guidance file."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_line(proposal: dict) -> str | None:
    conversation_id = proposal.get("source_conversation_id")
    message_id = proposal.get("source_message_id")
    if conversation_id and message_id:
        return f"- Source: conversation {conversation_id}, message {message_id}"
    if conversation_id:
        return f"- Source: conversation {conversation_id}"
    if message_id:
        return f"- Source: message {message_id}"
    return None


def build_guidance_append_block(
    proposal: dict,
    applied_at: str | None = None,
) -> str:
    """Build the deterministic Markdown block for one approved addition."""
    applied_at = applied_at or _now()
    lines = [
        f"### Proposal {proposal['proposal_id']}",
        "",
        f"- Proposal ID: {proposal['proposal_id']}",
        f"- Type: {proposal['proposal_type']}",
        f"- Applied: {applied_at}",
    ]
    source = _source_line(proposal)
    if source:
        lines.append(source)
    lines.extend(
        [
            f"- Guidance: {proposal['proposal_text']}",
            f"- Rationale: {proposal['rationale']}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _validate_applicable_proposal(proposal: dict | None) -> dict:
    if proposal is None:
        raise BehavioralGuidanceApplyError("Behavioral guidance proposal not found")
    if proposal.get("status") == "applied":
        raise BehavioralGuidanceApplyError("Behavioral guidance proposal is already applied")
    if proposal.get("status") != "approved":
        raise BehavioralGuidanceApplyError(
            "Only approved behavioral guidance proposals can be applied"
        )
    if proposal.get("proposal_type") != "addition":
        raise BehavioralGuidanceApplyError(
            "Only addition proposals can be applied in v1"
        )
    return proposal


def _read_guidance_file(guidance_path: Path) -> str:
    if not guidance_path.exists():
        raise BehavioralGuidanceApplyError(
            f"BEHAVIORAL_GUIDANCE.md not found at {guidance_path}"
        )
    return guidance_path.read_text(encoding="utf-8")


def _ensure_not_duplicate(content: str, proposal_id: str) -> None:
    if f"- Proposal ID: {proposal_id}" in content or f"### Proposal {proposal_id}" in content:
        raise BehavioralGuidanceApplyError(
            "BEHAVIORAL_GUIDANCE.md already contains this proposal ID"
        )


def _append_block(content: str, block: str) -> str:
    normalized = content.rstrip() + "\n"
    if ACTIVE_GUIDANCE_HEADING not in normalized:
        normalized += f"\n{ACTIVE_GUIDANCE_HEADING}\n"
    return normalized.rstrip() + "\n\n" + block.rstrip() + "\n"


def _write_atomic(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def plan_behavioral_guidance_apply(
    proposal_id: str,
    *,
    guidance_path: Path = DEFAULT_GUIDANCE_PATH,
) -> dict:
    """Validate and return the exact append block without mutating state."""
    guidance_path = Path(guidance_path)
    proposal = _validate_applicable_proposal(
        get_behavioral_guidance_proposal(proposal_id)
    )
    content = _read_guidance_file(guidance_path)
    _ensure_not_duplicate(content, proposal["proposal_id"])
    applied_at = _now()
    block = build_guidance_append_block(proposal, applied_at=applied_at)
    return {
        "ok": True,
        "proposal": proposal,
        "guidance_path": str(guidance_path),
        "applied_at": applied_at,
        "append_block": block,
    }


def apply_behavioral_guidance_proposal(
    proposal_id: str,
    *,
    applied_by_user_id: str | None = None,
    apply_note: str | None = None,
    guidance_path: Path = DEFAULT_GUIDANCE_PATH,
) -> dict:
    """Append an approved addition proposal and mark it applied."""
    plan = plan_behavioral_guidance_apply(
        proposal_id,
        guidance_path=guidance_path,
    )
    path = Path(guidance_path)
    content = _read_guidance_file(path)
    new_content = _append_block(content, plan["append_block"])
    _write_atomic(path, new_content)

    try:
        proposal = update_behavioral_guidance_proposal_status(
            proposal_id,
            "applied",
            reviewed_by_user_id=plan["proposal"].get("reviewed_by_user_id"),
            reviewed_by_role="admin",
            review_decision_reason=plan["proposal"].get("review_decision_reason"),
            applied_by_user_id=applied_by_user_id,
            apply_note=apply_note,
        )
    except BehavioralGuidanceValidationError as exc:
        raise BehavioralGuidanceApplyError(str(exc)) from exc

    return {
        "ok": True,
        "proposal": proposal,
        "guidance_path": str(path),
        "append_block": plan["append_block"],
    }
