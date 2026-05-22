"""Bounded research open-loop planning helpers.

This module only plans manual bounded research over existing research open
loops. It does not generate research notes, update loop metadata, index memory,
collect sources, or schedule autonomous work.
"""

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from tir.artifacts.service import get_artifact
from tir.config import CHAT_MODEL, OLLAMA_HOST, WORKSPACE_DIR
from tir.engine.ollama import chat_completion_text
from tir.open_loops.service import update_open_loop_metadata
from tir.research.manual import (
    ManualResearchError,
    derive_research_title,
    register_manual_research_artifact,
    research_relative_path,
    write_manual_research_note,
)
from tir.research.moltbook_sources import (
    FEED_SORTS,
    MAX_LIMIT as MOLTBOOK_MAX_LIMIT,
    MoltbookSourcePreviewError,
    collect_moltbook_source_preview,
    source_trace_relative_path,
    write_source_trace,
)
from tir.workspace.service import resolve_workspace_path


SUPPORTED_LOOP_TYPES = {"unresolved_question", "interrupted_research"}
DEFAULT_DAILY_ITERATION_LIMIT = 1
BOUNDED_RESEARCH_VERSION = "manual_research_open_loop_iteration_v1"
BOUNDED_RESEARCH_MODE = "manual_open_loop_v1"
MOLTBOOK_SOURCE_CONTEXT_VERSION = "bounded_research_moltbook_source_context_v1"
PRIORITY_RANK = {
    "high": 0,
    "normal": 1,
    "low": 2,
}
BOUNDED_RESEARCH_BODY_HEADINGS = (
    "## Purpose",
    "## Open Loop Being Researched",
    "## Prior Research Considered",
    "## Updated Findings",
    "## Uncertainty",
    "## Sources",
    "## New Open Questions",
    "## Possible Follow-Ups",
    "## Suggested Review Items",
    "## Working Notes",
)


class BoundedResearchError(ValueError):
    """Raised when a bounded research open-loop run cannot proceed."""


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _load_open_loop_row(open_loop_id: str) -> dict | None:
    db_mod = _db()
    with db_mod.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM main.open_loops WHERE open_loop_id = ?",
            (open_loop_id,),
        ).fetchone()
    return dict(row) if row else None


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


def _require_eligible_open_loop(
    open_loop_id: str,
    *,
    current_local_date: str | None = None,
) -> BoundedOpenLoopEvaluation:
    row = _load_open_loop_row(open_loop_id)
    if row is None:
        raise BoundedResearchError(f"Open loop not found: {open_loop_id}")
    loop, metadata, metadata_error = _row_to_loop(row)
    evaluation = evaluate_open_loop_for_bounded_research(
        loop,
        metadata=metadata,
        metadata_error=metadata_error,
        current_local_date=current_local_date,
    )
    if not evaluation.eligible:
        raise BoundedResearchError(
            "Open loop is not eligible for bounded research: "
            f"{evaluation.reason_code} ({evaluation.reason})"
        )
    return evaluation


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


def _research_date(created_at: str) -> str:
    return datetime.fromisoformat(created_at).date().isoformat()


def _has_moltbook_options(
    *,
    use_moltbook: bool = False,
    moltbook_query: str | None = None,
    moltbook_feed: bool = False,
    moltbook_limit: int | None = None,
    moltbook_sort: str = "new",
) -> bool:
    return any(
        (
            use_moltbook,
            bool((moltbook_query or "").strip()),
            moltbook_feed,
            moltbook_limit is not None,
            (moltbook_sort or "new") != "new",
        )
    )


