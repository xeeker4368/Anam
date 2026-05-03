from urllib.parse import urlparse

from tir.tools.registry import tool


def _clamp_max_results(max_results) -> int:
    try:
        value = int(max_results)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 10))


def _source_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _search_provider(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS

    with DDGS(timeout=10) as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def _normalize_result(item: dict) -> dict:
    url = item.get("href") or item.get("url") or ""
    return {
        "title": item.get("title") or "",
        "url": url,
        "snippet": item.get("body") or item.get("snippet") or "",
        "source": _source_from_url(url),
    }


@tool(
    name="web_search",
    description=(
        "Search the public web for current outside-world information, changing "
        "facts, URLs, or public resources. Returns search-result snippets only; "
        "it does not fetch full pages."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "The public web search query.",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum number of search results to return.",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 5) -> dict:
    normalized_query = (query or "").strip()
    if not normalized_query:
        return {"ok": False, "error": "query is required"}

    result_limit = _clamp_max_results(max_results)

    try:
        raw_results = _search_provider(normalized_query, result_limit)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"web_search provider failed: {type(exc).__name__}: {exc}",
        }

    return {
        "ok": True,
        "query": normalized_query,
        "results": [
            _normalize_result(item)
            for item in raw_results[:result_limit]
            if isinstance(item, dict)
        ],
    }
