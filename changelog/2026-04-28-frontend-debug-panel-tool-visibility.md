# Frontend Debug Panel Tool Visibility

## Summary

Added frontend debug visibility for streamed tool activity by organizing the debug panel into collapsible sections and capturing non-token stream events in the existing debug state.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `frontend/src/components/DebugPanel.jsx`
- `frontend/src/styles.css`

## Behavior Changed

- `Chat.jsx` now captures `tool_call` and `tool_result` NDJSON stream events.
- Debug data now accumulates `tool_events` and non-token `raw_events`.
- `DebugPanel` now has collapsible sections:
  - Overview
  - Tool Calls
  - Memory Retrieval
  - Raw Debug Data
- Tool calls display tool name, arguments/query, status, compact result summary, and expandable full arguments/result/raw JSON.
- Memory retrieval display remains available inside its own collapsible section.
- Long debug text wraps inside the panel instead of widening it.
- Health polling now marks backend health as unreachable and warns once when the backend is stopped or restarting.

## Tests/Checks Run

- `npm run build`
- `npm run lint`
- `git diff --check -- frontend/src/App.jsx frontend/src/components/Chat.jsx frontend/src/components/DebugPanel.jsx frontend/src/styles.css`
- `curl -sS http://127.0.0.1:8000/api/health`

The frontend build and lint checks passed. The health endpoint check failed with connection refused because the backend was not running at `127.0.0.1:8000`.

## Known Limitations

- Tool call/result pairing is order/name based because backend stream events do not include a stable tool-call id.
- The patch was not visually verified in the in-app browser because the backend was unavailable.
- Raw debug data intentionally excludes token events to avoid flooding frontend state.

## Follow-up Work

- Start the backend and visually verify the collapsible debug panel in the in-app browser.
- Trigger a real `memory_search` call and confirm Tool Calls shows pending/succeeded states as expected.
- Consider adding stable tool-call ids in backend stream events if concurrent or repeated same-name tool calls become hard to inspect.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not modify `soul.md`.
- Did not add personality traits or assigned identity.
- Did not add workspace tools, web search, autonomy, document ingestion, identity events, or self-modification.
- Did not rename `tir/`.
- Preserved retrieval/debug visibility and made tool/action traces more inspectable without changing backend behavior.
