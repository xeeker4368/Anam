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
from tir.artifacts.source_roles import display_origin, display_source_role
from tir.memory.retrieval import retrieve

import logging
logger = logging.getLogger(__name__)

BEHAVIORAL_GUIDANCE_CHAR_BUDGET = 3000
BEHAVIORAL_GUIDANCE_LABEL = """[Reviewed Behavioral Guidance]

Active behavioral guidance proposed by the AI and approved/applied by an admin. Use these entries to inform future behavior. They sit below soul.md and operational guidance in precedence."""


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


def _extract_active_guidance_items(content: str) -> list[str]:
    """Extract only '- Guidance: ...' lines from the Active Guidance section."""
    marker = "## Active Guidance"
    marker_index = content.find(marker)
    if marker_index < 0:
        return []

    active = content[marker_index + len(marker):]
    next_section = active.find("\n## ")
    if next_section >= 0:
        active = active[:next_section]

    items = []
    for line in active.splitlines():
        stripped = line.strip()
        if stripped.startswith("- Guidance:"):
            guidance = stripped.removeprefix("- Guidance:").strip()
            if guidance:
                items.append(guidance)
    return items


def _format_behavioral_guidance(
    items: list[str],
    *,
    max_chars: int | None = None,
) -> tuple[str | None, dict]:
    """Format active guidance items with a hard character budget."""
    if max_chars is None:
        max_chars = BEHAVIORAL_GUIDANCE_CHAR_BUDGET
    metadata = {
        "behavioral_guidance_items_found": len(items),
        "behavioral_guidance_items_included": 0,
        "behavioral_guidance_items_skipped": 0,
        "behavioral_guidance_budget_chars": max_chars,
        "behavioral_guidance_chars": 0,
    }
    if not items:
        return None, metadata

    included = []
    used = len(BEHAVIORAL_GUIDANCE_LABEL)
    for item in items:
        line = f"- {item}"
        additional = len("\n\n" if not included else "\n") + len(line)
        if used + additional > max_chars:
            metadata["behavioral_guidance_items_skipped"] += 1
            continue
        included.append(line)
        used += additional

    if not included:
        metadata["behavioral_guidance_items_skipped"] = len(items)
        return None, metadata

    section = BEHAVIORAL_GUIDANCE_LABEL + "\n\n" + "\n".join(included)
    metadata["behavioral_guidance_items_included"] = len(included)
    metadata["behavioral_guidance_items_skipped"] = len(items) - len(included)
    metadata["behavioral_guidance_chars"] = len(section)
    return section, metadata


def _load_behavioral_guidance() -> tuple[str | None, dict]:
    """Load active reviewed behavioral guidance for runtime context."""
    guidance_path = PROJECT_ROOT / "BEHAVIORAL_GUIDANCE.md"
    empty_metadata = {
        "behavioral_guidance_items_found": 0,
        "behavioral_guidance_items_included": 0,
        "behavioral_guidance_items_skipped": 0,
        "behavioral_guidance_budget_chars": BEHAVIORAL_GUIDANCE_CHAR_BUDGET,
        "behavioral_guidance_chars": 0,
    }
    if not guidance_path.exists():
        return None, empty_metadata

    content = guidance_path.read_text(encoding="utf-8")
    items = _extract_active_guidance_items(content)
    return _format_behavioral_guidance(items)


def load_reflection_entity_context() -> dict:
    """Load entity context for manual reflection journaling.

    Reflection uses the same seed context and active reviewed behavioral
    guidance extraction as runtime prompt construction, without loading
    proposal metadata or behavioral guidance governance prose.
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
        "behavioral_guidance_budget_chars": BEHAVIORAL_GUIDANCE_CHAR_BUDGET,
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

    # Section 3: Reviewed behavioral guidance
    behavioral_guidance, behavioral_guidance_debug = _load_behavioral_guidance()
    section_counts.update(behavioral_guidance_debug)
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
        source_type = chunk.get("source_type") or chunk.get("metadata", {}).get("source_type", "conversation")
        created_at = chunk.get("created_at") or chunk.get("metadata", {}).get("created_at", "unknown date")
        text = chunk.get("text", "")

        if source_type == "conversation":
            formatted_chunks.append(f"[Conversation — {created_at}]\n{text}")
        elif source_type == "journal":
            journal_date = chunk.get("journal_date") or chunk.get("metadata", {}).get("journal_date")
            formatted_chunks.append(f"[Your journal entry from {journal_date or created_at}]\n{text}")
        elif source_type == "research":
            formatted_chunks.append(f"[Research you wrote on {created_at}]\n{text}")
        elif source_type == "article":
            title = chunk.get("title", "untitled")
            formatted_chunks.append(f"[External source you read: {title}, ingested {created_at}]\n{text}")
        elif source_type == "artifact_document":
            metadata = chunk.get("metadata", {})
            title = chunk.get("title") or metadata.get("title", "untitled artifact")
            filename = metadata.get("filename", "unknown file")
            source_role = display_source_role(
                metadata.get("source_role"),
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
