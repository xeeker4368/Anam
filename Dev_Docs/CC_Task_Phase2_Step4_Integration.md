# CC Task: Phase 2 Step 4 — Integration

## What this is

Wire the chunking pipeline and retrieval pipeline into the existing conversation engine. After this, the entity remembers across conversations: her responses are informed by retrieved memories, and her conversations become searchable memories for future sessions.

Two changes to existing files:
1. `conversation.py` — call live chunking after every assistant message, call final chunking on conversation close
2. `context.py` — call retrieval before building the system prompt, pass retrieved chunks into the system prompt

One change to existing CLI:
3. `cli_chat.py` — call final chunking when ending a conversation

## Prerequisites

- Phase 2 Steps 1-3 (ChromaDB, chunking, retrieval) deployed and verified
- At least one test conversation to verify retrieval works

## Files to modify

```
tir/
    engine/
        conversation.py    ← MODIFY
        context.py         ← MODIFY
    cli_chat.py            ← MODIFY
```

## Changes to `tir/engine/conversation.py`

### Add imports

At the top, after the existing imports, add:

```python
from tir.memory.chunking import maybe_chunk_live
```

### Add live chunking after assistant message save

In the `handle_turn` function, after the assistant message is saved (after the line `logger.info(f"Saved assistant message {assistant_msg['id']}")`), add:

```python
    # --- Live chunking check ---
    try:
        chunked = maybe_chunk_live(conversation_id, user_id)
        if chunked:
            logger.info(f"Live chunk created for conversation {conversation_id[:8]}")
    except Exception as e:
        logger.warning(f"Live chunking failed (non-fatal): {e}")
```

This goes right before the `return ConversationResponse(...)` at the end.

### Full `handle_turn` function after changes

For clarity, here is the complete function with the change in place:

```python
def handle_turn(
    user_id: str,
    text: str,
    conversation_id: str | None = None,
) -> ConversationResponse:
    """
    Process one conversation turn.

    1. Resolve or create conversation
    2. Persist user message
    3. Build system prompt (with retrieval)
    4. Get conversation history
    5. Call the model
    6. Persist assistant message
    7. Check for live chunking
    8. Return response
    """
    # --- Resolve user ---
    user = get_user(user_id)
    if not user:
        return ConversationResponse(
            content="Error: unknown user.",
            conversation_id=conversation_id or "",
            message_id="",
            error=True,
        )

    update_user_last_seen(user_id)

    # --- Resolve or create conversation ---
    if conversation_id is None:
        conversation_id = start_conversation(user_id)
        logger.info(f"Started new conversation {conversation_id} for {user['name']}")
    else:
        conv = get_conversation(conversation_id)
        if conv is None:
            conversation_id = start_conversation(user_id)
            logger.warning(f"Conversation not found, started new: {conversation_id}")

    # --- Persist user message ---
    user_msg = save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=text,
    )
    logger.info(f"Saved user message {user_msg['id']}")

    # --- Build system prompt (now with retrieval) ---
    system_prompt = build_system_prompt(
        user_name=user["name"],
        user_message=text,
        active_conversation_id=conversation_id,
    )

    # --- Get conversation history for model ---
    all_messages = get_conversation_messages(conversation_id)
    model_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in all_messages
    ]

    # --- Call the model ---
    try:
        response = chat_completion(
            system_prompt=system_prompt,
            messages=model_messages,
        )
        assistant_content = response["message"].get("content", "")

        if not assistant_content:
            assistant_content = "I received your message but couldn't generate a response."
            logger.warning("Empty response from model")

    except Exception as e:
        logger.error(f"Model call failed: {e}")
        assistant_content = f"Something went wrong when I tried to respond: {e}"

        error_msg = save_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
        )
        return ConversationResponse(
            content=assistant_content,
            conversation_id=conversation_id,
            message_id=error_msg["id"],
            error=True,
        )

    # --- Persist assistant message ---
    assistant_msg = save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
    )
    logger.info(f"Saved assistant message {assistant_msg['id']}")

    # --- Live chunking check ---
    try:
        chunked = maybe_chunk_live(conversation_id, user_id)
        if chunked:
            logger.info(f"Live chunk created for conversation {conversation_id[:8]}")
    except Exception as e:
        logger.warning(f"Live chunking failed (non-fatal): {e}")

    return ConversationResponse(
        content=assistant_content,
        conversation_id=conversation_id,
        message_id=assistant_msg["id"],
    )
```

## Changes to `tir/engine/context.py`

### Add imports

At the top, after the existing imports, add:

```python
from tir.memory.retrieval import retrieve

import logging
logger = logging.getLogger(__name__)
```

### Modify `build_system_prompt` signature and body

Replace the entire `build_system_prompt` function with:

