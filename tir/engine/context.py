"""
Tír Context Construction

Assembles the entity's context for each turn.

Ordering:
1. Seed identity (soul.md)
2. Operational guidance (OPERATIONAL_GUIDANCE.md, if present)
3. Available tools
4. Retrieved memories
5. Current situation (who and when)
5. Current conversation (the exchange so far) — handled by message history

Everything except current conversation goes into the system prompt.
Current conversation goes into the messages array.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from tir.config import (
    TIMEZONE,
    PROJECT_ROOT,
)
from tir.artifacts.source_roles import display_origin, display_source_role
from tir.memory.retrieval import retrieve

import logging
logger = logging.getLogger(__name__)

BEHAVIORAL_GUIDANCE_DORMANT_STATUS = "dormant_before_go_live"


def _load_soul() -> str:
    """Load the seed identity from soul.md."""
    soul_path = PROJECT_ROOT / "soul.md"
    if not soul_path.exists():
        raise FileNotFoundError(f"soul.md not found at {soul_path}")
    return soul_path.read_text(encoding="utf-8").strip()


def _load_operational_guidance() -> str | None:
    """Load optional runtime guidance without treating it as memory."""
    guidance_path = PROJECT_ROOT / "OPERATIONAL_GUIDANCE.md"
    if not guidance_path.exists():
        return None

    content = guidance_path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return f"[Operational Guidance]\n\n{content}"


def _load_behavioral_guidance() -> tuple[str | None, dict]:
    """Return dormant behavioral guidance metadata without loading runtime text."""
    return None, {
        "behavioral_guidance_runtime_enabled": False,
        "behavioral_guidance_status": BEHAVIORAL_GUIDANCE_DORMANT_STATUS,
        "behavioral_guidance_items_found": 0,
        "behavioral_guidance_items_included": 0,
        "behavioral_guidance_items_skipped": 0,
        "behavioral_guidance_budget_chars": 0,
        "behavioral_guidance_chars": 0,
    }


def load_reflection_entity_context() -> dict:
    """Load entity context for manual reflection journaling.

    Behavioral guidance runtime loading is dormant before go-live, so
    reflection receives seed context without active behavioral guidance.
    """
    behavioral_guidance, behavioral_guidance_debug = _load_behavioral_guidance()
    return {
        "soul": _load_soul(),
        "behavioral_guidance": behavioral_guidance,
        "behavioral_guidance_debug": behavioral_guidance_debug,
    }


def _current_situation(user_name: str) -> str:
    """Build the current situation section."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    return f"[Current Situation]\n\nConversation with: {user_name}\nTime: {formatted}"


def _autonomous_situation() -> str:
    """Build the current situation for autonomous sessions."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    return f"[Current Situation]\n\nMode: autonomous work session\nTime: {formatted}"


# Simple patterns that don't need retrieval
_GREETING_PATTERNS = {
    "hi", "hello", "hey", "yo", "sup", "hiya", "heya",
    "good morning", "good afternoon", "good evening",
    "morning", "evening", "afternoon",
    "what's up", "whats up", "howdy",
}


def _is_greeting(text: str) -> bool:
    """Check if a message is a simple greeting that doesn't need retrieval."""
    cleaned = text.strip().lower().rstrip("!?.,'\"")
    return cleaned in _GREETING_PATTERNS


def build_system_prompt(
    user_name: str,
    user_message: str | None = None,
    active_conversation_id: str | None = None,
    retrieved_chunks: list[dict] | None = None,
    tool_descriptions: str | None = None,
    autonomous: bool = False,
) -> str:
    """
    Assemble the full system prompt.

    If user_message is provided and is not a greeting, automatic
    retrieval runs and retrieved chunks are included. If retrieved_chunks
    is passed directly (e.g., from a test), retrieval is skipped.

    Args:
        user_name: Display name of the current user.
        user_message: The user's message text (triggers retrieval).
        active_conversation_id: Current conversation ID (excluded from retrieval).
        retrieved_chunks: Pre-retrieved chunks (skips auto-retrieval).
        tool_descriptions: Formatted tool list (Phase 3).
        autonomous: If True, use autonomous situation framing.

    Returns:
        The complete system prompt string.
    """
    prompt, _debug = build_system_prompt_with_debug(
        user_name=user_name,
        user_message=user_message,
        active_conversation_id=active_conversation_id,
        retrieved_chunks=retrieved_chunks,
        tool_descriptions=tool_descriptions,
        autonomous=autonomous,
    )
    return prompt


