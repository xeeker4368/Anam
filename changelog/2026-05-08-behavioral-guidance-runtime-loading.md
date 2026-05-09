# Behavioral Guidance Runtime Loading v1

## Summary

Loaded applied behavioral guidance from `BEHAVIORAL_GUIDANCE.md` into the runtime prompt as a separate reviewed guidance section.

## Files Changed

- `tir/engine/context.py`
- `tests/test_context.py`

## Behavior Changed

- Runtime context now loads only the `## Active Guidance` section.
- Only `- Guidance: ...` lines are extracted.
- Proposal IDs, applied timestamps, source lines, rationale, rejected/proposed records, and seed governance prose are not loaded.
- Reviewed behavioral guidance is placed after operational guidance and before tool descriptions.
- A hard 3000 character budget limits included guidance items.
- Debug prompt breakdown now includes behavioral guidance character and item counts.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- No scoping by user, channel, or context yet.
- No automatic conflict detection between guidance entries.
- Over-budget guidance items are skipped, not truncated.

## Follow-Up Work

- Add scoped guidance only after there is a concrete need.
- Add conflict/review diagnostics if applied guidance grows.
- Monitor prompt size through the new debug fields.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not define a fixed personality.
- Keeps behavioral guidance separate from `soul.md`.
- Does not load proposal metadata as memory or identity.
- Preserves admin-applied guidance as explicit, inspectable runtime context.
