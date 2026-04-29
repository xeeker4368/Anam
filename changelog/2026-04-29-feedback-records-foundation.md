# Feedback Records Foundation

## Summary

Added an internal-only feedback records registry for storing structured user corrections, approvals, rejections, disputed outputs, inaccurate memory/tool signals, and related substrate-level learning evidence.

## Files Changed

- `tir/memory/db.py`
- `tir/feedback/__init__.py`
- `tir/feedback/service.py`
- `tests/test_feedback.py`
- `tests/test_db.py`
- `changelog/2026-04-29-feedback-records-foundation.md`

## Behavior Changed

- Added a working-db-only `feedback_records` table and indexes.
- Added internal feedback service operations:
  - `create_feedback_record(...)`
  - `get_feedback_record(feedback_id)`
  - `list_feedback_records(...)`
  - `update_feedback_status(feedback_id, status)`
- Feedback records can optionally link to artifacts and open loops.
- Conversation, message, target, and tool references are stored as loose metadata.
- `resolved_at` is set when status becomes `resolved` or `archived`.
- `resolved_at` is cleared when status becomes `open`, `accepted`, or `disputed`.
- Feedback metadata is not indexed, chunked, stored, or retrieved as memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_feedback.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_open_loops.py tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- No LLM tools, API routes, or UI.
- No behavior-changing learning system.
- No automatic diagnostic issues.
- No automatic operational guidance updates.
- No memory indexing/chunking.
- No autonomy or self-modification behavior.

## Follow-up Work

- Add review flows that can intentionally interpret feedback records.
- Add explicit diagnostics or open-loop creation only after approval.
- Add operational guidance update proposals only through a later reviewed process.

## Project Anam Alignment Check

- Did not expose LLM tools.
- Did not add API routes or UI.
- Did not add memory indexing/chunking.
- Did not automatically create diagnostic issues.
- Did not automatically modify operational guidance.
- Did not add document ingestion, web search, Moltbook, image generation, autonomy, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
