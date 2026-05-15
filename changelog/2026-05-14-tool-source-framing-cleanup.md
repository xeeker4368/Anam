# Tool Source Framing Cleanup

## Summary

Loosened tool/source framing for memory search and real-time tool freshness markers while preserving tool honesty, source clarity, live-source boundaries, and read/write safety.

## Files Changed

- `skills/active/memory_search/SKILL.md`
- `skills/active/memory_search/memory_search.py`
- `tir/tools/registry.py`
- `tests/test_memory_search_skill.py`
- `tests/test_tool_registry.py`
- `tests/test_declarative_http_skills.py`
- `docs/PROMPT_AUDIT_NOTES.md`
- `docs/PROMPT_INVENTORY.md`

## Behavior Changed

- `memory_search` is described as searching indexed prior records and memories instead of "your own memories."
- Empty memory search results now say no indexed prior records were found.
- Real-time tool freshness markers now say prior records can provide context while live tool results remain the source for current state.

## Tests/Checks Run

- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- This patch does not change tool behavior, registry semantics, Moltbook behavior, web fetch behavior, retrieval ranking, or memory authority.

## Follow-Up Work

- Continue with soul minimality review.
- Later review broader tool descriptions again when new media, research, or multi-user tools are added.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not assign personality or identity.
- Did not edit `soul.md`.
- Did not re-enable behavioral guidance runtime loading.
- Preserved tool honesty, failure honesty, live-source boundaries, and source clarity.
