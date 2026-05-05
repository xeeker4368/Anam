# Active Conversation Checkpointing

## Summary

Added active conversation checkpointing so completed assistant turns can be indexed into retrieval before a conversation is formally closed.

## Files Changed

- `tir/memory/chunking.py`
- `tir/api/routes.py`
- `tests/test_chunking.py`
- `tests/test_api_agent_stream.py`
- `changelog/2026-05-05-active-conversation-checkpointing.md`

## Behavior Changed

- Added `checkpoint_conversation(conversation_id, user_id)`, which upserts the latest/tail chunk group for an active conversation using deterministic chunk IDs.
- The streaming chat route now checkpoints after a real assistant message is persisted.
- Checkpoint failures are logged as warnings and do not break the chat response.
- Active conversations are not ended and are not marked `chunked=1` by checkpointing.
- Final close/final chunking behavior remains unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_chunking.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_audit.py -v`
- `git diff --check`

## Known Limitations

- Checkpointing writes only the latest chunk group in v1.
- Startup does not automatically checkpoint active conversations.
- Final close remains the full correctness pass for complete conversation chunking.

## Follow-Up Work

- Consider a bounded startup repair/checkpoint path for active conversations after the checkpointing behavior has live runtime history.
- Review whether `maybe_chunk_live` should remain as a compatibility helper once active checkpointing has settled.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality traits.
- Preserves raw conversation messages as primary experience.
- Improves retrievability of completed saved turns without changing memory architecture or database schema.
- Keeps workspace, self-modification, and conversation/session lifecycle boundaries intact.
