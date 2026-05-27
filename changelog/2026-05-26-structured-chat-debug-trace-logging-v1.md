# Structured Chat Debug Trace Logging v1

## Summary

Added compact JSONL debug traces for completed chat requests so model, context, timing, and result summaries can be inspected from runtime files after model smoke tests.

## Files Changed

- `tir/api/routes.py`
- `tir/engine/agent_loop.py`
- `tir/ops/chat_debug_trace.py`
- `docs/PROMPT_INVENTORY.md`
- `tests/test_api_agent_stream.py`
- `changelog/2026-05-26-structured-chat-debug-trace-logging-v1.md`

## Behavior Changed

- Chat requests now append one structured record to `data/prod/chat_debug.jsonl` after the backend finishes handling the request.
- Records include request/conversation/user identifiers, chat model, safe model options, prompt/context counts, tool-loop counts, timing summaries, result status, and optional Ollama stream counters when available.
- Debug trace logging failures are warning-only and do not break the chat response.
- The generated prompt inventory was refreshed for backend line-number changes.

## Tests/Checks Run

- Pending implementation verification.

## Known Limitations

- Full prompts, message bodies, retrieved chunk text, and raw tool payloads are intentionally excluded.
- Ollama final stream stats are logged only when the stream response includes them.

## Follow-Up Work

- Consider a rotation/retention policy for runtime diagnostic JSONL files after go-live.
- Consider an admin diagnostics view for recent chat trace summaries if file-based traces prove useful.

## Project Anam Alignment Check

- This patch does not assign the entity a name, avatar, personality, or identity.
- The change is runtime diagnostics only and preserves existing prompt, retrieval, model, memory, and research behavior.
- The trace is inspectable and avoids logging raw private conversation content by default.
