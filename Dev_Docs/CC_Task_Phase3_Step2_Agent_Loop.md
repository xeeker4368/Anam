# CC Task: Phase 3 Step 2 — Agent Loop

## What this is

The agent loop is the iteration machinery for tool calling. The entity calls Ollama, gets a response. If the response contains tool calls, it dispatches them via the skill registry, feeds the results back, and calls Ollama again. When the response is text (no tool calls), the loop is done.

The loop is a generator that yields events — token events when streaming text, tool_call/tool_result events when using tools, and a done event at the end. This lets the web streaming handler forward events to the browser in real time.

## Prerequisites

- Phase 3 Step 1 complete (Skill Registry deployed at `tir/tools/registry.py`)
- Ollama running with gemma4:26b

## Read before writing

Read these files first:

- `tir/engine/ollama.py` — current Ollama client (you're adding to this)
- `tir/tools/registry.py` — the registry you're dispatching through
- `tir/config.py` — constants (CHAT_MODEL, OLLAMA_HOST, CONVERSATION_ITERATION_LIMIT)

## Files to create

```
tir/
    engine/
        agent_loop.py     ← NEW
tests/
    test_agent_loop.py    ← NEW
```

## Files to modify

```
tir/
    engine/
        ollama.py         ← ADD one function
```

---

## Modify: `tir/engine/ollama.py`

Add this function after the existing `chat_completion_stream`:

```python
def chat_completion_stream_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = CHAT_MODEL,
    ollama_host: str = OLLAMA_HOST,
):
    """
    Stream chat completion with tool support. Yields raw parsed chunks.

    Each chunk is a dict from Ollama's streaming response. Key fields:
        chunk["message"]["content"]    — text token (empty during tool calls)
        chunk["message"]["tool_calls"] — list of tool calls (when model calls a tool)
        chunk["done"]                  — True on the final chunk

    Unlike chat_completion_stream (which yields content strings), this
    yields the full parsed chunk so callers can detect tool_calls.

    CRITICAL: think: false is mandatory. Without it, 800+ reasoning tokens
    and 40s+ response times.

    Yields:
        dict: Individual parsed chunks from Ollama's streaming response.

    Raises:
        requests.RequestException on network/server errors.
    """
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)

    payload = {
        "model": model,
        "messages": api_messages,
        "stream": True,
        "think": False,
    }

    if tools:
        payload["tools"] = tools

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line)
            yield chunk
```

Do NOT modify `chat_completion` or `chat_completion_stream`. They stay as-is.

---

## New file: `tir/engine/agent_loop.py`

```python
"""
Tír Agent Loop

The iteration machinery for tool calling. Streams text responses
and dispatches tool calls through the skill registry.

The loop is a generator that yields events:
    {"type": "token",       "content": "..."}           — streaming text token
    {"type": "tool_call",   "name": "...", "arguments": {...}}  — tool being called
    {"type": "tool_result", "name": "...", "ok": bool, "result": "..."}  — tool returned
    {"type": "done",        "result": LoopResult}       — loop complete

Callers iterate over events and handle them appropriately.
The web streaming handler translates them to NDJSON.
Any future caller (CLI, autonomous engine) can use the same interface.

Content is empty during tool calls (verified by smoke test with gemma4:26b).
This means text tokens stream safely — if a tool call appears, no content
tokens were yielded for that iteration.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LoopResult:
    """What the agent loop returns when it's done."""
    final_content: str | None       # The text response, or None if iteration limit
    tool_trace: list[dict]          # Record of all tool calls and results
    terminated_reason: str          # "complete" | "iteration_limit" | "error"
    iterations: int                 # How many iterations ran
    error: str | None = None        # Error message if terminated_reason == "error"


def run_agent_loop(
    system_prompt: str,
    messages: list[dict],
    registry,
    iteration_limit: int,
    ollama_host: str,
    model: str | None = None,
):
    """
    Run the agent loop. Generator that yields events.

    Calls Ollama with tool definitions from the registry. If the model
    responds with tool calls, dispatches them and loops. If the model
    responds with text, streams it and terminates.

    Args:
        system_prompt: The full system prompt (soul + tools + memories + situation).
        messages: Conversation history as [{"role": ..., "content": ...}, ...].
            This list is mutated — tool call/result messages are appended
            during the loop so the model sees them on the next iteration.
        registry: SkillRegistry instance. Can be None (no tools available).
        iteration_limit: Max iterations before forced termination.
        ollama_host: Ollama server URL.
        model: Model name override. Defaults to config CHAT_MODEL.

    Yields:
        dict: Event dicts. See module docstring for event types.
    """
    from tir.config import CHAT_MODEL
    from tir.engine.ollama import chat_completion_stream_with_tools

    if model is None:
        model = CHAT_MODEL

    tools = registry.list_tools() if registry and registry.has_tools() else None
    tool_trace = []

    for iteration in range(iteration_limit):
        # --- Stream from Ollama ---
        accumulated_content = []
        accumulated_tool_calls = []

        try:
            for chunk in chat_completion_stream_with_tools(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                model=model,
                ollama_host=ollama_host,
            ):
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                chunk_tool_calls = msg.get("tool_calls")

                # Stream text tokens as they arrive
                if content:
                    accumulated_content.append(content)
                    yield {"type": "token", "content": content}

                # Accumulate tool calls (appear in their own chunk)
                if chunk_tool_calls:
                    accumulated_tool_calls.extend(chunk_tool_calls)

                if chunk.get("done", False):
                    break

        except Exception as e:
            logger.error(f"Ollama call failed on iteration {iteration}: {e}")
            result = LoopResult(
                final_content=None,
                tool_trace=tool_trace,
                terminated_reason="error",
                iterations=iteration + 1,
                error=str(e),
            )
            yield {"type": "done", "result": result}
            return

        full_content = "".join(accumulated_content)

        # --- Tool-calling iteration ---
        if accumulated_tool_calls:
            # Add assistant message (with tool_calls) to conversation
            messages.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": accumulated_tool_calls,
            })

            trace_record = {
                "iteration": iteration,
                "tool_calls": [],
                "tool_results": [],
            }

            for tc in accumulated_tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "unknown")
                arguments = func.get("arguments", {})

                yield {
                    "type": "tool_call",
                    "name": tool_name,
                    "arguments": arguments,
                }

                # Dispatch through registry
                envelope = registry.dispatch(tool_name, arguments)

                if envelope["ok"]:
                    rendered = str(envelope["value"])
                else:
                    rendered = f"Error: {envelope['error']}"

                yield {
                    "type": "tool_result",
                    "name": tool_name,
                    "ok": envelope["ok"],
                    "result": rendered,
                }

                # Feed result back into conversation for next iteration
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": rendered,
                })

                trace_record["tool_calls"].append({
                    "name": tool_name,
                    "arguments": arguments,
                })
                trace_record["tool_results"].append({
                    "tool_name": tool_name,
                    "ok": envelope["ok"],
                    "rendered": rendered[:500],
                })

            tool_trace.append(trace_record)
            continue

        # --- Terminal iteration (text response, already streamed) ---
        result = LoopResult(
            final_content=full_content,
            tool_trace=tool_trace,
            terminated_reason="complete",
            iterations=iteration + 1,
        )
        yield {"type": "done", "result": result}
        return

    # --- Exhausted iteration limit ---
    result = LoopResult(
        final_content=None,
        tool_trace=tool_trace,
        terminated_reason="iteration_limit",
        iterations=iteration_limit,
    )
    yield {"type": "done", "result": result}
```

---

## New file: `tests/test_agent_loop.py`

Unit tests with mocked Ollama responses. No real Ollama needed.

```python
"""
Tests for the Tír Agent Loop.

All tests mock Ollama responses. No real model or server needed.
Tests validate loop control flow, event yielding, tool dispatch,
error handling, and tool trace recording.
"""

import pytest
from unittest.mock import patch, MagicMock
from tir.engine.agent_loop import run_agent_loop, LoopResult
from tir.tools.registry import SkillRegistry, tool


# ---------------------------------------------------------------------------
# Test tools (simple functions for dispatch testing)
# ---------------------------------------------------------------------------

@tool(
    name="echo",
    description="Echoes back the input",
    args_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo"},
        },
        "required": ["text"],
    },
)
def echo_tool(text: str) -> str:
    return f"Echo: {text}"


@tool(
    name="fail_tool",
    description="Always raises an exception",
    args_schema={
        "type": "object",
        "properties": {},
    },
)
def fail_tool() -> str:
    raise ValueError("Intentional failure")


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_text_chunks(text: str) -> list[dict]:
    """Simulate Ollama streaming a text response (no tools)."""
    words = text.split()
    chunks = []
    for word in words:
        chunks.append({
            "message": {"role": "assistant", "content": word + " "},
            "done": False,
        })
    chunks.append({
        "message": {"role": "assistant", "content": ""},
        "done": True,
    })
    return chunks


def _make_tool_call_chunks(tool_name: str, arguments: dict) -> list[dict]:
    """Simulate Ollama returning a tool call (no text content)."""
    return [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": tool_name, "arguments": arguments}}
                ],
            },
            "done": False,
        },
        {
            "message": {"role": "assistant", "content": ""},
            "done": True,
        },
    ]


def _build_test_registry():
    """Build a registry with echo and fail_tool registered."""
    registry = SkillRegistry()
    from tir.tools.registry import ToolDefinition

    registry._tools["echo"] = ToolDefinition(
        name="echo",
        description="Echoes back the input",
        args_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"},
            },
            "required": ["text"],
        },
        function=echo_tool,
        skill_name="test_echo",
    )
    registry._tools["fail_tool"] = ToolDefinition(
        name="fail_tool",
        description="Always fails",
        args_schema={"type": "object", "properties": {}},
        function=fail_tool,
        skill_name="test_fail",
    )
    registry._tool_to_skill["echo"] = "test_echo"
    registry._tool_to_skill["fail_tool"] = "test_fail"

    return registry


def _collect_events(event_generator) -> list[dict]:
    """Collect all events from the generator into a list."""
    return list(event_generator)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentLoopTextOnly:
    """Tests for responses with no tool calls."""

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_text_response_yields_tokens_and_done(self, mock_stream):
        """Simple text response: yields token events then done."""
        mock_stream.return_value = iter(_make_text_chunks("Hello world"))
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(token_events) == 2  # "Hello " and "world "
        assert len(done_events) == 1

        result = done_events[0]["result"]
        assert result.terminated_reason == "complete"
        assert result.final_content == "Hello world "
        assert result.tool_trace == []
        assert result.iterations == 1

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_no_registry_works(self, mock_stream):
        """Loop works without a registry (no tools available)."""
        mock_stream.return_value = iter(_make_text_chunks("No tools here"))

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            registry=None,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        done = [e for e in events if e["type"] == "done"][0]
        assert done["result"].terminated_reason == "complete"
        assert done["result"].final_content == "No tools here "


class TestAgentLoopToolCalling:
    """Tests for tool call dispatch and iteration."""

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_tool_call_then_text(self, mock_stream):
        """Model calls a tool, gets result, then responds with text."""
        # First call: tool call. Second call: text response.
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", {"text": "hello"})),
            iter(_make_text_chunks("The echo said hello")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "echo hello"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        # Should have: tool_call, tool_result, tokens, done
        types = [e["type"] for e in events]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "token" in types
        assert types[-1] == "done"

        # Verify tool events
        tc = [e for e in events if e["type"] == "tool_call"][0]
        assert tc["name"] == "echo"
        assert tc["arguments"] == {"text": "hello"}

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["name"] == "echo"
        assert tr["ok"] is True
        assert tr["result"] == "Echo: hello"

        # Verify done
        result = events[-1]["result"]
        assert result.terminated_reason == "complete"
        assert result.iterations == 2
        assert len(result.tool_trace) == 1
        assert result.tool_trace[0]["tool_calls"][0]["name"] == "echo"

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_tool_dispatch_failure(self, mock_stream):
        """Tool raises exception — dispatch returns error envelope, loop continues."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("fail_tool", {})),
            iter(_make_text_chunks("Tool failed but I recovered")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "call fail_tool"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["ok"] is False
        assert "Intentional failure" in tr["result"]

        # Loop should still complete with text on iteration 2
        result = events[-1]["result"]
        assert result.terminated_reason == "complete"
        assert result.iterations == 2

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_unknown_tool(self, mock_stream):
        """Model calls a tool that doesn't exist — error envelope, loop continues."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("nonexistent_tool", {"x": 1})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "call nonexistent"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["ok"] is False
        assert "nonexistent_tool" in tr["result"]


class TestAgentLoopEdgeCases:
    """Tests for iteration limits, errors, and edge cases."""

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_iteration_limit(self, mock_stream):
        """Model keeps calling tools until iteration limit."""
        # Every call returns a tool call — never text
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", {"text": str(i)}))
            for i in range(5)
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "loop forever"}],
            registry=registry,
            iteration_limit=3,
            ollama_host="http://fake",
            model="test-model",
        ))

        result = events[-1]["result"]
        assert result.terminated_reason == "iteration_limit"
        assert result.final_content is None
        assert result.iterations == 3
        assert len(result.tool_trace) == 3

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_ollama_error(self, mock_stream):
        """Ollama raises an exception — loop terminates with error."""
        mock_stream.side_effect = ConnectionError("Ollama is down")
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        assert len(events) == 1
        result = events[0]["result"]
        assert result.terminated_reason == "error"
        assert "Ollama is down" in result.error

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_messages_mutated_with_tool_history(self, mock_stream):
        """The messages list is mutated with tool call/result history."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", {"text": "test"})),
            iter(_make_text_chunks("Done")),
        ]
        registry = _build_test_registry()
        messages = [{"role": "user", "content": "echo test"}]

        _collect_events(run_agent_loop(
            system_prompt="test",
            messages=messages,
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        # Messages should now contain: user, assistant (with tool_calls), tool result
        assert len(messages) == 3
        assert messages[1]["role"] == "assistant"
        assert "tool_calls" in messages[1]
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_name"] == "echo"
        assert messages[2]["content"] == "Echo: test"

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_tool_trace_structure(self, mock_stream):
        """Tool trace has the expected structure for persistence."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", {"text": "hi"})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "echo hi"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        trace = events[-1]["result"].tool_trace
        assert len(trace) == 1

        record = trace[0]
        assert "iteration" in record
        assert "tool_calls" in record
        assert "tool_results" in record
        assert record["tool_calls"][0]["name"] == "echo"
        assert record["tool_calls"][0]["arguments"] == {"text": "hi"}
        assert record["tool_results"][0]["tool_name"] == "echo"
        assert record["tool_results"][0]["ok"] is True
        assert "Echo: hi" in record["tool_results"][0]["rendered"]

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_empty_content_response(self, mock_stream):
        """Model returns empty content with no tools — terminates cleanly."""
        mock_stream.return_value = iter([
            {"message": {"role": "assistant", "content": ""}, "done": True}
        ])
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "hi"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        result = events[-1]["result"]
        assert result.terminated_reason == "complete"
        assert result.final_content == ""
```

---

## Verify — unit tests pass

```bash
cd /Users/localadmin/Tir
python -m pytest tests/test_agent_loop.py -v
```

Expected: All tests pass. No Ollama needed.

---

## Verify — smoke test with real Ollama

After unit tests pass, run this smoke test that validates the loop against real gemma4:26b.

Create a temporary test skill first:

```bash
cd /Users/localadmin/Tir

# Create a test skill
mkdir -p skills/active/echo
cat > skills/active/echo/SKILL.md << 'EOF'
---
name: echo
description: Echoes back the input text. Use this when asked to repeat or echo something.
version: "1.0"
fabrication_patterns:
  - "echoed"
  - "repeated back"
---
# Echo Tool
A simple tool that returns its input unchanged.
EOF

cat > skills/active/echo/echo.py << 'PYEOF'
from tir.tools.registry import tool

@tool(
    name="echo",
    description="Echoes back the input text. Use this when asked to repeat or echo something.",
    args_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo back"}
        },
        "required": ["text"],
    },
)
def echo(text: str) -> str:
    return f"Echo: {text}"
PYEOF
```

Then run:

```bash
python3 -c "
from tir.tools.registry import SkillRegistry
from tir.engine.agent_loop import run_agent_loop

# Load the echo skill
registry = SkillRegistry.from_directory('skills/active/')
print(f'Registry loaded: {len(registry._tools)} tools')
assert registry.has_tools()

# Run the loop with a prompt that should trigger echo
messages = [{'role': 'user', 'content': 'Please use the echo tool to echo the text: Hello World'}]

for event in run_agent_loop(
    system_prompt='You are a helpful assistant. Use tools when appropriate.',
    messages=messages,
    registry=registry,
    iteration_limit=5,
    ollama_host='http://localhost:11434',
):
    print(f'Event: {event[\"type\"]}', end='')
    if event['type'] == 'token':
        print(f' -> {repr(event[\"content\"][:50])}')
    elif event['type'] == 'tool_call':
        print(f' -> {event[\"name\"]}({event[\"arguments\"]})')
    elif event['type'] == 'tool_result':
        print(f' -> ok={event[\"ok\"]}, result={repr(event[\"result\"][:100])}')
    elif event['type'] == 'done':
        r = event['result']
        print(f' -> reason={r.terminated_reason}, iterations={r.iterations}')
        print(f'   content: {repr(r.final_content[:200] if r.final_content else None)}')
        print(f'   tool_trace: {len(r.tool_trace)} records')
    else:
        print()

print('PASS')
"
```

Expected:
1. A tool_call event for echo with text "Hello World"
2. A tool_result event with "Echo: Hello World"
3. Token events as the model responds with text
4. A done event with terminated_reason="complete" and iterations=2

After the smoke test, clean up:

```bash
rm -rf skills/active/echo
```

---

## What NOT to do

- Do NOT modify `chat_completion` or `chat_completion_stream` in ollama.py
- Do NOT modify `conversation.py`, `context.py`, or `routes.py` — integration is Step 4
- Do NOT create any skills (memory_search is Step 3)
- Do NOT add async/await — synchronous is correct
- Do NOT add automatic retries on tool failure — the model decides what to do
- Do NOT add logging configuration — use module-level `logging.getLogger(__name__)`

## What comes next

After verifying the agent loop works:
- Step 3: Memory Search Skill (first real tool, validates the pipeline with existing retrieval)
- Step 4: Integration (wire agent loop into routes.py streaming handler and context.py)