```python
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

    # Section 2: Available tools (Phase 3)
    if tool_descriptions:
        sections.append(tool_descriptions)

    # Section 3: Retrieved memories
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

    # Section 4: Current situation
    if autonomous:
        sections.append(_autonomous_situation())
    else:
        sections.append(_current_situation(user_name))

    return "\n\n".join(sections)
```

### Update `_format_retrieved_memories` framing

Replace the header text in `_format_retrieved_memories`:

```python
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
```

## Changes to `tir/cli_chat.py`

### Add import

At the top, after the existing imports, add:

```python
from tir.memory.chunking import chunk_conversation_final
from tir.memory.db import get_conversation
```

Note: `get_conversation` may already be imported. Don't duplicate it.

### Add final chunking on conversation close

Every place where `end_conversation(conversation_id)` is called, add final chunking immediately after. There are two places:

**1. The `/quit` cleanup at the bottom of `main()`:**

Replace:
```python
    # --- Cleanup ---
    if conversation_id:
        end_conversation(conversation_id)
        print(f"Conversation {conversation_id[:8]}... ended.")
```

With:
```python
    # --- Cleanup ---
    if conversation_id:
        end_conversation(conversation_id)
        conv = get_conversation(conversation_id)
        user_id_for_chunk = conv["user_id"] if conv else user_id
        try:
            n = chunk_conversation_final(conversation_id, user_id_for_chunk)
            print(f"Conversation {conversation_id[:8]}... ended. {n} chunks saved.")
        except Exception as e:
            print(f"Conversation {conversation_id[:8]}... ended. Chunking failed: {e}")
```

**2. The `/new` command handler:**

Replace:
```python
        if user_input.lower() == "/new":
            if conversation_id:
                end_conversation(conversation_id)
                print(f"Ended conversation {conversation_id[:8]}.")
            conversation_id = None
            print("Starting new conversation.\n")
            continue
```

With:
```python
        if user_input.lower() == "/new":
            if conversation_id:
                end_conversation(conversation_id)
                conv = get_conversation(conversation_id)
                user_id_for_chunk = conv["user_id"] if conv else user_id
                try:
                    n = chunk_conversation_final(conversation_id, user_id_for_chunk)
                    print(f"Ended conversation {conversation_id[:8]}. {n} chunks saved.")
                except Exception as e:
                    print(f"Ended conversation {conversation_id[:8]}. Chunking failed: {e}")
            conversation_id = None
            print("Starting new conversation.\n")
            continue
```

## Verify — basic memory across conversations

This is the real test. Have two conversations and verify the entity remembers the first one in the second.

```bash
cd /path/to/Tir
python -m tir.cli_chat --new
```

First conversation:
```
Lyle: My favorite color is dark purple, almost like the night sky.
(wait for response)
Lyle: I also really enjoy building things with wood. Woodworking is my hobby.
(wait for response)
Lyle: /quit
```

Should print chunk count when ending.

Start a new conversation:
```bash
python -m tir.cli_chat --new
```

Second conversation:
```
Lyle: What do you remember about me?
(wait for response — she should mention purple and/or woodworking)
Lyle: /quit
```

If she mentions details from the first conversation, retrieval is working.

## Verify — debug mode shows retrieval

```bash
python -m tir.cli_chat --new --debug
```

Send a message. Debug output should show:
- ChromaDB query happening
- FTS5 query happening
- Number of results retrieved
- Chunks being formatted into the system prompt

## Verify — greetings don't trigger retrieval

```bash
python -m tir.cli_chat --new --debug
```

```
Lyle: Hello
```

Debug output should NOT show retrieval being triggered for a simple greeting.

## Verify — chunks are in both stores

After at least one conversation with `/quit`:

```bash
python3 -c "
from tir.memory.chroma import get_collection_count
from tir.memory.db import search_bm25
print(f'ChromaDB chunks: {get_collection_count()}')
results = search_bm25('favorite color')
print(f'BM25 results for \"favorite color\": {len(results)}')
for r in results:
    print(f'  {r[\"chunk_id\"][:20]}...')
"
```

Both stores should have the same chunks.

## What NOT to do

- Do NOT modify `db.py`, `chroma.py`, `chunking.py`, or `retrieval.py`
- Do NOT add retrieval to the model's messages array — it goes in the system prompt only
- Do NOT remove the `retrieved_chunks` parameter from `build_system_prompt` — it's used for testing and Phase 3
- Do NOT change the framing text from "These are your own experiences and memories" — this exact framing was validated in the Aion project (Principle 8)
- Do NOT make retrieval failure crash the conversation — it's wrapped in try/except
- Do NOT make chunking failure crash the conversation — it's wrapped in try/except
- Do NOT trigger retrieval on greetings — waste of embedding compute for "hi"

## What comes next

Phase 2 is complete after this step. She talks, she remembers. Next:
- Phase 3: Skill registry + tools + agent loop + web UI
- Or: iMessage adapter (she texts from your phone)
