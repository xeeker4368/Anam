"""
Test the database layer.

Run from project root: python -m pytest tests/test_db.py -v
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

# Override paths before importing db
_test_dir = None

@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    """Use a temp directory for databases in every test."""
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        # Re-import to pick up patched paths
        import importlib
        import tir.memory.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_databases()
        yield db_mod


class TestSchemaCreation:
    def test_archive_has_two_tables(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import ARCHIVE_DB
        conn = sqlite3.connect(str(ARCHIVE_DB))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        assert "messages" in table_names
        assert "users" in table_names
        assert len(table_names) == 2

    def test_working_has_expected_tables(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import WORKING_DB
        conn = sqlite3.connect(str(WORKING_DB))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        table_names = [t[0] for t in tables]
        for expected in ["users", "channel_identifiers", "conversations",
                         "messages", "summaries", "documents",
                         "overnight_runs", "tasks", "artifacts",
                         "open_loops", "feedback_records"]:
            assert expected in table_names, f"Missing table: {expected}"

    def test_fts5_table_exists(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import WORKING_DB
        conn = sqlite3.connect(str(WORKING_DB))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1

    def test_both_use_delete_journaling(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import ARCHIVE_DB, WORKING_DB
        for db_path in [ARCHIVE_DB, WORKING_DB]:
            conn = sqlite3.connect(str(db_path))
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
            assert mode == "delete", f"{db_path} has journal_mode={mode}"


class TestUserManagement:
    def test_create_user(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle", role="admin")
        assert user["name"] == "Lyle"
        assert user["role"] == "admin"
        assert user["id"] is not None

    def test_user_in_both_databases(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import ARCHIVE_DB, WORKING_DB

        user = db.create_user("Lyle")

        # Check archive
        conn = sqlite3.connect(str(ARCHIVE_DB))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row is not None

        # Check working
        conn = sqlite3.connect(str(WORKING_DB))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        conn.close()
        assert row is not None

    def test_get_user_by_name(self, temp_data_dir):
        db = temp_data_dir
        db.create_user("Lyle")
        user = db.get_user_by_name("Lyle")
        assert user is not None
        assert user["name"] == "Lyle"

    def test_get_nonexistent_user(self, temp_data_dir):
        db = temp_data_dir
        assert db.get_user_by_name("Nobody") is None


class TestChannelIdentifiers:
    def test_add_and_resolve(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        db.add_channel_identifier(user["id"], "imessage", "+15551234567")

        resolved = db.resolve_user_by_channel("imessage", "+15551234567")
        assert resolved is not None
        assert resolved["name"] == "Lyle"

    def test_resolve_unknown_channel(self, temp_data_dir):
        db = temp_data_dir
        assert db.resolve_user_by_channel("imessage", "+10000000000") is None

    def test_unique_constraint(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        user = db.create_user("Lyle")
        db.add_channel_identifier(user["id"], "imessage", "+15551234567")
        with pytest.raises(sqlite3.IntegrityError):
            db.add_channel_identifier(user["id"], "imessage", "+15551234567")


class TestAtomicDualWrite:
    def test_message_in_both_databases(self, temp_data_dir):
        db = temp_data_dir
        import sqlite3
        from tir.config import ARCHIVE_DB, WORKING_DB

        user = db.create_user("Lyle")
        conv_id = db.start_conversation(user["id"])
        msg = db.save_message(conv_id, user["id"], "user", "Hello there")

        # Check archive
        conn = sqlite3.connect(str(ARCHIVE_DB))
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg["id"],)).fetchone()
        conn.close()
        assert row is not None

        # Check working
        conn = sqlite3.connect(str(WORKING_DB))
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg["id"],)).fetchone()
        conn.close()
        assert row is not None

    def test_message_count_increments(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        conv_id = db.start_conversation(user["id"])
        db.save_message(conv_id, user["id"], "user", "Hello")
        db.save_message(conv_id, user["id"], "assistant", "Hi there")

        conv = db.get_conversation(conv_id)
        assert conv["message_count"] == 2

    def test_tool_trace_persists(self, temp_data_dir):
        db = temp_data_dir
        import json

        user = db.create_user("Lyle")
        conv_id = db.start_conversation(user["id"])
        trace = json.dumps([{"tool": "web_search", "args": {"query": "test"}}])
        msg = db.save_message(conv_id, user["id"], "assistant", "I searched for that", tool_trace=trace)

        messages = db.get_conversation_messages(conv_id)
        assert messages[0]["tool_trace"] == trace


class TestConversations:
    def test_start_and_end(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        conv_id = db.start_conversation(user["id"])
        assert not db.is_conversation_ended(conv_id)

        db.end_conversation(conv_id)
        assert db.is_conversation_ended(conv_id)

    def test_active_conversations(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        c1 = db.start_conversation(user["id"])
        c2 = db.start_conversation(user["id"])
        db.end_conversation(c1)

        active = db.get_active_conversations(user["id"])
        assert len(active) == 1
        assert active[0]["id"] == c2

    def test_turn_count(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        conv_id = db.start_conversation(user["id"])
        db.save_message(conv_id, user["id"], "user", "Hello")
        db.save_message(conv_id, user["id"], "assistant", "Hi")
        db.save_message(conv_id, user["id"], "user", "How are you?")
        db.save_message(conv_id, user["id"], "assistant", "Good, thanks")

        assert db.get_turn_count(conv_id) == 2


class TestTasks:
    def test_add_and_get_pending(self, temp_data_dir):
        db = temp_data_dir
        user = db.create_user("Lyle")
        t1 = db.add_task("Research something", source="user", source_user_id=user["id"], priority=3)
        t2 = db.add_task("Write a poem", source="self", priority=7)

        pending = db.get_pending_tasks()
        assert len(pending) == 2
        # Lower priority number comes first
        assert pending[0]["description"] == "Research something"

    def test_task_status_updates(self, temp_data_dir):
        db = temp_data_dir
        tid = db.add_task("Test task")
        db.update_task_status(tid, "running")
        db.update_task_status(tid, "completed")

        pending = db.get_pending_tasks()
        assert len(pending) == 0


class TestFTS5:
    def test_upsert_and_search(self, temp_data_dir):
        db = temp_data_dir
        from datetime import datetime, timezone

        db.upsert_chunk_fts(
            chunk_id="test_chunk_1",
            text="Lyle and I discussed memory architecture for the Tír project",
            conversation_id="conv_1",
            user_id="user_1",
            source_type="conversation",
            source_trust="firsthand",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        results = db.search_bm25("memory architecture")
        assert len(results) > 0
        assert results[0]["chunk_id"] == "test_chunk_1"

    def test_exclude_conversation(self, temp_data_dir):
        db = temp_data_dir
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        db.upsert_chunk_fts("c1", "memory architecture discussion", "conv_1",
                            "u1", "conversation", "firsthand", now)
        db.upsert_chunk_fts("c2", "memory architecture design", "conv_2",
                            "u1", "conversation", "firsthand", now)

        results = db.search_bm25("memory architecture", exclude_conversation_id="conv_1")
        assert len(results) == 1
        assert results[0]["conversation_id"] == "conv_2"
