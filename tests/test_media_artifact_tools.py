import importlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from tir.artifacts.ingestion import ingest_artifact_file
from tir.workspace.service import ensure_workspace


@dataclass(frozen=True)
class FakeToolContext:
    user_id: str = "user-1"
    conversation_id: str = "conv-1"
    source_message_id: str = "msg-user-1"
    request_id: str = "req-1"


@pytest.fixture()
def media_tool_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", workspace_root)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_ALLOW_AGENT_TOOL", False)
    monkeypatch.setattr("tir.config.IMAGE_GENERATION_DEFAULT_BACKEND", "comfyui")

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod

    importlib.reload(db_mod)
    chroma_mod.reset_client()
    db_mod.init_databases()

    media_tools = importlib.import_module("skills.active.media_artifacts.media_artifacts")
    monkeypatch.setattr(media_tools.config_mod, "IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(media_tools.config_mod, "IMAGE_GENERATION_ALLOW_AGENT_TOOL", False)

    return {
        "db": db_mod,
        "media_tools": media_tools,
        "workspace_root": workspace_root,
        "working_db": tmp_path / "data" / "prod" / "working.db",
        "context": FakeToolContext(),
    }


def _artifact_count(working_db: Path) -> int:
    conn = sqlite3.connect(working_db)
    try:
        return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    finally:
        conn.close()


def _create_generated_image(env, *, title="Blue Particle Face", prompt="blue particle face"):
    with patch("tir.memory.artifact_indexing.upsert_chunk"):
        return ingest_artifact_file(
            filename="blue-particle.png",
            content=b"\x89PNG generated media bytes should never be returned",
            user_id=env["context"].user_id,
            title=title,
            artifact_type="generated_file",
            source="generation",
            source_conversation_id=env["context"].conversation_id,
            source_message_id=env["context"].source_message_id,
            source_tool_name="image_generate:comfyui",
            created_by="tool",
            metadata={
                "media_kind": "generated_image",
                "prompt": prompt,
                "generation_backend": "comfyui",
                "generation_model": "test-model",
                "workflow_name": "test-workflow",
                "observed_description": "blue points forming a face",
                "intended_use": "reference",
            },
            workspace_root=env["workspace_root"],
        )["artifact"]


def test_image_generate_returns_clear_disabled_when_agent_tool_not_allowed(media_tool_env):
    result = media_tool_env["media_tools"].image_generate(
        prompt="make a blue generated media artifact",
        _context=media_tool_env["context"],
    )

    assert result["ok"] is False
    assert result["generation_error"] is True
    assert result["error_type"] == "config_error"
    assert "not enabled for chat tools" in result["error"]
    assert result["artifact_created"] is False
    assert _artifact_count(media_tool_env["working_db"]) == 0


def test_image_generate_rejects_avatar_intended_use(media_tool_env, monkeypatch):
    monkeypatch.setattr(media_tool_env["media_tools"].config_mod, "IMAGE_GENERATION_ALLOW_AGENT_TOOL", True)

    result = media_tool_env["media_tools"].image_generate(
        prompt="ordinary generated media",
        intended_use="avatar_exploration",
        _context=media_tool_env["context"],
    )

    assert result["ok"] is False
    assert result["generation_error"] is True
    assert result["error_type"] == "invalid_request"
    assert "Invalid intended_use" in result["error"]
    assert _artifact_count(media_tool_env["working_db"]) == 0


def test_image_generate_success_returns_safe_artifact_metadata(media_tool_env, monkeypatch):
    monkeypatch.setattr(media_tool_env["media_tools"].config_mod, "IMAGE_GENERATION_ALLOW_AGENT_TOOL", True)

    def fake_generate_image(**kwargs):
        artifact = _create_generated_image(
            media_tool_env,
            title=kwargs["title"],
            prompt=kwargs["prompt"],
        )
        metadata = artifact["metadata"]
        metadata["negative_prompt"] = kwargs["negative_prompt"]
        metadata["seed"] = kwargs["seed"]
        metadata["width"] = kwargs["width"]
        metadata["height"] = kwargs["height"]
        metadata["source_artifact_id"] = kwargs["source_artifact_id"]
        return {
            "ok": True,
            "generation_error": False,
            "backend": kwargs["backend"] or "comfyui",
            "artifact_created": True,
            "artifact": artifact,
            "file": {"path": artifact["path"], "bytes": 42},
            "indexing": {"status": "metadata_only"},
        }

    monkeypatch.setattr(
        media_tool_env["media_tools"].image_generation_mod,
        "generate_image",
        fake_generate_image,
    )

    result = media_tool_env["media_tools"].image_generate(
        prompt="blue generated reference image",
        negative_prompt="no assigned identity",
        title="Blue Particle Face",
        width=512,
        height=512,
        seed=123,
        backend="comfyui",
        intended_use="reference",
        _context=media_tool_env["context"],
    )

    assert result["ok"] is True
    assert result["generation_error"] is False
    assert result["artifact_title"] == "Blue Particle Face"
    assert result["artifact_type"] == "generated_file"
    assert result["media_kind"] == "generated_image"
    assert result["artifact_path"].startswith("generated/")
    assert result["preview_url"] == f"/api/artifacts/{result['artifact_id']}/file"
    assert result["prompt"] == "blue generated reference image"
    assert result["negative_prompt"] == "no assigned identity"
    assert result["backend"] == "comfyui"
    assert result["width"] == 512
    assert result["height"] == 512
    assert result["seed"] == 123
    assert "generated media bytes" not in str(result)


def test_image_generate_failure_creates_no_artifact(media_tool_env, monkeypatch):
    monkeypatch.setattr(media_tool_env["media_tools"].config_mod, "IMAGE_GENERATION_ALLOW_AGENT_TOOL", True)

    def fake_generate_image(**_kwargs):
        return {
            "ok": False,
            "generation_error": True,
            "error_type": "backend_unavailable",
            "error": "ComfyUI is unavailable",
            "artifact_created": False,
        }

    monkeypatch.setattr(
        media_tool_env["media_tools"].image_generation_mod,
        "generate_image",
        fake_generate_image,
    )

    result = media_tool_env["media_tools"].image_generate(
        prompt="will fail",
        _context=media_tool_env["context"],
    )

    assert result["generation_error"] is True
    assert result["error_type"] == "backend_unavailable"
    assert result["artifact_created"] is False
    assert _artifact_count(media_tool_env["working_db"]) == 0


def test_image_generate_supports_source_and_revision_references(media_tool_env, monkeypatch):
    source = _create_generated_image(
        media_tool_env,
        title="Reference Image",
        prompt="reference prompt",
    )
    monkeypatch.setattr(media_tool_env["media_tools"].config_mod, "IMAGE_GENERATION_ALLOW_AGENT_TOOL", True)
    captured = {}

    def fake_generate_image(**kwargs):
        captured.update(kwargs)
        artifact = _create_generated_image(
            media_tool_env,
            title="Reference Revision",
            prompt=kwargs["prompt"],
        )
        artifact["revision_of"] = kwargs["revision_of"]
        artifact["metadata"]["source_artifact_id"] = kwargs["source_artifact_id"]
        return {
            "ok": True,
            "generation_error": False,
            "backend": "comfyui",
            "artifact_created": True,
            "artifact": artifact,
            "file": {"path": artifact["path"], "bytes": 42},
            "indexing": {"status": "metadata_only"},
        }

    monkeypatch.setattr(
        media_tool_env["media_tools"].image_generation_mod,
        "generate_image",
        fake_generate_image,
    )

    result = media_tool_env["media_tools"].image_generate(
        prompt="make another version",
        title="Reference Revision",
        source_artifact_id=source["artifact_id"],
        revision_of=source["artifact_id"],
        _context=media_tool_env["context"],
    )

    assert result["ok"] is True
    assert captured["source_artifact_id"] == source["artifact_id"]
    assert captured["revision_of"] == source["artifact_id"]
    assert result["source_artifact_id"] == source["artifact_id"]
    assert result["revision_of"] == source["artifact_id"]


def test_media_search_finds_generated_image_by_title_and_prompt(media_tool_env):
    artifact = _create_generated_image(
        media_tool_env,
        title="Blue Particle Face",
        prompt="simple blue holographic particle face",
    )

    by_title = media_tool_env["media_tools"].media_search(
        query="Blue Particle",
        _context=media_tool_env["context"],
    )
    by_prompt = media_tool_env["media_tools"].media_search(
        query="holographic",
        media_kind="generated_image",
        _context=media_tool_env["context"],
    )

    assert by_title["ok"] is True
    assert by_title["results"][0]["artifact_id"] == artifact["artifact_id"]
    assert by_title["results"][0]["preview_url"] == f"/api/artifacts/{artifact['artifact_id']}/file"
    assert by_prompt["ok"] is True
    assert by_prompt["results"][0]["prompt"] == "simple blue holographic particle face"
    assert "generated media bytes" not in str(by_prompt)


def test_media_get_returns_safe_metadata_and_preview_url(media_tool_env):
    artifact = _create_generated_image(media_tool_env)

    result = media_tool_env["media_tools"].media_get(
        artifact_id=artifact["artifact_id"],
        _context=media_tool_env["context"],
    )

    assert result["ok"] is True
    item = result["artifact"]
    assert item["artifact_id"] == artifact["artifact_id"]
    assert item["title"] == "Blue Particle Face"
    assert item["media_kind"] == "generated_image"
    assert item["preview_url"] == f"/api/artifacts/{artifact['artifact_id']}/file"
    assert "generated media bytes" not in str(result)


def test_media_get_rejects_missing_unsafe_source_trace_and_governance(media_tool_env, monkeypatch):
    missing = media_tool_env["media_tools"].media_get(
        artifact_id="missing-artifact",
        _context=media_tool_env["context"],
    )
    assert missing["ok"] is False
    assert missing["error_type"] == "not_found"

    import tir.artifacts.search as search_mod

    monkeypatch.setattr(
        search_mod,
        "get_artifact",
        lambda _artifact_id: {
            "artifact_id": "trace-artifact",
            "path": "research/source-traces/example.moltbook-sources.json",
            "metadata": {"media_kind": "generated_image", "mime_type": "image/png"},
        },
    )
    trace = search_mod.get_media_artifact_reference("trace-artifact")
    assert trace["ok"] is False
    assert trace["error_type"] == "blocked_source_trace"

    monkeypatch.setattr(
        search_mod,
        "get_artifact",
        lambda _artifact_id: {
            "artifact_id": "governance-artifact",
            "path": "soul.md",
            "metadata": {"media_kind": "generated_image", "mime_type": "image/png"},
        },
    )
    governance = search_mod.get_media_artifact_reference("governance-artifact")
    assert governance["ok"] is False
    assert governance["error_type"] == "blocked_governance_file"
