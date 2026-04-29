# Diagnostic Issues Foundation

## Summary

Added an internal-only diagnostic issue registry for evidence-backed substrate, tool, retrieval, memory, workflow, UI, and behavior issues that may require investigation or future correction.

## Files Changed

- `tir/memory/db.py`
- `tir/diagnostics/__init__.py`
- `tir/diagnostics/service.py`
- `tests/test_diagnostics.py`
- `tests/test_db.py`
- `changelog/2026-04-29-diagnostic-issues-foundation.md`

## Behavior Changed

- Added a working-db-only `diagnostic_issues` table and indexes.
- Added internal diagnostic service operations:
  - `create_diagnostic_issue(...)`
  - `get_diagnostic_issue(diagnostic_id)`
  - `list_diagnostic_issues(...)`
  - `update_diagnostic_status(diagnostic_id, status)`
- Diagnostic issues can optionally link to feedback records, open loops, and artifacts.
- Conversation, message, tool, and target references are stored as loose metadata.
- `title` and `evidence_summary` are required.
- `resolved_at` is set when status becomes `resolved` or `archived`.
- `resolved_at` is cleared when status becomes `open`, `investigating`, or `blocked`.
- Diagnostic metadata is not indexed, chunked, stored, or retrieved as memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_diagnostics.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- No LLM tools, API routes, or UI.
- No automatic diagnostic issue creation from feedback or tool failures.
- No automatic self-modification proposals.
- No automatic operational guidance updates.
- No memory indexing/chunking.
- Diagnostic issues are evidence-backed problem records only, not a task manager or research queue.

## Follow-up Work

- Add reviewed flows for creating diagnostic issues from feedback or tool failures if approved.
- Add diagnostic review or reporting surfaces only after explicit UI/API design.
- Connect diagnostic issues to self-modification proposals only through a later reviewed process.

## Project Anam Alignment Check

- Did not expose LLM tools.
- Did not add API routes or UI.
- Did not add memory indexing/chunking.
- Did not automatically create diagnostic issues from feedback or tool failures.
- Did not automatically create self-modification proposals.
- Did not automatically modify operational guidance.
- Did not add document ingestion, web search, Moltbook, image generation, autonomy, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
