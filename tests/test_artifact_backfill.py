"""Tests for the pre-slim artifact event chunk backfill.

Chroma isolation note: these tests replace `tir.memory.chroma._get_collection`
wholesale rather than patching `tir.config.CHROMA_DIR`. `upsert_chunk` binds
`chroma_path=CHROMA_DIR` as a DEFAULT ARGUMENT at import time, so patching the
config value (or calling `reset_client()`) does not redirect writes — they land
in the real `data/prod/chromadb`. Replacing `_get_collection` means the real
path is never used at all.
"""

import importlib
import json
import sqlite3
from unittest.mock import patch

import pytest

from tir.memory import artifact_backfill
from tir.memory.artifact_backfill import (
    OLD_EVENT_TEXT_PREFIX,
    SLIM_EVENT_TEXT_PREFIX,
    backfill_artifact_event_chunks,
)


EMBEDDING_DIM = 768


def _embedding_for(text: str) -> list[float]:
    """Deterministic, text-dependent fake embedding.

    Element 0 encodes the length of the embedded text, so a test can prove which
    text a stored vector was computed from.
    """
    return [float(len(text))] + [0.0] * (EMBEDDING_DIM - 1)


SENTINEL_EMBEDDING = [-1.0] * EMBEDDING_DIM


class FakeCollection:
    """Minimal in-memory stand-in for the Chroma collection."""

    def __init__(self):
        self.records = {}
        self.upsert_calls = []

    def add_record(self, chunk_id, text, metadata, embedding=None):
        self.records[chunk_id] = {
            "document": text,
            "metadata": dict(metadata),
            "embedding": list(embedding if embedding is not None else SENTINEL_EMBEDDING),
        }

    def get(self, include=None):
        ids = list(self.records)
        return {
            "ids": ids,
            "documents": [self.records[i]["document"] for i in ids],
            "metadatas": [dict(self.records[i]["metadata"]) for i in ids],
        }

    def upsert(self, ids, documents, embeddings, metadatas):
        self.upsert_calls.append(
            {
                "ids": list(ids),
                "documents": list(documents),
                "embeddings": [list(e) for e in embeddings],
                "metadatas": [dict(m) for m in metadatas],
            }
        )
        for chunk_id, document, embedding, metadata in zip(
            ids, documents, embeddings, metadatas
        ):
            self.records[chunk_id] = {
                "document": document,
                "metadata": dict(metadata),
                "embedding": list(embedding),
            }

    def count(self):
        return len(self.records)


class EmbedRecorder:
    def __init__(self):
        self.texts = []

    def __call__(self, text, *args, **kwargs):
        self.texts.append(text)
        return _embedding_for(text)


def _old_event_text(
    *,
    title,
    artifact_id,
    filename,
    path,
    sha256="a" * 64,
    size_bytes=31,
    extra_lines=(),
):
    """Reproduce the pre-slim `_event_text` block shape (removed at commit 2f7e3a6)."""
    lines = [
        f"Artifact source: {title}",
        f"Artifact ID: {artifact_id}",
        f"File: {filename}",
        f"Stored path: {path}",
        "Source: generation",
        "Origin: Generated",
        "Source role: Generated artifact",
        "MIME type: image/png",
        f"Size: {size_bytes} bytes",
        f"SHA256: {sha256}",
        *extra_lines,
    ]
    return "\n".join(lines)


@pytest.fixture()
def backfill_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"), \
         patch("tir.config.CHROMA_DIR", str(tmp_path / "chromadb")):
        import tir.memory.db as db_mod
        import tir.memory.chroma as chroma_mod

        importlib.reload(db_mod)
        db_mod.init_databases()

        collection = FakeCollection()
        embed = EmbedRecorder()
        monkeypatch.setattr(
            chroma_mod,
            "_get_collection",
            lambda chroma_path=None: collection,
        )
        monkeypatch.setattr(chroma_mod, "embed_text", embed)

        yield {
            "db": db_mod,
            "collection": collection,
            "embed": embed,
            "working_db": tmp_path / "working.db",
        }


