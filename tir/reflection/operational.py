"""Manual operational reflection review.

This module reviews bounded operational/process activity and may create
operator review queue items. It does not create behavioral guidance proposals,
open loops, artifacts, schedules, or self-modification behavior.
"""

import json
import re
from datetime import datetime, timezone

from tir.behavioral_guidance.review import (
    BehavioralGuidanceReviewError,
    local_day_window_to_utc,
)
from tir.config import CHAT_MODEL, OLLAMA_HOST
from tir.engine.ollama import chat_completion_json
from tir.memory.db import get_connection
from tir.review.service import (
    ALLOWED_REVIEW_CATEGORIES,
    ALLOWED_REVIEW_PRIORITIES,
    create_review_item,
    list_review_items,
)


DEFAULT_OPERATIONAL_REFLECTION_MAX_ITEMS = 20
OPERATIONAL_REFLECTION_METHOD = "operational_reflection_v1"
OPERATIONAL_PACKET_CHAR_BUDGET = 16000
OPERATIONAL_EXCERPT_CHARS = 280
OBSERVATION_CATEGORIES = {
    "tool_failure",
    "artifact_issue",
    "retrieval_issue",
    "open_loop",
    "review_queue",
    "other",
}
REVIEW_CATEGORY_ALIASES = {
    "artifact_issue": "artifact",
    "retrieval_issue": "memory",
    "open_loop": "follow_up",
    "review_queue": "other",
}


class OperationalReflectionError(ValueError):
    """Raised when operational reflection cannot complete safely."""


def _normalize_positive_int(value, field: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise OperationalReflectionError(f"{field} must be an integer") from exc
    if normalized < 1:
        raise OperationalReflectionError(f"{field} must be at least 1")
    return normalized


def _parse_utc_timestamp(value: str, field: str) -> str:
    if not value or not value.strip():
        raise OperationalReflectionError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperationalReflectionError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise OperationalReflectionError(f"{field} must include timezone or Z")
    return parsed.astimezone(timezone.utc).isoformat()


def select_operational_reflection_window(
    *,
    date_text: str | None = None,
    since: str | None = None,
    tzinfo=None,
) -> dict:
    """Build the local-date or since window for operational reflection."""
    if date_text and since:
        raise OperationalReflectionError("Use either date or since, not both")
    if since:
        return {
            "selection_mode": "since",
            "local_date": None,
            "timezone": None,
            "local_offset": None,
            "utc_start": _parse_utc_timestamp(since, "since"),
            "utc_end": None,
            "since": since,
        }
    try:
        selection = local_day_window_to_utc(date_text, tzinfo=tzinfo)
    except BehavioralGuidanceReviewError as exc:
        raise OperationalReflectionError(str(exc)) from exc
    selection["selection_mode"] = "date"
    selection["since"] = None
    return selection


def _shorten(value, limit: int = OPERATIONAL_EXCERPT_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _window_where(fields: tuple[str, ...], selection: dict) -> tuple[str, list[str]]:
    utc_start = selection.get("utc_start")
    if not utc_start:
        return "WHERE 1 = 0", []
    clauses = []
    params = []
    for field in fields:
        if selection.get("utc_end"):
            clauses.append(f"({field} >= ? AND {field} < ?)")
            params.extend([utc_start, selection["utc_end"]])
        else:
            clauses.append(f"({field} >= ?)")
            params.append(utc_start)
    return "WHERE " + " OR ".join(clauses), params


def _tool_trace_records(trace_text: str | None) -> tuple[list[dict], str | None]:
    if not trace_text:
        return [], None
    try:
        parsed = json.loads(trace_text)
    except json.JSONDecodeError as exc:
        return [], f"unparseable tool trace: {exc.msg}"
    if isinstance(parsed, dict):
        return [parsed], None
    if isinstance(parsed, list):
        return [record for record in parsed if isinstance(record, dict)], None
    return [], "tool trace was not a JSON object or list"


def _tool_activity(selection: dict, max_items: int) -> tuple[list[str], dict]:
    where = "WHERE tool_trace IS NOT NULL AND TRIM(tool_trace) != '' AND timestamp >= ?"
    params = [selection.get("utc_start")]
    if selection.get("utc_end"):
        where += " AND timestamp < ?"
        params.append(selection["utc_end"])
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                f"""SELECT id, conversation_id, timestamp, tool_trace
                    FROM main.messages
                    {where}
                    ORDER BY timestamp ASC
                    LIMIT ?""",
                (*params, max_items + 1),
            ).fetchall()
        ]

    lines = []
    failures = 0
    for row in rows[:max_items]:
        records, error = _tool_trace_records(row.get("tool_trace"))
        if error:
            failures += 1
            lines.append(
                "- timestamp={timestamp}, conversation={conversation}, message={message}, status=failure, detail={detail}".format(
                    timestamp=row.get("timestamp") or "n/a",
                    conversation=row.get("conversation_id") or "n/a",
                    message=row.get("id") or "n/a",
                    detail=_shorten(error),
                )
            )
            continue
        for record in records or [{}]:
            calls = record.get("tool_calls") if isinstance(record, dict) else None
            results = record.get("tool_results") if isinstance(record, dict) else None
            tool_names = []
            if isinstance(calls, list):
                tool_names.extend(
                    str(call.get("name") or call.get("tool_name"))
                    for call in calls
                    if isinstance(call, dict) and (call.get("name") or call.get("tool_name"))
                )
            if not tool_names and isinstance(results, list):
                tool_names.extend(
                    str(result.get("name") or result.get("tool_name"))
                    for result in results
                    if isinstance(result, dict) and (result.get("name") or result.get("tool_name"))
                )
            status = "success"
            detail = ""
            if isinstance(results, list):
                for result in results:
                    if isinstance(result, dict) and (
                        result.get("ok") is False or result.get("error")
                    ):
                        status = "failure"
                        failures += 1
                        detail = result.get("error") or result.get("result") or result.get("rendered") or ""
                        break
            lines.append(
                "- timestamp={timestamp}, conversation={conversation}, message={message}, tools={tools}, status={status}, detail={detail}".format(
                    timestamp=row.get("timestamp") or "n/a",
                    conversation=row.get("conversation_id") or "n/a",
                    message=row.get("id") or "n/a",
                    tools=", ".join(sorted(set(tool_names))) or "unknown",
                    status=status,
                    detail=_shorten(detail) or "n/a",
                )
            )
    if not lines:
        lines = ["- No tool trace activity found in this window."]
    if len(rows) > max_items:
        lines.append(f"- {len(rows) - max_items} additional tool trace items omitted by limit.")
    return lines, {"tool_traces": len(rows), "tool_failures": failures}


