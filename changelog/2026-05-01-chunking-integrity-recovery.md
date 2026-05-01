# Chunking Integrity And Recovery

## Summary

Fixed final conversation chunking so failed chunk writes no longer mark a conversation as fully chunked, and added an explicit recovery helper for ended-but-unchunked conversations.

## Files Changed

- `tir/memory/chunking.py`
- `tests/test_chunking.py`
- `changelog/2026-05-01-chunking-integrity-recovery.md`

## Behavior Changed

- `chunk_conversation_final(...)` now tracks intended chunks and successful writes.
- Conversations are marked `chunked=1` only when all intended chunks are written successfully.
- Partial or failed final chunking leaves `chunked=0`, keeping ended conversations discoverable for recovery.
- Per-chunk failures are logged with exception info.
- Added `recover_unchunked_ended_conversations(...)` as an explicit helper.
- Recovery is not wired into startup.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_chunking.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`

## Known Limitations

- Existing partial chunks are not removed or reconciled.
- FTS5 remains secondary to ChromaDB; FTS failures do not fail the chunk write.
- Recovery must be invoked explicitly.
- No startup sweep or scheduler was added.

## Follow-up Work

- Add an operator command or scheduled bounded recovery pass if approved later.
- Consider explicit chunking status fields only if operational evidence shows they are needed.

## Project Anam Alignment Check

- Did not add new features beyond focused recovery helper.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change retrieval semantics.
- Did not add memory scopes.
- Did not add new registries.
- Did not add web search, Moltbook, image generation, autonomy, or self-modification.
- Did not wire recovery into startup.
- Did not change FTS/Chroma primary/secondary semantics.
