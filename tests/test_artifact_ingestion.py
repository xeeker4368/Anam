import importlib
import sqlite3
from unittest.mock import patch

import pytest

from tir.artifacts.ingestion import ArtifactIngestionError, ingest_artifact_file
from tir.engine.context import build_system_prompt
from tir.workspace.service import ensure_workspace


@pytest.fixture()
def temp_ingestion_env(tmp_path):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"), \
         patch("tir.config.CHROMA_DIR", str(tmp_path / "chromadb")):
        import tir.memory.db as db_mod
        import tir.memory.chroma as chroma_mod

        importlib.reload(db_mod)
        chroma_mod.reset_client()
        db_mod.init_databases()
        yield {
            "db": db_mod,
            "workspace_root": workspace_root,
            "working_db": tmp_path / "working.db",
        }


def _fts_rows(working_db):
    conn = sqlite3.connect(working_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT chunk_id, text, conversation_id, user_id, source_type, source_trust "
            "FROM chunks_fts ORDER BY chunk_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def test_ingest_saves_file_to_controlled_upload_path(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        result = ingest_artifact_file(
            filename="Project Notes.md",
            content=b"alpha project notes",
            user_id="user-1",
            source_conversation_id="conv-1",
            source_message_id="msg-1",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    artifact = result["artifact"]
    path = artifact["path"]
    assert path.startswith("uploads/")
    assert f"/{artifact['artifact_id']}/Project Notes.md" in path
    assert (temp_ingestion_env["workspace_root"] / path).read_bytes() == b"alpha project notes"
    assert result["file"]["bytes"] == len(b"alpha project notes")


@pytest.mark.parametrize("filename", ["../secret.txt", "..\\secret.txt"])
def test_ingest_rejects_path_traversal_filename(temp_ingestion_env, filename):
    with pytest.raises(ArtifactIngestionError):
        ingest_artifact_file(
            filename=filename,
            content=b"secret",
            workspace_root=temp_ingestion_env["workspace_root"],
        )


@pytest.mark.parametrize("filename", ["", "   ", "$$$"])
def test_ingest_rejects_empty_or_unsafe_filename(temp_ingestion_env, filename):
    with pytest.raises(ArtifactIngestionError):
        ingest_artifact_file(
            filename=filename,
            content=b"data",
            workspace_root=temp_ingestion_env["workspace_root"],
        )


def test_ingest_computes_hash_and_creates_artifact_metadata(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        result = ingest_artifact_file(
            filename="roadmap.md",
            content=b"Project Anam roadmap",
            user_id="user-2",
            title="Roadmap",
            description="Uploaded roadmap",
            source_conversation_id="conv-2",
            source_message_id="msg-2",
            source_tool_name="upload_helper",
            metadata={"topic": "planning"},
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    artifact = result["artifact"]
    metadata = artifact["metadata"]
    assert artifact["artifact_type"] == "uploaded_file"
    assert artifact["status"] == "active"
    assert artifact["title"] == "Roadmap"
    assert artifact["source"] == "upload"
    assert artifact["source_conversation_id"] == "conv-2"
    assert artifact["source_message_id"] == "msg-2"
    assert artifact["source_tool_name"] == "upload_helper"
    assert metadata["filename"] == "roadmap.md"
    assert metadata["safe_filename"] == "roadmap.md"
    assert metadata["size_bytes"] == len(b"Project Anam roadmap")
    assert metadata["sha256"] == result["file"]["sha256"]
    assert metadata["created_by"] == "user"
    assert metadata["authority"] == "source_material"
    assert metadata["indexing_status"] == "indexed"
    assert metadata["source_type"] == "artifact_document"
    assert metadata["user_id"] == "user-2"
    assert metadata["topic"] == "planning"


def test_supported_text_file_writes_event_and_content_chunks(temp_ingestion_env):
    captured = []

    def capture_upsert(chunk_id, text, metadata):
        captured.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})

    with patch("tir.memory.artifact_indexing.upsert_chunk", side_effect=capture_upsert):
        result = ingest_artifact_file(
            filename="notes.md",
            content=b"alpha concept\n\nbeta detail",
            user_id="user-3",
            title="Concept Notes",
            source_conversation_id="conv-3",
            source_message_id="msg-3",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    artifact_id = result["artifact"]["artifact_id"]
    assert result["indexing"] == {
        "status": "indexed",
        "content_chunks_written": 1,
        "event_chunks_written": 1,
        "reason": None,
    }
    assert [item["chunk_id"] for item in captured] == [
        f"artifact_{artifact_id}_event",
        f"artifact_{artifact_id}_chunk_0",
    ]
    for item in captured:
        metadata = item["metadata"]
        assert metadata["source_type"] == "artifact_document"
        assert metadata["artifact_id"] == artifact_id
        assert metadata["title"] == "Concept Notes"
        assert metadata["filename"] == "notes.md"
        assert metadata["path"] == result["artifact"]["path"]
        assert metadata["authority"] == "source_material"
        assert metadata["source_conversation_id"] == "conv-3"
        assert metadata["source_message_id"] == "msg-3"
        assert metadata["user_id"] == "user-3"

    rows = _fts_rows(temp_ingestion_env["working_db"])
    assert len(rows) == 2
    assert all(row["source_type"] == "artifact_document" for row in rows)
    assert all(row["conversation_id"] == "conv-3" for row in rows)
    assert all(row["user_id"] == "user-3" for row in rows)
    assert any("alpha concept" in row["text"] for row in rows)


def test_unsupported_file_writes_event_chunk_only(temp_ingestion_env):
    captured = []

    def capture_upsert(chunk_id, text, metadata):
        captured.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})

    with patch("tir.memory.artifact_indexing.upsert_chunk", side_effect=capture_upsert):
        result = ingest_artifact_file(
            filename="diagram.png",
            content=b"\x89PNG\r\nbinary",
            title="Diagram",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    artifact_id = result["artifact"]["artifact_id"]
    assert result["indexing"] == {
        "status": "metadata_only",
        "content_chunks_written": 0,
        "event_chunks_written": 1,
        "reason": "unsupported_type",
    }
    assert [item["chunk_id"] for item in captured] == [f"artifact_{artifact_id}_event"]
    assert result["artifact"]["metadata"]["indexing_status"] == "metadata_only"


def test_duplicate_hash_upload_does_not_silently_overwrite(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        first = ingest_artifact_file(
            filename="same.md",
            content=b"same content",
            workspace_root=temp_ingestion_env["workspace_root"],
        )
        second = ingest_artifact_file(
            filename="same.md",
            content=b"same content",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    assert first["file"]["sha256"] == second["file"]["sha256"]
    assert first["artifact"]["artifact_id"] != second["artifact"]["artifact_id"]
    assert first["artifact"]["path"] != second["artifact"]["path"]
    assert (temp_ingestion_env["workspace_root"] / first["artifact"]["path"]).exists()
    assert (temp_ingestion_env["workspace_root"] / second["artifact"]["path"]).exists()


def test_revision_of_can_be_recorded(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        original = ingest_artifact_file(
            filename="draft.md",
            content=b"draft one",
            title="Draft",
            workspace_root=temp_ingestion_env["workspace_root"],
        )
        revision = ingest_artifact_file(
            filename="draft.md",
            content=b"draft two",
            title="Draft v2",
            revision_of=original["artifact"]["artifact_id"],
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    assert revision["artifact"]["revision_of"] == original["artifact"]["artifact_id"]


def test_uploaded_content_is_not_operational_guidance_or_core_belief(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        result = ingest_artifact_file(
            filename="claim.md",
            content=b"This is source material, not core belief.",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    metadata = result["artifact"]["metadata"]
    assert metadata["authority"] == "source_material"
    assert metadata["authority"] != "current_project_state"
    assert "operational_guidance" not in metadata
    assert "core_belief" not in metadata


def test_generated_file_defaults_to_draft_authority(temp_ingestion_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        result = ingest_artifact_file(
            filename="generated-note.md",
            content=b"Generated draft",
            artifact_type="generated_file",
            source="generation",
            created_by="tool",
            workspace_root=temp_ingestion_env["workspace_root"],
        )

    assert result["artifact"]["path"].startswith("generated/")
    assert result["artifact"]["metadata"]["authority"] == "draft"


def test_artifact_document_context_formatting_identifies_source_material():
    prompt = build_system_prompt(
        user_name="Lyle",
        retrieved_chunks=[
            {
                "text": "Artifact body text",
                "metadata": {
                    "source_type": "artifact_document",
                    "title": "Project Anam Roadmap",
                    "filename": "roadmap.md",
                    "authority": "source_material",
                    "created_at": "2026-05-05T12:00:00+00:00",
                },
            }
        ],
    )

    assert "[Artifact source: Project Anam Roadmap, authority: source_material, file: roadmap.md]" in prompt
    assert "Artifact body text" in prompt
