import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from tir.research import manual


RESEARCH_BODY = """## Purpose

Clarify the implementation direction.

## Summary

This is a provisional model-only draft.

## Findings

- A narrow CLI path is enough for v1.

## Uncertainty

- No external sources were checked.

## Sources

- Model-only draft; no external sources collected.

## Open Questions

- Should registration be added later?

## Possible Follow-Ups

- Design artifact registration.

## Suggested Review Items

- None.

## Working Notes

- Keep this separate from guidance.
"""

CONTINUATION_BODY = """## Purpose

Continue the earlier provisional note.

## Prior Research Considered

- Prior note said the CLI path was enough.

## What Changed / What Is Being Extended

- This extends the registration path.

## Updated Findings

- Continuation should preserve lineage.

## Superseded Or Weakened Prior Claims

- No prior claims are superseded.

## Remaining Uncertainty

- Open-loop creation remains deferred.

## Sources

- Model-only draft plus prior provisional research note; no external sources collected.

## New Open Questions

- Should continuation support search later?

## Possible Follow-Ups

- Implement artifact continuation.

## Suggested Review Items

- None.

## Working Notes

- Keep prior research provisional.
"""


def _init_research_db(tmp_path, monkeypatch):
    import tir.artifacts.service as artifacts_mod
    import tir.memory.db as db_mod

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    db_mod.init_databases()
    return db_mod, artifacts_mod


def test_manual_research_prompt_allows_no_useful_findings():
    messages = manual.build_manual_research_messages(
        title="Quiet Research",
        question="Is there anything useful here?",
        scope="Check whether the prompt forces findings.",
    )
    prompt_text = "\n\n".join(message["content"] for message in messages)

    assert "no useful findings" in prompt_text
    assert "no open questions" in prompt_text
    assert "no suggested follow-ups" in prompt_text
    assert "no suggested review items" in prompt_text


def test_manual_research_continuation_prompt_allows_no_new_findings():
    messages = manual.build_manual_research_continuation_messages(
        title="Quiet Continuation",
        question="Did anything change?",
        scope="Continue prior provisional research.",
        continuation={
            "continued_from": "prior note",
            "registered": False,
            "content": "# Research Note — Prior\n\n## Findings\n\n- Nothing firm.\n",
        },
    )
    prompt_text = "\n\n".join(message["content"] for message in messages)

    assert "no useful updated findings" in prompt_text
    assert "no new open questions" in prompt_text
    assert "no suggested follow-ups" in prompt_text
    assert "no suggested review items" in prompt_text


def _create_research_artifact(
    artifacts_mod,
    tmp_path,
    *,
    artifact_id="prior-research",
    path="research/2026-05-09-prior.md",
    status="active",
    metadata=None,
):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Research Note — Prior\n\n## Findings\n\n- Prior provisional finding.\n",
        encoding="utf-8",
    )
    return artifacts_mod.create_artifact(
        artifact_id=artifact_id,
        artifact_type="research_note",
        title="Research Note — Prior",
        path=path,
        status=status,
        source="manual_research",
        metadata=metadata
        or {
            "source_type": "research",
            "source_role": "research_reference",
            "origin": "manual_research",
            "research_title": "Prior",
            "research_date": "2026-05-09",
            "research_version": "manual_research_v1",
            "provisional": True,
        },
        workspace_root=tmp_path,
    )


def test_dry_run_does_not_create_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)

    result = manual.run_manual_research(
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
        write=False,
        workspace_root=tmp_path,
    )

    assert result["mode"] == "dry-run"
    assert result["relative_path"].startswith("research/2026-05-10-")
    assert result["document"].startswith("# Research Note")
    assert not (tmp_path / "research").exists()


