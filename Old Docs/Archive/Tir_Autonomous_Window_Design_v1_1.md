# Project Tír — Autonomous Window Design

*Draft v1.1, April 2026. Revised from v1 with: conversation-vs-conversation concurrency rule, and conversation lifecycle close triggered by startup recovery.*

*The shape of the entity's existence: when she's working, when she's talking, and how she moves between those states.*

---

## Purpose

This document defines how the entity spends her time. Not every moment of it — that's too granular — but the operational shape of her existence. When is she doing autonomous work? When is she available for conversation? What happens when those two overlap? What gets persisted across the boundary?

The answer to those questions determines what "she" even means as a running system. Without this design settled, every piece of code that touches persistence, agent loops, or session lifecycle is guessing.

This is the v1 design. It is deliberately narrower than what the project will eventually need. The design is built so v1 can be extended into more ambitious models without rewriting the foundation.

---

## v1 scope

**What v1 includes:**

- Scheduled autonomous sessions — one or more configurable daily windows during which she does autonomous work (research, journaling, creative work, tool use).
- Single communication channel — web UI only on day one.
- Conversations take priority over autonomous work — if someone messages her during an autonomous window, the session ends and conversation begins.
- Turn-level serialization between conversations — one conversation turn at a time at the worker level.
- Conversation close via startup recovery — on worker startup, any conversations left open are closed cleanly.
- Task queue persisted from day one — three sources of work (user-assigned, scheduled recurring, self-generated), even though self-generated isn't implemented yet.
- Gateway pattern from day one — adapters translate channel-specific events into a normalized message format; the conversation engine never touches channel-specific code.

**What v1 explicitly defers:**

- Multi-channel communication (iMessage, Discord, etc.)
- Always-on autonomy (working outside scheduled windows)
- Fine-grained presence detection
- Sub-task interruption with state preservation
- Self-generated task creation during sessions
- Idle-timeout conversation close
- Graceful-shutdown conversation close (startup recovery handles both graceful and ungraceful shutdown cases)

Each deferred item is architecturally pre-accommodated — see "What's deliberately deferred" at the end.

---

## States and transitions

The worker — the process that runs the entity's agent loop — has two states:

- **WORKING** — a session is active. Either autonomous work or conversation. The model is being called, tools may be firing, the task queue or a conversation is being processed.
- **QUIET** — no session is active. The worker exists but is doing nothing.

There is no distinct "IDLE-but-waiting-for-work" state. If there's no work to do and no conversation happening, the machine is just quiet.

Transitions:

- **QUIET → WORKING (autonomous)**: triggered by the scheduler at a configured time. The worker starts an autonomous session, pulls a task from the queue, and begins an agent loop.
- **QUIET → WORKING (conversation)**: triggered by a message arriving through any adapter. The worker starts a conversation session.
- **WORKING (autonomous) → WORKING (conversation)**: triggered by a message arriving while an autonomous session is running. The autonomous session yields, saves state, and closes. A conversation session begins.
- **WORKING → QUIET**: a session ends — conversation closes, or autonomous window ends, or task queue is empty, or the worker explicitly stops.

The key simplification: **conversation always takes priority over autonomous work.** There is never a case where the worker is doing autonomous work *and* a conversation at the same time. A message arrival always ends the autonomous session.

---

## Conversation concurrency

Even with one channel (web UI), it is possible for the worker to receive messages from different conversations in rapid succession. v1 handles this with turn-level serialization.

**Rule: the worker processes one turn at a time. A turn is indivisible.**

A turn here is: receiving a user message, generating the assistant's response, and committing both to storage.

When the worker is mid-turn (generating the assistant response for conversation A) and a message for conversation B arrives:

- B's message is saved to storage immediately via the dual-write path (this doesn't block on the agent loop — storage writes are independent).
- B's message is queued for processing.
- When A's turn completes (assistant message saved), the worker picks up whatever's next.

If the worker is idle (between turns — e.g., A's last response sent, waiting for A's user to type again) and B's message arrives, B is picked up immediately. A's conversation isn't "still active" in any worker-state sense; it's just the most recent conversation that happened to be open.

