# Project Tír — Scheduler & Worker Process Design

*Design doc v1, April 2026. The top-level process shape. How the worker starts up, how the scheduler decides when to start autonomous work, how the yield signal coordinates between chat and autonomous sessions, how shutdown is handled. This is the outermost layer — everything below it runs inside this process.*

*Final design doc in the day-one architecture set.*

---

## Purpose

Something has to run. This doc decides what that "something" is.

Per Web Adapter v1: the worker process, the scheduler, and the Flask adapter all live in a single Python process. This doc specifies that process's shape: what runs on which thread, what gets initialized when, how autonomous work gets scheduled, how chat and autonomous work coordinate, and how the whole thing shuts down cleanly.

Responsibilities this doc owns:

- The startup sequence (order of initialization).
- The scheduler loop (when to start autonomous tasks, how to pick them).
- The yield signal mechanism (how chat interrupts autonomous work mid-session).
- Thread architecture (main thread + scheduler thread).
- Shutdown behavior (clean stop, in-flight work).
- The top-level `worker.py` or similar entry point.

Non-goals:

- What the scheduler's policy *should* be in nuanced cases. Day-one policy is simple; tuning is a later pass.
- Multi-process deployment. Single process day-one.
- Hot-reload. Restart-to-update.
- Horizontal scaling. One M4. One worker.
- Operating-system service integration (launchd, systemd). Ad-hoc launch via script or CLI; scale if needed.

---

## Summary of decisions

1. **Single Python process.** The Flask web adapter, the scheduler, and the autonomous engine all run in-process.
2. **Two threads of interest: main + scheduler.** Main runs Flask (which internally uses its own thread pool for requests). Scheduler runs as a single background daemon thread, looping on a sleep interval.
3. **Startup sequence is deterministic and idempotent.** Same order every time. Fails fast on corrupted state.
4. **Scheduler ticks every 30 seconds.** On each tick: if idle and a pending task exists, start an autonomous session.
5. **Idle threshold: 60 seconds since last chat activity.** Tunable.
6. **Engine lock serializes all model calls.** Chat and autonomous both acquire. Autonomous holds it for an entire session; chat holds it for a turn; yield signal lets autonomous release mid-session.
7. **Yield signal is a `threading.Event`.** Set by the web adapter when a chat message arrives; checked by the agent loop between iterations; cleared by the scheduler after autonomous releases the lock.
8. **Shutdown is signal-driven.** SIGINT / SIGTERM triggers a graceful stop: drain in-flight turns, tell the scheduler to exit after its current session, close databases.
9. **No autonomous work during startup recovery.** Scheduler thread doesn't start until startup recovery is complete.
10. **No autonomous work scheduling policies beyond "when idle, work on highest priority".** No time-of-day rules, no daily quotas, no minimum/maximum session length. If those become needed, add later. Day-one keeps it simple.

---

## Process architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  worker.py main process                     │
│                                                             │
│  ┌─────────────────────┐      ┌──────────────────────────┐  │
│  │   Main thread       │      │   Scheduler thread       │  │
│  │                     │      │   (daemon, background)   │  │
│  │   Flask server      │      │                          │  │
│  │     ├─ request      │      │   while not stop:        │  │
│  │     │   pool (N     │      │     sleep(30)            │  │
│  │     │   threads)    │      │     tick()               │  │
│  │                     │      │                          │  │
│  └─────────────────────┘      └──────────────────────────┘  │
│                                                             │
│  Shared state:                                              │
│    - engine_lock (threading.Lock)                           │
│    - yield_signal (threading.Event)                         │
│    - last_chat_activity (timestamp, lock-guarded)           │
│    - registry (read-only after startup)                     │
│    - config (read-only after startup)                       │
│                                                             │
│  Shared I/O:                                                │
│    - working.db (SQLite WAL mode)                           │
│    - archive.db (SQLite WAL mode)                           │
│    - ChromaDB (thread-safe via client)                      │
│    - Ollama (HTTP; safe from any thread)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Flask's default server spawns worker threads to handle concurrent requests. Per Web Adapter v1, all engine invocations serialize on the engine lock — so multiple simultaneous chat POSTs queue on that lock. The scheduler thread competes for the same lock when starting autonomous work.

SQLite WAL mode handles concurrent reads from all threads and serializes writes. ChromaDB's Python client is thread-safe (per its docs; day-one trust and verify). Ollama is HTTP; safe by construction.

### Why daemon thread for the scheduler

