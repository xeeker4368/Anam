# CC Task: Phase 2 Step 2 — Chunking Pipeline

## What this is

A new module `tir/memory/chunking.py` that turns conversation messages into retrievable memory chunks. It formats messages into timestamped transcript text, stores them in both ChromaDB (vector) and FTS5 (lexical), and handles both live mid-conversation chunking and final chunking at conversation close.

## Prerequisites

- Phase 2 Step 1 (ChromaDB module) deployed and verified
- Database layer with FTS5 table (`chunks_fts`) deployed and verified

## File to create

```
tir/
    memory/
        chunking.py    ← NEW
```

## Exact code for `tir/memory/chunking.py`

```python
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
```

## Verify — chunk text formatting

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.chunking import _format_chunk_text, _format_timestamp

# Test timestamp formatting
ts = '2026-04-22T19:30:00+00:00'
print(_format_timestamp(ts))

# Test chunk text
messages = [
    {'role': 'user', 'content': 'Hello there', 'timestamp': '2026-04-22T19:30:00+00:00'},
    {'role': 'assistant', 'content': 'Hi! How are you?', 'timestamp': '2026-04-22T19:30:05+00:00'},
    {'role': 'user', 'content': 'Good thanks', 'timestamp': '2026-04-22T19:31:00+00:00'},
    {'role': 'assistant', 'content': 'Glad to hear it.', 'timestamp': '2026-04-22T19:31:03+00:00'},
]
print()
print(_format_chunk_text(messages, 'Lyle'))
"
```

Expected: Timestamps in America/New_York time, user labeled as "Lyle", assistant labeled as "assistant".

## Verify — turn boundary assignment

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.chunking import _assign_messages_to_chunks

# 7 turns: should produce 2 groups (5 + 2)
messages = []
for i in range(7):
    messages.append({'role': 'user', 'content': f'msg {i}', 'timestamp': f'2026-04-22T{10+i}:00:00+00:00'})
    messages.append({'role': 'assistant', 'content': f'reply {i}', 'timestamp': f'2026-04-22T{10+i}:00:05+00:00'})

groups = _assign_messages_to_chunks(messages, chunk_size=5)
print(f'Groups: {len(groups)}')
print(f'Group 0 messages: {len(groups[0])}')  # 10 messages = 5 turns
print(f'Group 1 messages: {len(groups[1])}')  # 4 messages = 2 turns

# Multi-user-message turn: user, user, assistant = 1 turn
messages2 = [
    {'role': 'user', 'content': 'first', 'timestamp': '2026-04-22T10:00:00+00:00'},
    {'role': 'user', 'content': 'second', 'timestamp': '2026-04-22T10:00:01+00:00'},
    {'role': 'assistant', 'content': 'reply', 'timestamp': '2026-04-22T10:00:05+00:00'},
]
groups2 = _assign_messages_to_chunks(messages2, chunk_size=5)
print(f'Multi-msg turn groups: {len(groups2)}')  # 1 group, 1 turn
print(f'Messages in group: {len(groups2[0])}')   # 3 messages

# Orphan user message (no assistant reply)
messages3 = [
    {'role': 'user', 'content': 'hello', 'timestamp': '2026-04-22T10:00:00+00:00'},
    {'role': 'assistant', 'content': 'hi', 'timestamp': '2026-04-22T10:00:05+00:00'},
    {'role': 'user', 'content': 'orphan', 'timestamp': '2026-04-22T10:01:00+00:00'},
]
groups3 = _assign_messages_to_chunks(messages3, chunk_size=5)
print(f'Orphan case groups: {len(groups3)}')      # 1 group
print(f'Includes orphan: {len(groups3[0])}')      # 3 messages (all of them)
print('PASS')
"
```

Expected:
- 7 turns → 2 groups (5 turns + 2 turns)
- Multi-message turn counted correctly as 1 turn
- Orphan user message included in the tail chunk
- Prints PASS

## Verify — full round-trip with real DB

```bash
cd /path/to/Tir
python3 -c "
from tir.memory.db import (
    init_databases, create_user, start_conversation,
    save_message, end_conversation, get_turn_count,
)
from tir.memory.chunking import maybe_chunk_live, chunk_conversation_final
from tir.memory.chroma import get_collection_count, query_similar, reset_client
import tempfile, os, shutil
from unittest.mock import patch

# Use temp directories
tmpdir = tempfile.mkdtemp()
archive_path = os.path.join(tmpdir, 'archive.db')
working_path = os.path.join(tmpdir, 'working.db')
chroma_path = os.path.join(tmpdir, 'chromadb')

reset_client()

with patch('tir.config.DATA_DIR', tmpdir), \
     patch('tir.config.ARCHIVE_DB', archive_path), \
     patch('tir.config.WORKING_DB', working_path), \
     patch('tir.config.CHROMA_DIR', chroma_path):

    # Reload modules to pick up patched paths
    import importlib
    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.memory.chunking as chunk_mod
    importlib.reload(db_mod)
    importlib.reload(chroma_mod)
    importlib.reload(chunk_mod)

    db_mod.init_databases()

    user = db_mod.create_user('TestUser', role='admin')
    conv_id = db_mod.start_conversation(user['id'])

    # Send 6 turns (should trigger 1 live chunk at turn 5)
    chunked = False
    for i in range(6):
        db_mod.save_message(conv_id, user['id'], 'user', f'Question {i+1}')
        db_mod.save_message(conv_id, user['id'], 'assistant', f'Answer {i+1}')
        result = chunk_mod.maybe_chunk_live(conv_id, user['id'])
        if result:
            chunked = True
            print(f'Live chunk fired at turn {i+1}')

    assert chunked, 'Live chunk should have fired at turn 5'
    print(f'ChromaDB chunks after live: {chroma_mod.get_collection_count(chroma_path)}')

    # Close conversation — final chunking
    db_mod.end_conversation(conv_id)
    n = chunk_mod.chunk_conversation_final(conv_id, user['id'])
    print(f'Final chunking wrote {n} chunks')
    print(f'ChromaDB chunks after final: {chroma_mod.get_collection_count(chroma_path)}')

    # Query — should find our chunks
    results = chroma_mod.query_similar('Question 3', n_results=5, chroma_path=chroma_path)
    print(f'Query results: {len(results)}')
    for r in results:
        print(f'  {r[\"chunk_id\"]}: distance={r[\"distance\"]:.4f}')

shutil.rmtree(tmpdir)
reset_client()
print('PASS')
"
```

Expected:
- Live chunk fires at turn 5
- 1 chunk in ChromaDB after live chunking
- Final chunking writes 2 chunks (turns 1-5 + turns 6)
- 2 chunks in ChromaDB after final
- Query returns relevant results
- Prints PASS

## What NOT to do

- Do NOT modify `db.py`, `config.py`, `chroma.py`, or any engine files
- Do NOT add overlap between chunks — decision is no overlap
- Do NOT chunk by message count — chunk by turn count (assistant messages)
- Do NOT skip the FTS5 write — chunks must go to both stores
- Do NOT make live chunking failure block message saving — log warning, continue
- Do NOT delete chunks before re-chunking at close — upsert handles overwrites

## What comes next

After verifying chunking works:
- Step 3: Retrieval pipeline (searches both ChromaDB and FTS5)
