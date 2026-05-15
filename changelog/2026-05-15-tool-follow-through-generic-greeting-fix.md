# Tool Follow-Through Generic Greeting Fix

## Summary

Hardened the agent loop so text emitted during a tool-call iteration is buffered until the iteration is known to be a normal text response. If the model emits a tool call, buffered pre-tool text is suppressed from visible output and is not used as the final assistant answer.

## Files Changed

- `tir/engine/agent_loop.py`
- `tests/test_agent_loop.py`
- `tests/test_api_agent_stream.py`
- `changelog/2026-05-15-tool-follow-through-generic-greeting-fix.md`

## Behavior Changed

- Normal text-only responses still stream token events after the iteration completes.
- Tool-call iterations no longer stream intermediate text such as generic greetings.
- Assistant tool-call messages are appended with empty content before rendered tool results are added.
- Final post-tool responses continue to stream and persist as `LoopResult.final_content`.
- Suppressed pre-tool text is recorded in tool trace metadata as a preview and character count.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_agent_loop.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_declarative_http_skills.py -v`
- `.pyanam/bin/python -m pytest tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest`

## Known Limitations

- This does not compact large tool results.
- This does not add generic greeting detection.
- Text streaming for normal responses now waits until the model iteration is known not to contain a tool call.

## Follow-Up Work

- Add tool-result compaction for high-volume tools if large raw payloads still reduce follow-through quality.
- Add additional debug fields only if route-level visibility remains insufficient.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Preserves source/tool/action safety.
- Does not change memory authority, retrieval ranking, research behavior, model config, or runtime guidance.
