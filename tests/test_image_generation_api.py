import importlib
import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tir.media.backends.base import (
    ImageGenerationBackendRequest,
    ImageGenerationBackendResult,
)
from tir.workspace.service import ensure_workspace


class FakeImageBackend:
    backend_name = "comfyui"

    def __init__(self):
        self.requests = []

    def validate_config(self):
        return None

    def generate(self, request: ImageGenerationBackendRequest):
        self.requests.append(request)
        return ImageGenerationBackendResult(
            content=b"\x89PNG api generated image bytes",
            filename="api-generated.png",
            metadata={
                "workflow_id": "api-workflow",
                "generation_model": "api-test-model",
            },
        )


def _load_image_api_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", workspace_root)
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_DEFAULT_BACKEND", "comfyui")
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_MAX_PROMPT_CHARS", 2000)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_MAX_WIDTH", 2048)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_MAX_HEIGHT", 2048)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_ALLOW_AGENT_TOOL", False)
    monkeypatch.setattr("tir.config.COMFYUI_WORKFLOW_PATH", str(tmp_path / "workflow.json"))
    monkeypatch.setattr("tir.config.COMFYUI_BASE_URL", "http://127.0.0.1:8188")

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.media.image_generation as image_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    chroma_mod.reset_client()
    importlib.reload(image_mod)
    importlib.reload(routes_mod)
    db_mod.init_databases()

    user = db_mod.create_user("Image API User", role="admin")
    return {
        "client": TestClient(routes_mod.app),
        "db": db_mod,
        "image_mod": image_mod,
        "routes_mod": routes_mod,
        "user": user,
        "workspace_root": workspace_root,
        "working_db": tmp_path / "data" / "prod" / "working.db",
    }


def _fts_rows(working_db: Path):
    conn = sqlite3.connect(working_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT chunk_id, text, user_id, source_type FROM chunks_fts ORDER BY chunk_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _artifact_count(working_db: Path):
    conn = sqlite3.connect(working_db)
    try:
        return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    finally:
        conn.close()


def test_image_generation_api_disabled_returns_structured_error(tmp_path, monkeypatch):
    env = _load_image_api_env(tmp_path, monkeypatch)

    def disabled_generation(**kwargs):
        return {
            "ok": False,
            "generation_error": True,
            "error_type": "config_error",
            "error": "Image generation is disabled in configuration",
            "backend": kwargs.get("backend") or "comfyui",
            "artifact_created": False,
        }

    monkeypatch.setattr(env["routes_mod"], "generate_image", disabled_generation)

    response = env["client"].post(
        "/api/image-generation/generate",
        json={
            "user_id": env["user"]["id"],
            "prompt": "disabled generated media test",
            "backend": "comfyui",
            "width": 512,
            "height": 512,
        },
    )

    data = response.json()
    assert response.status_code == 400
    assert data["generation_error"] is True
    assert data["error_type"] == "config_error"
    assert data["artifact_created"] is False
    assert _artifact_count(env["working_db"]) == 0


def test_image_generation_api_success_creates_generated_image_artifact(tmp_path, monkeypatch):
    env = _load_image_api_env(tmp_path, monkeypatch)
    backend = FakeImageBackend()

    def fake_generate_image(**kwargs):
        return env["image_mod"].generate_image(
            **kwargs,
            backend_factory=lambda _name: backend,
            workspace_root=env["workspace_root"],
        )

    monkeypatch.setattr(env["routes_mod"], "generate_image", fake_generate_image)
    monkeypatch.setattr(env["image_mod"], "IMAGE_GENERATION_ENABLED", True)

    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        response = env["client"].post(
            "/api/image-generation/generate",
            json={
                "user_id": env["user"]["id"],
                "prompt": "browser generated media test",
                "negative_prompt": "no identity assignment",
                "backend": "comfyui",
                "width": 640,
                "height": 512,
                "seed": 123,
                "intended_use": "reference",
            },
        )

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["artifact_created"] is True
    artifact = data["artifact"]
    metadata = artifact["metadata"]
    assert artifact["artifact_type"] == "generated_file"
    assert artifact["source"] == "generation"
    assert metadata["media_kind"] == "generated_image"
    assert metadata["prompt"] == "browser generated media test"
    assert metadata["negative_prompt"] == "no identity assignment"
    assert metadata["generation_backend"] == "comfyui"
    assert metadata["generation_model"] == "api-test-model"
    assert metadata["workflow_id"] == "api-workflow"
    assert metadata["seed"] == 123
    assert metadata["width"] == 640
    assert metadata["height"] == 512
    assert metadata["source_user_id"] == env["user"]["id"]
    assert metadata["intended_use"] == "reference"

    rows = _fts_rows(env["working_db"])
    assert len(rows) == 1
    assert rows[0]["user_id"] == env["user"]["id"]
    assert "api generated image bytes" not in rows[0]["text"]
    assert "Generation prompt (provenance metadata): browser generated media test" in rows[0]["text"]

    preview = env["client"].get(f"/api/artifacts/{artifact['artifact_id']}/file")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")
    assert preview.content == b"\x89PNG api generated image bytes"


def test_image_generation_api_rejects_avatar_intended_use(tmp_path, monkeypatch):
    env = _load_image_api_env(tmp_path, monkeypatch)

    response = env["client"].post(
        "/api/image-generation/generate",
        json={
            "user_id": env["user"]["id"],
            "prompt": "invalid intended use",
            "backend": "comfyui",
            "intended_use": "avatar_exploration",
        },
    )

    assert response.status_code == 400
    assert "Invalid intended_use" in response.json()["error"]
    assert _artifact_count(env["working_db"]) == 0


def test_image_file_endpoint_rejects_non_image_artifact(tmp_path, monkeypatch):
    env = _load_image_api_env(tmp_path, monkeypatch)

    with monkeypatch.context() as context:
        context.setattr("tir.memory.artifact_indexing.upsert_chunk", lambda **_kwargs: None)
        upload = env["client"].post(
            "/api/artifacts/upload",
            data={"user_id": env["user"]["id"], "title": "Text Artifact"},
            files={"file": ("note.md", b"not an image", "text/markdown")},
        )

    artifact_id = upload.json()["artifact"]["artifact_id"]
    response = env["client"].get(f"/api/artifacts/{artifact_id}/file")

    assert response.status_code == 400
    assert "safe image media" in response.json()["detail"]


def test_image_file_endpoint_rejects_source_trace_and_governance_paths(tmp_path, monkeypatch):
    env = _load_image_api_env(tmp_path, monkeypatch)

    source_trace_artifact = {
        "artifact_id": "trace-artifact",
        "path": "research/source-traces/example.moltbook-sources.json",
        "metadata": {
            "media_kind": "generated_image",
            "mime_type": "image/png",
        },
    }
    monkeypatch.setattr(env["routes_mod"], "get_artifact", lambda _artifact_id: source_trace_artifact)
    trace_response = env["client"].get("/api/artifacts/trace-artifact/file")
    assert trace_response.status_code == 403
    assert "source traces" in trace_response.json()["detail"].lower()

    governance_artifact = {
        "artifact_id": "governance-artifact",
        "path": "uploads/2026/05/25/soul.md",
        "metadata": {
            "media_kind": "generated_image",
            "mime_type": "image/png",
        },
    }
    monkeypatch.setattr(env["routes_mod"], "get_artifact", lambda _artifact_id: governance_artifact)
    governance_response = env["client"].get("/api/artifacts/governance-artifact/file")
    assert governance_response.status_code == 403
    assert "governance" in governance_response.json()["detail"]
