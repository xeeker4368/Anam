# Journal Date Retrieval Grounding

## Summary

Added primary reflection journal context for explicit journal-date questions so the actual journal artifact/file is supplied before the current user message.

## Files Changed

- `tir/engine/journal_context.py`
- `tir/engine/context_debug.py`
- `tir/api/routes.py`
- `tests/test_journal_context.py`
- `tests/test_api_agent_stream.py`
- `changelog/2026-05-09-journal-date-retrieval-grounding.md`

## Behavior Changed

- Date-specific journal prompts such as "May 8 reflection journal" or "2026-05-08 journal" can now load the registered journal artifact as primary context.
- Normal memory retrieval still runs; retrieved memories are not deleted, suppressed, or downranked.
- The initial stream debug event includes `journal_primary_context`.
- `context_debug.primary_context.journal` exposes safe metadata for the inserted primary journal context.
- Prompt breakdown includes `journal_primary_context_chars` and `primary_context_chars`.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_journal_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- Month/day date inference uses the current local/system year and can choose the wrong year.
- Missing journal files are not reconstructed from indexed chunks in v1.
- Large journals are first-N truncated; section-aware journal loading is deferred.
- Normal retrieval may still include prior conversations about the journal.

## Follow-Up Work

- Add section-aware journal loading for large entries.
- Consider richer date parsing only after explicit design.
- Evaluate whether prior conversations about a requested journal should be downranked after observing the primary-source behavior.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Preserves raw experience and retrieval records.
- Keeps journal artifacts source-framed as reflective memory.
- Adds inspectable context/debug metadata without changing schema or autonomy behavior.
