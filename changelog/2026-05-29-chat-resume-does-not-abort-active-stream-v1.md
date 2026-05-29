# Chat Resume Does Not Abort Active Stream v1

## Summary

Stopped normal browser tab/focus/page resume events from aborting active chat streams.

## Files Changed

- `frontend/src/components/Chat.jsx`

## Behavior Changed

- `visibilitychange`, `focus`, and `pageshow` resume handling no longer cancels the active fetch stream or reader.
- Resume while streaming now performs only a safe message refresh/merge for the active conversation.
- Local pending Assistant bubbles and partial streamed content remain visible through resume refreshes.
- Recovery polling remains available for stream disruption/error paths instead of being the default resume behavior.
- Existing pending-message merge and new-conversation adoption behavior is preserved.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- If a browser or network genuinely terminates the stream, recovery still depends on polling for a persisted backend assistant message.
- Manual iPhone/Safari tab-background verification is still required.

## Follow-up Work

- Add frontend unit tests when a frontend test harness exists.
- Consider a backend request-status endpoint if long-running responses need more precise recovery state.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend API behavior, database schema, prompts, model config, research, scheduler, Moltbook/web, or image generation behavior.
- Preserves frontend continuity while keeping persisted backend chat messages authoritative.
