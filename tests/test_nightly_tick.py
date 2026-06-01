import importlib
import json

import pytest

from tir.workspace.service import ensure_workspace


TODAY = "2026-05-25"


@pytest.fixture()
def nightly_env(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    ensure_workspace(workspace_root)

    monkeypatch.setattr("tir.config.DATA_DIR", tmp_path / "data" / "prod")
    monkeypatch.setattr("tir.config.ARCHIVE_DB", tmp_path / "data" / "prod" / "archive.db")
    monkeypatch.setattr("tir.config.WORKING_DB", tmp_path / "data" / "prod" / "working.db")

    import tir.memory.db as db_mod
    import tir.scheduler.nightly as nightly_mod

    importlib.reload(db_mod)
    importlib.reload(nightly_mod)
    db_mod.init_databases()
    return {
        "db": db_mod,
        "nightly": nightly_mod,
        "workspace_root": workspace_root,
    }


def _set_scheduler_config(
    monkeypatch,
    nightly_mod,
    *,
    enabled=True,
    nightly_tick_enabled=True,
    max_actions_per_tick=1,
    allow_bounded_research=False,
    allow_moltbook=False,
    allow_web=False,
    allow_image_generation=False,
    go_live=False,
):
    monkeypatch.setattr(nightly_mod, "SCHEDULER_ENABLED", enabled)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_NIGHTLY_TICK_ENABLED", nightly_tick_enabled)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_MAX_ACTIONS_PER_TICK", max_actions_per_tick)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_ALLOW_BOUNDED_RESEARCH", allow_bounded_research)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_ALLOW_MOLTBOOK", allow_moltbook)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_ALLOW_WEB", allow_web)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_ALLOW_IMAGE_GENERATION", allow_image_generation)
    monkeypatch.setattr(nightly_mod, "SCHEDULER_GO_LIVE", go_live)


def _overnight_rows(db_mod):
    with db_mod.get_connection() as conn:
        rows = conn.execute("SELECT * FROM main.overnight_runs ORDER BY started_at").fetchall()
    return [dict(row) for row in rows]


def _row_summary(row):
    return json.loads(row["summary"])


