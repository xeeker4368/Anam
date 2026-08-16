"""Tests for the orphaned artifact chunk purge.

Chroma isolation: these tests replace `tir.memory.chroma._get_collection` with a
fake, so no real-path client is ever constructed and the `tests/conftest.py`
production-store guard is never approached.
"""

import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest

import tir.memory.chroma as chroma_mod
from tir.memory.artifact_orphan_purge import (
    EXPECTED_ORPHAN_TITLE,
    purge_orphan_artifact_chunks,
)


class FakeCollection:
    """In-memory stand-in that mimics the Chroma behaviour that matters here."""

    def __init__(self, *, lie_about_deletes=False, raise_on_delete=False):
        self.records = {}
        self.delete_calls = []
        self.lie_about_deletes = lie_about_deletes
        self.raise_on_delete = raise_on_delete

    def add_record(self, chunk_id, text, metadata):
        self.records[chunk_id] = {"document": text, "metadata": dict(metadata)}

    def get(self, ids=None, include=None):
        selected = list(self.records) if ids is None else [i for i in ids if i in self.records]
        return {
            "ids": selected,
            "documents": [self.records[i]["document"] for i in selected],
            "metadatas": [dict(self.records[i]["metadata"]) for i in selected],
        }

    def delete(self, ids):
        self.delete_calls.append(list(ids))
        if self.raise_on_delete:
            raise RuntimeError("chroma delete exploded")
        if not self.lie_about_deletes:
            for chunk_id in ids:
                self.records.pop(chunk_id, None)
        # Mirrors real chromadb: reports success regardless of what happened.
        return {"deleted": len(ids)}

    def count(self):
        return len(self.records)


@pytest.fixture()
def purge_env(tmp_path, monkeypatch):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod

        importlib.reload(db_mod)
        db_mod.init_databases()

        collection = FakeCollection()
        monkeypatch.setattr(
            chroma_mod, "_get_collection", lambda chroma_path=None: collection
        )

        yield {
            "db": db_mod,
            "collection": collection,
            "working_db": tmp_path / "working.db",
            "set_collection": lambda new: monkeypatch.setattr(
                chroma_mod, "_get_collection", lambda chroma_path=None: new
            ),
        }


def _insert_artifact(env, *, artifact_id, title="Real artifact"):
    with env["db"].get_connection() as conn:
        conn.execute(
            """INSERT INTO main.artifacts
               (artifact_id, artifact_type, title, path, status,
                created_at, updated_at, metadata_json)
               VALUES (?, 'generated_file', ?, ?, 'active', ?, ?, ?)""",
            (
                artifact_id,
                title,
                f"generated/{artifact_id}/f.png",
                "2026-06-01T00:00:00+00:00",
                "2026-06-01T00:00:00+00:00",
                json.dumps({"filename": "f.png"}),
            ),
        )
        conn.commit()


def _add_chunk(
    env,
    *,
    chunk_id,
    artifact_id,
    title,
    chunk_kind="event",
    source_type="artifact_document",
    text="Artifact: something (id: x)",
    with_fts=False,
):
    env["collection"].add_record(
        chunk_id,
        text,
        {
            "source_type": source_type,
            "artifact_id": artifact_id,
            "title": title,
            "chunk_kind": chunk_kind,
            "created_at": "2026-06-25T00:56:48+00:00",
        },
    )
    if with_fts:
        env["db"].upsert_chunk_fts(
            chunk_id=chunk_id,
            text=text,
            conversation_id=None,
            user_id=None,
            source_type=source_type,
            source_trust="generated",
            created_at="2026-06-25T00:56:48+00:00",
        )


def _add_orphan(env, *, artifact_id="orph-1", title=EXPECTED_ORPHAN_TITLE, **kwargs):
    _add_chunk(
        env,
        chunk_id=f"artifact_{artifact_id}_event",
        artifact_id=artifact_id,
        title=title,
        **kwargs,
    )
    return f"artifact_{artifact_id}_event"


def _fts_count(env):
    conn = sqlite3.connect(env["working_db"])
    try:
        return conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    finally:
        conn.close()


def _entry(summary, chunk_id):
    return next(e for e in summary["entries"] if e["chunk_id"] == chunk_id)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def test_orphan_fake_output_chunk_is_deleted(purge_env):
    chunk_id = _add_orphan(purge_env)

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["deleted"] == 1
    assert summary["needs_review"] == 0
    assert summary["failed"] == 0
    assert summary["partial"] == 0
    assert chunk_id not in purge_env["collection"].records
    entry = _entry(summary, chunk_id)
    assert entry["status"] == "deleted"
    assert entry["title"] == EXPECTED_ORPHAN_TITLE
    assert entry["created_at"] == "2026-06-25T00:56:48+00:00"


