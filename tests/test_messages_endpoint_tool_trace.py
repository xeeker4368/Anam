"""Contract test: GET /api/conversations/{id}/messages must keep returning tool_trace.

The chat UI rebuilds a persisted message's artifact cards from the structured
tool_results[].selection entries stored inside tool_trace. If this endpoint ever
stops returning the column, generated-image cards silently vanish on reload with
no error raised anywhere — the exact failure this test exists to catch.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import tir.memory.db as db_mod
from tir.api.routes import app


GENERATED_IMAGE_TRACE = [
    {
        "iteration": 0,
        "tool_calls": [
            {"name": "image_generate", "arguments": {"prompt": "a heron at dusk"}}
        ],
        "tool_results": [
            {
                "tool_name": "image_generate",
                "ok": True,
                "rendered": "Generated an image.",
                "selection": {
                    "kind": "generated_image",
                    "tool_name": "image_generate",
                    "artifact_id": "artifact-123",
                    "preview_url": "/api/artifacts/artifact-123/preview",
                    "title": "Heron at Dusk",
                    "media_kind": "image",
                },
            }
        ],
    }
]


@pytest.fixture()
def temp_db(tmp_path):
    """Point the db layer at throwaway databases for the duration of a test.

    Patches db module globals rather than reloading the module, so the function
    references already bound into tir.api.routes resolve the temp paths too.
    """
    with patch.object(db_mod, "DATA_DIR", tmp_path), \
         patch.object(db_mod, "ARCHIVE_DB", tmp_path / "archive.db"), \
         patch.object(db_mod, "WORKING_DB", tmp_path / "working.db"):
        db_mod.init_databases()
        yield tmp_path


@pytest.fixture()
def client(temp_db):
    return TestClient(app)


def _seed_conversation(tool_trace):
    user = db_mod.create_user("Lyle", role="admin")
    conversation_id = db_mod.start_conversation(user["id"])
    db_mod.save_message(conversation_id, user["id"], "user", "make me a heron")
    db_mod.save_message(
        conversation_id,
        user["id"],
        "assistant",
        "Here it is.",
        tool_trace=tool_trace,
    )
    return conversation_id


def test_messages_endpoint_returns_tool_trace_verbatim(client):
    conversation_id = _seed_conversation(json.dumps(GENERATED_IMAGE_TRACE))

    response = client.get(f"/api/conversations/{conversation_id}/messages")
    assert response.status_code == 200

    messages = response.json()
    assistant_messages = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assistant = assistant_messages[0]

    assert "tool_trace" in assistant, (
        "The chat UI hydrates artifact cards from tool_trace; dropping the field "
        "from this response silently breaks persisted generated-image cards."
    )
    assert json.loads(assistant["tool_trace"]) == GENERATED_IMAGE_TRACE


def test_messages_endpoint_exposes_generated_image_selection(client):
    conversation_id = _seed_conversation(json.dumps(GENERATED_IMAGE_TRACE))

    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()
    assistant = next(m for m in messages if m["role"] == "assistant")

    selections = [
        result["selection"]
        for record in json.loads(assistant["tool_trace"])
        for result in record.get("tool_results", [])
        if "selection" in result
    ]

    assert [s["kind"] for s in selections] == ["generated_image"]
    assert selections[0]["artifact_id"] == "artifact-123"
    assert selections[0]["preview_url"] == "/api/artifacts/artifact-123/preview"
    assert selections[0]["title"] == "Heron at Dusk"


def test_messages_without_a_trace_still_carry_the_field(client):
    conversation_id = _seed_conversation(None)

    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()

    assert messages, "expected the seeded conversation to have messages"
    for message in messages:
        assert "tool_trace" in message
        assert message["tool_trace"] is None
