import json
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from tir.api.routes import app


@dataclass
class FakeLoopResult:
    final_content: str | None
    tool_trace: list[dict]
    terminated_reason: str
    iterations: int
    error: str | None = None


class FakeRegistry:
    def __init__(self, has_tools=False):
        self._has_tools = has_tools

    def has_tools(self):
        return self._has_tools

    def list_tool_descriptions(self):
        return "You have access to the following tools:\n- memory_search: Search memory"

    def list_tools(self):
        return []


def _stream_lines(response):
    return [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]


def _fake_user():
    return {"id": "user-1", "name": "Lyle", "role": "admin"}


def _fake_message(role, content, message_id):
    return {
        "id": message_id,
        "conversation_id": "conv-1",
        "role": role,
        "content": content,
        "timestamp": "2026-04-27T12:00:00+00:00",
    }


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_no_tool_path_preserves_basic_events(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Hello", "msg-user"),
        _fake_message("assistant", "Hello back", "msg-assistant"),
    ]
    mock_get_messages.return_value = [_fake_message("user", "Hello", "msg-user")]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Hello "},
        {"type": "token", "content": "back"},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Hello back",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Hello"})
    events = _stream_lines(response)

    assert [event["type"] for event in events] == [
        "debug",
        "token",
        "token",
        "debug_update",
        "done",
    ]
    assert "timings" in events[0]
    assert "retrieval_ms" in events[0]["timings"]
    assert "total_backend_ms" in events[-2]["timings"]
    assert events[-1]["conversation_id"] == "conv-1"
    assistant_call = mock_save_message.call_args_list[-1]
    assert assistant_call.kwargs["tool_trace"] is None


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_tool_trace_is_emitted_and_persisted(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Search memory", "msg-user"),
        _fake_message("assistant", "I found it.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [_fake_message("user", "Search memory", "msg-user")]
    tool_trace = [
        {
            "iteration": 0,
            "tool_calls": [
                {"name": "memory_search", "arguments": {"query": "memory"}}
            ],
            "tool_results": [
                {"tool_name": "memory_search", "ok": True, "rendered": "Memory result"}
            ],
        }
    ]
    mock_loop.return_value = iter([
        {
            "type": "tool_call",
            "name": "memory_search",
            "arguments": {"query": "memory"},
        },
        {
            "type": "tool_result",
            "name": "memory_search",
            "ok": True,
            "result": "Memory result",
        },
        {"type": "token", "content": "I found it."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I found it.",
                tool_trace=tool_trace,
                terminated_reason="complete",
                iterations=2,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Search memory"})
    events = _stream_lines(response)

    assert [event["type"] for event in events] == [
        "debug",
        "tool_call",
        "tool_result",
        "token",
        "debug_update",
        "done",
    ]
    assert events[-2]["timings"]["tool_call_count"] == 1
    assert events[-2]["timings"]["tool_loop_iterations"] == 2
    assistant_call = mock_save_message.call_args_list[-1]
    persisted_trace = json.loads(assistant_call.kwargs["tool_trace"])
    assert persisted_trace[0]["tool_calls"][0]["name"] == "memory_search"


@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_user")
def test_stream_chat_unknown_explicit_user_id_returns_404_without_saving(
    mock_get_user,
    mock_save_message,
):
    mock_get_user.return_value = None

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Hello", "user_id": "missing-user"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    mock_save_message.assert_not_called()


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.get_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_ended_conversation_starts_new_conversation(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_get_conversation,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_get_conversation.return_value = {
        "id": "old-conv",
        "user_id": "user-1",
        "ended_at": "2026-04-27T12:00:00+00:00",
        "chunked": 1,
    }
    mock_start_conversation.return_value = "new-conv"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Continue", "msg-user"),
        _fake_message("assistant", "New conversation", "msg-assistant"),
    ]
    mock_get_messages.return_value = [_fake_message("user", "Continue", "msg-user")]
    mock_loop.return_value = iter([
        {"type": "token", "content": "New conversation"},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="New conversation",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Continue", "conversation_id": "old-conv"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["conversation_id"] == "new-conv"
    assert events[-1]["conversation_id"] == "new-conv"
    assert mock_save_message.call_args_list[0].args[0] == "new-conv"
    assert mock_save_message.call_args_list[1].args[0] == "new-conv"


@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation")
@patch("tir.api.routes._resolve_user")
def test_stream_chat_mismatched_conversation_user_returns_403_without_saving(
    mock_resolve_user,
    mock_get_conversation,
    mock_save_message,
):
    mock_resolve_user.return_value = _fake_user()
    mock_get_conversation.return_value = {
        "id": "other-conv",
        "user_id": "other-user",
        "ended_at": None,
    }

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Hello", "conversation_id": "other-conv"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Conversation does not belong to user"
    mock_save_message.assert_not_called()


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_agent_loop_exception_does_not_save_synthetic_assistant_message(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.return_value = _fake_message("user", "Break", "msg-user")
    mock_get_messages.return_value = [_fake_message("user", "Break", "msg-user")]
    mock_loop.side_effect = RuntimeError("model unavailable")

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Break"})
    events = _stream_lines(response)

    assert response.status_code == 200
    assert any(event["type"] == "error" for event in events)
    assert events[-1]["type"] == "done"
    assert events[-1]["message_id"] is None
    assert mock_save_message.call_count == 1
    assert mock_save_message.call_args.args[:3] == ("conv-1", "user-1", "user")
    mock_maybe_chunk_live.assert_not_called()


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_iteration_limit_does_not_save_synthetic_assistant_message(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.return_value = _fake_message("user", "Loop", "msg-user")
    mock_get_messages.return_value = [_fake_message("user", "Loop", "msg-user")]
    mock_loop.return_value = iter([
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content=None,
                tool_trace=[{"iteration": 0, "tool_calls": []}],
                terminated_reason="iteration_limit",
                iterations=5,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Loop"})
    events = _stream_lines(response)

    assert [event["type"] for event in events] == ["debug", "error", "debug_update", "done"]
    assert events[-1]["message_id"] is None
    assert mock_save_message.call_count == 1
    mock_maybe_chunk_live.assert_not_called()


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_unknown_termination_does_not_save_synthetic_assistant_message(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.return_value = _fake_message("user", "Fail", "msg-user")
    mock_get_messages.return_value = [_fake_message("user", "Fail", "msg-user")]
    mock_loop.return_value = iter([
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content=None,
                tool_trace=[],
                terminated_reason="model_error",
                iterations=1,
                error="bad model response",
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Fail"})
    events = _stream_lines(response)

    assert any(
        event["type"] == "error" and "bad model response" in event["message"]
        for event in events
    )
    assert events[-1]["message_id"] is None
    assert mock_save_message.call_count == 1
    mock_maybe_chunk_live.assert_not_called()


@patch("tir.api.routes.maybe_chunk_live")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_empty_complete_output_does_not_save_synthetic_assistant_message(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_maybe_chunk_live,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.return_value = _fake_message("user", "Empty", "msg-user")
    mock_get_messages.return_value = [_fake_message("user", "Empty", "msg-user")]
    mock_loop.return_value = iter([
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="   ",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "Empty"})
    events = _stream_lines(response)

    assert any(
        event["type"] == "error" and "couldn't generate a response" in event["message"]
        for event in events
    )
    assert events[-1]["message_id"] is None
    assert mock_save_message.call_count == 1
    mock_maybe_chunk_live.assert_not_called()
