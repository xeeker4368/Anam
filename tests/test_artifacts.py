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
    get_artifact,
    list_artifacts,
    update_artifact_status,
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
