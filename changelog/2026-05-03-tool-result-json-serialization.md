# Tool Result JSON Serialization

## Summary

Cleaned up tool result rendering so structured tool outputs are streamed and passed back to the model as valid JSON instead of Python repr strings.

## Files Changed

- `tir/tools/rendering.py`
- `tir/engine/agent_loop.py`
- `tir/api/routes.py`
- `tests/test_agent_loop.py`
- `tests/test_url_prefetch.py`
- `changelog/2026-05-03-tool-result-json-serialization.md`

## Behavior Changed

- Dict, list, and JSON-serializable primitive tool results are now rendered with `json.dumps(..., ensure_ascii=False)`.
- Plain string tool results remain unchanged and are not JSON-quoted.
- Non-JSON-serializable tool results fall back to `str(...)`.
- Agent-loop tool results, model tool context, and tool trace rendered snippets now use the shared renderer.
- Deterministic URL prefetch tool results, model context, and persisted prefetch traces now use the same renderer.
- Tool event shape remains unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_url_prefetch.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_web_search_skill.py tests/test_moltbook_search_semantics.py -v`
- `git diff --check`

## Known Limitations

- Persisted tool trace `rendered` strings for structured results now use JSON formatting, so older traces may still contain Python repr formatting.
- Non-JSON-serializable fallback remains best-effort text via `str(...)`.

## Follow-Up Work

- Consider normalizing older persisted tool trace renderings only if a future migration or trace export path needs it.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not add personality or identity behavior.
- Did not modify `soul.md` or `OPERATIONAL_GUIDANCE.md`.
- Did not add tools, API routes, UI, DB schema, memory writes, retrieval changes, artifacts, open loops, diagnostics, autonomy, or self-modification.
