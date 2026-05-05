import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


@dataclass
class FakeRegistry:
    skills: int = 2
    tools: tuple[str, ...] = ("memory_search", "web_search", "web_fetch")

    def __post_init__(self):
        self._skills = {f"skill_{index}": object() for index in range(self.skills)}

    def list_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{name} description",
                    "parameters": {},
                },
            }
            for name in self.tools
        ]


def _load_routes_with_temp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")

    import tir.memory.db as db_mod
    import tir.ops.status as status_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    importlib.reload(status_mod)
    importlib.reload(routes_mod)
    db_mod.init_databases()
    return db_mod, status_mod, routes_mod


def test_system_health_returns_ok_and_db_status(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    (tmp_path / "data" / "prod" / "chromadb").mkdir(parents=True)
    routes_mod.app.state.registry = FakeRegistry(
        skills=4,
        tools=("memory_search", "web_search", "web_fetch", "moltbook_me"),
    )

    with patch("tir.ops.status.get_collection_count", return_value=43):
        response = TestClient(routes_mod.app).get("/api/system/health")

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["api_ok"] is True
    assert data["project"] == "Project Anam"
    assert data["data_dir"] == {
        "exists": True,
        "name": "data/prod",
    }
    assert data["working_db"]["exists"] is True
    assert data["working_db"]["ok"] is True
    assert data["archive_db"]["exists"] is True
    assert data["archive_db"]["ok"] is True
    assert data["chroma"] == {
        "path_exists": True,
        "count": 43,
        "ok": True,
        "error": None,
    }
    assert data["skills"] == {
        "registry_loaded": True,
        "active_skill_count": 4,
        "active_tool_count": 4,
    }


def test_system_health_does_not_expose_moltbook_token_value(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("MOLTBOOK_TOKEN", "super-secret-token")
    routes_mod.app.state.registry = FakeRegistry()

    with patch("tir.ops.status.get_collection_count", return_value=0):
        response = TestClient(routes_mod.app).get("/api/system/health")

    text = response.text
    data = response.json()
    assert data["external"]["moltbook_token_configured"] is True
    assert "super-secret-token" not in text


def test_system_health_handles_chroma_count_failure_nonfatally(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    routes_mod.app.state.registry = FakeRegistry()

    with patch(
        "tir.ops.status.get_collection_count",
        side_effect=RuntimeError("chroma unavailable"),
    ):
        response = TestClient(routes_mod.app).get("/api/system/health")

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["chroma"]["ok"] is False
    assert data["chroma"]["count"] is None
    assert "chroma unavailable" in data["chroma"]["error"]


def test_system_health_handles_missing_registry_gracefully(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    if hasattr(routes_mod.app.state, "registry"):
        delattr(routes_mod.app.state, "registry")

    with patch("tir.ops.status.get_collection_count", return_value=0):
        response = TestClient(routes_mod.app).get("/api/system/health")

    data = response.json()
    assert response.status_code == 200
    assert data["skills"] == {
        "registry_loaded": False,
        "active_skill_count": 0,
        "active_tool_count": 0,
    }


def test_system_health_reports_latest_backup_manifest(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    backup_dir = tmp_path / "backups" / "2026-05-05T153012Z"
    backup_dir.mkdir(parents=True)
    (backup_dir / "manifest.json").write_text(
        json.dumps({"created_at": "2026-05-05T15:30:12+00:00"}),
        encoding="utf-8",
    )
    routes_mod.app.state.registry = FakeRegistry()

    with patch("tir.ops.status.get_collection_count", return_value=0):
        response = TestClient(routes_mod.app).get("/api/system/health")

    latest = response.json()["backups"]["latest_backup"]
    assert latest == {
        "name": "2026-05-05T153012Z",
        "has_manifest": True,
        "created_at": "2026-05-05T15:30:12+00:00",
    }


def test_system_memory_returns_audit_result_without_repair(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    routes_mod.app.state.registry = FakeRegistry()
    audit = {"message_id_parity_ok": True, "active_conversation_count": 0}

    with patch("tir.ops.status.audit_memory_integrity", return_value=audit) as mock_audit, \
         patch("tir.memory.audit.repair_memory_integrity") as mock_repair:
        response = TestClient(routes_mod.app).get("/api/system/memory")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "audit": audit,
    }
    mock_audit.assert_called_once_with()
    mock_repair.assert_not_called()


def test_system_memory_returns_structured_failure(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)

    with patch(
        "tir.ops.status.audit_memory_integrity",
        side_effect=RuntimeError("audit failed"),
    ):
        response = TestClient(routes_mod.app).get("/api/system/memory")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "error": "RuntimeError: audit failed",
    }


def test_system_capabilities_reports_available_and_disabled_features(
    tmp_path,
    monkeypatch,
):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("MOLTBOOK_TOKEN", "configured-token")
    routes_mod.app.state.registry = FakeRegistry(
        tools=("memory_search", "web_search", "web_fetch", "moltbook_me")
    )

    response = TestClient(routes_mod.app).get("/api/system/capabilities")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    capabilities = data["capabilities"]
    assert capabilities["memory_search"]["available"] is True
    assert capabilities["web_search"] == {
        "available": True,
        "configured": True,
        "source": "searxng",
    }
    assert capabilities["web_fetch"]["available"] is True
    assert capabilities["moltbook_read_only"] == {
        "available": True,
        "configured": True,
    }
    assert capabilities["backups"]["available"] is True
    assert capabilities["file_uploads"] == {
        "enabled": False,
        "status": "not_implemented",
    }
    assert capabilities["image_generation"]["status"] == "not_implemented"
    assert capabilities["autonomous_research"]["status"] == "not_implemented"
    assert capabilities["speech"]["status"] == "not_implemented"
    assert capabilities["vision"]["status"] == "not_implemented"
    assert capabilities["write_actions"]["enabled"] is False
    assert capabilities["self_modification"] == {
        "enabled": False,
        "status": "staged_only",
    }
    assert "configured-token" not in response.text


def test_existing_api_health_still_works(tmp_path, monkeypatch):
    _db_mod, _status_mod, routes_mod = _load_routes_with_temp_paths(tmp_path, monkeypatch)

    with patch("tir.api.routes.http_requests.get") as mock_get, \
         patch("tir.api.routes.get_collection_count", return_value=5):
        mock_get.return_value.status_code = 200
        response = TestClient(routes_mod.app).get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ollama"] == "ok"
    assert data["chromadb_chunks"] == 5
    assert data["conversations"] == 0
    assert data["messages"] == 0