def test_chunk_with_an_artifacts_row_is_never_selected(purge_env):
    _insert_artifact(purge_env, artifact_id="real-1", title=EXPECTED_ORPHAN_TITLE)
    _add_chunk(
        purge_env,
        chunk_id="artifact_real-1_event",
        artifact_id="real-1",
        title=EXPECTED_ORPHAN_TITLE,
    )

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["has_artifact_row"] == 1
    assert summary["orphans_found"] == 0
    assert summary["deleted"] == 0
    assert purge_env["collection"].delete_calls == []
    assert "artifact_real-1_event" in purge_env["collection"].records


def test_orphan_with_unexpected_title_is_needs_review_not_deleted(purge_env):
    """The half-completed-real-ingest case: chunks written, artifacts row never."""
    chunk_id = _add_orphan(purge_env, artifact_id="orph-2", title="Family photo.png")

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["orphans_found"] == 1
    assert summary["needs_review"] == 1
    assert summary["deletable"] == 0
    assert summary["deleted"] == 0
    assert purge_env["collection"].delete_calls == []
    assert chunk_id in purge_env["collection"].records
    entry = _entry(summary, chunk_id)
    assert entry["status"] == "needs_review"
    assert "unexpected_title" in entry["reason"]
    assert "Family photo.png" in entry["reason"]


def test_orphaned_content_chunk_is_needs_review_not_deleted(purge_env):
    _add_chunk(
        purge_env,
        chunk_id="artifact_orph-3_chunk_0",
        artifact_id="orph-3",
        title=EXPECTED_ORPHAN_TITLE,
        chunk_kind="content",
    )

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["needs_review"] == 1
    assert summary["deleted"] == 0
    assert "artifact_orph-3_chunk_0" in purge_env["collection"].records
    assert _entry(summary, "artifact_orph-3_chunk_0")["reason"] == "orphan_content_chunk"


def test_conversation_and_research_chunks_are_never_scanned(purge_env):
    _add_chunk(
        purge_env,
        chunk_id="conv-9_chunk_0",
        artifact_id=None,
        title="a conversation",
        chunk_kind=None,
        source_type="conversation",
    )
    _add_chunk(
        purge_env,
        chunk_id="research_note_1",
        artifact_id=None,
        title="a research note",
        chunk_kind="research_content",
        source_type="research",
    )

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["scanned"] == 0
    assert summary["deleted"] == 0
    assert purge_env["collection"].delete_calls == []
    assert len(purge_env["collection"].records) == 2


# ---------------------------------------------------------------------------
# Dry run and idempotency
# ---------------------------------------------------------------------------

def test_dry_run_deletes_nothing(purge_env):
    chunk_id = _add_orphan(purge_env)

    summary = purge_orphan_artifact_chunks()

    assert summary["dry_run"] is True
    assert summary["deletable"] == 1
    assert summary["deleted"] == 0
    assert _entry(summary, chunk_id)["status"] == "would_delete"
    assert purge_env["collection"].delete_calls == []
    assert chunk_id in purge_env["collection"].records
    assert summary["counts_before"] == summary["counts_after"]


def test_second_run_finds_nothing_to_delete(purge_env):
    _add_orphan(purge_env)

    first = purge_orphan_artifact_chunks(dry_run=False)
    second = purge_orphan_artifact_chunks(dry_run=False)

    assert first["deleted"] == 1
    assert second["deletable"] == 0
    assert second["deleted"] == 0
    assert second["orphans_found"] == 0
    assert len(purge_env["collection"].delete_calls) == 1


def test_limit_bounds_the_number_processed(purge_env):
    _add_orphan(purge_env, artifact_id="orph-a")
    _add_orphan(purge_env, artifact_id="orph-b")

    summary = purge_orphan_artifact_chunks(dry_run=False, limit=1)

    assert summary["deletable"] == 2
    assert summary["processed"] == 1
    assert summary["deleted"] == 1
    assert len(purge_env["collection"].records) == 1


# ---------------------------------------------------------------------------
# FTS symmetry
# ---------------------------------------------------------------------------

def test_orphan_with_an_fts_row_is_removed_from_both_stores(purge_env):
    chunk_id = _add_orphan(purge_env, with_fts=True)
    assert _fts_count(purge_env) == 1

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["deleted"] == 1
    assert summary["partial"] == 0
    assert chunk_id not in purge_env["collection"].records
    assert _fts_count(purge_env) == 0


def test_fts_untouched_when_orphan_has_no_fts_row(purge_env):
    _add_orphan(purge_env)
    _add_chunk(
        purge_env,
        chunk_id="conv-1_chunk_0",
        artifact_id=None,
        title="unrelated",
        chunk_kind=None,
        source_type="conversation",
        with_fts=True,
    )
    before = _fts_count(purge_env)

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["deleted"] == 1
    assert _fts_count(purge_env) == before
    assert summary["counts_after"]["fts_rows"] == before


