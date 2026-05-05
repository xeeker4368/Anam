"""
Compact context helpers for selected prior tool traces.

These helpers do not replay full tool traces. They recover only bounded,
tool-specific continuity metadata needed for follow-up tool use.
"""

import json


MOLTBOOK_SELECTION_KIND = "moltbook_authored_posts"
MAX_MOLTBOOK_SELECTION_POSTS = 10


def build_moltbook_authored_posts_selection(result: dict) -> dict | None:
    """Build compact selection metadata from moltbook_find_author_posts output."""
    if not isinstance(result, dict):
        return None

    posts = result.get("authored_posts")
    if not isinstance(posts, list) or not posts:
        return None

    compact_posts = []
    for index, post in enumerate(posts[:MAX_MOLTBOOK_SELECTION_POSTS], start=1):
        if not isinstance(post, dict):
            continue
        post_id = post.get("id")
        if not post_id:
            continue
        compact_posts.append({
            "index": index,
            "id": str(post_id),
            "title": str(post.get("title") or ""),
            "author_name": str(post.get("author_name") or result.get("author_name") or ""),
            "created_at": str(post.get("created_at") or ""),
            "submolt": str(post.get("submolt") or ""),
        })

    if not compact_posts:
        return None

    return {
        "kind": MOLTBOOK_SELECTION_KIND,
        "tool_name": "moltbook_find_author_posts",
        "author_name": str(result.get("author_name") or ""),
        "posts": compact_posts,
    }


def selection_metadata_for_tool_result(tool_name: str, result) -> dict | None:
    """Return bounded selection metadata for supported tool results."""
    if tool_name == "moltbook_find_author_posts":
        return build_moltbook_authored_posts_selection(result)
    return None


def latest_moltbook_selection_from_messages(messages: list[dict]) -> dict | None:
    """Find the latest compact Moltbook authored-post selection in messages."""
    for message in reversed(messages):
        tool_trace = message.get("tool_trace")
        if not tool_trace:
            continue

        try:
            trace_records = json.loads(tool_trace)
        except (TypeError, ValueError):
            continue

        if not isinstance(trace_records, list):
            continue

        for trace_record in reversed(trace_records):
            if not isinstance(trace_record, dict):
                continue
            for result in reversed(trace_record.get("tool_results") or []):
                if not isinstance(result, dict):
                    continue
                selection = result.get("selection")
                if (
                    isinstance(selection, dict)
                    and selection.get("kind") == MOLTBOOK_SELECTION_KIND
                ):
                    posts = selection.get("posts")
                    if isinstance(posts, list) and posts:
                        return {
                            **selection,
                            "posts": posts[:MAX_MOLTBOOK_SELECTION_POSTS],
                        }

    return None


def format_moltbook_selection_context(selection: dict | None) -> str | None:
    """Format compact Moltbook selection metadata for model context."""
    if not selection:
        return None

    posts = selection.get("posts")
    if not isinstance(posts, list) or not posts:
        return None

    lines = [
        "[Recent Moltbook Selection]",
        "Use these post ids for follow-up requests like read the first one, "
        "summarize the second post, or read the post matching a title. "
        "Use moltbook_read_post for full content before summarizing.",
    ]

    author_name = selection.get("author_name")
    if author_name:
        lines.append(f"Author: {author_name}")

    for post in posts[:MAX_MOLTBOOK_SELECTION_POSTS]:
        if not isinstance(post, dict):
            continue
        parts = [
            f"{post.get('index')}.",
            f"id={post.get('id')}",
            f"title={post.get('title')}",
        ]
        if post.get("author_name"):
            parts.append(f"author={post.get('author_name')}")
        if post.get("created_at"):
            parts.append(f"created_at={post.get('created_at')}")
        if post.get("submolt"):
            parts.append(f"submolt={post.get('submolt')}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


def build_moltbook_selection_context(messages: list[dict]) -> str | None:
    """Build latest bounded Moltbook selection context from message history."""
    return format_moltbook_selection_context(
        latest_moltbook_selection_from_messages(messages)
    )
