# Project Tír — Conversation Chunking Strategy

*Design doc v1.1, April 18, 2026. Revised from v1 with: orphan user messages rule (A), concrete timezone commitment, revised turn detection (count assistant messages), clarification of message_count vs turn count, and cross-reference to the close mechanism defined in the Autonomous Window design.*

*Defines how conversation messages become retrievable chunks in ChromaDB. Scope limited to conversation chunks — autonomous-session output (journals, research) and ingested documents are separate concerns.*

---

## Purpose

The memory layer stores messages verbatim in the archive (Principle 5). Those messages become *retrievable* memories only once they're chunked and embedded into ChromaDB. Chunking is the transformation from "a conversation happened" to "here are the units the entity can later find and reason over."

This document decides:

- When chunks get created during and after a conversation.
- What the boundaries of a chunk are.
- What text a chunk contains.
- Whether chunks overlap.
- What metadata each chunk carries.
- How "unchunked messages" is determined at close time.

Non-goals for this doc:

- How chunks are retrieved (separate spec).
- How autonomous-session content is chunked (different problem, different shape).
- How documents are chunked (URL/PDF/article ingestion — different problem).
- When and how the close operation fires (Autonomous Window Design v1.1 — conversation-lifecycle concern, not chunking's).

---

## Summary of decisions

1. **Boundary unit: turn.** A turn completes when an assistant message is saved. Turn count = count of assistant messages in the conversation. Any user messages (including consecutive ones) that preceded the assistant message belong to that turn.
2. **Chunk size:** 5 turns per regular chunk.
3. **Overlap:** none. Every turn belongs to exactly one chunk.
4. **Live chunking:** a chunk fires when the 5th, 10th, 15th... completed turn lands.
5. **Final chunk:** whatever messages remain since the last chunk (including any trailing orphan user messages with no assistant reply) become one final chunk on conversation close. Any size from 1 message up, or zero if the last regular chunk fully covered the conversation.
6. **Text format:** timestamped transcript with the user's resolved name embedded; entity's side rendered as `assistant`. Timestamps rendered in America/New_York timezone, no zone suffix.
7. **Metadata:** per the v1.2 schema, populated at chunk-creation time.
8. **Close-time determination of unchunked messages:** re-chunk the whole conversation from scratch on close. Deterministic chunk IDs + upsert semantics make this idempotent.

---

## Why these decisions

### Boundary: turn, not message count

The chunk is what the entity reads as her own experience (Principle 8 — framing is behavior). A chunk that ends with a user's question but no assistant response reads as a memory of an incomplete event. Turn-based boundaries make it structurally impossible for a chunk to end mid-exchange under normal conditions.

The precise definition: **a turn completes when an assistant message is saved. Any user messages that preceded it without an intervening assistant message belong to that same turn.** This handles the real-world case where a user sends multiple quick messages before the assistant responds:

- `user, user, assistant` → 1 turn.
- `user, assistant, user, assistant` → 2 turns.
- `user, user, user, assistant, user, assistant` → 2 turns.

Turn count is computed by `SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'assistant'`. Simple and always accurate.

This is a deliberate change from Aion, which chunked every 10 messages. Aion's boundaries usually fell between turns because conversations mostly alternate, but not always. Tír makes it always by design.

### Size: 5 turns

5 turns produces chunks that are:

- Large enough to contain a coherent conversational episode.
- Small enough that a retrieved chunk doesn't dominate the entity's context when surfaced alongside other memories.
- Consistent with Aion's observed 10-message average (around 2500 characters per chunk), which worked in practice.

Size is a tuning knob. If retrieval quality suggests 3-turn chunks retrieve better (more focused matches) or 7-turn chunks retrieve better (richer context), this changes without touching architecture — the collection can be wiped and re-chunked from the archive.

### Overlap: none

Overlap was considered and rejected. The argument for overlap is seam robustness. The argument against is that when both overlapping chunks surface for the same query, the entity sees the same exchange twice under the framing "your own experience" — a duplicate-memory problem.

Aion ran with no overlap. Its observable failure mode in the data was not seam failures but short, semantically thin tail chunks (2-message "hi / response" tails). Those are a semantic density problem handled by retrieval's distance threshold (Requirement 19), not a boundary problem.

No overlap is simpler, matches Aion's validated behavior, and avoids the duplicate-memory cost. If retrieval quality later shows seam failures, overlap can be added by re-chunking the archive.

### Live chunking on the 5th turn

A chunk fires when the 5th completed turn lands — meaning after the assistant's response to the 5th turn is saved. The next chunks fire at turn 10, 15, etc.

"Live" means the chunk becomes retrievable during the same session. Crash recovery: if the worker dies mid-conversation, everything up to the last live chunk is retrievable from restart (the archive has everything regardless; this is about the retrievable substrate).

### Final chunk: any size, includes orphan user messages (rule A)

When a conversation closes, any messages that haven't yet been chunked become one final chunk. This includes:

- The normal case: leftover turns after the last regular chunk (e.g., turns 11-12 after a chunk at turn 10).
- The orphan case: a trailing user message with no assistant response (e.g., user sent a message, worker crashed before responding).

Under rule A (settled this session), orphan user messages are included in the final chunk even though they don't represent a completed turn. The final chunk reflects what actually happened — user asked, no response was produced, conversation ended. That's an accurate memory of an awkward moment, which is part of experience (Principle 15).

This is the one case where a chunk can end on a user message rather than an assistant message. Accepted as a documented edge case.

If there are zero unchunked messages at close (a regular chunk just fired and the conversation ended immediately after), no final chunk is written. `chunked = 1` is still set.

### Text format

Each chunk's document text is a timestamped transcript:

```
[March 31, 2026 at 12:36 AM] Lyle: Hi how are you?
[March 31, 2026 at 12:36 AM] assistant: You just asked me that! We were in the middle...
```

Specifics:

- **Timestamp format:** `[Month D, YYYY at H:MM AM/PM]`. Matches Aion's format.
- **Timezone:** `zoneinfo("America/New_York")`, converting the stored UTC timestamp to local time at render. This handles DST automatically (EST in winter, EDT in summer). No zone suffix in the rendered text — chunks read as natural time, not as timestamps with metadata.
- **User side:** resolved user name from `users.name` lookup at chunk-creation time. Not user ID, not channel handle. Per the v1.2 schema decision, the name is embedded at chunk-creation time and never re-resolved — her memory of a conversation with "Sarah" remains "Sarah" even if the users row is later deleted or renamed.
- **Assistant side:** literal `assistant`. Not the entity's name. The framing in her retrieved-memories section ("your own experiences and memories") tells her she is the assistant voice. Labeling with her name would make the chunk read like third-person observation rather than first-person memory.
- **Separator:** one newline between messages.

### Metadata at chunk-creation time

Per the v1.2 schema, every conversation chunk carries:

```python
{
    "conversation_id": str,    # source conversation
    "chunk_index": int,        # 0, 1, 2... within the conversation
    "source_type": "conversation",
    "source_trust": "firsthand",
    "user_id": str,            # the user the entity was talking to
    "message_count": int,      # number of messages in this chunk
    "created_at": str,         # ISO 8601 UTC, when the chunk was written
}
```

All scalar, no `None` values (per the Chroma write path's rules).

**`message_count` clarification:** this metadata field is the count of *messages* in the chunk, not turns. A 5-turn chunk in a cleanly-alternating conversation has `message_count = 10`. A 5-turn chunk where the user sent two quick messages in one turn has `message_count = 11`. A final chunk with trailing orphan user messages has whatever total count of messages it holds. This matches Aion's usage and is what retrieval-side code expects.

**Not to be confused with `conversations.message_count`**, which is the running count of all messages in the conversation (used for UI display and bookkeeping, incremented on every `save_message` call). Chunk metadata's `message_count` is per-chunk; conversation row's `message_count` is per-conversation.

### Chunk ID format

`{conversation_id}_chunk_{chunk_index}`. Matches Aion and the Chroma write spec's convention. Idempotent — re-running chunking on the same conversation produces the same IDs, which makes re-chunking via upsert clean (see below).

### Close-time unchunked-message handling: re-chunk from scratch

When the close operation fires (triggered from the Autonomous Window design's lifecycle, not from this doc), it needs to decide which messages are "unchunked" and need to go into the final chunk. Three options were considered:

- **Derive unchunked from existing chunks:** query ChromaDB for existing chunks of this conversation, count covered messages, determine what's missing. Complex.
- **Track per-message chunked flag:** schema change adding a `chunked` column to `messages`. Most explicit, requires schema change.
- **Re-chunk from scratch:** on close, delete nothing; regenerate all chunks for the conversation using the chunking rules, upsert all of them. Deterministic chunk IDs mean chunks that existed before get overwritten with identical content (ChromaDB effectively no-ops), and any missing chunks (e.g., from a worker crash mid-chunk-write) get filled in.

**Tír chooses re-chunking from scratch.** Reasons:

- Simplest. One code path for close, not two.
- Handles every failure mode: crash mid-chunk-write, partial live-chunk failures, corruption-and-repair scenarios. If the live path ever misses a chunk, close catches it.
- Embedding cost on re-chunk is trivial (small number of chunks per conversation, nomic-embed-text on GPU is fast).
- Correctness property: after close, the ChromaDB state for a given conversation is exactly what the chunking rules say it should be. No drift possible between live chunking state and final state.

This means the live chunking path is an *optimization* (makes chunks retrievable during the conversation rather than only after). The close path is the *correctness guarantee*. Both use the same chunk-generation logic; live calls it incrementally, close calls it for the whole conversation.

---

## What this looks like in practice

### A 7-turn conversation, normal flow

- Turn 5 completes. Live chunking: chunk 0 written (turns 1-5).
- Turn 6, 7 complete. No chunk.
- Close fires. Re-chunk from scratch:
  - Regenerate chunk 0 (turns 1-5) → upsert to ChromaDB (content identical, no-op).
  - Generate chunk 1 (turns 6-7) → upsert.
- `chunked = 1`, `ended_at` set.

Result: 2 chunks, `{conv_id}_chunk_0` and `{conv_id}_chunk_1`.

### A 3-turn conversation

- Turns 1, 2, 3 complete. No live chunk (below 5).
- Close fires. Re-chunk from scratch:
  - Generate chunk 0 (turns 1-3) → upsert.

Result: 1 chunk, `{conv_id}_chunk_0` (3 turns).

### A 10-turn conversation, clean

- Turn 5 completes. Chunk 0 (turns 1-5) written live.
- Turn 10 completes. Chunk 1 (turns 6-10) written live.
- Close fires. Re-chunk from scratch:
  - Regenerate chunk 0 and chunk 1 (both upserted as no-ops).
  - 0 unchunked turns, no chunk 2.

Result: 2 chunks.

### Conversation with orphan user message

- Turn 5 completes. Chunk 0 (turns 1-5) written live.
- User sends message 11 (user role).
- Before assistant responds, worker crashes.
- Worker restarts. Startup recovery (from Autonomous Window Design) finds `ended_at IS NULL` and closes the conversation.
- Close re-chunks from scratch:
  - Regenerate chunk 0 (turns 1-5, no-op upsert).
  - Generate chunk 1 containing the orphan user message 11. Chunk 1's `message_count = 1`, and it ends on a user message.

Result: 2 chunks. Chunk 1 is an accurate record of "user asked, no reply ever came."

### Conversation where crash-recovery catches a partial live chunk

- Turn 5 completes. Live chunker begins writing chunk 0.
- Chunk 0's embedding call completes, upsert to ChromaDB starts.
- Worker crashes mid-upsert. Chroma's state is either unchanged or partially updated (implementation-dependent).
- Worker restarts. Startup recovery finds `ended_at IS NULL`, closes.
- Close re-chunks from scratch:
  - Generate chunk 0 → upsert. Whatever partial state existed in ChromaDB is overwritten with the correct chunk.
  - Any other turns get their chunks too.

Result: ChromaDB state is correct regardless of the crash timing. The re-chunking idempotency provides the safety net.

---

## What this does *not* decide

Deferred to other designs:

- **When close fires.** Handled by the Autonomous Window Design v1.1 (startup recovery is the primary mechanism in v1; other triggers may be added later).
- **Autonomous-session chunking.** Journal entries, research output, tool traces. Different shape — "turn" doesn't apply. Handled when autonomous window design is further along.
- **Document chunking.** URLs, files, articles. Character-based with overlap, separate spec.
- **Retrieval behavior.** What chunks surface for what queries, distance thresholds, deduplication, user filtering. Separate spec.
- **Cross-user retrieval framing.** When a chunk from one user's conversation surfaces during another user's session. Answered by Context Construction Design.
- **Worker-level concurrency.** Handled by Autonomous Window Design v1.1.

---

## Known downstream question

**Same-conversation live chunks and current-conversation context.** In a long conversation, turn 10's retrieval could surface a chunk of turns 1-5 of the same session. But the current-conversation context window already contains turns 1-10 verbatim. The retrieved chunk would duplicate content under a different framing.

This is not a chunking problem — chunking is correct, retrieval is correct, context construction is correct. It's an interaction between them that retrieval design should handle: retrieval should probably exclude or deprioritize chunks from the active conversation. Noted because this design creates the condition, solved in retrieval design.

---

## Implementation hooks (for the chunking implementation spec)

This doc is not the implementation spec, but identifies what the implementation will need:

- **Turn counting.** `SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'assistant'`.
- **Live chunking trigger.** After `save_message` commits an assistant message, check if the new turn count is a nonzero multiple of 5. If so, fire live chunking for the just-completed chunk.
- **Live chunk assembly.** Read the messages for the just-completed chunk (turns N-4 through N for chunk index (N/5)-1), format with timestamps and resolved user name, upsert to ChromaDB.
- **Close operation.** Re-chunk the whole conversation from scratch. For each chunk_index from 0 upward, compute which messages belong to that chunk using the turn-boundary rules, assemble chunk text, upsert to ChromaDB. Final chunk includes any unchunked tail (including orphan user messages). Set `chunked = 1` and `ended_at` on the conversation row.
- **Chunk text assembly utility.** Takes a list of messages (with role, content, timestamp) and a user name, returns the formatted chunk text. Shared between live and close paths.
- **Timezone conversion.** `datetime.fromisoformat(ts_utc).astimezone(zoneinfo.ZoneInfo("America/New_York"))`, then `.strftime("%B %-d, %Y at %-I:%M %p")`. (Or equivalent — exact format string left to implementation.)

---

## Open implementation questions

**a. Timezone configurability.** Hard-coding `America/New_York` is fine for the single-server, single-location case. If multi-timezone use ever becomes real, the timezone becomes a config value. Not v1 concern.

**b. Live-chunking failure handling.** If a live chunk's embedding call fails (Ollama down, GPU issue), does `save_message` fail, or does chunking fail silently and get caught at close? Recommend: chunking fails silently (logged warning), close re-chunks and fills the gap. `save_message` succeeds regardless, because message persistence to the archive is the sacred operation (Principle 5) — chunking can catch up later.

**c. Timezone format exact string.** `[%B %-d, %Y at %-I:%M %p]` produces `[March 31, 2026 at 12:36 AM]`. Note the `%-d` and `%-I` (no zero-padding) are POSIX-only. On Windows (not a target) this would need `%#d` and `%#I`. macOS uses POSIX.

---

*Project Tír Conversation Chunking Strategy · v1.1 · April 2026*