Daemon threads die when the main thread exits. Flask's shutdown (on SIGINT) ends the main thread; the scheduler thread dies automatically. Simpler than coordinating explicit stop. We still send a stop signal for graceful shutdown behavior (drain current session), but the daemon flag is the backstop.

### Why not asyncio

The codebase is synchronous throughout (memory layer, engine, tools). Introducing asyncio for the top layer only adds complexity without removing any blocking work — model calls, SQLite, chunking are all synchronous at their roots. Flask with threads is simpler and adequate.

If async shape ever earns its place (streaming responses, long-lived WebSocket connections, etc.), reconsider. Day-one: threads.

---

## Startup sequence

From `python -m tir.worker` or equivalent entry point:

```python
def main():
    # 1. Load config
    config = EngineConfig.load(config_path=os.environ.get("TIR_CONFIG", "./config.toml"))
    setup_logging(config)
    
    logger.info("Starting Tir worker, pid=%d", os.getpid())
    
    # 2. Initialize databases (idempotent)
    #    Creates archive.db, working.db, and all tables if not present.
    #    Verifies schema matches expected; raises if corrupted.
    create_databases(config.archive_path, config.working_path)
    
    # 3. Initialize ChromaDB collection (idempotent)
    #    Creates the collection if not present; returns a handle.
    chroma.init_collection(config.chromadb_path, ollama_host=config.ollama_host)
    
    # 4. Verify chunks_fts is present
    #    Created by create_databases; this is a paranoia check.
    chunks_fts.init_fts(config.working_path)
    
    # 5. Conversation startup recovery
    #    Closes any open conversations from prior run, rechunking and
    #    marking ended_at. See Autonomous Window v1.1.
    closed_count = conversations.startup_recovery(
        config.working_path,
        config.archive_path,
        config.chromadb_path,
        ollama_host=config.ollama_host,
    )
    logger.info("Closed %d open conversations on startup", closed_count)
    
    # 6. Task queue startup recovery
    #    Resets any in_progress tasks to pending.
    recovered_task_count = startup_task_recovery(config.working_path)
    logger.info("Reset %d in_progress tasks to pending", recovered_task_count)
    
    # 7. Build skill registry
    #    Scans skills/active/, loads all skills, builds tool definitions.
    registry = Registry.build(skills_root_path=config.skills_root_path)
    logger.info("Loaded %d skills", len(registry.list_tools()))
    
    # 8. Build shared coordination state
    shared = SharedState(
        engine_lock=threading.Lock(),
        yield_signal=threading.Event(),
        last_chat_activity=AtomicTimestamp(),
        stop_event=threading.Event(),
    )
    
    # 9. Start the scheduler thread
    scheduler_thread = threading.Thread(
        target=scheduler_loop,
        args=(config, registry, shared),
        daemon=True,
        name="scheduler",
    )
    scheduler_thread.start()
    logger.info("Scheduler thread started")
    
    # 10. Install signal handlers
    install_signal_handlers(shared)
    
    # 11. Build and run Flask
    app = create_flask_app(config, registry, shared)
    logger.info("Starting web server on %s:%d", config.web_host, config.web_port)
    app.run(host=config.web_host, port=config.web_port, threaded=True)
    
    # 12. On Flask exit (signal received): signal scheduler to stop, join
    logger.info("Main thread exiting; signaling scheduler")
    shared.stop_event.set()
    scheduler_thread.join(timeout=60)
    logger.info("Worker shut down")
```

### Ordering rationale

- **Config first.** Everything else depends on it.
- **Databases before anything that touches them.** Bootstrap creates; nothing runs before the schema is verified.
- **Conversation recovery before task recovery.** Both are independent but conversations are the more safety-critical archive path; errors there should surface first.
- **Registry before scheduler thread.** Scheduler needs the registry to dispatch tools.
- **Scheduler before Flask.** Could go either way — both are in their own threads. Putting scheduler first ensures its first tick can happen immediately; Flask doesn't need the scheduler to serve requests (chat works without autonomous), so the reverse order also works. Minor; current order reads naturally.
- **Signal handlers last before run.** Installed after all state is set up so the handler doesn't fire into a partially-initialized world.

### Failure during startup

Any exception raised by steps 2–7 is fatal. Log with full traceback, exit with nonzero status. Something is wrong; re-running will either fix it (transient condition) or surface the same error (which needs investigation).

---

## Scheduler loop

