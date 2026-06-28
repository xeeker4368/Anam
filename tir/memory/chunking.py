"""
Tír Chunking Pipeline

Turns conversation messages into retrievable memory chunks stored in
both ChromaDB (vector search) and FTS5 (lexical search).

Chunk boundaries are turn-based. A turn completes when an assistant
message is saved. 5 turns per chunk. No overlap.

Three entry points:
- maybe_chunk_live(): called after every assistant message. Fires a
  chunk if we just completed a multiple-of-5 turn.
- checkpoint_conversation(): called after a completed assistant turn to
  upsert the latest active-conversation tail chunk without closing it.
- chunk_conversation_final(): called at conversation close. Re-chunks
  the whole conversation from scratch for correctness.

All use the same chunk-assembly logic. Live chunking/checkpointing make
chunks retrievable during conversation. Final chunking is the correctness
guarantee (catches anything live chunking missed).
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tir.config import CHUNK_TURN_SIZE, EMBED_MAX_CHARS, TIMEZONE
from tir.memory.db import (
    get_conversation,
    get_conversation_messages,
    get_turn_count,
    get_unchunked_ended_conversations,
    get_user,
    end_conversation,
    delete_fts_chunk_index,
    upsert_chunk_fts,
    mark_conversation_chunked,
)
from tir.memory.chroma import (
    delete_chunk_records_by_index,
    upsert_chunk,
    embed_text,
)

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


def _format_message_line(msg: dict, user_name: str) -> str:
    """Format one message into a single transcript line."""
    ts = _format_timestamp(msg["timestamp"])
    speaker = user_name if msg["role"] == "user" else "assistant"
    return f"{ts} {speaker}: {msg['content']}"


def _hard_split_text(text: str, budget: int) -> list[str]:
    """Split a single over-budget line into <=budget-char pieces.

    Slices in str/codepoint space — Python str slicing NEVER splits a multi-byte
    UTF-8 character. Do NOT change this to bytes/byte-slicing: that would corrupt
    multibyte characters (emoji, CJK) at the cut points.
    """
    return [text[i:i + budget] for i in range(0, len(text), budget)]


def _split_chunk_for_embedding(
    messages: list[dict],
    user_name: str,
    budget: int = EMBED_MAX_CHARS,
) -> list[tuple[str, int]]:
    """Split a turn-group's formatted text into embed-sized sub-units.

    Turn-based grouping is unchanged; this only sub-divides a *formed* group
    whose text exceeds ``budget`` chars (nomic's context limit; Ollama 400s over
    it and truncate=true does not help). Prefers whole-message boundaries:
    contiguous runs of whole messages that fit the budget. Only when a single
    message's own line exceeds the budget is that line hard-split (in str space).

    Returns a list of ``(text, message_count)`` sub-units in order. Concatenating
    the sub-unit texts reproduces the group's content with no loss. A group that
    already fits returns exactly one sub-unit (the whole group).
    """
    sub_units: list[tuple[str, int]] = []
    run_lines: list[str] = []
    run_count = 0

    def flush_run() -> None:
        nonlocal run_lines, run_count
        if run_lines:
            sub_units.append(("\n".join(run_lines), run_count))
            run_lines = []
            run_count = 0

    for msg in messages:
        line = _format_message_line(msg, user_name)
        if len(line) > budget:
            # Single message exceeds the budget on its own: close the current
            # whole-message run, then hard-split THIS line (str-space) into pieces.
            flush_run()
            for k, piece in enumerate(_hard_split_text(line, budget)):
                # Attribute the message to its first piece so sub-unit counts sum
                # back to the group's message count.
                sub_units.append((piece, 1 if k == 0 else 0))
            continue
        candidate = "\n".join(run_lines + [line]) if run_lines else line
        if len(candidate) > budget:
            flush_run()
            run_lines = [line]
            run_count = 1
        else:
            run_lines.append(line)
            run_count += 1

    flush_run()
    return sub_units


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

    # ChromaDB (vector) — primary store.
    # Defect 2: if the vector write fails (e.g. an embed 400), do NOT skip the
    # FTS write. Record the error, still attempt FTS below so the chunk degrades
    # to lexically-searchable rather than being dropped from BOTH stores, then
    # re-raise so the caller leaves the conversation chunked=0 (recoverable).
    vector_error: Exception | None = None
    try:
        upsert_chunk(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
        )
    except Exception as e:
        vector_error = e
        logger.error(f"ChromaDB upsert failed for {chunk_id}: {e}")

    # FTS5 (lexical) — secondary store. Attempted regardless of the vector outcome.
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

    if vector_error is not None:
        raise vector_error  # vector storage failed → caller leaves it recoverable


def _store_chunk_group(
    conversation_id: str,
    user_id: str,
    chunk_index: int,
    chunk_messages: list[dict],
    user_name: str,
) -> tuple[int, int]:
    """Store one turn-group, splitting it into embed-sized sub-units if needed.

    Returns ``(intended, written)`` — the number of sub-units this group should
    produce and the number that fully stored (vector + lexical). A group that
    fits the budget is one sub-unit with the unchanged bare ID
    ``{conv}_chunk_{i}`` (no migration of the existing corpus). An over-budget
    group becomes ``{conv}_chunk_{i}_{j}`` sub-units.

    Convergence/idempotency: every write first removes ALL prior records for this
    (conversation_id, chunk_index) from both stores, so a changed split shape as
    a tail grows leaves no orphan, and re-running on frozen content reproduces the
    same stored set.
    """
    sub_units = _split_chunk_for_embedding(chunk_messages, user_name)
    base = f"{conversation_id}_chunk_{chunk_index}"

    # Remove any prior units for this index before writing the current shape.
    # (See delete_chunk_records_by_index / delete_fts_chunk_index for mechanism.)
    delete_chunk_records_by_index(conversation_id, chunk_index)
    delete_fts_chunk_index(conversation_id, chunk_index)

    intended = len(sub_units)
    written = 0
    single = intended == 1
    for j, (text, message_count) in enumerate(sub_units):
        chunk_id = base if single else f"{base}_{j}"
        try:
            _store_chunk(
                chunk_id=chunk_id,
                text=text,
                conversation_id=conversation_id,
                user_id=user_id,
                message_count=message_count,
                chunk_index=chunk_index,
            )
            written += 1
        except Exception as e:
            logger.error(f"Failed to write chunk {chunk_id}: {e}", exc_info=True)

    return intended, written


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

    intended, written = _store_chunk_group(
        conversation_id, user_id, chunk_index, chunk_messages, user_name
    )

    logger.info(
        "Live chunk %s created for conversation %s (%s messages, %s sub-chunks)",
        chunk_index,
        conversation_id[:8],
        len(chunk_messages),
        intended,
    )
    return written > 0


# ---------------------------------------------------------------------------
# Active conversation checkpointing (called after completed assistant turns)
# ---------------------------------------------------------------------------

def checkpoint_conversation(conversation_id: str, user_id: str) -> int:
    """Upsert the latest chunk group for an active conversation.

    This makes completed turns retrievable before final close without ending
    the conversation or marking it fully chunked. It intentionally writes only
    the latest/tail chunk group in v1. Existing deterministic chunk IDs make
    repeated checkpoints overwrite the same FTS/Chroma records instead of
    creating duplicates.

    Args:
        conversation_id: The active conversation.
        user_id: UUID of the user in the conversation.

    Returns:
        Number of chunks written. For v1 this is 0 or 1.
    """
    messages = get_conversation_messages(conversation_id)
    chunk_groups = _assign_messages_to_chunks(messages)

    if not chunk_groups:
        return 0

    chunk_index = len(chunk_groups) - 1
    chunk_messages = chunk_groups[chunk_index]

    user = get_user(user_id)
    user_name = user["name"] if user else "Unknown"

    intended, written = _store_chunk_group(
        conversation_id, user_id, chunk_index, chunk_messages, user_name
    )

    logger.info(
        "Checkpointed conversation %s chunk %s (%s messages, %s sub-chunks)",
        conversation_id[:8],
        chunk_index,
        len(chunk_messages),
        intended,
    )
    return 1 if written > 0 else 0


# ---------------------------------------------------------------------------
# Final chunking (called at conversation close)
# ---------------------------------------------------------------------------

def close_conversation(conversation_id: str, user_id: str) -> int:
    """Close a conversation: mark it ended, then run final chunking.

    The single shared close primitive — used by the idle-close janitor (and any
    other caller) so close behaviour can't diverge. Idempotent: a missing or
    already-ended conversation is a no-op returning 0. `ended_at` is set first, so
    a conversation still counts as closed even if final chunking fails.

    Returns the number of chunks created/updated by final chunking.
    """
    conv = get_conversation(conversation_id)
    if conv is None or conv.get("ended_at"):
        return 0
    end_conversation(conversation_id)
    try:
        return chunk_conversation_final(conversation_id, user_id)
    except Exception as e:
        logger.warning(
            "Final chunking failed during close of %s: %s", conversation_id, e
        )
        return 0


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
    chunk_groups = _assign_messages_to_chunks(messages)

    if len(chunk_groups) == 0:
        mark_conversation_chunked(conversation_id)
        return 0

    # Resolve user name
    user = get_user(user_id)
    user_name = user["name"] if user else "Unknown"

    # Completion is measured in stored SUB-units, not turn-groups: an over-budget
    # group produces >1 sub-unit, so comparing against len(chunk_groups) would
    # never mark a split conversation chunked.
    total_intended = 0
    chunks_written = 0
    for i, chunk_messages in enumerate(chunk_groups):
        intended, written = _store_chunk_group(
            conversation_id, user_id, i, chunk_messages, user_name
        )
        total_intended += intended
        chunks_written += written

    if chunks_written == total_intended and total_intended > 0:
        mark_conversation_chunked(conversation_id)
        logger.info(
            f"Final chunking complete for conversation {conversation_id[:8]}: "
            f"{chunks_written}/{total_intended} sub-chunks from {len(messages)} messages"
        )
    else:
        logger.error(
            f"Final chunking incomplete for conversation {conversation_id[:8]}: "
            f"{chunks_written}/{total_intended} sub-chunks written; "
            "leaving conversation unchunked for recovery"
        )

    return chunks_written


def recover_unchunked_ended_conversations(limit: int | None = None) -> dict:
    """Retry final chunking for ended conversations that remain unchunked.

    This helper is explicit and intentionally not wired into startup.
    """
    conversations = get_unchunked_ended_conversations()
    if limit is not None:
        conversations = conversations[:limit]

    summary = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "chunks_written": 0,
        "failures": [],
    }

    for conv in conversations:
        conversation_id = conv["id"]
        summary["attempted"] += 1
        try:
            chunks_written = chunk_conversation_final(conversation_id, conv["user_id"])
            summary["chunks_written"] += chunks_written
            updated = get_conversation(conversation_id)
            if updated and updated.get("chunked") == 1:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1
                summary["failures"].append({
                    "conversation_id": conversation_id,
                    "error": "conversation remained unchunked after retry",
                })
        except Exception as e:
            logger.error(
                f"Recovery chunking failed for conversation {conversation_id[:8]}: {e}",
                exc_info=True,
            )
            summary["failed"] += 1
            summary["failures"].append({
                "conversation_id": conversation_id,
                "error": str(e),
            })

    logger.info(
        "Unchunked conversation recovery attempted=%s succeeded=%s failed=%s chunks_written=%s",
        summary["attempted"],
        summary["succeeded"],
        summary["failed"],
        summary["chunks_written"],
    )
    return summary
