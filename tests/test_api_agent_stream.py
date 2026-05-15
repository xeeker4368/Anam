import json
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from tir.api.routes import app
from tir.engine.context_budget import AUTO_RETRIEVAL_RESULTS, PROMPT_BUDGET_WARNING_CHARS


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


def _selection_trace():
    return json.dumps([
        {
            "tool_results": [
                {
                    "selection": {
                        "kind": "moltbook_authored_posts",
                        "tool_name": "moltbook_find_author_posts",
                        "author_name": "xkai",
                        "posts": [
                            {
                                "index": 1,
                                "id": "post-1",
                                "title": "Token Budget Notes",
                                "author_name": "xkai",
                                "created_at": "2026-05-04T01:00:00Z",
                                "submolt": "agents",
                            }
                        ],
                    }
                }
            ]
        }
    ])


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    assert events[0]["retrieval_policy"] == {
        "mode": "normal",
        "reason": "normal",
    }
    assert events[0]["retrieval_budget"] == {
        "input_chunks": 0,
        "included_chunks": 0,
        "skipped_chunks": 0,
        "skipped_empty_chunks": 0,
        "skipped_budget_chunks": 0,
        "truncated_chunks": 0,
        "max_chars": 14000,
        "used_chars": 0,
    }
    assert events[0]["prompt_budget_warning"] is None
    assert events[0]["prompt_breakdown"]["system_prompt_chars"] == events[0]["system_prompt_length"]
    assert events[0]["prompt_breakdown"]["conversation_history_chars"] == len("Hello")
    assert events[0]["supplied_conversation_id"] is None
    assert events[0]["effective_conversation_id"] == "conv-1"
    assert events[0]["conversation_started_reason"] == "new_request"
    assert events[0]["history_db_message_count"] == 1
    assert events[0]["history_user_message_count"] == 1
    assert events[0]["history_assistant_message_count"] == 0
    assert events[0]["history_injected_system_message_count"] == 0
    assert events[0]["model_message_count"] == 1
    assert events[0]["previous_assistant_included"] is False
    assert events[0]["previous_assistant_chars"] == 0
    assert events[0]["prompt_breakdown"]["selection_context_chars"] == 0
    assert events[0]["prompt_breakdown"]["artifact_context_chars"] == 0
    assert events[0]["prompt_breakdown"]["recent_artifact_context_chars"] == 0
    assert events[0]["recent_artifact_context"] == {
        "included": False,
        "artifact_count": 0,
        "limit": 5,
        "chars": 0,
        "truncated": False,
    }
    assert events[0]["prompt_breakdown"]["total_chars"] >= events[0]["system_prompt_length"]
    assert events[0]["prompt_breakdown"]["other_chars"] >= 0
    assert "context_debug" in events[0]
    assert events[0]["context_debug"]["prompt_total_chars"] == events[0]["prompt_breakdown"]["total_chars"]
    assert events[0]["context_debug"]["prompt_section_chars"]["conversation_history"] == len("Hello")
    assert events[0]["context_debug"]["context_budget"]["skipped_empty_chunks"] == 0
    assert "total_backend_ms" in events[-2]["timings"]
    assert events[-1]["conversation_id"] == "conv-1"
    assistant_call = mock_save_message.call_args_list[-1]
    assert assistant_call.kwargs["tool_trace"] is None
    mock_checkpoint_conversation.assert_called_once_with("conv-1", "user-1")


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.get_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_includes_previous_assistant_response_for_immediate_history_question(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_get_conversation,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=False)
    current_text = "What was the last sentence of your previous response? Quote it exactly."
    prior_assistant_text = "The final sentence was: preserve source clarity."
    mock_resolve_user.return_value = _fake_user()
    mock_get_conversation.return_value = {
        "id": "conv-1",
        "user_id": "user-1",
        "ended_at": None,
    }
    mock_retrieve.return_value = [
        {
            "chunk_id": "old-last-response",
            "text": "An old unrelated last response answer.",
            "source_type": "conversation",
        }
    ]
    current_user = _fake_message("user", current_text, "msg-current")
    mock_save_message.side_effect = [
        current_user,
        _fake_message("assistant", "preserve source clarity.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "Give me a source-boundary summary.", "msg-prior-user"),
        _fake_message("assistant", prior_assistant_text, "msg-prior-assistant"),
        current_user,
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "preserve source clarity."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="preserve source clarity.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": current_text, "conversation_id": "conv-1"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["retrieval_skipped"] is True
    assert events[0]["retrieval_policy"] == {
        "mode": "skip_memory",
        "reason": "immediate_conversation_reference",
    }
    assert events[0]["chunks_retrieved"] == 0
    assert events[0]["supplied_conversation_id"] == "conv-1"
    assert events[0]["effective_conversation_id"] == "conv-1"
    assert events[0]["conversation_started_reason"] == "reused"
    assert events[0]["history_db_message_count"] == 3
    assert events[0]["history_user_message_count"] == 2
    assert events[0]["history_assistant_message_count"] == 1
    assert events[0]["history_injected_system_message_count"] == 0
    assert events[0]["model_message_count"] == 3
    assert events[0]["history_message_count"] == 3
    assert events[0]["previous_assistant_included"] is True
    assert events[0]["previous_assistant_chars"] == len(prior_assistant_text)
    mock_retrieve.assert_not_called()
    mock_start_conversation.assert_not_called()

    model_messages = mock_loop.call_args.kwargs["messages"]
    assert model_messages == [
        {"role": "user", "content": "Give me a source-boundary summary."},
        {"role": "assistant", "content": prior_assistant_text},
        {"role": "user", "content": current_text},
    ]
    mock_checkpoint_conversation.assert_called_once_with("conv-1", "user-1")


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_checkpoint_failure_does_not_break_response(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.side_effect = RuntimeError("checkpoint failed")
    mock_loop.return_value = iter([
        {"type": "token", "content": "Hello back"},
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

    assert response.status_code == 200
    assert events[-1] == {
        "type": "done",
        "conversation_id": "conv-1",
        "message_id": "msg-assistant",
    }
    assert mock_save_message.call_count == 2
    mock_checkpoint_conversation.assert_called_once_with("conv-1", "user-1")


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.assert_called_once_with("conv-1", "user-1")


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_skips_retrieval_for_direct_moltbook_state_prompt(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_save_message.side_effect = [
        _fake_message("user", "Can you check Moltbook for posts by xkai?", "msg-user"),
        _fake_message("assistant", "I will check Moltbook.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "Can you check Moltbook for posts by xkai?", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I will check Moltbook."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I will check Moltbook.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Can you check Moltbook for posts by xkai?"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["retrieval_skipped"] is True
    assert events[0]["retrieval_policy"] == {
        "mode": "skip_memory",
        "reason": "direct_moltbook_state",
    }
    assert events[0]["chunks_retrieved"] == 0
    assert events[0]["retrieved_chunks"] == []
    mock_retrieve.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_skips_retrieval_for_direct_web_current_prompt(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_save_message.side_effect = [
        _fake_message("user", "Search the web for current SearXNG info", "msg-user"),
        _fake_message("assistant", "I will search.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "Search the web for current SearXNG info", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I will search."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I will search.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Search the web for current SearXNG info"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["retrieval_skipped"] is True
    assert events[0]["retrieval_policy"] == {
        "mode": "skip_memory",
        "reason": "direct_web_current",
    }
    mock_retrieve.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_skips_retrieval_for_context_inspection_prompt(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_save_message.side_effect = [
        _fake_message("user", "What is in your current context?", "msg-user"),
        _fake_message("assistant", "I can describe the current visible context.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "What is in your current context?", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I can describe the current visible context."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I can describe the current visible context.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "What is in your current context?"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["retrieval_skipped"] is True
    assert events[0]["retrieval_policy"] == {
        "mode": "skip_memory",
        "reason": "context_inspection",
    }
    assert events[0]["retrieval_budget"]["input_chunks"] == 0
    mock_retrieve.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_normal_retrieval_still_runs(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = [
        {
            "chunk_id": "chunk-1",
            "text": "Relevant memory.",
            "source_type": "conversation",
        }
    ]
    mock_save_message.side_effect = [
        _fake_message("user", "What did we decide about Moltbook integration?", "msg-user"),
        _fake_message("assistant", "We chose read-only first.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "What did we decide about Moltbook integration?", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "We chose read-only first."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="We chose read-only first.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "What did we decide about Moltbook integration?"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["retrieval_skipped"] is False
    assert events[0]["retrieval_policy"] == {
        "mode": "normal",
        "reason": "normal",
    }
    assert events[0]["chunks_retrieved"] == 1
    assert events[0]["retrieval_budget"]["input_chunks"] == 1
    assert events[0]["retrieval_budget"]["included_chunks"] == 1
    assert events[0]["prompt_budget_warning"] is None
    assert "prompt_breakdown" in events[0]
    assert events[0]["prompt_breakdown"]["tool_descriptions_chars"] > 0
    assert events[0]["prompt_breakdown"]["retrieved_context_chars"] > 0
    assert events[0]["prompt_breakdown"]["conversation_history_chars"] == len(
        "What did we decide about Moltbook integration?"
    )
    assert events[0]["context_debug"]["retrieval"]["sources_by_type"] == {
        "conversation": 1,
    }
    assert events[0]["context_debug"]["retrieval"]["included_chunks"][0]["chunk_id"] == "chunk-1"
    mock_retrieve.assert_called_once_with(
        query="What did we decide about Moltbook integration?",
        active_conversation_id="conv-1",
        max_results=AUTO_RETRIEVAL_RESULTS,
        artifact_intent=False,
    )


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_context_debug_includes_journal_chunk_details(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = [
        {
            "chunk_id": "journal_2026_05_08_chunk_0",
            "text": "Reflection journal text.",
            "metadata": {
                "source_type": "journal",
                "artifact_id": "artifact-1",
                "journal_date": "2026-05-08",
                "title": "Reflection Journal — 2026-05-08",
                "chunk_index": 0,
                "chunk_kind": "journal_content",
            },
            "vector_rank": 1,
            "adjusted_score": 0.5,
        }
    ]
    mock_save_message.side_effect = [
        _fake_message("user", "What did your journal say yesterday?", "msg-user"),
        _fake_message("assistant", "It mentioned source framing.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "What did your journal say yesterday?", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "It mentioned source framing."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="It mentioned source framing.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "What did your journal say yesterday?"},
    )
    events = _stream_lines(response)

    chunk = events[0]["context_debug"]["retrieval"]["included_chunks"][0]
    assert chunk["source_type"] == "journal"
    assert chunk["metadata"]["artifact_id"] == "artifact-1"
    assert chunk["metadata"]["journal_date"] == "2026-05-08"
    assert chunk["metadata"]["chunk_index"] == 0
    assert chunk["journal"]["journal_date"] == "2026-05-08"
    assert chunk["journal"]["chunks_included_for_journal"] == 1
    assert chunk["journal"]["full_journal_included"] is None


@patch("tir.api.routes.build_primary_journal_context")
@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_injects_primary_journal_context_and_keeps_retrieval(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
    mock_build_primary_journal_context,
):
    app.state.registry = FakeRegistry(has_tools=False)
    current_text = "What did your May 8 reflection journal say?"
    journal_context = (
        "[Primary reflection journal source — 2026-05-08]\n\n"
        "This is the journal entry for the requested date. Treat it as the primary source "
        "for questions about that journal. Distinguish what the journal states from later interpretation.\n\n"
        "Journal source text."
    )
    mock_build_primary_journal_context.return_value = (
        journal_context,
        {
            "included": True,
            "journal_date": "2026-05-08",
            "artifact_id": "artifact-journal",
            "path": "journals/2026-05-08.md",
            "chars": len(journal_context),
            "truncated": False,
            "budget_chars": 8000,
            "reason": None,
            "year_inferred": True,
            "duplicate_count": 1,
        },
    )
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = [
        {
            "chunk_id": "conversation-about-journal",
            "text": "A prior conversation about the journal.",
            "source_type": "conversation",
        }
    ]
    mock_save_message.side_effect = [
        _fake_message("user", current_text, "msg-user"),
        _fake_message("assistant", "The journal mentioned source framing.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [_fake_message("user", current_text, "msg-user")]
    mock_loop.return_value = iter([
        {"type": "token", "content": "The journal mentioned source framing."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="The journal mentioned source framing.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": current_text})
    events = _stream_lines(response)

    assert response.status_code == 200
    mock_retrieve.assert_called_once_with(
        query=current_text,
        active_conversation_id="conv-1",
        max_results=AUTO_RETRIEVAL_RESULTS,
        artifact_intent=False,
    )
    model_messages = mock_loop.call_args.kwargs["messages"]
    assert model_messages[0] == {"role": "system", "content": journal_context}
    assert model_messages[1]["content"] == current_text
    assert events[0]["journal_primary_context"]["included"] is True
    assert events[0]["journal_primary_context"]["journal_date"] == "2026-05-08"
    assert events[0]["journal_primary_context"]["artifact_id"] == "artifact-journal"
    assert events[0]["prompt_breakdown"]["journal_primary_context_chars"] == len(journal_context)
    assert events[0]["prompt_breakdown"]["primary_context_chars"] == len(journal_context)
    assert events[0]["context_debug"]["primary_context"]["journal"]["included"] is True
    assert events[0]["context_debug"]["retrieval"]["sources_by_type"] == {
        "conversation": 1,
    }


@patch("tir.api.routes.build_recent_artifacts_context")
@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_injects_recent_artifact_context_for_artifact_prompt(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
    mock_build_recent_artifacts_context,
):
    app.state.registry = FakeRegistry(has_tools=True)
    context = (
        "Recent artifacts available as uploaded source material:\n"
        "- Upload Note, file=upload.md, type=uploaded_file, role=Uploaded source, "
        "origin=User upload, indexing=indexed, status=active, id=artifact"
    )
    mock_build_recent_artifacts_context.return_value = (
        context,
        {
            "included": True,
            "artifact_count": 1,
            "limit": 5,
            "chars": len(context),
            "truncated": False,
        },
    )
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    current_text = "I just uploaded two files, can you see them?"
    mock_save_message.side_effect = [
        _fake_message("user", current_text, "msg-user"),
        _fake_message("assistant", "I can see one recent upload.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", current_text, "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I can see one recent upload."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I can see one recent upload.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": current_text})
    events = _stream_lines(response)

    assert response.status_code == 200
    model_messages = mock_loop.call_args.kwargs["messages"]
    assert model_messages[0] == {"role": "system", "content": context}
    assert model_messages[1]["content"] == current_text
    assert events[0]["recent_artifact_context"]["included"] is True
    assert events[0]["recent_artifact_context"]["artifact_count"] == 1
    assert events[0]["prompt_breakdown"]["recent_artifact_context_chars"] == len(context)
    assert events[0]["prompt_breakdown"]["artifact_context_chars"] == len(context)
    assert events[0]["prompt_breakdown"]["total_chars"] >= (
        events[0]["system_prompt_length"] + len(current_text) + len(context)
    )
    mock_build_recent_artifacts_context.assert_called_once_with(
        user_id="user-1",
        limit=5,
    )
    mock_retrieve.assert_called_once_with(
        query=current_text,
        active_conversation_id="conv-1",
        max_results=AUTO_RETRIEVAL_RESULTS,
        artifact_intent=True,
    )


@patch("tir.api.routes.build_recent_artifacts_context")
@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_does_not_inject_recent_artifact_context_for_unrelated_prompt(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
    mock_build_recent_artifacts_context,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    current_text = "What did we decide about Moltbook integration?"
    mock_save_message.side_effect = [
        _fake_message("user", current_text, "msg-user"),
        _fake_message("assistant", "Read-only first.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", current_text, "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Read-only first."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Read-only first.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": current_text})
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["recent_artifact_context"]["included"] is False
    assert events[0]["prompt_breakdown"]["recent_artifact_context_chars"] == 0
    assert events[0]["prompt_breakdown"]["artifact_context_chars"] == 0
    mock_build_recent_artifacts_context.assert_not_called()
    mock_retrieve.assert_called_once_with(
        query=current_text,
        active_conversation_id="conv-1",
        max_results=AUTO_RETRIEVAL_RESULTS,
        artifact_intent=False,
    )


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_prompt_breakdown_counts_selection_context_separately(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    prior_assistant = _fake_message("assistant", "I found posts.", "msg-prior")
    prior_assistant["tool_trace"] = _selection_trace()
    current_user = _fake_message("user", "read the first one", "msg-user")
    mock_save_message.side_effect = [
        current_user,
        _fake_message("assistant", "I will read it.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        prior_assistant,
        current_user,
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I will read it."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I will read it.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"text": "read the first one"})
    events = _stream_lines(response)

    assert response.status_code == 200
    breakdown = events[0]["prompt_breakdown"]
    assert breakdown["selection_context_chars"] > 0
    assert breakdown["conversation_history_chars"] == len("I found posts.") + len(
        "read the first one"
    )
    model_messages = mock_loop.call_args.kwargs["messages"]
    assert any(
        message["role"] == "system"
        and "[Recent Moltbook Selection]" in message["content"]
        for message in model_messages
    )


@patch("tir.api.routes.build_system_prompt_with_debug")
@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_debug_warns_when_prompt_exceeds_budget(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
    mock_build_system_prompt_with_debug,
):
    app.state.registry = FakeRegistry(has_tools=True)
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_build_system_prompt_with_debug.return_value = (
        "x" * (PROMPT_BUDGET_WARNING_CHARS + 1),
        {
            "system_prompt_chars": PROMPT_BUDGET_WARNING_CHARS + 1,
            "soul_chars": PROMPT_BUDGET_WARNING_CHARS + 1,
            "operational_guidance_chars": 0,
            "tool_descriptions_chars": 0,
            "retrieved_context_chars": 0,
            "situation_chars": 0,
            "other_chars": 0,
            "best_effort": True,
        },
    )
    mock_save_message.side_effect = [
        _fake_message("user", "Please recall this", "msg-user"),
        _fake_message("assistant", "Done.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("user", "Please recall this", "msg-user")
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Done."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Done.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Please recall this"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["system_prompt_length"] == PROMPT_BUDGET_WARNING_CHARS + 1
    assert events[0]["prompt_budget_warning"] == "prompt_chars_over_budget"
    assert events[0]["prompt_breakdown"]["total_chars"] > PROMPT_BUDGET_WARNING_CHARS


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


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    assert events[0]["supplied_conversation_id"] == "old-conv"
    assert events[0]["effective_conversation_id"] == "new-conv"
    assert events[0]["conversation_started_reason"] == "ended_supplied_conversation"
    assert events[-1]["conversation_id"] == "new-conv"
    assert mock_save_message.call_args_list[0].args[0] == "new-conv"
    assert mock_save_message.call_args_list[1].args[0] == "new-conv"


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.get_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_stream_chat_missing_conversation_reports_replacement_reason(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_get_conversation,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    app.state.registry = FakeRegistry(has_tools=False)
    mock_resolve_user.return_value = _fake_user()
    mock_get_conversation.return_value = None
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
        json={"text": "Continue", "conversation_id": "missing-conv"},
    )
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[0]["conversation_id"] == "new-conv"
    assert events[0]["supplied_conversation_id"] == "missing-conv"
    assert events[0]["effective_conversation_id"] == "new-conv"
    assert events[0]["conversation_started_reason"] == "missing_supplied_conversation"
    assert events[-1]["conversation_id"] == "new-conv"


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


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
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
    mock_checkpoint_conversation,
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
    mock_checkpoint_conversation.assert_not_called()
