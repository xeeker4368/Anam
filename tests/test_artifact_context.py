import importlib

import pytest

from tir.workspace.service import ensure_workspace


@pytest.fixture()
def artifact_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    ensure_workspace(tmp_path / "workspace")

    import tir.memory.db as db_mod
    import tir.artifacts.service as service_mod
    import tir.engine.artifact_context as context_mod

    importlib.reload(db_mod)
    importlib.reload(service_mod)
    importlib.reload(context_mod)
    db_mod.init_databases()
    return {
        "db": db_mod,
        "service": service_mod,
        "context": context_mod,
        "workspace_root": tmp_path / "workspace",
    }


def _create_artifact(env, *, title, user_id=None, filename=None, metadata=None, created_at=None):
    merged_metadata = {
        "filename": filename or f"{title}.md",
        "safe_filename": filename or f"{title}.md",
        "origin": "user_upload",
        "source_role": "uploaded_source",
        "indexing_status": "indexed",
    }
    if user_id is not None:
        merged_metadata["user_id"] = user_id
    if metadata:
        merged_metadata.update(metadata)

    artifact = env["service"].create_artifact(
        artifact_type="uploaded_file",
        title=title,
        path=f"uploads/{filename or title}.md",
        status="active",
        source="upload",
        metadata=merged_metadata,
        workspace_root=env["workspace_root"],
    )
    if created_at:
        with env["db"].get_connection() as conn:
            conn.execute(
                "UPDATE main.artifacts SET created_at = ?, updated_at = ? WHERE artifact_id = ?",
                (created_at, created_at, artifact["artifact_id"]),
            )
            conn.commit()
        artifact = env["service"].get_artifact(artifact["artifact_id"])
    return artifact


@pytest.mark.parametrize(
    "text",
    [
        "I just uploaded two files, can you see them?",
        "Do you see the file?",
        "What did I upload?",
        "Show recent uploads",
        "Can you inspect this document?",
        "Is the artifact available?",
    ],
)
def test_recent_artifact_intent_detection(text, artifact_env):
    assert artifact_env["context"].has_recent_artifact_intent(text) is True


def test_recent_artifact_context_includes_latest_user_artifacts(artifact_env):
    _create_artifact(
        artifact_env,
        title="Older",
        user_id="user-1",
        filename="older.md",
        created_at="2026-05-06T10:00:00+00:00",
    )
    newest = _create_artifact(
        artifact_env,
        title="Newest",
        user_id="user-1",
        filename="newest.md",
        created_at="2026-05-06T12:00:00+00:00",
    )

    context, meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert meta["included"] is True
    assert meta["artifact_count"] == 2
    assert "Recent artifacts available as uploaded source material:" in context
    assert context.index("Newest") < context.index("Older")
    assert "file=newest.md" in context
    assert "type=uploaded_file" in context
    assert "role=Uploaded source" in context
    assert "origin=User upload" in context
    assert "indexing=indexed" in context
    assert "status=active" in context
    assert newest["artifact_id"][:8] in context


def test_recent_artifact_context_is_bounded_to_limit(artifact_env):
    for index in range(7):
        _create_artifact(
            artifact_env,
            title=f"Artifact {index}",
            user_id="user-1",
            filename=f"artifact-{index}.md",
            created_at=f"2026-05-06T12:0{index}:00+00:00",
        )

    context, meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert meta["artifact_count"] == 5
    assert context.count("- ") == 5


def test_recent_artifact_context_excludes_contents_raw_metadata_and_authority(artifact_env):
    _create_artifact(
        artifact_env,
        title="Sensitive Marker",
        user_id="user-1",
        filename="marker.md",
        metadata={
            "content": "FULL FILE CONTENT SHOULD NOT APPEAR",
            "raw": {"secret": "RAW SHOULD NOT APPEAR"},
            "metadata_json": "RAW METADATA SHOULD NOT APPEAR",
            "authority": "source_material",
            "sha256": "HASH SHOULD NOT APPEAR",
        },
    )

    context, _meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert "FULL FILE CONTENT SHOULD NOT APPEAR" not in context
    assert "RAW SHOULD NOT APPEAR" not in context
    assert "RAW METADATA SHOULD NOT APPEAR" not in context
    assert "HASH SHOULD NOT APPEAR" not in context
    assert "authority" not in context.lower()
    assert "source_material" not in context


def test_recent_artifact_context_excludes_other_user_artifacts(artifact_env):
    _create_artifact(
        artifact_env,
        title="Mine",
        user_id="user-1",
        filename="mine.md",
    )
    _create_artifact(
        artifact_env,
        title="Theirs",
        user_id="user-2",
        filename="theirs.md",
    )

    context, meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert meta["artifact_count"] == 1
    assert "Mine" in context
    assert "Theirs" not in context


def test_recent_artifact_context_includes_legacy_without_user_id(artifact_env):
    _create_artifact(
        artifact_env,
        title="Legacy",
        user_id=None,
        filename="legacy.md",
    )

    context, meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert meta["artifact_count"] == 1
    assert "Legacy" in context


def test_recent_artifact_context_char_budget_is_enforced(artifact_env):
    _create_artifact(
        artifact_env,
        title="T" * 5000,
        user_id="user-1",
        filename="large-title.md",
    )

    context, meta = artifact_env["context"].build_recent_artifacts_context(
        user_id="user-1",
        limit=5,
    )

    assert len(context) <= artifact_env["context"].RECENT_ARTIFACT_CONTEXT_CHAR_BUDGET
    assert meta["truncated"] is True
    assert meta["chars"] == len(context)
