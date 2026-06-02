# Attribution login + role-based view + source indicator (Part 2) — v2

Date: 2026-06-01

## Summary

Part 1 made the backend reject a missing/blank `user_id` (422) and added
`GET /api/users/resolve?name=...`. The frontend, however, still auto-selected a
user (admin or `data[0]`) on load and read `activeUserId` from localStorage,
which is null on fresh/cleared state — so chat would 422 by design, and the old
auto-select was itself a silent-default path.

This patch makes the frontend always identify a **resolved known user** before
chat is usable, and tailors the view to that user's role:

- A name-login gate resolves a typed name to a known user via
  `/api/users/resolve`; only the resolved `{id, name, role}` becomes active. A
  typed name is never sent as an identity into chat/upload/image requests.
- Role-based view: `admin` → full current layout; non-admin (household) → chat
  only, with all operator/inspector panels hidden.
- A prominent "You are: NAME" source indicator is always visible in the chat
  view (both roles), so wrong attribution is obvious at a glance.
- A "Switch user" control clears the active user and returns to the gate.

Frontend only — `tir/` (the backend) was Part 1 and is untouched here.

## Files changed

- `frontend/src/api.js`
  - Added `resolveUserByName(name)`: calls `/api/users/resolve`, returning
    `{ ok, status, user }` (422 for blank, 404 for unknown, 200 + user on match).
- `frontend/src/components/NameGate.jsx` (new)
  - Name-entry gate. On submit, resolves the name; 200 → `onResolved(user)`;
    404 → "User not recognized…"; 422 → "Please enter your name."; 401 → secret
    message; other → generic error. Only a resolved known user is passed up.
- `frontend/src/App.jsx`
  - Replaced the `activeUserId` string state with an `activeUser` object
    (`{id, name, role}`) persisted to a new `anam.activeUser` localStorage key
    (the legacy `anam.activeUserId` key is kept in sync for compatibility).
  - `applyActiveUser(user)` (core persist + conversation reconciliation),
    `handleUserResolved(user)` (gate), `selectActiveUser(userId)` (admin
    dropdown → looks up the user), and `handleSignOut()` (clear identity +
    conversation → gate).
  - `fetchUsers()` no longer auto-selects a user; it only validates that the
    stored active user still exists (signs out to the gate if it was deleted).
  - Renders `<NameGate>` when no active user; renders a chat-only layout for
    non-admins; admins keep the full desktop/mobile layout. Passes `onSignOut`
    to `Chat`; uses `isAdmin = activeUser?.role === 'admin'`.
- `frontend/src/components/Chat.jsx`
  - Replaced the free user-switch `<select>` with a **prominent** always-visible
    "You are: NAME" indicator plus a "Switch user" button (`onSignOut`). Removed
    the `users`/`onUserChange` props.
- `frontend/src/styles.css`
  - Added structural/functional classes only (no theme polish): `.name-gate*`,
    `.app-chat-only` / `.chat-only-main`, and a prominent restyle of the
    `.chat-active-user*` indicator (uppercase label + 18px bold accent name).

## Behavior changed

- On load with no resolved active user (fresh/cleared localStorage, or a stored
  user that no longer exists), the name gate is shown and chat is blocked.
- Submitting a known name (case-insensitive, via the backend resolve endpoint)
  activates that user and persists the resolved `{id, name, role}`. Unknown
  name → rejected; blank → prompt.
- Role-based view from `activeUser.role` (no names hardcoded): `admin` → full
  layout (chat + debug + status/registry/system panels, conversation list,
  user-switch dropdown). Non-admin → chat only; the debug panel/toggle,
  Registry (artifact upload + image generation), System (health/memory/
  capabilities, review queue, behavioral guidance), conversation list, mobile
  tab bar, and conversation viewer are all hidden.
- The chat view always shows a prominent "You are: NAME" indicator (both roles)
  and a "Switch user" button that returns to the gate.
- Every chat/upload/image request continues to send `user_id`, now guaranteed
  non-null past the gate.

## One-time re-entry after deploy (expected)

The legacy bare-string `anam.activeUserId` key (from before Part 2) is
**intentionally not auto-restored** as identity. After this deploys, each user
re-enters their name once via the gate; the full `anam.activeUser` blob is then
persisted and restores seamlessly on subsequent loads. This is deliberate and
correct — it guarantees the active identity is a freshly resolved known user
rather than a stale/ambiguous string, consistent with the attribution-integrity
goal.

## Tests/checks run

- No JS test harness exists in this project (no vitest/jest); per the task,
  verification is lint + build + documented manual steps (standing up a harness
  would add a dev dependency). The resolve/role logic is kept in small pure
  pieces (`resolveUserByName`, the `isAdmin` check) for future unit testing.
- `npm --prefix frontend run lint` → clean (eslint, no warnings/errors).
- `npm --prefix frontend run build` → succeeds (vite, 22 modules).
- Python suite unaffected: `python -m pytest -q` → 855 passed (frontend-only
  change). `git diff --check` clean. `frontend/dist` is gitignored (no build
  artifacts in the working tree).
- Manual verification steps (to run with the app up):
  1. Clear localStorage → name gate shown; chat blocked.
  2. Enter an unknown name → "User not recognized"; no proceed.
  3. Enter a blank name → "Please enter your name."
  4. Enter a valid **admin** name (e.g. Lyle after `set-role Lyle admin`) →
     full layout (sidebar, panels, debug).
  5. Switch user → enter a valid **household** name (e.g. Jodie) → chat only;
     no debug/status/registry panels, no conversation list/tabs.
  6. Confirm the prominent "You are: NAME" indicator shows the correct name in
     both roles.
  7. Send a message → it is attributed to the active user (no 422).
  8. "Switch user" → returns to the gate.

## Known limitations

- The role shown is the one captured at gate time (persisted blob); a
  server-side role change is reflected after the next sign-out/in. The
  admin/household split is a view convenience here, not a backend-enforced
  security boundary (out of scope).
- Visual/theme polish is deferred (separate post-go-live task); this is plain
  but correct functional structure.

## Follow-up work

- Out of scope: visual/theme polish, per-device binding, password auth.
- Optional future: a JS test harness (vitest) to unit-test `resolveUserByName`
  and the gate/role logic.

## Project Anam alignment check

1. Assign the entity a name? No — this is about household users, not the entity.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? Yes — and protects its integrity: chat is attributed
   to a resolved known user, never a silent default.
5. Are derived artifacts traceable? N/A (frontend view).
6. Are tool calls recorded? Unaffected.
7. Are created artifacts remembered? Unaffected (now correctly attributed).
8. Is context construction inspectable? The admin retains full debug/status
   panels; household view is a clean conversational surface by design.
9. Does this make autonomy more cumulative? Neutral.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No — frontend only; one-time localStorage re-entry,
    noted above. No DB/schema change.
12. Tests run? Frontend lint + build; Python suite (855 passed); manual steps
    documented.
13. Change core substrate behavior unnecessarily? No — frontend identity/view.
14. Add external dependencies/services? No (no new deps; harness deferred).
15. Preserve workspace vs self-modification distinction? Yes — unaffected.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
