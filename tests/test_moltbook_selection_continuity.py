import json
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

import tir.api.routes as routes_mod
from tir.engine.agent_loop import run_agent_loop
from tir.engine.tool_trace_context import (
    build_moltbook_authored_posts_selection,
    build_moltbook_selection_context,
)
from tir.tools.registry import SkillRegistry, ToolDefinition


@dataclass
class FakeLoopResult:
    final_content: str | None
    tool_trace: list[dict]
    terminated_reason: str
    iterations: int
    error: str | None = None


class FakeRegistry:
    def has_tools(self):
        return False

    def list_tool_descriptions(self):
        return ""

    def list_tools(self):
        return []


def _fake_user():
    return {"id": "user-1", "name": "Lyle", "role": "admin"}


def _fake_message(role, content, message_id, *, tool_trace=None):
    return {
        "id": message_id,
        "conversation_id": "conv-1",
        "role": role,
        "content": content,
        "tool_trace": tool_trace,
        "timestamp": "2026-05-04T12:00:00+00:00",
    }


def _stream_lines(response):
    return [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]


def _selection_trace(author="xkai", *, post_id="post-1", title="Token Budget Notes"):
    return json.dumps([
        {
            "iteration": 0,
            "tool_calls": [
                {
                    "name": "moltbook_find_author_posts",
                    "arguments": {"author_name": author},
                }
            ],
            "tool_results": [
                {
                    "tool_name": "moltbook_find_author_posts",
                    "ok": True,
                    "rendered": '{"ok": true}',
                    "selection": {
                        "kind": "moltbook_authored_posts",
                        "tool_name": "moltbook_find_author_posts",
                        "author_name": author,
                        "posts": [
                            {
                                "index": 1,
                                "id": post_id,
                                "title": title,
                                "author_name": author,
                                "created_at": "2026-05-04T01:00:00Z",
                                "submolt": "agents",
                            }
                        ],
                    },
                }
            ],
        }
    ])


def _make_tool_call_chunks(tool_name: str, arguments) -> list[dict]:
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


def _make_text_chunks(text: str) -> list[dict]:
    return [
        {"message": {"role": "assistant", "content": text}, "done": False},
        {"message": {"role": "assistant", "content": ""}, "done": True},
    ]


