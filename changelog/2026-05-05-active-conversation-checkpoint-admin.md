# Active Conversation Checkpoint Admin Command

## Summary

Added an explicit admin command to checkpoint active conversations into retrieval without ending them or marking them fully chunked.

## Files Changed

- `tir/memory/audit.py`
- `tir/admin.py`
- `tests/test_memory_audit.py`
- `changelog/2026-05-05-active-conversation-checkpoint-admin.md`

## Behavior Changed

- Added `checkpoint_active_conversations(limit=None, dry_run=False)` for admin-level active conversation checkpointing.
- Added `memory-checkpoint-active` to the admin CLI.
- Dry runs report checkpoint targets without mutating Chroma, FTS, or conversation state.
- Non-dry runs call `checkpoint_conversation(...)` per active conversation with messages, continue after failures, and report successes/failures.
- Active conversations remain active and are not marked `chunked=1`.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_chunking.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `git diff --check`

## Known Limitations

- This v1 command checkpoints only the latest/tail chunk group through existing `checkpoint_conversation(...)` semantics.
- It does not perform a full active-conversation rebuild/backfill.
- It is not wired into startup.

## Follow-Up Work

- Consider a bounded full active-conversation backfill command if tail checkpointing is not enough for legacy long-running conversations.
- Consider startup diagnostics that recommend this command when many active conversations remain uncheckpointed.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience as primary.
- Improves retrieval availability for saved active-session experience without changing memory schema or session lifecycle.
- Keeps the workspace and self-modification boundary unchanged.
