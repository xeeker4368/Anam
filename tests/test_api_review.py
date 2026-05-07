import importlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def review_api_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")

    import tir.memory.db as db_mod
    import tir.review.service as review_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    importlib.reload(review_mod)
    importlib.reload(routes_mod)
    db_mod.init_databases()
    return {
        "client": TestClient(routes_mod.app),
        "db": db_mod,
        "review": review_mod,
    }


def test_get_review_returns_items(review_api_env):
    item = review_api_env["review"].create_review_item(
        title="Review me",
        category="research",
    )

    response = review_api_env["client"].get("/api/review")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert [row["item_id"] for row in data["items"]] == [item["item_id"]]


def test_get_review_filters_by_status_category_and_priority(review_api_env):
    wanted = review_api_env["review"].create_review_item(
        title="Wanted",
        category="research",
        priority="high",
    )
    review_api_env["review"].create_review_item(
        title="Other category",
        category="artifact",
        priority="high",
    )
    review_api_env["review"].create_review_item(
        title="Other priority",
        category="research",
        priority="low",
    )
    review_api_env["review"].create_review_item(
        title="Resolved",
        category="research",
        status="resolved",
        priority="high",
    )

    response = review_api_env["client"].get(
        "/api/review",
        params={
            "status": "open",
            "category": "research",
            "priority": "high",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [row["item_id"] for row in data["items"]] == [wanted["item_id"]]


def test_post_review_creates_item_and_defaults_created_by(review_api_env):
    response = review_api_env["client"].post(
        "/api/review",
        json={
            "title": "New review item",
            "description": "Operator-created item",
            "category": "follow_up",
            "priority": "normal",
            "source_type": "conversation",
            "source_conversation_id": "conv-1",
            "source_message_id": "msg-1",
            "source_tool_name": "memory_search",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    item = data["item"]
    assert item["title"] == "New review item"
    assert item["description"] == "Operator-created item"
    assert item["category"] == "follow_up"
    assert item["priority"] == "normal"
    assert item["created_by"] == "operator"
    assert item["source_conversation_id"] == "conv-1"
    assert item["source_message_id"] == "msg-1"
    assert item["source_tool_name"] == "memory_search"


def test_post_review_metadata_round_trips(review_api_env):
    response = review_api_env["client"].post(
        "/api/review",
        json={
            "title": "Metadata item",
            "metadata": {
                "topic": "retrieval",
                "count": 2,
            },
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["metadata"] == {
        "topic": "retrieval",
        "count": 2,
    }
    assert item["metadata_json"] == '{"count": 2, "topic": "retrieval"}'


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"title": "Bad category", "category": "bad"}, "Invalid review category"),
        ({"title": "Bad priority", "priority": "urgent"}, "Invalid review priority"),
    ],
)
def test_post_review_rejects_invalid_inputs(review_api_env, payload, expected):
    response = review_api_env["client"].post("/api/review", json=payload)

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert expected in response.json()["error"]


def test_patch_review_updates_status(review_api_env):
    item = review_api_env["review"].create_review_item(title="Patch me")

    response = review_api_env["client"].patch(
        f"/api/review/{item['item_id']}",
        json={"status": "resolved"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["item"]["status"] == "resolved"
    assert data["item"]["reviewed_at"] is not None


def test_patch_review_missing_item_returns_404(review_api_env):
    response = review_api_env["client"].patch(
        "/api/review/missing-item",
        json={"status": "resolved"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error": "Review item not found",
    }


def test_patch_review_invalid_status_returns_400(review_api_env):
    item = review_api_env["review"].create_review_item(title="Patch me")

    response = review_api_env["client"].patch(
        f"/api/review/{item['item_id']}",
        json={"status": "queued"},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "Invalid review status" in response.json()["error"]


def test_review_api_does_not_invoke_memory_indexing(review_api_env):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        response = review_api_env["client"].post(
            "/api/review",
            json={
                "title": "No indexing",
                "category": "memory",
            },
        )

    assert response.status_code == 200
    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
