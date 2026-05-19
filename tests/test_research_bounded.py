import importlib
import json

import pytest

from tir.workspace.service import ensure_workspace


TODAY = "2026-05-15"
YESTERDAY = "2026-05-14"


@pytest.fixture()
def bounded_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")

    import tir.memory.db as db_mod
    import tir.artifacts.service as artifacts_mod
    import tir.open_loops.service as open_loop_mod
    import tir.research.bounded as bounded_mod

    importlib.reload(db_mod)
    importlib.reload(artifacts_mod)
    importlib.reload(open_loop_mod)
    importlib.reload(bounded_mod)
    db_mod.init_databases()
    return {
        "db": db_mod,
        "artifacts": artifacts_mod,
        "open_loops": open_loop_mod,
        "bounded": bounded_mod,
        "workspace_root": workspace_root,
    }


def _metadata(**overrides):
    metadata = {
        "source_type": "research",
        "source_artifact_id": "artifact-1",
        "source_research_title": "Prior Research",
        "source_research_date": "2026-05-14",
        "source_research_path": "research/prior.md",
        "question": "What remains unresolved?",
        "provisional": True,
        "daily_iteration_limit": 1,
        "daily_iteration_count": 0,
        "daily_iteration_local_date": None,
        "last_researched_at": None,
        "ready_for_synthesis": False,
    }
    metadata.update(overrides)
    return metadata


def _create_loop(
    env,
    *,
    title="Research loop",
    status="open",
    loop_type="unresolved_question",
    priority="normal",
    source="manual_research",
    next_action="Investigate the question",
    metadata=None,
):
    return env["open_loops"].create_open_loop(
        title=title,
        status=status,
        loop_type=loop_type,
        priority=priority,
        source=source,
        next_action=next_action,
        metadata=_metadata() if metadata is None else metadata,
    )


def _plan(env):
    return env["bounded"].plan_next_bounded_research_open_loop(current_local_date=TODAY)


def _selected_id(plan):
    return plan["selected"]["open_loop"]["open_loop_id"]


def test_eligible_open_loop_is_selected(bounded_env):
    loop = _create_loop(bounded_env, title="Eligible loop")

    plan = _plan(bounded_env)

    assert _selected_id(plan) == loop["open_loop_id"]
    assert plan["eligible_count"] == 1
    assert plan["selected"]["reason_code"] == "eligible"


def test_ranking_prefers_high_priority_over_normal_and_low(bounded_env):
    low = _create_loop(bounded_env, title="Low", priority="low")
    high = _create_loop(bounded_env, title="High", priority="high")
    normal = _create_loop(bounded_env, title="Normal", priority="normal")

    plan = _plan(bounded_env)

    assert _selected_id(plan) == high["open_loop_id"]
    assert [item["open_loop"]["open_loop_id"] for item in plan["eligible"]] == [
        high["open_loop_id"],
        normal["open_loop_id"],
        low["open_loop_id"],
    ]


def test_ranking_prefers_clear_next_action(bounded_env):
    question_only = _create_loop(
        bounded_env,
        title="Question only",
        next_action=None,
        metadata=_metadata(question="Can metadata question carry the loop?"),
    )
    with_action = _create_loop(bounded_env, title="With action", next_action="Investigate clearly")

    plan = _plan(bounded_env)

    assert _selected_id(plan) == with_action["open_loop_id"]
    assert question_only["open_loop_id"] in [
        item["open_loop"]["open_loop_id"] for item in plan["eligible"]
    ]


def test_never_researched_loops_sort_before_previously_researched(bounded_env):
    researched = _create_loop(
        bounded_env,
        title="Researched",
        metadata=_metadata(last_researched_at="2026-05-13T10:00:00+00:00"),
    )
    never = _create_loop(bounded_env, title="Never researched")

    plan = _plan(bounded_env)

    assert _selected_id(plan) == never["open_loop_id"]
    assert researched["open_loop_id"] in [
        item["open_loop"]["open_loop_id"] for item in plan["eligible"]
    ]


