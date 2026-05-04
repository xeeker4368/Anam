import os
from urllib.parse import urljoin

import requests

from tir.tools.registry import tool


MOLTBOOK_API_BASE = "https://www.moltbook.com/api/v1"
MOLTBOOK_AUTHOR_SEARCH_NOTE = (
    "authored_posts only includes post-like results whose author field matches "
    "the requested author. Moltbook semantic search is mixed-type and should "
    "be used separately for mentions or discovery, not authorship."
)


def _clamp_limit(limit) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, 25))


def _normalize_name(value) -> str:
    return str(value or "").strip().lower()


def _extract_posts(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("posts", "recentPosts", "results", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("posts", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


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


def _compact_profile_post(item: dict, author_name: str) -> dict:
    compact = _compact_result(item)
    if not compact["author_name"]:
        compact["author_name"] = author_name
    compact["type"] = "post"
    return compact


def _get_json(url: str, *, params: dict, token: str, label: str):
    try:
        response = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        return None, f"Moltbook {label} failed: {type(exc).__name__}: {exc}"

    if response.status_code != 200:
        return None, f"Moltbook {label} returned HTTP {response.status_code}"

    try:
        return response.json(), None
    except ValueError:
        return None, f"Moltbook {label} returned non-JSON response"


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
    freshness={
        "mode": "real_time",
        "source_of_truth": True,
        "memory_may_inform_but_not_replace": True,
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

    authored_posts = []
    mentions = []
    profiles = []
    other_results = []
    target = _normalize_name(normalized_author)

    posts_payload, error = _get_json(
        urljoin(MOLTBOOK_API_BASE.rstrip("/") + "/", "posts"),
        params={
            "author": normalized_author,
            "sort": "new",
            "limit": str(bounded_limit),
        },
        token=token,
        label="posts by author",
    )
    if error:
        return {"ok": False, "error": error}

    for item in _extract_posts(posts_payload):
        if not isinstance(item, dict):
            other_results.append({"type": "unknown", "raw": item})
            continue

        compact = _compact_result(item)
        author_matches = _normalize_name(compact["author_name"]) == target
        post_like = _is_post_like(item)

        if post_like and author_matches:
            authored_posts.append(compact)
        else:
            other_results.append(compact)

    if not authored_posts:
        profile_payload, error = _get_json(
            urljoin(MOLTBOOK_API_BASE.rstrip("/") + "/", "agents/profile"),
            params={"name": normalized_author},
            token=token,
            label="agent profile",
        )
        if error:
            return {"ok": False, "error": error}

        if isinstance(profile_payload, dict):
            agent = profile_payload.get("agent")
            if isinstance(agent, dict):
                profiles.append(_compact_result({
                    "type": "agent",
                    "id": agent.get("id"),
                    "name": agent.get("name"),
                    "description": agent.get("description", ""),
                    "karma": agent.get("karma"),
                    "url": f"https://www.moltbook.com/u/{agent.get('name', normalized_author)}",
                }))

        for item in _extract_posts(
            profile_payload.get("recentPosts", [])
            if isinstance(profile_payload, dict)
            else []
        ):
            if not isinstance(item, dict):
                other_results.append({"type": "unknown", "raw": item})
                continue

            compact = _compact_profile_post(item, normalized_author)
            author_matches = _normalize_name(compact["author_name"]) == target
            if _is_post_like(compact) and author_matches:
                authored_posts.append(compact)
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
