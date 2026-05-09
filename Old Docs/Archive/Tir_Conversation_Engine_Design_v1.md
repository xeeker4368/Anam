# Project Tír — Conversation Engine Design

*Design doc v1.1, April 2026. The runtime piece that wires adapters, memory, context construction, model calls, and tool dispatch into a single flow per conversation turn. Sits between channel adapters (which speak normalized messages) and the memory + tool layers (which do the work). Also covers the autonomous-session shape — same engine, different inputs.*

---

## Purpose

Something has to take a normalized user message and turn it into a normalized assistant response. That something is the conversation engine. It's the first place in the stack where "the entity" as a unified thing exists — everything below is infrastructure, everything above is channels and presentation.

The engine's job:

- Receive a normalized message from any adapter.
- Resolve or create the conversation, persist the message.
- Build the model's context via the context construction pipeline.
- Run the agent loop (model + tools).
- Persist the assistant response.
- Return the response for the adapter to deliver.

Non-goals:

- Channel-specific logic (HTTP, iMessage, Discord — the adapter's job).
- Memory primitives (dual-write, chunking, retrieval — already specified).
- Agent loop internals (Skill Registry & Dispatch v1).
- Scheduling (Task Queue + Scheduler design).
- Admin actions (outside the runtime path).

---

## Summary of decisions

1. **The engine is a library**, not a process. A function (`handle_conversation_turn`) that takes a normalized message and returns a normalized response. The worker process invokes it; the engine doesn't own its own process.
2. **One turn per call.** No long-lived engine state. Each call stands alone — load registry from the process-level registry, open DB connections as needed, return the response.
3. **Adapter owns conversation-ID assignment.** If the adapter passes `conversation_id=None`, the engine creates a new UUID. If the adapter passes an existing ID, the engine continues that conversation. The engine does not decide "resume vs. new" — that's a channel-level policy.
4. **Engine persists in the order: user message → (build context + run loop) → assistant message.** Two separate `save_and_chunk` calls with the model work between them. Partial failures leave coherent state.
5. **Tool traces are built by the agent loop and persisted with the assistant message.** One tool_trace JSON blob per assistant message. NULL for messages with no tool use.
6. **The engine does not handle yield signals.** The agent loop inside it does. The engine itself completes its one turn start-to-finish once invoked; yielding mid-turn is an autonomous-session concern (and even there, "mid-tool-call" is the atomic unit per Autonomous Window v1.1).
7. **Autonomous sessions reuse most of the engine.** Same context construction, same agent loop. Different top-level function (`run_autonomous_task`) because the inputs and outputs differ.
8. **No retry logic at the engine level.** If the model call fails, the engine returns an error response and marks the turn failed in logs. Retries are a policy decision that belongs above the engine.

---

## Interface

```python
def handle_conversation_turn(
    normalized_message: NormalizedMessage,
    registry: Registry,
    config: EngineConfig,
) -> EngineResponse:
    """Process one turn of a conversation.
    
    Persists the user message, builds context, runs the agent loop,
    persists the assistant message, returns the response.
    
    Raises EngineError on unrecoverable failures (dual-write failure,
    etc.). Model-side failures are wrapped into an EngineResponse
    with a failed status rather than raised — the channel should
    still be able to tell the user something went wrong.
    """
```

### NormalizedMessage

Per the Autonomous Window design, plus `conversation_id`:

```python
@dataclass
class NormalizedMessage:
    channel: str             # "web", "imessage", ...
    user_id: str             # resolved UUID
    conversation_id: str | None  # None = start a new conversation
    text: str
    timestamp: str           # ISO 8601 UTC
```

### EngineResponse

```python
@dataclass
class EngineResponse:
    status: str              # "ok", "model_failed", "iteration_limit", "error"
    text: str                # what to show the user (possibly an apology for errors)
    conversation_id: str     # the conversation the message belonged to (possibly newly created)
    assistant_message_id: str | None  # None if nothing was persisted
    timestamp: str           # ISO 8601 UTC, when the response was generated
    tool_call_count: int     # how many tool calls happened in this turn (0 for simple turns)
```

### EngineConfig

```python
@dataclass
class EngineConfig:
    archive_path: str
    working_path: str
    chromadb_path: str
    workspace_path: str                # entity's scratchpad for file tools
    ollama_host: str = "http://localhost:11434"
    model_name: str = "gemma4"
    conversation_iteration_limit: int = 5
    autonomous_iteration_limit: int = 50
    system_prompt_source: str = "soul.md"  # path, resolved at config construction
```

Config is constructed once at worker startup and passed into every engine call. Not mutated during a turn.

---

## Turn flow

Step-by-step for `handle_conversation_turn`:

### Step 1: Resolve conversation

```python
conversation_id = normalized_message.conversation_id or str(uuid.uuid4())
```

If the adapter provided an ID, use it. Otherwise generate a new one. Either way, `save_message`'s `INSERT OR IGNORE INTO conversations` will create the conversations row if it doesn't exist yet.

### Step 2: Persist the user message

Build a `Message`:

```python
user_message = Message(
    id=str(uuid.uuid4()),
    conversation_id=conversation_id,
    user_id=normalized_message.user_id,
    role="user",
    content=normalized_message.text,
    timestamp=normalized_message.timestamp,
    tool_trace=None,
)
```

Call `save_and_chunk(working_path, archive_path, chromadb_path, user_message, ollama_host)`.

This writes to both databases atomically, updates `conversations.message_count`, and (being a user message) skips live chunking.

### Step 3: Build the context

Hand off to context construction:

```python
context = build_conversation_context(
    user_id=normalized_message.user_id,
    conversation_id=conversation_id,
    user_text=normalized_message.text,
    registry=registry,
    config=config,
)
```

This returns a structured object with the five context sections (seed identity, tools, retrieved memories, current situation, current conversation). Assembly details live in Context Construction v1.1; the engine just invokes it.

Internally, context construction:

1. Loads the seed identity from `config.system_prompt_source`.
2. Gets the tool definitions from the registry.
3. Calls `retrieve(...)` with `active_conversation_id=conversation_id` to exclude current-conversation chunks.
4. Builds the current-situation block (user name lookup, current time).
5. Reads all prior messages in this conversation from working.db and builds the current-conversation section.
6. Assembles everything per CC v1.1's ordering and framing.

The returned context is a dict ready for the Ollama call — `system` string, `messages` list.

### Step 4: Run the agent loop

```python
tool_context = ToolContext(
    user_id=normalized_message.user_id,
    conversation_id=conversation_id,
    workspace_path=config.workspace_path,
    working_db_path=config.working_path,
    chromadb_path=config.chromadb_path,
    ollama_host=config.ollama_host,
    logger=logger,
)

loop_result = run_agent_loop(
    system_prompt=context["system"],
    conversation=context["messages"],
    registry=registry,
    context=tool_context,
    iteration_limit=config.conversation_iteration_limit,
    yield_check=None,   # chat turns don't yield mid-turn
    ollama_host=config.ollama_host,
)
```

The loop runs until terminal (model produces content with no tool_calls), iteration limit, or yield. Chat doesn't yield, so only the first two cases matter here.

### Step 5: Determine response status

```python
if loop_result.terminated_reason == "complete":
    status = "ok"
    content = loop_result.final_content
elif loop_result.terminated_reason == "iteration_limit":
    status = "iteration_limit"
    content = (
        "I took too many steps on that and need to stop here. "
        "Let me know what you want me to focus on."
    )
else:
    # shouldn't happen in chat but handle it
    status = "error"
    content = "Something went wrong processing that message."
```

The iteration-limit fallback content is a placeholder — a behavioral directive that Principle 15 would remove eventually. For v1 it's the minimum scaffolding to keep the chat loop functional when the model can't close out its own turn. Once we watch real iteration-limit cases, we may find a better pattern.

### Step 6: Persist the assistant message

```python
assistant_message = Message(
    id=str(uuid.uuid4()),
    conversation_id=conversation_id,
    user_id=normalized_message.user_id,    # same user — the one she's talking to
    role="assistant",
    content=content,
    timestamp=iso_now(),
    tool_trace=json.dumps(loop_result.tool_trace) if loop_result.tool_trace else None,
)

save_and_chunk(
    config.working_path,
    config.archive_path,
    config.chromadb_path,
    assistant_message,
    config.ollama_host,
)
```

`save_and_chunk` dual-writes and fires `maybe_live_chunk` (since it's an assistant message). If this is the 5th (or 10th, etc.) assistant message in the conversation, chunk N gets written to ChromaDB and chunks_fts.

### Step 7: Return

```python
return EngineResponse(
    status=status,
    text=content,
    conversation_id=conversation_id,
    assistant_message_id=assistant_message.id,
    timestamp=assistant_message.timestamp,
    tool_call_count=len(loop_result.tool_trace or []),
)
```

---

## Failure modes

Every step can fail. The engine's posture on each:

### User-message persistence fails

`save_and_chunk` on the user message raises (integrity error, disk full, etc.). The engine raises `EngineError` — nothing else to do. The adapter sees the raise and reports an error to the user. No assistant message is generated.

Diagnostic target: log the error with full context (user_id, conversation_id, message text). This is a real problem that needs investigation.

### Retrieval fails inside context construction

Context construction catches retrieval failures and builds the context without retrieved memories (empty section). The turn proceeds without memory. A warning is logged.

Rationale: missing memory is degraded but survivable. The entity can still respond based on the current conversation and seed identity. Better than failing the whole turn.

### Model call fails (network, Ollama down, timeout)

The agent loop raises the Ollama error up. The engine catches it, synthesizes an error response:

```python
status = "model_failed"
content = "I couldn't reach my own reasoning just now. Try again?"
```

The assistant message still gets persisted (per Principle 5 — the event happened, she saw the user message, her response is "I couldn't respond"). The tool_trace is empty. The channel shows the apology to the user.

Logged as a warning for Lyle to investigate.

### Tool dispatch fails within the agent loop

Per Skill Registry & Dispatch v1, tool failures become `ToolResult(success=False)` that the model sees and reasons over. The loop continues. No engine-level failure.

### Assistant-message persistence fails

This is ugly. The agent loop produced content, but we can't save it. The response to the adapter should still go out — the user sees the reply — but internally the archive is missing a message.

Engine-level response: log an error, return the content to the adapter, let the user see it. Mark in logs that persistence failed. The next time that conversation loads, it'll be missing this turn, which will be visible when the entity reads the current conversation back.

This is a bad state. Shouldn't happen in practice (dual-write to two local SQLite files is very reliable). Flag it if it does; don't try to paper over it.

### Live chunking fails (within `save_and_chunk`)

`save_and_chunk` already handles this with a warning log (per Chunking Spec v1). Engine sees the assistant message as saved; the chunk is missed; close-time rechunk catches up. No engine-level action.

---

## Cold-start behavior

First message in a new conversation (`conversation_id=None`):

- Step 1: generate new UUID.
- Step 2: `save_and_chunk` creates the conversations row (via INSERT OR IGNORE) and inserts the user message.
- Step 3: context construction runs. Current-conversation section has just this one message (the user's opening). Retrieved memories section surfaces whatever retrieval finds against the opening message — probably sparse, may be empty.
- Step 4: agent loop runs.
- Steps 5-7: standard.

Nothing special. The cold-start shape falls out of the general flow.

### First-ever message (fresh install)

ChromaDB and chunks_fts are empty. Retrieval returns `[]`. Context construction omits the retrieved-memories section (or shows an empty one — implementation choice, CC v1.1 should settle this). The entity reads her seed identity and the opening message, responds from there.

Her response is a chunk that gets live-written at turn 5. Over time, retrieval has more to surface.

---

## Conversation lifecycle vs. engine

The engine does not close conversations. Close is triggered by startup recovery (per Autonomous Window v1.1), not by the engine. Each engine call leaves `ended_at = NULL` — the conversation stays open after this turn.

The adapter may set `conversation_id = None` on the next message from the same user to start a fresh conversation. The prior one stays open until the next worker startup, which closes it.

This means a conversation's `ended_at` can lag by hours or days behind the last actual message. That's cosmetic, not functional, per Autonomous Window v1.1.

---

## Autonomous session shape

Different top-level function, most of the guts shared:

```python
def run_autonomous_task(
    task: Task,                          # from the task queue
    registry: Registry,
    config: EngineConfig,
    yield_check: Callable[[], bool],     # from the scheduler
) -> AutonomousTaskResult:
    """Run one autonomous task via the agent loop.
    
    Builds autonomous-session context (no user, task description as
    input), runs the agent loop with the autonomous iteration limit
    and the caller's yield check, returns the outcome.
    """
```

Key differences from `handle_conversation_turn`:

- **No user message to persist.** The task description is the input; the task queue is its persistence.
- **Autonomous-session context.** Section 4 renders as "You are in an autonomous work session. The time is ..." (per CC v1.1). Retrieval runs against the task description. Section 5 is task context, not a conversation transcript.
- **Higher iteration limit** (`config.autonomous_iteration_limit = 50`). Deep work needs space.
- **Yield check is active.** Scheduler-provided. The loop checks it between iterations.
- **No conversation_id.** The session isn't a conversation.
- **Outputs are whatever tools she used to produce them.** Journals write to journal storage; research writes to research storage; workspace files go to the workspace. The engine doesn't persist a final "assistant message" — there's no conversational counterpart.
- **Task state gets updated.** If the loop completed, the task becomes `completed` with a note. If it yielded, the task returns to `pending` with a progress_note. If something errored, the task gets `abandoned` with the error. Task queue design owns the exact semantics.

What about the session itself being recorded? The agent loop's messages (assistant outputs, tool calls, tool results) happened. They're part of her experience. They should be retrievable.

**Day-one decision:** autonomous session recording is deferred. The agent loop's outputs (written via skill tools) land in their respective stores (workspace files, journal entries via a future journal tool, etc.). The session-as-a-whole — "she worked on task X for 20 minutes and called these tools" — is not chunked or retrievable.

Autonomous-session chunking design (separate doc in this session's queue) will settle this.

---

## Configuration resolution

`EngineConfig` is constructed at worker startup. The worker reads a config file (or environment variables, CLI args — implementation choice), resolves paths, and builds the config once.

```python
config = EngineConfig(
    archive_path="./data/archive.db",
    working_path="./data/working.db",
    chromadb_path="./data/chromadb/",
    workspace_path="./data/workspace/",
    ollama_host="http://localhost:11434",
    model_name="gemma4",
    # ... defaults otherwise
)
```

The worker keeps the config alive for its entire lifetime. Every engine call gets the same config.

Changing config requires a worker restart (per Tool Framework v1: nothing changes under the entity's feet during a session).

---

## Ollama call shape

The engine's use of Ollama (via the agent loop's `ollama_call`) goes through a thin adapter inside the engine module:

```python
def ollama_call(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    host: str,
    model: str = "gemma4",
) -> dict:
    """Call Ollama's /api/chat endpoint with tools support.
    
    IMPORTANT: Every request MUST include "think": false in the payload.
    Without it, gemma4:26b generates 800+ reasoning tokens and 40s+
    response times. With it, responses are ~1s with 18 eval tokens.
    This cannot be baked into the Modelfile (verified: Ollama does not
    support think/nothink as a Modelfile parameter as of April 2026).
    
    Returns a dict with keys:
        "content": str         # the assistant's text content (empty string during tool calls)
        "tool_calls": list     # [] if no tools called
    
    Verified Ollama response shape (from gemma4:26b smoke test):
        tool_calls entries have the form:
        {
            "id": "call_xxxx",           # unique call ID
            "function": {
                "index": 0,              # position among multiple calls
                "name": "web_search",    # tool name
                "arguments": {...}       # parsed dict, not a string
            }
        }
    
    When feeding tool results back to the model, use:
        {"role": "tool", "tool_name": "<n>", "content": "<result text>"}
    """
```

Handles:
- Request construction (system message + conversation messages + tools array).
- Response parsing (Ollama's JSON response shape).
- Error translation (connection failures → specific exception classes).
- No retries.

This lives in a new module `tir/engine/ollama_client.py` or similar. One level below the conversation engine itself.

### Why not use the `ollama` Python package

The same reason `embeddings.py` uses raw HTTP against Ollama's `/api/embed`: smaller surface, fewer dependencies, failure modes are easy to reason about. The `/api/chat` endpoint's JSON is straightforward.

If the package grows features we want (streaming, better error handling, tool call parsing helpers), revisit. Day-one: urllib.

---

## Logging

Every turn produces log entries at INFO:

- Turn start (user_id, conversation_id, message length)
- Context built (chunk count retrieved, budget usage)
- Model call (duration, token counts if available)
- Each tool call (name, success)
- Turn end (status, duration, tool_call_count)

Errors log at WARNING or ERROR with full exc_info. Per Tool Framework v1's logging guidance — stdlib logging, module-level loggers, no global configuration set here.

Log volume per turn is modest (maybe 5-15 lines for a simple turn, 20-50 for a tool-heavy turn). Worker-level log configuration decides where this goes (file, stderr, both).

---

## What this design does NOT decide

- **The worker process shape** (how the engine gets invoked, concurrency model, lifecycle). That's Scheduler & Worker Process design.
- **Session management on the web side** (cookies, tokens, resume logic). That's Web Adapter design.
- **Error-reporting UX.** The engine returns an `EngineResponse` with a status; the adapter/UI decides how to render failure cases (inline error message, error banner, retry button).
- **Conversation continuation policy across reconnects.** Again, adapter-level.
- **Message deduplication** (if the same message arrives twice — network retry, user double-click). Adapter-level.
- **Conversation summarization for long-running sessions.** Per CC v1.1, the current conversation is never lossy-compressed; sessions end when they grow too big. Engine enforces this by… not doing anything special; the adapter sees the token budget pressure through growing turn latency and eventually the user-facing experience suggests ending the conversation.

---

## Open questions

**a. Ollama's exact tool-call response shape.** CLOSED. Verified by smoke test (2026-04-19, gemma4:26b, 5/5 clean). Response shape documented in the `ollama_call` docstring above. Key details: tool_calls include an `id` field and `function.index` field; arguments are returned as a parsed dict (not a JSON string); content is empty string during tool calls; the `thinking` field is absent when `think: false` is sent. Tool results feed back as `{"role": "tool", "tool_name": "...", "content": "..."}` per Ollama docs.

**b. First-turn context when there's no prior memory.** The engine/CC should degrade gracefully when retrieval returns empty. Current implicit behavior (empty retrieved-memories section) is probably fine but worth verifying in tests.

**c. Concurrent turn handling.** Per Autonomous Window v1.1, the worker is single-threaded at the turn level — one turn at a time. Two messages arriving at the same time queue up. The engine itself doesn't enforce this; the worker does. But if the engine is called from two threads concurrently (programming error), what happens? SQLite with rollback journaling serializes writes via exclusive locks. The engine's operations would mostly just work with some write contention. Not tested, not guaranteed. Document that the engine is single-threaded-per-turn and the caller is responsible.

**d. Iteration-limit fallback message.** Current placeholder is a hardcoded string, which is exactly the kind of directive Principle 15 wants removed. Keep it in v1 as scaffolding; revisit once we see real iteration-limit behavior.

**e. Model timeout handling.** If the Ollama call hangs (model genuinely stuck on a long generation), the engine blocks. Ollama has its own internal timeouts; Python urllib has a request timeout. Set the urllib timeout to something generous (120s). If a real timeout happens, the engine sees the exception and returns an error response. Acceptable.

**f. How the engine logs tool trace contents.** The full tool trace in the log might be huge (especially with web_fetch results). Default: log the trace metadata (tool names, success flags) but not full rendered content. Full content lives in the persisted archive; log is for operations.

**g. Persisting the iteration-limit placeholder message.** When the loop terminates for iteration_limit and we synthesize a placeholder response, that placeholder becomes her chunk in ChromaDB eventually. Future retrieval will surface "I took too many steps" as if it were her experience. Which it was — that turn did happen that way. Accept it.

---

## Cross-references

- **Autonomous Window Design v1.1** — gateway pattern (normalized message format), conversation concurrency (one turn at a time), autonomous session shape.
- **Context Construction v1.1** — the engine calls `build_conversation_context`; ordering, sections, and framing live there.
- **Retrieval Design v1** — called by context construction; the engine doesn't call `retrieve` directly.
- **Chunking Spec v1** + **BM25 Integration Spec v1** — `save_and_chunk` does the right thing; engine just calls it.
- **Skill Registry & Dispatch Design v1** — the agent loop (`run_agent_loop`) lives there; the engine invokes it.
- **Schema Design v1.4** — message persistence, tool_trace JSON, conversation lifecycle fields.
- **Tool Framework v1** — behaviors the engine enforces (e.g., turn is atomic, close on startup only).
- **Guiding Principles v1.1** — Principle 5 (dual-write is sacred; if user message persists, we proceed; if it doesn't, we fail honestly), Principle 14 (failures diagnosed, not papered over), Principle 15 (avoid behavioral directives; iteration-limit placeholder is debt).

---

*Project Tír Conversation Engine Design · v1.1 · April 2026*
