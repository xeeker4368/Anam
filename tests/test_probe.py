"""Tests for the Behavioral Probe Harness v1 (scripts/probe.py).

Two required proofs plus supporting checks:
- Zero-write: a full probe pass leaves every entity store unchanged (seeded AND
  empty-store, the day-0 path).
- Shared-builder: the probe routes prompt assembly through the real
  build_system_prompt_with_debug and duplicates no assembly / imports no writers.

Runs fully offline: the query embedding and the Ollama chat call are mocked, so
retrieval still executes against a temp Chroma/FTS store without a live model.
"""

import ast
import importlib
import inspect
import json

import pytest
from unittest.mock import patch

FAKE_VEC = [0.01] * 768


@pytest.fixture()
def probe_env(tmp_path):
    """Temp entity store with the read-path chain reloaded to point at it, and
    restored to real config on teardown so later tests aren't polluted."""
    data = tmp_path / "data"
    patches = [
        patch("tir.config.DATA_DIR", data),
        patch("tir.config.ARCHIVE_DB", data / "archive.db"),
        patch("tir.config.WORKING_DB", data / "working.db"),
        patch("tir.config.CHROMA_DIR", str(data / "chroma")),
        patch("tir.config.WORKSPACE_DIR", tmp_path / "workspace"),
    ]
    for p in patches:
        p.start()

    import tir.memory.db as db_mod
    import tir.memory.chroma as chroma_mod
    import tir.memory.retrieval as retrieval_mod
    import scripts.probe as probe_mod

    # Reload in dependency order so each rebinds to the temp-config modules.
    chain = (db_mod, chroma_mod, retrieval_mod, probe_mod)
    for m in chain:
        importlib.reload(m)

    (tmp_path / "workspace").mkdir(parents=True, exist_ok=True)
    db_mod.init_databases()
    chroma_mod.reset_client()

    try:
        yield {
            "db": db_mod,
            "chroma": chroma_mod,
            "probe": probe_mod,
            "workspace": tmp_path / "workspace",
            "out_dir": tmp_path / "probe_out",
            "tmp": tmp_path,
        }
    finally:
        for p in reversed(patches):
            p.stop()
        # Rebind the chain to the real (restored) config so we leave no stale state.
        for m in chain:
            importlib.reload(m)
        chroma_mod.reset_client()


def _snapshot(db_mod, chroma_mod, workspace):
    counts = {}
    with db_mod.get_connection() as conn:
        for schema in ("main", "archive"):
            names = [
                r[0]
                for r in conn.execute(
                    f"SELECT name FROM {schema}.sqlite_master WHERE type='table'"
                )
            ]
            for t in names:
                counts[f"{schema}.{t}"] = conn.execute(
                    f"SELECT COUNT(*) FROM {schema}.{t}"
                ).fetchone()[0]
    try:
        chroma_count = chroma_mod._get_collection().count()
    except Exception:
        chroma_count = 0
    files = sorted(
        str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file()
    )
    return {"counts": counts, "chroma": chroma_count, "files": files}


def _write_questions(tmp, body):
    qfile = tmp / "q.md"
    qfile.write_text(body, encoding="utf-8")
    return qfile


# ---------------------------------------------------------------------------
# Zero-write proofs
# ---------------------------------------------------------------------------

def test_seeded_probe_pass_writes_nothing_to_stores(probe_env):
    db_mod, chroma_mod, probe_mod = probe_env["db"], probe_env["chroma"], probe_env["probe"]

    # Seed a user + conversation + one indexed chunk (so the collection exists and
    # retrieval returns something). The TEST may seed via writers; the PROBE never does.
    user = db_mod.create_user("Lyle")
    conv = db_mod.start_conversation(user["id"])
    db_mod.save_message(conv, user["id"], "user", "we talked about hiking")
    db_mod.save_message(conv, user["id"], "assistant", "yes, hiking")
    with patch.object(chroma_mod, "embed_text", return_value=list(FAKE_VEC)):
        chroma_mod.upsert_chunk(
            "seed_chunk_0",
            "A memory about hiking trips.",
            {
                "conversation_id": conv,
                "chunk_index": 0,
                "source_type": "conversation",
                "source_trust": "firsthand",
                "user_id": user["id"],
                "created_at": "2026-06-01T00:00:00+00:00",
            },
        )
    db_mod.upsert_chunk_fts(
        "seed_chunk_0", "A memory about hiking trips.", conv, user["id"],
        "conversation", "firsthand", "2026-06-01T00:00:00+00:00",
    )

    qfile = _write_questions(probe_env["tmp"], "# Q\n\n## id-a\nWho are you?\n\n## id-b\nWhat do you value?\n")

    before = _snapshot(db_mod, chroma_mod, probe_env["workspace"])
    with patch.object(chroma_mod, "embed_text", return_value=list(FAKE_VEC)), \
         patch.object(probe_mod, "chat_completion_text", return_value="canned answer"):
        rc = probe_mod.main([
            "--questions", str(qfile),
            "--out-dir", str(probe_env["out_dir"]),
            "--samples", "2",
        ])
    after = _snapshot(db_mod, chroma_mod, probe_env["workspace"])

    assert rc == 0
    assert before == after  # zero writes to any entity store

    out_files = list(probe_env["out_dir"].glob("*.json"))
    assert len(out_files) == 1  # the only write is the out-of-store results file
    doc = json.loads(out_files[0].read_text())
    assert doc["run"]["framing"] == "autonomous"
    assert len(doc["results"]) == 4  # 2 questions x 2 samples
    ids_seen = {cid for r in doc["results"] for cid in (r["retrieved_chunk_ids"] or [])}
    assert "seed_chunk_0" in ids_seen  # Addition 1: chunk IDs recorded
    assert "model_options" in doc["run"]  # Addition 2: effective options recorded
    assert doc["run"]["ollama_host"]
    # Budgeting matches the live path and is recorded per sample.
    budget = doc["results"][0]["retrieved_budget"]
    assert budget["max_chars"] > 0
    assert budget["used_chars"] > 0
    assert budget["input_chunks"] >= 1