```python
def scheduler_loop(config: EngineConfig, registry: Registry, shared: SharedState) -> None:
    """Background thread. Periodically check whether to start autonomous work."""
    tick_interval = config.scheduler_tick_seconds  # default 30
    idle_threshold = config.idle_threshold_seconds  # default 60
    
    while not shared.stop_event.is_set():
        # Sleep in short increments so stop_event is responsive
        for _ in range(tick_interval):
            if shared.stop_event.is_set():
                return
            time.sleep(1)
        
        try:
            tick(config, registry, shared, idle_threshold)
        except Exception:
            logger.exception("Scheduler tick raised; continuing")


def tick(
    config: EngineConfig,
    registry: Registry,
    shared: SharedState,
    idle_threshold: int,
) -> None:
    """One scheduler tick. Check conditions; start a task if appropriate."""
    # Already yielding? A chat is trying to run; don't start new work.
    if shared.yield_signal.is_set():
        return
    
    # Chat activity recent? Don't start.
    idle_seconds = shared.last_chat_activity.seconds_since()
    if idle_seconds < idle_threshold:
        return
    
    # Try to claim a task. Atomic SQL transaction.
    task = claim_next_task(config.working_path)
    if task is None:
        return
    
    logger.info("Scheduler starting task %s (priority %d)", task["id"], task["priority"])
    
    # Acquire engine lock. May wait briefly if a chat is between "set signal"
    # and "acquire lock"; low contention in practice.
    with shared.engine_lock:
        # Chat may have arrived between claim and lock acquisition.
        # If yield_signal is set, we need to re-queue this task and not run.
        if shared.yield_signal.is_set():
            logger.info("Chat arrived mid-claim; re-queueing task %s", task["id"])
            requeue_task(config.working_path, task["id"])
            return
        
        # Clear yield signal for this session (fresh start)
        shared.yield_signal.clear()
        
        # Build tool context for the session (no user, no conversation)
        tool_context = ToolContext(
            user_id=None,
            conversation_id=None,
            workspace_path=config.workspace_path,
            working_db_path=config.working_path,
            chromadb_path=config.chromadb_path,
            ollama_host=config.ollama_host,
            logger=logger,
        )
        
        # Run the session
        task_obj = Task.from_row(task)
        yield_check = lambda: shared.yield_signal.is_set()
        
        try:
            result = run_autonomous_task(
                task=task_obj,
                registry=registry,
                config=config,
                yield_check=yield_check,
            )
        except Exception as e:
            logger.exception("Autonomous task %s raised", task["id"])
            result = AutonomousTaskResult(
                status="error",
                final_content=None,
                session_trace=[],
                error_message=str(e),
            )
        
        # Close the session (rechunk, update task status)
        close_autonomous_session(
            task_id=task["id"],
            session_trace=result.session_trace,
            final_status=result.status,   # "completed" | "yielded" | "iteration_limit" | "error"
            yield_context=result.yield_context,
            config=config,
        )
        
        logger.info(
            "Task %s ended with status %s (iterations=%d)",
            task["id"],
            result.status,
            len(result.session_trace),
        )
```

### Tick timing

30-second tick balances:
- Responsiveness: a task added while idle waits at most 30 seconds + idle_threshold (60s) = 90 seconds to start.
- Overhead: SQL queries + idle check are negligible; 30-second granularity avoids hot-spinning.

### Why the `if yield_signal.is_set()` check after acquiring the lock

Race: scheduler calls `claim_next_task` (short) → tries to acquire lock → chat arrives between those two calls and sets yield_signal while the scheduler waits on the lock. Without the re-check, scheduler starts a session immediately and has to yield on the first iteration. Cleaner to requeue and let chat run first.

### Requeueing

```python
def requeue_task(working_path: str, task_id: str) -> None:
    """Reset a just-claimed task back to pending."""
    with connections.open_working(working_path) as conn:
        conn.execute(
            "UPDATE tasks SET status = 'pending' WHERE id = ? AND status = 'in_progress'",
            (task_id,),
        )
```

The started_at stays set (it was set on claim); semantically this task "almost started" but no agent loop actually ran, so it's as if we'd never claimed. Acceptable to keep started_at — it reflects "first time the scheduler thought of running this."

---

## Yield signal mechanism

### The flow

