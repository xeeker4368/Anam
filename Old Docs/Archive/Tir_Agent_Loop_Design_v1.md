# Project Tír — Agent Loop Design

*Design doc v1, April 2026. The inner loop that runs tool-calling iterations between the model and the registry. Resolves the circular reference between Conversation Engine v1 (which said "the loop lives in Skill Registry") and Skill Registry v1 (which said "the loop lives in Conversation Engine"). It lives here, in its own module, called by both.*

---

## Purpose

The agent loop is the mechanism that lets the entity do more than generate text. It sends a prompt to the model, checks whether the response contains tool calls, dispatches those calls, feeds the results back, and repeats until the model produces a final text response or a limit is hit.

Two callers use the same loop with different parameters:

- **Conversation turns:** low iteration limit (5), no yield check, only the terminal iteration's content becomes the stored assistant message.
- **Autonomous sessions:** high iteration limit (50), scheduler-provided yield check, full iteration trace is preserved for chunking.

The loop itself doesn't know which caller invoked it. It runs the same logic either way; the caller controls behavior through the parameters it passes.

---

## Summary of decisions

1. **The loop is a standalone function in its own module** (`tir/engine/agent_loop.py`). Not part of the conversation engine, not part of the registry. Both import it.
2. **Terminal detection: content present + no tool_calls.** Verified by smoke test (2026-04-20): gemma4:26b produces either tool calls with empty content, or content with no tool calls. Never both.
3. **`think: false` in every Ollama request.** Cannot be set in the Modelfile. Must be in the HTTP payload. Without it: 800+ reasoning tokens, 40s+ response times. With it: ~1s tool calls, ~8-9s per 1K chars of terminal output.
4. **Tool results fed back as `{"role": "tool", "tool_name": "...", "content": "..."}`**. Verified working by smoke test.
5. **Tool definitions wrapped as `{"type": "function", "function": {...}}`** per Ollama's required format. The registry's `list_tools()` produces this shape.
6. **SKILL.md body loading: on first use within a turn.** The loop tracks which skill bodies have been loaded via a `loaded_skill_bodies` set. When a tool call fires for a skill not yet loaded, its body is injected into the system prompt for subsequent iterations. The set resets at turn boundary (caller's responsibility — the loop doesn't persist state between calls).
7. **Per-iteration tool trace records.** Each iteration produces a record with `iteration`, `timestamp`, `content`, `tool_calls`, `tool_results`. The full list is returned to the caller. `terminated_reason` lives on the loop's return value, not in the trace.
8. **Dispatch envelopes: `{ok: True, value}` for success (including tool-returned errors), `{ok: False, error}` for crashes.** The loop translates envelopes into the rendered text that enters the model's tool result message.
9. **No automatic retries.** Tool failures become experience. She sees the failure and decides what to do.
10. **Sequential tool calls only.** If the model emits multiple tool calls in one response, they execute sequentially. Parallel execution deferred.

---

## Verified model behavior

From the multi-turn smoke test (2026-04-20, gemma4:26b, 4/4 scenarios passed):

**Tool call response shape:**
```json
{
  "message": {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "id": "call_xxxx",
        "function": {
          "index": 0,
          "name": "web_search",
          "arguments": {"query": "unified memory architecture"}
        }
      }
    ]
  }
}
```

- `content` is empty string on non-terminal iterations. Never null, never has text alongside tool calls.
- `arguments` is a parsed dict, not a JSON string.
- `tool_calls` is absent (or empty list) on terminal iterations.
- `thinking` field is absent when `think: false` is sent.
- Multiple tool calls across iterations chain correctly (memory_search → web_search verified).
- Model terminates naturally after receiving tool results and producing a synthesis.

**Tool result format that works:**
```json
{"role": "tool", "tool_name": "web_search", "content": "Found 3 results for..."}
```

**Timing characteristics:**
- Tool call iterations: ~1-2s each.
- Terminal iterations (text generation): ~8-9s per 1K chars of output.
- Total turn time scales with output length, not iteration count.

---

