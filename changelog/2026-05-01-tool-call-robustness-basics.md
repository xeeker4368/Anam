# Tool-Call Robustness Basics

## Summary

Hardened the existing tool dispatch path by replacing `_context` TypeError heuristics with signature inspection and by accepting JSON-string tool arguments safely.

## Files Changed

- `tir/tools/registry.py`
- `tir/engine/agent_loop.py`
- `tests/test_tool_registry.py`
- `tests/test_agent_loop.py`
- `changelog/2026-05-01-tool-call-robustness-basics.md`

## Behavior Changed

- Tool dispatch now determines whether a tool accepts `_context` from its signature instead of retrying after a `TypeError`.
- Tools accepting `_context` or `**kwargs` receive the injected context.
- Tools that do not accept `_context` are called without it.
- Real `TypeError` exceptions raised inside tool bodies now surface as normal tool failures.
- Tool arguments supplied as JSON strings are parsed when possible.
- Invalid JSON, non-object JSON, and non-dict/non-string arguments return clear tool error envelopes.
- Invalid argument errors still flow through the existing `tool_result` event path and do not crash the agent loop.
- Successful JSON-string tool arguments are stored in tool traces as normalized dictionaries.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_chunking.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`

## Known Limitations

- Tool-call persistence remains message-level `tool_trace`; this patch intentionally does not add a dedicated `tool_calls` table.
- Invalid tool arguments are reported to the model as text tool results, not structured recovery instructions.

## Follow-up Work

- Re-run the full API/tool regression when additional tools such as workspace, web search, Moltbook, or image generation are introduced.
- Consider stronger typed tool-call diagnostics later if tool ecosystems become larger.

## Project Anam Alignment Check

- Did not add new tools.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change memory retrieval behavior.
- Did not add memory scopes.
- Did not add registries.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
- Did not add purpose, success criteria, result-quality scoring, extra model calls, or a `tool_calls` table.
- Did not make successful tool traces memory.