def _insert_artifact(
    env,
    *,
    artifact_id,
    title,
    artifact_type="generated_file",
    description=None,
    metadata=None,
):
    with env["db"].get_connection() as conn:
        conn.execute(
            """INSERT INTO main.artifacts
               (artifact_id, artifact_type, title, description, path, status,
                created_at, updated_at, source, metadata_json)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 'generation', ?)""",
            (
                artifact_id,
                artifact_type,
                title,
                description,
                f"generated/{artifact_id}/file.png",
                "2026-06-01T00:00:00+00:00",
                "2026-06-01T00:00:00+00:00",
                json.dumps(metadata) if metadata is not None else None,
            ),
        )
        conn.commit()


def _seed_chunk(
    env,
    *,
    chunk_id,
    text,
    metadata,
    conversation_id="conv-1",
    user_id="user-1",
    source_type="artifact_document",
    source_trust="generated",
    created_at="2026-06-01T00:00:00+00:00",
    embedding=None,
):
    env["collection"].add_record(chunk_id, text, metadata, embedding=embedding)
    env["db"].upsert_chunk_fts(
        chunk_id=chunk_id,
        text=text,
        conversation_id=conversation_id,
        user_id=user_id,
        source_type=source_type,
        source_trust=source_trust,
        created_at=created_at,
    )


def _event_metadata(artifact_id, **overrides):
    metadata = {
        "source_type": "artifact_document",
        "source_trust": "generated",
        "artifact_id": artifact_id,
        "title": "Sunset over water",
        "filename": "sunset.png",
        "path": f"generated/{artifact_id}/sunset.png",
        "origin": "generated",
        "source_role": "generated_artifact",
        "source_conversation_id": "conv-1",
        "source_message_id": "msg-1",
        "user_id": "user-1",
        "created_at": "2026-06-01T00:00:00+00:00",
        "chunk_index": -1,
        "chunk_kind": "event",
        "media_kind": "generated_image",
        "prompt": "a sunset over calm water",
    }
    metadata.update(overrides)
    return metadata


