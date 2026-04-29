import importlib
import sqlite3
from unittest.mock import patch

import pytest

from tir.artifacts.service import create_artifact
from tir.feedback.service import (
    FeedbackValidationError,
    create_feedback_record,
    get_feedback_record,
    list_feedback_records,
    update_feedback_status,
)
from tir.open_loops.service import create_open_loop
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


def test_create_get_list_and_update_feedback_record(temp_stores):
    feedback = create_feedback_record(
        feedback_type="user_correction",
        title="Correct project interpretation",
        description="The prior interpretation missed a project decision.",
        user_feedback="Learning means substrate-level learning, not weights.",
        status="open",
        target_type="message",
        target_id="msg-1",
        source="test",
        source_conversation_id="conv-1",
        source_message_id="msg-2",
        source_tool_name="memory_search",
        metadata={"topic": "learning"},
    )

    assert feedback["feedback_id"]
    assert feedback["feedback_type"] == "user_correction"
    assert feedback["title"] == "Correct project interpretation"
    assert feedback["description"] == "The prior interpretation missed a project decision."
    assert feedback["user_feedback"] == "Learning means substrate-level learning, not weights."
    assert feedback["status"] == "open"
    assert feedback["target_type"] == "message"
    assert feedback["target_id"] == "msg-1"
    assert feedback["source"] == "test"
    assert feedback["source_conversation_id"] == "conv-1"
    assert feedback["source_message_id"] == "msg-2"
    assert feedback["source_tool_name"] == "memory_search"
    assert feedback["resolved_at"] is None
    assert feedback["metadata"] == {"topic": "learning"}
    assert feedback["metadata_json"] == '{"topic": "learning"}'

    fetched = get_feedback_record(feedback["feedback_id"])
    assert fetched == feedback

    listed = list_feedback_records(
        feedback_type="user_correction",
        status="open",
        target_type="message",
        target_id="msg-1",
        source_conversation_id="conv-1",
    )
    assert [item["feedback_id"] for item in listed] == [feedback["feedback_id"]]

    updated = update_feedback_status(feedback["feedback_id"], "accepted")
    assert updated["status"] == "accepted"
    assert updated["resolved_at"] is None
    assert updated["updated_at"] >= feedback["updated_at"]


def test_required_title_and_user_feedback_validation(temp_stores):
    with pytest.raises(FeedbackValidationError):
        create_feedback_record(
            feedback_type="generic",
            title="   ",
            user_feedback="Required",
        )

    with pytest.raises(FeedbackValidationError):
        create_feedback_record(
            feedback_type="generic",
            title="Required",
            user_feedback="   ",
        )


def test_invalid_feedback_type_and_status_rejected(temp_stores):
    with pytest.raises(FeedbackValidationError):
        create_feedback_record(
            feedback_type="unknown",
            title="Bad type",
            user_feedback="Invalid type",
        )

    with pytest.raises(FeedbackValidationError):
        create_feedback_record(
            feedback_type="generic",
            title="Bad status",
            user_feedback="Invalid status",
            status="unknown",
        )

    feedback = create_feedback_record(
        feedback_type="generic",
        title="Good",
        user_feedback="Valid",
    )
    with pytest.raises(FeedbackValidationError):
        update_feedback_status(feedback["feedback_id"], "unknown")


def test_non_serializable_metadata_rejected(temp_stores):
    with pytest.raises(FeedbackValidationError):
        create_feedback_record(
            feedback_type="generic",
            title="Bad metadata",
            user_feedback="Metadata cannot be serialized",
            metadata={"bad": object()},
        )


def test_related_artifact_and_open_loop_links_work(temp_stores):
    artifact = create_artifact(
        artifact_type="research_note",
        title="Feedback target artifact",
        path="research/feedback-target.md",
        workspace_root=temp_stores["workspace_root"],
    )
    open_loop = create_open_loop(
        title="Feedback target loop",
        related_artifact_id=artifact["artifact_id"],
    )

    feedback = create_feedback_record(
        feedback_type="approval",
        title="Approve direction",
        user_feedback="This direction is useful.",
        related_artifact_id=artifact["artifact_id"],
        related_open_loop_id=open_loop["open_loop_id"],
    )

    assert feedback["related_artifact_id"] == artifact["artifact_id"]
    assert feedback["related_open_loop_id"] == open_loop["open_loop_id"]

    listed = list_feedback_records(
        related_artifact_id=artifact["artifact_id"],
        related_open_loop_id=open_loop["open_loop_id"],
    )
    assert [item["feedback_id"] for item in listed] == [feedback["feedback_id"]]


def test_related_foreign_keys_are_enforced(temp_stores):
    with pytest.raises(sqlite3.IntegrityError):
        create_feedback_record(
            feedback_type="generic",
            title="Bad artifact link",
            user_feedback="Missing artifact",
            related_artifact_id="missing-artifact",
        )

    with pytest.raises(sqlite3.IntegrityError):
        create_feedback_record(
            feedback_type="generic",
            title="Bad open-loop link",
            user_feedback="Missing open loop",
            related_open_loop_id="missing-open-loop",
        )


def test_resolved_at_lifecycle(temp_stores):
    feedback = create_feedback_record(
        feedback_type="generic",
        title="Lifecycle",
        user_feedback="Track lifecycle fields",
    )

    resolved = update_feedback_status(feedback["feedback_id"], "resolved")
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None

    disputed = update_feedback_status(feedback["feedback_id"], "disputed")
    assert disputed["status"] == "disputed"
    assert disputed["resolved_at"] is None

    archived = update_feedback_status(feedback["feedback_id"], "archived")
    assert archived["status"] == "archived"
    assert archived["resolved_at"] is not None

    reopened = update_feedback_status(feedback["feedback_id"], "open")
    assert reopened["status"] == "open"
    assert reopened["resolved_at"] is None


def test_feedback_records_table_is_working_db_only(temp_stores):
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

    assert "feedback_records" not in archive_tables
    assert "feedback_records" in working_tables


def test_feedback_creation_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_feedback_record(
            feedback_type="tool_behavior_feedback",
            title="No indexing",
            user_feedback="Do not index this feedback as memory.",
            metadata={"source": "test"},
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
