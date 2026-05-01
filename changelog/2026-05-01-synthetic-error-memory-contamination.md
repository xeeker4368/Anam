# Synthetic Error Memory Contamination

## Summary

Prevented framework-generated fallback and error strings from being persisted as normal assistant messages.

## Files Changed

- `tir/api/routes.py`
- `tir/engine/conversation.py`
- `tests/test_api_agent_stream.py`
- `tests/test_conversation_engine.py`
- `changelog/2026-05-01-synthetic-error-memory-contamination.md`

## Behavior Changed

- `/api/chat/stream` still saves user messages normally.
- Assistant messages are persisted only for completed, non-empty model output.
- Framework-authored exception, iteration-limit, unknown-termination, and empty-output messages are emitted as stream errors but not archived as assistant messages.
- `done` events keep `message_id` present as `null` when no assistant message was persisted.
- Live chunking is skipped when no real assistant message was saved.
- The legacy CLI conversation engine returns readable error/fallback text without saving it as assistant content.
- Real model-generated assistant content still persists normally.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_conversation_engine.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_chunking.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`

## Known Limitations

- User messages from failed turns are still persisted.
- Tool trace from failed turns without real assistant output is not persisted as assistant message metadata.
- Frontend display can still show transient error text, but it is not stored as assistant archive content.

## Follow-up Work

- Consider non-message error metadata for failed turns if preserving tool traces without memory contamination becomes necessary.
- Consider deprecating or replacing the older CLI conversation engine later.

## Project Anam Alignment Check

- Did not add new features.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change retrieval semantics.
- Did not add memory scopes.
- Did not add new registries.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
- Did not refactor or remove CLI chat.
