# Runtime Situation Label Cleanup v1

## Summary

Changed runtime current-situation labels so they describe the current mode and
context without using `You are...` phrasing.

## Files Changed

- `tir/engine/context.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_context.py`
- `changelog/2026-05-09-runtime-situation-label-cleanup.md`

## Behavior Changed

- Current conversation situation now renders as:
  `[Current Situation]`, `Conversation with: ...`, and `Time: ...`.
- Autonomous situation now renders as:
  `[Current Situation]`, `Mode: autonomous work session`, and `Time: ...`.
- Retrieval, memory, behavioral guidance, prompt ordering, autonomous behavior,
  and API behavior are unchanged.
- Prompt inventory was regenerated after the wording change.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `git diff --check`

## Known Limitations

- Other prompt/context entries may still use second-person phrasing where
  independently appropriate.
- Prompt inventory remains heuristic.

## Follow-Up Work

- Continue prompt inventory review for additional wording that defines the
  entity from outside or reads as overly assistant-like.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not change identity, memory, or guidance architecture.
- Removes unnecessary direct identity-adjacent situation phrasing while keeping
  factual context visible.