def test_oldest_last_researched_at_sorts_before_newer(bounded_env):
    newer = _create_loop(
        bounded_env,
        title="Newer research",
        metadata=_metadata(last_researched_at="2026-05-14T10:00:00+00:00"),
    )
    older = _create_loop(
        bounded_env,
        title="Older research",
        metadata=_metadata(last_researched_at="2026-05-13T10:00:00+00:00"),
    )

    plan = _plan(bounded_env)

    assert _selected_id(plan) == older["open_loop_id"]
    assert newer["open_loop_id"] in [
        item["open_loop"]["open_loop_id"] for item in plan["eligible"]
    ]


def test_stale_daily_iteration_local_date_treats_count_as_zero(bounded_env):
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(
            daily_iteration_count=99,
            daily_iteration_local_date=YESTERDAY,
        ),
    )

    plan = _plan(bounded_env)

    assert _selected_id(plan) == loop["open_loop_id"]
    assert plan["selected"]["effective_daily_iteration_count"] == 0
    assert plan["selected"]["stored_daily_iteration_count"] == 99


def test_loop_at_daily_limit_today_is_skipped(bounded_env):
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(
            daily_iteration_limit=1,
            daily_iteration_count=1,
            daily_iteration_local_date=TODAY,
        ),
    )

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"daily_limit_reached": 1}
    assert plan["skipped"][0]["open_loop"]["open_loop_id"] == loop["open_loop_id"]


def test_ready_for_synthesis_loop_is_skipped(bounded_env):
    _create_loop(bounded_env, metadata=_metadata(ready_for_synthesis=True))

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"ready_for_synthesis": 1}


@pytest.mark.parametrize("status", ["closed", "archived", "blocked", "in_progress"])
def test_non_open_loop_is_skipped(bounded_env, status):
    _create_loop(bounded_env, status=status)

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"unsupported_status": 1}


def test_paused_status_row_is_skipped(bounded_env):
    loop = _create_loop(bounded_env)
    with bounded_env["db"].get_connection() as conn:
        conn.execute(
            "UPDATE main.open_loops SET status = ? WHERE open_loop_id = ?",
            ("paused", loop["open_loop_id"]),
        )
        conn.commit()

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"unsupported_status": 1}


def test_non_research_source_loop_is_skipped(bounded_env):
    _create_loop(bounded_env, source="manual_note")

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"unsupported_source": 1}


def test_loop_missing_next_action_and_metadata_question_is_skipped(bounded_env):
    _create_loop(
        bounded_env,
        next_action=None,
        metadata=_metadata(question=None),
    )

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"missing_next_action_or_question": 1}


def test_dry_run_does_not_mutate_metadata(bounded_env):
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(
            daily_iteration_count=5,
            daily_iteration_local_date=YESTERDAY,
        ),
    )
    with bounded_env["db"].get_connection() as conn:
        before = conn.execute(
            "SELECT metadata_json FROM main.open_loops WHERE open_loop_id = ?",
            (loop["open_loop_id"],),
        ).fetchone()["metadata_json"]

    plan = _plan(bounded_env)

    with bounded_env["db"].get_connection() as conn:
        after = conn.execute(
            "SELECT metadata_json FROM main.open_loops WHERE open_loop_id = ?",
            (loop["open_loop_id"],),
        ).fetchone()["metadata_json"]
    assert plan["selected"]["effective_daily_iteration_count"] == 0
    assert before == after


def test_no_eligible_loops_returns_clear_result(bounded_env):
    _create_loop(bounded_env, status="blocked")

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["eligible_count"] == 0
    assert plan["skipped_count"] == 1


