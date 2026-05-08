import importlib

from fastapi.testclient import TestClient


def _auth_client(tmp_path, monkeypatch, *, secret: str | None):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    if secret is None:
        monkeypatch.delenv("ANAM_API_SECRET", raising=False)
    else:
        monkeypatch.setenv("ANAM_API_SECRET", secret)

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.api.auth as auth_mod
    import tir.api.routes as routes_mod

    importlib.reload(auth_mod)
    importlib.reload(db_mod)
    chroma_mod.reset_client()
    importlib.reload(routes_mod)
    db_mod.init_databases()
    db_mod.create_user("Lyle", role="admin")
    return TestClient(routes_mod.app)


def test_unset_api_secret_leaves_protected_routes_available(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret=None)

    response = client.get("/api/users")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Lyle"


def test_public_api_paths_work_without_secret_when_configured(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    health_response = client.get("/api/health")
    system_health_response = client.get("/api/system/health")
    capabilities_response = client.get("/api/system/capabilities")

    assert health_response.status_code == 200
    assert system_health_response.status_code == 200
    assert capabilities_response.status_code == 200


def test_system_memory_is_protected_when_secret_configured(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.get("/api/system/memory")

    assert response.status_code == 401
    assert response.json() == {"ok": False, "error": "unauthorized"}


def test_protected_api_route_requires_secret_when_configured(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.get("/api/users")

    assert response.status_code == 401
    assert response.json() == {"ok": False, "error": "unauthorized"}


def test_protected_api_route_rejects_wrong_secret(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.get("/api/users", headers={"x-anam-secret": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"ok": False, "error": "unauthorized"}


def test_protected_api_route_accepts_correct_secret(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.get("/api/users", headers={"x-anam-secret": "local-secret"})

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Lyle"


def test_options_request_is_not_blocked_by_api_secret(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.options("/api/users")

    assert response.status_code != 401


def test_non_api_route_is_not_blocked_by_api_secret(tmp_path, monkeypatch):
    client = _auth_client(tmp_path, monkeypatch, secret="local-secret")

    response = client.get("/not-api")

    assert response.status_code != 401