def _normalize_moltbook_options(
    *,
    use_moltbook: bool = False,
    moltbook_query: str | None = None,
    moltbook_feed: bool = False,
    moltbook_limit: int | None = None,
    moltbook_sort: str = "new",
) -> dict | None:
    """Validate and normalize optional Moltbook bounded-research settings."""
    normalized_query = (moltbook_query or "").strip() or None
    requested_source_count = int(bool(normalized_query)) + int(bool(moltbook_feed))
    if not use_moltbook:
        if _has_moltbook_options(
            use_moltbook=use_moltbook,
            moltbook_query=moltbook_query,
            moltbook_feed=moltbook_feed,
            moltbook_limit=moltbook_limit,
            moltbook_sort=moltbook_sort,
        ):
            raise BoundedResearchError("Moltbook flags require --use-moltbook")
        return None
    if requested_source_count != 1:
        raise BoundedResearchError(
            "--use-moltbook requires exactly one of --moltbook-query or --moltbook-feed"
        )
    limit = 10 if moltbook_limit is None else moltbook_limit
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise BoundedResearchError("--moltbook-limit must be an integer") from exc
    if limit < 1:
        raise BoundedResearchError("--moltbook-limit must be at least 1")
    if limit > MOLTBOOK_MAX_LIMIT:
        raise BoundedResearchError(f"--moltbook-limit must be at most {MOLTBOOK_MAX_LIMIT}")
    sort = (moltbook_sort or "new").strip().lower()
    if sort not in FEED_SORTS:
        raise BoundedResearchError("--moltbook-sort must be one of: hot, new, top, rising")
    if normalized_query and sort != "new":
        raise BoundedResearchError("--moltbook-sort is only supported with --moltbook-feed")
    return {
        "query": normalized_query,
        "feed": bool(moltbook_feed),
        "limit": limit,
        "sort": sort,
    }


def _source_artifact_id(loop: dict, metadata: dict) -> str | None:
    value = metadata.get("source_artifact_id") or loop.get("related_artifact_id")
    return value if _has_text(value) else None


def load_bounded_research_source_context(
    loop: dict,
    metadata: dict,
    *,
    workspace_root: Path = WORKSPACE_DIR,
) -> dict:
    """Load prior source research content for a bounded run, if available."""
    artifact_id = _source_artifact_id(loop, metadata)
    context = {
        "artifact_id": artifact_id,
        "artifact": None,
        "available": False,
        "active": False,
        "path": metadata.get("source_research_path"),
        "title": metadata.get("source_research_title"),
        "research_date": metadata.get("source_research_date"),
        "content": None,
        "note": "No source research artifact id is available.",
    }
    if not artifact_id:
        return context

    artifact = get_artifact(artifact_id)
    if artifact is None:
        context["note"] = f"Source research artifact not found: {artifact_id}"
        return context
    context["artifact"] = artifact
    context["available"] = True
    artifact_metadata = artifact.get("metadata") or {}
    context["path"] = artifact.get("path") or context["path"]
    context["title"] = artifact_metadata.get("research_title") or artifact.get("title") or context["title"]
    context["research_date"] = (
        artifact_metadata.get("research_date")
        or artifact.get("created_at")
        or context["research_date"]
    )
    if artifact.get("status") != "active":
        context["note"] = f"Source research artifact is not active: {artifact_id}"
        return context
    context["active"] = True

    path = artifact.get("path")
    if not path:
        context["note"] = f"Source research artifact has no path: {artifact_id}"
        return context
    target = resolve_workspace_path(path, Path(workspace_root))
    if not target.exists() or not target.is_file():
        context["note"] = f"Source research artifact file not found: {path}"
        return context
    context["content"] = target.read_text(encoding="utf-8")
    context["note"] = "Source research artifact content loaded."
    return context