1. **Web adapter receives POST /message.** Before acquiring engine_lock: `shared.yield_signal.set()`.
2. **Web adapter acquires engine_lock.** If autonomous is running, it has the lock; web adapter blocks on `.acquire()`.
3. **Autonomous agent loop notices yield_signal.** At the start of the next iteration, `yield_check()` returns True. Loop exits with terminated_reason="yielded".
4. **Scheduler's tick call:** run_autonomous_task returns → close_autonomous_session runs → `with shared.engine_lock:` block exits → lock released.
5. **Web adapter acquires the lock.** Clears yield_signal (so future scheduler ticks can run again).
6. **Web adapter runs the chat turn.** Releases lock.
7. **Scheduler on next tick:** idle check restarts from 0 (chat activity just happened). Waits full idle_threshold. Then tries next task. If the just-yielded task is highest priority, it runs again (pending status, with progress_note from yield).

### Responsiveness target

Between chat POST arrival and chat response start: ideally < 5 seconds. Dominated by "how long does autonomous's current iteration take." If autonomous is mid-tool-call (e.g., web_fetch), the fetch completes before yield. So worst case = slowest tool's timeout (60 seconds for web_fetch).

For most tool calls (seconds, not minutes), yield is fast. For a stuck tool, user waits up to a minute. Acceptable for day-one.

### Who clears yield_signal

The web adapter, after acquiring the lock:

```python
with shared.engine_lock:
    shared.yield_signal.clear()
    # ... run chat turn ...
```

Clearing before the chat turn (not after) is important: if a second chat arrives while the first is being processed, the second's `shared.yield_signal.set()` is a no-op for the current turn (already in the lock) but remains set, blocking scheduler from starting new autonomous until the second chat clears it.

### Scheduler clearing yield_signal

Scheduler also clears it at session start (after acquiring lock, before running), so a stale signal from a long-past chat doesn't fire immediately. This is belt-and-braces — the web adapter should always clear on its own chat turn, but if anything goes wrong, the scheduler clearing at session start is a backstop.

---

## The last_chat_activity timestamp

A shared, thread-safe timestamp. Updated by the web adapter on every chat turn. Read by the scheduler to check idle duration.

Python implementation:

```python
class AtomicTimestamp:
    """Thread-safe timestamp holder."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0.0  # unix time; 0 means "never"
    
    def update(self) -> None:
        with self._lock:
            self._value = time.time()
    
    def seconds_since(self) -> float:
        with self._lock:
            if self._value == 0.0:
                return float("inf")
            return time.time() - self._value
```

The locking is overkill for reading a float — GIL makes float reads/writes atomic — but the lock makes the intent obvious and future-proofs against subtle issues.

### Initial value

At startup, `last_chat_activity.update()` is NOT called. Seconds_since returns infinity. So the first scheduler tick after startup sees "idle since forever" and starts work immediately if a pending task exists.

**Alternative:** initialize to current time at startup, imposing a grace period before first autonomous work. Day-one decision: no grace period. If Lyle wants one, set a `startup_grace_seconds` config and have the scheduler skip early ticks.

### When the web adapter updates

On every authenticated chat request (POST /message). Not on /login, /logout, or GET /. Only actual chat activity counts as "chat activity."

---

## Shutdown

### Signal handlers

```python
def install_signal_handlers(shared: SharedState) -> None:
    def handler(signum, frame):
        logger.info("Received signal %d; initiating shutdown", signum)
        shared.stop_event.set()
        # Flask will also exit on the next request cycle; belt-and-braces:
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
```

`SIGINT` (Ctrl-C) and `SIGTERM` (kill) both go through the same handler. `SIGKILL` can't be caught — if someone sends it, we lose in-flight state the same way a crash does. Startup recovery handles that case on next boot.

### Graceful shutdown flow

1. Signal received → `stop_event.set()`.
2. Flask's `app.run()` returns on the next request cycle (or immediately if handler raises KeyboardInterrupt).
3. Main thread proceeds past `app.run()` to the scheduler join.
4. Scheduler thread checks `stop_event.is_set()` in its sleep loop, returns.
5. Main thread: `scheduler_thread.join(timeout=60)`. Gives the scheduler up to a minute to finish any in-flight session.
6. Main thread exits. Daemon threads die. Process terminates.

### What about an in-flight autonomous session at shutdown

If the scheduler is mid-session when stop_event fires:

- The scheduler's tick function is inside `with engine_lock:` running an agent loop.
- The stop_event signal doesn't propagate into the agent loop directly.
- The agent loop finishes its current iteration (takes seconds to a minute).
- close_autonomous_session runs (updates task row, rechunks).
- Lock releases. Tick returns.
- Scheduler loop's `while not stop_event.is_set()` exits.

Total shutdown time: up to ~ the longest tool call (60s for web_fetch) + chunking time (fast). The 60-second join timeout is generous.

