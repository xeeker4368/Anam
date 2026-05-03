from unittest.mock import patch

from skills.active.web_search.web_search import web_search
from tir.config import SKILLS_DIR
from tir.tools.registry import SkillRegistry


def test_web_search_skill_loads_from_active_directory():
    registry = SkillRegistry.from_directory(SKILLS_DIR)

    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert "memory_search" in tool_names
    assert "web_search" in tool_names


@patch("skills.active.web_search.web_search._search_provider")
def test_web_search_formats_results(mock_search_provider):
    mock_search_provider.return_value = [
        {
            "title": "Example Result",
            "href": "https://www.example.com/path",
            "body": "A compact search snippet.",
        }
    ]

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
    mock_search_provider.assert_called_once_with("current example", 5)


@patch("skills.active.web_search.web_search._search_provider")
def test_web_search_extracts_source_from_url_field(mock_search_provider):
    mock_search_provider.return_value = [
        {
            "title": "Provider Result",
            "url": "https://subdomain.example.org/article",
            "snippet": "Snippet from alternate field names.",
        }
    ]

    result = web_search("alternate fields")

    assert result["results"][0]["url"] == "https://subdomain.example.org/article"
    assert result["results"][0]["snippet"] == "Snippet from alternate field names."
    assert result["results"][0]["source"] == "subdomain.example.org"


@patch("skills.active.web_search.web_search._search_provider")
def test_web_search_caps_max_results(mock_search_provider):
    mock_search_provider.return_value = [
        {"title": f"Result {index}", "href": f"https://example.com/{index}", "body": ""}
        for index in range(12)
    ]

    result = web_search("many results", max_results=99)

    mock_search_provider.assert_called_once_with("many results", 10)
    assert len(result["results"]) == 10


@patch("skills.active.web_search.web_search._search_provider")
def test_web_search_empty_results(mock_search_provider):
    mock_search_provider.return_value = []

    result = web_search("no results")

    assert result == {
        "ok": True,
        "query": "no results",
        "results": [],
    }


@patch("skills.active.web_search.web_search._search_provider")
def test_web_search_provider_exception_returns_error(mock_search_provider):
    mock_search_provider.side_effect = RuntimeError("provider unavailable")

    result = web_search("breaking news")

    assert result["ok"] is False
    assert "web_search provider failed: RuntimeError: provider unavailable" == result["error"]


def test_web_search_empty_query_returns_clear_error():
    result = web_search("   ")

    assert result == {"ok": False, "error": "query is required"}
