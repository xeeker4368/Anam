"""One-shot bounded nightly tick runner.

This module does not run a daemon or background worker. It provides a small
operator/cron-callable heartbeat that can optionally run one existing bounded
research run-next action when both configuration and CLI flags allow it.
"""

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from tir.config import (
    SCHEDULER_ALLOW_BOUNDED_RESEARCH,
    SCHEDULER_ALLOW_IMAGE_GENERATION,
    SCHEDULER_ALLOW_MOLTBOOK,
    SCHEDULER_ALLOW_WEB,
    SCHEDULER_ENABLED,
    SCHEDULER_MAX_ACTIONS_PER_TICK,
    SCHEDULER_NIGHTLY_TICK_ENABLED,
    WORKSPACE_DIR,
)
from tir.research.bounded import (
    BoundedResearchError,
    plan_next_bounded_research_open_loop,
    run_next_bounded_research_open_loop,
)


NIGHTLY_TICK_VERSION = "nightly_tick_v1"


class NightlyTickError(ValueError):
    """Raised when nightly tick arguments are invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_local_date() -> str:
    return date.today().isoformat()


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _scheduler_config() -> dict:
    max_actions = max(int(SCHEDULER_MAX_ACTIONS_PER_TICK), 0)
    return {
        "enabled": bool(SCHEDULER_ENABLED),
        "nightly_tick_enabled": bool(SCHEDULER_NIGHTLY_TICK_ENABLED),
        "max_actions_per_tick": max_actions,
        "allow_bounded_research": bool(SCHEDULER_ALLOW_BOUNDED_RESEARCH),
        "allow_moltbook": bool(SCHEDULER_ALLOW_MOLTBOOK),
        "allow_web": bool(SCHEDULER_ALLOW_WEB),
        "allow_image_generation": bool(SCHEDULER_ALLOW_IMAGE_GENERATION),
    }


def _actions_allowed(config: dict, *, cli_allow_bounded_research: bool) -> list[str]:
    actions = ["heartbeat"]
    if config["allow_bounded_research"] and cli_allow_bounded_research:
        actions.append("bounded_research")
    return actions


def _base_result(
    *,
    mode: str,
    config: dict,
    current_local_date: str,
    cli_allow_bounded_research: bool,
) -> dict:
    enabled = config["enabled"] and config["nightly_tick_enabled"]
    return {
        "ok": True,
        "tick_version": NIGHTLY_TICK_VERSION,
        "mode": mode,
        "status": "planned" if enabled else "skipped",
        "scheduler_enabled": config["enabled"],
        "nightly_tick_enabled": config["nightly_tick_enabled"],
        "current_local_date": current_local_date,
        "pre_live_or_live": "pre_live",
        "config": config,
        "actions_allowed": (
            _actions_allowed(config, cli_allow_bounded_research=cli_allow_bounded_research)
            if enabled
            else []
        ),
        "actions_planned": [],
        "actions_run": [],
        "action_count": 0,
        "no_external_write_confirmed": True,
        "no_mutation_confirmed": mode == "dry-run",
        "tick_id": None,
        "started_at": None,
        "ended_at": None,
        "duration_seconds": None,
        "reason": None if enabled else "scheduler_disabled",
        "error_type": None,
        "error_message": None,
    }


def _bounded_research_plan(current_local_date: str) -> dict:
    plan = plan_next_bounded_research_open_loop(current_local_date=current_local_date)
    return {
        "action": "bounded_research",
        "allowed": True,
        "selected_open_loop_id": (
            plan.get("selected", {})
            .get("open_loop", {})
            .get("open_loop_id")
            if plan.get("selected")
            else None
        ),
        "eligible_count": plan.get("eligible_count", 0),
        "skipped_count": plan.get("skipped_count", 0),
        "skipped_count_by_reason": plan.get("skipped_count_by_reason", {}),
        "status": "planned" if plan.get("selected") else "noop",
        "reason": None if plan.get("selected") else "no_eligible_open_loops",
    }


def _summarize_run_next(result: dict) -> dict:
    selected = result.get("selected") or {}
    selected_loop = selected.get("open_loop") or {}
    artifact_result = result.get("artifact_result") or {}
    artifact = artifact_result.get("artifact") or {}
    write_result = result.get("write_result") or {}
    return {
        "action": "bounded_research",
        "status": "completed" if result.get("ran") else "noop",
        "ran": bool(result.get("ran")),
        "open_loop_id": selected_loop.get("open_loop_id"),
        "research_path": write_result.get("path") or result.get("relative_path"),
        "artifact_id": artifact.get("artifact_id"),
        "message": result.get("message"),
    }


def _save_audit_row(result: dict) -> str:
    summary = {
        "tick_version": result["tick_version"],
        "mode": result["mode"],
        "status": result["status"],
        "pre_live": result["pre_live_or_live"] == "pre_live",
        "actions_allowed": result["actions_allowed"],
        "actions_planned": result["actions_planned"],
        "actions_run": result["actions_run"],
        "action_count": result["action_count"],
        "reason": result["reason"],
        "error_type": result["error_type"],
        "error_message": result["error_message"],
        "no_external_write_confirmed": result["no_external_write_confirmed"],
    }
    return _db().save_overnight_run({
        "started_at": result["started_at"],
        "ended_at": result["ended_at"],
        "duration_seconds": result["duration_seconds"],
        "conversations_closed": 0,
        "summary": json.dumps(summary, sort_keys=True),
    })


def run_nightly_tick(
    *,
    write: bool = False,
    dry_run: bool = False,
    allow_bounded_research: bool = False,
    register_artifact: bool = False,
    model: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
    current_local_date: str | None = None,
) -> dict:
    """Run one bounded scheduler heartbeat, optionally with one research action."""
    if write == dry_run:
        raise NightlyTickError("Exactly one of --dry-run or --write is required")
    if register_artifact and not allow_bounded_research:
        raise NightlyTickError("--register-artifact requires --allow-bounded-research")

    mode = "write" if write else "dry-run"
    config = _scheduler_config()
    current_local_date = current_local_date or _current_local_date()
    result = _base_result(
        mode=mode,
        config=config,
        current_local_date=current_local_date,
        cli_allow_bounded_research=allow_bounded_research,
    )

    enabled = config["enabled"] and config["nightly_tick_enabled"]
    if not enabled:
        return result

    result["actions_planned"].append({"action": "heartbeat", "status": "planned"})

    bounded_allowed = config["allow_bounded_research"] and allow_bounded_research
    if allow_bounded_research and not config["allow_bounded_research"]:
        result["actions_planned"].append({
            "action": "bounded_research",
            "status": "skipped",
            "reason": "config_disallows_bounded_research",
        })
    elif bounded_allowed:
        if config["max_actions_per_tick"] < 1:
            result["actions_planned"].append({
                "action": "bounded_research",
                "status": "skipped",
                "reason": "max_actions_per_tick_zero",
            })
        else:
            result["actions_planned"].append(_bounded_research_plan(current_local_date))

    if dry_run:
        result["status"] = "planned"
        return result

    started = time.perf_counter()
    result["started_at"] = _now()
    result["actions_run"].append({"action": "heartbeat", "status": "recorded"})
    result["status"] = "completed"

    if bounded_allowed and config["max_actions_per_tick"] >= 1:
        try:
            run_result = run_next_bounded_research_open_loop(
                write=True,
                register_artifact=register_artifact,
                model=model,
                workspace_root=workspace_root,
                current_local_date=current_local_date,
                use_moltbook=False,
                moltbook_query=None,
                moltbook_feed=False,
                moltbook_limit=None,
                moltbook_sort="new",
            )
            action_summary = _summarize_run_next(run_result)
            result["actions_run"].append(action_summary)
            result["action_count"] = 1 if action_summary["ran"] else 0
        except BoundedResearchError as exc:
            result["ok"] = False
            result["status"] = "failed"
            result["error_type"] = "bounded_research_error"
            result["error_message"] = str(exc)
            result["actions_run"].append({
                "action": "bounded_research",
                "status": "failed",
                "error_type": "bounded_research_error",
                "error_message": str(exc),
            })
        except Exception as exc:
            result["ok"] = False
            result["status"] = "failed"
            result["error_type"] = "tool_error"
            result["error_message"] = str(exc)
            result["actions_run"].append({
                "action": "bounded_research",
                "status": "failed",
                "error_type": "tool_error",
                "error_message": str(exc),
            })

    result["ended_at"] = _now()
    result["duration_seconds"] = round(time.perf_counter() - started, 6)
    result["tick_id"] = _save_audit_row(result)
    return result
