# Chat Tab-Switch Stream Resume Polling v2

## Summary

Changed chat tab-switch and mobile resume handling so a suspended frontend stream enters a recoverable state instead of immediately showing an interrupted response.

## Files Changed

- `frontend/src/components/Chat.jsx`

## Behavior Changed

- Visibility/focus recovery no longer marks active assistant responses as interrupted immediately.
- Pending assistant messages enter a `recovering` state and show a neutral "Response still finishing..." status.
- The frontend polls the active conversation briefly for a persisted assistant response after resume.
- Persisted backend messages remain authoritative and replace the local recovering placeholder when available.
- Recovery timeout marks the local placeholder interrupted only after the polling window expires.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- A full page reload still cannot recover an unsaved in-memory stream unless the backend later persists the assistant response.
- The polling window is intentionally short and fixed for v2.

## Follow-up Work

- Add frontend unit tests if a frontend test harness is introduced.
- Consider a backend request status endpoint if longer model runs need more precise recovery state.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend memory, prompts, model config, research, scheduler, or image generation behavior.
- Keeps raw persisted chat history authoritative while preserving local user-visible continuity during browser resume.
