import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tir.artifacts.ingestion import MAX_INGEST_BYTES
from tir.workspace.service import ensure_workspace


@pytest.fixture()
def upload_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")
    ensure_workspace(tmp_path / "workspace")

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.artifacts.ingestion as ingestion_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    importlib.reload(ingestion_mod)
    chroma_mod.reset_client()
    importlib.reload(routes_mod)
    db_mod.init_databases()

    user = db_mod.create_user("Upload User", role="admin")
    other_user = db_mod.create_user("Other User")
    return {
        "client": TestClient(routes_mod.app),
        "db": db_mod,
        "workspace_root": tmp_path / "workspace",
        "working_db": tmp_path / "data" / "prod" / "working.db",
        "user": user,
        "other_user": other_user,
        "routes": routes_mod,
    }


def _post_upload(client, *, filename="note.md", content=b"upload marker", data=None):
    return client.post(
        "/api/artifacts/upload",
        data=data or {},
        files={"file": (filename, content, "application/octet-stream")},
    )


def _fts_rows(working_db):
    conn = sqlite3.connect(working_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT chunk_id, text, conversation_id, user_id, source_type "
            "FROM chunks_fts ORDER BY chunk_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def test_successful_text_upload_creates_artifact_and_returns_ok(upload_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="source.md",
            content=b"distinct upload marker alpha",
            data={
                "user_id": upload_env["user"]["id"],
                "title": "Source Note",
                "description": "Uploaded source",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["artifact"]["title"] == "Source Note"
    assert data["artifact"]["artifact_type"] == "uploaded_file"
    assert data["artifact"]["metadata"]["user_id"] == upload_env["user"]["id"]
    assert data["file"]["sha256"]
    assert data["indexing"]["status"] == "indexed"
    assert data["indexing"]["event_chunks_written"] == 1
    assert data["indexing"]["content_chunks_written"] == 1
    assert str(upload_env["workspace_root"]) not in response.text


def test_uploaded_text_is_retrievable_by_marker(upload_env):
    marker = "retrievableartifactmarker"
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="memory.md",
            content=f"This uploaded text contains {marker}.".encode(),
            data={"user_id": upload_env["user"]["id"]},
        )

    assert response.status_code == 200

    from tir.memory.retrieval import retrieve

    with patch("tir.memory.retrieval.query_similar", return_value=[]):
        results = retrieve(marker, max_results=5)

    assert results
    assert any("artifact_document" == item["metadata"]["source_type"] for item in results)
    assert any(marker in item["text"] for item in results)


def test_unsupported_binary_upload_is_metadata_only(upload_env):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="diagram.png",
            content=b"\x89PNG\r\nbinary",
            data={"user_id": upload_env["user"]["id"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["indexing"] == {
        "status": "metadata_only",
        "content_chunks_written": 0,
        "event_chunks_written": 1,
        "reason": "unsupported_type",
    }
    rows = _fts_rows(upload_env["working_db"])
    assert len(rows) == 1
    assert rows[0]["chunk_id"].endswith("_event")


def test_oversized_file_is_rejected(upload_env):
    response = _post_upload(
        upload_env["client"],
        filename="too-large.md",
        content=b"x" * (MAX_INGEST_BYTES + 1),
        data={"user_id": upload_env["user"]["id"]},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "exceeds" in response.json()["error"]


@pytest.mark.parametrize("filename", ["", "../bad.md", "..\\bad.md"])
def test_bad_filename_is_rejected(upload_env, filename):
    response = _post_upload(
        upload_env["client"],
        filename=filename,
        content=b"bad",
        data={"user_id": upload_env["user"]["id"]},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_valid_source_conversation_and_message_are_linked(upload_env):
    conv_id = upload_env["db"].start_conversation(upload_env["user"]["id"])
    message = upload_env["db"].save_message(
        conv_id,
        upload_env["user"]["id"],
        "user",
        "Here is source context",
    )

    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="linked.md",
            content=b"linked source",
            data={
                "user_id": upload_env["user"]["id"],
                "source_conversation_id": conv_id,
                "source_message_id": message["id"],
            },
        )

    assert response.status_code == 200
    artifact = response.json()["artifact"]
    assert artifact["source_conversation_id"] == conv_id
    assert artifact["source_message_id"] == message["id"]
    rows = _fts_rows(upload_env["working_db"])
    assert all(row["conversation_id"] == conv_id for row in rows)
    assert all(row["user_id"] == upload_env["user"]["id"] for row in rows)


def test_source_message_without_conversation_infers_valid_conversation(upload_env):
    conv_id = upload_env["db"].start_conversation(upload_env["user"]["id"])
    message = upload_env["db"].save_message(
        conv_id,
        upload_env["user"]["id"],
        "user",
        "Message source",
    )

    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="inferred.md",
            content=b"inferred source",
            data={
                "user_id": upload_env["user"]["id"],
                "source_message_id": message["id"],
            },
        )

    assert response.status_code == 200
    artifact = response.json()["artifact"]
    assert artifact["source_conversation_id"] == conv_id
    assert artifact["source_message_id"] == message["id"]


def test_message_conversation_mismatch_is_rejected(upload_env):
    conv_id = upload_env["db"].start_conversation(upload_env["user"]["id"])
    other_conv_id = upload_env["db"].start_conversation(upload_env["user"]["id"])
    message = upload_env["db"].save_message(
        other_conv_id,
        upload_env["user"]["id"],
        "user",
        "Other conversation message",
    )

    response = _post_upload(
        upload_env["client"],
        filename="mismatch.md",
        content=b"mismatch",
        data={
            "user_id": upload_env["user"]["id"],
            "source_conversation_id": conv_id,
            "source_message_id": message["id"],
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "ok": False,
        "error": "Source message does not belong to source conversation",
    }


def test_wrong_user_conversation_link_is_rejected(upload_env):
    other_conv_id = upload_env["db"].start_conversation(upload_env["other_user"]["id"])

    response = _post_upload(
        upload_env["client"],
        filename="wrong-conv.md",
        content=b"wrong user",
        data={
            "user_id": upload_env["user"]["id"],
            "source_conversation_id": other_conv_id,
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "ok": False,
        "error": "Source conversation does not belong to user",
    }


def test_wrong_user_message_link_is_rejected(upload_env):
    other_conv_id = upload_env["db"].start_conversation(upload_env["other_user"]["id"])
    message = upload_env["db"].save_message(
        other_conv_id,
        upload_env["other_user"]["id"],
        "user",
        "Other user message",
    )

    response = _post_upload(
        upload_env["client"],
        filename="wrong-message.md",
        content=b"wrong user",
        data={
            "user_id": upload_env["user"]["id"],
            "source_message_id": message["id"],
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "ok": False,
        "error": "Source message does not belong to user",
    }


def test_response_does_not_expose_absolute_paths_or_secrets(upload_env, monkeypatch):
    monkeypatch.setenv("MOLTBOOK_TOKEN", "secret-token")
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = _post_upload(
            upload_env["client"],
            filename="safe.md",
            content=b"safe content",
            data={"user_id": upload_env["user"]["id"]},
        )

    assert response.status_code == 200
    assert str(upload_env["workspace_root"]) not in response.text
    assert "secret-token" not in response.text
    # JSON serialization should not accidentally include raw absolute paths.
    json.dumps(response.json())
