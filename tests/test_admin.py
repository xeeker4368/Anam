import importlib
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest


class FakePasswordHasher:
    def hash(self, password):
        return f"hashed:{password}"


@pytest.fixture()
def temp_admin(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod
        import tir.admin as admin_mod

        importlib.reload(db_mod)
        importlib.reload(admin_mod)
        db_mod.init_databases()
        yield db_mod, admin_mod


def test_set_password_creates_web_channel_row_when_absent(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle")
    fake_argon2 = types.SimpleNamespace(PasswordHasher=FakePasswordHasher)

    with patch.dict("sys.modules", {"argon2": fake_argon2}), \
         patch("tir.admin.getpass.getpass", side_effect=["secret", "secret"]):
        admin_mod.cmd_set_password(SimpleNamespace(user="Lyle"))

    output = capsys.readouterr().out
    assert "Password set for Lyle (web channel)" in output

    with db_mod.get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.channel_identifiers
               WHERE channel = 'web' AND identifier = 'lyle'"""
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["user_id"] == user["id"]
    assert rows[0]["auth_material"] == "hashed:secret"
    assert rows[0]["verified"] == 1


def test_set_password_updates_existing_web_channel_without_duplicate(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle")
    existing = db_mod.add_channel_identifier(
        user_id=user["id"],
        channel="web",
        identifier="lyle",
        auth_material="old-hash",
        verified=False,
    )
    fake_argon2 = types.SimpleNamespace(PasswordHasher=FakePasswordHasher)

    with patch.dict("sys.modules", {"argon2": fake_argon2}), \
         patch("tir.admin.getpass.getpass", side_effect=["new-secret", "new-secret"]):
        admin_mod.cmd_set_password(SimpleNamespace(user="Lyle"))

    output = capsys.readouterr().out
    assert "Password set for Lyle (web channel)" in output

    with db_mod.get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.channel_identifiers
               WHERE channel = 'web' AND identifier = 'lyle'"""
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["id"] == existing["id"]
    assert rows[0]["auth_material"] == "hashed:new-secret"
    assert rows[0]["verified"] == 1


def test_behavioral_guidance_admin_commands(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")

    admin_mod.cmd_behavioral_guidance_proposal_add(
        SimpleNamespace(
            proposal_type="addition",
            proposal_text="Use one atomic guidance change per proposal.",
            target_existing_guidance_id=None,
            target_text=None,
            rationale="Atomic proposals make review decisions clearer.",
            source_experience_summary="A review identified mixed proposal scope.",
            source_user_id=user["id"],
            source_conversation_id="conv-1",
            source_message_id="msg-1",
            source_channel="chat",
            risk_if_added="May be too strict.",
            risk_if_not_added="Mixed proposals become harder to review.",
            metadata_json='{"scope": "behavioral_guidance"}',
        )
    )

    output = capsys.readouterr().out
    assert "Behavioral guidance proposal recorded" in output
    assert "status=proposed" in output
    proposal_id = output.strip().splitlines()[1].split()[0]

    admin_mod.cmd_behavioral_guidance_proposal_list(
        SimpleNamespace(status="proposed", proposal_type=None, limit=50)
    )
    output = capsys.readouterr().out
    assert proposal_id in output
    assert "type=addition" in output

    admin_mod.cmd_behavioral_guidance_proposal_update(
        SimpleNamespace(
            proposal_id=proposal_id,
            status="approved",
            reviewed_by_user_id=user["id"],
            reviewed_by_role="admin",
            review_decision_reason="Clear and atomic.",
            applied_by_user_id=None,
            apply_note=None,
        )
    )

    output = capsys.readouterr().out
    assert "Behavioral guidance proposal updated" in output
    assert "status=approved" in output


def test_reflection_journal_day_admin_dry_run(temp_admin, capsys, monkeypatch):
    _db_mod, admin_mod = temp_admin

    def fake_run(**kwargs):
        assert kwargs["write"] is False
        assert kwargs["date_text"] == "2026-05-08"
        return {
            "mode": "dry-run",
            "status": "generated",
            "target_path": "journals/2026-05-08.md",
            "conversation_count": 1,
            "message_count": 2,
            "selection": {
                "selection_mode": "date",
                "local_date": "2026-05-08",
                "timezone": "EDT",
                "local_offset": "-04:00",
                "utc_start": "2026-05-08T04:00:00+00:00",
                "utc_end": "2026-05-09T04:00:00+00:00",
            },
            "journal": "# Reflection Journal — 2026-05-08\n",
        }

    monkeypatch.setattr(admin_mod, "run_reflection_journal_day", fake_run)

    admin_mod.cmd_reflection_journal_day(
        SimpleNamespace(
            date="2026-05-08",
            since=None,
            write=False,
            register_artifact=False,
            max_conversations=10,
            model=None,
        )
    )

    output = capsys.readouterr().out
    assert "Reflection journal complete" in output
    assert "mode=dry-run" in output
    assert "target_path=journals/2026-05-08.md" in output
    assert "# Reflection Journal — 2026-05-08" in output


def test_reflection_journal_day_admin_write_summary(temp_admin, capsys, monkeypatch):
    _db_mod, admin_mod = temp_admin

    def fake_run(**kwargs):
        assert kwargs["write"] is True
        return {
            "mode": "write",
            "status": "generated",
            "target_path": "journals/2026-05-08.md",
            "conversation_count": 1,
            "message_count": 2,
            "selection": {
                "selection_mode": "since",
                "since": "2026-05-08T12:00:00Z",
                "utc_start": "2026-05-08T12:00:00+00:00",
            },
            "write_result": {
                "path": "journals/2026-05-08.md",
                "bytes": 123,
            },
            "journal": "# Reflection Journal — 2026-05-08\n",
        }

    monkeypatch.setattr(admin_mod, "run_reflection_journal_day", fake_run)

    admin_mod.cmd_reflection_journal_day(
        SimpleNamespace(
            date=None,
            since="2026-05-08T12:00:00Z",
            write=True,
            register_artifact=False,
            max_conversations=10,
            model=None,
        )
    )

    output = capsys.readouterr().out
    assert "mode=write" in output
    assert "since=2026-05-08T12:00:00Z" in output
    assert "written_path=journals/2026-05-08.md" in output
    assert "written_bytes=123" in output


def test_reflection_journal_day_admin_register_summary(temp_admin, capsys, monkeypatch):
    _db_mod, admin_mod = temp_admin

    def fake_run(**kwargs):
        assert kwargs["write"] is True
        assert kwargs["register_artifact"] is True
        return {
            "mode": "write",
            "status": "generated",
            "target_path": "journals/2026-05-08.md",
            "conversation_count": 1,
            "message_count": 2,
            "selection": {},
            "write_result": {
                "path": "journals/2026-05-08.md",
                "bytes": 123,
            },
            "artifact_result": {
                "artifact": {
                    "artifact_id": "artifact-1",
                    "path": "journals/2026-05-08.md",
                },
                "indexing": {
                    "status": "indexed",
                    "chunks_written": 2,
                },
            },
            "journal": None,
        }

    monkeypatch.setattr(admin_mod, "run_reflection_journal_day", fake_run)

    admin_mod.cmd_reflection_journal_day(
        SimpleNamespace(
            date="2026-05-08",
            since=None,
            write=True,
            register_artifact=True,
            max_conversations=10,
            model=None,
        )
    )

    output = capsys.readouterr().out
    assert "artifact_id=artifact-1" in output
    assert "indexing_status=indexed" in output
    assert "indexing_chunks=2" in output


def test_reflection_journal_register_command_prints_summary(temp_admin, capsys, monkeypatch):
    _db_mod, admin_mod = temp_admin

    monkeypatch.setattr(
        admin_mod,
        "register_reflection_journal_artifact",
        lambda date: {
            "path": f"journals/{date}.md",
            "artifact": {"artifact_id": "artifact-1"},
            "indexing": {"status": "indexed", "chunks_written": 2},
        },
    )

    admin_mod.cmd_reflection_journal_register(SimpleNamespace(date="2026-05-08"))

    output = capsys.readouterr().out
    assert "Reflection journal registered" in output
    assert "journal_date=2026-05-08" in output
    assert "artifact_id=artifact-1" in output
    assert "indexing_chunks=2" in output


def test_behavioral_guidance_admin_reject_requires_reason(temp_admin):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    proposal = admin_mod.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Atomic guidance.",
        rationale="Reason.",
    )

    with pytest.raises(SystemExit):
        admin_mod.cmd_behavioral_guidance_proposal_update(
            SimpleNamespace(
                proposal_id=proposal["proposal_id"],
                status="rejected",
                reviewed_by_user_id=user["id"],
                reviewed_by_role="admin",
                review_decision_reason=None,
                applied_by_user_id=None,
                apply_note=None,
            )
        )


def test_behavioral_guidance_review_command_dry_run_prints_output(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    conversation_id = db_mod.start_conversation(user["id"])

    review = {
        "conversation_id": conversation_id,
        "source_user_id": user["id"],
        "message_count": 2,
        "model": "test-model",
        "proposals": [
            {
                "proposal_type": "addition",
                "proposal_text": "Use one atomic guidance change per proposal.",
                "rationale": "Atomic proposals are easier to review.",
                "source_channel": "chat",
                "source_conversation_id": conversation_id,
                "source_user_id": user["id"],
                "metadata": {"generation_method": "conversation_review_v1"},
            }
        ],
    }

    with patch.object(admin_mod, "generate_behavioral_guidance_review", return_value=review):
        admin_mod.cmd_behavioral_guidance_review_conversation(
            SimpleNamespace(
                conversation_id=conversation_id,
                dry_run=True,
                write=False,
                max_proposals=1,
                model=None,
            )
        )

    output = capsys.readouterr().out
    assert "Behavioral guidance conversation review complete" in output
    assert "mode=dry-run" in output
    assert "Use one atomic guidance change" in output

    assert admin_mod.list_behavioral_guidance_proposals() == []


def test_behavioral_guidance_review_command_write_prints_created_ids(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    conversation_id = db_mod.start_conversation(user["id"])

    review = {
        "conversation_id": conversation_id,
        "source_user_id": user["id"],
        "message_count": 2,
        "model": "test-model",
        "proposals": [
            {
                "proposal_type": "addition",
                "proposal_text": "Use one atomic guidance change per proposal.",
                "rationale": "Atomic proposals are easier to review.",
                "source_channel": "chat",
                "source_conversation_id": conversation_id,
                "source_user_id": user["id"],
                "metadata": {"generation_method": "conversation_review_v1"},
            }
        ],
    }

    with patch.object(admin_mod, "generate_behavioral_guidance_review", return_value=review):
        admin_mod.cmd_behavioral_guidance_review_conversation(
            SimpleNamespace(
                conversation_id=conversation_id,
                dry_run=False,
                write=True,
                max_proposals=1,
                model=None,
            )
        )

    output = capsys.readouterr().out
    assert "mode=write" in output
    assert "Created behavioral guidance proposal IDs" in output
    assert "status=proposed" in output

    proposals = admin_mod.list_behavioral_guidance_proposals()
    assert len(proposals) == 1
    assert proposals[0]["reviewed_by_user_id"] is None


def test_behavioral_guidance_review_day_command_prints_summary(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    conversation_id = db_mod.start_conversation(user["id"])
    review = {
        "mode": "dry-run",
        "selected_conversations": 1,
        "reviewed_conversations": 1,
        "skipped_conversations": 0,
        "failed_conversations": 0,
        "proposal_count": 1,
        "created_proposal_count": 0,
        "selection": {
            "selection_mode": "date",
            "local_date": "2026-05-08",
            "timezone": "EDT",
            "local_offset": "-04:00",
            "utc_start": "2026-05-08T04:00:00+00:00",
            "utc_end": "2026-05-09T04:00:00+00:00",
        },
        "results": [
            {
                "conversation_id": conversation_id,
                "status": "reviewed",
                "message_count": 3,
                "proposal_count": 1,
                "proposals": [
                    {
                        "proposal_type": "addition",
                        "proposal_text": "Use one atomic guidance change per proposal.",
                        "rationale": "Atomic proposals are easier to review.",
                    }
                ],
                "created_proposal_ids": [],
            }
        ],
    }

    with patch.object(admin_mod, "generate_behavioral_guidance_daily_review", return_value=review):
        admin_mod.cmd_behavioral_guidance_review_day(
            SimpleNamespace(
                date=None,
                since=None,
                conversation_id=[conversation_id],
                dry_run=True,
                write=False,
                max_conversations=10,
                max_proposals_per_conversation=1,
                max_total_proposals=5,
                model=None,
                allow_duplicates=False,
            )
        )

    output = capsys.readouterr().out
    assert "Behavioral guidance daily review complete" in output
    assert "mode=dry-run" in output
    assert "selected_conversations=1" in output
    assert "local_date=2026-05-08" in output
    assert "utc_start=2026-05-08T04:00:00+00:00" in output
    assert "utc_end=2026-05-09T04:00:00+00:00" in output
    assert conversation_id in output
    assert "Use one atomic guidance change" in output


def test_behavioral_guidance_apply_command_dry_run_prints_block(temp_admin, capsys, tmp_path):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    proposal = admin_mod.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Keep behavioral guidance narrow.",
        rationale="A reviewed conversation supported this.",
        source_conversation_id="conv-1",
        source_message_id="msg-1",
        source_channel="chat",
    )
    approved = admin_mod.update_behavioral_guidance_proposal_status(
        proposal["proposal_id"],
        "approved",
        reviewed_by_user_id=user["id"],
        reviewed_by_role="admin",
    )
    guidance_path = tmp_path / "BEHAVIORAL_GUIDANCE.md"
    guidance_path.write_text("# BEHAVIORAL_GUIDANCE.md\n", encoding="utf-8")

    with patch("tir.admin.plan_behavioral_guidance_apply") as mock_plan:
        mock_plan.return_value = {
            "guidance_path": str(guidance_path),
            "append_block": f"### Proposal {approved['proposal_id']}\n",
        }
        admin_mod.cmd_behavioral_guidance_proposal_apply(
            SimpleNamespace(
                proposal_id=approved["proposal_id"],
                dry_run=True,
                write=False,
                applied_by_user_id=None,
                apply_note=None,
            )
        )

    output = capsys.readouterr().out
    assert "Behavioral guidance proposal apply dry-run" in output
    assert approved["proposal_id"] in output
    assert "append_block:" in output


def test_behavioral_guidance_apply_command_write_prints_applied(temp_admin, capsys):
    db_mod, admin_mod = temp_admin
    user = db_mod.create_user("Lyle", role="admin")
    proposal = admin_mod.create_behavioral_guidance_proposal(
        proposal_type="addition",
        proposal_text="Keep behavioral guidance narrow.",
        rationale="A reviewed conversation supported this.",
    )
    applied = {
        **proposal,
        "status": "applied",
        "applied_by_user_id": user["id"],
        "applied_at": "2026-05-08T12:00:00+00:00",
        "apply_note": "Applied.",
    }

    with patch("tir.admin.apply_behavioral_guidance_proposal", return_value={
        "proposal": applied,
        "append_block": "block",
    }):
        admin_mod.cmd_behavioral_guidance_proposal_apply(
            SimpleNamespace(
                proposal_id=proposal["proposal_id"],
                dry_run=False,
                write=True,
                applied_by_user_id=user["id"],
                apply_note="Applied.",
            )
        )

    output = capsys.readouterr().out
    assert "Behavioral guidance proposal applied" in output
    assert "status=applied" in output
