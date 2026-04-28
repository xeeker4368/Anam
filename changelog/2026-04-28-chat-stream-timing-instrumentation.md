# Chat Stream Timing Instrumentation

## Summary

Added observability-only timing instrumentation to `/api/chat/stream` and surfaced the timings in the frontend debug panel.

## Files Changed

- `tir/api/routes.py`
- `tests/test_api_agent_stream.py`
- `frontend/src/components/Chat.jsx`
- `frontend/src/components/DebugPanel.jsx`
- `frontend/src/styles.css`

## Behavior Changed

- The initial `debug` NDJSON event now includes backend timings for pre-model phases:
  - conversation resolution
  - user message save
  - retrieval
  - context build
  - history load
  - elapsed time before debug emission
- The stream now emits a non-token `debug_update` event after model/tool execution with backend timings for:
  - agent/tool loop
  - first token, when available
  - model stream or model total
  - tool call count
  - loop iterations, when available
  - assistant message save
  - chunking
  - total backend time
- The frontend merges `debug_update.timings` into existing debug data and stores the event in raw events without storing token events.
- The debug panel now has a collapsible Timings section with compact backend and frontend timing rows.
- Frontend-observed timings are added for request-to-debug, request-to-first-token, request-to-done, and total frontend stream duration.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_api_agent_stream.py -v`
- `npm run build`
- `npm run lint`
- `git diff --check -- tir/api/routes.py tests/test_api_agent_stream.py frontend/src/components/Chat.jsx frontend/src/components/DebugPanel.jsx frontend/src/styles.css changelog/2026-04-28-chat-stream-timing-instrumentation.md`

## Known Limitations

- Backend `first_token_ms` is measured from backend request handling start to first token emission.
- Frontend timing uses browser `performance.now()` and measures client-observed stream milestones, not actual paint/render cost.
- Model timing is approximate because the existing agent loop abstracts individual model calls and tool dispatch into one generator.

## Follow-up Work

- Consider adding stable per-iteration model/tool timing inside `run_agent_loop` if coarse route-level timing is not enough.
- Consider adding explicit browser render/paint measurement only if frontend rendering becomes a suspected bottleneck.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not add personality traits or assigned identity.
- Did not add tools, workspace, web search, autonomy, document ingestion, identity events, or self-modification.
- Did not rename `tir/`.
- Preserved model and retrieval behavior; this patch is observability only.
