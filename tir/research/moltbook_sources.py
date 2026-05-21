"""Compact read-only Moltbook source preview collection.

This module builds deterministic source traces from existing Moltbook read
tools. It does not call Moltbook HTTP APIs directly, create research notes,
register artifacts, index memory, update open loops, or write external state.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tir.config import SKILLS_DIR, WORKSPACE_DIR
from tir.tools.registry import SkillRegistry
from tir.workspace.service import ensure_workspace, resolve_workspace_path, write_workspace_file


COLLECTION_VERSION = "moltbook_source_collection_v1"
MODE = "preview"
DEFAULT_LIMIT = 10
MAX_LIMIT = 20
EXCERPT_LENGTH = 600
NO_RESULT_NOTE = (
    "No usable Moltbook results were returned. This is not evidence that no "
    "relevant material exists."
)
FEED_SORTS = {"hot", "new", "top", "rising"}


class MoltbookSourcePreviewError(ValueError):
    """Raised when Moltbook source preview cannot proceed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_limit(limit: int | None) -> int:
    value = DEFAULT_LIMIT if limit is None else limit
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise MoltbookSourcePreviewError("--limit must be an integer") from exc
    if value < 1:
        raise MoltbookSourcePreviewError("--limit must be at least 1")
    if value > MAX_LIMIT:
        raise MoltbookSourcePreviewError(f"--limit must be at most {MAX_LIMIT}")
    return value


def _normalize_text(value) -> str:
    return " ".join(str(value or "").split())


