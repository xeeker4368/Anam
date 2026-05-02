import importlib
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from tir.artifacts.service import (
    ArtifactValidationError,
    create_artifact,
    create_artifact_file,
    create_artifact_file_with_open_loop,
    get_artifact,
    list_artifacts,
    update_artifact_status,
)
from tir.open_loops.service import OpenLoopValidationError, list_open_loops
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


def test_create_get_list_and_update_artifact(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    artifact = create_artifact(
        artifact_type="research_note",
        title="Session notes",
        description="Initial notes",
        path="research/session-1/notes.md",
        status="draft",
        source="test",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_tool_name="memory_search",
        metadata={"topic": "memory"},
        workspace_root=workspace_root,
    )

    assert artifact["artifact_id"]
    assert artifact["artifact_type"] == "research_note"
    assert artifact["title"] == "Session notes"
    assert artifact["path"] == "research/session-1/notes.md"
    assert artifact["status"] == "draft"
    assert artifact["metadata"] == {"topic": "memory"}
    assert artifact["metadata_json"] == '{"topic": "memory"}'

    fetched = get_artifact(artifact["artifact_id"])
    assert fetched == artifact

    listed = list_artifacts(
        artifact_type="research_note",
        status="draft",
        workspace_root=workspace_root,
    )
    assert [item["artifact_id"] for item in listed] == [artifact["artifact_id"]]

    updated = update_artifact_status(artifact["artifact_id"], "active")
    assert updated["status"] == "active"
    assert updated["updated_at"] >= artifact["updated_at"]


def test_path_none_is_allowed(temp_stores):
    artifact = create_artifact(
        artifact_type="generic",
        title="No file yet",
        path=None,
        workspace_root=temp_stores["workspace_root"],
    )

    assert artifact["path"] is None


def test_invalid_type_and_status_rejected(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ArtifactValidationError):
        create_artifact(
            artifact_type="unknown",
            title="Bad type",
            workspace_root=workspace_root,
        )

    with pytest.raises(ArtifactValidationError):
        create_artifact(
            artifact_type="generic",
            title="Bad status",
            status="unknown",
            workspace_root=workspace_root,
        )

    artifact = create_artifact(
        artifact_type="generic",
        title="Good",
        workspace_root=workspace_root,
    )
    with pytest.raises(ArtifactValidationError):
        update_artifact_status(artifact["artifact_id"], "unknown")


def test_path_validation_rejects_absolute_and_traversal(temp_stores, tmp_path):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ValueError):
        create_artifact(
            artifact_type="generic",
            title="Absolute",
            path=tmp_path / "outside.txt",
            workspace_root=workspace_root,
        )

    with pytest.raises(ValueError):
        create_artifact(
            artifact_type="generic",
            title="Traversal",
            path="../outside.txt",
            workspace_root=workspace_root,
        )


