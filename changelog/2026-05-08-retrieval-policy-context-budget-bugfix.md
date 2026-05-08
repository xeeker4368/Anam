# Retrieval Policy and Context Budget Bugfix

## Summary

Fixed retrieval-policy edge cases for project/internal questions and tightened context-budget handling for empty retrieved chunks.

## Files Changed

- `tir/engine/retrieval_policy.py`
- `tir/engine/context_budget.py`
- `tests/test_retrieval_policy.py`
- `tests/test_context_budget.py`
- `changelog/2026-05-08-retrieval-policy-context-budget-bugfix.md`

## Behavior Changed

- Project/internal prompts now keep normal memory retrieval even when they contain words like latest, current, or today.
- Direct web/current prompts still skip memory when they are not project/internal.
- Bare discussion of the phrase "system prompt" no longer triggers context-inspection mode.
- Explicit prompt/context inspection requests still skip memory.
- Retrieved chunks with missing, `None`, non-string, empty, or whitespace-only text are skipped and counted as skipped.
- Context-budget skipped-count accounting is simpler and avoids including empty chunks.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_retrieval_policy.py -v`
- `.pyanam/bin/python -m pytest tests/test_context_budget.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- Project/internal intent is still keyword-based.
- Context-inspection detection is still phrase-pattern based and may need future tuning.

## Follow-up Work

- Consider precompiled regexes if retrieval policy grows more complex.
- Add route-level regression tests only if future stream behavior regresses around these policies.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not modify `soul.md` or `BEHAVIORAL_GUIDANCE.md`.
- Does not change memory architecture, retrieval budgets, DB schema, or tool behavior.
