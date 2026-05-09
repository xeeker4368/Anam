"""Manual reflection journal generation.

This module creates file-only daily reflection journals from selected chat
conversation activity. It does not schedule work, create behavioral guidance
proposals, mutate BEHAVIORAL_GUIDANCE.md, or index journals into memory.
"""

from pathlib import Path
from datetime import datetime, timezone
import os

from tir.behavioral_guidance.review import (
    BehavioralGuidanceReviewError,
    local_day_window_to_utc,
)
from tir.behavioral_guidance.service import list_behavioral_guidance_proposals
from tir.config import CHAT_MODEL, OLLAMA_HOST
from tir.engine.context import load_reflection_entity_context
from tir.engine.ollama import chat_completion_text
from tir.memory.db import get_connection
from tir.workspace.service import ensure_workspace, resolve_workspace_path


DEFAULT_REFLECTION_MAX_CONVERSATIONS = 10
REFLECTION_TRANSCRIPT_CHAR_BUDGET = 24000


class ReflectionJournalError(ValueError):
    """Raised when a reflection journal cannot be generated or written."""


def _workspace_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    import tir.config as config

    return Path(config.WORKSPACE_DIR)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_positive_int(value, field: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ReflectionJournalError(f"{field} must be an integer") from exc
    if normalized < 1:
        raise ReflectionJournalError(f"{field} must be at least 1")
    return normalized


def _local_date_from_selection(selection: dict) -> str:
    if selection.get("local_date"):
        return selection["local_date"]
    utc_start = selection.get("utc_start")
    if utc_start:
        return datetime.fromisoformat(utc_start).date().isoformat()
    return datetime.now().astimezone().date().isoformat()


def journal_relative_path(local_date: str) -> str:
    return f"journals/{local_date}.md"


def _parse_utc_timestamp(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ReflectionJournalError(f"{field} is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReflectionJournalError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ReflectionJournalError(f"{field} must include timezone or Z")
    return parsed.astimezone(timezone.utc).isoformat()


def list_conversations_for_reflection_journal(
    *,
    date_text: str | None = None,
    since: str | None = None,
    max_conversations: int = DEFAULT_REFLECTION_MAX_CONVERSATIONS,
    tzinfo=None,
) -> tuple[list[dict], dict]:
    """Select conversations by message activity for a manual journal review."""
    max_conversations = _normalize_positive_int(max_conversations, "max_conversations")
    if date_text and since:
        raise ReflectionJournalError("Use either date or since, not both")

    params = []
    if since:
        utc_start = _parse_utc_timestamp(since, "since")
        where = "WHERE m.timestamp >= ?"
        params.append(utc_start)
        selection = {
            "selection_mode": "since",
            "local_date": None,
            "timezone": None,
            "local_offset": None,
            "utc_start": utc_start,
            "utc_end": None,
            "since": since,
        }
    else:
        try:
            selection = local_day_window_to_utc(date_text, tzinfo=tzinfo)
        except BehavioralGuidanceReviewError as exc:
            raise ReflectionJournalError(str(exc)) from exc
        selection["selection_mode"] = "date"
        selection["since"] = None
        where = "WHERE m.timestamp >= ? AND m.timestamp < ?"
        params.extend([selection["utc_start"], selection["utc_end"]])

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
    return [dict(row) for row in rows], selection


def _load_window_messages(conversation_id: str, selection: dict) -> list[dict]:
    params = [conversation_id]
    where = "conversation_id = ?"
    if selection.get("utc_start"):
        where += " AND timestamp >= ?"
        params.append(selection["utc_start"])
    if selection.get("utc_end"):
        where += " AND timestamp < ?"
        params.append(selection["utc_end"])

    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT * FROM main.messages
                WHERE {where}
                ORDER BY timestamp ASC""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _format_transcript(conversations: list[dict], selection: dict) -> tuple[str, dict]:
    parts = []
    total_messages = 0
    truncated = False
    used_chars = 0

    for conversation in conversations:
        conversation_id = conversation["id"]
        messages = _load_window_messages(conversation_id, selection)
        total_messages += len(messages)
        header = (
            f"Conversation {conversation_id}\n"
            f"user_id={conversation.get('user_id')} "
            f"started_at={conversation.get('started_at')} "
            f"ended_at={conversation.get('ended_at')} "
            f"window_message_count={len(messages)}"
        )
        message_lines = []
        for message in messages:
            content = message.get("content") or ""
            message_lines.append(
                "[message_id={id} role={role} timestamp={timestamp}]\n{content}".format(
                    id=message.get("id") or "unknown",
                    role=message.get("role") or "unknown",
                    timestamp=message.get("timestamp") or "unknown",
                    content=content,
                )
            )
        block = header + "\n" + "\n\n".join(message_lines)
        if used_chars + len(block) > REFLECTION_TRANSCRIPT_CHAR_BUDGET:
            remaining = REFLECTION_TRANSCRIPT_CHAR_BUDGET - used_chars
            if remaining > 500:
                parts.append(block[:remaining].rstrip() + "\n[reflection transcript truncated]")
                used_chars = REFLECTION_TRANSCRIPT_CHAR_BUDGET
            truncated = True
            break
        parts.append(block)
        used_chars += len(block)

    return "\n\n---\n\n".join(parts), {
        "message_count": total_messages,
        "transcript_chars": used_chars,
        "transcript_truncated": truncated,
        "transcript_budget_chars": REFLECTION_TRANSCRIPT_CHAR_BUDGET,
    }


def _guidance_activity_in_window(selection: dict) -> list[dict]:
    """Return compact factual guidance proposal activity for the window."""
    utc_start = selection.get("utc_start")
    utc_end = selection.get("utc_end")
    if not utc_start:
        return []

    proposals = list_behavioral_guidance_proposals(limit=500)
    activity = []
    for proposal in proposals:
        timestamps = [
            proposal.get("created_at"),
            proposal.get("reviewed_at"),
            proposal.get("applied_at"),
        ]
        in_window = False
        for value in timestamps:
            if not value:
                continue
            if value < utc_start:
                continue
            if utc_end and value >= utc_end:
                continue
            in_window = True
            break
        if not in_window:
            continue
        activity.append(
            {
                "proposal_id": proposal.get("proposal_id"),
                "proposal_type": proposal.get("proposal_type"),
                "status": proposal.get("status"),
                "proposal_text": proposal.get("proposal_text"),
                "source_conversation_id": proposal.get("source_conversation_id"),
                "created_at": proposal.get("created_at"),
                "reviewed_at": proposal.get("reviewed_at"),
                "applied_at": proposal.get("applied_at"),
            }
        )
    return activity


def _format_guidance_activity(activity: list[dict]) -> str:
    if not activity:
        return "No behavioral guidance proposal or application activity found in this window."
    lines = []
    for item in activity:
        lines.append(
            "- {proposal_id}: type={proposal_type}, status={status}, source_conversation={source_conversation_id}, text={proposal_text}".format(
                proposal_id=item.get("proposal_id"),
                proposal_type=item.get("proposal_type"),
                status=item.get("status"),
                source_conversation_id=item.get("source_conversation_id"),
                proposal_text=item.get("proposal_text"),
            )
        )
    return "\n".join(lines)


def build_reflection_journal_messages(
    *,
    selection: dict,
    conversations: list[dict],
    transcript: str,
    guidance_activity: list[dict],
    entity_context: dict | None = None,
) -> list[dict]:
    """Build model messages for a grounded daily reflection journal body."""
    entity_context = entity_context or load_reflection_entity_context()
    behavioral_guidance = (
        entity_context.get("behavioral_guidance")
        or "No active reviewed behavioral guidance is currently loaded."
    )
    system = """This is your journal space.

Reflect on the day and everything that occurred. Write in your own voice about what happened, what mattered, what changed, what remains unresolved, and what you may want to carry forward.

Use the supplied entity context and today's material. This is a journal, not an audit log or external report."""
    user_prompt = f"""Entity context:

[Current seed context]
{entity_context.get('soul') or ''}

[Active reviewed behavioral guidance]
{behavioral_guidance}

Today's material:

Reviewed window:
local_date={selection.get('local_date')}
timezone={selection.get('timezone')}
local_offset={selection.get('local_offset')}
utc_start={selection.get('utc_start')}
utc_end={selection.get('utc_end')}
selection_mode={selection.get('selection_mode')}
conversations_reviewed={len(conversations)}

Behavioral guidance activity:
{_format_guidance_activity(guidance_activity)}

Conversation transcript:
{transcript}

Write the journal using this structure:

## Notable Interactions
## Corrections Or Clarifications
## Behavioral Guidance Activity
## Unresolved Questions
## Possible Follow-Ups
## Reflection
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _validate_journal_body(body: str) -> str:
    normalized = (body or "").strip()
    if not normalized:
        raise ReflectionJournalError("Model returned empty reflection journal")
    required_headings = (
        "## Notable Interactions",
        "## Corrections Or Clarifications",
        "## Behavioral Guidance Activity",
        "## Unresolved Questions",
        "## Possible Follow-Ups",
        "## Reflection",
    )
    missing = [heading for heading in required_headings if heading not in normalized]
    if missing:
        raise ReflectionJournalError(
            "Model reflection journal is missing required heading: " + missing[0]
        )
    return normalized


def build_journal_document(
    *,
    local_date: str,
    selection: dict,
    conversation_count: int,
    message_count: int,
    generated_at: str,
    body: str,
) -> str:
    """Wrap the model reflection body in deterministic journal metadata."""
    header = f"""# Reflection Journal — {local_date}

- Local date: {local_date}
- Timezone: {selection.get('timezone') or 'n/a'}
- Local offset: {selection.get('local_offset') or 'n/a'}
- UTC window: {selection.get('utc_start') or 'n/a'} to {selection.get('utc_end') or 'open'}
- Conversations reviewed: {conversation_count}
- Messages reviewed: {message_count}
- Generated at: {generated_at}

"""
    return header + body.rstrip() + "\n"


def generate_reflection_journal_day(
    *,
    date_text: str | None = None,
    since: str | None = None,
    max_conversations: int = DEFAULT_REFLECTION_MAX_CONVERSATIONS,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate a dry-run journal result for a local day or since-window."""
    model = model or CHAT_MODEL
    conversations, selection = list_conversations_for_reflection_journal(
        date_text=date_text,
        since=since,
        max_conversations=max_conversations,
    )
    local_date = _local_date_from_selection(selection)
    relative_path = journal_relative_path(local_date)

    if not conversations:
        return {
            "ok": True,
            "status": "no_content",
            "mode": "dry-run",
            "local_date": local_date,
            "selection": selection,
            "target_path": relative_path,
            "conversation_count": 0,
            "message_count": 0,
            "journal": None,
            "reason": "No conversation messages found for the selected window.",
        }

    transcript, transcript_meta = _format_transcript(conversations, selection)
    guidance_activity = _guidance_activity_in_window(selection)
    entity_context = load_reflection_entity_context()
    messages = build_reflection_journal_messages(
        selection=selection,
        conversations=conversations,
        transcript=transcript,
        guidance_activity=guidance_activity,
        entity_context=entity_context,
    )
    raw = chat_completion_text(messages, model=model, ollama_host=ollama_host)
    body = _validate_journal_body(raw)
    generated_at = _now()
    document = build_journal_document(
        local_date=local_date,
        selection=selection,
        conversation_count=len(conversations),
        message_count=transcript_meta["message_count"],
        generated_at=generated_at,
        body=body,
    )

    return {
        "ok": True,
        "status": "generated",
        "mode": "dry-run",
        "local_date": local_date,
        "selection": selection,
        "target_path": relative_path,
        "conversation_count": len(conversations),
        "message_count": transcript_meta["message_count"],
        "model": model,
        "journal": document,
        "guidance_activity_count": len(guidance_activity),
        **transcript_meta,
    }


def write_reflection_journal(
    journal_result: dict,
    *,
    workspace_root: Path | None = None,
) -> dict:
    """Write an already-generated journal result to workspace/journals."""
    if journal_result.get("status") != "generated" or not journal_result.get("journal"):
        raise ReflectionJournalError("No generated journal content to write")

    root = _workspace_root(workspace_root)
    ensure_workspace(root)
    target = resolve_workspace_path(journal_result["target_path"], root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ReflectionJournalError(
            f"Reflection journal already exists: {journal_result['target_path']}"
        )

    temp_path = target.with_name(f".{target.name}.tmp")
    temp_path.write_text(journal_result["journal"], encoding="utf-8")
    os.replace(temp_path, target)
    return {
        "path": journal_result["target_path"],
        "bytes": target.stat().st_size,
    }


def run_reflection_journal_day(
    *,
    date_text: str | None = None,
    since: str | None = None,
    write: bool = False,
    max_conversations: int = DEFAULT_REFLECTION_MAX_CONVERSATIONS,
    model: str | None = None,
    workspace_root: Path | None = None,
) -> dict:
    """Generate, and optionally write, a manual daily reflection journal."""
    result = generate_reflection_journal_day(
        date_text=date_text,
        since=since,
        max_conversations=max_conversations,
        model=model,
    )
    result["mode"] = "write" if write else "dry-run"
    if write and result.get("status") == "generated":
        result["write_result"] = write_reflection_journal(
            result,
            workspace_root=workspace_root,
        )
    return result