def test_path_validation_rejects_symlink_escape(temp_stores, tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink not available on this platform")

    workspace_root = temp_stores["workspace_root"]
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace_root / "research" / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not available: {exc}")

    with pytest.raises(ValueError):
        create_artifact(
            artifact_type="generic",
            title="Escape",
            path="research/escape/file.txt",
            workspace_root=workspace_root,
        )


def test_artifacts_table_is_working_db_only(temp_stores):
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

    assert "artifacts" not in archive_tables
    assert "artifacts" in working_tables


def test_artifact_creation_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_artifact(
            artifact_type="generic",
            title="No indexing",
            workspace_root=temp_stores["workspace_root"],
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()


def test_list_filters_by_path(temp_stores):
    workspace_root = temp_stores["workspace_root"]
    first = create_artifact(
        artifact_type="code",
        title="A",
        path="coding/a.py",
        workspace_root=workspace_root,
    )
    create_artifact(
        artifact_type="code",
        title="B",
        path="coding/b.py",
        workspace_root=workspace_root,
    )

    listed = list_artifacts(path="coding/a.py", workspace_root=workspace_root)

    assert [item["artifact_id"] for item in listed] == [first["artifact_id"]]


def test_create_artifact_file_creates_file_and_metadata(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    result = create_artifact_file(
        relative_path="research/session-2/notes.md",
        content="Session notes",
        artifact_type="research_note",
        title="Session 2",
        description="Created as one operation",
        status="active",
        source="test",
        source_conversation_id="conv-2",
        source_message_id="msg-2",
        source_tool_name="internal_helper",
        metadata={"topic": "artifacts"},
        workspace_root=workspace_root,
    )

    assert set(result) == {"artifact", "file"}
    assert result["file"] == {
        "path": "research/session-2/notes.md",
        "bytes": len("Session notes"),
    }
    assert (workspace_root / "research/session-2/notes.md").read_text(
        encoding="utf-8"
    ) == "Session notes"

    artifact = result["artifact"]
    assert artifact["artifact_type"] == "research_note"
    assert artifact["title"] == "Session 2"
    assert artifact["description"] == "Created as one operation"
    assert artifact["path"] == "research/session-2/notes.md"
    assert artifact["status"] == "active"
    assert artifact["source"] == "test"
    assert artifact["source_conversation_id"] == "conv-2"
    assert artifact["source_message_id"] == "msg-2"
    assert artifact["source_tool_name"] == "internal_helper"
    assert artifact["metadata"] == {"topic": "artifacts"}


def test_create_artifact_file_supports_draft_status(temp_stores):
    result = create_artifact_file(
        relative_path="drafts/example.md",
        content="Draft",
        artifact_type="writing",
        title="Draft file",
        status="draft",
        workspace_root=temp_stores["workspace_root"],
    )

    assert result["artifact"]["status"] == "draft"
    assert result["artifact"]["path"] == "drafts/example.md"


def test_create_artifact_file_invalid_path_does_not_create_metadata(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ValueError):
        create_artifact_file(
            relative_path="../outside.md",
            content="No file",
            artifact_type="generic",
            title="Bad path",
            workspace_root=workspace_root,
        )

    assert list_artifacts(workspace_root=workspace_root) == []


def test_create_artifact_file_invalid_metadata_does_not_create_file_or_metadata(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ArtifactValidationError):
        create_artifact_file(
            relative_path="drafts/bad-metadata.md",
            content="No file",
            artifact_type="generic",
            title="Bad metadata",
            metadata={"bad": object()},
            workspace_root=workspace_root,
        )

    assert not (workspace_root / "drafts/bad-metadata.md").exists()
    assert list_artifacts(workspace_root=workspace_root) == []


def test_create_artifact_file_invalid_type_and_status_do_not_create_file(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ArtifactValidationError):
        create_artifact_file(
            relative_path="drafts/bad-type.md",
            content="No file",
            artifact_type="unknown",
            title="Bad type",
            workspace_root=workspace_root,
        )

    with pytest.raises(ArtifactValidationError):
        create_artifact_file(
            relative_path="drafts/bad-status.md",
            content="No file",
            artifact_type="generic",
            title="Bad status",
            status="unknown",
            workspace_root=workspace_root,
        )

    assert not (workspace_root / "drafts/bad-type.md").exists()
    assert not (workspace_root / "drafts/bad-status.md").exists()
    assert list_artifacts(workspace_root=workspace_root) == []


def test_create_artifact_file_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_artifact_file(
            relative_path="drafts/no-index.md",
            content="No indexing",
            artifact_type="generic",
            title="No indexing",
            workspace_root=temp_stores["workspace_root"],
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()


def test_create_artifact_file_with_open_loop_creates_linked_records(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    result = create_artifact_file_with_open_loop(
        relative_path="drafts/linked.md",
        content="Draft to continue",
        artifact_type="writing",
        title="Linked Draft",
        description="Artifact description",
        status="draft",
        source="test",
        source_conversation_id="conv-3",
        source_message_id="msg-3",
        source_tool_name="internal_helper",
        metadata={"kind": "draft"},
        create_open_loop=True,
        open_loop_next_action="Revise the ending",
        workspace_root=workspace_root,
    )

    assert set(result) == {"artifact", "file", "open_loop"}
    assert result["file"] == {
        "path": "drafts/linked.md",
        "bytes": len("Draft to continue"),
    }
    assert (workspace_root / "drafts/linked.md").read_text(
        encoding="utf-8"
    ) == "Draft to continue"

    artifact = result["artifact"]
    open_loop = result["open_loop"]
    assert artifact["artifact_type"] == "writing"
    assert artifact["title"] == "Linked Draft"
    assert artifact["metadata"] == {"kind": "draft"}
    assert open_loop["related_artifact_id"] == artifact["artifact_id"]
    assert open_loop["title"] == "Continue draft: Linked Draft"
    assert open_loop["loop_type"] == "unfinished_artifact"
    assert open_loop["priority"] == "normal"
    assert open_loop["next_action"] == "Revise the ending"
    assert open_loop["source"] == "test"
    assert open_loop["source_conversation_id"] == "conv-3"
    assert open_loop["source_message_id"] == "msg-3"
    assert open_loop["source_tool_name"] == "internal_helper"

    listed = list_open_loops(related_artifact_id=artifact["artifact_id"])
    assert [item["open_loop_id"] for item in listed] == [open_loop["open_loop_id"]]


def test_create_artifact_file_with_open_loop_is_optional(temp_stores):
    result = create_artifact_file_with_open_loop(
        relative_path="drafts/no-loop.md",
        content="Finished enough",
        artifact_type="writing",
        title="No Loop",
        create_open_loop=False,
        workspace_root=temp_stores["workspace_root"],
    )

    assert result["artifact"]["title"] == "No Loop"
    assert result["open_loop"] is None
    assert list_open_loops(related_artifact_id=result["artifact"]["artifact_id"]) == []


def test_create_artifact_file_with_open_loop_preserves_custom_loop_data(temp_stores):
    result = create_artifact_file_with_open_loop(
        relative_path="research/custom-loop.md",
        content="Research note",
        artifact_type="research_note",
        title="Custom Loop",
        create_open_loop=True,
        open_loop_title="Finish research synthesis",
        open_loop_description="Needs one more comparison pass",
        open_loop_next_action="Compare against prior notes",
        open_loop_priority="high",
        open_loop_metadata={"reason": "unfinished"},
        source="artifact-source",
        source_conversation_id="artifact-conv",
        source_message_id="artifact-msg",
        source_tool_name="artifact-tool",
        open_loop_source="loop-source",
        open_loop_source_conversation_id="loop-conv",
        open_loop_source_message_id="loop-msg",
        open_loop_source_tool_name="loop-tool",
        workspace_root=temp_stores["workspace_root"],
    )

    open_loop = result["open_loop"]
    assert open_loop["title"] == "Finish research synthesis"
    assert open_loop["description"] == "Needs one more comparison pass"
    assert open_loop["next_action"] == "Compare against prior notes"
    assert open_loop["priority"] == "high"
    assert open_loop["metadata"] == {"reason": "unfinished"}
    assert open_loop["source"] == "loop-source"
    assert open_loop["source_conversation_id"] == "loop-conv"
    assert open_loop["source_message_id"] == "loop-msg"
    assert open_loop["source_tool_name"] == "loop-tool"


def test_create_artifact_file_with_open_loop_invalid_path_creates_nothing(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(ValueError):
        create_artifact_file_with_open_loop(
            relative_path="../outside.md",
            content="No file",
            artifact_type="writing",
            title="Bad Path",
            create_open_loop=True,
            workspace_root=workspace_root,
        )

    assert list_artifacts(workspace_root=workspace_root) == []
    assert list_open_loops() == []


def test_create_artifact_file_with_open_loop_invalid_loop_rejects_before_writing(temp_stores):
    workspace_root = temp_stores["workspace_root"]

    with pytest.raises(OpenLoopValidationError):
        create_artifact_file_with_open_loop(
            relative_path="drafts/bad-loop-priority.md",
            content="No file",
            artifact_type="writing",
            title="Bad Loop",
            create_open_loop=True,
            open_loop_priority="urgent",
            workspace_root=workspace_root,
        )

    with pytest.raises(OpenLoopValidationError):
        create_artifact_file_with_open_loop(
            relative_path="drafts/bad-loop-type.md",
            content="No file",
            artifact_type="writing",
            title="Bad Loop",
            create_open_loop=True,
            open_loop_type="task_manager_item",
            workspace_root=workspace_root,
        )

    with pytest.raises(OpenLoopValidationError):
        create_artifact_file_with_open_loop(
            relative_path="drafts/bad-loop-title.md",
            content="No file",
            artifact_type="writing",
            title="Bad Loop",
            create_open_loop=True,
            open_loop_title="   ",
            workspace_root=workspace_root,
        )

    assert not (workspace_root / "drafts/bad-loop-priority.md").exists()
    assert not (workspace_root / "drafts/bad-loop-type.md").exists()
    assert not (workspace_root / "drafts/bad-loop-title.md").exists()
    assert list_artifacts(workspace_root=workspace_root) == []
    assert list_open_loops() == []


def test_create_artifact_file_with_open_loop_does_not_invoke_memory_indexing(temp_stores):
    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        create_artifact_file_with_open_loop(
            relative_path="drafts/no-loop-index.md",
            content="No indexing",
            artifact_type="writing",
            title="No loop indexing",
            create_open_loop=True,
            workspace_root=temp_stores["workspace_root"],
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