def test_write_creates_one_markdown_file_in_workspace_research(tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)

    result = manual.run_manual_research(
        title="Manual Research Runtime",
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
        write=True,
        workspace_root=tmp_path,
    )

    research_files = list((tmp_path / "research").glob("*.md"))
    assert len(research_files) == 1
    assert research_files[0].name == "2026-05-10-manual-research-runtime.md"
    assert result["write_result"]["path"] == "research/2026-05-10-manual-research-runtime.md"
    content = research_files[0].read_text(encoding="utf-8")
    assert "- Research mode: manual_research_v1" in content
    assert "- Provisional: true" in content


def test_write_without_register_artifact_does_not_register_or_index(tmp_path, monkeypatch):
    import tir.artifacts.service as artifacts_mod
    import tir.memory.db as db_mod

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    db_mod.init_databases()
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)

    result = manual.run_manual_research(
        title="Manual Research Runtime",
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
        write=True,
        workspace_root=tmp_path,
    )

    assert "artifact_result" not in result
    assert artifacts_mod.list_artifacts(workspace_root=tmp_path) == []
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT * FROM main.chunks_fts").fetchall()
    assert rows == []


def test_write_register_artifact_creates_research_artifact_and_index(tmp_path, monkeypatch):
    import tir.artifacts.service as artifacts_mod
    import tir.memory.db as db_mod

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")
    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    db_mod.init_databases()
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    result = manual.run_manual_research(
        title="Manual Research Runtime",
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
        write=True,
        register_artifact=True,
        workspace_root=tmp_path,
    )

    artifact_result = result["artifact_result"]
    artifact = artifact_result["artifact"]
    assert artifact["artifact_type"] == "research_note"
    assert artifact["title"] == "Research Note — Manual Research Runtime"
    assert artifact["path"] == "research/2026-05-10-manual-research-runtime.md"
    assert artifact["status"] == "active"
    assert artifact["source"] == "manual_research"
    assert artifact["metadata"]["source_type"] == "research"
    assert artifact["metadata"]["source_role"] == "research_reference"
    assert artifact["metadata"]["origin"] == "manual_research"
    assert artifact["metadata"]["research_question"] == (
        "What should the manual research runtime do?"
    )
    assert artifact["metadata"]["research_title"] == "Manual Research Runtime"
    assert artifact["metadata"]["research_date"] == "2026-05-10"
    assert artifact["metadata"]["created_by"] == "admin_cli"
    assert artifact["metadata"]["research_version"] == "manual_research_v1"
    assert artifact["metadata"]["provisional"] is True
    assert artifact_result["indexing"]["status"] == "indexed"
    assert artifact_result["indexing"]["chunks_written"] == 1

    listed = artifacts_mod.list_artifacts(path=artifact["path"], workspace_root=tmp_path)
    assert [item["artifact_id"] for item in listed] == [artifact["artifact_id"]]
    with db_mod.get_connection() as conn:
        rows = conn.execute(
            "SELECT chunk_id, text, source_type FROM main.chunks_fts ORDER BY chunk_id"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["source_type"] == "research"
    assert "Manual research note: Research Note — Manual Research Runtime" in rows[0]["text"]


def _write_generated_research_file(tmp_path, monkeypatch, *, body=RESEARCH_BODY):
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: body)
    result = manual.generate_manual_research_note(
        title="Manual Research Runtime",
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
    )
    target = tmp_path / result["relative_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result["document"], encoding="utf-8")
    return result


def test_existing_research_file_without_artifact_registers_and_indexes(tmp_path, monkeypatch):
    db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    result = _write_generated_research_file(tmp_path, monkeypatch)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    recovery = manual.register_existing_research_note(
        result["relative_path"],
        write=True,
        workspace_root=tmp_path,
    )

    assert recovery["path"] == result["relative_path"]
    assert recovery["artifact_exists"] is True
    assert recovery["artifact_id"]
    assert recovery["chunks_status"] == "complete"
    assert recovery["action_needed"] == "register_and_index"
    assert recovery["action_taken"] == "registered"
    assert recovery["indexing_status"] == "indexed"
    assert recovery["open_loop_metadata_updated"] is False

    artifacts = artifacts_mod.list_artifacts(path=result["relative_path"], workspace_root=tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0]["metadata"]["recovered_existing_note"] is True
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT chunk_id FROM main.chunks_fts").fetchall()
    assert len(rows) == 1


def test_existing_artifact_with_missing_chunks_is_indexed(tmp_path, monkeypatch):
    db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    result = _write_generated_research_file(tmp_path, monkeypatch)
    metadata = manual.manual_research_metadata(result)
    artifact = artifacts_mod.create_artifact(
        artifact_type="research_note",
        title="Research Note — Manual Research Runtime",
        path=result["relative_path"],
        status="active",
        source="manual_research",
        metadata=metadata,
        workspace_root=tmp_path,
    )
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    recovery = manual.register_existing_research_note(
        result["relative_path"],
        write=True,
        workspace_root=tmp_path,
    )

    assert recovery["artifact_exists"] is True
    assert recovery["artifact_id"] == artifact["artifact_id"]
    assert recovery["action_needed"] == "index"
    assert recovery["action_taken"] == "indexed"
    assert recovery["indexing_status"] == "indexed"
    assert recovery["chunks_status"] == "complete"
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT chunk_id FROM main.chunks_fts").fetchall()
    assert len(rows) == 1


def test_existing_artifact_with_complete_chunks_is_noop_and_idempotent(tmp_path, monkeypatch):
    db_mod, _artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    result = _write_generated_research_file(tmp_path, monkeypatch)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    first = manual.register_manual_research_artifact(result, workspace_root=tmp_path)
    second = manual.register_manual_research_artifact(result, workspace_root=tmp_path)
    recovery = manual.register_existing_research_note(
        result["relative_path"],
        write=True,
        workspace_root=tmp_path,
    )

    assert first["indexing"]["status"] == "indexed"
    assert second["indexing"]["status"] == "already_indexed"
    assert second["action_taken"] == "noop"
    assert recovery["action_needed"] == "none"
    assert recovery["action_taken"] == "noop"
    assert recovery["indexing_status"] == "already_indexed"
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT chunk_id FROM main.chunks_fts").fetchall()
    assert len(rows) == 1


def test_existing_artifact_with_partial_chunks_is_repaired(tmp_path, monkeypatch):
    db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    result = _write_generated_research_file(tmp_path, monkeypatch)
    target = tmp_path / result["relative_path"]
    target.write_text(result["document"] + "\n\n" + ("extra research context " * 400), encoding="utf-8")
    metadata = manual.manual_research_metadata(result)
    artifact = artifacts_mod.create_artifact(
        artifact_type="research_note",
        title="Research Note — Manual Research Runtime",
        path=result["relative_path"],
        status="active",
        source="manual_research",
        metadata=metadata,
        workspace_root=tmp_path,
    )
    from tir.memory.research_indexing import research_chunk_prefix
    from tir.memory.db import upsert_chunk_fts

    upsert_chunk_fts(
        chunk_id=f"{research_chunk_prefix(result['relative_path'])}_chunk_99",
        text="stale chunk",
        conversation_id=None,
        user_id=None,
        source_type="research",
        source_trust="thirdhand",
        created_at="2026-05-10T12:00:00+00:00",
    )
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)
    monkeypatch.setattr("tir.memory.research_indexing.delete_chunks_by_prefix", lambda prefix: None)

    recovery = manual.register_existing_research_note(
        result["relative_path"],
        write=True,
        workspace_root=tmp_path,
    )

    assert recovery["artifact_id"] == artifact["artifact_id"]
    assert recovery["action_needed"] == "reindex"
    assert recovery["action_taken"] == "reindexed"
    assert recovery["indexing_status"] == "indexed"
    assert recovery["chunks_status"] == "complete"
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT chunk_id, text FROM main.chunks_fts ORDER BY chunk_id").fetchall()
    assert len(rows) == recovery["expected_chunks"]
    assert all("stale chunk" not in row["text"] for row in rows)


