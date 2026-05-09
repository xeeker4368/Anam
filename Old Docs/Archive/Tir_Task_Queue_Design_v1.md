# Project Tír — Task Queue Design

*Design doc v1.1, April 2026. Specifies the task queue table, the `add_task` tool, task lifecycle and state transitions, priority semantics, and crash recovery. The scheduler consumes this queue; the entity contributes to it via `add_task`; the admin surface also writes to it.*

*Companion to Scheduler & Worker Process design (next up). This doc is the storage layer; that doc is the invocation layer.*

---

## Purpose

Autonomous work needs a queue. Without one: either (a) she works on nothing, (b) she works on whatever the last person told her, overwriting everything, or (c) scheduling becomes implicit — entangled with adapter code and hard to reason about.

The task queue is a persistent, queryable, prioritized list of things she should do when she has autonomous time. It's written to by three sources: Lyle (via chat or admin), the entity herself (via `add_task`), and the scheduler (system-generated for recurring work — day-one, these are added manually too).

Responsibilities:

- Store tasks persistently across worker restarts.
- Support priority-ordered consumption by the scheduler.
- Track task lifecycle from creation through completion or abandonment.
- Carry progress context across yield/resume cycles.
- Provide the `add_task` tool path for the entity.
- Recover gracefully from crashes (in-progress tasks at startup restart-safely).

Non-goals:

- **Recurring task scheduling.** Day-one has no recurrence rules. "Daily reflection" is handled by Lyle re-adding the task when wanted, or by a scheduler-level policy that adds a reflection task once per day if none exists. Either way, not a task queue feature.
- **Task dependencies.** No "task B is blocked on task A." Linear queue. Add if needed later.
- **Task categorization / tagging.** No categories field. Description captures everything.
- **Task assignment (multiple workers).** Single worker day-one. No "claimed by worker X" field.
- **Concurrency primitives across processes.** All task queue access happens within the one worker process; no cross-process locking needed.

---

## Summary of decisions

1. **Single `tasks` table in working.db.** Schema additions go to v1.4 alongside `web_sessions` and the documents `note` column.
2. **Status state machine: `pending → in_progress → (completed | pending | abandoned)`.** A yielded task returns to `pending` with an updated `progress_note`. A completed task is terminal. An abandoned task (iteration limit, unrecoverable error, explicit admin action) is terminal.
3. **Priority is a signed integer.** Higher is more important. Day-one defaults: user=10, self=5, scheduled=3. Not enforced — callers can write any integer.
4. **Tie-break on `created_at`** (older first). FIFO within a priority band.
5. **`add_task` tool creates pending tasks with `source="self"` and default priority 5.** The entity can override priority via tool argument.
6. **Crash recovery: startup resets `in_progress` tasks to `pending`** with a progress_note appended. The scheduler picks up again fresh.
7. **`chunked` flag** tracks whether the autonomous session that ran on this task has been close-chunked. Default 0; set to 1 on successful `close_autonomous_session`.
8. **Lyle's chat-initiated tasks write via admin CLI or a separate chat-adapter path**, not via `add_task` (which is the entity's tool). Keeps provenance clean via the `source` field.

---

