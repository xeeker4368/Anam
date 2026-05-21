import json
from pathlib import Path

import pytest

from tir.research.moltbook_sources import (
    EXCERPT_LENGTH,
    MoltbookSourcePreviewError,
    collect_moltbook_source_preview,
)


class FakeRegistry:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def dispatch(self, tool_name, args):
        self.calls.append((tool_name, dict(args)))
        return {
            "ok": True,
            "value": {
                "ok": True,
                "json": self.payload,
                "text": "raw payload should not be copied moltbook-secret-token",
            },
            "normalized_args": dict(args),
        }


def _post(**overrides):
    post = {
        "id": "post-1",
        "title": "A compact source",
        "author": {"id": "author-1", "name": "source_author"},
        "submolt": {"name": "agents"},
        "created_at": "2026-05-21T10:00:00Z",
        "url": "https://www.moltbook.com/p/post-1",
        "upvotes": 3,
        "downvotes": 1,
        "score": 2,
        "comment_count": 4,
        "verification_status": "unverified",
        "is_spam": False,
        "content": "Source text " * 100,
    }
    post.update(overrides)
    return post


def _raw_feed_post(**overrides):
    post = {
        "id": "feed-raw-1",
        "name": "Feed title fallback",
        "body": "Feed body text " * 80,
        "author": {"id": "feed-author-1", "name": "feed_author"},
        "submolt": {"display_name": "Feed Agents"},
        "created_at": "2026-05-21T11:00:00Z",
        "url": "https://www.moltbook.com/p/feed-raw-1",
        "upvotes": 5,
        "downvotes": 0,
        "score": 5,
        "comment_count": 2,
        "verification_status": "unknown",
        "is_spam": False,
    }
    post.update(overrides)
    return post


def test_query_preview_compacts_post_records():
    registry = FakeRegistry({"results": [_post()]})

    trace = collect_moltbook_source_preview(
        query="agent autonomy before go-live",
        registry=registry,
    )

    assert registry.calls == [
        ("moltbook_search", {"q": "agent autonomy before go-live", "limit": 10})
    ]
    assert trace["collection_version"] == "moltbook_source_collection_v1"
    assert trace["mode"] == "preview"
    assert trace["query"] == "agent autonomy before go-live"
    assert trace["feed"] is False
    assert trace["limit"] == 10
    assert trace["no_external_write_confirmed"] is True
    assert trace["verification_status_is_metadata_only"] is True
    assert trace["tool_calls"] == [
        {
            "tool_name": "moltbook_search",
            "arguments": {"q": "agent autonomy before go-live", "limit": 10},
            "ok": True,
            "normalized_args": {"q": "agent autonomy before go-live", "limit": 10},
            "tool_returned_ok": True,
            "result_count": 1,
        }
    ]

    result = trace["results"][0]
    assert result["source_kind"] == "moltbook_post"
    assert result["tool_name"] == "moltbook_search"
    assert result["query"] == "agent autonomy before go-live"
    assert result["result_rank"] == 1
    assert result["post_id"] == "post-1"
    assert result["title"] == "A compact source"
    assert result["author_id"] == "author-1"
    assert result["author_name"] == "source_author"
    assert result["submolt"] == "agents"
    assert result["created_at"] == "2026-05-21T10:00:00Z"
    assert result["url"] == "https://www.moltbook.com/p/post-1"
    assert result["upvotes"] == 3
    assert result["downvotes"] == 1
    assert result["score"] == 2
    assert result["comment_count"] == 4
    assert result["verification_status"] == "unverified"
    assert result["is_spam"] is False
    assert len(result["content_excerpt"]) <= EXCERPT_LENGTH + 3
    assert "content" not in result


def test_feed_preview_compacts_post_records():
    registry = FakeRegistry({"posts": [_post(id="feed-post")]})

    trace = collect_moltbook_source_preview(feed=True, registry=registry)

    assert registry.calls == [("moltbook_feed", {"sort": "new", "limit": 10})]
    assert trace["feed"] is True
    assert trace["sort"] == "new"
    assert trace["results"][0]["tool_name"] == "moltbook_feed"
    assert trace["results"][0]["query"] is None
    assert trace["results"][0]["post_id"] == "feed-post"


