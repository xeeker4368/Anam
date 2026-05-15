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
    import tir.open_loops.service as open_loop_mod
    import tir.research.bounded as bounded_mod

    importlib.reload(db_mod)
    importlib.reload(open_loop_mod)
    importlib.reload(bounded_mod)
    db_mod.init_databases()
    return {
        "db": db_mod,
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