## Interface

```python
def run_agent_loop(
    system_prompt: str,
    conversation: list[dict],
    registry: SkillRegistry,
    tool_context: ToolContext,
    iteration_limit: int,
    yield_check: Callable[[], bool] | None,
    ollama_host: str,
    model: str = "gemma4:26b",
) -> LoopResult:
    """Run the agent loop until terminal, iteration limit, or yield.

    Args:
        system_prompt: The fully-assembled system prompt (seed identity,
            tool definitions, retrieved memories, current situation).
        conversation: The message history for this turn. For chat: the
            current conversation's messages. For autonomous: the task
            context as a user message.
        registry: The skill registry for tool dispatch and SKILL.md
            body lookup.
        tool_context: Contextual data tools may need (user_id, paths,
            etc.). Passed through to dispatch.
        iteration_limit: Max iterations before forced termination.
            Chat: 5. Autonomous: 50.
        yield_check: Callable that returns True if the loop should
            exit early (chat arrived during autonomous work). None
            for chat turns (they don't yield).
        ollama_host: Ollama server URL.
        model: Model name for Ollama.

    Returns:
        LoopResult with terminal content, tool trace, and termination
        reason.
    """
```

### ToolContext

Data that tools may need during execution. Passed through dispatch to tool functions. Not all tools use all fields.

```python
@dataclass(frozen=True)
class ToolContext:
    user_id: str | None          # None for autonomous sessions
    conversation_id: str | None  # None for autonomous sessions
    workspace_path: str          # entity's file workspace
    working_db_path: str         # for tools that query working.db (memory_search)
    chromadb_path: str           # for tools that query ChromaDB (memory_search)
    ollama_host: str             # for tools that need embeddings (document_ingest)
```

Tools receive this as a keyword argument. The `@tool` decorator and dispatch handle threading it through:

```python
# In dispatch:
result = tool_def.function(**args, _context=tool_context)

# In tool implementation:
@tool(name="memory_search", ...)
def memory_search(query: str, _context: ToolContext = None) -> str:
    # _context is injected by dispatch, not by the model
    ...
```

The underscore prefix signals "injected by infrastructure, not a model-facing parameter." The args schema does not include `_context`; jsonschema validation runs against the model-provided args only, before `_context` is added.

### LoopResult

```python
@dataclass
class LoopResult:
    terminated_reason: str    # "complete" | "iteration_limit" | "yielded" | "error"
    final_content: str | None # text from the terminal iteration, or None
    tool_trace: list[dict]    # per-iteration records (see shape below)
    iterations_run: int       # how many iterations actually executed
    error: str | None         # if terminated_reason == "error"
```

### Tool trace record shape

Each iteration produces one record:

```python
{
    "iteration": 0,
    "timestamp": "2026-04-20T20:15:33Z",
    "content": "",                        # model's text output this iteration
    "tool_calls": [                       # what the model asked for
        {
            "name": "web_search",
            "arguments": {"query": "..."},
            "id": "call_xxxx"
        }
    ],
    "tool_results": [                     # what came back
        {
            "tool_name": "web_search",
            "ok": true,
            "rendered": "Found 3 results for..."
        }
    ]
}
```

Terminal iteration has `tool_calls: []` and `tool_results: []`, with `content` populated.

The trace is a flat list. No wrapper object. `terminated_reason` lives on `LoopResult`, not in the trace — it describes the loop's outcome, not any individual iteration.

---

## Loop logic