def build_system_prompt_with_debug(
    user_name: str,
    user_message: str | None = None,
    active_conversation_id: str | None = None,
    retrieved_chunks: list[dict] | None = None,
    tool_descriptions: str | None = None,
    autonomous: bool = False,
) -> tuple[str, dict]:
    """
    Assemble the full system prompt and return best-effort section counts.

    This preserves build_system_prompt() output exactly. Counts are character
    counts, not token counts, and include section text while separator/wrapper
    overhead is reported in other_chars.
    """
    sections = []
    section_counts = {
        "soul_chars": 0,
        "operational_guidance_chars": 0,
        "behavioral_guidance_chars": 0,
        "behavioral_guidance_items_found": 0,
        "behavioral_guidance_items_included": 0,
        "behavioral_guidance_items_skipped": 0,
        "behavioral_guidance_budget_chars": 0,
        "tool_descriptions_chars": 0,
        "retrieved_context_chars": 0,
        "situation_chars": 0,
    }

    # Section 1: Seed identity
    soul = _load_soul()
    sections.append(soul)
    section_counts["soul_chars"] = len(soul)

    # Section 2: Operational guidance
    operational_guidance = _load_operational_guidance()
    if operational_guidance:
        sections.append(operational_guidance)
        section_counts["operational_guidance_chars"] = len(operational_guidance)

    # Section 3: Behavioral guidance is dormant before go-live.
    behavioral_guidance, behavioral_guidance_debug = _load_behavioral_guidance()
    section_counts.update(
        {
            key: value
            for key, value in behavioral_guidance_debug.items()
            if type(value) in (int, float)
        }
    )
    if behavioral_guidance:
        sections.append(behavioral_guidance)

    # Section 4: Available tools
    if tool_descriptions:
        sections.append(tool_descriptions)
        section_counts["tool_descriptions_chars"] = len(tool_descriptions)

    # Section 5: Retrieved memories
    if retrieved_chunks is None and user_message and not _is_greeting(user_message):
        # Automatic retrieval
        try:
            retrieved_chunks = retrieve(
                query=user_message,
                active_conversation_id=active_conversation_id,
            )
        except Exception as e:
            logger.warning(f"Retrieval failed (non-fatal): {e}")
            retrieved_chunks = []

    if retrieved_chunks:
        retrieved_context = _format_retrieved_memories(retrieved_chunks)
        sections.append(retrieved_context)
        section_counts["retrieved_context_chars"] = len(retrieved_context)

    # Section 6: Current situation
    if autonomous:
        situation = _autonomous_situation()
    else:
        situation = _current_situation(user_name)
    sections.append(situation)
    section_counts["situation_chars"] = len(situation)

    prompt = "\n\n".join(sections)
    known_chars = sum(section_counts.values())
    debug = {
        "system_prompt_chars": len(prompt),
        **section_counts,
        **{
            key: value
            for key, value in behavioral_guidance_debug.items()
            if type(value) not in (int, float)
        },
        "other_chars": max(0, len(prompt) - known_chars),
        "best_effort": True,
    }
    return prompt, debug


def _format_retrieved_memories(chunks: list[dict]) -> str:
    """
    Format retrieved chunks for the system prompt.

    Framed as the entity's own experiences. Each chunk formatted
    by source_type. Per Principle 8: framing is behavior.
    """
    header = "These are your own experiences and memories."
    formatted_chunks = []

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        source_type = chunk.get("source_type") or metadata.get("source_type", "conversation")
        source_role = chunk.get("source_role") or metadata.get("source_role")
        created_at = chunk.get("created_at") or metadata.get("created_at", "unknown date")
        text = chunk.get("text", "")

        if source_type == "conversation":
            formatted_chunks.append(f"[Conversation — {created_at}]\n{text}")
        elif source_type == "journal":
            journal_date = chunk.get("journal_date") or metadata.get("journal_date")
            formatted_chunks.append(
                f"[Your reflection journal entry from {journal_date or created_at} — personal reflection]\n{text}"
            )
        elif source_type == "research" or source_role == "research_reference":
            research_date = chunk.get("research_date") or metadata.get("research_date") or created_at
            research_title = (
                chunk.get("research_title")
                or metadata.get("research_title")
                or chunk.get("title")
                or metadata.get("title")
            )
            if research_title:
                formatted_chunks.append(
                    f"[Research you wrote on {research_date}: {research_title} — working research notes]\n{text}"
                )
            else:
                formatted_chunks.append(
                    f"[Research you wrote on {research_date} — working research notes]\n{text}"
                )
        elif source_type == "article":
            title = chunk.get("title", "untitled")
            formatted_chunks.append(f"[External source you read: {title}, ingested {created_at}]\n{text}")
        elif source_type == "artifact_document":
            title = chunk.get("title") or metadata.get("title", "untitled artifact")
            filename = metadata.get("filename", "unknown file")
            if source_role == "project_reference":
                formatted_chunks.append(
                    f"[Project reference document: {filename} — source material, not runtime guidance]\n{text}"
                )
                continue
            source_role = display_source_role(
                source_role,
                authority=metadata.get("authority"),
            )
            origin = display_origin(metadata.get("origin"))
            formatted_chunks.append(
                f"[Artifact source: {title}, role: {source_role}, origin: {origin}, "
                f"file: {filename}]\n{text}"
            )
        else:
            formatted_chunks.append(f"[{source_type} — {created_at}]\n{text}")

    return header + "\n\n" + "\n\n".join(formatted_chunks)
