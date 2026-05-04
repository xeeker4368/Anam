"""
Tests for the Tír Agent Loop.

All tests mock Ollama responses. No real model or server needed.
Tests validate loop control flow, event yielding, tool dispatch,
error handling, and tool trace recording.
"""

import json
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


@tool(
    name="dict_tool",
    description="Returns structured data",
    args_schema={"type": "object", "properties": {}},
)
def dict_tool() -> dict:
    return {"ok": True, "value": None}


@tool(
    name="list_tool",
    description="Returns a list",
    args_schema={"type": "object", "properties": {}},
)
def list_tool() -> list:
    return [{"ok": True}, "next"]


@tool(
    name="unicode_tool",
    description="Returns Unicode text inside structured data",
    args_schema={"type": "object", "properties": {}},
)
def unicode_tool() -> dict:
    return {"text": "café"}


class NonJsonSerializable:
    def __str__(self):
        return "non-json-value"


@tool(
    name="object_tool",
    description="Returns a non-JSON-serializable value",
    args_schema={"type": "object", "properties": {}},
)
def object_tool() -> NonJsonSerializable:
    return NonJsonSerializable()


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


def _make_tool_call_chunks(tool_name: str, arguments) -> list[dict]:
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
    registry._tools["dict_tool"] = ToolDefinition(
        name="dict_tool",
        description="Returns structured data",
        args_schema={"type": "object", "properties": {}},
        function=dict_tool,
        skill_name="test_structured",
    )
    registry._tools["list_tool"] = ToolDefinition(
        name="list_tool",
        description="Returns a list",
        args_schema={"type": "object", "properties": {}},
        function=list_tool,
        skill_name="test_structured",
    )
    registry._tools["unicode_tool"] = ToolDefinition(
        name="unicode_tool",
        description="Returns Unicode structured data",
        args_schema={"type": "object", "properties": {}},
        function=unicode_tool,
        skill_name="test_structured",
    )
    registry._tools["object_tool"] = ToolDefinition(
        name="object_tool",
        description="Returns non-JSON data",
        args_schema={"type": "object", "properties": {}},
        function=object_tool,
        skill_name="test_structured",
    )
    registry._tool_to_skill["echo"] = "test_echo"
    registry._tool_to_skill["fail_tool"] = "test_fail"
    registry._tool_to_skill["dict_tool"] = "test_structured"
    registry._tool_to_skill["list_tool"] = "test_structured"
    registry._tool_to_skill["unicode_tool"] = "test_structured"
    registry._tool_to_skill["object_tool"] = "test_structured"

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

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_invalid_json_arguments_are_tool_result_not_crash(self, mock_stream):
        """Invalid JSON-string tool args return a tool result and loop continues."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", '{"text":')),
            iter(_make_text_chunks("I saw the tool error")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "echo malformed"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["ok"] is False
        assert "failed to parse JSON string" in tr["result"]

        result = events[-1]["result"]
        assert result.terminated_reason == "complete"
        assert result.final_content == "I saw the tool error "

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_json_string_arguments_are_normalized_in_tool_trace(self, mock_stream):
        """Successful JSON-string tool args are stored as normalized dicts."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", '{"text": "hello"}')),
            iter(_make_text_chunks("OK")),
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

        tc = [e for e in events if e["type"] == "tool_call"][0]
        assert tc["arguments"] == '{"text": "hello"}'

        trace = events[-1]["result"].tool_trace
        assert trace[0]["tool_calls"][0]["arguments"] == {"text": "hello"}

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_structured_dict_tool_result_renders_as_json(self, mock_stream):
        """Dict tool results are streamed and passed to the model as JSON."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("dict_tool", {})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()
        messages = [{"role": "user", "content": "call dict"}]

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=messages,
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr == {
            "type": "tool_result",
            "name": "dict_tool",
            "ok": True,
            "result": '{"ok": true, "value": null}',
        }
        assert json.loads(tr["result"]) == {"ok": True, "value": None}
        assert messages[2]["content"] == tr["result"]
        assert events[-1]["result"].tool_trace[0]["tool_results"][0]["rendered"] == (
            tr["result"][:500]
        )

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_list_tool_result_renders_as_json(self, mock_stream):
        """List tool results are rendered as valid JSON."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("list_tool", {})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "call list"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["result"] == '[{"ok": true}, "next"]'
        assert json.loads(tr["result"]) == [{"ok": True}, "next"]

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_unicode_structured_tool_result_remains_readable(self, mock_stream):
        """JSON rendering keeps Unicode readable."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("unicode_tool", {})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "call unicode"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["result"] == '{"text": "café"}'

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_string_tool_result_remains_unquoted(self, mock_stream):
        """Plain string tool results stay unchanged."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("echo", {"text": "hello"})),
            iter(_make_text_chunks("OK")),
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

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["result"] == "Echo: hello"

    @patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
    def test_non_json_serializable_tool_result_falls_back_to_string(self, mock_stream):
        """Non-JSON-serializable values fall back to str(...)."""
        mock_stream.side_effect = [
            iter(_make_tool_call_chunks("object_tool", {})),
            iter(_make_text_chunks("OK")),
        ]
        registry = _build_test_registry()

        events = _collect_events(run_agent_loop(
            system_prompt="test",
            messages=[{"role": "user", "content": "call object"}],
            registry=registry,
            iteration_limit=5,
            ollama_host="http://fake",
            model="test-model",
        ))

        tr = [e for e in events if e["type"] == "tool_result"][0]
        assert tr["result"] == "non-json-value"


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
