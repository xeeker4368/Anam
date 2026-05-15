"""Bounded research open-loop planning helpers.

This module only plans manual bounded research over existing research open
loops. It does not generate research notes, update loop metadata, index memory,
collect sources, or schedule autonomous work.
"""

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date


SUPPORTED_LOOP_TYPES = {"unresolved_question", "interrupted_research"}
DEFAULT_DAILY_ITERATION_LIMIT = 1
PRIORITY_RANK = {
    "high": 0,
    "normal": 1,
    "low": 2,
}


@dataclass(frozen=True)
class BoundedOpenLoopEvaluation:
    loop: dict
    metadata: dict | None
    eligible: bool
    reason_code: str
    reason: str
    current_local_date: str
    effective_daily_iteration_count: int
    daily_iteration_limit: int
    has_next_action: bool

    def to_dict(self) -> dict:
        metadata = self.metadata or {}
        return {
            "open_loop": self.loop,
            "metadata": self.metadata,
            "eligible": self.eligible,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "current_local_date": self.current_local_date,
            "effective_daily_iteration_count": self.effective_daily_iteration_count,
            "daily_iteration_limit": self.daily_iteration_limit,
            "stored_daily_iteration_count": metadata.get("daily_iteration_count"),
            "stored_daily_iteration_local_date": metadata.get("daily_iteration_local_date"),
            "has_next_action": self.has_next_action,
            "question": _loop_question(self.loop, metadata),
            "source_artifact_id": metadata.get("source_artifact_id"),
            "source_research_title": metadata.get("source_research_title"),
            "source_research_date": metadata.get("source_research_date"),
            "source_research_path": metadata.get("source_research_path"),
            "selection_reason": "highest_ranked_eligible_loop" if self.eligible else None,
        }


def _db():
    import tir.memory.db as db_mod

    return db_mod


def _current_local_date() -> str:
    return date.today().isoformat()


