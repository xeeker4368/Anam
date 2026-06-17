# Resume-on-Load v1 (server thread reuse + /current endpoint + client display)

## Summary

When a user opens the app on a fresh device or browser, they now land back in
their existing ongoing conversation with its message history rendered, instead of
a blank "Start a conversation" screen. Implements the agreed **B-minimal +
A-as-display** design with a single server-side source of truth for "the user's
current open thread."

Scope unchanged: storage stays segmented, no conversation list, one resumable
thread per user.

## Design

Two jobs, one primitive:
- **Thread identity (server, B):** the chat-stream now reuses the user's newest
  open conversation when no `conversation_id` is supplied, instead of always
  creating a new one. This is on the shared layer, so a send that races the
  client's resume-selection cannot fork a duplicate thread.
- **Display (client, A):** on load/identity-resolve, the client fetches the
  user's current open thread and sets it active so its history renders.

Both read the **same** primitive `db.get_active_conversations(user_id)` (newest
open first) — no parallel "current thread" query. The new HTTP endpoint and the
stream reuse are the only two call sites.

## Files Changed

- `tir/api/routes.py`
- `frontend/src/api.js`
- `frontend/src/App.jsx`
- `tests/test_api_agent_stream.py` (new tests)
- `docs/PROMPT_INVENTORY.md` (regenerated — line-number drift only)

## Behavior Changed

- **New endpoint** `GET /api/conversations/current?user_id=` — returns the user's
  newest open conversation (or `null` if none). Validates via `_resolve_user`
  (422 missing `user_id`, 404 unknown). Declared before the
  `/{conversation_id}/...` routes so "current" isn't captured as an id. Calls
  `get_active_conversations(user["id"])`.
- **Stream reuse (B)** `tir/api/routes.py` (`conversation_id is None` branch):
  now calls `get_active_conversations(user_id)`; if an open thread exists, reuses
  the newest (`conversation_started_reason = "resumed_open"`), else
  `start_conversation` as before (`"new_request"`). The supplied-id paths
  (missing/ended → new) are unchanged.
- **Client display (A)** `App.jsx` `fetchConversations` gains an optional
  `resumeCurrentIfNone` flag. When set and no stored/live conversation id
  resolved and a user is active, it calls `getCurrentConversation(activeUserId)`
  and sets `activeConversationId` → Chat's existing load-effect fetches messages.
  - Triggers: the mount effect (covers a **restored** user — `activeUser` is set
    at mount) and `handleUserResolved` (covers **gate-login** users). All other
    `fetchConversations` callers (resume, onRefresh, close) keep the default
    `false`, so no behavior change there — the resume-current path runs only on
    initial load / identity resolve, never overriding a mid-session selection.
  - `handleUserResolved` calls `fetchConversations` and omits it from the dep
    array (it's a stable `useCallback([])`) to avoid a render-time TDZ; flagged
    with an `eslint-disable-line` and a comment.
- `frontend/src/api.js`: new `getCurrentConversation(userId)` helper hitting the
  endpoint (returns `null` on missing user / non-ok / error).

## Why This Doesn't Add a Parallel Resume System

Selection stays owned by `fetchConversations`; A-display sets the **same**
`activeConversationId` that the existing resume machinery (resumeSignal, Chat
load-effect, Phase A one-shot) already consumes. Server reuse and the endpoint
both read the single `get_active_conversations` primitive.

## Not in This Change (deliberate)

- **B-hardened** (partial unique index `WHERE ended_at IS NULL`) is **not**
  included: it needs a migration plus a one-time dedup of users already holding
  multiple open threads. `working.db` currently has **Jodie = 4, Lyle = 30** open
  threads (accumulated from the client-only-resume era), so that dedup would
  close 32 threads. For v1, `get_active_conversations` newest-first means both
  paths resume the most recent open thread; the older opens sit unused. A go-live
  reset would clear them anyway. So duplicate open threads are **not yet
  structurally impossible** — B-minimal closes the realistic client race
  (send-before-select), but a genuine concurrent first-send could still
  double-create. Tracked as a follow-up.

## Tests/Checks Run

- `pytest` — **861 passed** (added 6: stream reuse of an open thread, stream
  create-when-none, and four `/api/conversations/current` cases — newest-open,
  null-when-none, 422 missing user, 404 unknown).
- `docs/PROMPT_INVENTORY.md` regenerated (`python -m scripts.extract_prompt_inventory`):
  the only delta is two line-number references shifting (`routes.py:802→813`,
  `821→832`) because the reuse block added lines above two pre-existing
  prompt-like strings. Its drift-guard test passes.
- Frontend `lint` clean; `build` succeeds (`index-De6A1DZP.js`).

## Known Limitations

- Device verification pending (the loop): fresh browser/device as Jodie → lands
  in her newest open thread with history, not blank; send from two tabs → one
  thread, no duplicate.
- Existing stream tests use the real `working.db` with a fake user `user-1` (no
  conversations) so `null → new_request` still holds; the new reuse/endpoint
  tests mock `get_active_conversations` for determinism.

## Follow-Up Work

- B-hardened (partial unique index + open-thread dedup) for a structural
  no-duplicate guarantee — staged separately due to migration + dedup cost.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, model config, memory architecture, scheduler, research,
  or image generation. (`docs/PROMPT_INVENTORY.md` change is a regenerated
  line-number index, not a prompt edit.)
- No schema change; **no migration** (uses the existing `get_active_conversations`
  primitive and `conversations` table as-is).
- No new external dependencies or services.
- No package rename; `tir/` untouched structurally.
- Preserves segmented storage and source attribution: the endpoint and stream
  reuse both validate the user via `_resolve_user` (missing/unknown rejected),
  consistent with the no-silent-default attribution rule.