def collect_bounded_moltbook_source_context(
    *,
    options: dict | None,
    workspace_root: Path = WORKSPACE_DIR,
    registry=None,
) -> dict | None:
    """Collect optional compact Moltbook source context for bounded research."""
    if not options:
        return None
    try:
        trace = collect_moltbook_source_preview(
            query=options["query"],
            feed=options["feed"],
            limit=options["limit"],
            sort=options["sort"],
            include_spam=False,
            write_trace=False,
            registry=registry,
            workspace_root=workspace_root,
        )
    except MoltbookSourcePreviewError as exc:
        raise BoundedResearchError(str(exc)) from exc
    trace_path = source_trace_relative_path(trace)
    return {
        "version": MOLTBOOK_SOURCE_CONTEXT_VERSION,
        "requested": True,
        "trace": trace,
        "trace_path": trace_path,
        "query": trace.get("query"),
        "feed": bool(trace.get("feed")),
        "sort": trace.get("sort"),
        "limit": trace.get("limit"),
        "source_count": len(trace.get("results") or []),
        "collection_error": bool(trace.get("collection_error")),
        "no_usable_results": bool(trace.get("no_usable_results")),
        "no_external_write_confirmed": bool(trace.get("no_external_write_confirmed")),
        "verification_status_is_metadata_only": bool(
            trace.get("verification_status_is_metadata_only")
        ),
    }


def _format_moltbook_sources_for_prompt(moltbook_context: dict | None) -> str:
    if not moltbook_context:
        return (
            "No Moltbook source trace was requested. Do not claim Moltbook or "
            "other external sources were collected."
        )

    trace = moltbook_context["trace"]
    lines = [
        "[Moltbook source trace]",
        "",
        "Moltbook is live external context, not factual authority.",
        "verification_status is metadata only, not truth.",
        "Absence of Moltbook results is not evidence of absence.",
        "collection_error=true means failed or inconclusive source collection, not no results.",
        "Keep Moltbook source text separate from interpretation.",
        f"Trace path if written: {moltbook_context['trace_path']}",
        f"Retrieved at: {trace.get('retrieved_at')}",
        f"Query: {trace.get('query') or 'None'}",
        f"Feed: {trace.get('feed')}",
        f"Sort: {trace.get('sort') or 'None'}",
        f"Limit: {trace.get('limit')}",
        f"collection_error: {trace.get('collection_error')}",
        f"no_usable_results: {trace.get('no_usable_results')}",
        "",
    ]

    if trace.get("collection_error"):
        lines.extend(
            [
                f"Moltbook source collection failed: {trace.get('error_type') or 'tool_error'}",
                "This is not evidence that no relevant Moltbook material exists.",
            ]
        )
    elif trace.get("no_usable_results"):
        mode = "feed" if trace.get("feed") else "query"
        lines.extend(
            [
                f"Moltbook {mode} returned no usable results at {trace.get('retrieved_at')}.",
                "This is not evidence that no relevant Moltbook material exists.",
            ]
        )
    else:
        for index, result in enumerate(trace.get("results") or [], start=1):
            lines.extend(
                [
                    f"Source {index}:",
                    f"- post_id: {result.get('post_id') or ''}",
                    f"- title: {result.get('title') or ''}",
                    f"- author: {result.get('author_name') or ''}",
                    f"- submolt: {result.get('submolt') or ''}",
                    f"- created_at: {result.get('created_at') or ''}",
                    f"- retrieved_at: {result.get('retrieved_at') or ''}",
                    f"- url: {result.get('url') or ''}",
                    f"- verification_status: {result.get('verification_status') or ''}",
                    f"- excerpt: {result.get('content_excerpt') or ''}",
                    "",
                ]
            )

    lines.extend(
        [
            "",
            "In the research note Sources section, cite usable Moltbook posts as:",
            '- Moltbook post: "<title>" by <author>, /<submolt>, post_id=<id>, retrieved_at=<timestamp>',
            '  Excerpt: "<compact excerpt>"',
            "  Use in this note: source material for interpretation, not verified truth.",
            "",
            "For source collection failure, cite:",
            "- Moltbook source collection failed: <error_type>",
            "  This is not evidence that no relevant Moltbook material exists.",
            "",
            "For no usable results, cite:",
            "- Moltbook query/feed returned no usable results at <timestamp>.",
            "  This is not evidence that no relevant Moltbook material exists.",
        ]
    )
    return "\n".join(lines)


