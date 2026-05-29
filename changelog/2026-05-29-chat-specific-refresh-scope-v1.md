# Chat-Specific Refresh Scope v1

## Summary

Reduced frontend refresh noise by narrowing the refresh callback used after chat stream completion.

## Files Changed

- `frontend/src/App.jsx`

## Behavior Changed

- Chat stream completion now refreshes the conversation list only.
- Chat completion no longer refreshes health, artifacts, or open loops.
- Registry/media UI refresh paths still refresh artifacts and open loops where appropriate.
- App-level startup and throttled resume refreshes still refresh broader app state.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- App-level resume still performs one throttled broad refresh for stale-panel recovery.
- Health continues to refresh on its existing interval.

## Follow-up Work

- Consider centralizing App refresh ownership if future panels add heavier data sources.
- Add frontend unit tests if a frontend test harness is introduced.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend API behavior, database schema, prompts, model config, research, scheduler, Moltbook/web, or image generation behavior.
- Keeps chat refresh scoped to conversation/history state while preserving registry and system refresh behavior in their own UI paths.