def test_recovery_dry_run_reports_action_without_mutation(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    result = _write_generated_research_file(tmp_path, monkeypatch)

    recovery = manual.register_existing_research_note(
        result["relative_path"],
        write=False,
        workspace_root=tmp_path,
    )

    assert recovery["file_exists"] is True
    assert recovery["artifact_exists"] is False
    assert recovery["action_needed"] == "register_and_index"
    assert recovery["action_taken"] == "dry_run"
    assert artifacts_mod.list_artifacts(workspace_root=tmp_path) == []


def test_recovery_rejects_missing_file(tmp_path, monkeypatch):
    _init_research_db(tmp_path, monkeypatch)

    with pytest.raises(manual.ManualResearchError, match="file not found"):
        manual.register_existing_research_note(
            "research/missing.md",
            write=True,
            workspace_root=tmp_path,
        )


def test_recovery_rejects_non_research_markdown(tmp_path, monkeypatch):
    _init_research_db(tmp_path, monkeypatch)
    target = tmp_path / "research" / "not-research.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Notes\n\nNot a research note.\n", encoding="utf-8")

    with pytest.raises(manual.ManualResearchError, match="not a Project Anam research note"):
        manual.register_existing_research_note(
            "research/not-research.md",
            write=True,
            workspace_root=tmp_path,
        )


