# Operational Guidance Runtime Context

## Summary

Loaded root-level `OPERATIONAL_GUIDANCE.md` into the runtime system prompt as a distinct `[Operational Guidance]` section.

## Files Changed

- `tir/engine/context.py`
- `tests/test_context.py`
- `changelog/2026-04-28-operational-guidance-runtime-context.md`

## Behavior Changed

- When `OPERATIONAL_GUIDANCE.md` exists and is non-empty, its content is included in the constructed system prompt after `soul.md` and before tool descriptions, retrieved memories, and current situation.
- If `OPERATIONAL_GUIDANCE.md` is absent or empty, the section is omitted and chat continues normally.
- `DESIGN_RATIONALE.md` is not loaded into runtime context.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py tests/test_api_agent_stream.py -v`
- `git diff --check -- tir/engine/context.py tests/test_context.py changelog/2026-04-28-operational-guidance-runtime-context.md`

## Known Limitations

- Operational guidance is loaded on every prompt construction rather than cached.
- Large guidance content will increase system prompt size.

## Follow-up Work

- Consider adding prompt length diagnostics that break out seed, guidance, tools, memory, and situation sections separately.

## Project Anam Alignment Check

- Did not modify `soul.md`.
- Did not rename `tir/`.
- Did not add tools, workspace, web search, autonomy, document ingestion, identity events, or self-modification.
- Did not treat operational guidance as memory.
- Did not index, chunk, store, or retrieve operational guidance.
- Preserved existing retrieval behavior.
