# Context Assembly Debug Detail

## Summary

Added structured backend debug metadata for context sizing, retrieval composition, retrieval budget usage, and journal chunk visibility.

## Files Changed

- `tir/api/routes.py`
- `tir/engine/context_budget.py`
- `tir/engine/context_debug.py`
- `tests/test_api_agent_stream.py`
- `tests/test_context.py`
- `tests/test_context_budget.py`

## Behavior Changed

- Added `context_debug` to the initial `/api/chat/stream` debug event.
- Preserved existing top-level debug fields for compatibility.
- Split retrieval budget skip metadata into empty-skip and budget-skip counts while preserving `skipped_chunks`.
- Added safe retrieved chunk snippets and metadata subsets for debug inspection.
- Added journal-specific chunk debug fields for retrieved journal memory.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context_budget.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`

## Known Limitations

- `full_journal_included` is currently `null` because total journal chunk counts are not stored in chunk metadata.
- Frontend rendering was not changed; the new data is visible through the existing raw debug object.
- Debug snippets are intentionally truncated and do not expose the full raw prompt.

## Follow-Up Work

- Add frontend rendering for `context_debug` if raw debug inspection is too cumbersome.
- Consider recording total journal chunk count during journal indexing to make `full_journal_included` exact.

## Project Anam Alignment Check

- Does not change retrieval ranking, prompt wording, journal indexing, or database schema.
- Improves context construction inspectability.
- Preserves raw experience and source framing.
- Does not assign the entity a name or fixed personality.