def test_continue_artifact_loads_registered_research_artifact_and_prior_file(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path)
    captured = {}

    def fake_completion(messages, **kwargs):
        captured["messages"] = messages
        return CONTINUATION_BODY

    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", fake_completion)

    result = manual.run_manual_research(
        title="Prior Follow Up",
        question="What changed?",
        scope="Continue prior provisional research.",
        continue_artifact=artifact["artifact_id"],
        workspace_root=tmp_path,
    )

    assert result["mode"] == "dry-run"
    assert result["research_version"] == "manual_research_continuation_v1"
    assert result["continuation"]["artifact_id"] == artifact["artifact_id"]
    assert result["continuation"]["path"] == artifact["path"]
    assert not (tmp_path / "research" / "2026-05-10-prior-follow-up.md").exists()
    assert "[Prior provisional research note]" in captured["messages"][1]["content"]
    assert "not truth, project decision, behavioral guidance, or self-understanding" in (
        captured["messages"][1]["content"]
    )
    assert "Prior provisional finding." in captured["messages"][1]["content"]
    assert "- Research mode: manual_research_continuation_v1" in result["document"]
    assert "- Continued from: Prior / research/2026-05-09-prior.md / artifact prior-research / 2026-05-09" in result["document"]
    assert "## Prior Research Considered" in result["document"]
    assert "## Superseded Or Weakened Prior Claims" in result["document"]


def test_continue_artifact_rejects_non_research_artifact(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    path = "research/not-research.md"
    (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / path).write_text("not research\n", encoding="utf-8")
    artifact = artifacts_mod.create_artifact(
        artifact_id="artifact-1",
        artifact_type="generic",
        title="Generic",
        path=path,
        status="active",
        source="manual_research",
        metadata={},
        workspace_root=tmp_path,
    )

    with pytest.raises(manual.ManualResearchError, match="Artifact is not a research note"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact=artifact["artifact_id"],
            workspace_root=tmp_path,
        )


def test_continue_artifact_rejects_missing_artifact(tmp_path, monkeypatch):
    _init_research_db(tmp_path, monkeypatch)

    with pytest.raises(manual.ManualResearchError, match="Research artifact not found: missing"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact="missing",
            workspace_root=tmp_path,
        )


def test_continue_artifact_rejects_inactive_artifact(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path, status="archived")

    with pytest.raises(manual.ManualResearchError, match="Research artifact is not active"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact=artifact["artifact_id"],
            workspace_root=tmp_path,
        )


def test_continue_artifact_rejects_prior_artifact_with_missing_file(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path)
    (tmp_path / artifact["path"]).unlink()

    with pytest.raises(manual.ManualResearchError, match="Prior research note file not found"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact=artifact["artifact_id"],
            workspace_root=tmp_path,
        )


def test_continue_artifact_rejects_missing_required_metadata(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(
        artifacts_mod,
        tmp_path,
        metadata={
            "source_type": "research",
            "origin": "manual_research",
            "research_title": "Prior",
            "research_date": "2026-05-09",
            "provisional": True,
        },
    )

    with pytest.raises(
        manual.ManualResearchError,
        match="Research artifact is missing required metadata: source_role",
    ):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact=artifact["artifact_id"],
            workspace_root=tmp_path,
        )


def test_continue_file_accepts_workspace_research_markdown_file(tmp_path, monkeypatch):
    _init_research_db(tmp_path, monkeypatch)
    prior = tmp_path / "research" / "2026-05-09-prior.md"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_text("# Research Note — Prior\n\nPrior file-only note.\n", encoding="utf-8")
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: CONTINUATION_BODY)

    result = manual.run_manual_research(
        title="File Continuation",
        question="What changed?",
        scope="Continue.",
        continue_file="workspace/research/2026-05-09-prior.md",
        workspace_root=tmp_path,
    )

    assert result["continuation"]["registered"] is False
    assert result["continuation"]["path"] == "research/2026-05-09-prior.md"
    assert "file-only/unregistered" in result["document"]


