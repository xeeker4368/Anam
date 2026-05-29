# Preserve Empty Pending Assistant Bubble on Tab Resume v1

## Summary

Fixed a chat resume timing bug where an empty frontend-only pending Assistant bubble could disappear after a backend refresh, especially during a new conversation before the persisted assistant reply existed.

## Files Changed

- `frontend/src/components/Chat.jsx`

## Behavior Changed

- Backend refresh merging now preserves local pending Assistant messages even when their content is empty.
- Partial streamed Assistant content remains local and visible until the persisted backend assistant reply appears.
- New-chat pending messages can be adopted by the first persisted conversation refresh when the persisted user message matches the optimistic user message.
- Persisted backend assistant messages remain authoritative and replace local pending/recovering placeholders.
- Pending message state remains scoped and is not carried across unrelated History selections.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint` (passes with existing `App.jsx` hook dependency warnings)
- `git diff --check`

## Known Limitations

- A full page reload still cannot restore frontend-only pending state unless the backend later persists the assistant response.
- Matching new-chat pending state relies on the persisted user message content when no server message id exists yet.

## Follow-up Work

- Add frontend unit tests when a frontend test harness exists.
- Consider backend request status tracking if exact in-flight response state becomes necessary.

## Project Anam Alignment Check

- Does not assign the entity a name, avatar, or fixed personality.
- Does not change backend API behavior, database schema, prompts, model config, research, scheduler, Moltbook/web, or image generation behavior.
- Preserves local visible chat continuity while keeping persisted backend messages authoritative.
