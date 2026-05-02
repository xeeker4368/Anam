# Remove CLI Chat Path

## Summary

Removed the old terminal chat path and its pre-agent-loop conversation engine. Web UI/API chat is now the supported chat interface.

## Files Changed

- `tir/cli_chat.py`
- `tir/engine/conversation.py`
- `tests/test_conversation_engine.py`
- `changelog/2026-05-01-remove-cli-chat-path.md`

## Behavior Changed

- `python -m tir.cli_chat` is no longer available.
- The old `tir.engine.conversation.handle_turn` path is removed.
- Web UI/API chat remains the supported chat path.
- `tir/admin.py` remains available for admin CLI tasks.

## Tests/Checks Run

- `rg "tir\\.cli_chat|cli_chat|tir\\.engine\\.conversation|engine\\.conversation|handle_turn" . -g '!data/prod/**' -g '!*.pyc'`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_agent_loop.py tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_search_skill.py tests/test_tool_registry.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_chunking.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`

## Known Limitations

- Historical `Dev_Docs/` files may still mention the old CLI chat path as archival implementation notes.

## Follow-up Work

- If user-facing setup docs are added later, document `run_server.py` and the Web UI/API path as the supported chat entrypoint.

## Project Anam Alignment Check

- Did not remove `admin.py`.
- Did not change Web/API chat behavior.
- Did not change agent loop behavior.
- Did not change memory retrieval behavior.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add new features.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