### What if the join times out

Some tool is genuinely stuck. Process exits with the daemon thread killed mid-session. Task row may be in `in_progress` state. Startup task recovery on next boot handles it (resets to pending). In-memory session trace is lost; no chunks written for that session after the last live chunk fired. Acceptable failure mode.

### What about in-flight chat turns at shutdown

Flask's request handling is synchronous per request. A chat turn in progress when shutdown fires completes normally (the request handler returns a response before Flask's next accept loop iteration notices the stop). Edge case: if the chat is blocked waiting for the engine lock (behind an autonomous session), it may time out from the user's perspective but the chat turn itself hasn't started. On next startup, the user just re-sends.

---

## Configuration

Extends EngineConfig:

```python
@dataclass
class EngineConfig:
    # ... existing fields from Conversation Engine Design v1 ...
    
    # Web adapter
    web_host: str = "127.0.0.1"
    web_port: int = 5050
    session_cookie_name: str = "tir_session"
    session_ttl_days: int = 30
    resume_conversation_hours: int = 24
    
    # Scheduler
    scheduler_tick_seconds: int = 30
    idle_threshold_seconds: int = 60
    
    # Skills
    skills_root_path: str = "./skills/"
```

All read from a config file (`config.toml` or similar) at startup. No runtime mutation.

### Configuration file layout

TOML example:

```toml
[paths]
archive = "./data/archive.db"
working = "./data/working.db"
chromadb = "./data/chromadb/"
workspace = "./data/workspace/"
skills_root = "./skills/"
system_prompt = "./soul.md"

[model]
ollama_host = "http://localhost:11434"
name = "gemma4"

[web]
host = "127.0.0.1"
port = 5050
session_ttl_days = 30
resume_conversation_hours = 24

[scheduler]
tick_seconds = 30
idle_threshold_seconds = 60

[limits]
conversation_iteration_limit = 5
autonomous_iteration_limit = 50
```

---

## Startup output / logging

First 20-ish lines of startup log (representative):

```
[INFO] Starting Tir worker, pid=12345
[INFO] Loaded config from ./config.toml
[INFO] Creating/verifying databases at ./data/archive.db, ./data/working.db
[INFO] Schema verified: archive.db (2 tables), working.db (9 tables, 1 FTS5 vtable)
[INFO] ChromaDB collection 'tir_memory' ready at ./data/chromadb/
[INFO] chunks_fts verified
[INFO] Conversation startup recovery: closed 0 open conversations
[INFO] Task startup recovery: reset 0 in_progress tasks to pending
[INFO] Skill registry: loaded 9 skills (web_search, web_fetch, document_ingest, ...)
[INFO] Scheduler thread started (tick=30s, idle_threshold=60s)
[INFO] Signal handlers installed (SIGINT, SIGTERM)
[INFO] Starting web server on 127.0.0.1:5050
 * Serving Flask app 'tir.web'
 * Debug mode: off
```

Clean, informative, diagnostic. Errors abort with a full traceback.

---

## What this design does NOT decide

- **Auto-scaling to multiple workers.** Single worker. If scaling is ever needed, the queue table already supports atomic task claim; multi-worker is a natural extension. Not now.
- **Cross-node coordination.** One node. No distributed locking.
- **Time-window constraints on autonomous work.** ("Only between midnight and 6 AM," "only on weekends.") Config-level extension; scheduler could check cron-style rules before starting. Flagged as open question.
- **Rate limiting on autonomous task starts.** Currently, back-to-back autonomous sessions can chain with one 30-second gap between. If autonomous work should have cooldowns, add a field. Day-one is "as fast as the scheduler ticks."
- **Priorities between different users' chats.** All chats go through the engine lock first-come-first-served. If Lyle wants his chats prioritized over other users', that's a future concern (multi-user isn't really live yet).
- **Autonomous session timeout beyond iteration limit.** A 50-iteration session could take an hour if every iteration involves a slow tool call. Nothing caps wall-clock time. If needed, add a watchdog that triggers yield after N minutes. Not day-one.
- **Observability / metrics.** No Prometheus, no OpenTelemetry. Logs are the observability surface. If the project grows, instrumentation is straightforward.

---

## Failure modes

### Scheduler thread dies unexpectedly

The `try/except` around `tick()` catches most exceptions and continues. An exception in the outer loop (e.g., `time.sleep` error — vanishingly rare) would kill the thread. Main thread doesn't notice immediately.

