import importlib
import sqlite3
from unittest.mock import patch

import pytest

from tir.media.backends.base import (
    ImageGenerationBackendError,
    ImageGenerationBackendRequest,
    ImageGenerationBackendResult,
)
from tir.workspace.service import ensure_workspace


class FakeBackend:
    backend_name = "comfyui"

    def __init__(self, result=None, error=None):
        self.result = result or ImageGenerationBackendResult(
            content=b"\x89PNG fake generated image bytes",
            filename="fake-output.png",
            metadata={"workflow_id": "backend-workflow"},
        )
        self.error = error
        self.requests = []
        self.validated = False

    def validate_config(self):
        self.validated = True

    def generate(self, request: ImageGenerationBackendRequest):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture()
def image_generation_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", workspace_root)

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.media.image_generation as image_mod

    importlib.reload(db_mod)
    chroma_mod.reset_client()
    db_mod.init_databases()

    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_MAX_PROMPT_CHARS", 2000)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_MAX_WIDTH", 2048)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_MAX_HEIGHT", 2048)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_DEFAULT_WIDTH", 512)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_DEFAULT_HEIGHT", 512)
    monkeypatch.setattr(image_mod, "IMAGE_GENERATION_DEFAULT_BACKEND", "comfyui")

    return {
        "db": db_mod,
        "image_mod": image_mod,
        "workspace_root": workspace_root,
        "working_db": tmp_path / "data" / "prod" / "working.db",
    }


def _artifact_count(working_db):
    conn = sqlite3.connect(working_db)
    try:
        return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    finally:
        conn.close()


