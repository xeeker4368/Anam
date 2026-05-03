from unittest.mock import Mock, patch

import requests

from skills.active.web_search.web_search import web_search
from tir.config import SEARXNG_URL, SKILLS_DIR, WEB_SEARCH_TIMEOUT_SECONDS
from tir.tools.registry import SkillRegistry


def _response(status_code=200, payload=None, json_error=None):
    response = Mock()
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload if payload is not None else {"results": []}
    return response


def test_web_search_skill_loads_from_active_directory():
    registry = SkillRegistry.from_directory(SKILLS_DIR)

    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert "memory_search" in tool_names
    assert "web_search" in tool_names


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_calls_searxng_with_url_params_and_timeout(mock_get):
    mock_get.return_value = _response(payload={"results": []})

    result = web_search("current example", max_results=5)

    assert result == {
        "ok": True,
        "query": "current example",
        "results": [],
    }
    mock_get.assert_called_once_with(
        f"{SEARXNG_URL}/search",
        params={"q": "current example", "format": "json"},
        timeout=WEB_SEARCH_TIMEOUT_SECONDS,
    )


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_formats_searxng_results(mock_get):
    mock_get.return_value = _response(
        payload={
            "results": [
                {
                    "title": "Example Result",
                    "url": "https://www.example.com/path",
                    "content": "A compact search snippet.",
                }
            ]
        }
    )

    result = web_search("current example", max_results=5)

    assert result == {
        "ok": True,
        "query": "current example",
        "results": [
            {
                "title": "Example Result",
                "url": "https://www.example.com/path",
                "snippet": "A compact search snippet.",
                "source": "example.com",
            }
        ],
    }


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_extracts_source_and_snippet_fallback(mock_get):
    mock_get.return_value = _response(
        payload={
            "results": [
                {
                    "title": "Provider Result",
                    "url": "https://subdomain.example.org/article",
                    "snippet": "Snippet from fallback field.",
                }
            ]
        }
    )

    result = web_search("alternate fields")

    assert result["results"][0]["url"] == "https://subdomain.example.org/article"
    assert result["results"][0]["snippet"] == "Snippet from fallback field."
    assert result["results"][0]["source"] == "subdomain.example.org"


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_caps_max_results(mock_get):
    mock_get.return_value = _response(
        payload={
            "results": [
                {
                    "title": f"Result {index}",
                    "url": f"https://example.com/{index}",
                    "content": "",
                }
                for index in range(12)
            ]
        }
    )

    result = web_search("many results", max_results=99)

    assert len(result["results"]) == 10


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_empty_results(mock_get):
    mock_get.return_value = _response(payload={"results": []})

    result = web_search("no results")

    assert result == {
        "ok": True,
        "query": "no results",
        "results": [],
    }


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_timeout_exception_returns_error(mock_get):
    mock_get.side_effect = requests.Timeout("provider timed out")

    result = web_search("breaking news")

    assert result["ok"] is False
    assert result["error"] == "web_search provider failed: Timeout: provider timed out"


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_connection_exception_returns_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("provider unavailable")

    result = web_search("breaking news")

    assert result["ok"] is False
    assert result["error"] == (
        "web_search provider failed: ConnectionError: provider unavailable"
    )


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_non_200_returns_error(mock_get):
    mock_get.return_value = _response(status_code=503, payload={"results": []})

    result = web_search("breaking news")

    assert result == {"ok": False, "error": "SearXNG returned HTTP 503"}


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_invalid_json_returns_error(mock_get):
    mock_get.return_value = _response(json_error=ValueError("not json"))

    result = web_search("breaking news")

    assert result == {"ok": False, "error": "SearXNG returned non-JSON response"}


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_missing_results_returns_error(mock_get):
    mock_get.return_value = _response(payload={"not_results": []})

    result = web_search("breaking news")

    assert result == {"ok": False, "error": "SearXNG response missing results list"}


@patch("skills.active.web_search.web_search.requests.get")
def test_web_search_non_list_results_returns_error(mock_get):
    mock_get.return_value = _response(payload={"results": {"bad": "shape"}})

    result = web_search("breaking news")

    assert result == {"ok": False, "error": "SearXNG response missing results list"}


def test_web_search_empty_query_returns_clear_error():
    result = web_search("   ")

    assert result == {"ok": False, "error": "query is required"}
