import importlib
import logging
from unittest.mock import patch

import pytest


@pytest.fixture()
def temp_chunking(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"), \
         patch("tir.config.CHROMA_DIR", str(tmp_path / "chroma")):
        import tir.memory.db as db_mod
        import tir.memory.chroma as chroma_mod
        import tir.memory.chunking as chunking_mod

        importlib.reload(db_mod)
        importlib.reload(chroma_mod)
        importlib.reload(chunking_mod)
        db_mod.init_databases()
        chroma_mod.reset_client()
        yield db_mod, chunking_mod


def _make_ended_conversation(db_mod, user_name="Lyle", turns=6):
    user = db_mod.create_user(user_name)
    conversation_id = db_mod.start_conversation(user["id"])

    for i in range(turns):
        db_mod.save_message(conversation_id, user["id"], "user", f"Question {i}")
        db_mod.save_message(conversation_id, user["id"], "assistant", f"Answer {i}")

    db_mod.end_conversation(conversation_id)
    return user, conversation_id


def _make_active_conversation(db_mod, user_name="Lyle", turns=1):
    user = db_mod.create_user(user_name)
    conversation_id = db_mod.start_conversation(user["id"])

    for i in range(turns):
        db_mod.save_message(conversation_id, user["id"], "user", f"Question {i}")
        db_mod.save_message(conversation_id, user["id"], "assistant", f"Answer {i}")

    return user, conversation_id


def test_checkpoint_conversation_writes_active_tail_chunk(temp_chunking):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_active_conversation(db_mod, turns=1)

    with patch.object(chunking_mod, "_store_chunk") as mock_store_chunk:
        chunks_written = chunking_mod.checkpoint_conversation(
            conversation_id,
            user["id"],
        )

    assert chunks_written == 1
    assert mock_store_chunk.call_count == 1
    call = mock_store_chunk.call_args
    assert call.kwargs["chunk_id"] == f"{conversation_id}_chunk_0"
    assert call.kwargs["chunk_index"] == 0
    assert call.kwargs["message_count"] == 2
    assert "Question 0" in call.kwargs["text"]
    assert "Answer 0" in call.kwargs["text"]


def test_checkpoint_conversation_does_not_mark_active_conversation_chunked(
    temp_chunking,
):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_active_conversation(db_mod, turns=1)

    with patch.object(chunking_mod, "_store_chunk"):
        chunks_written = chunking_mod.checkpoint_conversation(
            conversation_id,
            user["id"],
        )

    assert chunks_written == 1
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


def test_checkpoint_conversation_overwrites_tail_chunk_without_duplicate_fts_rows(
    temp_chunking,
):
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_active_conversation(db_mod, turns=1)

    with patch.object(chunking_mod, "upsert_chunk"):
        assert chunking_mod.checkpoint_conversation(conversation_id, user["id"]) == 1
        db_mod.save_message(conversation_id, user["id"], "user", "Question 1")
        db_mod.save_message(conversation_id, user["id"], "assistant", "Answer 1")
        assert chunking_mod.checkpoint_conversation(conversation_id, user["id"]) == 1

    with db_mod.get_connection() as conn:
        rows = conn.execute(
            "SELECT chunk_id, text FROM main.chunks_fts WHERE chunk_id = ?",
            (f"{conversation_id}_chunk_0",),
        ).fetchall()

    assert len(rows) == 1
    assert "Question 0" in rows[0]["text"]
    assert "Question 1" in rows[0]["text"]
    assert "Answer 1" in rows[0]["text"]
    assert db_mod.get_conversation(conversation_id)["chunked"] == 0


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


# ---------------------------------------------------------------------------
# Option B: over-length sub-chunk splitting + degrade-don't-destroy (Defect 2)
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.01] * 768  # matches EXPECTED_EMBEDDING_DIM; avoids Ollama


def _make_ended_conversation_with_big_message(db_mod, *, fill_chars=12000):
    """One ended conversation whose first turn's assistant message alone blows
    past the embed budget (forces a sub-split)."""
    user = db_mod.create_user("Lyle")
    conversation_id = db_mod.start_conversation(user["id"])
    db_mod.save_message(conversation_id, user["id"], "user", "Tell me a long story")
    db_mod.save_message(conversation_id, user["id"], "assistant", "A" * fill_chars)
    db_mod.end_conversation(conversation_id)
    return user, conversation_id


def _fts_ids(db_mod, conversation_id):
    with db_mod.get_connection() as conn:
        rows = conn.execute(
            "SELECT chunk_id FROM main.chunks_fts WHERE conversation_id = ? ORDER BY chunk_id",
            (conversation_id,),
        ).fetchall()
    return [r["chunk_id"] for r in rows]


def _chroma_ids(chroma_mod, conversation_id):
    got = chroma_mod._get_collection().get(where={"conversation_id": conversation_id})
    return sorted(got["ids"])


def test_split_prefers_whole_message_boundaries_and_hard_splits_giant_message():
    # (a)/(e) unit-level: whole-message runs preferred; a single over-budget
    # message is hard-split in str space without losing or corrupting content.
    import tir.memory.chunking as chunking_mod

    messages = [
        {"role": "user", "content": "hi", "timestamp": "2026-06-28T12:00:00+00:00"},
        {"role": "assistant", "content": "ok", "timestamp": "2026-06-28T12:00:01+00:00"},
        {"role": "user", "content": "😀" * 400, "timestamp": "2026-06-28T12:00:02+00:00"},
    ]
    sub_units = chunking_mod._split_chunk_for_embedding(messages, "Lyle", budget=200)

    # All sub-units within budget.
    assert all(len(text) <= 200 for text, _ in sub_units)
    # The two small whole messages share one run; the giant message is hard-split.
    assert len(sub_units) >= 3
    # No multibyte corruption: no replacement chars introduced.
    assert all("�" not in text for text, _ in sub_units)
    # Lossless: the giant emoji line is reconstructed exactly from its pieces.
    giant_line = chunking_mod._format_message_line(messages[2], "Lyle")
    joined = "".join(text for text, _ in sub_units)
    assert giant_line in joined
    assert joined.count("😀") == 400
    # Message counts sum back to the group's message count.
    assert sum(count for _, count in sub_units) == 3