def _coerce_positive_int(value, default: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    if coerced < 1:
        return default
    return coerced


def _coerce_non_negative_int(value, default: int = 0) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    if coerced < 0:
        return default
    return coerced


def _has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _loop_question(loop: dict, metadata: dict | None) -> str | None:
    metadata = metadata or {}
    if _has_text(metadata.get("question")):
        return metadata["question"].strip()
    if _has_text(loop.get("title")):
        return loop["title"].strip()
    return None


def _load_open_loop_rows(*, max_loops: int = 1000) -> list[dict]:
    db_mod = _db()
    with db_mod.get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM main.open_loops
               ORDER BY created_at DESC
               LIMIT ?""",
            (max_loops,),
        ).fetchall()
    return [dict(row) for row in rows]


def _row_to_loop(row: dict) -> tuple[dict, dict | None, str | None]:
    metadata_json = row.get("metadata_json")
    metadata = None
    metadata_error = None
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            metadata_error = str(exc)

    loop = {
        "open_loop_id": row["open_loop_id"],
        "title": row["title"],
        "description": row.get("description"),
        "status": row["status"],
        "loop_type": row["loop_type"],
        "priority": row["priority"],
        "related_artifact_id": row.get("related_artifact_id"),
        "source": row.get("source"),
        "source_conversation_id": row.get("source_conversation_id"),
        "source_message_id": row.get("source_message_id"),
        "source_tool_name": row.get("source_tool_name"),
        "next_action": row.get("next_action"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "closed_at": row.get("closed_at"),
        "metadata_json": metadata_json,
        "metadata": metadata,
    }
    return loop, metadata, metadata_error


def _daily_state(metadata: dict, current_local_date: str) -> tuple[int, int]:
    limit = _coerce_positive_int(
        metadata.get("daily_iteration_limit"),
        DEFAULT_DAILY_ITERATION_LIMIT,
    )
    stored_date = metadata.get("daily_iteration_local_date")
    if stored_date != current_local_date:
        return 0, limit
    count = _coerce_non_negative_int(metadata.get("daily_iteration_count"), 0)
    return count, limit


def evaluate_open_loop_for_bounded_research(
    loop: dict,
    *,
    metadata: dict | None = None,
    metadata_error: str | None = None,
    current_local_date: str | None = None,
) -> BoundedOpenLoopEvaluation:
    """Evaluate one open loop for manual bounded research eligibility."""
    current_local_date = current_local_date or _current_local_date()
    metadata = metadata if metadata is not None else loop.get("metadata")
    has_next_action = _has_text(loop.get("next_action"))

    if metadata_error is not None:
        return BoundedOpenLoopEvaluation(
            loop=loop,
            metadata=None,
            eligible=False,
            reason_code="metadata_parse_error",
            reason=f"metadata_json could not be parsed: {metadata_error}",
            current_local_date=current_local_date,
            effective_daily_iteration_count=0,
            daily_iteration_limit=DEFAULT_DAILY_ITERATION_LIMIT,
            has_next_action=has_next_action,
        )

    metadata = metadata or {}
    effective_count, daily_limit = _daily_state(metadata, current_local_date)

    if loop.get("status") != "open":
        reason_code = "unsupported_status"
        reason = f"status is {loop.get('status')!r}, expected 'open'"
    elif loop.get("loop_type") not in SUPPORTED_LOOP_TYPES:
        reason_code = "unsupported_loop_type"
        reason = f"loop_type is {loop.get('loop_type')!r}"
    elif loop.get("source") != "manual_research":
        reason_code = "unsupported_source"
        reason = f"source is {loop.get('source')!r}, expected 'manual_research'"
    elif metadata.get("source_type") != "research":
        reason_code = "unsupported_metadata_source_type"
        reason = f"metadata.source_type is {metadata.get('source_type')!r}"
    elif metadata.get("provisional") is not True:
        reason_code = "not_provisional"
        reason = "metadata.provisional is not true"
    elif metadata.get("ready_for_synthesis") is True:
        reason_code = "ready_for_synthesis"
        reason = "metadata.ready_for_synthesis is true"
    elif not has_next_action and not _has_text(metadata.get("question")):
        reason_code = "missing_next_action_or_question"
        reason = "loop has no next_action and metadata.question is missing"
    elif effective_count >= daily_limit:
        reason_code = "daily_limit_reached"
        reason = f"daily iteration count {effective_count} reached limit {daily_limit}"
    else:
        reason_code = "eligible"
        reason = "eligible for manual bounded research"

    return BoundedOpenLoopEvaluation(
        loop=loop,
        metadata=metadata,
        eligible=reason_code == "eligible",
        reason_code=reason_code,
        reason=reason,
        current_local_date=current_local_date,
        effective_daily_iteration_count=effective_count,
        daily_iteration_limit=daily_limit,
        has_next_action=has_next_action,
    )


def _selection_sort_key(evaluation: BoundedOpenLoopEvaluation) -> tuple:
    loop = evaluation.loop
    metadata = evaluation.metadata or {}
    last_researched_at = metadata.get("last_researched_at")
    never_researched_rank = 0 if not last_researched_at else 1
    last_researched_sort = last_researched_at or ""
    return (
        PRIORITY_RANK.get(loop.get("priority"), PRIORITY_RANK["normal"]),
        0 if evaluation.has_next_action else 1,
        never_researched_rank,
        last_researched_sort,
        loop.get("created_at") or "",
        loop.get("open_loop_id") or "",
    )


def plan_next_bounded_research_open_loop(
    *,
    current_local_date: str | None = None,
    max_loops: int = 1000,
) -> dict:
    """Plan the next manual bounded research open loop without writing state."""
    current_local_date = current_local_date or _current_local_date()
    evaluations = []
    for row in _load_open_loop_rows(max_loops=max_loops):
        loop, metadata, metadata_error = _row_to_loop(row)
        evaluations.append(
            evaluate_open_loop_for_bounded_research(
                loop,
                metadata=metadata,
                metadata_error=metadata_error,
                current_local_date=current_local_date,
            )
        )

    eligible = sorted(
        [evaluation for evaluation in evaluations if evaluation.eligible],
        key=_selection_sort_key,
    )
    skipped = [evaluation for evaluation in evaluations if not evaluation.eligible]
    skipped_counts = Counter(evaluation.reason_code for evaluation in skipped)

    return {
        "current_local_date": current_local_date,
        "selected": eligible[0].to_dict() if eligible else None,
        "eligible": [evaluation.to_dict() for evaluation in eligible],
        "skipped": [evaluation.to_dict() for evaluation in skipped],
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
        "total_count": len(evaluations),
        "skipped_count_by_reason": dict(sorted(skipped_counts.items())),
        "global_daily_cap": {
            "enforced": False,
            "reason": "global daily research cap is deferred in planner v1",
        },
    }
