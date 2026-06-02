import importlib

import chromadb
import pytest

from tir.workspace.service import ensure_workspace


NOW = "2026-06-01T00:00:00Z"
PHRASE = "WIPE PRE-LIVE RUNTIME STATE"


@pytest.fixture()
def reset_env(tmp_path, monkeypatch):
    monkeypatch.setattr("tir.config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "data" / "prod" / "chromadb"))
    monkeypatch.setattr("tir.config.WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr("tir.config.BACKUP_DIR", tmp_path / "backups")

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.ops.backup as backup_mod
    import tir.ops.go_live_reset as reset_mod

    importlib.reload(db_mod)
    importlib.reload(chroma_mod)
    importlib.reload(backup_mod)
    importlib.reload(reset_mod)
    chroma_mod.reset_client()
    db_mod.init_databases()

    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    yield {
        "db": db_mod,
        "chroma": chroma_mod,
        "reset": reset_mod,
        "tmp_path": tmp_path,
        "workspace_root": workspace_root,
        "chroma_dir": str(tmp_path / "data" / "prod" / "chromadb"),
    }

    chroma_mod.reset_client()


def _seed_db(db_mod):
    with db_mod.get_connection() as conn:
        # Preserved identity / config rows.
        conn.execute(
            "INSERT INTO users (id, name, role, created_at, last_seen_at) "
            "VALUES ('u1', 'Lyle', 'user', ?, ?)",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO channel_identifiers (id, user_id, channel, identifier, created_at) "
            "VALUES ('ch1', 'u1', 'web', 'lyle', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO archive.users (id, name, created_at) VALUES ('u1', 'Lyle', ?)",
            (NOW,),
        )

        # Wiped experiment/memory/activity rows (FK-valid order).
        conn.execute(
            "INSERT INTO conversations (id, user_id, started_at) VALUES ('c1', 'u1', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) "
            "VALUES ('m1', 'c1', 'user', 'hello', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO summaries (id, conversation_id, content, created_at) "
            "VALUES ('sm1', 'c1', 'summary', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO documents (id, title, created_at) VALUES ('d1', 'doc', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO overnight_runs (id, started_at) VALUES ('o1', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO tasks (id, description, created_at) VALUES ('t1', 'task', ?)",
            (NOW,),
        )
        # Two artifacts including a self-referential revision_of to exercise
        # defer_foreign_keys during the wipe.
        conn.execute(
            "INSERT INTO artifacts (artifact_id, artifact_type, title, created_at, updated_at) "
            "VALUES ('a1', 'note', 'A1', ?, ?)",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO artifacts (artifact_id, artifact_type, title, created_at, updated_at, revision_of) "
            "VALUES ('a2', 'note', 'A2', ?, ?, 'a1')",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO open_loops (open_loop_id, title, created_at, updated_at, related_artifact_id) "
            "VALUES ('ol1', 'loop', ?, ?, 'a1')",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO feedback_records "
            "(feedback_id, feedback_type, title, user_feedback, created_at, updated_at, "
            "related_artifact_id, related_open_loop_id) "
            "VALUES ('fr1', 'bug', 'fb', 'text', ?, ?, 'a1', 'ol1')",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO diagnostic_issues "
            "(diagnostic_id, title, evidence_summary, created_at, updated_at, "
            "related_feedback_id, related_open_loop_id, related_artifact_id) "
            "VALUES ('di1', 'issue', 'ev', ?, ?, 'fr1', 'ol1', 'a1')",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO review_items (item_id, title, created_at, updated_at, source_artifact_id) "
            "VALUES ('ri1', 'review', ?, ?, 'a1')",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO behavioral_guidance_proposals "
            "(proposal_id, proposal_type, proposal_text, rationale, created_at, updated_at) "
            "VALUES ('bp1', 'add', 'text', 'why', ?, ?)",
            (NOW, NOW),
        )
        conn.execute(
            "INSERT INTO chunks_fts (chunk_id, text, conversation_id, user_id, source_type, source_trust, created_at) "
            "VALUES ('chunk1', 'hello world', 'c1', 'u1', 'conversation', 'firsthand', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO archive.messages (id, conversation_id, user_id, role, content, timestamp) "
            "VALUES ('m1', 'c1', 'u1', 'user', 'hello', ?)",
            (NOW,),
        )
        conn.commit()


def _seed_chroma(chroma_dir):
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name="tir_memory", metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=["chunk1"],
        embeddings=[[0.1] * 768],
        documents=["hello world"],
        metadatas=[{"conversation_id": "c1"}],
    )


def _seed_workspace(workspace_root):
    (workspace_root / "research" / "r1.md").write_text("research", encoding="utf-8")
    (workspace_root / "research" / "sub").mkdir(parents=True, exist_ok=True)
    (workspace_root / "research" / "sub" / "inner.md").write_text("nested", encoding="utf-8")
    (workspace_root / "research" / "source-traces").mkdir(parents=True, exist_ok=True)
    (workspace_root / "research" / "source-traces" / "s1.json").write_text("{}", encoding="utf-8")
    (workspace_root / "journals" / "j1.md").write_text("journal", encoding="utf-8")
    (workspace_root / "uploads" / "u1.bin").write_text("upload", encoding="utf-8")
    (workspace_root / "generated" / "g1.txt").write_text("gen", encoding="utf-8")
    # A non-wiped workspace dir that must survive.
    (workspace_root / "writing" / "keep.md").write_text("keep me", encoding="utf-8")


def _seed_all(env):
    _seed_db(env["db"])
    _seed_chroma(env["chroma_dir"])
    _seed_workspace(env["workspace_root"])


def _table_count(db_mod, qualified):
    with db_mod.get_connection() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0])


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_reports_targets_without_mutation(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]

    summary = reset.plan_go_live_reset()

    assert summary["mode"] == "dry-run"
    wipe = summary["would_wipe"]
    assert wipe["working_db"]["conversations"] == 1
    assert wipe["working_db"]["messages"] == 1
    assert wipe["working_db"]["chunks_fts"] == 1
    assert wipe["archive_db"]["messages"] == 1
    assert wipe["chroma_chunks"] == 1
    # research(3: r1, sub/inner, source-traces/s1) + journals(1) + uploads(1) + generated(1)
    assert wipe["workspace"]["total_files"] == 6
    assert wipe["workspace"]["nested_subdirs"]["research/source-traces"] == 1
    assert wipe["users_last_seen_at_to_clear"] == 1
    assert summary["would_preserve"]["working_users"][0]["name"] == "Lyle"

    # No mutation.
    assert _table_count(db_mod, "conversations") == 1
    assert _table_count(db_mod, "archive.messages") == 1
    assert reset_env["chroma"].get_collection_count() == 1
    assert (reset_env["workspace_root"] / "research" / "r1.md").exists()
    assert not (reset_env["tmp_path"] / "backups").exists()


