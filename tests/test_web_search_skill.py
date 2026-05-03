from unittest.mock import Mock, patch

import requests

from skills.active.web_search.web_search import (
    FETCH_HEADERS,
    web_fetch,
    web_search,
)
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


def _fetch_response(
    status_code=200,
    content=b"<html><body>Readable text</body></html>",
    headers=None,
    encoding="utf-8",
    apparent_encoding=None,
):
    response = Mock()
    response.status_code = status_code
    response.headers = headers if headers is not None else {"Content-Type": "text/html"}
    response.encoding = encoding
    response.apparent_encoding = apparent_encoding
    response.iter_content.return_value = [content]
    return response


def test_web_search_skill_loads_from_active_directory():
    registry = SkillRegistry.from_directory(SKILLS_DIR)

    tool_names = {tool["function"]["name"] for tool in registry.list_tools()}

    assert "memory_search" in tool_names
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names


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


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_non_http_urls_without_request(mock_get):
    result = web_fetch("ftp://example.com/file")

    assert result == {
        "ok": False,
        "error": "web_fetch only supports http and https URLs",
        "url": "ftp://example.com/file",
    }
    mock_get.assert_not_called()


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_localhost_without_request(mock_get):
    result = web_fetch("http://localhost/page")

    assert result == {
        "ok": False,
        "error": "web_fetch rejects localhost URLs",
        "url": "http://localhost/page",
    }
    mock_get.assert_not_called()


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_private_and_loopback_ip_urls_without_request(mock_get):
    private_result = web_fetch("http://192.168.1.2/page")
    loopback_result = web_fetch("http://127.0.0.1/page")

    assert private_result == {
        "ok": False,
        "error": "web_fetch rejects private or local network URLs",
        "url": "http://192.168.1.2/page",
    }
    assert loopback_result == {
        "ok": False,
        "error": "web_fetch rejects private or local network URLs",
        "url": "http://127.0.0.1/page",
    }
    mock_get.assert_not_called()


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_url_credentials_without_request(mock_get):
    result = web_fetch("https://user:pass@example.com/page")

    assert result == {
        "ok": False,
        "error": "web_fetch rejects URLs with embedded credentials",
        "url": "https://user:pass@example.com/page",
    }
    mock_get.assert_not_called()


@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_passes_request_safety_flags(mock_get, mock_extract, mock_metadata):
    mock_get.return_value = _fetch_response()
    mock_extract.return_value = "Extracted readable text."
    mock_metadata.return_value = Mock(title="Example Page")

    result = web_fetch("https://example.com/page", max_chars=12000)

    assert result == {
        "ok": True,
        "url": "https://example.com/page",
        "title": "Example Page",
        "text": "Extracted readable text.",
        "truncated": False,
        "source": "example.com",
    }
    mock_get.assert_called_once_with(
        "https://example.com/page",
        timeout=WEB_SEARCH_TIMEOUT_SECONDS,
        headers=FETCH_HEADERS,
        stream=True,
        allow_redirects=False,
    )


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_non_200_response(mock_get):
    mock_get.return_value = _fetch_response(status_code=404)

    result = web_fetch("https://example.com/missing")

    assert result == {
        "ok": False,
        "error": "web_fetch returned HTTP 404",
        "url": "https://example.com/missing",
    }


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_rejects_binary_content_type(mock_get):
    mock_get.return_value = _fetch_response(
        headers={"Content-Type": "application/pdf"},
    )

    result = web_fetch("https://example.com/file.pdf")

    assert result == {
        "ok": False,
        "error": "web_fetch rejected non-text content type: application/pdf",
        "url": "https://example.com/file.pdf",
    }


@patch("skills.active.web_search.web_search.MAX_FETCH_BYTES", 5)
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_enforces_response_byte_cap(mock_get):
    response = _fetch_response()
    response.iter_content.return_value = [b"123", b"456"]
    mock_get.return_value = response

    result = web_fetch("https://example.com/large")

    assert result == {
        "ok": False,
        "error": "web_fetch response exceeded 5 bytes",
        "url": "https://example.com/large",
    }