def test_continue_file_rejects_path_traversal(tmp_path):
    with pytest.raises(manual.ManualResearchError, match="under workspace/research"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_file="research/../secrets.md",
            workspace_root=tmp_path,
        )


def test_continue_file_rejects_non_markdown_files(tmp_path):
    with pytest.raises(manual.ManualResearchError, match="Markdown file"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_file="research/prior.txt",
            workspace_root=tmp_path,
        )


def test_continue_file_rejects_files_outside_research(tmp_path):
    with pytest.raises(manual.ManualResearchError, match="under workspace/research"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_file="journals/2026-05-09.md",
            workspace_root=tmp_path,
        )


def test_continue_file_uses_registered_artifact_metadata_when_path_matches(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path)
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: CONTINUATION_BODY)

    result = manual.run_manual_research(
        title="Registered File Continuation",
        question="What changed?",
        scope="Continue.",
        continue_file=artifact["path"],
        workspace_root=tmp_path,
    )

    assert result["continuation"]["registered"] is True
    assert result["continuation"]["artifact_id"] == artifact["artifact_id"]
    assert result["continuation"]["title"] == "Prior"


def test_continue_artifact_write_creates_new_note_and_preserves_prior_note(tmp_path, monkeypatch):
    _db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path)
    prior_path = tmp_path / artifact["path"]
    prior_content = prior_path.read_text(encoding="utf-8")
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: CONTINUATION_BODY)

    result = manual.run_manual_research(
        title="Prior Follow Up",
        question="What changed?",
        scope="Continue.",
        continue_artifact=artifact["artifact_id"],
        write=True,
        workspace_root=tmp_path,
    )

    assert result["write_result"]["path"] == "research/2026-05-10-prior-follow-up.md"
    assert (tmp_path / "research" / "2026-05-10-prior-follow-up.md").exists()
    assert prior_path.read_text(encoding="utf-8") == prior_content
    assert "artifact_result" not in result


def test_continue_artifact_registers_and_indexes_new_continuation_note(tmp_path, monkeypatch):
    db_mod, artifacts_mod = _init_research_db(tmp_path, monkeypatch)
    artifact = _create_research_artifact(artifacts_mod, tmp_path)
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: CONTINUATION_BODY)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    result = manual.run_manual_research(
        title="Prior Follow Up",
        question="What changed?",
        scope="Continue.",
        continue_artifact=artifact["artifact_id"],
        write=True,
        register_artifact=True,
        workspace_root=tmp_path,
    )

    new_artifact = result["artifact_result"]["artifact"]
    metadata = new_artifact["metadata"]
    assert new_artifact["artifact_type"] == "research_note"
    assert new_artifact["path"] == "research/2026-05-10-prior-follow-up.md"
    assert metadata["research_version"] == "manual_research_continuation_v1"
    assert metadata["continuation_mode"] == "manual"
    assert metadata["continuation_of_artifact_id"] == artifact["artifact_id"]
    assert metadata["continuation_of_path"] == artifact["path"]
    assert metadata["continuation_of_title"] == "Prior"
    assert metadata["continuation_of_research_date"] == "2026-05-09"
    assert metadata["continuation_source_registered"] is True
    assert result["artifact_result"]["indexing"]["chunks_written"] == 1

    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT * FROM main.open_loops").fetchall()
        review_rows = conn.execute("SELECT * FROM main.review_items").fetchall()
    assert rows == []
    assert review_rows == []


