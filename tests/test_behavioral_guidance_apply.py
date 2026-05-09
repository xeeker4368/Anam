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


def test_dry_run_does_not_modify_file_or_status(apply_env):
    apply_mod = apply_env["apply"]
    guidance = apply_env["guidance"]
    guidance_path = apply_env["guidance_path"]
    original = guidance_path.read_text(encoding="utf-8")

    plan = apply_mod.plan_behavioral_guidance_apply(
        apply_env["proposal"]["proposal_id"],
        guidance_path=guidance_path,
    )

    assert "Keep behavioral guidance narrow" in plan["append_block"]
    assert guidance_path.read_text(encoding="utf-8") == original
    proposal = guidance.get_behavioral_guidance_proposal(
        apply_env["proposal"]["proposal_id"]
    )
    assert proposal["status"] == "approved"


def test_approved_addition_produces_expected_append_block(apply_env):
    apply_mod = apply_env["apply"]

    block = apply_mod.build_guidance_append_block(
        apply_env["proposal"],
        applied_at="2026-05-08T12:00:00+00:00",
    )

    assert block.startswith(f"### Proposal {apply_env['proposal']['proposal_id']}")
    assert f"- Proposal ID: {apply_env['proposal']['proposal_id']}" in block
    assert "- Type: addition" in block
    assert "- Applied: 2026-05-08T12:00:00+00:00" in block
    assert "- Source: conversation conv-1, message msg-1" in block
    assert "- Guidance: Keep behavioral guidance narrow and evidence-linked." in block
    assert "- Rationale: The reviewed conversation showed broad guidance would overfit." in block


def test_write_mode_appends_block_and_marks_proposal_applied(apply_env):
    apply_mod = apply_env["apply"]
    guidance_path = apply_env["guidance_path"]

    result = apply_mod.apply_behavioral_guidance_proposal(
        apply_env["proposal"]["proposal_id"],
        applied_by_user_id=apply_env["user"]["id"],
        apply_note="Applied after review.",
        guidance_path=guidance_path,
    )

    content = guidance_path.read_text(encoding="utf-8")
    assert "Seed file." in content
    assert "## Active Guidance" in content
    assert f"### Proposal {apply_env['proposal']['proposal_id']}" in content
    assert result["proposal"]["status"] == "applied"
    assert result["proposal"]["applied_by_user_id"] == apply_env["user"]["id"]
    assert result["proposal"]["applied_at"] is not None
    assert result["proposal"]["apply_note"] == "Applied after review."


@pytest.mark.parametrize("status", ["proposed", "rejected", "archived"])
def test_non_approved_proposals_cannot_be_applied(apply_env, status):
    apply_mod = apply_env["apply"]
    guidance = apply_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text=f"{status} guidance.",
        rationale="Reason.",
    )
    if status != "proposed":
        proposal = guidance.update_behavioral_guidance_proposal_status(
            proposal["proposal_id"],
            status,
            reviewed_by_user_id=apply_env["user"]["id"],
            reviewed_by_role="admin",
            review_decision_reason="Rejected." if status == "rejected" else None,
        )

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError, match="approved"):
        apply_mod.plan_behavioral_guidance_apply(
            proposal["proposal_id"],
            guidance_path=apply_env["guidance_path"],
        )


def test_already_applied_proposal_cannot_be_applied_again(apply_env):
    apply_mod = apply_env["apply"]
    proposal_id = apply_env["proposal"]["proposal_id"]

    apply_mod.apply_behavioral_guidance_proposal(
        proposal_id,
        guidance_path=apply_env["guidance_path"],
    )

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError, match="already applied"):
        apply_mod.plan_behavioral_guidance_apply(
            proposal_id,
            guidance_path=apply_env["guidance_path"],
        )


@pytest.mark.parametrize("proposal_type", ["removal", "revision"])
def test_removal_and_revision_apply_are_rejected(apply_env, proposal_type):
    apply_mod = apply_env["apply"]
    guidance = apply_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type=proposal_type,
        proposal_text="Change an existing guidance item.",
        target_text="Existing guidance.",
        rationale="Reason.",
    )
    approved = guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "approved",
        reviewed_by_user_id=apply_env["user"]["id"],
        reviewed_by_role="admin",
    )

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError, match="addition"):
        apply_mod.plan_behavioral_guidance_apply(
            approved["proposal_id"],
            guidance_path=apply_env["guidance_path"],
        )


def test_duplicate_proposal_block_in_file_is_rejected(apply_env):
    apply_mod = apply_env["apply"]
    proposal_id = apply_env["proposal"]["proposal_id"]
    apply_env["guidance_path"].write_text(
        f"# BEHAVIORAL_GUIDANCE.md\n\n- Proposal ID: {proposal_id}\n",
        encoding="utf-8",
    )

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError, match="already contains"):
        apply_mod.plan_behavioral_guidance_apply(
            proposal_id,
            guidance_path=apply_env["guidance_path"],
        )


def test_missing_behavioral_guidance_file_fails_clearly(apply_env):
    apply_mod = apply_env["apply"]
    missing_path = apply_env["guidance_path"].parent / "missing.md"

    with pytest.raises(apply_mod.BehavioralGuidanceApplyError, match="not found"):
        apply_mod.plan_behavioral_guidance_apply(
            apply_env["proposal"]["proposal_id"],
            guidance_path=missing_path,
        )


def test_file_write_preserves_existing_seed_content(apply_env):
    apply_mod = apply_env["apply"]
    guidance_path = apply_env["guidance_path"]

    apply_mod.apply_behavioral_guidance_proposal(
        apply_env["proposal"]["proposal_id"],
        guidance_path=guidance_path,
    )

    content = guidance_path.read_text(encoding="utf-8")
    assert content.startswith("# BEHAVIORAL_GUIDANCE.md\n\nSeed file.")
