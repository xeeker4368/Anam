# Chat Resume Polling Deduplication / Scope Fix v1

## Summary

Tightened chat resume recovery so tab-switch polling stays scoped to the active conversation and does not trigger repeated broad application refreshes.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`

## Behavior Changed

- Chat recovery polling now keeps at most one active poll timer for a conversation.
- Recovery polling is cleared when the active conversation changes, the chat component clears, recovery completes, or recovery times out.
- Resume recovery no longer calls the broad app refresh callback from the stream cleanup path.
- App-level resume refreshes are throttled so `visibilitychange`, `focus`, and `pageshow` do not each trigger full conversations/health/registry refreshes for the same return event.
- Pending and recovering Assistant messages remain local while `/messages` polling waits for the persisted backend assistant reply.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- Recovery still uses fixed frontend polling rather than a backend request-status endpoint.
- App-level resume still performs one broad refresh per throttle window for normal stale-panel recovery.

## Follow-up Work

- Add frontend unit tests when a frontend test harness exists.
- Consider splitting chat-only refresh from panel refresh at the App API boundary if future panels become heavier.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend API behavior, database schema, prompts, model config, research, scheduler, Moltbook/web, or image generation behavior.
- Keeps persisted backend messages authoritative while preserving visible in-flight chat continuity.
