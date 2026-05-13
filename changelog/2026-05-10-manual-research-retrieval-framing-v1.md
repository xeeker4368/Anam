# Manual Research Retrieval Framing v1

## Summary

Retrieved manual research notes now use explicit provisional research framing in runtime context.

## Files Changed

- `tir/engine/context.py`
- `tests/test_context.py`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-10-manual-research-retrieval-framing-v1.md`

## Behavior Changed

- Retrieved chunks with `source_type=research` or `source_role=research_reference` are labeled as:
  - `[Research you wrote on <date> — working research notes]`
  - `[Research you wrote on <date>: <title> — working research notes]`
- Research labels prefer `research_date` and `research_title` metadata, with a graceful fallback to `created_at`.
- Research reference chunks are not formatted as project reference documents or generic artifact sources.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py tests/test_context_budget.py -v`
- `.pyanam/bin/python -m pytest tests/test_manual_research.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest` — 604 passed
- `git diff --check` — passed

## Known Limitations

- This patch changes retrieval framing only.
- It does not change registration, indexing, ranking, artifact metadata, web search, open-loop creation, review-item creation, or scheduler behavior.

## Follow-Up Work

- Consider a later source-framing audit for retrieved research if working-theory or supersession paths are added.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality.
- Preserved research notes as provisional working material rather than truth, guidance, self-understanding, or project decisions.
- Did not change governance files or runtime prompt guidance.