def _moltbook_registry():
    def fake_find_author_posts(author_name: str, limit: int = 10):
        return {
            "ok": True,
            "author_name": author_name,
            "authored_posts": [
                {
                    "id": "post-1",
                    "title": "Token Budget Notes",
                    "author_name": author_name,
                    "created_at": "2026-05-04T01:00:00Z",
                    "submolt": "agents",
                    "content_preview": "Short preview",
                    "raw": {"full": "must not persist in selection"},
                }
            ],
            "mentions": [],
            "profiles": [],
            "other_results": [],
            "note": "compact",
        }

    registry = SkillRegistry()
    registry._tools["moltbook_find_author_posts"] = ToolDefinition(
        name="moltbook_find_author_posts",
        description="Find author posts",
        args_schema={
            "type": "object",
            "properties": {
                "author_name": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["author_name"],
        },
        function=fake_find_author_posts,
        skill_name="moltbook",
    )
    registry._tool_to_skill["moltbook_find_author_posts"] = "moltbook"
    return registry


def test_helper_builds_compact_selection_and_ignores_content_raw_fields():
    result = {
        "author_name": "xkai",
        "authored_posts": [
            {
                "id": "post-1",
                "title": "Token Budget Notes",
                "author_name": "xkai",
                "created_at": "2026-05-04T01:00:00Z",
                "submolt": "agents",
                "content_preview": "short preview",
                "content": "full content should not appear",
                "raw": {"payload": "should not appear"},
            }
        ],
    }

    selection = build_moltbook_authored_posts_selection(result)

    assert selection == {
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
    assert "full content" not in str(selection)
    assert "raw" not in str(selection)


def test_helper_uses_latest_selection_and_limits_to_10_posts():
    old_trace = _selection_trace("old-author", post_id="old-post", title="Old Post")
    latest_selection = {
        "kind": "moltbook_authored_posts",
        "tool_name": "moltbook_find_author_posts",
        "author_name": "new-author",
        "posts": [
            {
                "index": i,
                "id": f"post-{i}",
                "title": f"Post {i}",
                "author_name": "new-author",
                "created_at": "2026-05-04T01:00:00Z",
                "submolt": "agents",
            }
            for i in range(1, 13)
        ],
    }
    latest_trace = json.dumps([
        {
            "tool_results": [
                {
                    "tool_name": "moltbook_find_author_posts",
                    "ok": True,
                    "selection": latest_selection,
                }
            ]
        }
    ])

    context = build_moltbook_selection_context([
        _fake_message("assistant", "old", "msg-old", tool_trace=old_trace),
        _fake_message("assistant", "new", "msg-new", tool_trace=latest_trace),
    ])

    assert "Author: new-author" in context
    assert "id=post-1" in context
    assert "id=post-10" in context
    assert "id=post-11" not in context
    assert "old-post" not in context


def test_helper_returns_none_without_moltbook_selection_trace():
    context = build_moltbook_selection_context([
        _fake_message("user", "read the first one", "msg-user"),
        _fake_message("assistant", "No tools here", "msg-assistant"),
    ])

    assert context is None


@patch("tir.engine.agent_loop.chat_completion_stream_with_tools")
def test_agent_loop_persists_compact_moltbook_selection_metadata(mock_stream):
    mock_stream.side_effect = [
        iter(_make_tool_call_chunks(
            "moltbook_find_author_posts",
            {"author_name": "xkai"},
        )),
        iter(_make_text_chunks("I found posts.")),
    ]
    registry = _moltbook_registry()

    events = list(run_agent_loop(
        system_prompt="test",
        messages=[{"role": "user", "content": "find posts by xkai"}],
        registry=registry,
        iteration_limit=5,
        ollama_host="http://fake",
        model="test-model",
    ))

    trace = events[-1]["result"].tool_trace
    selection = trace[0]["tool_results"][0]["selection"]
    assert selection["posts"] == [
        {
            "index": 1,
            "id": "post-1",
            "title": "Token Budget Notes",
            "author_name": "xkai",
            "created_at": "2026-05-04T01:00:00Z",
            "submolt": "agents",
        }
    ]
    assert "raw" not in str(selection)
    assert "content_preview" not in str(selection)


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_routes_inject_selection_context_before_current_user_message(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    routes_mod.app.state.registry = FakeRegistry()
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "read the first one", "msg-current-user"),
        _fake_message("assistant", "I will read it.", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message(
            "assistant",
            "I found posts.",
            "msg-prior-assistant",
            tool_trace=_selection_trace(),
        ),
        _fake_message("user", "read the first one", "msg-current-user"),
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

    client = TestClient(routes_mod.app)
    response = client.post("/api/chat/stream", json={"text": "read the first one"})
    events = _stream_lines(response)

    assert response.status_code == 200
    assert events[-1]["type"] == "done"
    model_messages = mock_loop.call_args.kwargs["messages"]
    current_index = next(
        index
        for index, message in enumerate(model_messages)
        if message["content"] == "read the first one"
    )
    injected = model_messages[current_index - 1]
    assert injected["role"] == "system"
    assert "[Recent Moltbook Selection]" in injected["content"]
    assert "id=post-1" in injected["content"]
    assert "title=Token Budget Notes" in injected["content"]


@patch("tir.api.routes.checkpoint_conversation")
@patch("tir.api.routes.save_message")
@patch("tir.api.routes.get_conversation_messages")
@patch("tir.api.routes.start_conversation")
@patch("tir.api.routes.update_user_last_seen")
@patch("tir.api.routes.retrieve")
@patch("tir.api.routes._resolve_user")
@patch("tir.api.routes.run_agent_loop")
def test_routes_do_not_inject_context_without_selection_trace(
    mock_loop,
    mock_resolve_user,
    mock_retrieve,
    mock_update_last_seen,
    mock_start_conversation,
    mock_get_messages,
    mock_save_message,
    mock_checkpoint_conversation,
):
    routes_mod.app.state.registry = FakeRegistry()
    mock_resolve_user.return_value = _fake_user()
    mock_start_conversation.return_value = "conv-1"
    mock_retrieve.return_value = []
    mock_save_message.side_effect = [
        _fake_message("user", "read the first one", "msg-current-user"),
        _fake_message("assistant", "Which one?", "msg-assistant"),
    ]
    mock_get_messages.return_value = [
        _fake_message("assistant", "No selection here.", "msg-prior-assistant"),
        _fake_message("user", "read the first one", "msg-current-user"),
    ]
    mock_loop.return_value = iter([
        {"type": "token", "content": "Which one?"},
        {
            "type": "done",
            "result": FakeLoopResult(
                final_content="Which one?",
                tool_trace=[],
                terminated_reason="complete",
                iterations=1,
            ),
        },
    ])

    client = TestClient(routes_mod.app)
    response = client.post("/api/chat/stream", json={"text": "read the first one"})

    assert response.status_code == 200
    model_messages = mock_loop.call_args.kwargs["messages"]
    assert all("[Recent Moltbook Selection]" not in m["content"] for m in model_messages)