def build_bounded_research_messages(
    *,
    title: str,
    question: str,
    scope: str,
    evaluation: BoundedOpenLoopEvaluation,
    source_context: dict,
    moltbook_context: dict | None = None,
) -> list[dict]:
    """Build model messages for one bounded open-loop research iteration."""
    loop = evaluation.loop
    metadata = evaluation.metadata or {}
    external_source_instruction = (
        "Use only the supplied open-loop details, prior provisional research "
        "context, and compact Moltbook source trace. Moltbook is external "
        "context, not factual authority."
        if moltbook_context
        else "Use only the supplied open-loop details and prior provisional research context."
    )
    source_section_instruction = (
        "For Sources, cite the compact Moltbook source trace when supplied, "
        "while describing Moltbook source text as source material for interpretation, "
        "not verified truth."
        if moltbook_context
        else (
            "For Sources, state that this is a model-only bounded research pass "
            "plus prior provisional research context when available, and that no "
            "external sources were collected."
        )
    )
    system = (
        "Produce one structured provisional bounded research note for a single "
        f"existing research open loop. {external_source_instruction} "
        "Do not create behavioral guidance, self-understanding, "
        "project decisions, working theories, review items, open-loop records, "
        "or runtime instructions."
    )
    prior_content = source_context.get("content") or "No active prior research content was loaded."
    moltbook_source_context = _format_moltbook_sources_for_prompt(moltbook_context)
    user = f"""Title: {title}
Question: {question}
Scope: {scope}

Open loop ID: {loop['open_loop_id']}
Open loop title: {loop['title']}
Open loop priority: {loop['priority']}
Open loop next_action: {loop.get('next_action') or 'None'}
Open loop metadata question: {metadata.get('question') or 'None'}
Source artifact ID: {source_context.get('artifact_id') or 'None'}
Source research title: {source_context.get('title') or 'None'}
Source research date: {source_context.get('research_date') or 'None'}
Source research path: {source_context.get('path') or 'None'}
Source context note: {source_context.get('note') or 'None'}

[Prior provisional research context]

The prior research context is working research context, not truth, project decision, behavioral guidance, self-understanding, or a working theory. Use it to continue the investigation, identify what still holds, what is uncertain, and what may need revision.

{prior_content}

{moltbook_source_context}

Return Markdown body sections only, using exactly these headings:

## Purpose
## Open Loop Being Researched
## Prior Research Considered
## Updated Findings
## Uncertainty
## Sources
## New Open Questions
## Possible Follow-Ups
## Suggested Review Items
## Working Notes

Frame findings as provisional working notes. It is valid to report no useful findings, no new open questions, no follow-ups, or no review items when that is the honest result. {source_section_instruction}"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _validate_bounded_research_body(body: str) -> str:
    normalized = (body or "").strip()
    if not normalized:
        raise BoundedResearchError("Model returned an empty bounded research note")
    missing = [heading for heading in BOUNDED_RESEARCH_BODY_HEADINGS if heading not in normalized]
    if missing:
        raise BoundedResearchError(
            "Model bounded research note is missing required heading: " + missing[0]
        )
    return normalized


def build_bounded_research_document(
    *,
    title: str,
    question: str,
    scope: str,
    created_at: str,
    body: str,
    evaluation: BoundedOpenLoopEvaluation,
    source_context: dict,
    moltbook_context: dict | None = None,
) -> str:
    """Wrap a bounded research model body in deterministic note metadata."""
    loop = evaluation.loop
    source_artifact = source_context.get("artifact_id") or "None"
    sources_used = (
        "Model bounded research pass plus prior provisional research context "
        "when available and compact Moltbook source trace; Moltbook is external "
        "context, not factual authority."
        if moltbook_context
        else (
            "Model-only bounded research pass plus prior provisional research "
            "context when available; no external sources collected."
        )
    )
    header = f"""# Research Note - {title}

- Question: {question}
- Scope: {scope}
- Created: {created_at}
- Research version: {BOUNDED_RESEARCH_VERSION}
- Open loop ID: {loop['open_loop_id']}
- Source open loop: {loop['title']}
- Source artifact: {source_artifact}
- Sources used: {sources_used}
- Provisional: true