```python
def run_agent_loop(
    system_prompt: str,
    conversation: list[dict],
    registry: SkillRegistry,
    tool_context: ToolContext,
    iteration_limit: int,
    yield_check: Callable[[], bool] | None,
    ollama_host: str,
    model: str = "gemma4:26b",
) -> LoopResult:
    messages = list(conversation)  # copy; we append to this
    tool_trace: list[dict] = []
    loaded_skill_bodies: set[str] = set()
    active_system_prompt = system_prompt

    for iteration in range(iteration_limit):
        # ── Yield check (autonomous only) ──
        if yield_check is not None and yield_check():
            return LoopResult(
                terminated_reason="yielded",
                final_content=None,
                tool_trace=tool_trace,
                iterations_run=iteration,
                error=None,
            )

        # ── Call the model ──
        try:
            response = ollama_call(
                system_prompt=active_system_prompt,
                messages=messages,
                tools=registry.list_tools(),
                host=ollama_host,
                model=model,
            )
        except Exception as e:
            logger.exception("Ollama call failed on iteration %d", iteration)
            return LoopResult(
                terminated_reason="error",
                final_content=None,
                tool_trace=tool_trace,
                iterations_run=iteration + 1,
                error=f"Model call failed: {type(e).__name__}: {e}",
            )

        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        # ── Build trace record ──
        trace_record = {
            "iteration": iteration,
            "timestamp": iso_now(),
            "content": content,
            "tool_calls": [],
            "tool_results": [],
        }

        # ── Terminal check ──
        if content and content.strip() and not tool_calls:
            trace_record["tool_calls"] = []
            trace_record["tool_results"] = []
            tool_trace.append(trace_record)
            return LoopResult(
                terminated_reason="complete",
                final_content=content,
                tool_trace=tool_trace,
                iterations_run=iteration + 1,
                error=None,
            )

        # ── No tool calls and no content = unexpected ──
        if not tool_calls:
            tool_trace.append(trace_record)
            return LoopResult(
                terminated_reason="error",
                final_content=content if content else None,
                tool_trace=tool_trace,
                iterations_run=iteration + 1,
                error="Model produced neither content nor tool calls.",
            )

        # ── Process tool calls ──
        # Add the assistant message (with its tool_calls) to the conversation
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": response.get("raw_tool_calls", tool_calls),
            # raw_tool_calls preserves the original shape from Ollama
            # (with id, function.index) for the model's next turn
        })

        for tc in tool_calls:
            tool_name = tc.get("name") or tc.get("function", {}).get("name")
            arguments = tc.get("arguments") or tc.get("function", {}).get("arguments", {})
            call_id = tc.get("id")

            trace_call = {
                "name": tool_name,
                "arguments": arguments,
                "id": call_id,
            }
            trace_record["tool_calls"].append(trace_call)

            # ── Dispatch ──
            envelope = registry.dispatch(tool_name, arguments, _context=tool_context)

            # ── Translate envelope to rendered text ──
            if envelope["ok"]:
                rendered = str(envelope["value"])
            else:
                rendered = envelope["error"]

            trace_record["tool_results"].append({
                "tool_name": tool_name,
                "ok": envelope["ok"],
                "rendered": rendered,
            })

            # ── Feed result back to conversation ──
            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": rendered,
            })

            # ── Progressive disclosure: load SKILL.md body if first use ──
            try:
                skill = registry.get_skill_for_tool(tool_name)
                if skill.name not in loaded_skill_bodies:
                    loaded_skill_bodies.add(skill.name)
                    active_system_prompt = _inject_skill_body(
                        active_system_prompt, skill.name, skill.body
                    )
            except KeyError:
                pass  # unknown tool; dispatch already returned an error

        tool_trace.append(trace_record)

    # ── Exhausted iteration limit ──
    return LoopResult(
        terminated_reason="iteration_limit",
        final_content=None,
        tool_trace=tool_trace,
        iterations_run=iteration_limit,
        error=None,
    )
```

### `ollama_call` — the HTTP wrapper

```python
def ollama_call(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    host: str,
    model: str = "gemma4:26b",
) -> dict:
    """Call Ollama's /api/chat endpoint. Returns parsed response.

    CRITICAL: Every request includes "think": false. Without it,
    gemma4:26b generates 800+ reasoning tokens and 40s+ response
    times. Verified by smoke test; cannot be set in the Modelfile.

    Returns:
        {
            "content": str,           # empty string during tool calls
            "tool_calls": list[dict], # normalized: [{name, arguments, id}]
            "raw_tool_calls": list,   # original Ollama shape for passthrough
        }
    """
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "tools": tools,
    }

    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    msg = body.get("message", {})
    content = msg.get("content", "")
    raw_calls = msg.get("tool_calls", [])

    # Normalize tool calls to a simpler shape for the loop
    normalized = []
    for call in raw_calls:
        fn = call.get("function", {})
        normalized.append({
            "name": fn.get("name"),
            "arguments": fn.get("arguments", {}),
            "id": call.get("id"),
        })

    return {
        "content": content,
        "tool_calls": normalized,
        "raw_tool_calls": raw_calls,
    }
```

