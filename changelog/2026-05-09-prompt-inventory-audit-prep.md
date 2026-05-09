# Prompt Inventory / Prompt Audit Prep v1

## Summary

Added a reproducible backend prompt inventory for auditing model-facing and
model-adjacent wording before further prompt changes.

## Files Changed

- `scripts/extract_prompt_inventory.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_prompt_inventory.py`
- `changelog/2026-05-09-prompt-inventory-audit-prep.md`

## Behavior Changed

- No runtime behavior changed.
- Added a standalone AST-based script that scans `tir/**/*.py` without importing
  runtime modules.
- Added a checked-in generated Markdown inventory grouped by prompt category.
- Added tests that verify known prompt entries, risk flags, audit-note
  placeholders, and report freshness.

## Tests/Checks Run

- Pending in this patch.

## Known Limitations

- The extractor is heuristic and may miss dynamically composed prompt text.
- Some model-adjacent UI/error text may be included when it matches prompt-like
  patterns.
- Frontend strings are intentionally out of scope for v1.

## Follow-Up Work

- Review `docs/PROMPT_INVENTORY.md` and mark each entry with an audit decision.
- Add frontend/operator-copy inventory if needed.
- Consider stricter AST coverage for dynamically composed prompt fragments after
  the first manual audit.

## Project Anam Alignment Check

- Does not change prompt behavior.
- Does not modify `soul.md`, `OPERATIONAL_GUIDANCE.md`, or
  `BEHAVIORAL_GUIDANCE.md`.
- Supports review of wording that may define the entity from outside or become
  too prescriptive.
