# Prompt Audit Notes v1

## Summary

Added a human-maintained prompt audit notes document separate from the generated
prompt inventory.

## Files Changed

- `docs/PROMPT_AUDIT_NOTES.md`
- `changelog/2026-05-09-prompt-audit-notes.md`

## Behavior Changed

- No runtime behavior changed.
- Prompt audit decisions now live in `docs/PROMPT_AUDIT_NOTES.md`.
- `docs/PROMPT_INVENTORY.md` remains generated-only.

## Tests/Checks Run

- Pending in this patch.

## Known Limitations

- Audit notes may drift from generated inventory entries if prompt locations or
  labels change.
- Notes intentionally reference file/function/label rather than exact line
  numbers to reduce churn.

## Follow-Up Work

- Continue reviewing prompt inventory entries and record decisions here.
- Decide whether tool freshness wording belongs in metadata or operational
  guidance.
- Decide whether fallback/error response text should use a more consistent
  failure style.

## Project Anam Alignment Check

- Does not change runtime prompts.
- Does not modify `soul.md`, `OPERATIONAL_GUIDANCE.md`, or
  `BEHAVIORAL_GUIDANCE.md`.
- Preserves prompt audit decisions separately from generated output.
