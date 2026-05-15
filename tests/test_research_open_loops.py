import importlib
from unittest.mock import patch

import pytest

from tir.research import open_loops as research_open_loops
from tir.workspace.service import ensure_workspace


RESEARCH_NOTE_WITH_LOOPS = """# Research Note — Prior

- Research mode: manual_research_v1
- Provisional: true

## Summary

This note has unresolved research questions.

## Open Questions

- Should the local model use a lower temperature?
- [ ] How should research loops reset each day?
- None

## Possible Follow-Ups

1. Compare continuation notes against prior research.
2. No suggested follow-ups

## Suggested Review Items

- This should not become an open loop.

## Working Notes

- Keep this provisional.
"""


RESEARCH_NOTE_NO_LOOPS = """# Research Note — Quiet

## Open Questions

- None

## Possible Follow-Ups

No suggested follow-ups.

## Suggested Review Items

- Admin may review this someday.
"""


@pytest.fixture()
def research_loop_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")

    import tir.artifacts.service as artifacts_mod
    import tir.memory.db as db_mod
    import tir.open_loops.service as open_loop_mod
    import tir.review.service as review_mod

    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    importlib.reload(open_loop_mod)
    importlib.reload(review_mod)
    importlib.reload(research_open_loops)
    db_mod.init_databases()
    return {
        "workspace_root": workspace_root,
        "artifacts": artifacts_mod,
        "db": db_mod,
        "open_loops": open_loop_mod,
        "review": review_mod,
    }


def _create_research_artifact(
    env,
    *,
    artifact_id="research-artifact",
    artifact_type="research_note",
    status="active",
    path="research/prior.md",
    content=RESEARCH_NOTE_WITH_LOOPS,
    metadata=None,
):
    target = env["workspace_root"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return env["artifacts"].create_artifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
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
            "research_date": "2026-05-14",
            "research_version": "manual_research_v1",
            "provisional": True,
        },
        workspace_root=env["workspace_root"],
    )


def test_preview_from_registered_research_artifact_returns_candidates_and_writes_nothing(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)

    result = research_open_loops.preview_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )

    assert result["candidate_count"] == 3
    assert result["skipped_duplicate_count"] == 0
    titles = [candidate["title"] for candidate in result["candidates"]]
    assert "Should the local model use a lower temperature?" in titles
    assert "How should research loops reset each day?" in titles
    assert "Compare continuation notes against prior research." in titles
    assert "This should not become an open loop." not in titles
    assert research_loop_env["open_loops"].list_open_loops() == []


def test_create_from_registered_research_artifact_creates_open_loop_records(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)

    result = research_open_loops.create_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )

    assert result["created_count"] == 3
    loops = research_loop_env["open_loops"].list_open_loops(
        related_artifact_id=artifact["artifact_id"],
        limit=10,
    )
    assert len(loops) == 3
    loop = next(item for item in loops if item["title"] == "Should the local model use a lower temperature?")
    assert loop["status"] == "open"
    assert loop["loop_type"] == "unresolved_question"
    assert loop["priority"] == "normal"
    assert loop["source"] == "manual_research"
    assert loop["next_action"] == "Investigate: Should the local model use a lower temperature?"
    metadata = loop["metadata"]
    assert metadata["generation_method"] == "research_open_loop_v1"
    assert metadata["source_type"] == "research"
    assert metadata["source_artifact_id"] == artifact["artifact_id"]
    assert metadata["source_research_version"] == "manual_research_v1"
    assert metadata["source_research_title"] == "Prior"
    assert metadata["source_research_date"] == "2026-05-14"
    assert metadata["source_research_path"] == "research/prior.md"
    assert metadata["source_section"] == "Open Questions"
    assert metadata["provisional"] is True
    assert metadata["daily_iteration_limit"] == 1
    assert metadata["daily_iteration_count"] == 0
    assert metadata["daily_iteration_local_date"] is None
    assert metadata["global_daily_cap_class"] == "research"
    assert metadata["last_researched_at"] is None
    assert metadata["ready_for_synthesis"] is False
    assert metadata["diminishing_returns_note"] is None


