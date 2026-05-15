import importlib

import pytest


@pytest.fixture()
def apply_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "working.db")
    monkeypatch.setattr("tir.config.PROJECT_ROOT", tmp_path)

    import tir.memory.db as db_mod
    import tir.behavioral_guidance.service as guidance_mod
    import tir.behavioral_guidance.apply as apply_mod

    importlib.reload(db_mod)
    importlib.reload(guidance_mod)
    importlib.reload(apply_mod)
    db_mod.init_databases()

    guidance_path = tmp_path / "BEHAVIORAL_GUIDANCE.md"
    guidance_path.write_text(
        "# BEHAVIORAL_GUIDANCE.md\n\nSeed file.\n",
        encoding="utf-8",
    )
    user = db_mod.create_user("Lyle", role="admin")
    proposal = guidance_mod.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Keep behavioral guidance narrow and evidence-linked.",
        rationale="The reviewed conversation showed broad guidance would overfit.",
        source_user_id=user["id"],
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_channel="chat",
    )
    approved = guidance_mod.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "approved",
        reviewed_by_user_id=user["id"],
        reviewed_by_role="admin",
        review_decision_reason="Clear and atomic.",
    )
    return {
        "db": db_mod,
        "guidance": guidance_mod,
        "apply": apply_mod,
        "guidance_path": guidance_path,
        "user": user,
        "proposal": approved,
    }


def test_dry_run_fails_dormant_and_does_not_modify_file_or_status(apply_env):
    apply_mod = apply_env["apply"]
    guidance = apply_env["guidance"]
    guidance_path = apply_env["guidance_path"]
    original = guidance_path.read_text(encoding="utf-8")

    with pytest.raises(
        apply_mod.BehavioralGuidanceApplyError,
        match="dormant before go-live",
    ):
        apply_mod.plan_behavioral_guidance_apply(
            apply_env["proposal"]["proposal_id"],
            guidance_path=guidance_path,
        )

    assert guidance_path.read_text(encoding="utf-8") == original
    proposal = guidance.get_behavioral_guidance_proposal(
        apply_env["proposal"]["proposal_id"]
    )
    assert proposal["status"] == "approved"


def test_write_mode_fails_dormant_and_does_not_modify_file_or_status(apply_env):
    apply_mod = apply_env["apply"]
    guidance = apply_env["guidance"]
    guidance_path = apply_env["guidance_path"]
    original = guidance_path.read_text(encoding="utf-8")

    with pytest.raises(
        apply_mod.BehavioralGuidanceApplyError,
        match="dormant before go-live",
    ):
        apply_mod.apply_behavioral_guidance_proposal(
            apply_env["proposal"]["proposal_id"],
            applied_by_user_id=apply_env["user"]["id"],
            apply_note="Applied after review.",
            guidance_path=guidance_path,
        )

    assert guidance_path.read_text(encoding="utf-8") == original
    proposal = guidance.get_behavioral_guidance_proposal(
        apply_env["proposal"]["proposal_id"]
    )
    assert proposal["status"] == "approved"
    assert proposal["applied_at"] is None
    assert proposal["applied_by_user_id"] is None
    assert proposal["apply_note"] is None


def test_dormant_error_message_is_clear(apply_env):
    apply_mod = apply_env["apply"]

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError) as excinfo:
        apply_mod.plan_behavioral_guidance_apply(
            apply_env["proposal"]["proposal_id"],
            guidance_path=apply_env["guidance_path"],
        )

    assert str(excinfo.value) == apply_mod.DORMANT_BEFORE_GO_LIVE_ERROR