def test_feed_raw_post_objects_without_search_markers_compact():
    registry = FakeRegistry({"posts": [_raw_feed_post()]})

    trace = collect_moltbook_source_preview(feed=True, limit=3, registry=registry)

    assert trace["feed"] is True
    assert trace["limit"] == 3
    assert trace["no_usable_results"] is False
    assert trace["no_result_note"] is None
    assert trace["omitted_count"] == 0
    assert trace["omitted_reasons"] == []

    result = trace["results"][0]
    assert result["source_kind"] == "moltbook_post"
    assert result["tool_name"] == "moltbook_feed"
    assert result["post_id"] == "feed-raw-1"
    assert result["title"] == "Feed title fallback"
    assert result["author_id"] == "feed-author-1"
    assert result["author_name"] == "feed_author"
    assert result["submolt"] == "Feed Agents"
    assert result["created_at"] == "2026-05-21T11:00:00Z"
    assert result["url"] == "https://www.moltbook.com/p/feed-raw-1"
    assert result["verification_status"] == "unknown"
    assert result["is_spam"] is False
    assert result["content_excerpt"].startswith("Feed body text")
    assert len(result["content_excerpt"]) <= EXCERPT_LENGTH + 3
    assert "content" not in result
    assert "body" not in result


def test_explicit_limit_works():
    registry = FakeRegistry({"results": []})

    trace = collect_moltbook_source_preview(query="agents", limit=5, registry=registry)

    assert registry.calls == [("moltbook_search", {"q": "agents", "limit": 5})]
    assert trace["limit"] == 5


def test_limit_above_max_is_rejected():
    registry = FakeRegistry({"results": []})

    with pytest.raises(MoltbookSourcePreviewError, match="at most 20"):
        collect_moltbook_source_preview(query="agents", limit=21, registry=registry)

    assert registry.calls == []


def test_spam_omitted_by_default():
    registry = FakeRegistry(
        {
            "results": [
                _post(id="spam-post", is_spam=True),
                _post(id="normal-post", is_spam=False),
            ]
        }
    )

    trace = collect_moltbook_source_preview(query="agents", registry=registry)

    assert [item["post_id"] for item in trace["results"]] == ["normal-post"]
    assert trace["omitted_count"] == 1
    assert trace["omitted_reasons"] == [
        {"reason": "spam_omitted", "result_rank": 1, "post_id": "spam-post"}
    ]


def test_include_spam_preserves_labeled_spam():
    registry = FakeRegistry({"results": [_post(id="spam-post", is_spam=True)]})

    trace = collect_moltbook_source_preview(
        query="agents",
        include_spam=True,
        registry=registry,
    )

    assert trace["omitted_count"] == 0
    assert trace["results"][0]["post_id"] == "spam-post"
    assert trace["results"][0]["is_spam"] is True


def test_spam_feed_posts_are_omitted_by_default():
    registry = FakeRegistry(
        {
            "posts": [
                _raw_feed_post(id="feed-spam", is_spam=True),
                _raw_feed_post(id="feed-normal", is_spam=False),
            ]
        }
    )

    trace = collect_moltbook_source_preview(feed=True, registry=registry)

    assert [item["post_id"] for item in trace["results"]] == ["feed-normal"]
    assert trace["no_usable_results"] is False
    assert trace["omitted_count"] == 1
    assert trace["omitted_reasons"] == [
        {"reason": "spam_omitted", "result_rank": 1, "post_id": "feed-spam"}
    ]


def test_include_spam_preserves_labeled_feed_spam():
    registry = FakeRegistry({"posts": [_raw_feed_post(id="feed-spam", is_spam=True)]})

    trace = collect_moltbook_source_preview(
        feed=True,
        include_spam=True,
        registry=registry,
    )

    assert trace["omitted_count"] == 0
    assert trace["no_usable_results"] is False
    assert trace["results"][0]["post_id"] == "feed-spam"
    assert trace["results"][0]["is_spam"] is True


def test_verification_status_preserved_as_metadata_only():
    registry = FakeRegistry({"results": [_post(verification_status="verified")]})

    trace = collect_moltbook_source_preview(query="agents", registry=registry)

    assert trace["verification_status_is_metadata_only"] is True
    assert trace["results"][0]["verification_status"] == "verified"


