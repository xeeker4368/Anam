# Frontend Reliability Cleanup

## Summary

Improved frontend handling for failed HTTP responses and fixed a resize listener cleanup bug without changing backend behavior or the chat streaming protocol.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `changelog/2026-05-02-frontend-reliability-cleanup.md`

## Behavior Changed

- Chat streaming now checks HTTP status before reading the NDJSON stream.
- Non-OK chat responses now replace the pending assistant placeholder with a clear error message.
- Failed chat HTTP responses are appended to raw debug events.
- Message, conversation, user, and conversation-view fetches now check HTTP status before updating state.
- Fetch helpers now avoid mapping non-array error payloads as normal data.
- The mobile resize hook now removes its `resize` event listener correctly.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py tests/test_agent_loop.py tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- This patch does not add new UI error banners or redesign error display.
- Manual browser verification of backend error states remains useful.
- ESLint still reports existing React hook dependency warnings; there are no lint errors.

## Follow-up Work

- Consider consolidating frontend fetch error helpers if more endpoints are added.

## Project Anam Alignment Check

- Did not redesign the UI.
- Did not change backend API behavior.
- Did not change the chat streaming protocol.
- Did not add frontend libraries.
- Did not modify `soul.md`.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
- Did not rename `tir/`.
- Did not add features.
