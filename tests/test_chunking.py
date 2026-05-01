import importlib
import logging
from unittest.mock import patch

import pytest


@pytest.fixture()
def temp_chunking(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod
        import tir.memory.chunking as chunking_mod

        importlib.reload(db_mod)
        importlib.reload(chunking_mod)
        db_mod.init_databases()
        yield db_mod, chunking_mod


def _make_ended_conversation(db_mod, user_name="Lyle", turns=6):
    user = db_mod.create_user(user_name)
    conversation_id = db_mod.start_conversation(user["id"])

    for i in range(turns):
        db_mod.save_message(conversation_id, user["id"], "user", f"Question {i}")
        db_mod.save_message(conversation_id, user["id"], "assistant", f"Answer {i}")

    db_mod.end_conversation(conversation_id)
    return user, conversation_id


def test_final_chunking_marks_chunked_when_all_chunks_succeed(temp_chunking):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=6)

    with patch.object(chunking_mod, "_store_chunk") as mock_store_chunk:
        chunks_written = chunking_mod.chunk_conversation_final(
            conversation_id,
            user["id"],
        )

    assert chunks_written == 2
    assert mock_store_chunk.call_count == 2
    assert db_mod.get_conversation(conversation_id)["chunked"] == 1
    assert db_mod.get_unchunked_ended_conversations() == []


def test_final_chunking_partial_failure_remains_recoverable(temp_chunking, caplog):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=6)

    with caplog.at_level(logging.ERROR, logger="tir.memory.chunking"):
        with patch.object(
            chunking_mod,
            "_store_chunk",
            side_effect=[None, RuntimeError("vector write failed")],
        ):
            chunks_written = chunking_mod.chunk_conversation_final(
                conversation_id,
                user["id"],
            )

    assert chunks_written == 1
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0
    assert [
        conv["id"] for conv in db_mod.get_unchunked_ended_conversations()
    ] == [conversation_id]
    assert "Failed to write chunk" in caplog.text
    assert "Final chunking incomplete" in caplog.text
    assert "vector write failed" in caplog.text


def test_final_chunking_all_fail_remains_recoverable(temp_chunking, caplog):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=6)

    with caplog.at_level(logging.ERROR, logger="tir.memory.chunking"):
        with patch.object(
            chunking_mod,
            "_store_chunk",
            side_effect=RuntimeError("all writes failed"),
        ):
            chunks_written = chunking_mod.chunk_conversation_final(
                conversation_id,
                user["id"],
            )

    assert chunks_written == 0
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0
    assert [
        conv["id"] for conv in db_mod.get_unchunked_ended_conversations()
    ] == [conversation_id]
    assert "Failed to write chunk" in caplog.text
    assert "Final chunking incomplete" in caplog.text


def test_recovery_helper_retries_and_marks_successful_conversations_chunked(temp_chunking):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=6)

    with patch.object(chunking_mod, "_store_chunk") as mock_store_chunk:
        summary = chunking_mod.recover_unchunked_ended_conversations()

    assert summary == {
        "attempted": 1,
        "succeeded": 1,
        "failed": 0,
        "chunks_written": 2,
        "failures": [],
    }
    assert mock_store_chunk.call_count == 2
    assert db_mod.get_conversation(conversation_id)["chunked"] == 1
    assert db_mod.get_unchunked_ended_conversations() == []
    assert user["id"]


def test_recovery_helper_reports_failures_and_leaves_conversation_discoverable(
    temp_chunking,
):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=6)

    with patch.object(
        chunking_mod,
        "_store_chunk",
        side_effect=RuntimeError("still failing"),
    ):
        summary = chunking_mod.recover_unchunked_ended_conversations()

    assert summary["attempted"] == 1
    assert summary["succeeded"] == 0
    assert summary["failed"] == 1
    assert summary["chunks_written"] == 0
    assert summary["failures"] == [{
        "conversation_id": conversation_id,
        "error": "conversation remained unchunked after retry",
    }]
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0
    assert [
        conv["id"] for conv in db_mod.get_unchunked_ended_conversations()
    ] == [conversation_id]
    assert user["id"]


def test_recovery_helper_honors_limit(temp_chunking):
    db_mod, chunking_mod = temp_chunking
    first_user, first_id = _make_ended_conversation(db_mod, user_name="Lyle", turns=6)
    second_user, second_id = _make_ended_conversation(db_mod, user_name="Mara", turns=6)

    with patch.object(chunking_mod, "_store_chunk") as mock_store_chunk:
        summary = chunking_mod.recover_unchunked_ended_conversations(limit=1)

    assert summary["attempted"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert summary["chunks_written"] == 2
    assert mock_store_chunk.call_count == 2
    assert db_mod.get_conversation(first_id)["chunked"] == 1
    assert db_mod.get_conversation(second_id)["chunked"] == 0
    assert [
        conv["id"] for conv in db_mod.get_unchunked_ended_conversations()
    ] == [second_id]
    assert first_user["id"]
    assert second_user["id"]
