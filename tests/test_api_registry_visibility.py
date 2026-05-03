import importlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tir.api.routes import app
from tir.artifacts.service import create_artifact_file
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
            "workspace_root": workspace_root,
            "archive_db": tmp_path / "archive.db",
            "working_db": tmp_path / "working.db",
        }


@pytest.fixture()
def client(temp_stores):
    return TestClient(app)


def test_list_artifacts_returns_existing_metadata(client, temp_stores):
    first = create_artifact_file(
        relative_path="research/visible.md",
        content="Private workspace content",
        artifact_type="research_note",
        title="Visible Note",
        status="active",
        metadata={"topic": "visibility"},
        workspace_root=temp_stores["workspace_root"],
    )["artifact"]
    create_artifact_file(
        relative_path="drafts/hidden-by-filter.md",
        content="Other content",
        artifact_type="writing",
        title="Other Draft",
        status="draft",
        workspace_root=temp_stores["workspace_root"],
    )

    response = client.get(
        "/api/artifacts",
        params={"artifact_type": "research_note", "status": "active", "limit": 10},
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["artifact_id"] for item in data] == [first["artifact_id"]]
    assert data[0]["title"] == "Visible Note"
    assert data[0]["path"] == "research/visible.md"
    assert data[0]["metadata"] == {"topic": "visibility"}
    assert "content" not in data[0]
    assert "Private workspace content" not in str(data[0])


def test_get_artifact_returns_metadata_only(client, temp_stores):
    artifact = create_artifact_file(
        relative_path="research/get-me.md",
        content="Do not expose this file body",
        artifact_type="research_note",
        title="Fetch Me",
        workspace_root=temp_stores["workspace_root"],
    )["artifact"]

    response = client.get(f"/api/artifacts/{artifact['artifact_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["artifact_id"] == artifact["artifact_id"]
    assert data["path"] == "research/get-me.md"
    assert "content" not in data
    assert "Do not expose this file body" not in str(data)


def test_get_missing_artifact_returns_404(client):
    response = client.get("/api/artifacts/missing-artifact")

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"


def test_invalid_artifact_filter_returns_400(client):
    response = client.get("/api/artifacts", params={"artifact_type": "not-real"})

    assert response.status_code == 400
    assert "Invalid artifact_type" in response.json()["detail"]


def test_list_open_loops_returns_existing_metadata(client, temp_stores):
    artifact = create_artifact_file(
        relative_path="drafts/loop-target.md",
        content="Draft",
        artifact_type="writing",
        title="Loop Target",
        workspace_root=temp_stores["workspace_root"],
    )["artifact"]
    open_loop = create_open_loop(
        title="Continue draft",
        loop_type="unfinished_artifact",
        priority="high",
        related_artifact_id=artifact["artifact_id"],
        next_action="Revise conclusion",
        metadata={"reason": "unfinished"},
    )
    create_open_loop(
        title="Other loop",
        loop_type="generic",
        priority="normal",
    )

    response = client.get(
        "/api/open-loops",
        params={
            "status": "open",
            "loop_type": "unfinished_artifact",
            "priority": "high",
            "related_artifact_id": artifact["artifact_id"],
            "limit": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["open_loop_id"] for item in data] == [open_loop["open_loop_id"]]
    assert data[0]["related_artifact_id"] == artifact["artifact_id"]
    assert data[0]["next_action"] == "Revise conclusion"
    assert data[0]["metadata"] == {"reason": "unfinished"}


def test_get_open_loop_returns_one_record(client, temp_stores):
    artifact = create_artifact_file(
        relative_path="drafts/single-loop.md",
        content="Draft",
        artifact_type="writing",
        title="Single Loop Target",
        workspace_root=temp_stores["workspace_root"],
    )["artifact"]
    open_loop = create_open_loop(
        title="Single loop",
        loop_type="unfinished_artifact",
        related_artifact_id=artifact["artifact_id"],
    )

    response = client.get(f"/api/open-loops/{open_loop['open_loop_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["open_loop_id"] == open_loop["open_loop_id"]
    assert data["related_artifact_id"] == artifact["artifact_id"]


def test_get_missing_open_loop_returns_404(client):
    response = client.get("/api/open-loops/missing-loop")

    assert response.status_code == 404
    assert response.json()["detail"] == "Open loop not found"


def test_invalid_open_loop_filter_returns_400(client):
    response = client.get("/api/open-loops", params={"priority": "urgent"})

    assert response.status_code == 400
    assert "Invalid open-loop priority" in response.json()["detail"]