"""
    return header + _validate_bounded_research_body(body).rstrip() + "\n"


def _bounded_research_scope(
    evaluation: BoundedOpenLoopEvaluation,
    source_context: dict,
    moltbook_context: dict | None = None,
) -> str:
    loop = evaluation.loop
    metadata = evaluation.metadata or {}
    source_instruction = (
        "Use prior provisional research context and the compact Moltbook source trace; "
        "treat Moltbook as external context, not factual authority."
        if moltbook_context
        else "Use prior provisional research context only; do not collect external sources."
    )
    return (
        "Run one bounded research pass against this existing research "
        f"open loop. Next action: {loop.get('next_action') or 'None'}. "
        f"Source artifact: {source_context.get('artifact_id') or 'None'}. "
        f"{source_instruction}"
    )


def _bounded_artifact_metadata(
    *,
    result: dict,
    evaluation: BoundedOpenLoopEvaluation,
    source_context: dict,
    moltbook_context: dict | None,
    open_loop_iteration: int,
) -> dict:
    loop = evaluation.loop
    metadata = evaluation.metadata or {}
    artifact_metadata = {
        "artifact_type": "research_note",
        "origin": "manual_research",
        "source_type": "research",
        "source_role": "research_reference",
        "research_question": result["question"],
        "research_title": result["title"],
        "research_date": _research_date(result["created_at"]),
        "created_by": "admin_cli",
        "research_version": BOUNDED_RESEARCH_VERSION,
        "provisional": True,
        "open_loop_id": loop["open_loop_id"],
        "open_loop_title": loop["title"],
        "open_loop_iteration": open_loop_iteration,
        "bounded_research_mode": BOUNDED_RESEARCH_MODE,
        "global_daily_cap_class": "research",
        "source_open_loop_generation_method": metadata.get("generation_method"),
    }
    if source_context.get("artifact_id"):
        artifact_metadata["source_research_artifact_id"] = source_context["artifact_id"]
    if moltbook_context:
        artifact_metadata.update(
            {
                "moltbook_source_trace_path": moltbook_context["trace_path"],
                "moltbook_source_count": moltbook_context["source_count"],
                "moltbook_collection_error": moltbook_context["collection_error"],
                "moltbook_no_usable_results": moltbook_context["no_usable_results"],
                "moltbook_no_external_write_confirmed": moltbook_context[
                    "no_external_write_confirmed"
                ],
                "moltbook_verification_status_is_metadata_only": moltbook_context[
                    "verification_status_is_metadata_only"
                ],
            }
        )
        if moltbook_context.get("query"):
            artifact_metadata["moltbook_query"] = moltbook_context["query"]
        if moltbook_context.get("feed"):
            artifact_metadata["moltbook_feed"] = True
            artifact_metadata["moltbook_sort"] = moltbook_context.get("sort")
    return artifact_metadata


def generate_bounded_research_open_loop_note(
    *,
    evaluation: BoundedOpenLoopEvaluation,
    source_context: dict,
    moltbook_context: dict | None = None,
    model: str | None = None,
    ollama_host: str = OLLAMA_HOST,
) -> dict:
    """Generate a dry-run bounded research note for one eligible open loop."""
    question = _loop_question(evaluation.loop, evaluation.metadata)
    if not question:
        raise BoundedResearchError("Open loop has no research question")
    title = derive_research_title(question)
    scope = _bounded_research_scope(evaluation, source_context, moltbook_context)
    created_at = _now()
    messages = build_bounded_research_messages(
        title=title,
        question=question,
        scope=scope,
        evaluation=evaluation,
        source_context=source_context,
        moltbook_context=moltbook_context,
    )
    raw = chat_completion_text(
        messages,
        model=model or CHAT_MODEL,
        ollama_host=ollama_host,
        role="default",
    )
    document = build_bounded_research_document(
        title=title,
        question=question,
        scope=scope,
        created_at=created_at,
        body=raw,
        evaluation=evaluation,
        source_context=source_context,
        moltbook_context=moltbook_context,
    )
    open_loop_iteration = evaluation.effective_daily_iteration_count + 1
    result = {
        "ok": True,
        "mode": "dry-run",
        "research_version": BOUNDED_RESEARCH_VERSION,
        "title": title,
        "question": question,
        "scope": scope,
        "created_at": created_at,
        "relative_path": research_relative_path(created_at, title),
        "document": document,
        "open_loop": evaluation.to_dict(),
        "source_context": {
            key: value
            for key, value in source_context.items()
            if key not in {"artifact", "content"}
        },
        "moltbook_context": moltbook_context,
        "artifact_metadata": {},
    }
    result["artifact_metadata"] = _bounded_artifact_metadata(
        result=result,
        evaluation=evaluation,
        source_context=source_context,
        moltbook_context=moltbook_context,
        open_loop_iteration=open_loop_iteration,
    )
    return result


def _completion_metadata(
    *,
    evaluation: BoundedOpenLoopEvaluation,
    result: dict,
    completed_at: str,
    current_local_date: str,
) -> dict:
    metadata = dict(evaluation.metadata or {})
    metadata["daily_iteration_limit"] = evaluation.daily_iteration_limit
    metadata["daily_iteration_count"] = evaluation.effective_daily_iteration_count + 1
    metadata["daily_iteration_local_date"] = current_local_date
    metadata["last_researched_at"] = completed_at
    metadata["last_research_path"] = result["relative_path"]
    metadata["last_research_result"] = "completed"
    artifact_result = result.get("artifact_result")
    if artifact_result:
        metadata["last_research_artifact_id"] = artifact_result["artifact"]["artifact_id"]
    moltbook_context = result.get("moltbook_context")
    if moltbook_context:
        metadata["last_moltbook_source_trace_path"] = moltbook_context["trace_path"]
        metadata["last_moltbook_source_count"] = moltbook_context["source_count"]
        metadata["last_moltbook_collection_error"] = moltbook_context["collection_error"]
    return metadata


def _preflight_workspace_path_available(relative_path: str, *, workspace_root: Path) -> None:
    target = resolve_workspace_path(relative_path, Path(workspace_root))
    if target.exists():
        raise BoundedResearchError(f"Workspace file already exists: {relative_path}")


def _mark_open_loop_completed(
    *,
    open_loop_id: str,
    result: dict,
    current_local_date: str,
) -> dict:
    evaluation = _require_eligible_open_loop(
        open_loop_id,
        current_local_date=current_local_date,
    )
    completed_at = _now()
    metadata = _completion_metadata(
        evaluation=evaluation,
        result=result,
        completed_at=completed_at,
        current_local_date=current_local_date,
    )
    updated = update_open_loop_metadata(open_loop_id, metadata)
    return {
        "open_loop": updated,
        "completed_at": completed_at,
        "metadata": metadata,
    }


def run_bounded_research_open_loop(
    *,
    open_loop_id: str,
    write: bool = False,
    register_artifact: bool = False,
    model: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
    current_local_date: str | None = None,
    use_moltbook: bool = False,
    moltbook_query: str | None = None,
    moltbook_feed: bool = False,
    moltbook_limit: int | None = None,
    moltbook_sort: str = "new",
    moltbook_registry=None,
) -> dict:
    """Run one bounded research iteration against a specific open loop."""
    if register_artifact and not write:
        raise BoundedResearchError("--register-artifact requires --write")
    moltbook_options = _normalize_moltbook_options(
        use_moltbook=use_moltbook,
        moltbook_query=moltbook_query,
        moltbook_feed=moltbook_feed,
        moltbook_limit=moltbook_limit,
        moltbook_sort=moltbook_sort,
    )

    current_local_date = current_local_date or _current_local_date()
    evaluation = _require_eligible_open_loop(
        open_loop_id,
        current_local_date=current_local_date,
    )
    source_context = load_bounded_research_source_context(
        evaluation.loop,
        evaluation.metadata or {},
        workspace_root=workspace_root,
    )
    moltbook_context = collect_bounded_moltbook_source_context(
        options=moltbook_options,
        workspace_root=workspace_root,
        registry=moltbook_registry,
    )
    result = generate_bounded_research_open_loop_note(
        evaluation=evaluation,
        source_context=source_context,
        moltbook_context=moltbook_context,
        model=model,
    )
    result["mode"] = "write" if write else "dry-run"
    result["register_artifact_requested"] = register_artifact

    if not write:
        return result

    # Revalidate immediately before writing in case another run used the loop.
    _require_eligible_open_loop(open_loop_id, current_local_date=current_local_date)
    _preflight_workspace_path_available(result["relative_path"], workspace_root=workspace_root)
    if moltbook_context:
        _preflight_workspace_path_available(
            moltbook_context["trace_path"],
            workspace_root=workspace_root,
        )
    try:
        if moltbook_context:
            result["moltbook_trace_write_result"] = write_source_trace(
                moltbook_context["trace"],
                workspace_root=workspace_root,
            )
        result["write_result"] = write_manual_research_note(
            result,
            workspace_root=workspace_root,
        )
        if register_artifact:
            result["artifact_result"] = register_manual_research_artifact(
                result,
                workspace_root=workspace_root,
            )
    except (ManualResearchError, MoltbookSourcePreviewError) as exc:
        raise BoundedResearchError(str(exc)) from exc

    # Revalidate again before marking the loop completed. If this fails, the
    # durable note remains but the loop is not silently advanced.
    result["open_loop_update"] = _mark_open_loop_completed(
        open_loop_id=open_loop_id,
        result=result,
        current_local_date=current_local_date,
    )
    return result


def run_next_bounded_research_open_loop(
    *,
    write: bool = False,
    register_artifact: bool = False,
    model: str | None = None,
    workspace_root: Path = WORKSPACE_DIR,
    current_local_date: str | None = None,
    use_moltbook: bool = False,
    moltbook_query: str | None = None,
    moltbook_feed: bool = False,
    moltbook_limit: int | None = None,
    moltbook_sort: str = "new",
    moltbook_registry=None,
) -> dict:
    """Plan and run at most one eligible bounded research open loop."""
    if register_artifact and not write:
        raise BoundedResearchError("--register-artifact requires --write")

    current_local_date = current_local_date or _current_local_date()
    plan = plan_next_bounded_research_open_loop(current_local_date=current_local_date)
    selected = plan.get("selected")
    if selected is None:
        return {
            "ok": True,
            "mode": "write" if write else "dry-run",
            "research_version": BOUNDED_RESEARCH_VERSION,
            "run_next": True,
            "ran": False,
            "selected": None,
            "plan": plan,
            "message": "No eligible bounded research open loops found.",
        }

    open_loop_id = selected["open_loop"]["open_loop_id"]
    result = run_bounded_research_open_loop(
        open_loop_id=open_loop_id,
        write=write,
        register_artifact=register_artifact,
        model=model,
        workspace_root=workspace_root,
        current_local_date=current_local_date,
        use_moltbook=use_moltbook,
        moltbook_query=moltbook_query,
        moltbook_feed=moltbook_feed,
        moltbook_limit=moltbook_limit,
        moltbook_sort=moltbook_sort,
        moltbook_registry=moltbook_registry,
    )
    result["run_next"] = True
    result["ran"] = True
    result["selected"] = selected
    result["plan"] = {
        "current_local_date": plan["current_local_date"],
        "eligible_count": plan["eligible_count"],
        "skipped_count": plan["skipped_count"],
        "total_count": plan["total_count"],
        "skipped_count_by_reason": plan["skipped_count_by_reason"],
        "global_daily_cap": plan["global_daily_cap"],
    }
    return result