### `_inject_skill_body` — progressive disclosure

```python
def _inject_skill_body(system_prompt: str, skill_name: str, body: str) -> str:
    """Append a skill's SKILL.md body to the system prompt.

    Injected after the first tool call for this skill within a turn.
    The body provides detailed usage instructions the model can
    reference for subsequent iterations.
    """
    section = (
        f"\n\n[Skill reference: {skill_name}]\n"
        f"{body}\n"
        f"[End skill reference: {skill_name}]"
    )
    return system_prompt + section
```

Simple string append. The system prompt grows over the course of a turn as skills are used. This is bounded by the number of distinct skills used in a single turn (typically 2-3, never more than the full skill set). At turn boundary, the caller constructs a fresh system prompt — the accumulated bodies are gone.

---

## How callers use the loop

### Conversation engine (chat turn)

```python
loop_result = run_agent_loop(
    system_prompt=context["system"],
    conversation=context["messages"],
    registry=registry,
    tool_context=tool_context,
    iteration_limit=config.conversation_iteration_limit,  # 5
    yield_check=None,
    ollama_host=config.ollama_host,
)

# Only the terminal content becomes the assistant message
if loop_result.terminated_reason == "complete":
    assistant_content = loop_result.final_content
elif loop_result.terminated_reason == "iteration_limit":
    assistant_content = (
        "I took too many steps on that and need to stop here. "
        "Let me know what you want me to focus on."
    )
else:
    assistant_content = "Something went wrong processing that message."

# Persist with tool_trace
assistant_message = Message(
    ...
    content=assistant_content,
    tool_trace=json.dumps(loop_result.tool_trace) if loop_result.tool_trace else None,
)
```

### Autonomous engine (task session)

```python
loop_result = run_agent_loop(
    system_prompt=autonomous_context["system"],
    conversation=autonomous_context["messages"],
    registry=registry,
    tool_context=tool_context,
    iteration_limit=config.autonomous_iteration_limit,  # 50
    yield_check=lambda: shared.yield_signal.is_set(),
    ollama_host=config.ollama_host,
)

# Full trace is preserved for autonomous chunking
# (per Autonomous Chunking v1 — chunk the whole session trace)
return AutonomousTaskResult(
    status=loop_result.terminated_reason,
    final_content=loop_result.final_content,
    session_trace=loop_result.tool_trace,
    yield_context=_extract_yield_context(loop_result) if loop_result.terminated_reason == "yielded" else None,
    error_message=loop_result.error,
)
```

---

## Dispatch integration

The loop calls `registry.dispatch(tool_name, arguments, _context=tool_context)`. This requires a small extension to the Skill Registry's dispatch signature:

```python
def dispatch(self, tool_name: str, args: dict, _context: ToolContext = None) -> dict:
    """Invoke a tool. Returns {ok, value|error} envelope.

    If _context is provided, it's passed to the tool function as
    a keyword argument. Tools that need it declare _context in
    their signature; tools that don't, ignore it.
    """
    # ... lookup, validation (unchanged) ...

    try:
        if _context is not None:
            result = tool_def.function(**args, _context=_context)
        else:
            result = tool_def.function(**args)
    except TypeError as e:
        # Tool doesn't accept _context — call without it
        if "_context" in str(e):
            result = tool_def.function(**args)
        else:
            raise
    except Exception as e:
        # ... error envelope (unchanged) ...
```

The TypeError fallback handles tools that don't declare `_context` in their signature. This avoids requiring every tool to accept a parameter it may not need.

