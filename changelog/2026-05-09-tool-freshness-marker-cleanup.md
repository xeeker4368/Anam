# Tool Freshness Marker Cleanup v1

## Summary

Clarified the real-time tool freshness marker while preserving the
live-source-vs-memory boundary.

## Files Changed

- `tir/tools/registry.py`
- `tests/test_tool_registry.py`
- `tests/test_declarative_http_skills.py`
- `docs/PROMPT_INVENTORY.md`
- `docs/PROMPT_AUDIT_NOTES.md`
- `changelog/2026-05-09-tool-freshness-marker-cleanup.md`

## Behavior Changed

- Real-time source-of-truth tool descriptions now say:
  `memory can provide context; use live tool results for current state`.
- Tool behavior, retrieval policy, memory behavior, and source precedence are
  unchanged.
- Prompt inventory was regenerated after the wording change.
- Prompt audit notes now record the freshness marker as reviewed and changed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_tool_registry.py tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `git diff --check`

## Known Limitations

- The marker is longer than before and may add prompt clutter if many real-time
  tools are loaded.
- A future compact marker plus shared legend may be preferable if the tool list
  grows.

## Follow-Up Work

- Continue prompt audit work on fallback/error response text.
- Revisit tool-description compactness after more live-source tools are added.

## Project Anam Alignment Check

- Does not change memory architecture.
- Does not modify `OPERATIONAL_GUIDANCE.md`, `BEHAVIORAL_GUIDANCE.md`, or
  `soul.md`.
- Keeps live-source boundaries explicit without moving tool-specific guidance
  into broader identity or operational text.