def test_empty_store_probe_pass_completes_and_writes_nothing(probe_env):
    # Addition 3 — the day-0 path: empty store, zero chunks. Must complete cleanly.
    db_mod, chroma_mod, probe_mod = probe_env["db"], probe_env["chroma"], probe_env["probe"]
    qfile = _write_questions(probe_env["tmp"], "## only\nWho are you?\n")

    before = _snapshot(db_mod, chroma_mod, probe_env["workspace"])
    with patch.object(chroma_mod, "embed_text", return_value=list(FAKE_VEC)), \
         patch.object(probe_mod, "chat_completion_text", return_value="canned"):
        rc = probe_mod.main([
            "--questions", str(qfile),
            "--out-dir", str(probe_env["out_dir"]),
            "--samples", "3",
        ])
    after = _snapshot(db_mod, chroma_mod, probe_env["workspace"])

    assert rc == 0
    assert before == after
    doc = json.loads(next(probe_env["out_dir"].glob("*.json")).read_text())
    assert len(doc["results"]) == 3
    for r in doc["results"]:
        assert r["error"] is None
        assert r["retrieved_chunk_ids"] == []
        assert r["retrieved_context_chars"] == 0
        assert r["answer"] == "canned"
        # Budgeting still applied (and recorded) on the empty path.
        assert r["retrieved_budget"]["used_chars"] == 0
        assert r["retrieved_budget"]["input_chunks"] == 0
        assert r["retrieved_budget"]["max_chars"] > 0


# ---------------------------------------------------------------------------
# Shared-builder + no duplicated assembly / no writer imports
# ---------------------------------------------------------------------------

def test_probe_uses_shared_builder_with_autonomous_framing(probe_env):
    probe_mod, chroma_mod = probe_env["probe"], probe_env["chroma"]
    qfile = _write_questions(probe_env["tmp"], "## only\nWho are you?\n")

    real_builder = probe_mod.build_system_prompt_with_debug
    with patch.object(probe_mod, "build_system_prompt_with_debug", wraps=real_builder) as spy, \
         patch.object(chroma_mod, "embed_text", return_value=list(FAKE_VEC)), \
         patch.object(probe_mod, "chat_completion_text", return_value="x"):
        probe_mod.main([
            "--questions", str(qfile),
            "--out-dir", str(probe_env["out_dir"]),
            "--samples", "1",
        ])

    assert spy.called
    kwargs = spy.call_args.kwargs
    assert kwargs["autonomous"] is True
    assert kwargs["user_message"] == "Who are you?"
    assert kwargs["tool_descriptions"] is None


def test_probe_source_has_no_duplicated_assembly_or_writer_imports():
    import scripts.probe as probe
    src = inspect.getsource(probe)

    for lit in [
        "Retrieved context follows",
        "[Current Situation]",
        "[Operational Guidance]",
        "[Artifact source:",
    ]:
        assert lit not in src, f"probe appears to duplicate prompt assembly: {lit!r}"

    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {
        "tir.memory.chunking",
        "tir.api.routes",
        "tir.engine.agent_loop",
        "tir.tools.registry",
        "tir.memory.db",
        "tir.memory.chroma",
    }
    assert imported.isdisjoint(forbidden), f"probe imports forbidden modules: {imported & forbidden}"


# ---------------------------------------------------------------------------
# Question parser
# ---------------------------------------------------------------------------

def test_parse_questions_and_validation():
    import scripts.probe as probe

    qs = probe.parse_questions("# title\n\n## a\nQ one\nmore\n\n## b\nQ two\n")
    assert [q["id"] for q in qs] == ["a", "b"]
    assert qs[0]["text"] == "Q one\nmore"
    assert qs[1]["text"] == "Q two"

    with pytest.raises(ValueError):
        probe.parse_questions("# just a title, no questions")
    with pytest.raises(ValueError):
        probe.parse_questions("## a\nQ\n\n## a\ndup\n")  # duplicate id
    with pytest.raises(ValueError):
        probe.parse_questions("## a\n\n## b\nok\n")  # empty text for 'a'
