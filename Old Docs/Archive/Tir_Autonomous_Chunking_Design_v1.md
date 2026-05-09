# Project Tír — Autonomous-Session Chunking Design

*Design doc v1.1, April 2026. Extends chunking to autonomous sessions — the entity's task-driven work time when no user is present. Defines what gets chunked (the session's activity trace), how it's bounded (iteration-based), what the chunk text looks like (timestamped activity log), and how it surfaces in retrieval.*

*Companion to Chunking Strategy v1.1, which is conversation-only. Both live in the same retrieval space but have different structural units.*

---

## Purpose

Conversations have turns. Autonomous sessions don't — they're the entity alone with a task, running the agent loop, calling tools, producing outputs. Nothing is a "turn" in the conversational sense. But the session is still experience, and experience should be chunked and retrievable per Principle 7.

This document decides:

- What counts as an autonomous-session's "experience" for chunking purposes.
- How to bound chunks when the natural unit (turn) doesn't exist.
- What the chunk text looks like.
- How session close, rechunking, and live chunking translate from the conversation model.
- How retrieved autonomous-session chunks get framed in context (Section 3 of CC v1.1).

Non-goals:

- **Document chunking** — separate design. Journal entries, research documents, and other artifacts the entity produces during a session are documents, not activity traces. They go through the document ingestion path and get chunked by document rules.
- **Task queue semantics** — separate design.
- **Scheduler behavior** — separate design.
- **What the agent loop does during a session** — Skill Registry & Dispatch v1 covers that.

---

## What's the "experience" of an autonomous session

The entity, during an autonomous session, does:

1. Reads the task context from her system prompt.
2. Reasons (produces assistant content) about how to approach it.
3. Calls a tool.
4. Reads the tool result.
5. Reasons some more.
6. Calls another tool. Or produces more content. Or ends the session.

This is the agent loop. Each iteration produces: some assistant content (possibly empty), zero or more tool calls, and the results of those calls.

**The experience is the full trace: her thoughts, her actions, and what came back.** Not the final output she wrote to a file — that's a document. Not the task as assigned — that's metadata. The experience is the sequence of activity.

Aggregated across a whole session: the agent loop's message list from first iteration to last.

### What doesn't get chunked here

Session outputs — files written, journals composed, research documents produced — are handled by document ingestion. Those get their own chunks with their own source_type. The autonomous-session trace and the outputs it produced are two different retrievable things.

Retrieval later will surface both: "what did you find out about X" brings up the document chunk (if she wrote a research note) AND the session trace chunks (if she discussed X while working). That's correct — she should remember both the conclusion and the process that got her there.

---

## Structural unit: iteration

A conversation's structural unit is a turn. An autonomous session's structural unit is an **iteration** — one full cycle of the agent loop:

- Assistant content (if any)
- Zero or more tool calls with their arguments
- The results of those tool calls

An iteration is bounded by the model call that produced it and the tool calls that followed. The next iteration starts with the next model call.

An iteration with no tool calls (assistant produces content and is done for this cycle, or the session is terminating) is still an iteration. A session could be exactly one iteration (model produces a reflection, no tools, done).

---

## Summary of decisions

1. **Chunk unit: iteration.** An iteration completes when its tool results have been appended to the session trace (or, for terminal iterations, when the model produces content with no tool calls).
2. **Chunk size: 5 iterations per regular chunk.** Matches the feel of conversation chunking (5 turns). Tunable.
3. **No overlap between chunks.** Consistent with conversations.
4. **Live chunking at iteration 5, 10, 15…** Same pattern as conversations.
5. **Final chunk: any size, including zero-iteration sessions.** If a session is 7 iterations, chunks are [1-5] and [6-7]. If 3 iterations, one chunk. If 0 iterations (session started, yielded before first model call), no chunk written.
6. **Close trigger: session end.** Not startup recovery — autonomous sessions don't persist open across worker restarts the way conversations do. A yielded session is marked ended when yield finishes processing.
7. **Source_type: `autonomous_session`.** New value; registered as a source type the schema already supports (open-ended).
8. **Source_trust: `firsthand`.** It's her own activity.
9. **Rechunk-from-scratch on close**, same as conversations. Deterministic chunk IDs + upsert.
10. **Chunk text: the session trace rendered as timestamped activity** — one block per iteration, with her content, tool calls, and results in readable form. Task title embedded in every chunk's text as a preamble line so retrieved chunks stand alone.