def test_file_only_continuation_metadata_marks_source_unregistered(tmp_path, monkeypatch):
    _init_research_db(tmp_path, monkeypatch)
    prior = tmp_path / "research" / "2026-05-09-prior.md"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_text("# Research Note — Prior\n\nPrior file-only note.\n", encoding="utf-8")
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: CONTINUATION_BODY)

    result = manual.run_manual_research(
        title="File Continuation",
        question="What changed?",
        scope="Continue.",
        continue_file="research/2026-05-09-prior.md",
        workspace_root=tmp_path,
    )

    metadata = manual.manual_research_metadata(result)
    assert "continuation_of_artifact_id" not in metadata
    assert metadata["continuation_of_path"] == "research/2026-05-09-prior.md"
    assert metadata["continuation_source_registered"] is False
    assert metadata["research_version"] == "manual_research_continuation_v1"


def test_continue_artifact_and_continue_file_are_mutually_exclusive():
    with pytest.raises(manual.ManualResearchError, match="mutually exclusive"):
        manual.run_manual_research(
            question="What changed?",
            scope="Continue.",
            continue_artifact="artifact-1",
            continue_file="research/prior.md",
        )


def test_register_artifact_requires_write():
    with pytest.raises(manual.ManualResearchError, match="requires --write"):
        manual.run_manual_research(
            question="What should the manual research runtime do?",
            scope="CLI-only v1.",
            register_artifact=True,
        )


def test_output_includes_required_provisional_metadata(monkeypatch):
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)

    result = manual.run_manual_research(
        title="Research Note",
        question="What is the question?",
        scope="Model-only.",
    )

    document = result["document"]
    assert document.startswith("# Research Note — Research Note")
    assert "- Question: What is the question?" in document
    assert "- Scope: Model-only." in document
    assert "- Created: 2026-05-10T12:00:00+00:00" in document
    assert "- Sources used: Model-only draft; no external sources collected." in document
    for heading in manual.REQUIRED_BODY_HEADINGS:
        assert heading in document


def test_slug_generation_is_filesystem_safe():
    assert manual.slugify_title(" Avatar Box: Pi/Screen? v1 ") == "avatar-box-pi-screen-v1"
    assert manual.slugify_title("$$$") == "research-note"


def test_missing_required_question_fails_cleanly(capsys):
    import tir.admin as admin_mod

    with patch("sys.argv", ["tir.admin", "research-run", "--scope", "CLI-only"]):
        with pytest.raises(SystemExit) as exc:
            admin_mod.main()

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "the following arguments are required: --question" in captured.err


def test_existing_research_file_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "_now", lambda: "2026-05-10T12:00:00+00:00")
    monkeypatch.setattr(manual, "chat_completion_text", lambda *args, **kwargs: RESEARCH_BODY)
    existing = tmp_path / "research" / "2026-05-10-manual-research-runtime.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing\n", encoding="utf-8")

    result = manual.run_manual_research(
        title="Manual Research Runtime",
        question="What should the manual research runtime do?",
        scope="CLI-only v1.",
        write=False,
        workspace_root=tmp_path,
    )
    with pytest.raises(manual.ManualResearchError):
        manual.write_manual_research_note(result, workspace_root=tmp_path)

    assert existing.read_text(encoding="utf-8") == "existing\n"