# ---------------------------------------------------------------------------
# Verification and partial-failure reporting
# ---------------------------------------------------------------------------

def test_delete_that_did_not_land_is_reported_failed_not_deleted(purge_env):
    """chromadb returns {'deleted': n} even when nothing was removed, so success
    must come from re-reading the id."""
    lying = FakeCollection(lie_about_deletes=True)
    purge_env["set_collection"](lying)
    chunk_id = "artifact_orph-9_event"
    lying.add_record(
        chunk_id,
        "text",
        {
            "source_type": "artifact_document",
            "artifact_id": "orph-9",
            "title": EXPECTED_ORPHAN_TITLE,
            "chunk_kind": "event",
            "created_at": "2026-06-25T00:56:48+00:00",
        },
    )

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["deleted"] == 0
    assert summary["failed"] == 1
    entry = _entry(summary, chunk_id)
    assert entry["status"] == "failed"
    assert "still_present" in entry["reason"]


def test_fts_removed_then_chroma_failure_is_reported_partial(purge_env):
    exploding = FakeCollection(raise_on_delete=True)
    chunk_id = "artifact_orph-8_event"
    exploding.add_record(
        chunk_id,
        "text",
        {
            "source_type": "artifact_document",
            "artifact_id": "orph-8",
            "title": EXPECTED_ORPHAN_TITLE,
            "chunk_kind": "event",
            "created_at": "2026-06-25T00:56:48+00:00",
        },
    )
    purge_env["db"].upsert_chunk_fts(
        chunk_id=chunk_id,
        text="text",
        conversation_id=None,
        user_id=None,
        source_type="artifact_document",
        source_trust="generated",
        created_at="2026-06-25T00:56:48+00:00",
    )
    purge_env["set_collection"](exploding)

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["deleted"] == 0
    assert summary["partial"] == 1
    assert summary["failed"] == 0
    entry = _entry(summary, chunk_id)
    assert entry["status"] == "partial"
    assert "chroma_delete_failed" in entry["reason"]
    assert "FTS row already removed" in entry["reason"]


def test_one_failing_chunk_does_not_abort_the_others(purge_env):
    class FlakyCollection(FakeCollection):
        def delete(self, ids):
            if ids == ["artifact_orph-bad_event"]:
                self.delete_calls.append(list(ids))
                raise RuntimeError("boom")
            return super().delete(ids)

    flaky = FlakyCollection()
    for artifact_id in ("orph-bad", "orph-good"):
        flaky.add_record(
            f"artifact_{artifact_id}_event",
            "text",
            {
                "source_type": "artifact_document",
                "artifact_id": artifact_id,
                "title": EXPECTED_ORPHAN_TITLE,
                "chunk_kind": "event",
                "created_at": "2026-06-25T00:56:48+00:00",
            },
        )
    purge_env["set_collection"](flaky)

    summary = purge_orphan_artifact_chunks(dry_run=False)

    assert summary["failed"] == 1
    assert summary["deleted"] == 1
    assert _entry(summary, "artifact_orph-bad_event")["status"] == "failed"
    assert "artifact_orph-good_event" not in flaky.records
    assert "artifact_orph-bad_event" in flaky.records


# ---------------------------------------------------------------------------
# The chroma helper itself
# ---------------------------------------------------------------------------

def test_delete_chunks_by_ids_verifies_by_re_reading(monkeypatch):
    lying = FakeCollection(lie_about_deletes=True)
    honest = FakeCollection()
    for collection in (lying, honest):
        collection.add_record("chunk-a", "a", {})

    monkeypatch.setattr(chroma_mod, "_get_collection", lambda chroma_path=None: lying)
    assert chroma_mod.delete_chunks_by_ids(["chunk-a"]) == {"chunk-a": False}

    monkeypatch.setattr(chroma_mod, "_get_collection", lambda chroma_path=None: honest)
    assert chroma_mod.delete_chunks_by_ids(["chunk-a"]) == {"chunk-a": True}


def test_delete_chunks_by_ids_deletes_one_id_at_a_time(monkeypatch):
    collection = FakeCollection()
    for chunk_id in ("a", "b", "c"):
        collection.add_record(chunk_id, chunk_id, {})
    monkeypatch.setattr(chroma_mod, "_get_collection", lambda chroma_path=None: collection)

    result = chroma_mod.delete_chunks_by_ids(["a", "b"])

    assert result == {"a": True, "b": True}
    assert collection.delete_calls == [["a"], ["b"]]
    assert set(collection.records) == {"c"}


def test_delete_chunks_by_ids_on_missing_id_reports_removed(monkeypatch):
    """Absent is the desired end state, so a re-run of the purge is a cheap no-op."""
    collection = FakeCollection()
    monkeypatch.setattr(chroma_mod, "_get_collection", lambda chroma_path=None: collection)

    assert chroma_mod.delete_chunks_by_ids(["never-existed"]) == {"never-existed": True}
