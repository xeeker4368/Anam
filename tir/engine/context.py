"""
Tír Context Construction

Assembles the entity's context for each turn.

Ordering:
1. Seed identity (soul.md)
2. Operational guidance (OPERATIONAL_GUIDANCE.md, if present)
3. Available tools
4. Current situation (current speaker + direct-address directive) — placed
   immediately before retrieved memories so the current-speaker signal is the
   nearest, strongest identity reference before the (possibly third-person-dense)
   memory block.
5. Retrieved memories
6. Current conversation (the exchange so far) — handled by message history

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


def _join_names(names: list[str]) -> str:
    """Join names for prose: 'A', 'A and B', 'A, B, and C'."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _current_situation(user_name: str, other_user_names: list[str] | None = None) -> str:
    """Build the current-situation / direct-address section.

    Active directive (not a passive description): asserts the current speaker by
    name, instructs second-person direct address, and warns that retrieved memory
    may reference other people who are NOT the current speaker. ``other_user_names``
    (if cheaply available from the caller) names those other people dynamically;
    no name is ever hardcoded — absent that list, the warning stays fully generic.
    """
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    formatted = now.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")

    others = [name for name in (other_user_names or []) if name and name != user_name]
    if others:
        others_clause = (
            f"Retrieved memory below may mention other people (such as "
            f"{_join_names(others)}); they are context, not the person you are "
            f"speaking with."
        )
    else:
        others_clause = (
            "Retrieved memory below may mention other people; they are context, "
            "not the person you are speaking with."
        )

    return (
        f"[Current Situation]\n\n"
        f"You are speaking with {user_name}. Address {user_name} directly, in the "
        f"second person. The current time is {formatted}. {others_clause}"
    )


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


def is_greeting(text: str) -> bool:
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
    other_user_names: list[str] | None = None,
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
        other_user_names=other_user_names,
    )
    return prompt


def build_system_prompt_with_debug(
    user_name: str,
    user_message: str | None = None,
    active_conversation_id: str | None = None,
    retrieved_chunks: list[dict] | None = None,
    tool_descriptions: str | None = None,
    autonomous: bool = False,
    other_user_names: list[str] | None = None,
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

    # Section 5: Current situation — placed BEFORE retrieved memories so the
    # current-speaker directive is the nearest preceding signal to the memory
    # block (which may be dense with third-person references to other people).
    if autonomous:
        situation = _autonomous_situation()
    else:
        situation = _current_situation(user_name, other_user_names)
    sections.append(situation)
    section_counts["situation_chars"] = len(situation)

    # Section 6: Retrieved memories
    if retrieved_chunks is None and user_message and not is_greeting(user_message):
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

    Framed as retrieved context. Each chunk is labeled by source_type.
    """
    header = "Retrieved context follows. Each item is labeled by source type."
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