This is why this concurrency rule is simple: **there is no concept of "an active conversation" at the worker level.** The worker has in-flight turns, not active sessions. Between turns, there's nothing to preserve. The next message to arrive (from any conversation, in any channel) gets handled next.

Practical consequences for v1:

- Single user, single channel: message arrivals will rarely overlap with in-flight turns. Concurrency is theoretical.
- When multi-channel arrives (iMessage etc.), this rule continues to work without change. Two users conversing concurrently each wait tens of seconds (at most) for the other's turn to complete between their own turns.
- The cost is a small wait when turns overlap. In a single-user personal project, this is not a user-facing problem.

---

## Conversation lifecycle

A conversation begins when the first message from a user arrives (the adapter creates or reuses a conversation row and calls `save_message`). A conversation ends when `close_conversation` is called, which sets `ended_at` and writes the final chunk.

**v1 has one trigger for `close_conversation`: worker startup.**

On worker startup, the worker scans for any conversation with `ended_at IS NULL` and calls `close_conversation` on each. This handles every realistic shutdown scenario:

- **Graceful shutdown (deploy, planned restart):** the worker stops with conversations possibly still open. On next startup, those conversations get closed. Lyle's next message starts a new conversation.
- **Ungraceful shutdown (crash, power loss):** same as graceful from the storage perspective — conversations were left open. On restart, they get closed.
- **Browser closed without explicit "end conversation":** the conversation stays open until next startup. Lyle could in principle open a new browser session and send a message in the same conversation (if the adapter's resume logic allows it). Next restart closes.

**Consequence for v1:** conversations with `ended_at IS NULL` may accumulate between worker restarts. This is cosmetic (data is fine, chunks are fine, retrieval works), not functional. If it becomes annoying, an idle-timeout close mechanism can be added later.

**What close does (from the Chunking Strategy v1.1):**

- Re-chunks the whole conversation from scratch (deterministic chunk IDs + upsert make this idempotent).
- Writes any missing chunks, including a final chunk if there are unchunked trailing messages (including orphan user messages with no assistant reply — rule A).
- Sets `chunked = 1` and `ended_at` on the conversation row.

Close is safe to call multiple times on the same conversation — the re-chunking is idempotent, and subsequent calls are no-ops.

---

## The yield signal

When the autonomous session needs to stop, it stops through a **yield signal** — a flag the agent loop checks between iterations.

On day one, the yield signal is triggered by two things:

1. The autonomous window's end time is reached.
2. A message arrives on any channel.

The agent loop, inside an autonomous session, looks roughly like:

```
loop:
    check yield signal
    if yield signal is set:
        save current state to the task queue (note what step was reached)
        close the session
        return
    generate next model output (may include a tool call)
    execute tool call if present
    save result to memory
```

The **atomic unit** — the thing that runs to completion before checking the yield signal again — is one complete tool call and its result. This means:

- If a message arrives mid-generation, she finishes generating and runs the tool.
- If the tool takes 10-30 seconds (a web fetch, a research query), she finishes it before yielding.
- Once the tool result is in and saved, she checks the yield signal and stops if set.

The consequence: when someone messages her during autonomous work, she responds within seconds to tens of seconds, not instantly. That's an accepted tradeoff for v1 — in the web UI, a brief "finishing something up..." indicator can cover this gap naturally.

**Why this boundary:** finer than "one tool call" means she might yield mid-plan — saying "let me check that" without actually checking, which is an awkward stopping point. Coarser than "one tool call" means multi-step agent loops could hold the user waiting minutes, which is unacceptable for responsive chat.

---

## The task queue

The task queue is how work is organized. It exists from day one and persists across sessions.

**Shape:** a simple table (initially a SQLite table in the working store, though a JSON file would also work for v1). Each row represents a piece of work.

**Fields (proposed for v1):**
- `id` — UUID
- `description` — natural language description of the work
- `source` — where the task came from: `user`, `scheduled`, or `self` (`self` reserved for future use)
- `priority` — numeric, higher is more important. Simple integer on day one, no complex scheduling logic.
- `status` — `pending`, `in_progress`, `completed`, `abandoned`
- `progress_note` — free text field where the entity writes what step she reached when yielding. Null for tasks never started.
- `created_at`, `started_at`, `completed_at` — timestamps

**Three sources on day one:**

1. **User-assigned.** Lyle (or any user) can add tasks through conversation. Example: "Read this paper and tell me what you think tomorrow." The entity or an admin writes the task to the queue.
2. **Scheduled recurring.** Tasks the entity does on a cadence. Example: "Journal about yesterday's conversations." These are added to the queue by the scheduler at appropriate times.
3. **Self-generated.** Reserved for future. The entity isn't yet adding her own tasks; this field exists so the schema doesn't need changes later.

**Lifecycle:**

- A task starts as `pending`.
- The scheduler picks a pending task and hands it to the worker. Status → `in_progress`, `started_at` set.
- The entity works on it inside an autonomous session.
- If she finishes: status → `completed`, `completed_at` set, a note about what was produced is saved to memory.
- If she yields before finishing: status → `pending` again, `progress_note` updated with what step she reached.
- If she actively gives up or decides it's not worth doing: status → `abandoned`, reason saved to `progress_note`.

**Progress note on yield:** when the yield signal fires mid-task, she doesn't preserve her working memory (the full agent loop context). She writes a short note — "Got to step 2 of 4: finished reading paper, haven't written summary yet" — and saves it to the task. Next time she picks up this task, she starts with fresh context and reads her own note to orient herself.

**This matches how humans handle interrupted work.** You don't literally resume mid-thought after an interruption; you remember what you were doing and pick it back up.

---

## The scheduler

The scheduler is a separate process from the worker. Its job is simple: at configured times, invoke the worker to start an autonomous session.

**Day-one scheduler behavior:**
- Reads a configuration file defining autonomous windows (e.g., "2am-10am daily").
- At the start of a window, checks if the worker is QUIET. If yes, invoke it with "autonomous session."
- If the worker is already WORKING (in a conversation), do nothing. The window passes; she just doesn't do autonomous work this time.
- At the end of the window, if the worker is still doing autonomous work, set the yield signal so the current task yields cleanly.

**Task selection within a session:**
- When the worker starts an autonomous session, it pulls the highest-priority pending task from the queue.
- When a task completes (or yields), the worker pulls the next pending task.
- When the queue has no pending tasks, the autonomous session ends early.

**Why the scheduler is separate:**
- The worker shouldn't know what time it is or when it's supposed to be working. It just runs sessions when told.
- The scheduler can be replaced or extended without touching the worker.
- Future "always-on" mode is a scheduler change: instead of "run from 2am-10am," the rule becomes "run whenever the queue has pending work." Worker code doesn't change.

---

## Gateway pattern

Channels are different in how they deliver messages. Web UI has HTTP requests. iMessage has macOS events. Discord has webhooks. Each has its own format, quirks, and metadata.

The **gateway pattern** keeps channel-specific code out of the conversation engine. The shape:

- Each channel has an **adapter** — a small module that handles only that channel's specifics.
- The adapter listens for incoming events (HTTP, iMessage, whatever) and translates them into a **normalized message format**.
- The conversation engine receives normalized messages. It never sees HTTP requests, iMessage GUIDs, or Discord payloads.
- When the engine produces a response, it's also in the normalized format.
- The adapter translates the normalized response back into channel-specific output (HTTP response, iMessage send call, Discord webhook reply).

**Normalized message format (day-one proposal):**
```python
{
    "channel": str,           # "web" on day one
    "user_id": str,           # resolved to a row in the users table
    "text": str,              # the actual message content
    "timestamp": str,         # ISO 8601 UTC
}
```

**Normalized response format:**
```python
{
    "text": str,              # the entity's response
    "timestamp": str,         # when generated
}
```

The normalized format will grow as new capabilities are added — attachments, typing indicators, multi-part messages. v1 keeps it minimal. Each new capability is a new optional field that adapters ignore if they can't render it.

**Day-one adapter:**
- `web_adapter.py` — Flask (or similar) route handler that receives POST requests and calls `conversation_engine.handle_message(normalized_message)`.

**Future adapters, each following the same pattern:**
- `imessage_adapter.py` — listens for iMessage events, translates to normalized format.
- Any other channel — same shape.

---

## What's deliberately deferred

Each of the following is part of the larger design but explicitly not in v1. Each has a note on how v1 accommodates its future addition.

**Multi-channel communication.** v1 has web UI only. Adding iMessage is writing a new adapter that speaks the normalized format. The conversation engine needs no changes.

**Always-on autonomy.** v1 runs autonomous work only during scheduled windows. Adding always-on is a scheduler change: replace "run from 2am-10am" with "run whenever queue has pending work." Worker code is unchanged.

**Fine-grained presence detection.** v1 has no concept of "is the user currently present" beyond "did a message just arrive." Conversation ends via startup recovery, not via user-absence detection. Adding presence is new logic in the scheduler or conversation engine; adapters can contribute presence signals (last-activity timestamps, heartbeats) that the engine interprets.

**Idle-timeout conversation close.** v1 uses startup recovery as the sole close mechanism. Adding an idle timeout means a periodic process that scans for conversations whose last message is older than N hours and calls `close_conversation` on them. The close operation is already idempotent; adding the timer is the whole change.

**Graceful-shutdown conversation close.** v1 does not attempt to close conversations on shutdown. Startup recovery handles the same state on the next run. Adding graceful-shutdown close means registering a signal handler (SIGTERM) that iterates open conversations and calls `close_conversation` before exit. Minor, not needed day-one.

**Sub-task state preservation.** v1 yields by saving a progress note, not working memory. Adding resumable agent state means extending the task row (or adding a parallel state store) to serialize the full agent loop context on yield. The agent loop needs to learn how to deserialize and continue. This is a real change but it only touches the yield path and session start.

**Self-generated tasks.** v1 task queue has a `source` field that accepts `self` but no code writes with that value yet. Adding self-generation is: (a) giving the entity a tool for `add_task`, (b) deciding when during conversation/work she's allowed to use it. The queue and lifecycle are already there.

**Intra-session task switching.** v1 runs one task at a time within a session. Adding multi-task sessions (she decides mid-session to switch because something more important came up) means the agent loop gains a decision step between tasks. Queue shape supports this already.

**Concurrent autonomous and conversation work.** v1 treats these as mutually exclusive. Allowing them to coexist (she continues a slow research task while chatting) would require concurrent agent loops and shared memory access. This is not just deferred — it's an open design question. If v1's pattern proves limiting in practice, that's when this gets designed.

---

## Open questions

These are real questions not settled in v1. They're flagged so they get visited again when v1 is running and we have data.

**a. Window length and number.** Is one window per day (2am-10am) right, or should there be multiple short windows? Depends on how much work the entity accumulates and how long individual tasks take. Answer comes from watching v1 run.

**b. Task priority logic.** Day one uses a simple integer priority with ties broken by creation time. Is that enough, or does the queue need due dates, dependencies, categories? Answer comes from watching what kinds of work the entity does in practice.

**c. What happens when the autonomous window starts and the queue is empty.** Three options: (1) she's quiet until a task appears, (2) she picks something to do on her own (requires Level 3 prompting — "what do you want to do?"), (3) the scheduler generates a default task (e.g., "journal about yesterday"). v1 probably starts with option 1 but will likely need option 2 or 3 quickly.

**d. Yield indicator in conversation.** When a message arrives during autonomous work and she takes 30 seconds to respond, does the web UI show "thinking..." or "finishing up a task..." or just nothing? This is a UX question that affects perceived responsiveness.

**e. How long after the autonomous window ends should the worker stay up before going QUIET.** If she just finished a task at 9:58am and the window ends at 10am, does she go QUIET at 10am sharp? Probably yes — but if a conversation started at 9:59am, it shouldn't be cut off at 10am. Session boundaries need to be clearly defined.

**f. Crash recovery for autonomous tasks.** The task queue: a task marked `in_progress` with no worker running needs to be reset to `pending` on next startup. Conversation-level crash recovery is handled by the startup conversation-close rule; the task-level equivalent is a small addition to startup logic.

**g. Web adapter conversation resume vs. new.** When Lyle reconnects via web after closing the browser, does the adapter continue the most recent open conversation, or start a new one? This is a web-adapter design question, not an autonomous-window one, but it interacts with the "conversations accumulate open" behavior described above.

---

*Project Tír Autonomous Window Design · v1.1 · April 2026*