@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_uses_trafilatura_extract_result(mock_get, mock_extract, mock_metadata):
    mock_get.return_value = _fetch_response(
        content=b"<html><head><title>Ignored</title></head><body>Raw</body></html>",
    )
    mock_extract.return_value = "Article body from trafilatura."
    mock_metadata.return_value = Mock(title="Metadata Title")

    result = web_fetch("https://www.example.com/article")

    assert result["ok"] is True
    assert result["title"] == "Metadata Title"
    assert result["text"] == "Article body from trafilatura."
    assert result["source"] == "example.com"


@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_merges_visible_lead_when_trafilatura_omits_it(
    mock_get,
    mock_extract,
    mock_metadata,
):
    lead = (
        '"Ransomware activity jumped again in Q1 2026," writes Slashdot '
        "reader BrianFagioli, citing a new industry report."
    )
    html = f"""
        <html>
            <head><title>Ransomware Activity Jumps</title></head>
            <body>
                <nav>Login Subscribe</nav>
                <article>
                    <p>{lead}</p>
                    <p>The report said attacks increased across several sectors.</p>
                    <p>Security teams are still working through the backlog.</p>
                </article>
            </body>
        </html>
    """
    mock_get.return_value = _fetch_response(content=html.encode("utf-8"))
    mock_extract.return_value = "The report said attacks increased across several sectors."
    mock_metadata.return_value = Mock(title="Ransomware Activity Jumps")

    result = web_fetch("https://slashdot.org/story/example")

    assert result["ok"] is True
    assert lead in result["text"]
    assert "BrianFagioli" in result["text"]
    assert "The report said attacks increased" in result["text"]


@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_falls_back_to_basic_html_stripping(mock_get, mock_extract, mock_metadata):
    mock_get.return_value = _fetch_response(
        content=(
            b"<html><head><title>Fallback Title</title><script>bad()</script></head>"
            b"<body><h1>Hello</h1><style>.x{}</style><p>World</p></body></html>"
        ),
    )
    mock_extract.return_value = None
    mock_metadata.return_value = None

    result = web_fetch("https://example.com/fallback")

    assert result["ok"] is True
    assert result["title"] == "Fallback Title"
    assert result["text"] == "Hello World"


@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_caps_max_chars_and_reports_truncated(mock_get, mock_extract, mock_metadata):
    mock_get.return_value = _fetch_response()
    mock_extract.return_value = "x" * 1500
    mock_metadata.return_value = None

    result = web_fetch("https://example.com/long", max_chars=1200)

    assert result["ok"] is True
    assert len(result["text"]) == 1200
    assert result["truncated"] is True


@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_timeout_and_connection_errors_return_ok_false(mock_get):
    mock_get.side_effect = requests.Timeout("timed out")
    timeout_result = web_fetch("https://example.com/timeout")

    mock_get.side_effect = requests.ConnectionError("connection failed")
    connection_result = web_fetch("https://example.com/down")

    assert timeout_result == {
        "ok": False,
        "error": "web_fetch failed: Timeout: timed out",
        "url": "https://example.com/timeout",
    }
    assert connection_result == {
        "ok": False,
        "error": "web_fetch failed: ConnectionError: connection failed",
        "url": "https://example.com/down",
    }


@patch("tir.diagnostics.service.create_diagnostic_issue")
@patch("tir.open_loops.service.create_open_loop")
@patch("tir.artifacts.service.create_artifact")
@patch("tir.memory.chroma.upsert_chunk")
@patch("tir.memory.chunking._store_chunk")
@patch("skills.active.web_search.web_search.trafilatura.extract_metadata")
@patch("skills.active.web_search.web_search.trafilatura.extract")
@patch("skills.active.web_search.web_search.requests.get")
def test_web_fetch_does_not_invoke_memory_or_registry_writes(
    mock_get,
    mock_extract,
    mock_metadata,
    mock_store_chunk,
    mock_upsert_chunk,
    mock_create_artifact,
    mock_create_open_loop,
    mock_create_diagnostic_issue,
):
    mock_get.return_value = _fetch_response()
    mock_extract.return_value = "Extracted text."
    mock_metadata.return_value = None

    result = web_fetch("https://example.com/no-side-effects")

    assert result["ok"] is True
    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
    mock_create_artifact.assert_not_called()
    mock_create_open_loop.assert_not_called()
    mock_create_diagnostic_issue.assert_not_called()
