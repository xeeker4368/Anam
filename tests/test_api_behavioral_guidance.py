import importlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def behavioral_guidance_api_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")

    import tir.memory.db as db_mod
    import tir.behavioral_guidance.service as guidance_mod
    import tir.api.routes as routes_mod

    importlib.reload(db_mod)
    importlib.reload(guidance_mod)
    importlib.reload(routes_mod)
    db_mod.init_databases()
    return {
        "client": TestClient(routes_mod.app),
        "db": db_mod,
        "guidance": guidance_mod,
    }


def _proposal(guidance, *, proposal_type="addition", proposal_text="Atomic guidance."):
    kwargs = {
        "proposal_type": proposal_type,
        "proposal_text": proposal_text,
        "rationale": "The proposal is based on a reviewed interaction.",
        "source_channel": "chat",
    }
    if proposal_type in {"removal", "revision"}:
        kwargs["target_text"] = "Existing guidance."
    return guidance.create_behavioral_guidance_proposal(**kwargs)


def test_get_behavioral_guidance_proposals_returns_items(behavioral_guidance_api_env):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].get(
        "/api/behavioral-guidance/proposals"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert [row["proposal_id"] for row in data["proposals"]] == [proposal["proposal_id"]]


def test_get_behavioral_guidance_proposals_filters(
    behavioral_guidance_api_env,
):
    guidance = behavioral_guidance_api_env["guidance"]
    wanted = _proposal(guidance, proposal_type="revision", proposal_text="Revise one item.")
    other = _proposal(guidance, proposal_type="addition")
    guidance.update_behavioral_guidance_proposal_status(
        other["proposal_id"],
        "approved",
        reviewed_by_role="admin",
    )

    response = behavioral_guidance_api_env["client"].get(
        "/api/behavioral-guidance/proposals",
        params={
            "status": "proposed",
            "proposal_type": "revision",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert [row["proposal_id"] for row in data["proposals"]] == [wanted["proposal_id"]]


def test_get_behavioral_guidance_invalid_filter_returns_400(
    behavioral_guidance_api_env,
):
    response = behavioral_guidance_api_env["client"].get(
        "/api/behavioral-guidance/proposals",
        params={"proposal_type": "merge"},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "Invalid behavioral guidance proposal type" in response.json()["error"]


def test_patch_behavioral_guidance_approves_with_admin_role(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].patch(
        f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
        json={
            "status": "approved",
            "reviewed_by_user_id": "admin-user",
            "reviewed_by_role": "admin",
            "review_decision_reason": "Clear and atomic.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["proposal"]["status"] == "approved"
    assert data["proposal"]["reviewed_by_user_id"] == "admin-user"
    assert data["proposal"]["review_decision_reason"] == "Clear and atomic."


def test_patch_behavioral_guidance_rejects_with_reason(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].patch(
        f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
        json={
            "status": "rejected",
            "reviewed_by_role": "admin",
            "review_decision_reason": "Contains multiple distinct guidance changes.",
        },
    )

    assert response.status_code == 200
    assert response.json()["proposal"]["status"] == "rejected"


def test_patch_behavioral_guidance_reject_without_reason_returns_400(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].patch(
        f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
        json={
            "status": "rejected",
            "reviewed_by_role": "admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "review_decision_reason is required" in response.json()["error"]


def test_patch_behavioral_guidance_non_admin_returns_400(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].patch(
        f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
        json={
            "status": "approved",
            "reviewed_by_role": "user",
        },
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "reviewed_by_role=admin" in response.json()["error"]


def test_patch_behavioral_guidance_missing_proposal_returns_404(
    behavioral_guidance_api_env,
):
    response = behavioral_guidance_api_env["client"].patch(
        "/api/behavioral-guidance/proposals/missing",
        json={
            "status": "approved",
            "reviewed_by_role": "admin",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error": "Behavioral guidance proposal not found",
    }


def test_patch_behavioral_guidance_applied_returns_400(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    response = behavioral_guidance_api_env["client"].patch(
        f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
        json={
            "status": "applied",
            "reviewed_by_role": "admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "not exposed by this review API" in response.json()["error"]


def test_behavioral_guidance_api_does_not_mutate_guidance_or_prompt(
    behavioral_guidance_api_env,
):
    proposal = _proposal(behavioral_guidance_api_env["guidance"])

    with patch("tir.engine.context._load_operational_guidance") as mock_load_guidance:
        response = behavioral_guidance_api_env["client"].patch(
            f"/api/behavioral-guidance/proposals/{proposal['proposal_id']}",
            json={
                "status": "approved",
                "reviewed_by_role": "admin",
            },
        )

    assert response.status_code == 200
    mock_load_guidance.assert_not_called()