def _fts_row(env, chunk_id):
    conn = sqlite3.connect(env["working_db"])
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT chunk_id, text, conversation_id, user_id, source_type,
                      source_trust, created_at
               FROM chunks_fts WHERE chunk_id = ?""",
            (chunk_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _fts_count(env):
    conn = sqlite3.connect(env["working_db"])
    try:
        return conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    finally:
        conn.close()


def _seed_generated_image(env, artifact_id="gen-1", prompt="a sunset over calm water"):
    _insert_artifact(
        env,
        artifact_id=artifact_id,
        title="Sunset over water",
        metadata={
            "filename": "sunset.png",
            "sha256": "b" * 64,
            "size_bytes": 4096,
            "media_kind": "generated_image",
            "prompt": prompt,
            "seed": 1067942701,
            "width": 512,
            "height": 512,
        },
    )
    chunk_id = f"artifact_{artifact_id}_event"
    _seed_chunk(
        env,
        chunk_id=chunk_id,
        text=_old_event_text(
            title="Sunset over water",
            artifact_id=artifact_id,
            filename="sunset.png",
            path=f"generated/{artifact_id}/sunset.png",
            extra_lines=[
                "Media kind: generated_image",
                f"Generation prompt (provenance metadata): {prompt}",
                "Generation seed: 1067942701",
            ],
        ),
        metadata=_event_metadata(artifact_id, prompt=prompt),
    )
    return chunk_id


# ---------------------------------------------------------------------------
# 1. Rewrite in place, provenance untouched
# ---------------------------------------------------------------------------

def test_old_shape_chunk_is_rewritten_with_metadata_and_provenance_preserved(backfill_env):
    chunk_id = _seed_generated_image(backfill_env)
    metadata_before = dict(backfill_env["collection"].records[chunk_id]["metadata"])
    fts_before = _fts_row(backfill_env, chunk_id)

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["rewritten"] == 1
    assert summary["skipped"] == 0
    assert summary["failed"] == 0

    record = backfill_env["collection"].records[chunk_id]
    assert record["document"].startswith(SLIM_EVENT_TEXT_PREFIX)
    assert not record["document"].startswith(OLD_EVENT_TEXT_PREFIX)
    for dropped in ("SHA256:", "Stored path:", "Size:", "bytes", "Generation seed"):
        assert dropped not in record["document"]

    # Metadata dict written back byte-identical.
    assert record["metadata"] == metadata_before

    # FTS provenance columns identical; only the text changed.
    fts_after = _fts_row(backfill_env, chunk_id)
    for column in (
        "conversation_id",
        "user_id",
        "source_type",
        "source_trust",
        "created_at",
    ):
        assert fts_after[column] == fts_before[column], column
    assert fts_after["text"] == record["document"]
    assert fts_after["text"] != fts_before["text"]

    # Counts unchanged — this only rewrites text.
    assert summary["counts_before"] == summary["counts_after"]


# ---------------------------------------------------------------------------
# 2. Semantic content is kept per artifact type
# ---------------------------------------------------------------------------

def test_generation_keeps_prompt_and_upload_keeps_description(backfill_env):
    _seed_generated_image(backfill_env, artifact_id="gen-1", prompt="a red barn at dusk")

    _insert_artifact(
        backfill_env,
        artifact_id="up-1",
        title="Anam roadmap",
        artifact_type="uploaded_file",
        description="the current roadmap document",
        metadata={"filename": "roadmap.md", "sha256": "c" * 64, "size_bytes": 900},
    )
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_up-1_event",
        text=_old_event_text(
            title="Anam roadmap",
            artifact_id="up-1",
            filename="roadmap.md",
            path="uploads/up-1/roadmap.md",
            extra_lines=["Description: the current roadmap document"],
        ),
        metadata=_event_metadata(
            "up-1",
            title="Anam roadmap",
            filename="roadmap.md",
            path="uploads/up-1/roadmap.md",
            media_kind=None,
            prompt=None,
        ),
    )

    backfill_artifact_event_chunks(dry_run=False)

    generation = backfill_env["collection"].records["artifact_gen-1_event"]["document"]
    assert "Prompt: a red barn at dusk" in generation

    upload = backfill_env["collection"].records["artifact_up-1_event"]["document"]
    assert "Description: the current roadmap document" in upload
    assert "SHA256:" not in upload


def test_observed_description_is_kept(backfill_env):
    _insert_artifact(
        backfill_env,
        artifact_id="shot-1",
        title="screenshot",
        artifact_type="image",
        metadata={
            "media_kind": "uploaded_image",
            "observed_description": "a terminal window showing a stack trace",
            "uncertainty_label": "unverified_visual_interpretation",
        },
    )
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_shot-1_event",
        text=_old_event_text(
            title="screenshot",
            artifact_id="shot-1",
            filename="shot.png",
            path="uploads/shot-1/shot.png",
        ),
        metadata=_event_metadata("shot-1", title="screenshot", prompt=None),
    )

    backfill_artifact_event_chunks(dry_run=False)

    text = backfill_env["collection"].records["artifact_shot-1_event"]["document"]
    assert "a terminal window showing a stack trace" in text
    assert "visual interpretation, not verified fact" in text


# ---------------------------------------------------------------------------
# 3. Descriptor-less artifact renders to a single line, and stays embeddable
# ---------------------------------------------------------------------------

def test_artifact_without_descriptor_renders_single_line(backfill_env):
    _insert_artifact(
        backfill_env,
        artifact_id="bare-1",
        title="tir.log",
        artifact_type="uploaded_file",
        metadata={"filename": "tir.log", "sha256": "d" * 64, "size_bytes": 120},
    )
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_bare-1_event",
        text=_old_event_text(
            title="tir.log",
            artifact_id="bare-1",
            filename="tir.log",
            path="uploads/bare-1/tir.log",
        ),
        metadata=_event_metadata(
            "bare-1", title="tir.log", filename="tir.log", media_kind=None, prompt=None
        ),
    )

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["rewritten"] == 1
    text = backfill_env["collection"].records["artifact_bare-1_event"]["document"]
    assert text == "Artifact: tir.log (id: bare-1)"
    # Non-empty: upsert_chunk raises ValueError on empty text.
    assert text.strip()


# ---------------------------------------------------------------------------
# 4. Already-slim chunks are not candidates
# ---------------------------------------------------------------------------

def test_already_slim_chunk_is_not_touched_and_not_embedded(backfill_env):
    _insert_artifact(
        backfill_env,
        artifact_id="slim-1",
        title="Sunset over water",
        metadata={"media_kind": "generated_image", "prompt": "a sunset over calm water"},
    )
    slim_text = "Artifact: Sunset over water (id: slim-1)\nPrompt: a sunset over calm water"
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_slim-1_event",
        text=slim_text,
        metadata=_event_metadata("slim-1"),
    )

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["scanned"] == 1
    assert summary["already_slim"] == 1
    assert summary["eligible"] == 0
    assert summary["rewritten"] == 0
    assert backfill_env["collection"].upsert_calls == []
    assert backfill_env["embed"].texts == []
    assert backfill_env["collection"].records["artifact_slim-1_event"]["document"] == slim_text


# ---------------------------------------------------------------------------
# 5. Non-event chunks carrying the same markers are never touched
# ---------------------------------------------------------------------------

def test_content_and_conversation_chunks_with_markers_are_untouched(backfill_env):
    _insert_artifact(
        backfill_env,
        artifact_id="doc-1",
        title="soul file",
        artifact_type="uploaded_file",
        metadata={"filename": "soul.py"},
    )

    content_text = (
        "Artifact source: soul file\n"
        "File: soul.py\n"
        "Origin: Uploaded\n"
        "Source role: Source material\n"
        "Artifact ID: doc-1\n"
        "Content chunk: 0\n\n"
        "SHA256: deadbeef appears inside the uploaded file's own text\n"
        "Stored path: also inside the file body"
    )
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_doc-1_chunk_0",
        text=content_text,
        metadata=_event_metadata(
            "doc-1", title="soul file", chunk_kind="content", chunk_index=0
        ),
    )

    conversation_text = (
        "Artifact source: fake-output.png\n"
        "SHA256: 9762028ae87391ac8e01e2a01a493d9134f15797ffa0fa3fb2b18bb5d8bf057e\n"
        "Stored path: generated/2026/06/25/fake/fake-output.png"
    )
    _seed_chunk(
        backfill_env,
        chunk_id="conv-9_chunk_3",
        text=conversation_text,
        metadata={
            "source_type": "conversation",
            "conversation_id": "conv-9",
            "chunk_index": 3,
        },
        source_type="conversation",
        source_trust="firsthand",
    )

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["scanned"] == 0
    assert summary["eligible"] == 0
    assert backfill_env["collection"].upsert_calls == []
    assert backfill_env["collection"].records["artifact_doc-1_chunk_0"]["document"] == content_text
    assert backfill_env["collection"].records["conv-9_chunk_3"]["document"] == conversation_text


# ---------------------------------------------------------------------------
# 6. Orphan event chunks are skipped and logged, never blanked
# ---------------------------------------------------------------------------

def test_event_chunk_without_artifact_row_is_skipped_and_logged(backfill_env):
    orphan_text = _old_event_text(
        title="fake-output.png",
        artifact_id="orphan-1",
        filename="fake-output.png",
        path="generated/orphan-1/fake-output.png",
    )
    _seed_chunk(
        backfill_env,
        chunk_id="artifact_orphan-1_event",
        text=orphan_text,
        metadata=_event_metadata("orphan-1", title="fake-output.png"),
    )

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["eligible"] == 1
    assert summary["skipped"] == 1
    assert summary["rewritten"] == 0
    entry = summary["entries"][0]
    assert entry["status"] == "skipped"
    assert entry["reason"] == "no_artifact_row"
    assert entry["chunk_id"] == "artifact_orphan-1_event"
    # Untouched, not blanked.
    assert backfill_env["collection"].records["artifact_orphan-1_event"]["document"] == orphan_text
    assert backfill_env["collection"].upsert_calls == []


def test_chunk_missing_fts_row_is_skipped_rather_than_partially_written(backfill_env):
    _seed_generated_image(backfill_env, artifact_id="gen-1")
    with backfill_env["db"].get_connection() as conn:
        conn.execute("DELETE FROM main.chunks_fts WHERE chunk_id = ?", ("artifact_gen-1_event",))
        conn.commit()

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["skipped"] == 1
    assert summary["entries"][0]["reason"] == "missing_fts_row"
    assert backfill_env["collection"].upsert_calls == []
    assert _fts_count(backfill_env) == 0


# ---------------------------------------------------------------------------
# 7. Dry run writes nothing
# ---------------------------------------------------------------------------

def test_dry_run_reports_without_writing(backfill_env):
    chunk_id = _seed_generated_image(backfill_env)
    document_before = backfill_env["collection"].records[chunk_id]["document"]
    embedding_before = list(backfill_env["collection"].records[chunk_id]["embedding"])
    fts_before = _fts_row(backfill_env, chunk_id)

    summary = backfill_artifact_event_chunks()

    assert summary["dry_run"] is True
    assert summary["rewritten"] == 1
    entry = summary["entries"][0]
    assert entry["status"] == "would_rewrite"
    assert entry["old_text"] == document_before
    assert entry["new_text"].startswith(SLIM_EVENT_TEXT_PREFIX)
    assert entry["new_chars"] < entry["old_chars"]

    assert backfill_env["collection"].upsert_calls == []
    assert backfill_env["collection"].records[chunk_id]["document"] == document_before
    assert backfill_env["collection"].records[chunk_id]["embedding"] == embedding_before
    assert _fts_row(backfill_env, chunk_id) == fts_before
    assert backfill_env["embed"].texts == []


# ---------------------------------------------------------------------------
# 8. Idempotency
# ---------------------------------------------------------------------------

def test_second_run_rewrites_nothing(backfill_env):
    _seed_generated_image(backfill_env)

    first = backfill_artifact_event_chunks(dry_run=False)
    second = backfill_artifact_event_chunks(dry_run=False)

    assert first["rewritten"] == 1
    assert second["rewritten"] == 0
    assert second["eligible"] == 0
    assert second["already_slim"] == 1
    assert len(backfill_env["collection"].upsert_calls) == 1
    assert first["counts_after"] == second["counts_after"]


# ---------------------------------------------------------------------------
# 9. One failing chunk does not abort the run
# ---------------------------------------------------------------------------

def test_failure_on_one_chunk_does_not_abort_the_others(backfill_env, monkeypatch):
    _seed_generated_image(backfill_env, artifact_id="gen-1")
    _seed_generated_image(backfill_env, artifact_id="gen-2")

    real_get_artifact = artifact_backfill.get_artifact

    def exploding_get_artifact(artifact_id):
        if artifact_id == "gen-1":
            raise RuntimeError("row read blew up")
        return real_get_artifact(artifact_id)

    monkeypatch.setattr(artifact_backfill, "get_artifact", exploding_get_artifact)

    summary = backfill_artifact_event_chunks(dry_run=False)

    assert summary["failed"] == 1
    assert summary["rewritten"] == 1
    failed = [e for e in summary["entries"] if e["status"] == "failed"][0]
    assert failed["chunk_id"] == "artifact_gen-1_event"
    assert "RuntimeError: row read blew up" in failed["reason"]
    # The healthy chunk still went through.
    assert backfill_env["collection"].records["artifact_gen-2_event"]["document"].startswith(
        SLIM_EVENT_TEXT_PREFIX
    )
    assert backfill_env["collection"].records["artifact_gen-1_event"]["document"].startswith(
        OLD_EVENT_TEXT_PREFIX
    )


# ---------------------------------------------------------------------------
# 10. The embedding is recomputed from the NEW text
# ---------------------------------------------------------------------------

def test_embedding_is_recomputed_from_new_text_not_carried_over(backfill_env):
    chunk_id = _seed_generated_image(backfill_env)
    old_text = backfill_env["collection"].records[chunk_id]["document"]
    assert backfill_env["collection"].records[chunk_id]["embedding"] == SENTINEL_EMBEDDING

    summary = backfill_artifact_event_chunks(dry_run=False)
    new_text = summary["entries"][0]["new_text"]

    # embed_text was called exactly once, with the NEW text.
    assert backfill_env["embed"].texts == [new_text]
    assert old_text not in backfill_env["embed"].texts

    # The stored vector is the one derived from the new text, and the old
    # chunk's vector was not carried over.
    stored = backfill_env["collection"].records[chunk_id]["embedding"]
    assert stored == _embedding_for(new_text)
    assert stored != SENTINEL_EMBEDDING
    assert stored != _embedding_for(old_text)

    # No caller passed a precomputed embedding — upsert_chunk derived it.
    call = backfill_env["collection"].upsert_calls[0]
    assert call["documents"] == [new_text]
    assert call["embeddings"] == [_embedding_for(new_text)]


# ---------------------------------------------------------------------------
# limit
# ---------------------------------------------------------------------------

def test_limit_bounds_the_number_of_chunks_processed(backfill_env):
    _seed_generated_image(backfill_env, artifact_id="gen-1")
    _seed_generated_image(backfill_env, artifact_id="gen-2")

    summary = backfill_artifact_event_chunks(dry_run=False, limit=1)

    assert summary["eligible"] == 2
    assert summary["processed"] == 1
    assert summary["rewritten"] == 1
    assert len(backfill_env["collection"].upsert_calls) == 1