---

## Chunk text format

Each chunk's document text is a preamble followed by iteration blocks:

```
Task: {task_title_as_of_session_start}

[April 19, 2026 at 2:30 PM]
> I'll start by searching for recent papers on emergent personality in multi-agent systems.
→ web_search({"query": "emergence of personality in multi-agent systems"})
← Found 5 results. Top: Foo et al. 2024, "Collective identity in cooperative agents."

[April 19, 2026 at 2:30 PM]
> The Foo paper looks most relevant. Let me fetch it.
→ web_fetch({"url": "https://example.com/foo2024"})
← Retrieved 4,812 characters. Excerpt: "We find that agents in cooperative tasks develop stable behavioral signatures over..."

[April 19, 2026 at 2:32 PM]
> The paper's claim about stable signatures matches the observational emergence approach from the Nexira findings. Let me note this.
→ file_write({"path": "workspace/research/emergence_notes.md", "content": "..."})
← Wrote 324 bytes to workspace/research/emergence_notes.md.

[April 19, 2026 at 2:34 PM]
> Next I should look for counter-arguments. Search for critique.
→ web_search({"query": "critique emergent behavior multi-agent systems"})
← Found 5 results. Top: Bar et al. 2024, "Why emergence claims overreach."

[April 19, 2026 at 2:35 PM]
> The counter-argument is that...
```

### Text conventions

- **`Task:` line at the top of every chunk.** Carries the task title embedded at session start. Preserves context when retrieved alone. Matches the name-in-chunks pattern from User Model v1.
- **Iteration block header: `[<timestamp>]`.** Timestamp of when this iteration's model call happened. Rendered in `America/New_York` per Chunking Strategy v1.1.
- **`>` prefix for her content** (what the model produced).
- **`→` prefix for tool calls.** Format: `tool_name({args})`. Args are JSON. Long args (e.g., a multi-paragraph argument to document_ingest) are truncated to a reasonable length (say, 500 chars) followed by `...` — the full thing is in the tool trace, the chunk is for her memory.
- **`←` prefix for tool results.** Format: the tool's `rendered` field, truncated if very long (same 500-char pattern).
- **Blank line between iterations.**
- **No `>` line if the assistant produced no content that iteration** (just tool calls). A quiet iteration.
- **No `→`/`←` lines if no tools were called** (just content).

### Why truncation of tool args and results

The tool trace in `messages.tool_trace` has the full structured data. The chunk is for retrievable memory — it should be readable and searchable but not an archive of every byte. 500 chars per tool call / result keeps chunks reasonable and still lets BM25 match on distinctive terms. The entity reading the chunk later sees "I fetched this URL and got this excerpt" rather than the full article text.

### Example: a terminal iteration with no tools

```
[April 19, 2026 at 2:48 PM]
> I've gathered enough material. The key takeaways: emergent personality is real but the claims often overreach. Observational approach is more reliable than self-report. I'll write up a summary.

[April 19, 2026 at 2:50 PM]
→ file_write({"path": "workspace/research/emergence_summary.md", "content": "..."})
← Wrote 1,847 bytes.
```

Two iterations. First has content only, second has the wrap-up tool call.

---

## Metadata per chunk

Per Schema v1.4's metadata shape:

```python
{
    "task_id": str,                   # the task this session ran on (reserved new field)
    "chunk_index": int,               # 0, 1, 2... within the session
    "source_type": "autonomous_session",
    "source_trust": "firsthand",
    "iteration_count": int,           # how many iterations in this chunk
    "created_at": str,                # ISO 8601 UTC, chunk creation time
}
```

