import importlib
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tir.artifacts.service import create_artifact
from tir.workspace.service import ensure_workspace


@pytest.fixture()
def temp_stores(tmp_path):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod
        import tir.review.service as review_mod

        importlib.reload(db_mod)
        importlib.reload(review_mod)
        db_mod.init_databases()
        yield {
            "db": db_mod,
            "review": review_mod,
            "workspace_root": workspace_root,
            "archive_db": tmp_path / "archive.db",
            "working_db": tmp_path / "working.db",
        }


def test_create_get_list_and_update_review_item(temp_stores):
    review = temp_stores["review"]

    item = review.create_review_item(
        title="Investigate retrieval conflict",
        description="Artifact and conversation chunks disagreed.",
        category="contradiction",
        status="open",
        priority="high",
        source_type="artifact_document",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_artifact_id=None,
        source_tool_name="memory_search",
        created_by="operator",
        owner="Lyle",
        metadata={"query": "roadmap.md"},
    )

    assert item["item_id"]
    assert item["title"] == "Investigate retrieval conflict"
    assert item["description"] == "Artifact and conversation chunks disagreed."
    assert item["category"] == "contradiction"
    assert item["status"] == "open"
    assert item["priority"] == "high"
    assert item["source_type"] == "artifact_document"
    assert item["source_conversation_id"] == "conv-1"
    assert item["source_message_id"] == "msg-1"
    assert item["source_tool_name"] == "memory_search"
    assert item["created_by"] == "operator"
    assert item["owner"] == "Lyle"
    assert item["reviewed_at"] is None
    assert item["metadata"] == {"query": "roadmap.md"}
    assert item["metadata_json"] == '{"query": "roadmap.md"}'

    fetched = review.get_review_item(item["item_id"])
    assert fetched == item

    listed = review.list_review_items(
        status="open",
        category="contradiction",
        priority="high",
    )
    assert [row["item_id"] for row in listed] == [item["item_id"]]

    updated = review.update_review_item_status(item["item_id"], "reviewed")
    assert updated["status"] == "reviewed"
    assert updated["reviewed_at"] is not None
    assert updated["updated_at"] >= item["updated_at"]


def test_list_filters_by_status_category_and_priority(temp_stores):
    review = temp_stores["review"]
    first = review.create_review_item(
        title="Research seed",
        category="research",
        priority="normal",
    )
    review.create_review_item(
        title="Tool failure",
        category="tool_failure",
        priority="high",
    )

    open_ids = {item["item_id"] for item in review.list_review_items(status="open")}
    assert first["item_id"] in open_ids
    assert [item["item_id"] for item in review.list_review_items(category="research")] == [
        first["item_id"]
    ]
    assert [item["item_id"] for item in review.list_review_items(priority="normal")] == [
        first["item_id"]
    ]


def test_invalid_category_status_and_priority_rejected(temp_stores):
    review = temp_stores["review"]

    with pytest.raises(review.ReviewValidationError):
        review.create_review_item(title="Bad category", category="unknown")

    with pytest.raises(review.ReviewValidationError):
        review.create_review_item(title="Bad status", status="queued")

    with pytest.raises(review.ReviewValidationError):
        review.create_review_item(title="Bad priority", priority="urgent")

    item = review.create_review_item(title="Valid")
    with pytest.raises(review.ReviewValidationError):
        review.update_review_item_status(item["item_id"], "unknown")


def test_source_artifact_link_can_be_stored(temp_stores):
    review = temp_stores["review"]
    artifact = create_artifact(
        artifact_type="research_note",
        title="Review target artifact",
        path="research/review-target.md",
        workspace_root=temp_stores["workspace_root"],
    )

    item = review.create_review_item(
        title="Review artifact conflict",
        category="artifact",
        source_artifact_id=artifact["artifact_id"],
    )

    assert item["source_artifact_id"] == artifact["artifact_id"]


def test_metadata_must_be_json_serializable(temp_stores):
    review = temp_stores["review"]

    with pytest.raises(review.ReviewValidationError):
        review.create_review_item(
            title="Bad metadata",
            metadata={"bad": object()},
        )


@pytest.mark.parametrize("status", ["reviewed", "dismissed", "resolved"])
def test_reviewed_at_set_for_reviewed_statuses(temp_stores, status):
    review = temp_stores["review"]

    item = review.create_review_item(title="Lifecycle")
    updated = review.update_review_item_status(item["item_id"], status)

    assert updated["status"] == status
    assert updated["reviewed_at"] is not None


def test_reviewed_at_cleared_when_reopened(temp_stores):
    review = temp_stores["review"]

    item = review.create_review_item(title="Lifecycle", status="resolved")
    assert item["reviewed_at"] is not None

    reopened = review.update_review_item_status(item["item_id"], "open")

    assert reopened["status"] == "open"
    assert reopened["reviewed_at"] is None


def test_review_items_table_is_working_db_only(temp_stores):
    archive_conn = sqlite3.connect(temp_stores["archive_db"])
    working_conn = sqlite3.connect(temp_stores["working_db"])
    try:
        archive_tables = {
            row[0]
            for row in archive_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        working_tables = {
            row[0]
            for row in working_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        archive_conn.close()
        working_conn.close()

    assert "review_items" not in archive_tables
    assert "review_items" in working_tables


def test_review_creation_does_not_invoke_memory_indexing(temp_stores):
    review = temp_stores["review"]

    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        review.create_review_item(
            title="No indexing",
            category="memory",
            metadata={"source": "test"},
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()


def test_admin_review_commands(temp_stores, capsys):
    import tir.admin as admin_mod

    importlib.reload(admin_mod)

    admin_mod.cmd_review_add(
        SimpleNamespace(
            title="Review CLI item",
            description="Created from CLI test",
            category="research",
            priority="high",
            source_type="conversation",
            source_conversation_id="conv-1",
            source_message_id="msg-1",
            source_artifact_id=None,
            source_tool_name="memory_search",
            created_by="operator",
            metadata_json='{"topic": "review"}',
        )
    )
    add_output = capsys.readouterr().out
    assert "Review item created" in add_output
    assert "category=research" in add_output
    item_id = add_output.splitlines()[1].split()[0]

    admin_mod.cmd_review_list(
        SimpleNamespace(
            status="open",
            category="research",
            priority=None,
            limit=50,
        )
    )
    list_output = capsys.readouterr().out
    assert item_id in list_output
    assert "Review CLI item" in list_output

    admin_mod.cmd_review_update(
        SimpleNamespace(
            item_id=item_id,
            status="resolved",
        )
    )
    update_output = capsys.readouterr().out
    assert "Review item updated" in update_output
    assert "status=resolved" in update_output

    updated = temp_stores["review"].get_review_item(item_id)
    assert updated["status"] == "resolved"