def test_over_budget_chunk_splits_and_all_sub_units_embed_and_store(temp_chunking):
    # (a): an over-budget chunk splits; every sub-unit embeds + stores in both
    # Chroma and FTS, each within budget.
    import tir.memory.chroma as chroma_mod
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation_with_big_message(db_mod)

    with patch.object(chroma_mod, "embed_text", return_value=list(_FAKE_EMBEDDING)):
        chunking_mod.chunk_conversation_final(conversation_id, user["id"])

    fts_ids = _fts_ids(db_mod, conversation_id)
    chroma_ids = _chroma_ids(chroma_mod, conversation_id)
    assert len(fts_ids) >= 2                      # split happened
    assert fts_ids == chroma_ids                  # both stores agree
    assert all("_chunk_0_" in cid for cid in fts_ids)  # suffixed sub-IDs
    with db_mod.get_connection() as conn:
        texts = conn.execute(
            "SELECT text FROM main.chunks_fts WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchall()
    assert all(len(r["text"]) <= 5000 for r in texts)


def test_split_conversation_reaches_chunked(temp_chunking):
    # (b): a conversation that required splitting still reaches chunked=1.
    import tir.memory.chroma as chroma_mod
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation_with_big_message(db_mod)

    with patch.object(chroma_mod, "embed_text", return_value=list(_FAKE_EMBEDDING)):
        chunking_mod.chunk_conversation_final(conversation_id, user["id"])

    assert db_mod.get_conversation(conversation_id)["chunked"] == 1
    assert db_mod.get_unchunked_ended_conversations() == []


def test_rechunk_of_split_conversation_is_idempotent(temp_chunking):
    # (c): re-running final chunking on frozen content reproduces the same stored
    # set — same sub-IDs, no duplicates, no orphans.
    import tir.memory.chroma as chroma_mod
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation_with_big_message(db_mod)

    with patch.object(chroma_mod, "embed_text", return_value=list(_FAKE_EMBEDDING)):
        chunking_mod.chunk_conversation_final(conversation_id, user["id"])
        fts_first = _fts_ids(db_mod, conversation_id)
        chroma_first = _chroma_ids(chroma_mod, conversation_id)
        chunking_mod.chunk_conversation_final(conversation_id, user["id"])
        fts_second = _fts_ids(db_mod, conversation_id)
        chroma_second = _chroma_ids(chroma_mod, conversation_id)

    assert fts_first == fts_second           # stable, no orphans/dupes in FTS
    assert chroma_first == chroma_second      # stable, no orphans/dupes in Chroma
    assert fts_second == chroma_second


def test_tail_growth_across_split_threshold_leaves_no_orphan(temp_chunking):
    # (c, live path): a tail that grows from fitting (bare _chunk_0) to splitting
    # (_chunk_0_0/_1) must not leave the bare id orphaned.
    import tir.memory.chroma as chroma_mod
    db_mod, chunking_mod = temp_chunking
    user = db_mod.create_user("Lyle")
    conversation_id = db_mod.start_conversation(user["id"])

    with patch.object(chroma_mod, "embed_text", return_value=list(_FAKE_EMBEDDING)):
        db_mod.save_message(conversation_id, user["id"], "user", "hi")
        db_mod.save_message(conversation_id, user["id"], "assistant", "short")
        chunking_mod.checkpoint_conversation(conversation_id, user["id"])
        assert _chroma_ids(chroma_mod, conversation_id) == [f"{conversation_id}_chunk_0"]
        # Grow the same tail group past the budget -> it must re-split cleanly.
        db_mod.save_message(conversation_id, user["id"], "user", "more")
        db_mod.save_message(conversation_id, user["id"], "assistant", "B" * 12000)
        chunking_mod.checkpoint_conversation(conversation_id, user["id"])

    ids = _chroma_ids(chroma_mod, conversation_id)
    assert f"{conversation_id}_chunk_0" not in ids        # bare id removed
    assert all("_chunk_0_" in cid for cid in ids)         # only suffixed sub-units
    assert _fts_ids(db_mod, conversation_id) == ids        # FTS converged too


def test_embed_failure_writes_fts_and_leaves_conversation_recoverable(temp_chunking):
    # (d): Defect 2 degrade path — vector write fails, FTS is still written, and
    # the conversation stays chunked=0 (recoverable), not dropped from both stores.
    db_mod, chunking_mod = temp_chunking
    user, conversation_id = _make_ended_conversation(db_mod, turns=2)

    # Patch the name `_store_chunk` actually calls (chunking's imported ref), so
    # the vector write fails while FTS still runs.
    with patch.object(chunking_mod, "upsert_chunk", side_effect=RuntimeError("vector down")):
        chunking_mod.chunk_conversation_final(conversation_id, user["id"])

    assert db_mod.get_conversation(conversation_id)["chunked"] == 0   # recoverable
    assert _fts_ids(db_mod, conversation_id)                          # FTS written
    assert [c["id"] for c in db_mod.get_unchunked_ended_conversations()] == [conversation_id]


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
