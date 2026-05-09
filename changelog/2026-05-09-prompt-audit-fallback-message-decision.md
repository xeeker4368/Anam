# Prompt Audit Fallback Message Decision

## Summary

Recorded the prompt audit decision to keep the current fallback/error response
text in `tir/api/routes.py`.

## Files Changed

- `docs/PROMPT_AUDIT_NOTES.md`
- `changelog/2026-05-09-prompt-audit-fallback-message-decision.md`

## Behavior Changed

- No runtime behavior changed.
- Fallback/error response text remains plain and operational.

## Tests/Checks Run

- Pending in this patch.

## Known Limitations

- Future UI or voice polish may revisit fallback/error copy.

## Follow-Up Work

- Continue prompt audit as new prompts or model-facing strings are added.

## Project Anam Alignment Check

- Does not modify runtime prompts.
- Does not modify `soul.md`, `OPERATIONAL_GUIDANCE.md`, or
  `BEHAVIORAL_GUIDANCE.md`.
- Keeps prompt audit decisions separate from generated inventory output.