---

## Error handling

### Model call failure (network, Ollama down, timeout)

The loop catches the exception and returns `LoopResult(terminated_reason="error")`. The caller (conversation engine or autonomous engine) decides how to surface it.

### Tool dispatch crash (`ok: False`)

The error text enters the model's context as a tool result. The model sees it, reasons about it, and decides: retry with different arguments, try a different approach, or explain the failure in its response. No automatic retry at the loop level.

### Tool-returned error (`ok: True`, value describes a failure)

Same path as success — the rendered text enters the model's context. The distinction between "tool crashed" and "tool returned an error" is captured in the trace (`ok` field) for fabrication detection. The model doesn't see the distinction; it sees text either way.

### Unknown tool name

Registry returns `{ok: False, error: "No tool named X"}`. The model sees the error and can self-correct. Smoke test showed gemma4:26b never called an unknown tool across 4 scenarios, but the handling exists for robustness.

### Empty response (no content, no tool calls)

Treated as an error. The loop returns with `terminated_reason="error"`. This state was never observed in the smoke test but is handled defensively.

---

## What this design does NOT decide

- **What content goes into the system prompt.** Context Construction v1.1 builds it; the loop receives it.
- **How the tool trace is persisted.** The conversation engine persists it as JSON on the assistant message. The autonomous engine passes it to the chunking pipeline. The loop just returns it.
- **Fabrication detection.** The trace enables it; the detection mechanism is Phase 2 per Tool Framework v1.
- **Streaming.** Day-one is non-streaming (`"stream": false`). Adding streaming later means changing `ollama_call` to process chunks and yielding partial content. The loop's structure (iterate until terminal) doesn't change.
- **Parallel tool calls.** Sequential day-one. If parallel is ever needed, the dispatch section of the loop changes but the overall structure doesn't.

---

## Open questions

**a. System prompt token growth during a turn.** Each skill body injection grows the system prompt. With 9 day-one skills and bodies of ~500-2000 tokens each, a turn using 3 skills adds ~1500-6000 tokens to the system prompt. Within budget for gemma4:26b's 256K context, but worth monitoring. If skill count grows significantly, consider a context budget check before injection.

**b. Tool call ID passthrough.** Ollama assigns `id` fields to tool calls. The loop preserves them in `raw_tool_calls` so the model sees consistent IDs when results come back. Whether the model actually uses these IDs for matching (vs. positional ordering) is unverified. Smoke test worked without explicitly matching IDs, but the passthrough costs nothing.

**c. Multiple tool calls in a single response.** The smoke test only produced one tool call per non-terminal iteration. Gemma 4 may be capable of emitting multiple — the loop handles it (iterates over `tool_calls` list), but it's untested. If observed, verify that sequential dispatch + sequential result feeding produces coherent behavior.

---

## Cross-references

- **Conversation Engine v1** — primary caller for chat turns. Open question (a) is closed by this doc (the loop lives here, not in the engine or registry).
- **Skill Registry v1** — provides `list_tools()`, `dispatch()`, `get_skill_for_tool()`. Dispatch signature extended with `_context` parameter.
- **Scheduler & Worker Design v1** — autonomous caller via `run_autonomous_task`. Provides `yield_check` via `shared.yield_signal`.
- **Tool Framework v1** — execution model (explicit tool calling, sequential dispatch, errors as experience, agent loop with context-dependent iteration limit). This doc implements that model.
- **Autonomous Chunking v1** — consumes the full `tool_trace` for autonomous session chunking.
- **Context Construction v1.1** — builds the system prompt and conversation that the loop receives.
- **Schema v1.4** — `tool_trace` JSON column on messages table stores what this loop produces.
- **Guiding Principles v1.1** — Principle 9 (she sees her own tool calls and results), Principle 10 (the model reasons about tool results; don't pre-process), Principle 14 (errors surface honestly), Principle 15 (no automatic retries — she learns from failure).

---

*Project Tír Agent Loop Design · v1 · April 2026*