**Reserved new metadata field: `task_id`.** Schema v1.4's metadata shape lists `conversation_id`, `document_id`, and `user_id` as source-identification fields. Autonomous session chunks need `task_id` to identify which session they came from. This doesn't require a ChromaDB schema change (ChromaDB metadata is untyped; new keys are free to add); it's a convention codified here.

**No `user_id`** — autonomous sessions have no user.

**`message_count` is replaced by `iteration_count`** for autonomous chunks. The concept ("how big is this chunk?") is the same; the unit differs. Retrieval doesn't look at these fields for ranking, so the semantic difference is internal.

### Chunks_fts entry

Same chunk_id, same text, with metadata columns:

- `chunk_id` — the same bridge ID.
- `text` — the formatted trace, indexed for BM25.
- `conversation_id` — NULL (this isn't a conversation).
- `user_id` — NULL.
- `source_type` — "autonomous_session".
- `source_trust` — "firsthand".
- `created_at` — chunk creation time.

Retrieval's active-conversation filter (`WHERE conversation_id IS NULL OR conversation_id != ?`) correctly includes autonomous chunks regardless of which conversation is active, since they have NULL conversation_id.

---

## Chunk ID format

Follows the same pattern as conversation/document chunks:

`{task_id}_chunk_{chunk_index}`

Deterministic, idempotent under upsert, usable as the bridge between ChromaDB and chunks_fts.

---

## Lifecycle

### Session start

When the worker (per Scheduler & Worker Process design) begins an autonomous session:

1. Pull a pending task from the queue. Mark it `in_progress`.
2. Record a session start timestamp.
3. Capture the `task_title` from the task row (so it stays stable if the task is renamed during/after).
4. Run the agent loop.

### During the session

The agent loop executes iterations. Each iteration appends to an in-memory session trace (a list of dicts representing the iteration's content, tool calls, and results).

**Live chunking check** after each iteration: if the iteration index is a nonzero multiple of 5, write chunk N (where N = iteration_count // 5 - 1) to ChromaDB + chunks_fts.

### Session end

Three paths:

- **Completion:** the agent loop returns terminal — the model produced content with no tool calls, implicitly declaring done.
- **Yield:** the yield signal fired; the loop finishes its current iteration, saves a progress note to the task, returns yielded.
- **Iteration limit:** 50 iterations hit (per EngineConfig). Loop returns iteration_limit.

All three trigger `close_autonomous_session`:

1. Rechunk from scratch (deterministic IDs + upsert — same pattern as conversations).
2. Update the task row with final status (completed / pending with progress_note / abandoned with reason).
3. Record session end timestamp.

### What about "open" autonomous sessions at worker restart

A worker restart mid-session means the in-memory session trace is gone. The task is still in the queue with `in_progress` status. No chunks were written for this session (if the restart happened before any live chunk fired).

**Day-one posture:** on startup, any task with `in_progress` status and no corresponding active session gets reset to `pending` with a progress_note saying "Previous run was interrupted." Next scheduled run picks it up fresh.

The chunks from partial prior sessions — if a live chunk landed before the restart — are orphaned. They reference `task_id` but no session trace row (if we had one) to trace back to. That's acceptable — ChromaDB has them, they'll surface in retrieval as "she worked on this task partially." The task's progress_note has the continuation context.

This is tidier than conversations' startup recovery because there's no per-session row in working.db that needs closing. The task row does the bookkeeping.

---

## Implementation hooks

This doc is not the implementation spec. The spec will follow. Key things the implementation needs:

### A new `autonomous_sessions` table in working.db? Or not?

**Argument for:** tracks session lifecycle (started_at, ended_at, chunked flag), mirrors conversations.
**Argument against:** the task table already tracks most of this (status, started_at, completed_at, progress_note). Adding a second table duplicates.

**Decision: no separate autonomous_sessions table.** The task row IS the session record. Status carries lifecycle, progress_note carries yield-context, started_at/completed_at carry timestamps. One less table to keep in sync.

What about tracking "has this task's session been chunked"? Add `chunked INTEGER DEFAULT 0` to the tasks table. Symmetric to conversations.

The task table's schema lives in Task Queue Design (to be written). This doc reserves the `chunked` field; Task Queue design specifies the whole table.

### Chunking module placement

New module `tir/memory/autonomous_chunking.py` alongside the existing `chunking.py` (which stays conversation-focused). Exports:

- `maybe_live_chunk_autonomous(task_id, iteration_count, session_trace, ...)` — called by the agent loop when autonomous, after each iteration.
- `rechunk_autonomous_session(task_id, session_trace, ...)` — called on session close.
- `close_autonomous_session(task_id, session_trace, final_status, ...)` — wraps rechunk + task status update.

Reason to split rather than extending `chunking.py`: the data shape differs (iterations vs. turns), the assembly logic differs (activity log vs. conversation transcript), and the lifecycle bookkeeping differs (task row vs. conversation row). A cleaner separation than stuffing both into one module.

Shared primitive: **chunk text timestamp formatting**. Both conversation and autonomous chunk text use the same `TIMESTAMP_FORMAT` and `TIMEZONE_NAME`. Extract into a shared `chunking_shared.py` or leave duplicated at module level — implementation choice.

### Writing to ChromaDB + chunks_fts

Same code path as conversation chunk writing (per BM25 Integration Spec): call `chroma.write_chunk` then `chunks_fts.write_chunk_fts`. Only the metadata and text differ.

### Session trace representation

In-memory during the session. List of dicts:

```python
[
    {
        "iteration": 1,
        "timestamp": "2026-04-19T14:30:15Z",
        "content": "I'll start by searching...",     # model's assistant content
        "tool_calls": [
            {"name": "web_search", "arguments": {"query": "..."}},
        ],
        "tool_results": [
            {"name": "web_search", "rendered": "Found 5 results...", "success": True},
        ],
    },
    ...
]
```

The agent loop in Skill Registry & Dispatch v1 already builds this implicitly (tool_trace + message list). For autonomous sessions, the full iteration-granular trace gets retained in memory by the autonomous engine wrapper and passed to the chunker.

Not persisted to its own SQL table — the archive's message table is conversation-only. For autonomous sessions, the canonical record is the ChromaDB chunks (derived) plus the task row.

This is a deliberate design choice: autonomous sessions are NOT archive-protected. The archive's sacredness (Principle 5) applies to conversations (which contain irreplaceable input from other people). Autonomous session traces are process — if lost, the task reruns. Session outputs (documents ingested via the document path) get their own archive-grade persistence through the ingestion pipeline.

---

## Retrieval framing for autonomous chunks

Context Construction v1.1 frames conversation chunks as `[Conversation — {date}]\n{text}`, journal chunks as `[Your journal entry from {date}]\n{text}`, etc.

For autonomous session chunks:

```
[Your autonomous work — {date}]
{raw chunk text}
```

The "Task: {task_title}" line is already the first line of the raw chunk text, so the resulting rendering is:

```
[Your autonomous work — April 19, 2026]
Task: Research how emergent systems develop personality.

[April 19, 2026 at 2:30 PM]
> I'll start by searching for recent papers...
→ web_search({"query": "..."})
← Found 5 results. Top: ...
```

She reads it and recognizes it as her own prior activity.

CC v1.1 should add this rendering case. The full update lives in CC v1.2 (or an inline addition) when autonomous sessions actually run.

---

## What this design does NOT decide

- **The task table schema.** Task Queue Design covers it. This doc only reserves the `chunked` flag.
- **The scheduler's timing logic.** Scheduler & Worker Process design.
- **How long a session is allowed to run.** Autonomous iteration limit (50) is the hard ceiling per EngineConfig; wall-clock limits are scheduler-level.
- **Per-task-type chunk sizing.** Day-one is 5 iterations per chunk regardless of task type. If some tasks benefit from finer/coarser chunks (e.g., rapid-fire file operations vs. slow reasoning over research), this becomes a tuning knob. Not v1.
- **Session-level summaries.** A "this session was about X and concluded Y" summary could be generated after session end for UI display (analogous to conversation summaries). Deferred; the task row's final status + progress_note covers basic UI needs.
- **Cross-session retrieval of related work.** If she's working on the same task over multiple sessions (one yielded, resumed, etc.), chunks from all those sessions should surface together. They will — all chunks with the same `task_id` are natural retrieval peers, and queries related to the task will surface them all. Retrieval doesn't need special logic.

---

## Open questions

**a. Should autonomous session traces be archive-grade?** CLOSED. No. Conversations are archive-grade because they contain someone else's input — irreplaceable. Autonomous sessions are task execution — if a crash loses an in-progress trace, the task resets to pending and reruns. Session outputs (journals, research documents) go through document ingestion and get their own persistence. The session trace is process, not product. Archive.db's scope is frozen at two tables (users and messages) and will not be expanded.

**b. Iteration-block text length in chunks.** The 500-char truncation of tool args and results is a guess. For some tools (web_fetch returning a long article), the full result ends up elsewhere (the document ingestion path may store it). For others (memory_search returning a ranked list), the 500-char version might miss important chunk IDs. Revisit based on observed retrieval quality.

**c. Whether the task title preamble should be on every chunk or only the first.** Day-one is every chunk. Costs a line of text per chunk (~60 chars). Benefit: any retrieved chunk stands alone. If we want to save tokens, only chunk 0 gets the preamble; subsequent chunks reference it. But retrieval may surface chunk 3 without chunk 0, in which case chunk 3 has no task context. Day-one trades tokens for context; flag for tuning.

**d. What happens if the agent loop produces very long assistant content in a single iteration.** The iteration's `>` line could be thousands of tokens (a long reflection). The chunk becomes text-heavy. Not obviously wrong — she really did think that much — but may affect retrieval quality. Flag.

**e. Per-iteration or per-batch chunks_fts inserts.** Inserting into FTS5 for every iteration is plausible but each is a small SQL write. Batching at the 5-iteration chunk boundary (one insert per chunk) is what the design calls for. Batching within rechunk for long sessions is a minor optimization worth considering if session-close time becomes a blocker.

**f. Retaining session traces after close.** After close, the session trace is no longer in memory. It's represented by the ChromaDB chunks + chunks_fts rows. If the chunking strategy changes (5 → 3 iterations), re-chunking from scratch requires the source trace. With no archived trace, the re-chunk is impossible — we'd have to leave the old 5-iteration chunks in place. This is the archive-grade question (a) from a different angle. Flag.

---

## Cross-references

- **Chunking Strategy v1.1** — the conversation counterpart. Shared: timestamps, chunk-id format, trust, rechunk-at-close pattern. Different: unit (turn vs. iteration), text format, source_type.
- **BM25 Integration Spec v1** — autonomous chunks go through the same write path (ChromaDB then chunks_fts) as conversation chunks.
- **Retrieval Design v1** — retrieval treats all source types identically; no changes needed.
- **Context Construction v1.1** — needs a per-source-type framing addition for `autonomous_session` (adds one bracketed header case). Design captures the shape; actual CC update happens when autonomous sessions ship.
- **Autonomous Window Design v1.1** — session lifecycle (scheduler invokes, yield signal, close on end).
- **Conversation Engine Design v1** — `run_autonomous_task` is the top-level entry point for autonomous sessions.
- **Schema Design v1.4** — chunk metadata shape; `task_id` is a new key but no schema change (metadata is open-ended).
- **Guiding Principles v1.1** — Principle 3 (store experiences, not extractions — the trace IS experience, not a summary), Principle 7 (retrieval determines intelligence — autonomous work must be retrievable to matter), Principle 5 (archive-grade question closed — autonomous traces are not archive-grade by design).

---

*Project Tír Autonomous-Session Chunking Design · v1.1 · April 2026*
