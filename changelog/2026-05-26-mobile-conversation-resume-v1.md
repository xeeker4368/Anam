# Mobile Conversation Resume / Client State Persistence v1

## Summary

Added small browser-side state persistence and resume refresh behavior so the web UI can recover the current household user, conversation, mobile tab, and draft message after iOS Safari suspends or reloads the page.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`
- `changelog/2026-05-26-mobile-conversation-resume-v1.md`

## Behavior Changed

- The frontend persists the active household user, active conversation id, and active mobile tab in `localStorage`.
- The chat input draft is persisted locally per household user and conversation until it is sent or cleared.
- On app load, users and conversations are refreshed from the backend and the stored conversation is kept only if it still exists and belongs to the active user.
- On browser resume/focus/pageshow, the app refreshes the conversation list, health, registries, and the active conversation messages.
- If a stream was interrupted while the page was hidden, the UI aborts the stale client-side stream state and reloads persisted messages from the backend instead of leaving an endless streaming indicator.

## Tests/Checks Run

- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`
- Browser smoke check at `http://127.0.0.1:5174/` verified the app loads and reloads against the local backend. The in-app browser environment did not expose `localStorage`, so full persistence behavior still needs a Safari/iPhone smoke test.

## Known Limitations

- Browser storage is only a convenience layer; the backend remains the source of truth.
- The frontend does not cache full message history in local storage.
- If a mobile browser suspends a request before the backend saves an assistant response, the UI can only show what the backend persisted.

## Follow-up Work

- Run an iPhone Safari manual smoke test against the LAN app before go-live.
- Consider frontend tests if a browser test harness is added later.

## Project Anam Alignment Check

- Preserves trusted household mode without adding login or authentication.
- Does not change prompts, guidance, model config, backend memory, research, Moltbook, web, scheduler, image generation, or avatar behavior.
- Does not assign the entity a name, avatar, appearance, personality, or self-representation.