## Table schema

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    source TEXT NOT NULL,              -- 'user' | 'self' | 'scheduled'
    priority INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'in_progress' | 'completed' | 'abandoned'
    progress_note TEXT,                -- free-text context for resumption / final reason
    chunked INTEGER NOT NULL DEFAULT 0,  -- 0 until close_autonomous_session succeeds
    created_at TEXT NOT NULL,
    started_at TEXT,                   -- null until scheduler picks it up the first time
    completed_at TEXT,                 -- null until status is terminal
    created_by_user_id TEXT,           -- who created it, null for source='self' and 'scheduled'
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE INDEX idx_tasks_status_priority ON tasks(status, priority DESC, created_at);
CREATE INDEX idx_tasks_source ON tasks(source);
CREATE INDEX idx_tasks_chunked ON tasks(status, chunked) WHERE status = 'completed' OR status = 'abandoned';
```

### Field notes

- **`id`** — UUID string.
- **`description`** — what to do, in Lyle's words, her own words, or the scheduler's template. Plain text; can be long.
- **`source`** — enum of three strings. Used for priority defaulting, audit trail, and analytics.
- **`priority`** — signed int; higher wins. Callers may write any value. Defaults exist for each source.
- **`status`** — enum of four strings. See state machine below.
- **`progress_note`** — updated on yield with a continuation context; updated on completion/abandonment with a final note. Accumulates via append — each yield adds a timestamp-prefixed line so the full history of the task's yield/resume cycles is preserved. Per Principle 6 (never delete, only layer).
- **`chunked`** — 0 or 1. Reserved by Autonomous Chunking Design v1. Set to 1 by `close_autonomous_session` after rechunking succeeds.
- **`created_at`** — ISO 8601 UTC.
- **`started_at`** — ISO 8601 UTC, when the scheduler first moved this to `in_progress`. Stays set across yield/resume (first start wins).
- **`completed_at`** — ISO 8601 UTC, when status transitioned to `completed` or `abandoned`.
- **`created_by_user_id`** — for `source='user'`, the user whose chat triggered the task (or whose admin action added it). NULL for self and scheduled.

### Why `status, priority DESC, created_at` as the primary index

The hot query is "give me the next task to work on":

```sql
SELECT * FROM tasks
WHERE status = 'pending'
ORDER BY priority DESC, created_at ASC
LIMIT 1;
```

The index supports this directly — status filter + priority ordering + created_at tiebreak, all in one index scan. No sort in memory.

### Why the `chunked` partial index

Queries like "which completed tasks need chunking cleanup" use `WHERE status IN ('completed', 'abandoned') AND chunked = 0`. The partial index makes this fast and small — only terminal-status rows are indexed.

---

## State machine

```
          ┌─────────┐
          │ pending │◄────────────────┐
          └────┬────┘                 │
               │                      │ yield (agent loop yielded)
               │ scheduler picks up   │ — progress_note updated
               ▼                      │
         ┌──────────────┐             │
         │ in_progress  ├─────────────┘
         └───┬───────┬──┘
             │       │
 complete    │       │ abandon
 (loop done) │       │ (iteration limit, error, admin action)
             ▼       ▼
     ┌────────────┐ ┌────────────┐
     │ completed  │ │ abandoned  │
     └────────────┘ └────────────┘
     (terminal)     (terminal)
```

Transitions are owned by specific code:

- **pending → in_progress:** Scheduler's task-pickup code. Sets `started_at` if null; updates `status`; returns the row.
- **in_progress → completed:** `close_autonomous_session` on natural agent-loop termination. Sets `status='completed'`, `completed_at=now()`, updates `progress_note` with a final summary or leaves as-is.
- **in_progress → pending (yield):** `close_autonomous_session` on yield-triggered termination. Sets `status='pending'`, leaves `started_at` intact, updates `progress_note` to the yield context. Does NOT touch `completed_at`.
- **in_progress → abandoned:** `close_autonomous_session` on iteration_limit or unhandled error. Sets `status='abandoned'`, `completed_at=now()`, progress_note with the reason.
- **pending → abandoned:** Admin action only. Never automatic.
- **completed | abandoned → anything:** Impossible. Terminal states. If Lyle wants to retry a completed task, he creates a new task.

---

## `add_task` tool

The entity's day-one self-directed task path.

### Arguments

```yaml
arguments:
  type: object
  properties:
    description:
      type: string
      description: The task to queue for autonomous work later.
    priority:
      type: integer
      description: How important this is. Higher is more important. Default 5.
      default: 5
  required: [description]
