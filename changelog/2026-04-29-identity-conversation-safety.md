# Identity And Conversation Safety

## Summary

Fixed identity and conversation safety issues in chat streaming and admin password management.

## Files Changed

- `tir/api/routes.py`
- `tir/memory/db.py`
- `tir/admin.py`
- `tests/test_api_agent_stream.py`
- `tests/test_db.py`
- `tests/test_admin.py`
- `changelog/2026-04-29-identity-conversation-safety.md`

## Behavior Changed

- Explicit unknown `user_id` values now return 404 instead of silently using the default user.
- Default user fallback remains available only when no user identity is supplied.
- Supplied ended conversations are no longer appended to; chat starts a new conversation instead.
- Supplied conversations owned by another user now return 403 and are not mutated.
- `set-password` now creates or updates the `web` channel auth row through an UPSERT.
- Password setup no longer depends on a pre-existing web channel row.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_feedback.py tests/test_open_loops.py tests/test_artifacts.py tests/test_diagnostics.py -v`
- `git diff --check`

## Known Limitations

- Missing conversation IDs still start a new conversation for chat UX.
- Conversation ownership enforcement is currently applied to `/api/chat/stream`.
- The admin password helper updates the owner of an existing `(channel, identifier)` row if called for a different user.

## Follow-up Work

- Consider applying explicit ownership checks to non-stream conversation endpoints.
- Consider returning explicit metadata in the stream when an ended conversation is rolled over to a new one.

## Project Anam Alignment Check

- Did not add new features.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not change memory retrieval behavior.
- Did not change agent loop behavior except to prevent state corruption.
- Did not intentionally touch `data/prod` files.
