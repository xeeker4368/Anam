# Frontend Resume Event Coalescing v1

## Summary

Coalesced browser resume events so a single tab return does not trigger separate refreshes for `visibilitychange`, `focus`, and `pageshow`.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`

## Behavior Changed

- App-level resume refreshes are scheduled through one short-delay timer and throttled across resume event bursts.
- Chat-level active-message resume refreshes are scheduled through one short-delay timer and throttled across resume event bursts.
- A tab return should now produce at most one broad App refresh and one active conversation message refresh within the coalescing window.
- Chat resume still does not abort active streams or start recovery polling.
- Existing recovery polling remains scoped to real stream disruption/error paths.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- App startup still intentionally performs its initial data load burst.
- App-level resume still performs a broad refresh after the throttle window for stale-panel recovery.
- Manual browser/iPhone verification is still needed to validate actual event ordering in Safari.

## Follow-up Work

- Consider moving browser resume ownership fully into `App.jsx` if future frontend state grows more complex.
- Add frontend unit tests if a frontend test harness is introduced.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend API behavior, database schema, prompts, model config, research, scheduler, Moltbook/web, or image generation behavior.
- Keeps chat stream state local while reducing repeated frontend refresh traffic.
