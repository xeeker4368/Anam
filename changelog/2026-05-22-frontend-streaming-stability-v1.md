# Frontend Streaming Stability v1

## Summary

Hardened the chat frontend streaming lifecycle by adding explicit stream cancellation and stable client-side message IDs.

## Files Changed

- `frontend/src/components/Chat.jsx`
- `changelog/2026-05-22-frontend-streaming-stability-v1.md`

## Behavior Changed

- Chat streaming requests now use an `AbortController`.
- In-flight stream fetches are aborted on component unmount.
- Any previous stream controller is aborted before a new stream starts.
- Active response readers are cancelled and released in cleanup/finally paths.
- `AbortError` is treated as normal cancellation and is not shown as a user-facing connection error.
- Streaming token updates target the specific assistant message by stable message ID instead of updating whichever message happens to be last.
- Rendered chat messages use stable IDs as React keys instead of array indexes.
- Server-provided message IDs are preserved when present; local optimistic user/assistant messages get stable client IDs.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- No frontend unit test harness exists in this project, so this patch relies on lint/build and recommended manual smoke testing.
- The UI still intentionally disables overlapping sends while a stream is active.

## Follow-Up Work

- Add a frontend test harness for stream lifecycle behavior if the frontend grows more complex.
- Manually smoke test token streaming, refresh/navigation during streaming, and a new message after interruption.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved backend API behavior, conversation handling, debug/tool event handling, and trusted household active-user display.
- Did not change DB schema, retrieval, research behavior, Moltbook/web behavior, prompts, guidance files, `soul.md`, model config, or auth/trusted-household semantics.
