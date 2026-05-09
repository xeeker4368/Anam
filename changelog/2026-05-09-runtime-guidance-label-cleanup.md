# Runtime Behavioral Guidance Label Cleanup v1

## Summary

Cleaned up the runtime reviewed behavioral guidance label so it preserves
source and precedence while removing defensive identity/personality wording
from every-turn context.

## Files Changed

- `tir/engine/context.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_context.py`
- `tests/test_prompt_inventory.py`
- `changelog/2026-05-09-runtime-guidance-label-cleanup.md`

## Behavior Changed

- `BEHAVIORAL_GUIDANCE_LABEL` now says active behavioral guidance is
  AI-proposed, admin-approved/applied, and below `soul.md` and operational
  guidance in precedence.
- The label no longer says behavioral guidance does not define fixed
  personality or identity on every turn.
- Behavioral guidance extraction, budget behavior, debug fields, runtime
  ordering, and proposal workflows are unchanged.
- Prompt inventory was regenerated after the label change.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `git diff --check`

## Known Limitations

- The broader identity/personality boundary remains in governance/runtime seed
  files rather than this repeated label.
- Prompt inventory remains heuristic.

## Follow-Up Work

- Continue reviewing remaining prompt inventory entries for defensive or
  identity-adjacent wording.

## Project Anam Alignment Check

- Does not modify `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, or
  `soul.md`.
- Does not change guidance precedence.
- Reduces repeated identity-adjacent context wording while preserving source
  clarity.
