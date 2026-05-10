# Reflection Journal Relevant Memory Retrieval

## Summary

Added an optional `--include-memory` path for manual reflection journals so a journal can receive bounded prior remembered context when explicitly requested.

## Files Changed

- `tir/reflection/journal.py`
- `tir/admin.py`
- `tests/test_reflection_journal.py`
- `tests/test_admin.py`
- `changelog/2026-05-09-reflection-journal-relevant-memory.md`

## Behavior Changed

- `reflection-journal-day` accepts `--include-memory`.
- Default journal behavior remains unchanged when the flag is omitted.
- When enabled, the journal command builds a deterministic bounded query from the selected day/window material and retrieves a small set of prior memory chunks.
- Current-window conversation chunks and same-date journal chunks are filtered out before prompt inclusion.
- Prior-date journal chunks may be included as relevant remembered context.
- Retrieved memory is labeled as context, not instructions.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_reflection_journal.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Query construction is deterministic and intentionally simple; it may miss subtle related memories.
- Retrieval filtering is post-retrieval and does not alter global ranking behavior.
- Prior journal memories can still carry earlier reflection errors; source framing is explicit but not a substitute for judgment.

## Follow-Up Work

- Add richer debug output for reflection memory selection if needed.
- Consider section-aware prior journal retrieval after observing use.
- Evaluate whether generated journals should summarize how prior memories influenced reflection.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Preserves raw experience and existing memory architecture.
- Does not mutate `BEHAVIORAL_GUIDANCE.md`.
- Keeps journaling manual/admin-triggered with no scheduler or background automation.
