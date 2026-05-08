import importlib

import pytest


@pytest.fixture()
def behavioral_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "working.db")

    import tir.memory.db as db_mod
    import tir.behavioral_guidance.service as guidance_mod

    importlib.reload(db_mod)
    importlib.reload(guidance_mod)
    db_mod.init_databases()
    return {
        "db": db_mod,
        "guidance": guidance_mod,
    }


def test_create_addition_proposal_without_creator_fields(behavioral_env):
    guidance = behavioral_env["guidance"]

    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Prefer asking before making durable behavioral claims.",
        rationale="A conversation showed durable guidance needed review first.",
        source_channel="chat",
        source_user_id="user-1",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        metadata={"topic": "guidance"},
    )

    assert proposal["proposal_type"] == "addition"
    assert proposal["proposal_text"] == "Prefer asking before making durable behavioral claims."
    assert proposal["source_user_id"] == "user-1"
    assert proposal["source_channel"] == "chat"
    assert proposal["status"] == "proposed"
    assert proposal["metadata"] == {"topic": "guidance"}
    assert "created_by" not in proposal
    assert "proposal_created_by" not in proposal


@pytest.mark.parametrize("proposal_type", ["removal", "revision"])
def test_removal_and_revision_require_target(behavioral_env, proposal_type):
    guidance = behavioral_env["guidance"]

    with pytest.raises(guidance.BehavioralGuidanceValidationError):
        guidance.create_behavioral_guidance_proposal(
            proposal_type=proposal_type,
            proposal_text="Change one existing guidance item.",
            rationale="The target is required for this proposal type.",
        )


def test_revision_with_target_text_is_valid(behavioral_env):
    guidance = behavioral_env["guidance"]

    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="revision",
        proposal_text="Replace the old wording with a narrower instruction.",
        target_text="Old guidance wording.",
        rationale="The prior wording was too broad.",
    )

    assert proposal["proposal_type"] == "revision"
    assert proposal["target_text"] == "Old guidance wording."


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (
            {
                "proposal_type": "merge",
                "proposal_text": "Text",
                "rationale": "Reason",
            },
            "Invalid behavioral guidance proposal type",
        ),
        (
            {
                "proposal_type": "addition",
                "proposal_text": "",
                "rationale": "Reason",
            },
            "proposal_text is required",
        ),
        (
            {
                "proposal_type": "addition",
                "proposal_text": "Text",
                "rationale": "",
            },
            "rationale is required",
        ),
        (
            {
                "proposal_type": "addition",
                "proposal_text": "Text",
                "rationale": "Reason",
                "source_channel": "email",
            },
            "Invalid behavioral guidance source channel",
        ),
    ],
)
def test_create_validation_errors(behavioral_env, kwargs, expected):
    guidance = behavioral_env["guidance"]

    with pytest.raises(guidance.BehavioralGuidanceValidationError) as exc:
        guidance.create_behavioral_guidance_proposal(**kwargs)

    assert expected in str(exc.value)


def test_rejected_requires_decision_reason_and_admin_role(behavioral_env):
    guidance = behavioral_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )

    with pytest.raises(guidance.BehavioralGuidanceValidationError):
        guidance.update_behavioral_guidance_proposal_status(
            proposal["proposal_id"],
            "rejected",
            reviewed_by_role="admin",
        )

    with pytest.raises(guidance.BehavioralGuidanceValidationError):
        guidance.update_behavioral_guidance_proposal_status(
            proposal["proposal_id"],
            "rejected",
            reviewed_by_role="user",
            review_decision_reason="Rejected.",
        )

    rejected = guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "rejected",
        reviewed_by_user_id="admin-user",
        reviewed_by_role="admin",
        review_decision_reason="Contains multiple distinct guidance changes; split it.",
    )

    assert rejected["status"] == "rejected"
    assert rejected["reviewed_by_user_id"] == "admin-user"
    assert rejected["reviewed_by_role"] == "admin"
    assert rejected["review_decision_reason"].startswith("Contains multiple")
    assert rejected["reviewed_at"] is not None


def test_approved_accepts_optional_decision_reason(behavioral_env):
    guidance = behavioral_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )

    approved = guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "approved",
        reviewed_by_user_id="admin-user",
        reviewed_by_role="admin",
    )

    assert approved["status"] == "approved"
    assert approved["review_decision_reason"] is None
    assert approved["reviewed_at"] is not None


def test_applied_logs_application_fields(behavioral_env):
    guidance = behavioral_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )

    applied = guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "applied",
        reviewed_by_user_id="admin-user",
        reviewed_by_role="admin",
        applied_by_user_id="admin-user",
        apply_note="Applied manually.",
    )

    assert applied["status"] == "applied"
    assert applied["applied_by_user_id"] == "admin-user"
    assert applied["applied_at"] is not None
    assert applied["apply_note"] == "Applied manually."


def test_reopening_clears_review_and_application_fields(behavioral_env):
    guidance = behavioral_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )
    guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "applied",
        reviewed_by_user_id="admin-user",
        reviewed_by_role="admin",
        apply_note="Applied manually.",
    )

    reopened = guidance.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "proposed",
    )

    assert reopened["status"] == "proposed"
    assert reopened["reviewed_by_user_id"] is None
    assert reopened["reviewed_by_role"] is None
    assert reopened["review_decision_reason"] is None
    assert reopened["reviewed_at"] is None
    assert reopened["applied_by_user_id"] is None
    assert reopened["applied_at"] is None
    assert reopened["apply_note"] is None


def test_rejected_proposals_remain_visible_and_filterable(behavioral_env):
    guidance = behavioral_env["guidance"]
    first = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )
    guidance.create_behavioral_guidance_proposal(
        proposal_type="removal",
        proposal_text="Remove one guidance item.",
        target_text="Existing guidance.",
        rationale="Reason.",
    )
    guidance.update_behavioral_guidance_proposal_status(
        first["proposal_id"],
        "rejected",
        reviewed_by_role="admin",
        review_decision_reason="Not durable enough.",
    )

    rejected = guidance.list_behavioral_guidance_proposals(status="rejected")

    assert [proposal["proposal_id"] for proposal in rejected] == [first["proposal_id"]]


def test_invalid_status_rejected(behavioral_env):
    guidance = behavioral_env["guidance"]
    proposal = guidance.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )

    with pytest.raises(guidance.BehavioralGuidanceValidationError):
        guidance.update_behavioral_guidance_proposal_status(
            proposal["proposal_id"],
            "queued",
        )


def test_behavioral_guidance_table_is_working_db_only(behavioral_env):
    db_mod = behavioral_env["db"]

    with db_mod.get_connection() as conn:
        working_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM main.sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        archive_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM archive.sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "behavioral_guidance_proposals" in working_tables
    assert "behavioral_guidance_proposals" not in archive_tables