def test_metadata_parse_error_is_reported_as_skip_reason(bounded_env):
    with bounded_env["db"].get_connection() as conn:
        conn.execute(
            """INSERT INTO main.open_loops
               (open_loop_id, title, description, status, loop_type, priority,
                related_artifact_id, source, source_conversation_id,
                source_message_id, source_tool_name, next_action, created_at,
                updated_at, closed_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "bad-metadata-loop",
                "Bad metadata",
                None,
                "open",
                "unresolved_question",
                "normal",
                None,
                "manual_research",
                None,
                None,
                None,
                "Investigate",
                "2026-05-15T10:00:00+00:00",
                "2026-05-15T10:00:00+00:00",
                None,
                '{"source_type":',
            ),
        )
        conn.commit()

    plan = _plan(bounded_env)

    assert plan["selected"] is None
    assert plan["skipped_count_by_reason"] == {"metadata_parse_error": 1}


def test_plan_result_is_json_serializable(bounded_env):
    _create_loop(bounded_env)

    plan = _plan(bounded_env)

    json.dumps(plan)


BOUNDED_BODY = """## Purpose

Continue the open-loop research question.

## Open Loop Being Researched

- The loop asks what remains unresolved.

## Prior Research Considered

- Prior research was treated as provisional context.

## Updated Findings

- No useful findings beyond the prior context.

## Uncertainty

- No external sources were collected.

## Sources

- Model-only bounded research pass plus prior provisional research context; no external sources collected.

## New Open Questions

- No new open questions.

## Possible Follow-Ups

- No follow-ups.

## Suggested Review Items

- No review items.

## Working Notes

- Keep the result provisional.
"""


def _patch_bounded_generation(env, monkeypatch, body=BOUNDED_BODY):
    monkeypatch.setattr(
        env["bounded"],
        "_now",
        lambda: "2026-05-15T12:00:00+00:00",
    )
    monkeypatch.setattr(
        env["bounded"],
        "chat_completion_text",
        lambda *args, **kwargs: body,
    )


def _create_source_artifact(env, *, artifact_id="artifact-1"):
    path = "research/prior.md"
    target = env["workspace_root"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Research Note - Prior\n\n## Findings\n\n- Prior provisional context.\n",
        encoding="utf-8",
    )
    return env["artifacts"].create_artifact(
        artifact_id=artifact_id,
        artifact_type="research_note",
        title="Research Note - Prior Research",
        path=path,
        status="active",
        source="manual_research",
        metadata={
            "source_type": "research",
            "source_role": "research_reference",
            "origin": "manual_research",
            "research_title": "Prior Research",
            "research_date": "2026-05-14",
            "research_version": "manual_research_v1",
            "provisional": True,
        },
        workspace_root=env["workspace_root"],
    )


def test_bounded_run_dry_run_validates_eligible_loop_and_writes_nothing(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env)
    before_metadata = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=False,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    assert result["mode"] == "dry-run"
    assert result["research_version"] == "manual_research_open_loop_iteration_v1"
    assert result["document"].startswith("# Research Note - ")
    assert list((bounded_env["workspace_root"] / "research").glob("*.md")) == []
    after_metadata = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    assert after_metadata == before_metadata


def test_bounded_run_dry_run_rejects_ineligible_loop_with_clear_reason(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env, status="blocked")

    with pytest.raises(
        bounded_env["bounded"].BoundedResearchError,
        match="unsupported_status",
    ):
        bounded_env["bounded"].run_bounded_research_open_loop(
            open_loop_id=loop["open_loop_id"],
            current_local_date=TODAY,
            workspace_root=bounded_env["workspace_root"],
        )


def test_bounded_run_write_creates_one_markdown_note_without_registering(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env)

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=True,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    research_files = list((bounded_env["workspace_root"] / "research").glob("*.md"))
    assert len(research_files) == 1
    assert result["write_result"]["path"] == "research/2026-05-15-what-remains-unresolved.md"
    assert "artifact_result" not in result
    assert bounded_env["artifacts"].list_artifacts(workspace_root=bounded_env["workspace_root"]) == []
    with bounded_env["db"].get_connection() as conn:
        rows = conn.execute("SELECT * FROM main.chunks_fts").fetchall()
    assert rows == []


def test_bounded_run_write_register_creates_artifact_and_indexes(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    _create_source_artifact(bounded_env)
    loop = _create_loop(bounded_env)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=True,
        register_artifact=True,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    artifact = result["artifact_result"]["artifact"]
    metadata = artifact["metadata"]
    assert artifact["artifact_type"] == "research_note"
    assert result["artifact_result"]["indexing"]["status"] == "indexed"
    assert result["artifact_result"]["indexing"]["chunks_written"] == 1
    assert metadata["open_loop_id"] == loop["open_loop_id"]
    assert metadata["research_version"] == "manual_research_open_loop_iteration_v1"
    assert metadata["provisional"] is True
    assert metadata["bounded_research_mode"] == "manual_open_loop_v1"
    assert metadata["source_research_artifact_id"] == "artifact-1"


def test_bounded_run_write_updates_open_loop_metadata_after_success(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(daily_iteration_limit=2, daily_iteration_count=1, daily_iteration_local_date=TODAY),
    )

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=True,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    updated = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])
    metadata = updated["metadata"]
    assert result["open_loop_update"]["metadata"]["daily_iteration_count"] == 2
    assert metadata["daily_iteration_count"] == 2
    assert metadata["daily_iteration_local_date"] == TODAY
    assert metadata["last_researched_at"] == "2026-05-15T12:00:00+00:00"
    assert metadata["last_research_path"] == result["relative_path"]
    assert metadata["last_research_result"] == "completed"
    assert "last_research_artifact_id" not in metadata


def test_bounded_run_write_register_updates_metadata_after_registration(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env)
    monkeypatch.setattr("tir.memory.research_indexing.upsert_chunk", lambda **kwargs: None)

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=True,
        register_artifact=True,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    metadata = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    assert metadata["last_research_artifact_id"] == result["artifact_result"]["artifact"]["artifact_id"]
    assert metadata["daily_iteration_count"] == 1


def test_bounded_run_stale_daily_date_resets_before_increment(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(daily_iteration_count=5, daily_iteration_local_date=YESTERDAY),
    )

    bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        write=True,
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    metadata = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    assert metadata["daily_iteration_count"] == 1
    assert metadata["daily_iteration_local_date"] == TODAY


def test_bounded_run_rejects_loop_at_daily_limit(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(
        bounded_env,
        metadata=_metadata(daily_iteration_count=1, daily_iteration_local_date=TODAY),
    )

    with pytest.raises(
        bounded_env["bounded"].BoundedResearchError,
        match="daily_limit_reached",
    ):
        bounded_env["bounded"].run_bounded_research_open_loop(
            open_loop_id=loop["open_loop_id"],
            write=True,
            current_local_date=TODAY,
            workspace_root=bounded_env["workspace_root"],
        )


def test_bounded_run_accepts_no_useful_findings_output(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch, body=BOUNDED_BODY)
    loop = _create_loop(bounded_env)

    result = bounded_env["bounded"].run_bounded_research_open_loop(
        open_loop_id=loop["open_loop_id"],
        current_local_date=TODAY,
        workspace_root=bounded_env["workspace_root"],
    )

    assert "No useful findings" in result["document"] or "No useful findings".lower() in result["document"].lower()
    assert "No new open questions" in result["document"]


def test_bounded_run_write_failure_does_not_mutate_metadata(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env)
    before = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    target = bounded_env["workspace_root"] / "research" / "2026-05-15-what-remains-unresolved.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(bounded_env["bounded"].BoundedResearchError, match="already exists"):
        bounded_env["bounded"].run_bounded_research_open_loop(
            open_loop_id=loop["open_loop_id"],
            write=True,
            current_local_date=TODAY,
            workspace_root=bounded_env["workspace_root"],
        )

    after = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    assert after == before


def test_bounded_run_registration_failure_does_not_mutate_metadata(bounded_env, monkeypatch):
    _patch_bounded_generation(bounded_env, monkeypatch)
    loop = _create_loop(bounded_env)
    before = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]

    def fail_register(*args, **kwargs):
        raise bounded_env["bounded"].ManualResearchError("Manual research indexing failed: boom")

    monkeypatch.setattr(bounded_env["bounded"], "register_manual_research_artifact", fail_register)

    with pytest.raises(bounded_env["bounded"].BoundedResearchError, match="indexing failed"):
        bounded_env["bounded"].run_bounded_research_open_loop(
            open_loop_id=loop["open_loop_id"],
            write=True,
            register_artifact=True,
            current_local_date=TODAY,
            workspace_root=bounded_env["workspace_root"],
        )

    assert (bounded_env["workspace_root"] / "research" / "2026-05-15-what-remains-unresolved.md").exists()
    after = bounded_env["open_loops"].get_open_loop(loop["open_loop_id"])["metadata"]
    assert after == before