def test_create_is_idempotent_for_same_artifact(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)

    first = research_open_loops.create_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )
    second = research_open_loops.create_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )

    assert first["created_count"] == 3
    assert second["created_count"] == 0
    assert second["skipped_duplicate_count"] == 3
    assert len(research_loop_env["open_loops"].list_open_loops(limit=10)) == 3


def test_duplicate_prevention_uses_same_artifact_and_question(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)
    research_loop_env["open_loops"].create_open_loop(
        title="Should the local model use a lower temperature?",
        related_artifact_id=artifact["artifact_id"],
        status="open",
        loop_type="unresolved_question",
        metadata={
            "generation_method": "research_open_loop_v1",
            "question": "Should the local model use a lower temperature?",
        },
    )

    preview = research_open_loops.preview_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )

    assert preview["candidate_count"] == 3
    assert preview["skipped_duplicate_count"] == 1
    duplicate = next(candidate for candidate in preview["candidates"] if candidate["skipped_duplicate"])
    assert duplicate["title"] == "Should the local model use a lower temperature?"


def test_non_research_artifact_is_rejected(research_loop_env):
    artifact = _create_research_artifact(
        research_loop_env,
        artifact_type="uploaded_file",
    )

    with pytest.raises(research_open_loops.ResearchOpenLoopError, match="Artifact is not a research note"):
        research_open_loops.preview_research_open_loops(
            artifact["artifact_id"],
            workspace_root=research_loop_env["workspace_root"],
        )


def test_missing_artifact_is_rejected(research_loop_env):
    with pytest.raises(research_open_loops.ResearchOpenLoopError, match="Research artifact not found"):
        research_open_loops.preview_research_open_loops(
            "missing",
            workspace_root=research_loop_env["workspace_root"],
        )


def test_inactive_artifact_is_rejected(research_loop_env):
    artifact = _create_research_artifact(research_loop_env, status="archived")

    with pytest.raises(research_open_loops.ResearchOpenLoopError, match="Research artifact is not active"):
        research_open_loops.preview_research_open_loops(
            artifact["artifact_id"],
            workspace_root=research_loop_env["workspace_root"],
        )


def test_missing_artifact_file_is_rejected(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)
    (research_loop_env["workspace_root"] / "research" / "prior.md").unlink()

    with pytest.raises(research_open_loops.ResearchOpenLoopError, match="Research artifact file not found"):
        research_open_loops.preview_research_open_loops(
            artifact["artifact_id"],
            workspace_root=research_loop_env["workspace_root"],
        )


def test_missing_required_metadata_is_rejected(research_loop_env):
    artifact = _create_research_artifact(
        research_loop_env,
        metadata={
            "source_type": "research",
            "source_role": "research_reference",
            "origin": "manual_research",
            "research_title": "Prior",
            "research_date": "2026-05-14",
            "provisional": True,
        },
    )

    with pytest.raises(
        research_open_loops.ResearchOpenLoopError,
        match="Research artifact is missing required metadata: research_version",
    ):
        research_open_loops.preview_research_open_loops(
            artifact["artifact_id"],
            workspace_root=research_loop_env["workspace_root"],
        )


def test_no_open_questions_reports_zero_candidates_and_creates_nothing(research_loop_env):
    artifact = _create_research_artifact(
        research_loop_env,
        content=RESEARCH_NOTE_NO_LOOPS,
    )

    preview = research_open_loops.preview_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )
    created = research_open_loops.create_research_open_loops(
        artifact["artifact_id"],
        workspace_root=research_loop_env["workspace_root"],
    )

    assert preview["candidate_count"] == 0
    assert created["created_count"] == 0
    assert research_loop_env["open_loops"].list_open_loops() == []


def test_no_chroma_indexing_or_review_items_are_created(research_loop_env):
    artifact = _create_research_artifact(research_loop_env)

    with patch("tir.memory.chunking._store_chunk") as mock_store_chunk, \
         patch("tir.memory.chroma.upsert_chunk") as mock_upsert_chunk:
        research_open_loops.create_research_open_loops(
            artifact["artifact_id"],
            workspace_root=research_loop_env["workspace_root"],
        )

    mock_store_chunk.assert_not_called()
    mock_upsert_chunk.assert_not_called()
    assert research_loop_env["review"].list_review_items() == []
