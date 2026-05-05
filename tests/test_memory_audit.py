import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture()
def temp_memory_audit(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"), \
         patch("tir.config.CHROMA_DIR", str(tmp_path / "chromadb")):
        import tir.memory.db as db_mod
        import tir.memory.audit as audit_mod
        import tir.admin as admin_mod

        importlib.reload(db_mod)
        importlib.reload(audit_mod)
        importlib.reload(admin_mod)
        db_mod.init_databases()
        yield db_mod, audit_mod, admin_mod


def _make_conversation(db_mod, *, ended=False, turns=1):
    user = db_mod.create_user("Lyle")
    conversation_id = db_mod.start_conversation(user["id"])
    for index in range(turns):
        db_mod.save_message(conversation_id, user["id"], "user", f"Question {index}")
        db_mod.save_message(
            conversation_id,
            user["id"],
            "assistant",
            f"Answer {index}",
        )
    if ended:
        db_mod.end_conversation(conversation_id)
    return user, conversation_id


def _make_empty_active_conversation(db_mod):
    user = db_mod.create_user("Empty")
    conversation_id = db_mod.start_conversation(user["id"])
    return user, conversation_id


def test_audit_reports_working_archive_message_parity(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _make_conversation(db_mod, ended=False, turns=1)

    with patch("tir.memory.audit.get_collection_count", return_value=0):
        audit = audit_mod.audit_memory_integrity()

    assert audit["working_message_count"] == 2
    assert audit["archive_message_count"] == 2
    assert audit["message_id_parity_ok"] is True
    assert audit["missing_from_archive_count"] == 0
    assert audit["missing_from_working_count"] == 0


def test_audit_detects_missing_message_ids_bounded_by_limit(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    user = db_mod.create_user("Lyle")
    conversation_id = db_mod.start_conversation(user["id"])
    missing_archive = [
        db_mod.save_message(conversation_id, user["id"], "user", f"archive gap {i}")["id"]
        for i in range(3)
    ]
    missing_working = [
        db_mod.save_message(conversation_id, user["id"], "assistant", f"working gap {i}")["id"]
        for i in range(3)
    ]

    with db_mod.get_connection() as conn:
        conn.executemany(
            "DELETE FROM archive.messages WHERE id = ?",
            [(message_id,) for message_id in missing_archive],
        )
        conn.executemany(
            "DELETE FROM main.messages WHERE id = ?",
            [(message_id,) for message_id in missing_working],
        )
        conn.commit()

    with patch("tir.memory.audit.get_collection_count", return_value=0):
        audit = audit_mod.audit_memory_integrity(limit=2)

    assert audit["message_id_parity_ok"] is False
    assert audit["missing_from_archive_count"] == 3
    assert len(audit["missing_from_archive"]) == 2
    assert audit["missing_from_working_count"] == 3
    assert len(audit["missing_from_working"]) == 2


def test_audit_detects_ended_unchunked_and_reports_active_conversations(
    temp_memory_audit,
):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _active_user, active_id = _make_conversation(db_mod, ended=False, turns=1)
    _ended_user, ended_id = _make_conversation(db_mod, ended=True, turns=1)

    with patch("tir.memory.audit.get_collection_count", return_value=0):
        audit = audit_mod.audit_memory_integrity()

    assert audit["total_conversations"] == 2
    assert audit["active_conversation_count"] == 1
    assert audit["ended_conversation_count"] == 1
    assert audit["ended_unchunked_count"] == 1
    assert audit["ended_unchunked_ids"] == [ended_id]
    assert any("active conversation" in warning for warning in audit["warnings"])
    assert any("remain unchunked" in warning for warning in audit["warnings"])
    assert active_id not in audit["ended_unchunked_ids"]


def test_audit_reports_fts_chunk_count(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    user, conversation_id = _make_conversation(db_mod, ended=True, turns=1)
    db_mod.upsert_chunk_fts(
        chunk_id=f"{conversation_id}_chunk_0",
        text="chunk text",
        conversation_id=conversation_id,
        user_id=user["id"],
        source_type="conversation",
        source_trust="firsthand",
        created_at="2026-05-05T12:00:00+00:00",
    )

    with patch("tir.memory.audit.get_collection_count", return_value=1):
        audit = audit_mod.audit_memory_integrity()

    assert audit["fts_chunk_count"] == 1
    assert audit["chroma_chunk_count"] == 1
    assert audit["fts_chroma_count_match"] is True


def test_chroma_count_failure_is_non_fatal_and_adds_warning(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _make_conversation(db_mod, ended=False, turns=1)

    with patch(
        "tir.memory.audit.get_collection_count",
        side_effect=RuntimeError("chroma unavailable"),
    ):
        audit = audit_mod.audit_memory_integrity()

    assert audit["chroma_chunk_count"] is None
    assert audit["fts_chroma_count_match"] is None
    assert any("Chroma count unavailable" in warning for warning in audit["warnings"])


def test_repair_dry_run_does_not_call_recovery(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _user, conversation_id = _make_conversation(db_mod, ended=True, turns=1)

    with patch(
        "tir.memory.audit.chunking.recover_unchunked_ended_conversations"
    ) as mock_recover:
        summary = audit_mod.repair_memory_integrity(dry_run=True)

    mock_recover.assert_not_called()
    assert summary["dry_run"] is True
    assert summary["repairable_ended_unchunked_count"] == 1
    assert summary["would_attempt"] == 1
    assert summary["conversation_ids"] == [conversation_id]
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


def test_repair_non_dry_run_calls_recovery_with_limit(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _make_conversation(db_mod, ended=True, turns=1)

    with patch(
        "tir.memory.audit.chunking.recover_unchunked_ended_conversations",
        return_value={
            "attempted": 1,
            "succeeded": 1,
            "failed": 0,
            "chunks_written": 1,
            "failures": [],
        },
    ) as mock_recover:
        summary = audit_mod.repair_memory_integrity(limit=1)

    mock_recover.assert_called_once_with(limit=1)
    assert summary["dry_run"] is False
    assert summary["attempted"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["chunks_written"] == 1


def test_checkpoint_active_dry_run_reports_targets_without_mutation(
    temp_memory_audit,
):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _empty_user, empty_id = _make_empty_active_conversation(db_mod)
    _user, conversation_id = _make_conversation(db_mod, ended=False, turns=1)

    with patch(
        "tir.memory.audit.chunking.checkpoint_conversation"
    ) as mock_checkpoint:
        summary = audit_mod.checkpoint_active_conversations(dry_run=True)

    mock_checkpoint.assert_not_called()
    assert summary["dry_run"] is True
    assert summary["active_conversation_count"] == 2
    assert summary["checkpointable_active_count"] == 1
    assert summary["attempted"] == 0
    assert summary["conversation_ids"] == [conversation_id]
    assert empty_id not in summary["conversation_ids"]
    assert db_mod.get_conversation(conversation_id)["ended_at"] is None
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


def test_checkpoint_active_calls_checkpoint_for_active_conversations(
    temp_memory_audit,
):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    user, conversation_id = _make_conversation(db_mod, ended=False, turns=1)

    with patch(
        "tir.memory.audit.chunking.checkpoint_conversation",
        return_value=1,
    ) as mock_checkpoint:
        summary = audit_mod.checkpoint_active_conversations()

    mock_checkpoint.assert_called_once_with(conversation_id, user["id"])
    assert summary["dry_run"] is False
    assert summary["attempted"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["chunks_written"] == 1
    assert summary["conversation_ids"] == [conversation_id]
    assert db_mod.get_conversation(conversation_id)["ended_at"] is None
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


def test_checkpoint_active_limit_bounds_attempted_targets(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _first_user, _first_id = _make_conversation(db_mod, ended=False, turns=1)
    _second_user, _second_id = _make_conversation(db_mod, ended=False, turns=1)

    with patch(
        "tir.memory.audit.chunking.checkpoint_conversation",
        return_value=1,
    ) as mock_checkpoint:
        summary = audit_mod.checkpoint_active_conversations(limit=1)

    assert mock_checkpoint.call_count == 1
    assert summary["active_conversation_count"] == 2
    assert summary["checkpointable_active_count"] == 2
    assert summary["attempted"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert len(summary["conversation_ids"]) == 1


def test_checkpoint_active_reports_failure_and_continues(temp_memory_audit):
    db_mod, audit_mod, _admin_mod = temp_memory_audit
    _first_user, first_id = _make_conversation(db_mod, ended=False, turns=1)
    _second_user, second_id = _make_conversation(db_mod, ended=False, turns=1)

    with patch(
        "tir.memory.audit.chunking.checkpoint_conversation",
        side_effect=[RuntimeError("checkpoint failed"), 1],
    ):
        summary = audit_mod.checkpoint_active_conversations()

    assert summary["attempted"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["chunks_written"] == 1
    assert summary["failures"] == [{
        "conversation_id": summary["conversation_ids"][0],
        "error": "checkpoint failed",
    }]
    assert db_mod.get_conversation(first_id)["ended_at"] is None
    assert db_mod.get_conversation(second_id)["ended_at"] is None


def test_admin_memory_audit_command_runs_and_prints_summary(
    temp_memory_audit,
    capsys,
):
    db_mod, _audit_mod, admin_mod = temp_memory_audit
    _make_conversation(db_mod, ended=False, turns=1)

    with patch("tir.memory.audit.get_collection_count", return_value=0):
        admin_mod.cmd_memory_audit(SimpleNamespace(limit=25))

    output = capsys.readouterr().out
    assert "Memory audit" in output
    assert "Working messages: 2" in output
    assert "Message parity: ok" in output


def test_admin_memory_repair_dry_run_runs_and_does_not_mutate(
    temp_memory_audit,
    capsys,
):
    db_mod, _audit_mod, admin_mod = temp_memory_audit
    _user, conversation_id = _make_conversation(db_mod, ended=True, turns=1)

    admin_mod.cmd_memory_repair(SimpleNamespace(limit=None, dry_run=True))

    output = capsys.readouterr().out
    assert "Memory repair" in output
    assert "Dry run: True" in output
    assert "Would attempt: 1" in output
    assert conversation_id in output
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


def test_admin_memory_checkpoint_active_dry_run_prints_summary(
    temp_memory_audit,
    capsys,
):
    db_mod, _audit_mod, admin_mod = temp_memory_audit
    _user, conversation_id = _make_conversation(db_mod, ended=False, turns=1)

    admin_mod.cmd_memory_checkpoint_active(SimpleNamespace(limit=None, dry_run=True))

    output = capsys.readouterr().out
    assert "Active conversation checkpoint" in output
    assert "Dry run: True" in output
    assert "Checkpointable active conversations: 1" in output
    assert "Would attempt: 1" in output
    assert conversation_id in output
    assert db_mod.get_conversation(conversation_id)["ended_at"] is None
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0
