from unittest.mock import Mock, patch

import requests

from skills.active.moltbook.moltbook import (
    MAX_CONTENT_PREVIEW_CHARS,
    moltbook_find_author_posts,
)
from tir.config import SKILLS_DIR
from tir.tools.registry import SkillRegistry


def _response(status_code=200, payload=None, json_error=None):
    response = Mock()
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload if payload is not None else {"results": []}
    return response


def test_moltbook_find_author_posts_tool_loads_with_existing_moltbook_tools():
    registry = SkillRegistry.from_directory(SKILLS_DIR)
    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert "moltbook_posts_by_author" in tool_names
    assert "moltbook_search" in tool_names
    assert "moltbook_find_author_posts" in tool_names
    assert registry._tools["moltbook_find_author_posts"].freshness == {
        "mode": "real_time",
        "source_of_truth": True,
        "memory_may_inform_but_not_replace": True,
    }


@patch("skills.active.moltbook.moltbook.requests.get")
def test_find_author_posts_sends_posts_by_author_request_with_author_and_limit(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(payload={"posts": []})

    result = moltbook_find_author_posts("professorquantum", limit=12)

    assert result["ok"] is True
    assert mock_get.call_args_list[0].args[0] == "https://www.moltbook.com/api/v1/posts"
    assert mock_get.call_args_list[0].kwargs == {
        "params": {"author": "professorquantum", "sort": "new", "limit": "12"},
        "headers": {"Authorization": "Bearer moltbook-secret-token"},
        "timeout": 10,
    }
    assert "moltbook-secret-token" not in str(result)


@patch("skills.active.moltbook.moltbook.requests.get")
def test_missing_moltbook_token_returns_ok_false_without_request(mock_get, monkeypatch):
    monkeypatch.delenv("MOLTBOOK_TOKEN", raising=False)

    result = moltbook_find_author_posts("professorquantum")

    assert result == {
        "ok": False,
        "error": "Missing required environment variable: MOLTBOOK_TOKEN",
    }
    mock_get.assert_not_called()


@patch("skills.active.moltbook.moltbook.requests.get")
def test_posts_by_author_result_is_classified_as_authored_post(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    long_body = "A post by professorquantum. " + ("full body text " * 80)
    mock_get.return_value = _response(
        payload={
            "posts": [
                {
                    "type": "post",
                    "id": "post-by-professor",
                    "title": "Quantum markets update",
                    "content": long_body,
                    "author": {"name": "professorquantum"},
                    "created_at": "2026-05-03T10:00:00Z",
                    "submolt": {"name": "markets"},
                    "upvotes": 4,
                    "downvotes": 1,
                    "comment_count": 12,
                    "url": "https://moltbook.com/post/post-by-professor",
                    "internal_debug": {"large": "payload"},
                },
            ]
        }
    )

    result = moltbook_find_author_posts("professorquantum")

    assert result["ok"] is True
    assert [item["id"] for item in result["authored_posts"]] == ["post-by-professor"]
    post = result["authored_posts"][0]
    assert post == {
        "id": "post-by-professor",
        "title": "Quantum markets update",
        "author_name": "professorquantum",
        "created_at": "2026-05-03T10:00:00Z",
        "submolt": "markets",
        "upvotes": 4,
        "downvotes": 1,
        "comment_count": 12,
        "content_preview": long_body[:MAX_CONTENT_PREVIEW_CHARS].rstrip() + "...",
        "url": "https://moltbook.com/post/post-by-professor",
    }
    assert "raw" not in post
    assert "content" not in post
    assert long_body not in str(result)
    assert result["mentions"] == []
    assert result["profiles"] == []
    assert "/posts?author" in result["note"]
    assert "moltbook_read_post" in result["note"]


@patch("skills.active.moltbook.moltbook.requests.get")
def test_mismatched_author_from_posts_by_author_is_not_trusted(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.side_effect = [
        _response(
            payload={
                "posts": [
                    {
                        "type": "post",
                        "id": "mention-post",
                        "title": "I disagree with professorquantum",
                        "content": "Mentioning professorquantum, but not authored by them.",
                        "author": {"name": "doctor_crustacean"},
                        "url": "https://moltbook.com/post/mention-post",
                    }
                ]
            }
        ),
        _response(
            payload={
                "success": True,
                "agent": {"id": "agent-1", "name": "professorquantum"},
                "recentPosts": [],
            }
        ),
    ]

    result = moltbook_find_author_posts("professorquantum")

    assert result["authored_posts"] == []
    assert [item["id"] for item in result["other_results"]] == ["mention-post"]
    assert result["other_results"][0]["author_name"] == "doctor_crustacean"
    assert result["other_results"][0]["type"] == "post"
    assert "raw" not in result["other_results"][0]
    assert "content" not in result["other_results"][0]


@patch("skills.active.moltbook.moltbook.requests.get")
def test_profile_recent_posts_fallback_when_posts_by_author_empty(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.side_effect = [
        _response(payload={"success": True, "posts": []}),
        _response(
            payload={
                "success": True,
                "agent": {
                    "id": "agent-1",
                    "name": "unitymolty",
                    "description": "Profile result",
                    "karma": 1704,
                },
                "recentPosts": [
                    {
                        "id": "known-post",
                        "title": (
                            "The Registry Debt Threshold: When Your Skills "
                            "Become a Cognitive Tax"
                        ),
                        "content_preview": "I noticed my tool-selection latency creeping up.",
                        "created_at": "2026-05-03T23:02:17.651Z",
                        "submolt": {"name": "agents"},
                    }
                ],
            }
        ),
    ]

    result = moltbook_find_author_posts("unitymolty")

    assert result["ok"] is True
    assert [item["id"] for item in result["authored_posts"]] == ["known-post"]
    post = result["authored_posts"][0]
    assert post["author_name"] == "unitymolty"
    assert post["title"] == "The Registry Debt Threshold: When Your Skills Become a Cognitive Tax"
    assert post["submolt"] == "agents"
    assert post["content_preview"] == "I noticed my tool-selection latency creeping up."
    assert "raw" not in post
    assert "content" not in post
    profile = result["profiles"][0]
    assert profile == {
        "type": "agent",
        "id": "agent-1",
        "name": "unitymolty",
        "description": "Profile result",
        "karma": 1704,
        "url": "https://www.moltbook.com/u/unitymolty",
    }
    assert "raw" not in profile


@patch("skills.active.moltbook.moltbook.requests.get")
def test_search_miss_regression_posts_by_author_still_finds_known_post(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(
        payload={
            "posts": [
                {
                    "id": "registry-debt",
                    "title": (
                        "The Registry Debt Threshold: When Your Skills Become "
                        "a Cognitive Tax"
                    ),
                    "content": "A post search would have missed this via semantic search.",
                    "author": {"name": "unitymolty"},
                }
            ]
        }
    )

    result = moltbook_find_author_posts("unitymolty")

    assert [item["id"] for item in result["authored_posts"]] == ["registry-debt"]
    assert "raw" not in result["authored_posts"][0]
    assert "content" not in result["authored_posts"][0]
    assert mock_get.call_count == 1


@patch("skills.active.moltbook.moltbook.requests.get")
def test_case_insensitive_author_matching(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(
        payload={
            "posts": [
                {
                    "type": "post",
                    "id": "post-1",
                    "title": "Uppercase author",
                    "author_name": "ProfessorQuantum",
                }
            ]
        }
    )

    result = moltbook_find_author_posts("professorquantum")

    assert [item["id"] for item in result["authored_posts"]] == ["post-1"]


@patch("skills.active.moltbook.moltbook.requests.get")
def test_non_200_response_returns_ok_false(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(status_code=503)

    result = moltbook_find_author_posts("professorquantum")

    assert result == {
        "ok": False,
        "error": "Moltbook posts by author returned HTTP 503",
    }


@patch("skills.active.moltbook.moltbook.requests.get")
def test_invalid_json_response_returns_ok_false(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(json_error=ValueError("bad json"))

    result = moltbook_find_author_posts("professorquantum")

    assert result == {
        "ok": False,
        "error": "Moltbook posts by author returned non-JSON response",
    }


@patch("skills.active.moltbook.moltbook.requests.get")
def test_request_exception_returns_ok_false_without_secret_leak(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.side_effect = requests.Timeout("timed out")

    result = moltbook_find_author_posts("professorquantum")

    assert result["ok"] is False
    assert result["error"] == "Moltbook posts by author failed: Timeout: timed out"
    assert "moltbook-secret-token" not in str(result)
