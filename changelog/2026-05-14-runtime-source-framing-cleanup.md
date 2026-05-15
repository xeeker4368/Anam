# Runtime Source Framing Cleanup

## Summary

Reduced runtime prompt prescription by replacing the broad retrieved-context header with neutral source framing and compressing `OPERATIONAL_GUIDANCE.md` to source/tool/action safety essentials.

## Files Changed

- `OPERATIONAL_GUIDANCE.md`
- `docs/PROMPT_AUDIT_NOTES.md`
- `docs/PROMPT_INVENTORY.md`
- `tir/engine/context.py`
- `tests/test_context.py`

## Behavior Changed

- Retrieved context now begins with: `Retrieved context follows. Each item is labeled by source type.`
- The old broad header `These are your own experiences and memories.` is no longer emitted.
- Per-source labels for conversation, journal, research, project reference, external, and artifact chunks remain unchanged.
- `OPERATIONAL_GUIDANCE.md` is shorter and focused on current conversation priority, memory/current-state boundaries, URL fetching, tool honesty, failure honesty, action approval, and uncertainty.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- `soul.md` was intentionally not audited or changed in this patch.
- Journal and research prompt looseness remain separate follow-up work.
- Tool descriptions and source labels were preserved except for the retrieved-context header.

## Follow-Up Work

- Journal Prompt Looseness v1.
- Manual Research Prompt Looseness v1.
- Tool Description Source Framing v1.
- Dedicated `soul.md` minimality review if approved separately.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add personality or identity guidance.
- Preserved source provenance and live-tool boundaries.
- Did not change retrieval ranking, DB schema, model config, research behavior, journal behavior, or tool behavior.
