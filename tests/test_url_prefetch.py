import json
from dataclasses import dataclass
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import tir.api.routes as routes_mod
from tir.engine.url_prefetch import (
    extract_http_urls,
    get_url_prefetch_candidate,
    has_url_content_intent,
)


@dataclass
class FakeLoopResult:
    final_content: str | None
    tool_trace: list[dict]
    terminated_reason: str
    iterations: int
    error: str | None = None


class FakeRegistry:
    def __init__(self, envelope=None):
        self.envelope = envelope or {
            "ok": True,
            "value": {
                "ok": True,
                "url": "https://example.com/article",
                "title": "Example",
                "text": "Fetched page text.",
                "truncated": False,
                "source": "example.com",
            },
            "normalized_args": {"url": "https://example.com/article"},
        }
        self.dispatch = Mock(return_value=self.envelope)

    def has_tools(self):
        return True

    def list_tool_descriptions(self):
        return "You have access to the following tools:\n- web_fetch: Fetch a page"

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
        "timestamp": "2026-05-03T12:00:00+00:00",
    }


def test_extract_http_urls_strips_common_trailing_punctuation():
    text = "Read https://example.com/article), then https://example.org/path."

    assert extract_http_urls(text) == [
        "https://example.com/article",
        "https://example.org/path",
    ]


def test_url_prefetch_candidate_requires_content_intent():
    assert (
        get_url_prefetch_candidate("Summarize this URL: https://example.com/article")
        == "https://example.com/article"
    )
    assert (
        get_url_prefetch_candidate("Here is a URL I may use later: https://example.com")
        is None
    )


def test_url_content_intent_covers_detail_questions():
    assert has_url_content_intent(
        "From this URL https://example.com can you tell me which states were involved?"
    )
    assert has_url_content_intent(
        "Does this page mention deployment requirements? https://example.com"
    )


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_url_content_question_prefetches_before_model_tokens(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    registry = FakeRegistry()
    routes_mod.app.state.registry = registry
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Summarize", "msg-user"),
        _fake_message("assistant", "Fetched summary.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message(
            "user",
            "Can you summarize this URL: https://example.com/article",
            "msg-user",
        )
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Fetched summary."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Fetched summary.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Can you summarize this URL: https://example.com/article"},
    )
    events = _stream_lines(response)

    assert [event["type"] for event in events] == [
        "debug",
        "tool_call",
        "tool_result",
        "token",
        "debug_update",
        "done",
    ]
    assert events[1] == {
        "type": "tool_call",
        "name": "web_fetch",
        "arguments": {"url": "https://example.com/article"},
    }
    assert events[2]["name"] == "web_fetch"
    assert events[2]["ok"] is True
    rendered_result = json.loads(events[2]["result"])
    assert rendered_result["ok"] is True
    assert rendered_result["text"] == "Fetched page text."
    assert events[-2]["timings"]["tool_call_count"] == 1

    registry.dispatch.assert_called_once_with(
        "web_fetch",
        {"url": "https://example.com/article"},
    )
    model_messages = mock_loop.call_args.kwargs["messages"]
    assert model_messages[-2]["tool_calls"][0]["function"]["name"] == "web_fetch"
    assert model_messages[-1]["role"] == "tool"
    assert json.loads(model_messages[-1]["content"])["text"] == "Fetched page text."

    assistant_call = mock_save_message.call_args_list[-1]
    persisted_trace = json.loads(assistant_call.kwargs["tool_trace"])
    assert persisted_trace[0]["phase"] == "url_prefetch"
    assert persisted_trace[0]["tool_calls"][0]["name"] == "web_fetch"
    assert json.loads(persisted_trace[0]["tool_results"][0]["rendered"])["text"] == (
        "Fetched page text."
    )


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_failed_web_fetch_result_is_passed_to_model(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    registry = FakeRegistry(
        envelope={
            "ok": True,
            "value": {
                "ok": False,
                "error": "web_fetch rejected localhost URLs",
                "url": "http://localhost/page",
            },
            "normalized_args": {"url": "http://localhost/page"},
        }
    )
    routes_mod.app.state.registry = registry
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Fetch", "msg-user"),
        _fake_message("assistant", "I could not fetch it.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message(
            "user",
            "What does this page say? http://localhost/page",
            "msg-user",
        )
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "I could not fetch it."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="I could not fetch it.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "What does this page say? http://localhost/page"},
    )
    events = _stream_lines(response)

    assert events[2]["type"] == "tool_result"
    assert events[2]["ok"] is False
    rendered_result = json.loads(events[2]["result"])
    assert rendered_result == {
        "ok": False,
        "error": "web_fetch rejected localhost URLs",
        "url": "http://localhost/page",
    }

    model_messages = mock_loop.call_args.kwargs["messages"]
    assert json.loads(model_messages[-1]["content"])["error"] == (
        "web_fetch rejected localhost URLs"
    )


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_generic_url_mention_does_not_force_fetch(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    registry = FakeRegistry()
    routes_mod.app.state.registry = registry
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Store URL", "msg-user"),
        _fake_message("assistant", "Noted.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message(
            "user",
            "Here is a URL I may use later: https://example.com",
            "msg-user",
        )
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Noted."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Noted.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/chat/stream",
        json={"text": "Here is a URL I may use later: https://example.com"},
    )
    events = _stream_lines(response)

    assert [event["type"] for event in events] == [
        "debug",
        "token",
        "debug_update",
        "done",
    ]
    registry.dispatch.assert_not_called()


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_prefetch_uses_first_url_only(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    registry = FakeRegistry(
        envelope={
            "ok": True,
            "value": {"ok": True, "text": "First URL text."},
            "normalized_args": {"url": "https://first.example/article"},
        }
    )
    routes_mod.app.state.registry = registry
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "Compare", "msg-user"),
        _fake_message("assistant", "First only.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message(
            "user",
            (
                "Summarize https://first.example/article and "
                "https://second.example/article"
            ),
            "msg-user",
        )
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "First only."},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="First only.",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(routes_mod.app)
    client.post(
        "/api/chat/stream",
        json={
            "text": (
                "Summarize https://first.example/article and "
                "https://second.example/article"
            )
        },
    )

    registry.dispatch.assert_called_once_with(
        "web_fetch",
        {"url": "https://first.example/article"},
    )
