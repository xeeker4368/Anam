# Suppress Resume Refresh During Active Chat Stream v1

## Summary

Prevented browser tab resume events from refreshing broad app state or active chat messages while an assistant response stream is in progress.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`

## Behavior Changed

- `Chat` now reports active stream state to `App`.
- `App` skips and clears coalesced broad resume refreshes while a chat stream is active.
- `Chat` skips and clears resume message refreshes while a chat stream is active.
- Stream completion still triggers the narrow conversation-list refresh used for chat history updates.
- Recovery polling remains reserved for real stream disruption/error paths.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
  - Passed with existing `frontend/src/App.jsx` React hook dependency warnings.
- `git diff --check`

## Known Limitations

- Manual iPhone Safari verification is still needed to confirm browser-specific resume behavior.
- Idle tab resume still performs the existing coalesced refresh behavior.

## Follow-Up Work

- Continue observing request logs during slow-model testing to confirm resume refreshes remain quiet during active streams.

## Project Anam Alignment Check

- Did not assign the entity a name or visual identity.
- Did not alter prompts, guidance, model config, memory, scheduler, research, image generation, or backend behavior.
- Preserved local pending/partial chat state as raw UI experience rather than replacing it with inferred state.
