# Behavioral Guidance Review Prompt Cleanup v1

## Summary

Lightly cleaned up the behavioral guidance review system prompt so it is less
compliance-heavy and less identity-adjacent while preserving strict JSON and
task constraints.

## Files Changed

- `tir/behavioral_guidance/review.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_prompt_inventory.py`
- `changelog/2026-05-09-behavioral-guidance-review-prompt-cleanup.md`

## Behavior Changed

- The behavioral guidance review system prompt no longer names Project Anam in
  the task framing.
- The system prompt no longer includes the old broad personality-related
  negative instructions.
- The proposal schema, validation, CLI behavior, model invocation, and user
  prompt rules are unchanged.
- Prompt inventory was regenerated after the wording change.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_review.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `git diff --check`

## Known Limitations

- The behavioral guidance review user prompt still contains task-boundary
  `Do not...` rules.
- Prompt inventory is heuristic and remains an audit aid, not a complete parser
  for every possible model-facing string.

## Follow-Up Work

- Continue auditing prompt inventory entries for wording that is too
  prescriptive, assistant-like, audit-like, or identity-adjacent.

## Project Anam Alignment Check

- Does not change behavioral guidance governance.
- Does not mutate `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, or
  `soul.md`.
- Reduces identity-adjacent prompt wording without changing runtime behavior.
