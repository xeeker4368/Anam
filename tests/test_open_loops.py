import importlib
import sqlite3
from unittest.mock import patch

import pytest

from tir.artifacts.service import create_artifact
from tir.open_loops.service import (
    OpenLoopValidationError,
    create_open_loop,
    get_open_loop,
    list_open_loops,
    update_open_loop_status,
)
from tir.workspace.service import ensure_workspace


@pytest.fixture()
def temp_stores(tmp_path):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod

        importlib.reload(db_mod)
        db_mod.init_databases()
        yield {
            "db": db_mod,
            "workspace_root": workspace_root,
            "archive_db": tmp_path / "archive.db",
            "working_db": tmp_path / "working.db",
        }


def test_create_get_list_and_update_open_loop(temp_stores):
    open_loop = create_open_loop(
        title="Continue research",
        description="Unfinished research note",
        status="open",
        loop_type="interrupted_research",
        priority="high",
        source="test",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_tool_name="memory_search",
        next_action="Review the remaining sources",
        metadata={"topic": "continuity"},
    )

    assert open_loop["open_loop_id"]
    assert open_loop["title"] == "Continue research"
    assert open_loop["description"] == "Unfinished research note"
    assert open_loop["status"] == "open"
    assert open_loop["loop_type"] == "interrupted_research"
    assert open_loop["priority"] == "high"
    assert open_loop["source"] == "test"
    assert open_loop["source_conversation_id"] == "conv-1"
    assert open_loop["source_message_id"] == "msg-1"
    assert open_loop["source_tool_name"] == "memory_search"
    assert open_loop["next_action"] == "Review the remaining sources"
    assert open_loop["closed_at"] is None
    assert open_loop["metadata"] == {"topic": "continuity"}
    assert open_loop["metadata_json"] == '{"topic": "continuity"}'

    fetched = get_open_loop(open_loop["open_loop_id"])
    assert fetched == open_loop

    listed = list_open_loops(
        status="open",
        loop_type="interrupted_research",
        priority="high",
        source_conversation_id="conv-1",
    )
    assert [item["open_loop_id"] for item in listed] == [open_loop["open_loop_id"]]

    updated = update_open_loop_status(open_loop["open_loop_id"], "in_progress")
    assert updated["status"] == "in_progress"
    assert updated["closed_at"] is None
    assert updated["updated_at"] >= open_loop["updated_at"]


def test_optional_artifact_link(temp_stores):
    artifact = create_artifact(
        artifact_type="research_note",
        title="Linked artifact",
        path="research/linked.md",
        workspace_root=temp_stores["workspace_root"],
    )

    open_loop = create_open_loop(
        title="Summarize artifact",
        loop_type="unfinished_artifact",
        related_artifact_id=artifact["artifact_id"],
    )

    assert open_loop["related_artifact_id"] == artifact["artifact_id"]

    listed = list_open_loops(related_artifact_id=artifact["artifact_id"])
    assert [item["open_loop_id"] for item in listed] == [open_loop["open_loop_id"]]


def test_related_artifact_foreign_key_is_enforced(temp_stores):
    with pytest.raises(sqlite3.IntegrityError):
        create_open_loop(
            title="Bad artifact link",
            related_artifact_id="missing-artifact",
        )


def test_closed_at_is_set_for_closed_and_archived(temp_stores):
    first = create_open_loop(title="Close this")
    second = create_open_loop(title="Archive this")

    closed = update_open_loop_status(first["open_loop_id"], "closed")
    archived = update_open_loop_status(second["open_loop_id"], "archived")

    assert closed["status"] == "closed"
    assert closed["closed_at"] is not None
    assert archived["status"] == "archived"
    assert archived["closed_at"] is not None


def test_closed_at_is_cleared_when_reopened(temp_stores):
    open_loop = create_open_loop(title="Reopen this", status="closed")
    assert open_loop["closed_at"] is not None

    reopened = update_open_loop_status(open_loop["open_loop_id"], "open")
    assert reopened["status"] == "open"
    assert reopened["closed_at"] is None

    blocked = update_open_loop_status(open_loop["open_loop_id"], "blocked")
    assert blocked["status"] == "blocked"
    assert blocked["closed_at"] is None


def test_invalid_status_type_priority_and_title_rejected(temp_stores):
    with pytest.raises(OpenLoopValidationError):
        create_open_loop(title="Bad status", status="unknown")

    with pytest.raises(OpenLoopValidationError):
        create_open_loop(title="Bad type", loop_type="task_manager_item")

    with pytest.raises(OpenLoopValidationError):
        create_open_loop(title="Bad priority", priority="urgent")

    with pytest.raises(OpenLoopValidationError):
        create_open_loop(title="   ")

    open_loop = create_open_loop(title="Good")
    with pytest.raises(OpenLoopValidationError):
        update_open_loop_status(open_loop["open_loop_id"], "unknown")


def test_invalid_metadata_rejected(temp_stores):
    with pytest.raises(OpenLoopValidationError):
        create_open_loop(
            title="Bad metadata",
            metadata={"bad": object()},
        )


def test_open_loops_table_is_working_db_only(temp_stores):
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

    assert "open_loops" not in archive_tables
    assert "open_loops" in working_tables


def test_open_loop_creation_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_open_loop(
            title="No indexing",
            loop_type="generic",
            metadata={"source": "test"},
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
