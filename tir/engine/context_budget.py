"""Context budgeting helpers for automatic retrieval."""

AUTO_RETRIEVAL_RESULTS = 8
RETRIEVED_CONTEXT_CHAR_BUDGET = 14000
PROMPT_BUDGET_WARNING_CHARS = 30000
MAX_RETRIEVED_CHUNK_CHARS = 3000

_TRUNCATION_MARKER = "\n\n[retrieved chunk truncated]"
_MIN_USEFUL_REMAINING_CHARS = 500


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to fit max_chars including the truncation marker."""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(_TRUNCATION_MARKER):
        return text[:max_chars]
    return text[: max_chars - len(_TRUNCATION_MARKER)].rstrip() + _TRUNCATION_MARKER


def budget_retrieved_chunks(
    chunks,
    max_chars: int = RETRIEVED_CONTEXT_CHAR_BUDGET,
    max_chunk_chars: int = MAX_RETRIEVED_CHUNK_CHARS,
) -> tuple[list[dict], dict]:
    """Apply a character budget to ranked retrieved chunks.

    Returns a shallow-copied chunk list with text possibly truncated, plus
    budget metadata for debug visibility.
    """
    input_chunks = list(chunks or [])
    budgeted = []
    used_chars = 0
    skipped_chunks = 0
    skipped_empty_chunks = 0
    skipped_budget_chunks = 0
    truncated_chunks = 0

    for index, chunk in enumerate(input_chunks):
        original_text = chunk.get("text")
        if not isinstance(original_text, str) or not original_text.strip():
            skipped_chunks += 1
            skipped_empty_chunks += 1
            continue

        candidate_text = _truncate_text(original_text, max_chunk_chars)
        was_truncated = candidate_text != original_text
        remaining = max_chars - used_chars

        if len(candidate_text) > remaining:
            if remaining > _MIN_USEFUL_REMAINING_CHARS:
                candidate_text = _truncate_text(original_text, remaining)
                was_truncated = candidate_text != original_text
            else:
                skipped_chunks += 1
                skipped_budget_chunks += 1
                continue

        next_chunk = dict(chunk)
        next_chunk["text"] = candidate_text
        budgeted.append(next_chunk)
        used_chars += len(candidate_text)
        if was_truncated:
            truncated_chunks += 1

        if used_chars >= max_chars:
            remaining_chunks = len(input_chunks) - index - 1
            skipped_chunks += remaining_chunks
            skipped_budget_chunks += remaining_chunks
            break

    metadata = {
        "input_chunks": len(input_chunks),
        "included_chunks": len(budgeted),
        "skipped_chunks": skipped_chunks,
        "skipped_empty_chunks": skipped_empty_chunks,
        "skipped_budget_chunks": skipped_budget_chunks,
        "truncated_chunks": truncated_chunks,
        "max_chars": max_chars,
        "used_chars": used_chars,
    }
    return budgeted, metadata
