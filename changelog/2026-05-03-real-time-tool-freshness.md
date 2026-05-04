# Real-Time Tool Freshness Metadata

## Summary

Added lightweight freshness metadata for real-time source-of-truth tools and surfaced that metadata in runtime tool descriptions.

## Files Changed

- `tir/tools/registry.py`
- `tir/tools/http_declarative.py`
- `skills/active/web_search/SKILL.md`
- `skills/active/web_search/web_search.py`
- `skills/active/moltbook/SKILL.md`
- `skills/active/moltbook/skill.yaml`
- `skills/active/moltbook/moltbook.py`
- `OPERATIONAL_GUIDANCE.md`
- `tests/test_tool_registry.py`
- `tests/test_declarative_http_skills.py`
- `tests/test_context.py`
- `tests/test_web_search_skill.py`
- `tests/test_moltbook_declarative_skill.py`
- `tests/test_moltbook_search_semantics.py`
- `changelog/2026-05-03-real-time-tool-freshness.md`

## Behavior Changed

- `ToolDefinition` now carries optional freshness metadata.
- Python `@tool` definitions can declare freshness metadata.
- Declarative HTTP `skill.yaml` tools can declare validated freshness metadata.
- Runtime tool descriptions now include a compact marker for real-time source-of-truth tools.
- `web_search`, `web_fetch`, `moltbook_find_author_posts`, and all current declarative Moltbook read tools are marked real-time source-of-truth.
- `memory_search` remains unmarked.
- Operational guidance now states that real-time source-of-truth tools must be used for current or source-specific external state.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py tests/test_moltbook_declarative_skill.py tests/test_moltbook_search_semantics.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- This patch is metadata and guidance only. It does not add deterministic Moltbook routing or a broad planner.
- Model compliance may still require future narrow routing if guidance is insufficient.

## Follow-Up Work

- Consider a narrow deterministic Moltbook router only if real-time metadata and guidance do not reliably trigger live checks.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add assigned personality or identity behavior.
- Did not modify `soul.md`.
- Did not add write actions, UI, API routes, DB schema, memory architecture changes, autonomy, broad planning, or self-modification.