def _table_activity(
    *,
    table: str,
    fields: tuple[str, ...],
    order: str,
    formatter,
    selection: dict,
    max_items: int,
    empty_line: str,
) -> tuple[list[str], int]:
    where, params = _window_where(fields, selection)
    with get_connection() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                f"""SELECT * FROM main.{table}
                    {where}
                    ORDER BY {order}
                    LIMIT ?""",
                (*params, max_items + 1),
            ).fetchall()
        ]
    lines = [formatter(row) for row in rows[:max_items]]
    if not lines:
        lines = [empty_line]
    if len(rows) > max_items:
        lines.append(f"- {len(rows) - max_items} additional {table} items omitted by limit.")
    return lines, len(rows)


def build_operational_activity_packet(
    selection: dict,
    *,
    max_items: int = DEFAULT_OPERATIONAL_REFLECTION_MAX_ITEMS,
) -> tuple[str, dict]:
    """Build compact operational/system activity for a manual review pass."""
    max_items = _normalize_positive_int(max_items, "max_items")
    tool_lines, tool_counts = _tool_activity(selection, max_items)

    artifact_lines, artifact_count = _table_activity(
        table="artifacts",
        fields=("created_at", "updated_at"),
        order="COALESCE(updated_at, created_at) ASC",
        selection=selection,
        max_items=max_items,
        empty_line="- No artifact activity found in this window.",
        formatter=lambda row: (
            "- artifact={artifact_id}, title={title}, type={artifact_type}, status={status}, path={path}, source_conversation={conversation}, source_message={message}, source_tool={tool}".format(
                artifact_id=row.get("artifact_id") or "n/a",
                title=_shorten(row.get("title")),
                artifact_type=row.get("artifact_type") or "n/a",
                status=row.get("status") or "n/a",
                path=_shorten(row.get("path")) or "n/a",
                conversation=row.get("source_conversation_id") or "n/a",
                message=row.get("source_message_id") or "n/a",
                tool=row.get("source_tool_name") or "n/a",
            )
        ),
    )
    review_lines, review_count = _table_activity(
        table="review_items",
        fields=("created_at", "updated_at", "reviewed_at"),
        order="COALESCE(reviewed_at, updated_at, created_at) ASC",
        selection=selection,
        max_items=max_items,
        empty_line="- No review queue activity found in this window.",
        formatter=lambda row: (
            "- review_item={item_id}, title={title}, category={category}, status={status}, priority={priority}, source_message={message}, source_artifact={artifact}, source_tool={tool}".format(
                item_id=row.get("item_id") or "n/a",
                title=_shorten(row.get("title")),
                category=row.get("category") or "n/a",
                status=row.get("status") or "n/a",
                priority=row.get("priority") or "n/a",
                message=row.get("source_message_id") or "n/a",
                artifact=row.get("source_artifact_id") or "n/a",
                tool=row.get("source_tool_name") or "n/a",
            )
        ),
    )
    open_loop_lines, open_loop_count = _table_activity(
        table="open_loops",
        fields=("created_at", "updated_at", "closed_at"),
        order="COALESCE(closed_at, updated_at, created_at) ASC",
        selection=selection,
        max_items=max_items,
        empty_line="- No open-loop activity found in this window.",
        formatter=lambda row: (
            "- open_loop={open_loop_id}, title={title}, type={loop_type}, status={status}, priority={priority}, next_action={next_action}, related_artifact={artifact}".format(
                open_loop_id=row.get("open_loop_id") or "n/a",
                title=_shorten(row.get("title")),
                loop_type=row.get("loop_type") or "n/a",
                status=row.get("status") or "n/a",
                priority=row.get("priority") or "n/a",
                next_action=_shorten(row.get("next_action")) or "n/a",
                artifact=row.get("related_artifact_id") or "n/a",
            )
        ),
    )
    guidance_lines, guidance_count = _table_activity(
        table="behavioral_guidance_proposals",
        fields=("created_at", "updated_at", "reviewed_at", "applied_at"),
        order="COALESCE(applied_at, reviewed_at, updated_at, created_at) ASC",
        selection=selection,
        max_items=max_items,
        empty_line="- No behavioral guidance proposal activity found in this window.",
        formatter=lambda row: (
            "- guidance_proposal={proposal_id}, type={proposal_type}, status={status}, source_conversation={conversation}, source_message={message}".format(
                proposal_id=row.get("proposal_id") or "n/a",
                proposal_type=row.get("proposal_type") or "n/a",
                status=row.get("status") or "n/a",
                conversation=row.get("source_conversation_id") or "n/a",
                message=row.get("source_message_id") or "n/a",
            )
        ),
    )
    conversation_lines, conversation_count = _table_activity(
        table="conversations",
        fields=("started_at", "ended_at"),
        order="COALESCE(ended_at, started_at) ASC",
        selection=selection,
        max_items=max_items,
        empty_line="- No conversation metadata activity found in this window.",
        formatter=lambda row: (
            "- conversation={id}, user_id={user_id}, started={started}, ended={ended}".format(
                id=row.get("id") or "n/a",
                user_id=row.get("user_id") or "n/a",
                started=row.get("started_at") or "n/a",
                ended=row.get("ended_at") or "active",
            )
        ),
    )

    sections = [
        ("[Tool trace activity]", tool_lines),
        ("[Artifact activity]", artifact_lines),
        ("[Review queue activity]", review_lines),
        ("[Open-loop activity]", open_loop_lines),
        ("[Behavioral guidance operational metadata]", guidance_lines),
        ("[Conversation/message shallow metadata]", conversation_lines),
    ]
    packet = "\n\n".join(title + "\n" + "\n".join(lines) for title, lines in sections)
    truncated = False
    if len(packet) > OPERATIONAL_PACKET_CHAR_BUDGET:
        packet = packet[:OPERATIONAL_PACKET_CHAR_BUDGET].rstrip() + "\n[operational activity packet truncated]"
        truncated = True
    return packet, {
        "counts": {
            **tool_counts,
            "artifacts": artifact_count,
            "review_items": review_count,
            "open_loops": open_loop_count,
            "behavioral_guidance_proposals": guidance_count,
            "conversations": conversation_count,
        },
        "chars": len(packet),
        "budget": OPERATIONAL_PACKET_CHAR_BUDGET,
        "truncated": truncated,
    }


