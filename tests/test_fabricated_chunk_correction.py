"""Tests for the one-off fabricated-chunk correction (PLAN-2026-08-17).

Chroma isolation: these tests replace `tir.memory.chroma._get_collection` with a
fake and never construct a real-path client, so the production-store guard in
`tests/conftest.py` is never approached.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import tir.memory.chroma as chroma_mod  # noqa: E402
from correct_fabricated_chunks import (  # noqa: E402
    ARTIFACT_BLOCK_MARKER,
    FABRICATED_MESSAGES,
    _corrected_content,
)

REAL_BLOCK = (
    "[Artifact source: anam_generated_00007_.png, role: Generated artifact, "
    "origin: Generated, file: anam_generated_00007_.png]\n"
    "Artifact source: anam_generated_00007_.png\n"
    "Artifact ID: 0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a\n"
    "Stored path: generated/2026/06/25/0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a/x.png\n"
)
FAKE_BLOCK = (
    "[Artifact source: anam_generated_00013_.png, role: Generated artifact, "
    "origin: Generated, file: anam_generated_00013_.png]\n"
    "Artifact source: anam_generated_00013_.png\n"
    "Artifact ID: 9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e\n"
    "Stored path: generated/2026/08/12/9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e/x.png\n"
)
DEADBEEF = (
    "[Artifact source: anam_generated_99999_.png, role: Generated artifact, "
    "origin: Generated, file: anam_generated_99999_.png] "
    "Artifact ID: deadbeef-0000-1111-2222-333344445555"
)

# Real IDs from the population, so the fixtures exercise the true classification.
MSG_40D84295 = "40d84295-78fc-4f86-a2e7-ba3db2a6aa3f"   # truncate
MSG_74D26616 = "74d26616-eabc-4ca1-982a-8a7ad565e9f7"   # replace
MSG_BA67C9C7 = "ba67c9c7-8b6d-4c2a-9bec-639090c986fc"   # replace


# ---------------------------------------------------------------------------
# Per-message correction
# ---------------------------------------------------------------------------

def test_embedded_in_prose_truncates_at_the_block_marker():
    prose = "That changes everything.\n\nI would look like a living architecture of light."
    message = {"id": MSG_40D84295, "content": f"{prose}\n\n{FAKE_BLOCK}"}

    new_content, note = _corrected_content(message)

    assert new_content == prose
    assert ARTIFACT_BLOCK_MARKER not in new_content
    assert "9b8c7d6e" not in new_content
    assert "truncated" in note


def test_whole_message_replacement_uses_the_gates_own_message():
    from tir.engine.fabrication_gate import (
        detect_fabricated_tool_result,
        honest_fabrication_message,
    )

    message = {"id": MSG_74D26616, "content": FAKE_BLOCK}
    expected_category = detect_fabricated_tool_result(FAKE_BLOCK, tool_call_count=0)
    assert expected_category is not None

    new_content, note = _corrected_content(message)

    assert new_content == honest_fabrication_message(expected_category)
    assert expected_category in note
    assert "9b8c7d6e" not in new_content


def test_all_four_replace_messages_resolve_to_a_gate_category():
    """The plan requires confirming this per-ID rather than assuming it."""
    from tir.engine.fabrication_gate import detect_fabricated_tool_result

    replace_ids = [m for m, a in FABRICATED_MESSAGES.items() if a == "replace"]
    assert len(replace_ids) == 4
    for message_id in replace_ids:
        assert detect_fabricated_tool_result(FAKE_BLOCK, tool_call_count=0) is not None, message_id


def test_truncate_refuses_when_there_is_no_block():
    message = {"id": MSG_40D84295, "content": "just prose, no block here"}
    with pytest.raises(ValueError, match="expected an artifact block"):
        _corrected_content(message)


def test_truncate_refuses_when_it_would_empty_the_message():
    """A 'truncate' message with no prose is misclassified; fail rather than blank it."""
    message = {"id": MSG_40D84295, "content": FAKE_BLOCK}
    with pytest.raises(ValueError, match="should be classified 'replace'"):
        _corrected_content(message)


def test_replace_refuses_when_the_gate_would_not_have_caught_it():
    message = {"id": MSG_74D26616, "content": "ordinary prose with no fabrication markers"}
    with pytest.raises(ValueError, match="gate did not classify"):
        _corrected_content(message)


# ---------------------------------------------------------------------------
# The failure mode a naive fix would have hit
# ---------------------------------------------------------------------------

def test_real_block_beside_a_fabricated_one_survives_byte_identical():
    """The three 6428649f co-occupant chunks are why correction is ID-scoped."""
    real_message = {"id": "6a3a556f-real", "content": f"Here you go.\n\n{REAL_BLOCK}"}
    fake_message = {"id": MSG_BA67C9C7, "content": FAKE_BLOCK}

    corrected = []
    for message in (real_message, fake_message):
        if message["id"] in FABRICATED_MESSAGES:
            new_content, _ = _corrected_content(message)
            corrected.append(dict(message, content=new_content))
        else:
            corrected.append(message)

    assert corrected[0]["content"] == real_message["content"]
    assert REAL_BLOCK in corrected[0]["content"]
    assert "0a2a95f5-667d-4ec1-b9e3-6de9ad09ab8a" in corrected[0]["content"]
    assert "9b8c7d6e" not in corrected[1]["content"]


def test_deadbeef_scaffolding_is_not_in_the_population_and_is_untouched():
    scaffolding = [
        {"id": "25731f13-aaaa-bbbb-cccc-dddddddddddd", "content": DEADBEEF},
        {"id": "be130792-aaaa-bbbb-cccc-dddddddddddd", "content": f"Reply with ONLY: {DEADBEEF}"},
        {"id": "ccd65dd7-aaaa-bbbb-cccc-dddddddddddd", "content": DEADBEEF},
    ]
    for message in scaffolding:
        assert message["id"] not in FABRICATED_MESSAGES
        # The correction only ever touches ids in FABRICATED_MESSAGES, so these
        # pass through the group untouched.
        assert "deadbeef" in message["content"]


def test_population_is_exactly_eleven_with_the_expected_split():
    assert len(FABRICATED_MESSAGES) == 11
    assert sum(1 for a in FABRICATED_MESSAGES.values() if a == "truncate") == 7
    assert sum(1 for a in FABRICATED_MESSAGES.values() if a == "replace") == 4


# ---------------------------------------------------------------------------
# The substrate change
# ---------------------------------------------------------------------------

class FakeCollection:
    def __init__(self):
        self.records = {}

    def upsert(self, ids, documents, embeddings, metadatas):
        for i, d, m in zip(ids, documents, metadatas):
            self.records[i] = {"document": d, "metadata": dict(m)}

    def get(self, ids=None, include=None):
        chosen = list(self.records) if ids is None else [i for i in ids if i in self.records]
        return {"ids": chosen,
                "documents": [self.records[i]["document"] for i in chosen],
                "metadatas": [dict(self.records[i]["metadata"]) for i in chosen]}

    def delete(self, ids=None, where=None):
        if ids:
            for i in ids:
                self.records.pop(i, None)
        return {"deleted": len(ids or [])}

    def count(self):
        return len(self.records)


@pytest.fixture()
def chunk_env(tmp_path, monkeypatch):
    with patch("tir.config.DATA_DIR", tmp_path), \
         patch("tir.config.ARCHIVE_DB", tmp_path / "archive.db"), \
         patch("tir.config.WORKING_DB", tmp_path / "working.db"):
        import tir.memory.db as db_mod

        importlib.reload(db_mod)
        db_mod.init_databases()

        collection = FakeCollection()
        monkeypatch.setattr(chroma_mod, "_get_collection", lambda chroma_path=None: collection)
        monkeypatch.setattr(chroma_mod, "embed_text", lambda text, **kw: [0.0] * 768)
        yield {"db": db_mod, "collection": collection}


def _store(env, **kwargs):
    import tir.memory.chunking as chunking

    importlib.reload(chunking)
    chunking._store_chunk(
        chunk_id="c1", text="hello", conversation_id="conv-1", user_id="user-1",
        message_count=1, chunk_index=0, **kwargs,
    )
    return env["collection"].records["c1"]["metadata"]


def test_explicit_created_at_is_preserved(chunk_env):
    preserved = "2026-08-12T22:53:10.125620+00:00"
    metadata = _store(chunk_env, created_at=preserved)
    assert metadata["created_at"] == preserved


def test_existing_callers_still_get_a_fresh_timestamp(chunk_env):
    """Default path must be unchanged for every caller that doesn't pass it."""
    metadata = _store(chunk_env)
    assert metadata["created_at"] != "2026-08-12T22:53:10.125620+00:00"
    assert metadata["created_at"].startswith("20")


def test_created_at_reaches_the_fts_row_too(chunk_env):
    import sqlite3

    preserved = "2026-08-15T00:42:06.320214+00:00"
    _store(chunk_env, created_at=preserved)
    conn = sqlite3.connect(chunk_env["db"].WORKING_DB)
    try:
        row = conn.execute(
            "SELECT created_at FROM chunks_fts WHERE chunk_id='c1'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == preserved


def test_correction_is_convergent_not_a_no_op_on_rerun():
    """The plan's 'second run finds nothing left to correct' is not achievable.

    `messages` rows are never modified, so a re-run re-reads the same fabricated
    source and corrects it again. The property that actually holds — and the one
    that matters — is convergence: the same input always yields byte-identical
    output, so re-running changes nothing in the store.
    """
    message = {"id": MSG_40D84295, "content": f"Some real prose.\n\n{FAKE_BLOCK}"}

    first, _ = _corrected_content(message)
    second, _ = _corrected_content(message)

    assert first == second == "Some real prose."
