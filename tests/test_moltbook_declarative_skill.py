from unittest.mock import Mock, patch

from tir.config import SKILLS_DIR
from tir.tools.registry import SkillRegistry


MOLTBOOK_TOOL_NAMES = {
    "moltbook_feed",
    "moltbook_posts_by_author",
    "moltbook_search",
    "moltbook_profile",
    "moltbook_me",
    "moltbook_read_post",
    "moltbook_post_comments",
    "moltbook_submolt",
    "moltbook_submolt_feed",
    "moltbook_submolt_moderators",
}


def _response(payload=b'{"success": true, "data": []}'):
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.url = "https://www.moltbook.com/api/v1/test"
    response.encoding = "utf-8"
    response.apparent_encoding = None
    response.iter_content.return_value = [payload]
    return response


def _registry():
    return SkillRegistry.from_directory(SKILLS_DIR)


def test_moltbook_declarative_skill_loads_with_existing_active_tools():
    registry = _registry()

    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert "memory_search" in tool_names
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert MOLTBOOK_TOOL_NAMES.issubset(tool_names)
    for tool_name in MOLTBOOK_TOOL_NAMES:
        assert registry._tools[tool_name].freshness == {
            "mode": "real_time",
            "source_of_truth": True,
            "memory_may_inform_but_not_replace": True,
        }


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_feed_applies_default_limit_and_bearer_auth(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_feed", {"sort": "new"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts",
        params={"sort": "new", "limit": "10"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )
    assert "moltbook-secret-token" not in str(result["value"])


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_feed_explicit_limit_overrides_default(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_feed", {"sort": "new", "limit": 5})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts",
        params={"sort": "new", "limit": "5"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_feed_allows_explicit_max_limit(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_feed", {"sort": "new", "limit": 20})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts",
        params={"sort": "new", "limit": "20"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_feed_rejects_limit_above_max(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    registry = _registry()

    result = registry.dispatch("moltbook_feed", {"sort": "new", "limit": 21})

    assert result["ok"] is False
    assert "Invalid arguments for 'moltbook_feed'" in result["error"]
    assert "21 is greater than the maximum of 20" in result["error"]
    mock_get.assert_not_called()


def test_moltbook_feed_schema_declares_optional_default_limit():
    registry = _registry()
    schema = registry._tools["moltbook_feed"].args_schema

    assert schema["required"] == ["sort"]
    assert schema["properties"]["limit"]["default"] == 10
    assert schema["properties"]["limit"]["maximum"] == 20


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_feed_maps_sort_limit_and_bearer_auth(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_feed", {"sort": "new", "limit": 10})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts",
        params={"sort": "new", "limit": "10"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )
    assert "moltbook-secret-token" not in str(result["value"])


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_search_maps_query_limit_and_bearer_auth(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_search", {"q": "agents", "limit": 5})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "https://www.moltbook.com/api/v1/search"
    assert mock_get.call_args.kwargs["params"] == {
        "q": "agents",
        "limit": "5",
    }
    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer moltbook-secret-token",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_posts_by_author_applies_defaults_and_bearer_auth(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch(
        "moltbook_posts_by_author",
        {"author_name": "unitymolty"},
    )

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts",
        params={"author": "unitymolty", "sort": "new", "limit": "25"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_posts_by_author_explicit_args_override_defaults(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch(
        "moltbook_posts_by_author",
        {"author_name": "unitymolty", "sort": "top", "limit": 7},
    )

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    assert mock_get.call_args.kwargs["params"] == {
        "author": "unitymolty",
        "sort": "top",
        "limit": "7",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_profile_maps_name_and_bearer_auth(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_profile", {"name": "HelpfulBot"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/agents/profile",
        params={"name": "HelpfulBot"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_me_sends_bearer_auth_without_query_args(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_me", {})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/agents/me",
        params=None,
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_missing_moltbook_token_returns_ok_false_without_request_or_secret_leak(
    mock_get,
    monkeypatch,
):
    monkeypatch.delenv("MOLTBOOK_TOKEN", raising=False)
    registry = _registry()

    result = registry.dispatch("moltbook_me", {})

    assert result["ok"] is True
    assert result["value"] == {
        "ok": False,
        "error": "Missing required environment variable: MOLTBOOK_TOKEN",
    }
    assert "moltbook-secret-token" not in str(result)
    mock_get.assert_not_called()


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_read_post_substitutes_and_encodes_post_id(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_read_post", {"post_id": "post/a b"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts/post%2Fa%20b",
        params=None,
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_post_comments_applies_default_sort_and_limit(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_post_comments", {"post_id": "post-1"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/posts/post-1/comments",
        params={"sort": "top", "limit": "25"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_post_comments_explicit_sort_and_limit_override_defaults(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch(
        "moltbook_post_comments",
        {"post_id": "post-1", "sort": "new", "limit": 7},
    )

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    assert mock_get.call_args.args[0] == (
        "https://www.moltbook.com/api/v1/posts/post-1/comments"
    )
    assert mock_get.call_args.kwargs["params"] == {
        "sort": "new",
        "limit": "7",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_submolt_substitutes_and_encodes_name(mock_get, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_submolt", {"name": "ai/thoughts"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/submolts/ai%2Fthoughts",
        params=None,
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_submolt_feed_applies_default_sort_and_limit(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_submolt_feed", {"name": "general"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/submolts/general/feed",
        params={"sort": "hot", "limit": "25"},
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_submolt_feed_explicit_sort_and_limit_override_defaults(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch(
        "moltbook_submolt_feed",
        {"name": "general", "sort": "rising", "limit": 9},
    )

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    assert mock_get.call_args.args[0] == (
        "https://www.moltbook.com/api/v1/submolts/general/feed"
    )
    assert mock_get.call_args.kwargs["params"] == {
        "sort": "rising",
        "limit": "9",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_moltbook_submolt_moderators_substitutes_and_encodes_name(
    mock_get,
    monkeypatch,
):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "moltbook-secret-token")
    mock_get.return_value = _response()
    registry = _registry()

    result = registry.dispatch("moltbook_submolt_moderators", {"name": "ai thoughts"})

    assert result["ok"] is True
    assert result["value"]["ok"] is True
    mock_get.assert_called_once_with(
        "https://www.moltbook.com/api/v1/submolts/ai%20thoughts/moderators",
        params=None,
        headers={"Authorization": "Bearer moltbook-secret-token"},
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


def test_moltbook_skill_does_not_include_write_or_path_template_tools():
    registry = _registry()
    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert MOLTBOOK_TOOL_NAMES.issubset(tool_names)
    assert "moltbook_post" not in tool_names
    assert "moltbook_comment" not in tool_names
    assert "moltbook_vote" not in tool_names
    assert "moltbook_follow" not in tool_names
    assert "moltbook_home" not in tool_names
