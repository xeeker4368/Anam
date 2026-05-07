## Summary

Added a working-db-only operator review queue foundation for recording items that may need human attention, such as research seeds, contradictions, corrections, artifact issues, tool failures, memory issues, decisions, and safety notes.

## Files Changed

- `tir/memory/db.py`
- `tir/review/__init__.py`
- `tir/review/service.py`
- `tir/admin.py`
- `tests/test_review_queue.py`

## Behavior Changed

- Added a `review_items` table in `working.db`.
- Added review queue service functions:
  - `create_review_item(...)`
  - `get_review_item(...)`
  - `list_review_items(...)`
  - `update_review_item_status(...)`
- Added admin CLI commands:
  - `review-list`
  - `review-add`
  - `review-update`
- Review item metadata round-trips as parsed `metadata`.
- `reviewed_at` is set when status becomes `reviewed`, `dismissed`, or `resolved`.
- `reviewed_at` is cleared when status returns to `open`.

## Schema Added

Added working-db table:

- `review_items`

Indexes:

- `idx_review_items_status`
- `idx_review_items_category`
- `idx_review_items_priority`
- `idx_review_items_artifact`
- `idx_review_items_conversation`
- `idx_review_items_created_at`

No `archive.db`, Chroma, or FTS schema changes were made.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_review_queue.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- No API endpoints were added.
- No UI was added.
- No model tool can create review items.
- No automatic review item creation exists.
- Review items are not indexed into Chroma or FTS.

## Follow-Up Work

- Add read-only API visibility once the operator workflow is stable.
- Add UI visibility in a separate explicitly scoped patch.
- Consider later reviewed/approved promotion paths into research, reflection, or open-loop workflows.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not add autonomous research, scheduling, background workers, or self-modification.
- Preserved operator control and did not create model tool access.
- Preserved raw memory and existing memory architecture.
- Did not rename `tir/`.
