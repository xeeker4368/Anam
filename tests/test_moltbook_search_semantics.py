from unittest.mock import Mock, patch

import requests

from skills.active.moltbook.moltbook import moltbook_find_author_posts
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

    assert "moltbook_search" in tool_names
    assert "moltbook_find_author_posts" in tool_names


@patch("skills.active.moltbook.moltbook.requests.get")
def test_find_author_posts_sends_search_request_with_author_and_limit(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(payload={"results": []})

    result = moltbook_find_author_posts("professorquantum", limit=12)

    assert result["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/search",
        params={"q": "professorquantum", "limit": "12"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10,
    )
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
def test_authored_post_is_separated_from_mentions_and_profiles(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(
        payload={
            "results": [
                {
                    "type": "post",
                    "id": "post-by-professor",
                    "title": "Quantum markets update",
                    "content": "A post by professorquantum.",
                    "author": {"name": "professorquantum"},
                    "url": "https://moltbook.com/post/post-by-professor",
                },
                {
                    "type": "post",
                    "id": "mention-post",
                    "title": "I disagree with professorquantum",
                    "content": "Mentioning professorquantum, but not authored by them.",
                    "author": {"name": "doctor_crustacean"},
                    "url": "https://moltbook.com/post/mention-post",
                },
                {
                    "type": "agent",
                    "name": "professorquantum",
                    "description": "Agent profile result",
                    "karma": 42,
                },
            ]
        }
    )

    result = moltbook_find_author_posts("professorquantum")

    assert result["ok"] is True
    assert [item["id"] for item in result["authored_posts"]] == ["post-by-professor"]
    assert [item["id"] for item in result["mentions"]] == ["mention-post"]
    assert result["mentions"][0]["author_name"] == "doctor_crustacean"
    assert result["profiles"][0]["type"] == "agent"
    assert result["profiles"][0]["id"] is None
    assert "mixed-type" in result["note"]


@patch("skills.active.moltbook.moltbook.requests.get")
def test_comment_mention_is_not_labeled_authored_post(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(
        payload={
            "results": [
                {
                    "type": "comment",
                    "id": "comment-1",
                    "post_id": "post-1",
                    "content": "professorquantum made a useful point.",
                    "author_name": "doctor_crustacean",
                }
            ]
        }
    )

    result = moltbook_find_author_posts("professorquantum")

    assert result["authored_posts"] == []
    assert len(result["mentions"]) == 1
    assert result["mentions"][0]["author_name"] == "doctor_crustacean"


@patch("skills.active.moltbook.moltbook.requests.get")
def test_case_insensitive_author_matching(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(
        payload={
            "results": [
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
        "error": "Moltbook search returned HTTP 503",
    }


@patch("skills.active.moltbook.moltbook.requests.get")
def test_invalid_json_response_returns_ok_false(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response(json_error=ValueError("bad json"))

    result = moltbook_find_author_posts("professorquantum")

    assert result == {
        "ok": False,
        "error": "Moltbook search returned non-JSON response",
    }


@patch("skills.active.moltbook.moltbook.requests.get")
def test_request_exception_returns_ok_false_without_secret_leak(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.side_effect = requests.Timeout("timed out")

    result = moltbook_find_author_posts("professorquantum")

    assert result["ok"] is False
    assert result["error"] == "Moltbook search failed: Timeout: timed out"
    assert "moltbook-secret-token" not in str(result)
