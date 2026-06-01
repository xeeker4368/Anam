# Deduplicate greeting helper + add no-persist warning log — v1

Date: 2026-05-31

## Summary

The greeting helper (`_GREETING_PATTERNS` + `_is_greeting`) was defined
byte-for-byte identically in both `tir/engine/context.py` and
`tir/api/routes.py`. This patch consolidates it into a single public
`is_greeting` in `context.py`, which `routes.py` now imports. It also replaces
the only fully silent no-persist path in the chat stream — the bare `pass` in
the `if loop_result is None:` branch — with a `logger.warning`, without changing
control flow. The generated prompt-inventory doc was regenerated to reflect
shifted line numbers in `routes.py`.

## Files changed

- `tir/engine/context.py`
  - Renamed `_is_greeting` → public `is_greeting` (single source of truth).
    `_GREETING_PATTERNS` stays module-internal; its content is unchanged.
  - Updated the internal caller in `build_system_prompt_with_debug` to use
    `is_greeting`.
- `tir/api/routes.py`
  - Deleted the duplicate `_GREETING_PATTERNS` / `_is_greeting` definitions and
    the now-orphaned `# Greeting detection (matches context.py)` comment header.
  - Added `is_greeting` to the existing `from tir.engine.context import (...)`.
  - Updated the retrieval-skip caller to use the imported `is_greeting`.
  - Replaced the bare `pass` in the `if loop_result is None:` assistant-persist
    branch with `logger.warning("Agent loop returned no result; no assistant
    message was persisted")`. Control flow is unchanged: still no persist, no
    new yield to the client.
- `docs/PROMPT_INVENTORY.md`
  - Regenerated via `scripts/extract_prompt_inventory.py` (the canonical
    generator). The only change is two `routes.py` line numbers shifting down by
    12 (817→805, 836→824) from the deleted greeting block. No prompt content
    changed. Keeps `tests/test_prompt_inventory.py` green.

## Behavior changed

- Greeting detection is now defined once. The pattern set and matching logic
  (`.strip().lower().rstrip("!?.,'\"")` membership test) are identical to before;
  consolidation is behavior-preserving.
- The previously-silent `loop_result is None` no-persist path now emits a warning
  log. It still does not persist an assistant message and yields nothing new to
  the client.

## Tests / checks run

- `grep -rn "_is_greeting\|_GREETING_PATTERNS" --include="*.py" .` → only the
  internal `_GREETING_PATTERNS` set in `context.py` remains; exactly one
  `is_greeting` definition exists (`context.py`), imported by `routes.py`. No
  duplicate function remains.
- Regenerated inventory diff confirmed to be line-number-only (no prompt-content
  change) before writing the doc.
- Full suite: `python -m pytest -q` → **838 passed**, 133 pre-existing
  deprecation warnings (chromadb / FastAPI `on_event`), unrelated to this change.

## Known limitations

- No test referenced the greeting helper before or after this change, so the
  rename is covered only indirectly (via the chat-stream and prompt-build paths
  exercised by the existing suite).
- The warning log is informational only; it does not change error reporting or
  the trace record (the line-882 `loop_result is None` trace branch that sets
  `error_type = "stream_exception"` is untouched and continues to fire).

## Follow-up work

- Out of scope here: improving greeting detection, changing retrieval-skip
  behavior, touching other persist branches (`complete`, `iteration_limit`,
  `error`), and the unbounded-conversation-history issue.

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? Yes — persistence behavior is unchanged; the None
   path now merely logs that nothing was persisted.
5. Are derived artifacts traceable? Yes — `docs/PROMPT_INVENTORY.md` was
   regenerated from source via its canonical generator script.
6. Are tool calls recorded? Unaffected.
7. Are created artifacts remembered? Unaffected.
8. Is context construction inspectable? Yes — greeting/retrieval-skip logic is
   now single-sourced and easier to inspect; the no-persist path is now visible
   in logs.
9. Does this make autonomy more cumulative? Neutral.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No — no schema change.
12. Tests run? Full suite (838 passed).
13. Change core substrate behavior unnecessarily? No — dedup + one log line.
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
