"""Backend attribution integrity: a request must identify a known user.

These tests prove a missing/blank user_id is rejected by our explicit check in
_resolve_user (HTTP 422), never silently attributed to a default user. A `Lyle`
user is created in the reject tests so that any regression to the old
DEFAULT_USER fallback would mis-attribute to him and be caught.
"""

import importlib
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient


@dataclass
class FakeLoopResult:
    final_content: str | None
    tool_trace: list
    terminated_reason: str
    iterations: int
    error: str | None = None


class FakeRegistry:
    def has_tools(self):
        return False

    def list_tool_descriptions(self):
        return ""

    def list_tools(self):
        return []


def _load(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")

    import tir.memory.db as db_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    importlib.reload(routes_mod)
    db_mod.init_databases()
    return db_mod, routes_mod


def _counts(db_mod):
    with db_mod.get_connection() as conn:
        conversations = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return int(conversations), int(messages)


# ---------------------------------------------------------------------------
# Chat: reject missing / unknown user, never default
# ---------------------------------------------------------------------------

def test_chat_missing_user_id_rejected_not_attributed_to_default(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    db_mod.create_user("Lyle", role="admin")  # would be the silent default

    client = TestClient(routes_mod.app)
    response = client.post("/api/chat/stream", json={"text": "hi"})

    assert response.status_code == 422
    # Our explicit check, not pydantic's field-required error (which is a list).
    assert response.json()["detail"] == (
        "user_id is required; the request must identify a known user"
    )
    # Nothing attributed to Lyle (or anyone).
    assert _counts(db_mod) == (0, 0)


def test_chat_unknown_user_id_rejected(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    db_mod.create_user("Lyle", role="admin")

    client = TestClient(routes_mod.app)
    response = client.post("/api/chat/stream", json={"text": "hi", "user_id": "ghost"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    assert _counts(db_mod) == (0, 0)


def test_chat_valid_user_id_attributes_to_that_user(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    # Lyle exists first; a regression to the default would attribute to him.
    db_mod.create_user("Lyle", role="admin")
    renee = db_mod.create_user("Renee", role="user")

    routes_mod.app.state.registry = FakeRegistry()

    saved = []

    def fake_save_message(conversation_id, user_id, role, content, tool_trace=None):
        saved.append({"user_id": user_id, "role": role})
        return {
            "id": f"msg-{role}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": "2026-06-01T00:00:00+00:00",
        }

    started = []

    def fake_start_conversation(user_id):
        started.append(user_id)
        return "conv-1"

    monkeypatch.setattr(routes_mod, "save_message", fake_save_message)
    monkeypatch.setattr(routes_mod, "start_conversation", fake_start_conversation)
    monkeypatch.setattr(routes_mod, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(routes_mod, "update_user_last_seen", lambda *a, **k: None)
    monkeypatch.setattr(routes_mod, "checkpoint_conversation", lambda *a, **k: None)
    monkeypatch.setattr(
        routes_mod,
        "get_conversation_messages",
        lambda *a, **k: [
            {
                "id": "msg-user",
                "conversation_id": "conv-1",
                "role": "user",
                "content": "hi",
                "timestamp": "2026-06-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        routes_mod,
        "run_agent_loop",
        lambda *a, **k: iter(
            [
                {"type": "token", "content": "hello"},
                {
                    "type": "done",
                    "result": FakeLoopResult(
                        final_content="hello",
                        tool_trace=[],
                        terminated_reason="complete",
                        iterations=1,
                    ),
                },
            ]
        ),
    )

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/chat/stream", json={"text": "hi", "user_id": renee["id"]}
    )

    assert response.status_code == 200
    # Attribution flows from the resolved (real) user, not Lyle.
    assert started == [renee["id"]]
    assert saved and all(entry["user_id"] == renee["id"] for entry in saved)


# ---------------------------------------------------------------------------
# Upload + image generation: reject missing user before doing work
# ---------------------------------------------------------------------------

def test_upload_missing_user_id_rejected(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    db_mod.create_user("Lyle", role="admin")

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/artifacts/upload",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "user_id is required" in body["error"]


def test_image_generation_missing_user_id_rejected(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    db_mod.create_user("Lyle", role="admin")

    client = TestClient(routes_mod.app)
    response = client.post(
        "/api/image-generation/generate", json={"prompt": "a cat"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert "user_id is required" in body["error"]


# ---------------------------------------------------------------------------
# Case-insensitive name resolution for the login UI
# ---------------------------------------------------------------------------

def test_resolve_user_by_name_case_insensitive_and_404(tmp_path, monkeypatch):
    db_mod, routes_mod = _load(tmp_path, monkeypatch)
    renee = db_mod.create_user("Renee", role="user")

    client = TestClient(routes_mod.app)

    exact = client.get("/api/users/resolve", params={"name": "Renee"})
    assert exact.status_code == 200
    assert exact.json()["id"] == renee["id"]

    lowered = client.get("/api/users/resolve", params={"name": "renee"})
    assert lowered.status_code == 200
    assert lowered.json()["id"] == renee["id"]

    upper = client.get("/api/users/resolve", params={"name": "  RENEE  "})
    assert upper.status_code == 200
    assert upper.json()["id"] == renee["id"]

    missing = client.get("/api/users/resolve", params={"name": "ghost"})
    assert missing.status_code == 404

    blank = client.get("/api/users/resolve", params={"name": "   "})
    assert blank.status_code == 422
