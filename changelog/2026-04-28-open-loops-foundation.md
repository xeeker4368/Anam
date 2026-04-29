# Open Loops Foundation

## Summary

Added an internal-only open-loops registry for tracking unfinished, interrupted, unresolved, or worth-revisiting threads as continuity metadata.

## Files Changed

- `tir/memory/db.py`
- `tir/open_loops/__init__.py`
- `tir/open_loops/service.py`
- `tests/test_open_loops.py`
- `tests/test_db.py`
- `changelog/2026-04-28-open-loops-foundation.md`

## Behavior Changed

- Added a working-db-only `open_loops` table and indexes.
- Added internal open-loop service operations:
  - `create_open_loop(...)`
  - `get_open_loop(open_loop_id)`
  - `list_open_loops(...)`
  - `update_open_loop_status(open_loop_id, status)`
- Open loops can optionally link to an artifact through `related_artifact_id`.
- Conversation and message references are stored as loose metadata.
- `closed_at` is set when status becomes `closed` or `archived`.
- `closed_at` is cleared when status becomes `open`, `in_progress`, or `blocked`.
- Open-loop metadata is not indexed, chunked, stored, or retrieved as memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_open_loops.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- No LLM tools, API routes, or UI.
- No autonomy or scheduled continuation behavior.
- No memory indexing/chunking.
- No artifact content reads.
- No workspace operations.
- Open loops are continuity markers only, not a general task manager.

## Follow-up Work

- Add read-only debug/admin visibility if approved later.
- Add intentional summarization or archival flows only after explicit design approval.
- Connect open loops to artifact-producing flows only when those flows are approved.

## Project Anam Alignment Check

- Did not expose LLM tools.
- Did not add API routes or UI.
- Did not add memory indexing/chunking.
- Did not read artifact contents.
- Did not perform workspace operations.
- Did not add document ingestion, web search, Moltbook, image generation, autonomy, or self-modification.
- Did not rename `tir/`.
- Did not modify `soul.md`.
- Did not modify operational guidance.
