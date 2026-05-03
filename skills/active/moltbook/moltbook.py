import os
from urllib.parse import urljoin

import requests

from tir.tools.registry import tool


MOLTBOOK_API_BASE = "https://www.moltbook.com/api/v1"
MOLTBOOK_AUTHOR_SEARCH_NOTE = (
    "Moltbook search is mixed-type and not a strict author filter. "
    "authored_posts only includes post-like results whose author field matches "
    "the requested author."
)


def _clamp_limit(limit) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, 25))


def _normalize_name(value) -> str:
    return str(value or "").strip().lower()


def _extract_results(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("results", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    combined = []
    for key in ("posts", "comments", "agents", "profiles", "submolts"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "type" not in item:
                    item = dict(item)
                    item["type"] = key[:-1] if key.endswith("s") else key
                combined.append(item)
    return combined


def _nested_get(item: dict, path: tuple[str, ...]):
    value = item
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _author_name(item: dict):
    candidates = (
        _nested_get(item, ("author", "name")),
        item.get("author_name"),
        item.get("author"),
        _nested_get(item, ("post", "author", "name")),
        _nested_get(item, ("post", "author_name")),
        _nested_get(item, ("post", "author")),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("name")
        if candidate:
            return str(candidate)
    return ""


def _result_type(item: dict) -> str:
    value = item.get("type") or item.get("result_type") or item.get("kind")
    if value:
        return str(value).lower()
    if item.get("post") and isinstance(item.get("post"), dict):
        return "post"
    if item.get("comment") or item.get("comment_id"):
        return "comment"
    if item.get("agent") or item.get("profile") or item.get("karma") is not None:
        return "agent"
    if item.get("submolt") and not _author_name(item):
        return "submolt"
    if item.get("title") or item.get("post_id") or item.get("content"):
        return "post"
    return "unknown"


def _is_post_like(item: dict) -> bool:
    result_type = _result_type(item)
    if result_type in {"post", "posts"}:
        return True
    if isinstance(item.get("post"), dict):
        return True
    if item.get("post_id") and (item.get("title") or item.get("content")):
        return True
    return False


def _is_profile_like(item: dict) -> bool:
    result_type = _result_type(item)
    return result_type in {"agent", "profile", "agents", "profiles"}


def _compact_result(item: dict) -> dict:
    post = item.get("post") if isinstance(item.get("post"), dict) else {}
    return {
        "type": _result_type(item),
        "id": item.get("id") or post.get("id") or item.get("post_id"),
        "post_id": item.get("post_id") or post.get("id"),
        "title": item.get("title") or post.get("title") or "",
        "content": item.get("content") or post.get("content") or "",
        "author_name": _author_name(item),
        "url": item.get("url") or post.get("url") or "",
        "raw": item,
    }


def _mentions_author(item: dict, author_name: str) -> bool:
    target = _normalize_name(author_name)
    compact = _compact_result(item)
    haystack = " ".join(
        str(compact.get(key) or "")
        for key in ("title", "content", "url", "author_name")
    )
    if isinstance(item.get("post"), dict):
        haystack += " " + " ".join(
            str(item["post"].get(key) or "")
            for key in ("title", "content", "url", "author_name", "author")
        )
    return target in haystack.lower()


@tool(
    name="moltbook_find_author_posts",
    description=(
        "Search Moltbook for a specific author's posts and separate authored "
        "posts from mixed search mentions, comments, profiles, and other "
        "results. Read-only."
    ),
    args_schema={
        "type": "object",
        "properties": {
            "author_name": {
                "type": "string",
                "minLength": 1,
                "description": "Moltbook agent/author name to search for.",
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 25,
                "description": "Maximum number of search results to inspect.",
            },
        },
        "required": ["author_name"],
    },
)
def moltbook_find_author_posts(author_name: str, limit: int = 10) -> dict:
    normalized_author = (author_name or "").strip()
    if not normalized_author:
        return {"ok": False, "error": "author_name is required"}

    token = os.getenv("MOLTBOOK_TOKEN")
    if token is None:
        return {"ok": False, "error": "Missing required environment variable: MOLTBOOK_TOKEN"}

    bounded_limit = _clamp_limit(limit)

    try:
        response = requests.get(
            urljoin(MOLTBOOK_API_BASE.rstrip("/") + "/", "search"),
            params={"q": normalized_author, "limit": str(bounded_limit)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Moltbook search failed: {type(exc).__name__}: {exc}"}

    if response.status_code != 200:
        return {"ok": False, "error": f"Moltbook search returned HTTP {response.status_code}"}

    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "error": "Moltbook search returned non-JSON response"}

    authored_posts = []
    mentions = []
    profiles = []
    other_results = []
    target = _normalize_name(normalized_author)

    for item in _extract_results(payload):
        if not isinstance(item, dict):
            other_results.append({"type": "unknown", "raw": item})
            continue

        compact = _compact_result(item)
        author_matches = _normalize_name(compact["author_name"]) == target
        post_like = _is_post_like(item)

        if post_like and author_matches:
            authored_posts.append(compact)
        elif _is_profile_like(item):
            profiles.append(compact)
        elif (post_like or _result_type(item) in {"comment", "comments"}) and _mentions_author(
            item,
            normalized_author,
        ):
            mentions.append(compact)
        else:
            other_results.append(compact)

    return {
        "ok": True,
        "author_name": normalized_author,
        "authored_posts": authored_posts,
        "mentions": mentions,
        "profiles": profiles,
        "other_results": other_results,
        "note": MOLTBOOK_AUTHOR_SEARCH_NOTE,
    }
