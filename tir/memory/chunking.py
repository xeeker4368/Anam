"""
Tír Chunking Pipeline

Turns conversation messages into retrievable memory chunks stored in
both ChromaDB (vector search) and FTS5 (lexical search).

Chunk boundaries are turn-based. A turn completes when an assistant
message is saved. 5 turns per chunk. No overlap.

Two entry points:
- maybe_chunk_live(): called after every assistant message. Fires a
  chunk if we just completed a multiple-of-5 turn.
- chunk_conversation_final(): called at conversation close. Re-chunks
  the whole conversation from scratch for correctness.

Both use the same chunk-assembly logic. Live chunking is the optimization
(makes chunks retrievable during conversation). Final chunking is the
correctness guarantee (catches anything live chunking missed).
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tir.config import CHUNK_TURN_SIZE, TIMEZONE
from tir.memory.db import (
    get_conversation_messages,
    get_turn_count,
    get_user,
    upsert_chunk_fts,
    mark_conversation_chunked,
)
from tir.memory.chroma import upsert_chunk, embed_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chunk text formatting
# ---------------------------------------------------------------------------

def _format_timestamp(iso_timestamp: str) -> str:
    """Convert UTC ISO timestamp to local display format.

    Example: '2026-04-22T15:30:00+00:00' → '[April 22, 2026 at 3:30 PM]'
    """
    tz = ZoneInfo(TIMEZONE)
    dt = datetime.fromisoformat(iso_timestamp).astimezone(tz)
    # %-d and %-I are POSIX-only (no zero-padding). macOS is POSIX.
    return dt.strftime("[%B %-d, %Y at %-I:%M %p]")


def _format_chunk_text(messages: list[dict], user_name: str) -> str:
    """Format a list of messages into chunk transcript text.

    Args:
        messages: List of message dicts with 'role', 'content', 'timestamp'.
        user_name: Resolved display name for the user side.

    Returns:
        Timestamped transcript string. Example:
            [April 22, 2026 at 3:30 PM] Lyle: Hello
            [April 22, 2026 at 3:30 PM] assistant: Hi there!
    """
    lines = []
    for msg in messages:
        ts = _format_timestamp(msg["timestamp"])
        speaker = user_name if msg["role"] == "user" else "assistant"
        lines.append(f"{ts} {speaker}: {msg['content']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Turn-based chunk boundary logic
# ---------------------------------------------------------------------------

def _assign_messages_to_chunks(
    messages: list[dict],
    chunk_size: int = CHUNK_TURN_SIZE,
) -> list[list[dict]]:
    """Split messages into chunk groups based on turn boundaries.

    A turn completes when an assistant message appears. Multiple
    consecutive user messages before an assistant message belong
    to the same turn.

    Args:
        messages: All messages in the conversation, ordered by timestamp.
        chunk_size: Turns per chunk (default 5).

    Returns:
        List of message groups. Each group is one chunk's worth of messages.
        The last group may be smaller than chunk_size turns (the tail).
        Includes any trailing user messages with no assistant reply.
    """
    if not messages:
        return []

    chunks = []
    current_chunk_messages = []
    turn_count_in_chunk = 0

    for msg in messages:
        current_chunk_messages.append(msg)

        if msg["role"] == "assistant":
            turn_count_in_chunk += 1

            if turn_count_in_chunk >= chunk_size:
                chunks.append(current_chunk_messages)
                current_chunk_messages = []
                turn_count_in_chunk = 0

    # Any remaining messages (incomplete chunk or orphan user messages)
    if current_chunk_messages:
        chunks.append(current_chunk_messages)

    return chunks


# ---------------------------------------------------------------------------
# Store a single chunk to both ChromaDB and FTS5
# ---------------------------------------------------------------------------

def _store_chunk(
    chunk_id: str,
    text: str,
    conversation_id: str,
    user_id: str,
    message_count: int,
    chunk_index: int,
    source_type: str = "conversation",
    source_trust: str = "firsthand",
):
    """Store a chunk in both ChromaDB and FTS5.

    ChromaDB write happens first. If FTS5 write fails, the chunk is
    still vector-searchable. Final chunking at close will retry and
    bring FTS5 back into sync.

    Args:
        chunk_id: Unique ID (e.g., "{conversation_id}_chunk_0").
        text: Formatted chunk transcript text.
        conversation_id: Source conversation UUID.
        user_id: UUID of the user in the conversation.
        message_count: Number of messages in this chunk.
        chunk_index: 0-indexed position within the conversation.
        source_type: Type of source (default "conversation").
        source_trust: Trust level (default "firsthand").
    """
    now = datetime.now(timezone.utc).isoformat()

    metadata = {
        "conversation_id": conversation_id,
        "chunk_index": chunk_index,
        "source_type": source_type,
        "source_trust": source_trust,
        "user_id": user_id,
        "message_count": message_count,
        "created_at": now,
    }

    # ChromaDB (vector) — primary store
    try:
        upsert_chunk(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
        )
    except Exception as e:
        logger.error(f"ChromaDB upsert failed for {chunk_id}: {e}")
        raise  # Can't proceed without vector storage

    # FTS5 (lexical) — secondary store
    try:
        upsert_chunk_fts(
            chunk_id=chunk_id,
            text=text,
            conversation_id=conversation_id,
            user_id=user_id,
            source_type=source_type,
            source_trust=source_trust,
            created_at=now,
        )
    except Exception as e:
        logger.warning(f"FTS5 upsert failed for {chunk_id}: {e} (will retry at close)")


# ---------------------------------------------------------------------------
# Live chunking (called after every assistant message)
# ---------------------------------------------------------------------------

def maybe_chunk_live(conversation_id: str, user_id: str) -> bool:
    """Check if a new chunk should be created and do it if so.

    Called after every assistant message is saved. Checks if the
    turn count is a nonzero multiple of CHUNK_TURN_SIZE. If so,
    creates a chunk for the just-completed group of turns.

    Args:
        conversation_id: The active conversation.
        user_id: UUID of the user in the conversation.

    Returns:
        True if a chunk was created, False otherwise.
    """
    turn_count = get_turn_count(conversation_id)

    if turn_count == 0 or turn_count % CHUNK_TURN_SIZE != 0:
        return False

    chunk_index = (turn_count // CHUNK_TURN_SIZE) - 1

    # Get all messages and assign to chunks
    messages = get_conversation_messages(conversation_id)
    chunk_groups = _assign_messages_to_chunks(messages)

    # The chunk we want is at chunk_index
    if chunk_index >= len(chunk_groups):
        logger.warning(
            f"Chunk index {chunk_index} out of range "
            f"({len(chunk_groups)} groups) for conversation {conversation_id[:8]}"
        )
        return False

    chunk_messages = chunk_groups[chunk_index]

    # Resolve user name for formatting
    user = get_user(user_id)
    user_name = user["name"] if user else "Unknown"

    chunk_text = _format_chunk_text(chunk_messages, user_name)
    chunk_id = f"{conversation_id}_chunk_{chunk_index}"

    _store_chunk(
        chunk_id=chunk_id,
        text=chunk_text,
        conversation_id=conversation_id,
        user_id=user_id,
        message_count=len(chunk_messages),
        chunk_index=chunk_index,
    )

    logger.info(
        f"Live chunk {chunk_index} created for conversation "
        f"{conversation_id[:8]} ({len(chunk_messages)} messages)"
    )
    return True


# ---------------------------------------------------------------------------
# Final chunking (called at conversation close)
# ---------------------------------------------------------------------------

def chunk_conversation_final(conversation_id: str, user_id: str) -> int:
    """Re-chunk an entire conversation from scratch.

    Called when a conversation closes. Regenerates all chunks using
    the chunking rules. Upsert semantics mean existing chunks get
    overwritten with identical content (no-op), and any missing
    chunks get filled in.

    This is the correctness guarantee. Live chunking is the optimization.

    Args:
        conversation_id: The conversation to chunk.
        user_id: UUID of the user in the conversation.

    Returns:
        Number of chunks created/updated.
    """
    messages = get_conversation_messages(conversation_id)

    if not messages:
        mark_conversation_chunked(conversation_id)
        return 0

    chunk_groups = _assign_messages_to_chunks(messages)

    # Resolve user name
    user = get_user(user_id)
    user_name = user["name"] if user else "Unknown"

    chunks_written = 0
    for i, chunk_messages in enumerate(chunk_groups):
        chunk_text = _format_chunk_text(chunk_messages, user_name)
        chunk_id = f"{conversation_id}_chunk_{i}"

        try:
            _store_chunk(
                chunk_id=chunk_id,
                text=chunk_text,
                conversation_id=conversation_id,
                user_id=user_id,
                message_count=len(chunk_messages),
                chunk_index=i,
            )
            chunks_written += 1
        except Exception as e:
            logger.error(f"Failed to write chunk {chunk_id}: {e}")

    mark_conversation_chunked(conversation_id)

    logger.info(
        f"Final chunking complete for conversation {conversation_id[:8]}: "
        f"{chunks_written} chunks from {len(messages)} messages"
    )
    return chunks_written