# ---------------------------------------------------------------------------
# Destructive reset
# ---------------------------------------------------------------------------

def test_destructive_reset_wipes_and_preserves(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]
    tmp_path = reset_env["tmp_path"]
    workspace_root = reset_env["workspace_root"]

    # Governance file that must remain untouched.
    (tmp_path / "soul.md").write_text("seed identity", encoding="utf-8")

    summary = reset.execute_go_live_reset(
        confirm=True,
        typed_confirm=PHRASE,
        verify_target_dir=tmp_path / "verify",
    )

    assert summary["ok"] is True
    assert summary["backup_verified"] is True

    # Every wiped table empty.
    for table in reset.WORKING_WIPE_TABLES:
        assert _table_count(db_mod, table) == 0
    assert _table_count(db_mod, "chunks_fts") == 0
    assert _table_count(db_mod, "archive.messages") == 0

    # Preserved identity / config / schema.
    assert _table_count(db_mod, "users") == 1
    assert _table_count(db_mod, "channel_identifiers") == 1
    assert _table_count(db_mod, "archive.users") == 1
    assert _table_count(db_mod, "schema_versions") >= 1
    with db_mod.get_connection() as conn:
        last_seen = conn.execute("SELECT last_seen_at FROM users WHERE id='u1'").fetchone()[0]
    assert last_seen is None

    # Chroma emptied.
    assert reset_env["chroma"].get_collection_count() == 0

    # Workspace dirs cleared but structure kept.
    assert reset.WORKSPACE_WIPE_DIRS  # sanity
    for name in reset.WORKSPACE_WIPE_DIRS:
        target = workspace_root / name
        assert target.exists()
        assert sum(1 for p in target.rglob("*") if p.is_file()) == 0
    assert (workspace_root / "research" / "source-traces").is_dir()
    # Non-wiped workspace content survives.
    assert (workspace_root / "writing" / "keep.md").exists()

    # Governance + backup untouched / present.
    assert (tmp_path / "soul.md").read_text(encoding="utf-8") == "seed identity"
    assert (tmp_path / "backups").exists()

    # Audit file records the backup path (rollback artifact).
    import json

    audit_path = tmp_path / "backups" / "go-live-reset-audit"
    audit_files = list(audit_path.glob("go-live-reset-*.json"))
    assert len(audit_files) == 1
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    assert audit["backup_path"] == summary["backup_path"]
    assert audit["backup_is_rollback_artifact"] is True
    assert audit["wiped"]["working_db"]["conversations"] == 1
    assert audit["wiped"]["users_last_seen_cleared"] == 1
    assert audit["preserved"]["working_users"][0]["id"] == "u1"