```

### Behavior

```python
def run(args: dict, context: ToolContext) -> ToolResult:
    task_id = str(uuid.uuid4())
    description = args["description"].strip()
    priority = args.get("priority", 5)
    
    if not description:
        return ToolResult(
            success=False,
            rendered="I need a description for the task.",
            structured={"error": "empty_description"},
        )
    
    with connections.open_working(context.working_db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (id, description, source, priority, status, "
            "created_at) VALUES (?, ?, 'self', ?, 'pending', ?)",
            (task_id, description, priority, iso_now()),
        )
    
    return ToolResult(
        success=True,
        rendered=(
            f"Queued task (priority {priority}): {description[:100]}"
            + ("..." if len(description) > 100 else "")
        ),
        structured={"task_id": task_id, "priority": priority},
    )
```

No user_id attached (`created_by_user_id` is NULL); source is `'self'`.

The tool does not WAKE the scheduler. The next scheduler tick picks it up naturally. Day-one has no "run this task immediately" semantics from inside the agent loop — scheduler timing is deterministic per its own design.

### Fabrication pattern

Per Tool Framework v1's fabrication detection: if her output says "I've added a task" without an `add_task` call in the tool trace, that's fabrication. Pattern string in the skill's frontmatter:

```yaml
fabrication_patterns:
  - "added a task"
  - "queued a task"
  - "added to my todo"
  - "I'll remember to"
```

(The last one is a stretch — "I'll remember to think about X later" may or may not imply task-creation. Test in practice; remove if it produces false positives.)

---

## Who writes tasks

### Lyle via chat

Not through `add_task`. When Lyle says "add a task to research X" to the entity, the entity may interpret that as either "call add_task" (but that attributes the task to her) or as "Lyle is giving me a task" (attribute to him).

**Decision: entity's judgment.** If she calls `add_task` from a conversation, the task is `source='self'` — she decided to queue it. If Lyle wanted a `source='user'` task, he'd use the admin CLI. This keeps the source field semantically clean: it reflects who DECIDED to queue the task, not who originated the idea.

If in practice Lyle's natural language tasks all end up as `source='self'`, we lose the provenance distinction. If that matters, add an alternative path. Day-one trusts her judgment.

### Lyle via admin CLI

The CLI has a `tir admin task add --description "..." --priority 10` command. Writes with `source='user'` and `created_by_user_id=<lyle's id>`.

### The entity via `add_task`

Covered above.

### The scheduler (scheduled/recurring)

Day-one: no automatic recurring. Lyle can configure the scheduler to add a task once at startup (e.g., "daily reflection" on first-of-day startup) — scheduler-level logic, writes with `source='scheduled'`.

If/when recurrence arrives, a `scheduled_tasks` table with cron-style rules, periodically materialized into the tasks queue. Not v1.

---

## Scheduler interaction

The scheduler owns task pickup logic (Scheduler & Worker Process design covers timing). When it's time to start a task:

```python
def claim_next_task(working_path: str) -> dict | None:
    """Atomically move the next pending task to in_progress."""
    with connections.open_working(working_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, description, source, priority, progress_note, "
            "  started_at, created_at "
            "FROM tasks "
            "WHERE status = 'pending' "
            "ORDER BY priority DESC, created_at ASC "
            "LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return None
        started = row["started_at"] or iso_now()
        conn.execute(
            "UPDATE tasks SET status = 'in_progress', started_at = ? "
            "WHERE id = ?",
            (started, row["id"]),
        )
        conn.execute("COMMIT")
        return dict(row) | {"started_at": started}
```

`BEGIN IMMEDIATE` grabs a write lock immediately — serializes with any concurrent readers. Single-worker, so contention is minimal; the transaction is belt-and-braces.

If the call returns None, no pending tasks — scheduler waits for its next tick.

---

## Close (post-session) writeback

When `close_autonomous_session(task_id, session_trace, final_status, yield_context)` runs:

```python
if final_status == "completed":
    status = "completed"
    completed_at = iso_now()
    progress_note = None  # or a generated "completed naturally" note
elif final_status == "yielded":
    status = "pending"
    completed_at = None
    progress_note = (existing_progress_note or "") + f"\n[{iso_now()}] {yield_context}"
elif final_status == "iteration_limit":
    status = "abandoned"
    completed_at = iso_now()
    progress_note = "Hit iteration limit before completion."
elif final_status == "error":
    status = "abandoned"
    completed_at = iso_now()
    progress_note = f"Abandoned due to error: {error_message}"

with connections.open_working(working_path) as conn:
    conn.execute(
        "UPDATE tasks "
        "SET status = ?, completed_at = ?, progress_note = ?, chunked = ? "
        "WHERE id = ?",
        (status, completed_at, progress_note, 1 if chunking_succeeded else 0, task_id),
    )
```

The `chunked=1` flag is set to 1 only if the chunking step succeeded. Separate transactions for chunks_fts/ChromaDB writes vs. task status update — per Autonomous Chunking design, chunking failures are tolerable and retriable; task status update is fire-and-forget.

---

## Crash recovery on startup

At worker startup, before the scheduler starts ticking:

```python
def startup_task_recovery(working_path: str) -> int:
    """Reset any in_progress tasks back to pending.
    
    A task in 'in_progress' at startup means the worker was killed mid-session.
    The session trace was in memory and is lost; reset so the next scheduled
    run picks the task up fresh.
    
    Returns the number of tasks recovered.
    """
    with connections.open_working(working_path) as conn:
        cursor = conn.execute(
            "UPDATE tasks "
            "SET status = 'pending', "
            "    progress_note = COALESCE(progress_note, '') || "
            "                    '\n[Previous run interrupted by worker restart.]' "
            "WHERE status = 'in_progress'"
        )
        return cursor.rowcount
```

Log the count. Each recovered task's progress_note has the interruption annotation, so the entity has context when she resumes.

Runs once at startup. Symmetric with conversation close recovery (per Autonomous Window v1.1).

---

## Conversation ↔ task integration

### Tasks don't become conversations

A task runs as an autonomous session, not a conversation. No conversations row, no user_id, no messages table entries. The session's activity trace lives in memory during the session and is chunked per Autonomous Chunking design.

### Conversations don't automatically become tasks

If Lyle says "research X" in chat, the entity decides whether to `add_task` in response. She might answer inline (quick question — just answer), or queue it (needs time — add_task + respond "Queued that; I'll work on it later"). Her judgment.

### The `memory_search` overlap

If she's working autonomously on a task and calls `memory_search`, chunks from prior conversations AND prior autonomous sessions surface together. Tasks and conversations share the retrieval substrate. She doesn't distinguish "I learned this in chat" from "I learned this while working alone" unless she wants to (the source_type metadata is there if CC v1.1 frames it distinctively, which it does).

---

## Lifecycle examples

### Simple: user adds task, scheduler runs it, completes

1. Lyle: `tir admin task add --description "Read the Foo 2024 paper" --priority 10` → task inserted, status=pending.
2. Scheduler tick: picks it up (only pending task; highest priority wins) → status=in_progress, started_at=T1.
3. Agent loop runs: web_fetch, document_ingest, reflection. No tool calls on iteration 5 → loop terminates.
4. `close_autonomous_session(task_id, ..., "completed", None)` → status=completed, completed_at=T2, progress_note=None, chunked=1.

### Yield and resume

1. Self-added task: "Look into emergent behavior" (priority 5, source=self).
2. Scheduler starts it. 20 minutes in, Lyle sends a chat message.
3. Agent loop's yield_check returns True after the next tool call. Loop exits; yield_context returned = "Was fetching paper about multi-agent emergence; need to continue reading."
4. `close_autonomous_session(task_id, ..., "yielded", "Was fetching paper...")` → status=pending, completed_at=None, progress_note=yield_context, chunked=1 (session chunks persisted).
5. Chat turn runs.
6. Next scheduler tick, same task pulls again (highest priority pending). in_progress set (started_at UNCHANGED from step 2). Agent loop gets the progress_note as part of its context.
7. Continues. Eventually completes normally.

### Crash mid-session

1. Task in_progress. Worker killed (crash, reboot).
2. Startup: startup_task_recovery resets status to pending, appends `[Previous run interrupted by worker restart.]` to progress_note.
3. Scheduler picks up fresh. Agent loop has the progress_note context; any chunks from the interrupted session are in ChromaDB already (if iteration >= 5 fired a live chunk); task's session starts over from current task description + accumulated progress_note.

This is a bit wasteful (interrupted work partially redone) but correct. For day-one, acceptable.

---

## Priority guidance

The integer is signed and any value is allowed. Meaningful ranges:

- **10+:** user-critical. Lyle explicitly elevated. Rare.
- **5–9:** normal. Most tasks live here.
- **1–4:** background. "When you have nothing else to do."
- **0 or negative:** deferred indefinitely. Will never run if higher-priority tasks keep arriving. Functional equivalent of "abandoned but not marked."

The scheduler doesn't know these ranges — it just picks highest. These are conventions for humans reading / writing tasks.

The entity's `add_task` defaults to 5. She can pass higher or lower. Principle 15: no hard rule about when she should use which.

---

## Admin operations

Via CLI:

- `tir admin task list [--status=pending] [--source=user|self|scheduled] [--limit=N]` — list tasks with filters.
- `tir admin task add --description "..." [--priority N] [--user <n>]` — insert a task.
- `tir admin task abandon --id <task_id> [--reason "..."]` — mark as abandoned with a reason in progress_note.
- `tir admin task show --id <task_id>` — full task details including progress_note.
- `tir admin task clear --status=completed [--older-than 30d]` — bulk delete completed tasks. (Admin operation; deletion is possible because tasks are not archive-grade — they're operational state, not experience. See Principle 5 for what IS archive-grade.)

The CLI operates on working.db directly. No special API needed.

---

## What this design does NOT decide

- **When the scheduler ticks.** Scheduler & Worker Process design.
- **Whether multiple autonomous sessions can run concurrently.** Scheduler design will settle this (day-one is one at a time).
- **Recurring task mechanics.** Deferred.
- **The admin CLI's exact structure.** Minimal set sketched here; detailed shape is implementation.
- **Task templates / presets.** No "task types" day-one. Every task is free-form description.
- **Task notifications to the entity when added.** Day-one: she discovers tasks when she looks at her queue or when the scheduler starts one. No push.
- **Estimated duration / deadlines.** No fields for "expected to take X hours" or "deadline Y." Priority + FIFO covers the common case.
- **Task-internal progress tracking beyond progress_note.** progress_note is free text; no structured fields.

---

## Open questions

**a. Progress_note accumulation vs. replacement.** CLOSED. Append with timestamps. Replacing on yield loses earlier context, violating Principle 6 (never delete, only layer). On each yield, the caller appends a timestamp-prefixed line to progress_note rather than replacing it. The field grows into a small log of the task's history across yield/resume cycles. No schema change — same text field, caller-side behavior only.

**b. `started_at` on first vs. every in_progress.** Current design: first pickup sets `started_at`, subsequent pickups (after yields) don't update it. "When did this task first begin." Alternative: every pickup updates; a `last_resumed_at` field captures the most recent start. Day-one keeps it simple.

**c. Priority inversion / starvation.** If high-priority tasks keep arriving, low-priority tasks never run. Day-one: accepted. If real starvation becomes an issue, add an aging mechanism (older pending tasks get priority boosts over time). Not now.

**d. Task-initiated conversation.** If during an autonomous task the entity decides she needs Lyle's input, she has no mechanism to "pause the task and ask." Day-one: she just adds a note to progress_note, yields, and finishes without asking. When Lyle next chats, she may bring it up. Not ideal; flag for future proactive-messaging design.

**e. Soft delete vs. hard delete.** `tir admin task clear` hard-deletes. If in the future we want tasks to be recoverable, add a `deleted_at` column for soft delete. For now, hard delete is fine — completed tasks are operational state, not experience, and their autonomous session chunks persist in ChromaDB regardless.

**f. Priority values encoded with meaning vs. pure ordinals.** If "priority 7" starts meaning something specific (e.g., "urgent," "maintenance," "aspirational"), we'd want named priorities. Day-one is pure ordinals. Watch behavior.

**g. Whether `source='user'` tasks should be visible to the entity in a specific way.** "Lyle explicitly asked for this" might deserve different framing than "I added this to myself" when she reads her queue. Currently, she sees the description + progress_note; the source is present in metadata but not necessarily prominent. If context construction should include source framing when rendering task context, flag for CC v1.2.

---

## Cross-references

- **Autonomous Window Design v1.1** — the queue's semantic shape (fields, lifecycle) originates here; this doc formalizes.
- **Autonomous Chunking Design v1** — owns the `chunked` flag's lifecycle; this doc reserves it.
- **Scheduler & Worker Process Design** — consumes this queue.
- **Tool Framework v1** — `add_task` is a day-one tool; this doc specifies its behavior.
- **Skill Registry & Dispatch Design v1** — `add_task`'s SKILL.md follows that pattern.
- **User Model Design v1.1** — `created_by_user_id` foreign-keys `users(id)`; user creation is independent.
- **Schema Design v1.4** — tasks table belongs in schema v1.4 alongside web_sessions and documents.note.
- **Guiding Principles v1.1** — Principle 3 (tasks are operational state, not experience — deletable, unlike conversations), Principle 5 (what IS archive-grade lives in archive.db; tasks live in working.db for this reason), Principle 15 (priority conventions are norms, not enforced rules; entity decides).

---

*Project Tír Task Queue Design · v1.1 · April 2026*
