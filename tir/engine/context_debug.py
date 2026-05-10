"""Structured debug helpers for context assembly."""

from collections import Counter, defaultdict


_SNIPPET_CHARS = 240
_METADATA_DEBUG_KEYS = {
    "artifact_id",
    "journal_date",
    "title",
    "filename",
    "path",
    "chunk_index",
    "chunk_kind",
    "source_type",
    "source_trust",
    "origin",
    "source_role",
    "created_at",
}


def _source_type(chunk: dict) -> str:
    return (
        chunk.get("metadata", {}).get("source_type")
        or chunk.get("source_type")
        or "unknown"
    )


def _snippet(text: str | None) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= _SNIPPET_CHARS:
        return normalized
    return normalized[:_SNIPPET_CHARS].rstrip() + "..."


def _metadata_subset(chunk: dict) -> dict:
    metadata = chunk.get("metadata") or {}
    subset = {
        key: metadata.get(key)
        for key in sorted(_METADATA_DEBUG_KEYS)
        if metadata.get(key) not in (None, "")
    }
    if chunk.get("created_at") and "created_at" not in subset:
        subset["created_at"] = chunk.get("created_at")
    return subset


def _journal_debug(chunk: dict, journal_counts: dict) -> dict | None:
    if _source_type(chunk) != "journal":
        return None
    metadata = chunk.get("metadata") or {}
    journal_date = metadata.get("journal_date")
    key = metadata.get("artifact_id") or journal_date or chunk.get("chunk_id")
    return {
        "artifact_id": metadata.get("artifact_id"),
        "journal_date": journal_date,
        "title": metadata.get("title"),
        "chunk_index": metadata.get("chunk_index"),
        "chunk_kind": metadata.get("chunk_kind"),
        "chunks_included_for_journal": journal_counts.get(key, 1),
        "full_journal_included": None,
    }


def prompt_section_chars(prompt_breakdown: dict) -> dict:
    """Map existing prompt breakdown fields into a stable debug shape."""
    return {
        "soul": prompt_breakdown.get("soul_chars", 0),
        "operational_guidance": prompt_breakdown.get("operational_guidance_chars", 0),
        "behavioral_guidance": prompt_breakdown.get("behavioral_guidance_chars", 0),
        "tools": prompt_breakdown.get("tool_descriptions_chars", 0),
        "retrieved_memories": prompt_breakdown.get("retrieved_context_chars", 0),
        "conversation_history": prompt_breakdown.get("conversation_history_chars", 0),
        "artifact_context": prompt_breakdown.get("artifact_context_chars", 0),
        "selection_context": prompt_breakdown.get("selection_context_chars", 0),
        "current_situation": prompt_breakdown.get("situation_chars", 0),
        "other": prompt_breakdown.get("other_chars", 0),
    }


def build_context_debug(
    *,
    prompt_breakdown: dict,
    retrieval_skipped: bool,
    retrieval_policy: dict,
    query: str,
    retrieved_chunks: list[dict],
    retrieval_budget: dict,
    primary_context: dict | None = None,
) -> dict:
    """Build safe, structured context assembly debug metadata."""
    source_counts = Counter(_source_type(chunk) for chunk in retrieved_chunks)
    journal_counts = defaultdict(int)
    for chunk in retrieved_chunks:
        if _source_type(chunk) != "journal":
            continue
        metadata = chunk.get("metadata") or {}
        key = metadata.get("artifact_id") or metadata.get("journal_date") or chunk.get("chunk_id")
        journal_counts[key] += 1

    included = []
    for rank, chunk in enumerate(retrieved_chunks, start=1):
        metadata = _metadata_subset(chunk)
        entry = {
            "rank": rank,
            "chunk_id": chunk.get("chunk_id", ""),
            "source_type": _source_type(chunk),
            "chars": len(chunk.get("text") or ""),
            "snippet": _snippet(chunk.get("text")),
            "vector_distance": chunk.get("vector_distance"),
            "vector_rank": chunk.get("vector_rank"),
            "bm25_rank": chunk.get("bm25_rank"),
            "adjusted_score": chunk.get("adjusted_score"),
            "metadata": metadata,
        }
        journal = _journal_debug(chunk, journal_counts)
        if journal:
            entry["journal"] = journal
        included.append(entry)

    budget_chars = retrieval_budget.get("max_chars", 0)
    used_chars = retrieval_budget.get("used_chars", 0)
    return {
        "prompt_total_chars": prompt_breakdown.get("total_chars")
        or prompt_breakdown.get("system_prompt_chars", 0),
        "prompt_section_chars": prompt_section_chars(prompt_breakdown),
        "retrieval": {
            "enabled": not retrieval_skipped,
            "skipped": retrieval_skipped,
            "policy": retrieval_policy,
            "query": query,
            "items_considered": retrieval_budget.get("input_chunks", len(retrieved_chunks)),
            "items_included": retrieval_budget.get("included_chunks", len(retrieved_chunks)),
            "items_skipped": retrieval_budget.get("skipped_chunks", 0),
            "items_truncated": retrieval_budget.get("truncated_chunks", 0),
            "sources_by_type": dict(sorted(source_counts.items())),
            "included_chunks": included,
        },
        "context_budget": {
            "budget_chars": budget_chars,
            "used_chars": used_chars,
            "remaining_chars": max(0, budget_chars - used_chars),
            "input_chunks": retrieval_budget.get("input_chunks", len(retrieved_chunks)),
            "included_chunks": retrieval_budget.get("included_chunks", len(retrieved_chunks)),
            "skipped_chunks": retrieval_budget.get("skipped_chunks", 0),
            "skipped_empty_chunks": retrieval_budget.get("skipped_empty_chunks", 0),
            "skipped_budget_chunks": retrieval_budget.get("skipped_budget_chunks", 0),
            "truncated_chunks": retrieval_budget.get("truncated_chunks", 0),
        },
        "primary_context": primary_context or {},
    }