def _excerpt(value, *, max_chars: int = EXCERPT_LENGTH) -> str:
    text = _normalize_text(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _nested_get(item: dict, path: tuple[str, ...]):
    value = item
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _first_value(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _extract_results(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("posts", "results", "data", "items"):
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


def _post_payload(item: dict) -> dict:
    post = item.get("post")
    return post if isinstance(post, dict) else {}


def _result_type(item: dict) -> str:
    value = item.get("type") or item.get("result_type") or item.get("kind")
    if value:
        return str(value).lower()
    if isinstance(item.get("post"), dict):
        return "post"
    if item.get("post_id") or item.get("title") or item.get("content"):
        return "post"
    return "unknown"


def _is_post_like(item: dict, *, feed: bool = False) -> bool:
    result_type = _result_type(item)
    if result_type in {
        "comment",
        "comments",
        "agent",
        "profile",
        "submolt",
        "mention",
        "mentions",
    }:
        return False
    if feed and result_type == "unknown":
        return True
    return result_type in {"post", "posts"} or isinstance(item.get("post"), dict)


def _author_id(item: dict, post: dict):
    return _first_value(
        _nested_get(item, ("author", "id")),
        item.get("author_id"),
        _nested_get(post, ("author", "id")),
        post.get("author_id"),
    )


def _author_name(item: dict, post: dict) -> str:
    candidates = (
        _nested_get(item, ("author", "name")),
        item.get("author_name"),
        item.get("author"),
        _nested_get(post, ("author", "name")),
        post.get("author_name"),
        post.get("author"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("name")
        if candidate:
            return str(candidate)
    return ""


def _submolt(item: dict, post: dict) -> str:
    for source in (item.get("submolt"), post.get("submolt")):
        if isinstance(source, dict):
            return str(source.get("name") or source.get("display_name") or "")
        if source:
            return str(source)
    return str(item.get("submolt_name") or post.get("submolt_name") or "")


def _content_source(item: dict, post: dict):
    return _first_value(
        item.get("content_preview"),
        item.get("preview"),
        item.get("excerpt"),
        item.get("content"),
        item.get("body"),
        item.get("text"),
        post.get("content_preview"),
        post.get("preview"),
        post.get("excerpt"),
        post.get("content"),
        post.get("body"),
        post.get("text"),
    )


def _compact_post_record(
    item: dict,
    *,
    tool_name: str,
    query: str | None,
    result_rank: int,
    retrieved_at: str,
) -> dict:
    post = _post_payload(item)
    return {
        "source_kind": "moltbook_post",
        "tool_name": tool_name,
        "query": query,
        "result_rank": result_rank,
        "post_id": _first_value(item.get("id"), post.get("id"), item.get("post_id")),
        "title": str(
            _first_value(
                item.get("title"),
                post.get("title"),
                item.get("name"),
                post.get("name"),
                "",
            )
            or ""
        ),
        "author_id": _author_id(item, post),
        "author_name": _author_name(item, post),
        "submolt": _submolt(item, post),
        "created_at": _first_value(item.get("created_at"), post.get("created_at")),
        "retrieved_at": retrieved_at,
        "url": _first_value(item.get("url"), post.get("url")),
        "upvotes": _first_value(item.get("upvotes"), post.get("upvotes"), 0),
        "downvotes": _first_value(item.get("downvotes"), post.get("downvotes"), 0),
        "score": _first_value(item.get("score"), post.get("score"), 0),
        "comment_count": _first_value(
            item.get("comment_count"),
            post.get("comment_count"),
            0,
        ),
        "verification_status": _first_value(
            item.get("verification_status"),
            post.get("verification_status"),
        ),
        "is_spam": bool(_first_value(item.get("is_spam"), post.get("is_spam"), False)),
        "content_excerpt": _excerpt(_content_source(item, post)),
    }


def _base_trace(
    *,
    retrieved_at: str,
    query: str | None,
    feed: bool,
    sort: str,
    limit: int,
) -> dict:
    return {
        "collection_version": COLLECTION_VERSION,
        "mode": MODE,
        "retrieved_at": retrieved_at,
        "query": query,
        "feed": feed,
        "sort": sort if feed else None,
        "limit": limit,
        "tool_calls": [],
        "results": [],
        "omitted_count": 0,
        "omitted_reasons": [],
        "no_external_write_confirmed": True,
        "verification_status_is_metadata_only": True,
        "no_usable_results": False,
        "no_result_note": None,
    }


def _add_omission(trace: dict, *, reason: str, result_rank: int, post_id=None) -> None:
    trace["omitted_count"] += 1
    trace["omitted_reasons"].append(
        {
            "reason": reason,
            "result_rank": result_rank,
            "post_id": post_id,
        }
    )


def _json_payload_from_tool_value(value: dict):
    if not isinstance(value, dict):
        return None
    return value.get("json")


def _dispatch_moltbook(
    *,
    registry,
    tool_name: str,
    arguments: dict,
) -> tuple[dict, dict]:
    envelope = registry.dispatch(tool_name, arguments)
    tool_call = {
        "tool_name": tool_name,
        "arguments": dict(arguments),
        "ok": bool(envelope.get("ok")),
    }
    if envelope.get("normalized_args"):
        tool_call["normalized_args"] = envelope["normalized_args"]
    if not envelope.get("ok"):
        tool_call["error"] = envelope.get("error")
        raise MoltbookSourcePreviewError(envelope.get("error") or f"{tool_name} failed")

    value = envelope.get("value")
    tool_call["tool_returned_ok"] = bool(isinstance(value, dict) and value.get("ok"))
    if not isinstance(value, dict) or not value.get("ok"):
        error = value.get("error") if isinstance(value, dict) else None
        tool_call["error"] = error or f"{tool_name} returned an invalid response"
        raise MoltbookSourcePreviewError(tool_call["error"])
    return value, tool_call


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80].rstrip("-") or "moltbook-source-preview"


def source_trace_relative_path(trace: dict) -> str:
    retrieved_at = trace["retrieved_at"]
    date_text = datetime.fromisoformat(retrieved_at).date().isoformat()
    if trace.get("feed"):
        slug = _slugify(f"feed-{trace.get('sort') or 'new'}")
    else:
        slug = _slugify(trace.get("query") or "query")
    return f"research/source-traces/{date_text}-{slug}.moltbook-sources.json"


def write_source_trace(trace: dict, *, workspace_root: Path = WORKSPACE_DIR) -> dict:
    root = ensure_workspace(Path(workspace_root))
    relative_path = source_trace_relative_path(trace)
    target = resolve_workspace_path(relative_path, root)
    if target.exists():
        raise MoltbookSourcePreviewError(f"Source trace already exists: {relative_path}")
    trace["trace_path"] = relative_path
    content = json.dumps(trace, indent=2, sort_keys=True) + "\n"
    return write_workspace_file(relative_path, content, root=root)


def collect_moltbook_source_preview(
    *,
    query: str | None = None,
    feed: bool = False,
    limit: int | None = None,
    sort: str = "new",
    include_spam: bool = False,
    write_trace: bool = False,
    registry=None,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Collect a compact read-only Moltbook source preview trace."""
    normalized_query = (query or "").strip() or None
    if bool(normalized_query) == bool(feed):
        raise MoltbookSourcePreviewError("Exactly one of --query or --feed is required")
    bounded_limit = _require_limit(limit)
    normalized_sort = (sort or "new").strip().lower()
    if normalized_sort not in FEED_SORTS:
        raise MoltbookSourcePreviewError("--sort must be one of: hot, new, top, rising")

    registry = registry or SkillRegistry.from_directory(SKILLS_DIR)
    retrieved_at = _now()
    tool_name = "moltbook_feed" if feed else "moltbook_search"
    arguments = (
        {"sort": normalized_sort, "limit": bounded_limit}
        if feed
        else {"q": normalized_query, "limit": bounded_limit}
    )
    trace = _base_trace(
        retrieved_at=retrieved_at,
        query=normalized_query,
        feed=feed,
        sort=normalized_sort,
        limit=bounded_limit,
    )

    try:
        tool_value, tool_call = _dispatch_moltbook(
            registry=registry,
            tool_name=tool_name,
            arguments=arguments,
        )
    except MoltbookSourcePreviewError as exc:
        trace["tool_calls"].append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "ok": False,
                "error": str(exc),
            }
        )
        raise

    payload = _json_payload_from_tool_value(tool_value)
    raw_results = _extract_results(payload)
    tool_call["result_count"] = len(raw_results)
    trace["tool_calls"].append(tool_call)

    for index, item in enumerate(raw_results, start=1):
        if not isinstance(item, dict):
            _add_omission(trace, reason="unsupported_result_shape", result_rank=index)
            continue
        if not _is_post_like(item, feed=feed):
            _add_omission(trace, reason="non_post_result", result_rank=index)
            continue
        record = _compact_post_record(
            item,
            tool_name=tool_name,
            query=normalized_query,
            result_rank=index,
            retrieved_at=retrieved_at,
        )
        if record["is_spam"] and not include_spam:
            _add_omission(
                trace,
                reason="spam_omitted",
                result_rank=index,
                post_id=record.get("post_id"),
            )
            continue
        trace["results"].append(record)

    if not trace["results"]:
        trace["no_usable_results"] = True
        trace["no_result_note"] = NO_RESULT_NOTE

    if write_trace:
        write_source_trace(trace, workspace_root=workspace_root)

    return trace
