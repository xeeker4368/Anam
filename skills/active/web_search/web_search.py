import html
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

from tir.config import SEARXNG_URL, WEB_SEARCH_TIMEOUT_SECONDS
from tir.tools.registry import tool

MAX_FETCH_BYTES = 2 * 1024 * 1024
FETCH_HEADERS = {
    "User-Agent": "ProjectAnam-web-fetch/1.0",
    "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1",
}
FETCH_TEXT_CONTENT_TYPES = {
    "application/xhtml+xml",
}


class WebSearchProviderError(RuntimeError):
    """Raised when the configured SearXNG provider returns unusable data."""


class WebFetchError(RuntimeError):
    """Raised when a single-page fetch cannot safely continue."""


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"head", "script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"head", "script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _clamp_max_results(max_results) -> int:
    try:
        value = int(max_results)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 10))


def _clamp_max_chars(max_chars) -> int:
    try:
        value = int(max_chars)
    except (TypeError, ValueError):
        value = 12000
    return max(1000, min(value, 30000))


def _source_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _validate_fetch_url(url: str) -> tuple[str | None, str | None]:
    normalized = (url or "").strip()
    if not normalized:
        return None, "url is required"

    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None, "web_fetch only supports http and https URLs"
    if not parsed.hostname:
        return None, "web_fetch URL must include a hostname"
    if parsed.username or parsed.password:
        return None, "web_fetch rejects URLs with embedded credentials"

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return None, "web_fetch rejects localhost URLs"

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return normalized, None

    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return None, "web_fetch rejects private or local network URLs"

    return normalized, None


def _is_text_response(content_type: str) -> bool:
    if not content_type:
        return True
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("text/") or media_type in FETCH_TEXT_CONTENT_TYPES


def _read_response_bytes(response) -> bytes:
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_FETCH_BYTES:
            raise WebFetchError(f"web_fetch response exceeded {MAX_FETCH_BYTES} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(content: bytes, response) -> str:
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _fallback_title(page_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _normalize_whitespace(html.unescape(match.group(1)))


def _extract_title(page_text: str) -> str:
    try:
        metadata = trafilatura.extract_metadata(page_text)
        title = getattr(metadata, "title", None) if metadata else None
        if title:
            return _normalize_whitespace(title)
    except Exception:
        pass
    return _fallback_title(page_text)


def _fallback_text(page_text: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(page_text)
        return _normalize_whitespace(html.unescape(parser.get_text()))
    except Exception:
        return _normalize_whitespace(page_text)


def _extract_text(page_text: str) -> str:
    try:
        extracted = trafilatura.extract(
            page_text,
            output_format="txt",
            include_comments=False,
            include_tables=False,
        )
    except Exception:
        extracted = None

    if extracted:
        return _normalize_whitespace(extracted)

    return _fallback_text(page_text)


def _search_provider(query: str, max_results: int) -> list[dict]:
    response = requests.get(
        urljoin(SEARXNG_URL.rstrip("/") + "/", "search"),
        params={"q": query, "format": "json"},
        timeout=WEB_SEARCH_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise WebSearchProviderError(f"SearXNG returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise WebSearchProviderError("SearXNG returned non-JSON response") from exc

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise WebSearchProviderError("SearXNG response missing results list")

    return results[:max_results]


def _normalize_result(item: dict) -> dict:
    url = item.get("url") or ""
    return {
        "title": item.get("title") or "",
        "url": url,
        "snippet": item.get("content") or item.get("snippet") or "",
        "source": _source_from_url(url),
    }


@tool(
    name="web_fetch",
    description=(
        "Fetch and extract readable text from one public HTTP/HTTPS web page. "
        "Use this after web_search identifies a candidate URL or when the user "
        "provides a specific public URL. It does not crawl, execute scripts, "
        "download files, or access localhost/private networks. When the user "
        "provides a public URL and asks what it says, asks for a summary, asks "
        "about page contents, or asks to verify details from that page, call "
        "this tool before answering. Do not infer page contents from URL slugs "
        "or snippets."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "minLength": 1,
                "description": "The public HTTP/HTTPS page URL to fetch.",
            },
            "max_chars": {
                "type": "integer",
                "default": 12000,
                "minimum": 1000,
                "maximum": 30000,
                "description": "Maximum extracted text characters to return.",
            },
        },
        "required": ["url"],
    },
)
def web_fetch(url: str, max_chars: int = 12000) -> dict:
    safe_url, validation_error = _validate_fetch_url(url)
    returned_url = (url or "").strip()
    if validation_error:
        return {"ok": False, "error": validation_error, "url": returned_url}

    char_limit = _clamp_max_chars(max_chars)

    try:
        response = requests.get(
            safe_url,
            timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            headers=FETCH_HEADERS,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": f"web_fetch failed: {type(exc).__name__}: {exc}",
            "url": safe_url,
        }

    if response.status_code != 200:
        return {
            "ok": False,
            "error": f"web_fetch returned HTTP {response.status_code}",
            "url": safe_url,
        }

    content_type = response.headers.get("Content-Type", "")
    if not _is_text_response(content_type):
        return {
            "ok": False,
            "error": f"web_fetch rejected non-text content type: {content_type}",
            "url": safe_url,
        }

    try:
        response_bytes = _read_response_bytes(response)
    except (WebFetchError, requests.RequestException) as exc:
        return {"ok": False, "error": str(exc), "url": safe_url}

    page_text = _decode_response(response_bytes, response)
    title = _extract_title(page_text)
    extracted_text = _extract_text(page_text)
    truncated = len(extracted_text) > char_limit

    return {
        "ok": True,
        "url": safe_url,
        "title": title,
        "text": extracted_text[:char_limit].rstrip() if truncated else extracted_text,
        "truncated": truncated,
        "source": _source_from_url(safe_url),
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
    except WebSearchProviderError as exc:
        return {"ok": False, "error": str(exc)}
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": f"web_search provider failed: {type(exc).__name__}: {exc}",
        }
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
