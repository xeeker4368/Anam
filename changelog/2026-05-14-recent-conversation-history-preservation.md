# Recent Conversation History Preservation v1

## Summary

Added a narrow retrieval skip policy for immediate previous-response questions, clearer chat debug metadata for conversation continuity/history composition, and frontend handling for backend-replaced conversation IDs.

## Files Changed

- `tir/engine/retrieval_policy.py`
- `tir/api/routes.py`
- `frontend/src/components/Chat.jsx`
- `tests/test_api_agent_stream.py`
- `tests/test_retrieval_policy.py`
- `docs/PROMPT_INVENTORY.md`

## Behavior Changed

- Questions about the immediately previous response skip long-term memory retrieval with reason `immediate_conversation_reference`.
- Normal long-term memory questions still use retrieval.
- Chat debug output now reports supplied/effective conversation IDs, replacement reason, DB history counts, injected system-message count, model-message count, and previous-assistant presence.
- The frontend now follows a backend-returned `conversation_id` when it differs from the current prop.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `.pyanam/bin/python -m pytest tests/test_retrieval_policy.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python -m pytest` passed, 636 tests.
- `npm --prefix frontend run build`
- `git diff --check` passed.

## Known Limitations

- This does not add conversation-history truncation or protected token budgeting.
- This does not change retrieval ranking.
- This does not add frontend unit tests; the frontend change is validated with the production build.

## Follow-Up Work

- Consider clearer UI display for conversation replacement/debug state if it happens frequently.
- Consider explicit protected recent-history budgeting if future context packing starts truncating conversation history.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not assign personality or identity.
- Preserved raw conversation history as primary local context.
- Avoided memory authority changes and retrieval ranking changes.
- Preserved Behavioral Guidance dormant status.
