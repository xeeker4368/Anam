"""Tests for idle-close: the get_idle_open_conversations query, the shared
close_conversation primitive, the in-process sweep janitor, and the config floor.
"""

import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _iso(minutes_from_now: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)).isoformat()


# ---------------------------------------------------------------------------
# get_idle_open_conversations — real temp DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_databases()
        yield db_mod
        importlib.reload(db_mod)  # restore real paths for later tests


def test_idle_query_returns_open_conv_before_cutoff(db):
    user = db.create_user("Lyle")
    conv = db.start_conversation(user["id"])
    db.save_message(conv, user["id"], "user", "hi")

    # cutoff in the future → the just-now conversation is "older than cutoff"
    assert any(r["id"] == conv for r in db.get_idle_open_conversations(_iso(1)))
    # cutoff in the past → not idle
    assert all(r["id"] != conv for r in db.get_idle_open_conversations(_iso(-1)))


def test_idle_query_excludes_id_and_ended(db):
    user = db.create_user("Lyle")
    a = db.start_conversation(user["id"]); db.save_message(a, user["id"], "user", "a")
    b = db.start_conversation(user["id"]); db.save_message(b, user["id"], "user", "b")

    ids = {r["id"] for r in db.get_idle_open_conversations(_iso(1), exclude_id=a)}
    assert a not in ids and b in ids

    db.end_conversation(b)
    assert b not in {r["id"] for r in db.get_idle_open_conversations(_iso(1))}


def test_idle_query_no_messages_falls_back_to_started_at(db):
    user = db.create_user("Lyle")
    conv = db.start_conversation(user["id"])  # no messages
    assert any(r["id"] == conv for r in db.get_idle_open_conversations(_iso(1)))


def test_idle_query_respects_limit(db):
    user = db.create_user("Lyle")
    for _ in range(4):
        c = db.start_conversation(user["id"])
        db.save_message(c, user["id"], "user", "x")
    assert len(db.get_idle_open_conversations(_iso(1), limit=2)) == 2


# ---------------------------------------------------------------------------
# close_conversation — shared primitive (mocked orchestration)
# ---------------------------------------------------------------------------

def test_close_conversation_ends_then_chunks():
    import tir.memory.chunking as ch
    with patch.object(ch, "get_conversation",
                      return_value={"id": "c1", "user_id": "u1", "ended_at": None}), \
         patch.object(ch, "end_conversation") as mock_end, \
         patch.object(ch, "chunk_conversation_final", return_value=3) as mock_chunk:
        assert ch.close_conversation("c1", "u1") == 3
    mock_end.assert_called_once_with("c1")
    mock_chunk.assert_called_once_with("c1", "u1")


def test_close_conversation_already_ended_is_noop():
    import tir.memory.chunking as ch
    with patch.object(ch, "get_conversation",
                      return_value={"id": "c1", "ended_at": "2026-01-01T00:00:00+00:00"}), \
         patch.object(ch, "end_conversation") as mock_end, \
         patch.object(ch, "chunk_conversation_final") as mock_chunk:
        assert ch.close_conversation("c1", "u1") == 0
    mock_end.assert_not_called()
    mock_chunk.assert_not_called()


def test_close_conversation_missing_is_noop():
    import tir.memory.chunking as ch
    with patch.object(ch, "get_conversation", return_value=None), \
         patch.object(ch, "end_conversation") as mock_end:
        assert ch.close_conversation("c1", "u1") == 0
    mock_end.assert_not_called()


def test_close_conversation_marks_ended_even_if_chunking_fails():
    import tir.memory.chunking as ch
    with patch.object(ch, "get_conversation",
                      return_value={"id": "c1", "user_id": "u1", "ended_at": None}), \
         patch.object(ch, "end_conversation") as mock_end, \
         patch.object(ch, "chunk_conversation_final", side_effect=RuntimeError("boom")):
        assert ch.close_conversation("c1", "u1") == 0
    mock_end.assert_called_once_with("c1")  # still closed


# ---------------------------------------------------------------------------
# _sweep_idle_conversations — janitor logic (mocked)
# ---------------------------------------------------------------------------

def test_sweep_skips_active_and_exclude_and_bounds():
    import tir.api.routes as routes
    routes._active_generations.clear()
    routes._active_generations.add("active1")
    routes._last_idle_sweep_monotonic = 0.0
    candidates = [
        {"id": "active1", "user_id": "u"},  # in-flight → must be skipped
        {"id": "idle1", "user_id": "u"},
        {"id": "idle2", "user_id": "u"},
    ]
    with patch.object(routes, "get_idle_open_conversations", return_value=candidates) as mock_q, \
         patch.object(routes, "close_conversation", return_value=1) as mock_close:
        routes._sweep_idle_conversations(exclude_id="current")

    # query is asked to exclude the caller's conv and is bounded
    _, kwargs = mock_q.call_args
    assert kwargs.get("exclude_id") == "current"
    assert kwargs.get("limit") == routes._MAX_CLOSES_PER_SWEEP
    # closes the idle ones, never the in-flight one
    closed = [call.args[0] for call in mock_close.call_args_list]
    assert closed == ["idle1", "idle2"]
    routes._active_generations.clear()


def test_sweep_is_throttled():
    import tir.api.routes as routes
    routes._active_generations.clear()
    routes._last_idle_sweep_monotonic = 0.0
    with patch.object(routes, "get_idle_open_conversations", return_value=[]) as mock_q:
        routes._sweep_idle_conversations(None)  # first runs (stamps)
        routes._sweep_idle_conversations(None)  # within throttle window → skipped
    assert mock_q.call_count == 1


# ---------------------------------------------------------------------------
# Config floor
# ---------------------------------------------------------------------------

def test_idle_close_minutes_floored_at_two(monkeypatch):
    import tir.config as cfg
    monkeypatch.setenv("ANAM_IDLE_CLOSE_MINUTES", "1")
    importlib.reload(cfg)
    assert cfg.IDLE_CLOSE_MINUTES == 2  # floored
    monkeypatch.setenv("ANAM_IDLE_CLOSE_MINUTES", "30")
    importlib.reload(cfg)
    assert cfg.IDLE_CLOSE_MINUTES == 30
    monkeypatch.delenv("ANAM_IDLE_CLOSE_MINUTES", raising=False)
    importlib.reload(cfg)  # restore default for later tests
