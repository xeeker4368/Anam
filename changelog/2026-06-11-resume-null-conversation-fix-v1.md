# Resume Active-Conversation Null Fix v1 (fetchConversations live-vs-restored)

## Summary

Fixed a vanishing-bubble bug on hard app-switch return: after sending a message
and switching to another app mid-response, returning cleared the assistant bubble
(user message remained, no reply, no "interrupted"). Root cause is pre-existing
App.jsx logic, not Phase A/B/C. `fetchConversations` nulled the active
conversation whenever the active id was merely missing from *that* list response,
which on resume races a freshly-created conversation; the null cascaded to Chat's
load-effect `setMessages([])`, wiping the pane.

## Root Cause

On resume, App's coordinated refresh issues `GET /api/conversations`. The resolve
logic did `if (!candidate) setActiveConversationId(null)` — treating "absent from
this (possibly stale or early) list response" as "deleted". `list_conversations`
reliably returns an existing conversation (newest-first, within the limit, user
JOIN satisfied), and there is no in-app conversation-delete, so a *live* active
conversation is never genuinely gone — its absence from a given response is a
race. Nulling the live id flipped Chat's `conversationId` prop to null, triggering
the load-effect's `else if (!conversationId) setMessages([])` wipe.

This also explained a secondary symptom: a double `GET /…/messages` on resume.
The null→reset toggle re-fired Chat's conversationId load-effect (a second fetch)
on top of the intended Phase B resumeSignal refetch. Removing the toggle collapses
resume to a single coordinated message refetch.

## Files Changed

- `frontend/src/App.jsx` (`fetchConversations` resolve/null path only)

## Behavior Changed

- `fetchConversations` now captures `liveConversationId = activeConversationIdRef.current`
  and only clears the active conversation in the `else if (!liveConversationId)`
  branch. A **live** session id is never nulled by a list refresh; only an
  unvalidated **restored-from-storage** id (e.g. after a go-live reset) is cleared
  when absent. The found-and-belongs path is unchanged.
- Net effect table vs. before:
  - live id, found+belongs → set (unchanged; same-value no-op).
  - live id, not found → keep (was: null) — removes the resume race.
  - live id, found but other-user → keep (was: null); user-switch is already
    handled by `applyActiveUser`/`fetchUsers`, so this cannot legitimately occur.
  - restored id (no live), not found → null (unchanged) — preserves
    genuine-gone cleanup of a stale restored id.

## Why This Is Safe

- No in-app conversation-delete exists (grep-confirmed), so a live active
  conversation cannot be genuinely deleted; "keep the live id" cannot strand a
  real deletion. The only legitimate "gone" case is a restored-from-storage
  phantom after a reset, which is still cleared on the first load where it is
  absent.
- The same-value `setActiveConversationId(candidateConversationId)` on the
  found path is an `Object.is` no-op; React bails out, so it does not retrigger
  Chat's load-effect.

## Tests/Checks Run

- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run build` — succeeds.
- Device-verified on `:8000` via temporary on-screen instrumentation (since
  removed): hard app-switch return for a new conversation showed only the benign
  cold-start mount WIPE, no post-resume `APP nulling`, no post-resume WIPE, and
  the assistant bubble survived (settled to "interrupted", id-anchor reconciliation
  correct). Single `/messages` refetch on resume confirmed.

## Known Limitations

- A genuinely deleted *live* conversation (no in-app trigger today) would leave a
  phantom active id rather than clearing it; it self-heals to an empty chat and is
  effectively impossible in the household model.

## Follow-Up Work

- None. Resume coordination (Phase B) and the keyboard fix (Phase C) are separate
  changes.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, guidance, model config, memory, scheduler, research,
  image generation, or backend behavior.
- No schema change; no migration required.
- No new external dependencies or services.
- No package rename; `tir/` untouched.
- Net reduction in spurious state churn (no null→reset toggle, single resume
  refetch), consistent with the ACTIVE_TASK directive to reduce refresh/state
  complexity. Debug/instrumentation fully removed.