def _fts_rows(working_db):
    conn = sqlite3.connect(working_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT chunk_id, text, source_type FROM chunks_fts ORDER BY chunk_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def test_image_generation_dry_run_validates_and_writes_nothing(image_generation_env):
    backend = FakeBackend()
    result = image_generation_env["image_mod"].generate_image(
        prompt="A quiet generated artifact test",
        backend="comfyui",
        dry_run=True,
        width=512,
        height=512,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["artifact_created"] is False
    assert backend.validated is True
    assert backend.requests == []
    assert _artifact_count(image_generation_env["working_db"]) == 0
    assert not any(path.is_file() for path in image_generation_env["workspace_root"].rglob("*"))


def test_disabled_image_generation_rejects_without_artifact(image_generation_env, monkeypatch):
    monkeypatch.setattr(image_generation_env["image_mod"], "IMAGE_GENERATION_ENABLED", False)

    result = image_generation_env["image_mod"].generate_image(
        prompt="disabled generation",
        backend="comfyui",
        dry_run=True,
        backend_factory=lambda _name: FakeBackend(),
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "config_error"
    assert "disabled" in result["error"]
    assert _artifact_count(image_generation_env["working_db"]) == 0


def test_backend_unavailable_returns_failure_without_artifact(image_generation_env):
    backend = FakeBackend(
        error=ImageGenerationBackendError(
            "offline",
            error_type="backend_unavailable",
            safe_url="http://127.0.0.1:8188/prompt",
        )
    )

    result = image_generation_env["image_mod"].generate_image(
        prompt="backend unavailable",
        backend="comfyui",
        write=True,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "backend_unavailable"
    assert result["url"] == "http://127.0.0.1:8188/prompt"
    assert _artifact_count(image_generation_env["working_db"]) == 0


def test_invalid_comfyui_workflow_path_returns_config_error(image_generation_env, monkeypatch, tmp_path):
    image_mod = image_generation_env["image_mod"]
    monkeypatch.setattr(image_mod, "COMFYUI_WORKFLOW_PATH", str(tmp_path / "missing.json"))

    result = image_mod.generate_image(
        prompt="invalid workflow",
        backend="comfyui",
        dry_run=True,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "config_error"
    assert "workflow_path" in result["error"]
    assert _artifact_count(image_generation_env["working_db"]) == 0


def test_successful_generation_registers_media_artifact_and_metadata(image_generation_env):
    captured = []

    def capture_upsert(chunk_id, text, metadata):
        captured.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})

    backend = FakeBackend()
    with patch("tir.memory.artifact_indexing.upsert_chunk", side_effect=capture_upsert):
        result = image_generation_env["image_mod"].generate_image(
            prompt="A source-linked generated image",
            negative_prompt="no identity assignment",
            backend="comfyui",
            write=True,
            width=768,
            height=512,
            seed=42,
            title="Generated Test Image",
            user_id="user-1",
            source_conversation_id="conv-1",
            source_message_id="msg-1",
            source_artifact_id="artifact-source",
            revision_of=None,
            intended_use="reference",
            generation_model="test-model",
            workflow_name="default-test-workflow",
            generation_params={"steps": 4},
            backend_factory=lambda _name: backend,
            workspace_root=image_generation_env["workspace_root"],
        )

    assert result["ok"] is True
    artifact = result["artifact"]
    metadata = artifact["metadata"]
    assert artifact["artifact_type"] == "generated_file"
    assert artifact["path"].startswith("generated/")
    assert metadata["media_kind"] == "generated_image"
    assert metadata["prompt"] == "A source-linked generated image"
    assert metadata["negative_prompt"] == "no identity assignment"
    assert metadata["generation_backend"] == "comfyui"
    assert metadata["generation_model"] == "test-model"
    assert metadata["workflow_name"] == "default-test-workflow"
    assert metadata["workflow_id"] == "backend-workflow"
    assert metadata["generation_params"] == {"steps": 4, "seed": 42, "width": 768, "height": 512}
    assert metadata["seed"] == 42
    assert metadata["width"] == 768
    assert metadata["height"] == 512
    assert metadata["source_user_id"] == "user-1"
    assert metadata["source_conversation_id"] == "conv-1"
    assert metadata["source_message_id"] == "msg-1"
    assert metadata["source_artifact_id"] == "artifact-source"
    assert metadata["intended_use"] == "reference"
    assert result["indexing"]["status"] == "metadata_only"
    assert result["indexing"]["content_chunks_written"] == 0

    rows = _fts_rows(image_generation_env["working_db"])
    assert len(rows) == 1
    assert "fake generated image bytes" not in rows[0]["text"]
    assert "Generation prompt (provenance metadata): A source-linked generated image" in rows[0]["text"]
    assert "Generation dimensions: 768x512" in rows[0]["text"]
    assert captured[0]["metadata"]["media_kind"] == "generated_image"


def test_backend_no_output_creates_no_artifact(image_generation_env):
    backend = FakeBackend(
        result=ImageGenerationBackendResult(
            content=b"",
            filename="empty.png",
            metadata={},
        )
    )

    result = image_generation_env["image_mod"].generate_image(
        prompt="empty output",
        backend="comfyui",
        write=True,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "no_output"
    assert _artifact_count(image_generation_env["working_db"]) == 0


def test_load_workflow_raises_on_unsubstituted_placeholder(tmp_path):
    from tir.media.backends import comfyui as comfyui_mod

    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        '{"3": {"inputs": {"text": "{{prompt}}", "extra": "{{unknown}}"}}}',
        encoding="utf-8",
    )
    request = ImageGenerationBackendRequest(
        prompt="a prompt",
        width=512,
        height=512,
        seed=7,
    )

    with pytest.raises(ImageGenerationBackendError) as excinfo:
        comfyui_mod._load_workflow(workflow_path, request)

    assert excinfo.value.error_type == "config_error"
    assert "{{unknown}}" in str(excinfo.value)


def test_load_workflow_substitutes_all_known_placeholders(tmp_path):
    from tir.media.backends import comfyui as comfyui_mod

    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        '{"3": {"inputs": {"text": "{{prompt}}", "width": "{{width}}", '
        '"height": "{{height}}", "seed": "{{seed}}", "neg": "{{negative_prompt}}"}}}',
        encoding="utf-8",
    )
    request = ImageGenerationBackendRequest(
        prompt="a prompt",
        negative_prompt="bad",
        width=640,
        height=480,
        seed=11,
    )

    rendered = comfyui_mod._load_workflow(workflow_path, request)

    inputs = rendered["3"]["inputs"]
    assert inputs["text"] == "a prompt"
    assert inputs["width"] == 640
    assert inputs["height"] == 480
    assert inputs["seed"] == 11
    assert inputs["neg"] == "bad"


def test_missing_dimensions_and_seed_resolve_to_concrete_integers(image_generation_env):
    backend = FakeBackend()

    result = image_generation_env["image_mod"].generate_image(
        prompt="conversational path with no dimensions",
        backend="comfyui",
        write=True,
        width=None,
        height=None,
        seed=None,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["ok"] is True
    assert len(backend.requests) == 1
    request = backend.requests[0]
    assert request.width == 512
    assert request.height == 512
    assert isinstance(request.seed, int)
    assert 0 <= request.seed <= 2**32 - 1

    metadata = result["artifact"]["metadata"]
    assert metadata["width"] == 512
    assert metadata["height"] == 512
    assert metadata["seed"] == request.seed
    assert metadata["generation_params"]["width"] == 512
    assert metadata["generation_params"]["height"] == 512
    assert metadata["generation_params"]["seed"] == request.seed


def test_explicit_dimensions_and_seed_are_preserved(image_generation_env):
    backend = FakeBackend()

    image_generation_env["image_mod"].generate_image(
        prompt="explicit overrides survive",
        backend="comfyui",
        write=True,
        width=1024,
        height=768,
        seed=99,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    request = backend.requests[0]
    assert request.width == 1024
    assert request.height == 768
    assert request.seed == 99


def test_backend_unsafe_output_filename_is_rejected(image_generation_env):
    backend = FakeBackend(
        result=ImageGenerationBackendResult(
            content=b"\x89PNG unsafe",
            filename="../unsafe.png",
            metadata={},
        )
    )

    result = image_generation_env["image_mod"].generate_image(
        prompt="unsafe output",
        backend="comfyui",
        write=True,
        backend_factory=lambda _name: backend,
        workspace_root=image_generation_env["workspace_root"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "tool_error"
    assert "unsafe" in result["error"]
    assert _artifact_count(image_generation_env["working_db"]) == 0
