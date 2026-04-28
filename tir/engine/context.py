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

from tir.config import TIMEZONE, PROJECT_ROOT
from tir.memory.retrieval import retrieve

import logging
logger = logging.getLogger(__name__)


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


def _current_situation(user_name: str) -> str:
    """Build the current situation section."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    return f"You are currently in conversation with {user_name}.\nThe time is {formatted}."


def _autonomous_situation() -> str:
    """Build the current situation for autonomous sessions."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    return f"You are in an autonomous work session.\nThe time is {formatted}."


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
    sections = []

    # Section 1: Seed identity
    sections.append(_load_soul())

    # Section 2: Operational guidance
    operational_guidance = _load_operational_guidance()
    if operational_guidance:
        sections.append(operational_guidance)

    # Section 3: Available tools
    if tool_descriptions:
        sections.append(tool_descriptions)

    # Section 4: Retrieved memories
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
        sections.append(_format_retrieved_memories(retrieved_chunks))

    # Section 5: Current situation
    if autonomous:
        sections.append(_autonomous_situation())
    else:
        sections.append(_current_situation(user_name))

    return "\n\n".join(sections)


def _format_retrieved_memories(chunks: list[dict]) -> str:
    """
    Format retrieved chunks for the system prompt.

    Framed as the entity's own experiences. Each chunk formatted
    by source_type. Per Principle 8: framing is behavior.
    """
    header = "These are your own experiences and memories."
    formatted_chunks = []

    for chunk in chunks:
        source_type = chunk.get("source_type") or chunk.get("metadata", {}).get("source_type", "conversation")
        created_at = chunk.get("created_at") or chunk.get("metadata", {}).get("created_at", "unknown date")
        text = chunk.get("text", "")

        if source_type == "conversation":
            formatted_chunks.append(f"[Conversation — {created_at}]\n{text}")
        elif source_type == "journal":
            formatted_chunks.append(f"[Your journal entry from {created_at}]\n{text}")
        elif source_type == "research":
            formatted_chunks.append(f"[Research you wrote on {created_at}]\n{text}")
        elif source_type == "article":
            title = chunk.get("title", "untitled")
            formatted_chunks.append(f"[External source you read: {title}, ingested {created_at}]\n{text}")
        else:
            formatted_chunks.append(f"[{source_type} — {created_at}]\n{text}")

    return header + "\n\n" + "\n\n".join(formatted_chunks)