def build_operational_reflection_messages(
    *,
    selection: dict,
    activity_packet: str,
    max_items: int,
) -> list[dict]:
    system = (
        "Review bounded operational/system activity and return only a strict JSON object. "
        "This review may identify operational observations and review queue candidates for admin review. "
        "It does not create behavioral guidance, apply changes, create open loops, or modify files."
    )
    user_prompt = f"""Review window:
local_date={selection.get('local_date')}
timezone={selection.get('timezone')}
local_offset={selection.get('local_offset')}
utc_start={selection.get('utc_start')}
utc_end={selection.get('utc_end')}
selection_mode={selection.get('selection_mode')}

Operational activity packet:
{activity_packet}

Return JSON with this shape:
{{
  "operational_observations": [
    {{
      "title": "...",
      "description": "...",
      "category": "tool_failure|artifact_issue|retrieval_issue|open_loop|review_queue|other",
      "severity": "low|normal|high",
      "evidence": "...",
      "source_type": "...",
      "source_conversation_id": "...",
      "source_message_id": "...",
      "source_artifact_id": "...",
      "source_tool_name": "..."
    }}
  ],
  "review_item_candidates": [
    {{
      "title": "...",
      "description": "...",
      "category": "tool_failure|artifact_issue|research|contradiction|follow_up|other",
      "priority": "low|normal|high",
      "source_type": "...",
      "source_conversation_id": "...",
      "source_message_id": "...",
      "source_artifact_id": "...",
      "source_tool_name": "...",
      "rationale": "..."
    }}
  ],
  "open_loop_candidates": [],
  "diagnostic_notes": ["..."],
  "no_action_reason": null
}}

Rules:
- Review operational issues only.
- Do not create behavioral guidance proposals.
- Do not deeply review normal conversation content unless it is tied to operational issues.
- Keep candidates concrete and evidence-linked.
- Return at most {max_items} review_item_candidates.
- Return zero candidates when no action is warranted.
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _parse_model_json(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "")
    except json.JSONDecodeError as exc:
        raise OperationalReflectionError(f"Model returned malformed JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise OperationalReflectionError("Model JSON root must be an object")
    return parsed


def _normalize_review_category(category: str | None) -> str:
    value = (category or "other").strip()
    value = REVIEW_CATEGORY_ALIASES.get(value, value)
    if value not in ALLOWED_REVIEW_CATEGORIES:
        raise OperationalReflectionError(f"Invalid review item category: {category}")
    return value


def _normalize_priority(priority: str | None) -> str:
    value = (priority or "normal").strip()
    if value not in ALLOWED_REVIEW_PRIORITIES:
        raise OperationalReflectionError(f"Invalid review item priority: {priority}")
    return value


def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_title(title) -> str:
    text = _optional_text(title)
    if not text:
        raise OperationalReflectionError("review item candidate title is required")
    return re.sub(r"\s+", " ", text).strip()


def validate_operational_reflection_output(parsed: dict, *, max_items: int) -> dict:
    """Validate and normalize model JSON before any write occurs."""
    observations = parsed.get("operational_observations", [])
    candidates = parsed.get("review_item_candidates", [])
    open_loop_candidates = parsed.get("open_loop_candidates", [])
    diagnostic_notes = parsed.get("diagnostic_notes", [])
    if not isinstance(observations, list):
        raise OperationalReflectionError("operational_observations must be a list")
    if not isinstance(candidates, list):
        raise OperationalReflectionError("review_item_candidates must be a list")
    if not isinstance(open_loop_candidates, list):
        raise OperationalReflectionError("open_loop_candidates must be a list")
    if not isinstance(diagnostic_notes, list):
        raise OperationalReflectionError("diagnostic_notes must be a list")
    if len(candidates) > max_items:
        raise OperationalReflectionError(f"review_item_candidates must be {max_items} or fewer")

    normalized_observations = []
    for item in observations:
        if not isinstance(item, dict):
            raise OperationalReflectionError("operational observation must be an object")
        category = _optional_text(item.get("category")) or "other"
        if category not in OBSERVATION_CATEGORIES:
            raise OperationalReflectionError(f"Invalid operational observation category: {category}")
        severity = _optional_text(item.get("severity")) or "normal"
        if severity not in {"low", "normal", "high"}:
            raise OperationalReflectionError(f"Invalid operational observation severity: {severity}")
        normalized_observations.append({**item, "category": category, "severity": severity})

    normalized_candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            raise OperationalReflectionError("review item candidate must be an object")
        normalized_candidates.append(
            {
                "title": _normalize_title(item.get("title")),
                "description": _optional_text(item.get("description")),
                "category": _normalize_review_category(item.get("category")),
                "priority": _normalize_priority(item.get("priority")),
                "source_type": _optional_text(item.get("source_type")),
                "source_conversation_id": _optional_text(item.get("source_conversation_id")),
                "source_message_id": _optional_text(item.get("source_message_id")),
                "source_artifact_id": _optional_text(item.get("source_artifact_id")),
                "source_tool_name": _optional_text(item.get("source_tool_name")),
                "rationale": _optional_text(item.get("rationale")),
            }
        )

    return {
        "operational_observations": normalized_observations,
        "review_item_candidates": normalized_candidates,
        "open_loop_candidates": open_loop_candidates,
        "diagnostic_notes": [str(note) for note in diagnostic_notes],
        "no_action_reason": parsed.get("no_action_reason"),
    }


def _normalized_title_for_duplicate(title: str) -> str:
    return re.sub(r"\s+", " ", title or "").strip().lower()


def _candidate_is_duplicate(candidate: dict) -> bool:
    normalized_title = _normalized_title_for_duplicate(candidate["title"])
    for item in list_review_items(limit=500):
        metadata = item.get("metadata") or {}
        if metadata.get("generation_method") != OPERATIONAL_REFLECTION_METHOD:
            continue
        if _normalized_title_for_duplicate(item.get("title")) != normalized_title:
            continue
        source_message_id = candidate.get("source_message_id")
        source_artifact_id = candidate.get("source_artifact_id")
        if source_message_id:
            if item.get("source_message_id") == source_message_id:
                return True
            continue
        if source_artifact_id:
            if item.get("source_artifact_id") == source_artifact_id:
                return True
            continue
        return True
    return False


def write_operational_review_items(
    candidates: list[dict],
    *,
    selection: dict,
) -> dict:
    """Create non-duplicate review items from validated candidates."""
    created = []
    skipped_duplicates = []
    source_window = {
        "local_date": selection.get("local_date"),
        "utc_start": selection.get("utc_start"),
        "utc_end": selection.get("utc_end"),
    }
    for candidate in candidates:
        if _candidate_is_duplicate(candidate):
            skipped_duplicates.append(candidate)
            continue
        created.append(
            create_review_item(
                title=candidate["title"],
                description=candidate.get("description"),
                category=candidate["category"],
                priority=candidate["priority"],
                source_type=candidate.get("source_type"),
                source_conversation_id=candidate.get("source_conversation_id"),
                source_message_id=candidate.get("source_message_id"),
                source_artifact_id=candidate.get("source_artifact_id"),
                source_tool_name=candidate.get("source_tool_name"),
                created_by="operational_reflection",
                metadata={
                    "generation_method": OPERATIONAL_REFLECTION_METHOD,
                    "source_window": source_window,
                    "rationale": candidate.get("rationale"),
                },
            )
        )
    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
    }


def generate_operational_reflection_day(
    *,
    date_text: str | None = None,
    since: str | None = None,
    max_items: int = DEFAULT_OPERATIONAL_REFLECTION_MAX_ITEMS,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate a dry-run operational reflection result."""
    max_items = _normalize_positive_int(max_items, "max_items")
    selection = select_operational_reflection_window(date_text=date_text, since=since)
    packet, packet_meta = build_operational_activity_packet(selection, max_items=max_items)
    messages = build_operational_reflection_messages(
        selection=selection,
        activity_packet=packet,
        max_items=max_items,
    )
    raw = chat_completion_json(messages, model=model or CHAT_MODEL, ollama_host=ollama_host)
    parsed = _parse_model_json(raw)
    normalized = validate_operational_reflection_output(parsed, max_items=max_items)
    return {
        "ok": True,
        "mode": "dry-run",
        "selection": selection,
        "activity_packet": packet,
        "activity_packet_meta": packet_meta,
        "model": model or CHAT_MODEL,
        **normalized,
    }


def run_operational_reflection_day(
    *,
    date_text: str | None = None,
    since: str | None = None,
    write: bool = False,
    max_items: int = DEFAULT_OPERATIONAL_REFLECTION_MAX_ITEMS,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate, and optionally write, operational review items."""
    result = generate_operational_reflection_day(
        date_text=date_text,
        since=since,
        max_items=max_items,
        model=model,
        ollama_host=ollama_host,
    )
    result["mode"] = "write" if write else "dry-run"
    if write:
        result["write_result"] = write_operational_review_items(
            result["review_item_candidates"],
            selection=result["selection"],
        )
    return result