def test_dry_run_writes_no_overnight_rows_or_files(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(monkeypatch, nightly)

    result = nightly.run_nightly_tick(
        dry_run=True,
        current_local_date=TODAY,
        workspace_root=nightly_env["workspace_root"],
    )

    assert result["mode"] == "dry-run"
    assert result["status"] == "planned"
    assert result["no_mutation_confirmed"] is True
    assert result["actions_planned"] == [{"action": "heartbeat", "status": "planned"}]
    assert _overnight_rows(nightly_env["db"]) == []
    assert list((nightly_env["workspace_root"] / "research").glob("*.md")) == []


def test_disabled_scheduler_reports_skipped_without_writing(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(monkeypatch, nightly, enabled=False, nightly_tick_enabled=False)

    result = nightly.run_nightly_tick(write=True, current_local_date=TODAY)

    assert result["status"] == "skipped"
    assert result["reason"] == "scheduler_disabled"
    assert result["actions_allowed"] == []
    assert result["tick_id"] is None
    assert _overnight_rows(nightly_env["db"]) == []


def test_enabled_write_records_one_overnight_audit_row(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(monkeypatch, nightly)

    result = nightly.run_nightly_tick(write=True, current_local_date=TODAY)

    assert result["status"] == "completed"
    assert result["tick_id"]
    rows = _overnight_rows(nightly_env["db"])
    assert len(rows) == 1
    summary = _row_summary(rows[0])
    assert summary["tick_version"] == "nightly_tick_v1"
    assert summary["mode"] == "write"
    assert summary["actions_run"] == [{"action": "heartbeat", "status": "recorded"}]
    assert summary["no_external_write_confirmed"] is True


def test_default_tick_records_pre_live(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(monkeypatch, nightly)

    result = nightly.run_nightly_tick(write=True, current_local_date=TODAY)

    assert result["config"]["go_live"] is False
    assert result["pre_live_or_live"] == "pre_live"
    rows = _overnight_rows(nightly_env["db"])
    assert len(rows) == 1
    assert _row_summary(rows[0])["pre_live"] is True


def test_go_live_tick_records_live(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(monkeypatch, nightly, go_live=True)

    result = nightly.run_nightly_tick(write=True, current_local_date=TODAY)

    assert result["config"]["go_live"] is True
    assert result["pre_live_or_live"] == "live"
    rows = _overnight_rows(nightly_env["db"])
    assert len(rows) == 1
    assert _row_summary(rows[0])["pre_live"] is False


def test_max_actions_per_tick_one_is_enforced(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        max_actions_per_tick=0,
        allow_bounded_research=True,
    )

    def fail_run_next(**_kwargs):
        raise AssertionError("bounded research should not run")

    monkeypatch.setattr(nightly, "run_next_bounded_research_open_loop", fail_run_next)

    result = nightly.run_nightly_tick(
        write=True,
        allow_bounded_research=True,
        current_local_date=TODAY,
    )

    assert result["status"] == "completed"
    assert result["action_count"] == 0
    assert {
        "action": "bounded_research",
        "status": "skipped",
        "reason": "max_actions_per_tick_zero",
    } in result["actions_planned"]


@pytest.mark.parametrize(
    "config_allows,cli_allows,expected_reason",
    [
        (True, False, None),
        (False, True, "config_disallows_bounded_research"),
    ],
)
def test_bounded_research_requires_config_and_cli_gate(
    nightly_env,
    monkeypatch,
    config_allows,
    cli_allows,
    expected_reason,
):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        allow_bounded_research=config_allows,
    )

    def fail_run_next(**_kwargs):
        raise AssertionError("bounded research should not run")

    monkeypatch.setattr(nightly, "run_next_bounded_research_open_loop", fail_run_next)

    result = nightly.run_nightly_tick(
        write=True,
        allow_bounded_research=cli_allows,
        current_local_date=TODAY,
    )

    assert result["status"] == "completed"
    assert result["action_count"] == 0
    if expected_reason:
        assert any(
            item.get("reason") == expected_reason
            for item in result["actions_planned"]
        )


def test_allowed_bounded_research_calls_existing_run_next_model_only(
    nightly_env,
    monkeypatch,
):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        allow_bounded_research=True,
    )
    calls = []

    monkeypatch.setattr(
        nightly,
        "plan_next_bounded_research_open_loop",
        lambda **_kwargs: {
            "selected": {"open_loop": {"open_loop_id": "loop-1"}},
            "eligible_count": 1,
            "skipped_count": 0,
            "skipped_count_by_reason": {},
        },
    )

    def fake_run_next(**kwargs):
        calls.append(kwargs)
        return {
            "ran": True,
            "selected": {"open_loop": {"open_loop_id": "loop-1"}},
            "relative_path": "research/2026-05-25-loop.md",
            "write_result": {"path": "research/2026-05-25-loop.md"},
            "artifact_result": {
                "artifact": {"artifact_id": "artifact-1"},
            },
        }

    monkeypatch.setattr(nightly, "run_next_bounded_research_open_loop", fake_run_next)

    result = nightly.run_nightly_tick(
        write=True,
        allow_bounded_research=True,
        register_artifact=True,
        current_local_date=TODAY,
        workspace_root=nightly_env["workspace_root"],
    )

    assert result["action_count"] == 1
    assert result["actions_run"][-1] == {
        "action": "bounded_research",
        "status": "completed",
        "ran": True,
        "open_loop_id": "loop-1",
        "research_path": "research/2026-05-25-loop.md",
        "artifact_id": "artifact-1",
        "message": None,
    }
    assert calls == [{
        "write": True,
        "register_artifact": True,
        "model": None,
        "workspace_root": nightly_env["workspace_root"],
        "current_local_date": TODAY,
        "use_moltbook": False,
        "moltbook_query": None,
        "moltbook_feed": False,
        "moltbook_limit": None,
        "moltbook_sort": "new",
    }]


def test_no_eligible_open_loops_is_clean_noop_tick(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        allow_bounded_research=True,
    )

    monkeypatch.setattr(
        nightly,
        "plan_next_bounded_research_open_loop",
        lambda **_kwargs: {
            "selected": None,
            "eligible_count": 0,
            "skipped_count": 1,
            "skipped_count_by_reason": {"daily_limit_reached": 1},
        },
    )
    monkeypatch.setattr(
        nightly,
        "run_next_bounded_research_open_loop",
        lambda **_kwargs: {
            "ran": False,
            "message": "No eligible bounded research open loops found.",
            "selected": None,
        },
    )

    result = nightly.run_nightly_tick(
        write=True,
        allow_bounded_research=True,
        current_local_date=TODAY,
    )

    assert result["status"] == "completed"
    assert result["action_count"] == 0
    assert result["actions_run"][-1]["status"] == "noop"
    rows = _overnight_rows(nightly_env["db"])
    assert len(rows) == 1


def test_run_next_failure_is_recorded_without_unbounded_retry(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        allow_bounded_research=True,
    )

    def fail_run_next(**_kwargs):
        raise nightly.BoundedResearchError("model failed")

    monkeypatch.setattr(nightly, "run_next_bounded_research_open_loop", fail_run_next)

    result = nightly.run_nightly_tick(
        write=True,
        allow_bounded_research=True,
        current_local_date=TODAY,
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error_type"] == "bounded_research_error"
    assert "model failed" in result["error_message"]
    assert result["actions_run"][-1]["status"] == "failed"
    rows = _overnight_rows(nightly_env["db"])
    assert len(rows) == 1
    assert _row_summary(rows[0])["status"] == "failed"


def test_register_artifact_requires_bounded_research_flag(nightly_env):
    nightly = nightly_env["nightly"]

    with pytest.raises(nightly.NightlyTickError, match="requires --allow-bounded-research"):
        nightly.run_nightly_tick(write=True, register_artifact=True)


def test_v1_forbidden_actions_are_config_visible_but_not_runnable(nightly_env, monkeypatch):
    nightly = nightly_env["nightly"]
    _set_scheduler_config(
        monkeypatch,
        nightly,
        allow_moltbook=True,
        allow_web=True,
        allow_image_generation=True,
    )

    result = nightly.run_nightly_tick(write=True, current_local_date=TODAY)

    assert result["config"]["allow_moltbook"] is True
    assert result["config"]["allow_web"] is True
    assert result["config"]["allow_image_generation"] is True
    assert "moltbook" not in result["actions_allowed"]
    assert "web" not in result["actions_allowed"]
    assert "image_generation" not in result["actions_allowed"]
    assert result["actions_run"] == [{"action": "heartbeat", "status": "recorded"}]
