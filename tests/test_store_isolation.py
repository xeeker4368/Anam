"""Regression tests for production-store isolation.

Covers the two halves of PLAN-2026-08-16-chroma-test-isolation.md:
the source-side fix (store paths resolve from `tir.config` at call time, so
patching `tir.config.CHROMA_DIR` / `tir.config.DATA_DIR` actually redirects),
and the `tests/conftest.py` guard that catches a reintroduced leak.

Note on scope: a single-file run of the file that *had* the leak
(`test_image_generation.py`) never reproduced it — the leak only appears in a
full-suite run, because the default path is bound when `tir.memory.chroma` is
first imported and pytest imports every test module before running anything.
These tests therefore assert the mechanism directly rather than trying to
reproduce the leak.
"""

import os
from pathlib import Path

import chromadb
import pytest

import tir.memory.chroma as chroma
from tir.ops import chat_debug_trace
from tests.conftest import (
    REAL_CHAT_DEBUG_TRACE_PATH,
    REAL_CHROMA_DIR,
    StoreIsolationViolation,
)


class RecordingCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def count(self):
        return 0


class RecordingClient:
    """Stands in for chromadb.PersistentClient and records the path it got."""

    def __init__(self, path=None, **_kwargs):
        self.path = path
        RecordingClient.paths.append(path)
        self.collection = RecordingCollection()

    paths: list = []

    def get_or_create_collection(self, name=None, metadata=None):
        return self.collection


@pytest.fixture()
def recording_client(monkeypatch):
    RecordingClient.paths = []
    monkeypatch.setattr(chromadb, "PersistentClient", RecordingClient)
    chroma.reset_client()
    yield RecordingClient
    chroma.reset_client()


# ---------------------------------------------------------------------------
# Source-side fix: patching tir.config alone is enough
# ---------------------------------------------------------------------------

def test_patching_config_chroma_dir_alone_redirects_writes(
    tmp_path, monkeypatch, recording_client
):
    """No importlib.reload, no bespoke plumbing — the fixture assumption 19
    existing test fixtures already made, now actually true."""
    isolated = str(tmp_path / "chromadb")
    monkeypatch.setattr("tir.config.CHROMA_DIR", isolated)

    chroma.upsert_chunk(
        chunk_id="chunk-1",
        text="isolated text",
        metadata={"source_type": "test"},
        embedding=[0.0] * 768,
    )

    assert recording_client.paths == [isolated]
    assert REAL_CHROMA_DIR not in recording_client.paths


def test_explicit_chroma_path_still_wins_over_config(
    tmp_path, monkeypatch, recording_client
):
    explicit = str(tmp_path / "explicit")
    monkeypatch.setattr("tir.config.CHROMA_DIR", str(tmp_path / "from-config"))

    chroma.get_collection_count(chroma_path=explicit)

    assert recording_client.paths == [explicit]


def test_get_collection_rebinds_when_the_path_changes(
    tmp_path, recording_client
):
    """The cache used to ignore chroma_path once bound, silently handing back
    another store's collection."""
    first = str(tmp_path / "first")
    second = str(tmp_path / "second")

    chroma._get_collection(first)
    chroma._get_collection(first)
    chroma._get_collection(second)

    assert recording_client.paths == [first, second]


def test_chroma_dir_compatibility_alias_is_still_exposed():
    """tests/test_chroma.py reads chroma.CHROMA_DIR as a default sentinel."""
    assert isinstance(chroma.CHROMA_DIR, str)


def test_patching_config_data_dir_alone_redirects_chat_debug_trace(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path)

    assert chat_debug_trace.chat_debug_trace_path() == tmp_path / "chat_debug.jsonl"

    chat_debug_trace.write_chat_debug_trace({"request_id": "abc"})

    written = (tmp_path / "chat_debug.jsonl").read_text(encoding="utf-8")
    assert '"request_id":"abc"' in written


# ---------------------------------------------------------------------------
# The guard: a reintroduced leak is caught
# ---------------------------------------------------------------------------

def test_guard_blocks_opening_the_production_chroma_store(
    expected_isolation_violations,
):
    with pytest.raises(StoreIsolationViolation) as excinfo:
        chromadb.PersistentClient(path=REAL_CHROMA_DIR)

    assert "PRODUCTION Chroma store" in str(excinfo.value)
    assert len(expected_isolation_violations) == 1
    assert "PRODUCTION Chroma store" in expected_isolation_violations.recorded[0]


def test_guard_blocks_writing_the_production_chat_debug_trace(
    expected_isolation_violations,
):
    real = Path(REAL_CHAT_DEBUG_TRACE_PATH)
    size_before = real.stat().st_size if real.exists() else None

    with pytest.raises(StoreIsolationViolation):
        chat_debug_trace.write_chat_debug_trace(
            {"request_id": "should-never-land"}, path=REAL_CHAT_DEBUG_TRACE_PATH
        )

    size_after = real.stat().st_size if real.exists() else None
    assert size_after == size_before, "guard let a write through to production"
    assert len(expected_isolation_violations) == 1


def test_guard_violation_survives_a_broad_except_clause(
    expected_isolation_violations,
):
    """`retrieve`, `index_artifact_file` and the routes trace call all wrap
    store access in `except Exception`. A guard those swallow is no guard."""
    with pytest.raises(StoreIsolationViolation):
        try:
            chromadb.PersistentClient(path=REAL_CHROMA_DIR)
        except Exception:  # noqa: BLE001 - deliberately mimics runtime paths
            pytest.fail("StoreIsolationViolation was swallowed by except Exception")

    assert len(expected_isolation_violations) == 1


def test_guard_allows_isolated_paths(tmp_path):
    client = chromadb.PersistentClient(path=str(tmp_path / "fine"))
    assert client is not None
    assert os.path.exists(tmp_path / "fine")