# ---------------------------------------------------------------------------
# verify-clean
# ---------------------------------------------------------------------------

def test_verify_clean_passes_after_reset_and_fails_when_dirty(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]
    tmp_path = reset_env["tmp_path"]

    reset.execute_go_live_reset(
        confirm=True,
        typed_confirm=PHRASE,
        verify_target_dir=tmp_path / "verify",
    )

    clean = reset.verify_clean()
    assert clean["ok"] is True
    assert clean["status"] == "passed"
    assert clean["failures"] == []

    # Dirty it: insert a conversation referencing the preserved user.
    with db_mod.get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, started_at) VALUES ('cX', 'u1', ?)",
            (NOW,),
        )
        conn.commit()

    dirty = reset.verify_clean()
    assert dirty["ok"] is False
    assert dirty["status"] == "failed"
    assert any("conversations" in failure for failure in dirty["failures"])


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_phrase_mismatch_aborts_with_no_changes(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]
    tmp_path = reset_env["tmp_path"]

    with pytest.raises(reset.GoLiveResetError, match="phrase mismatch"):
        reset.execute_go_live_reset(
            confirm=True,
            typed_confirm="WRONG PHRASE",
            verify_target_dir=tmp_path / "verify",
        )

    # No wipe occurred.
    assert _table_count(db_mod, "conversations") == 1
    assert _table_count(db_mod, "archive.messages") == 1
    assert reset_env["chroma"].get_collection_count() == 1
    assert (reset_env["workspace_root"] / "research" / "r1.md").exists()
    # No audit file written.
    assert not (tmp_path / "backups" / "go-live-reset-audit").exists()


def test_backup_verification_failure_aborts_before_wipe(reset_env, monkeypatch):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]
    tmp_path = reset_env["tmp_path"]

    monkeypatch.setattr(
        reset, "verify_backup_restore", lambda *a, **k: {"ok": False, "status": "failed"}
    )

    with pytest.raises(reset.GoLiveResetError, match="verification failed"):
        reset.execute_go_live_reset(
            confirm=True,
            typed_confirm=PHRASE,
            verify_target_dir=tmp_path / "verify",
        )

    assert _table_count(db_mod, "conversations") == 1
    assert reset_env["chroma"].get_collection_count() == 1
    assert not (tmp_path / "backups" / "go-live-reset-audit").exists()


def test_confirm_flag_required(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]
    tmp_path = reset_env["tmp_path"]

    with pytest.raises(reset.GoLiveResetError, match="confirm-go-live-reset"):
        reset.execute_go_live_reset(confirm=False, typed_confirm=PHRASE)

    # Aborted before creating any backup.
    assert not (tmp_path / "backups").exists()
    assert _table_count(db_mod, "conversations") == 1


def test_unclassified_table_aborts(reset_env):
    _seed_all(reset_env)
    reset = reset_env["reset"]
    db_mod = reset_env["db"]

    with db_mod.get_connection() as conn:
        conn.execute("CREATE TABLE stray_experiment (id TEXT)")
        conn.commit()

    with pytest.raises(reset.GoLiveResetError, match="stray_experiment"):
        reset.plan_go_live_reset()