**Mitigation:** day-one, accept it. The loop's `try/except` already covers realistic failure modes. If thread-death-detection matters later, add a watchdog.

### Engine lock held forever

If the agent loop hangs (a stuck thread inside a skill), the lock is never released. All future chat requests block indefinitely. Scheduler ticks can't acquire lock either.

**Mitigation:** tools have per-call timeouts (60s default). If a tool somehow bypasses that (uses a C library that doesn't honor Python's signal-based timeout), the system becomes unresponsive.

Day-one: acceptable risk. Lyle sees the process unresponsive; kills and restarts. Startup recovery handles it. If it becomes common, add a hard watchdog.

### Clock skew during idle calculation

`time.time()` can go backwards (NTP adjustment). `seconds_since()` could return a negative value.

**Mitigation:** `max(0, time.time() - self._value)` in `seconds_since`. Trivially added.

### Database corruption mid-run

If working.db or archive.db becomes inconsistent mid-session:

- SQLite integrity error raised on next operation.
- Engine call fails.
- For chat: returns error response to user.
- For autonomous: close_autonomous_session may partially succeed (task row updated) or fail (task stuck in in_progress); startup recovery on next boot fixes it.

Unrecoverable corruption is outside day-one's fault-tolerance scope. If archive.db is corrupt, the entity's history is damaged — that's the worst possible outcome, and the dual-write pattern is meant to minimize its likelihood. Corrupted working.db is rebuildable from archive.db + ChromaDB via future maintenance tools.

---

## Open questions

**a. Time-of-day constraints.** If Lyle wants "autonomous work only between 22:00 and 06:00," scheduler tick needs to check wall-clock time. Simple addition (a `config.autonomous_hours` window check). Not day-one; flagged.

**b. Idle threshold tuning.** 60 seconds is arbitrary. Too short: scheduler restarts autonomous almost immediately after a chat ends, interrupting Lyle's next message. Too long: autonomous work rarely happens during active days. Watch behavior.

**c. Scheduler starvation under chat load.** If Lyle chats constantly with < 60s gaps, autonomous never runs. Task queue grows. Current design accepts this — if he's chatting, he's engaged; autonomous can wait. If the backlog becomes a problem, add a "max pending tasks before forcing an autonomous window" policy. Not now.

**d. Graceful restart vs. full shutdown.** If Lyle wants to deploy config changes without losing state, a SIGHUP-style "reload" could re-read config without stopping the process. Day-one: restart the process. Config changes are rare.

**e. Separate scheduler process for isolation.** If a bug in the scheduler kills the worker, Flask dies too. Running scheduler in a separate process (sharing dbs via their file paths) is more isolated but requires IPC for lock/signal/timestamp sharing. Day-one's single-process model is simpler and per decision 1; revisit if scheduler bugs cause actual outages.

**f. Multiple autonomous sessions in sequence.** Current tick can start one session per tick. If a session ends immediately (e.g., quick task), the scheduler waits 30 seconds for its next tick before starting the next task. Could be faster: after session end, check for next task immediately without waiting. Minor optimization; day-one accepts the 30-second gap.

**g. Health-check endpoint.** A GET /health that returns scheduler status, database connectivity, Ollama reachability. Useful for monitoring. Trivial to add later; not part of v1's minimal surface.

---

## Cross-references

- **Autonomous Window Design v1.1** — the scheduler implements the autonomous-work mechanism described there; yield signal and close pattern originate there.
- **Web Adapter Design v1** — single-process model decision and engine_lock coordination.
- **Conversation Engine Design v1** — what the scheduler and web adapter both call into.
- **Task Queue Design v1** — what the scheduler reads from and writes to.
- **Autonomous Chunking Design v1** — close_autonomous_session is called by the scheduler after each session.
- **Bootstrap Spec v1** / **Chunking Spec v1** / **BM25 Integration Spec v1** — initialization functions called during startup.
- **Skill Registry & Dispatch Design v1** — Registry.build() happens during startup.
- **User Model Design v1** — login/logout flows in Flask depend on users + channel_identifiers from this.
- **Guiding Principles v1.1** — Principle 5 (startup recovery ensures archive-grade data survives crashes), Principle 9 (scheduler and threading are infrastructure the entity never sees — she just experiences "I was working on X; now Lyle is here"), Principle 12 (simple process shape: single process, two threads, explicit coordination primitives), Principle 14 (failures surface honestly in logs rather than being papered over).

---

*Project Tír Scheduler & Worker Process Design · v1 · April 2026*