def test_no_result_trace_is_success_and_warns_against_absence_proof():
    registry = FakeRegistry({"results": []})

    trace = collect_moltbook_source_preview(query="unlikely query", registry=registry)

    assert trace["results"] == []
    assert trace["no_usable_results"] is True
    assert "not evidence that no relevant material exists" in trace["no_result_note"]


def test_explicit_non_post_results_are_omitted():
    registry = FakeRegistry(
        {
            "results": [
                {
                    "type": "comment",
                    "id": "comment-1",
                    "content": "Comment support is deferred.",
                    "post": _post(id="nested-post"),
                },
                {"type": "agent", "name": "profile-result"},
            ]
        }
    )

    trace = collect_moltbook_source_preview(query="agents", registry=registry)

    assert trace["results"] == []
    assert trace["no_usable_results"] is True
    assert trace["omitted_count"] == 2
    assert [item["reason"] for item in trace["omitted_reasons"]] == [
        "non_post_result",
        "non_post_result",
    ]


def test_feed_explicit_non_post_results_are_still_omitted():
    registry = FakeRegistry(
        {
            "posts": [
                {"type": "comment", "id": "comment-1", "body": "Not a v1 source."},
                {"type": "agent", "id": "agent-1", "name": "profile-result"},
                {"type": "mention", "id": "mention-1", "body": "Mention result."},
            ]
        }
    )

    trace = collect_moltbook_source_preview(feed=True, registry=registry)

    assert trace["results"] == []
    assert trace["no_usable_results"] is True
    assert trace["omitted_count"] == 3
    assert [item["reason"] for item in trace["omitted_reasons"]] == [
        "non_post_result",
        "non_post_result",
        "non_post_result",
    ]


def test_no_usable_results_true_when_all_feed_posts_omitted_as_spam():
    registry = FakeRegistry({"posts": [_raw_feed_post(id="feed-spam", is_spam=True)]})

    trace = collect_moltbook_source_preview(feed=True, registry=registry)

    assert trace["results"] == []
    assert trace["no_usable_results"] is True
    assert "not evidence that no relevant material exists" in trace["no_result_note"]
    assert trace["omitted_reasons"] == [
        {"reason": "spam_omitted", "result_rank": 1, "post_id": "feed-spam"}
    ]


def test_token_secret_never_appears_in_trace_output():
    registry = FakeRegistry({"results": [_post()]})

    trace = collect_moltbook_source_preview(query="agents", registry=registry)
    output = json.dumps(trace)

    assert "moltbook-secret-token" not in output


def test_uses_registry_dispatch_for_read_only_tools():
    registry = FakeRegistry({"results": [_post()]})

    collect_moltbook_source_preview(query="agents", registry=registry)
    collect_moltbook_source_preview(feed=True, registry=registry)

    assert registry.calls == [
        ("moltbook_search", {"q": "agents", "limit": 10}),
        ("moltbook_feed", {"sort": "new", "limit": 10}),
    ]


def test_no_db_chroma_or_artifact_registration(monkeypatch):
    registry = FakeRegistry({"results": [_post()]})

    def fail(*_args, **_kwargs):
        raise AssertionError("unexpected durable memory/indexing call")

    monkeypatch.setattr("tir.memory.db.init_databases", fail)
    monkeypatch.setattr("tir.artifacts.service.create_artifact", fail)
    monkeypatch.setattr("tir.memory.research_indexing.index_manual_research_note", fail)

    trace = collect_moltbook_source_preview(query="agents", registry=registry)

    assert trace["results"][0]["post_id"] == "post-1"


def test_write_trace_writes_compact_sidecar_json_only(tmp_path):
    registry = FakeRegistry({"results": [_post()]})
    workspace_root = tmp_path / "workspace"

    trace = collect_moltbook_source_preview(
        query="agent autonomy before go-live",
        registry=registry,
        write_trace=True,
        workspace_root=workspace_root,
    )

    assert trace["trace_path"].startswith("research/source-traces/")
    assert trace["trace_path"].endswith(".moltbook-sources.json")
    written = Path(workspace_root / trace["trace_path"])
    assert written.exists()
    stored = json.loads(written.read_text(encoding="utf-8"))
    assert stored == trace
    assert stored["results"][0]["post_id"] == "post-1"
    assert "content" not in stored["results"][0]
