## Summary

Added prompt section breakdown metadata to chat debug output so prompt character usage can be inspected before further latency tuning.

## Files Changed

- `tir/engine/context.py`
- `tir/api/routes.py`
- `tests/test_context.py`
- `tests/test_api_agent_stream.py`

## Behavior Changed

- Added `build_system_prompt_with_debug(...)`, which returns the same system prompt as `build_system_prompt(...)` plus best-effort character counts by prompt section.
- `/api/chat/stream` debug events now include `prompt_breakdown`.
- Prompt breakdown includes system prompt sections, conversation history characters, Moltbook selection context characters, artifact context placeholder characters, total characters, and non-negative `other_chars`.
- Existing prompt content, ordering, separators, retrieval behavior, memory architecture, and model behavior are unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Counts are character counts, not token counts.
- Breakdown is marked best-effort because model input formatting and separators add wrapper overhead.
- `artifact_context_chars` is currently reported as `0` because there is no separate artifact context block in this path yet.

## Follow-Up Work

- Use the breakdown to identify whether the next optimization should target tool descriptions, operational guidance, retrieved memory, or history.
- Add frontend-specific rendering only if the existing debug panel does not expose nested debug fields clearly.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not change memory architecture, DB schema, Chroma, or FTS.
- Preserved inspectable context construction.
- Did not rename `tir/`.
