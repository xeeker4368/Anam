# Recovery-Poll Replacement v1 (Frontend Consolidation Phase A)

## Summary

Replaced the time-based mid-stream "recovery polling" machinery with a single
message refetch when a chat stream ends without a clean `done` event. This is
Phase A of the refresh/resume/viewport/keyboard consolidation. It removes the
30s recovery poll loop and the `recovering` placeholder state, and reconciles a
disconnected reply against server-persisted history exactly once.

Root cause confirmed (code + device, per planning brief): `/api/chat/stream` is
a sync generator whose assistant `save_message` runs AFTER the token-yield loop.
On mid-stream client disconnect the generator is torn down at a `yield` and
raises `GeneratorExit` (a `BaseException`, not `Exception`), so `except Exception`
misses it and the assistant reply is never persisted. Time-based polling never
catches anything that lands late; one refetch cheaply catches the iOS edge where
the socket stays alive and the server does finish and save.

## Files Changed

- `frontend/src/components/Chat.jsx`

## Behavior Changed

- Added a one-shot recovery refetch: when a stream began (`streamStarted`) but
  ended without a clean `done` event, without a server `error` event, and without
  an explicit user/unmount abort, `Chat` now calls `fetchMessages` exactly once.
  - If the server persisted the assistant reply, the existing merge logic adopts
    it and drops the local bubble.
  - If not, the local bubble is settled as `interrupted` ("Response interrupted;
    send again if needed.").
- Added a `streamStarted` gate so a failure before streaming begins (e.g. HTTP
  error, backend unreachable) still shows a `Connection error:` bubble and does
  NOT trigger a recovery refetch.
- Cleaned up the `catch` block: removed the `wasHiddenRef`-driven
  `resume_recovery` path. A mid-stream interruption after the stream started now
  falls through to the single refetch in `finally` instead of immediately showing
  a hard `Connection error` bubble.
- Normal history-fetch-on-load and the clean `done` completion path remain
  authoritative and unchanged.

## Code Removed

- `recoveringAssistantMessage` helper and the `recovering` message state/render
  branch ("Response still finishing...").
- `startRecoveryPolling`, `clearRecoveryPoll`, `markRecoveryTimedOut`, and the
  `recovering`-tracking `useEffect`.
- Recovery refs: `recoveryPollTimerRef`, `recoveryPollDeadlineRef`,
  `recoveryConversationIdRef`, `hasRecoveringPendingRef`, plus their unmount and
  conversation-change cleanup.
- Constants `RECOVERY_POLL_INTERVAL_MS` and `RECOVERY_POLL_TIMEOUT_MS`.
- Stray `recovering: false` fields in the message updaters.

`interruptedAssistantMessage` is kept (used to settle the local bubble).

## Tests/Checks Run

- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run build` — succeeds.

## Known Limitations

- On-device verification still pending (per the per-phase loop): background a
  chat mid-response on iOS, return, and confirm the dropped reply is recovered if
  the server saved it, or settled as interrupted if it did not — with no 30s poll.
- `wasHiddenRef` is intentionally retained: its only consumer was removed here,
  but its producer (the Chat resume effect) is removed in Phase B. After Phase A
  it is write-only by design; Phase B deletes the declaration and the effect.
- Backend non-persistence on disconnect (`GeneratorExit` skipping `save_message`)
  is unchanged and out of scope; the decided remedy is this client-side refetch.

## Follow-Up Work

- Phase B — Resume coordination (Finding #2): App-owned single resume listener +
  signal to Chat; removes the Chat resume effect and `wasHiddenRef`.
- Phase C — Keyboard loop (Finding #4): stop hand-computing composer top from
  sampled viewport snapshots; covers both admin-mobile and household layouts.

## Addendum — ID-Based Pending Reconciliation (device-test fix, folded into Phase A)

Device testing on `:8000` surfaced a real bug exercised by the new recovery
refetch: after a mid-stream drop the bubble correctly settled to "interrupted",
then **vanished** when the one-shot `fetchMessages` landed — but only for a
REPEATED message (a UNIQUE message stuck correctly).

### Root cause (pre-existing, not introduced by Phase A)

`hasPersistedAssistantForPending` matched the pending bubble to a server
user-message by exact CONTENT string, then checked whether any assistant message
followed it. With repeated content it anchored on an EARLIER identical user turn
that DID get a reply, concluded "this turn was answered", and dropped the local
interrupted bubble — even though the backend never persisted THIS turn's reply
(mid-stream disconnect). A false-positive content collision. Phase A's refetch is
simply the first thing to exercise it on the disconnect path.

### Fix — reconcile by message id, not content

- The `debug` stream event already carries `user_message_id` (the server's
  persisted user-message id, `routes.py:626`); the refetched message list carries
  the same id per message (`get_conversation_messages` `SELECT *`). The `debug`
  handler now stamps `serverUserMessageId` onto the pending assistant bubble.
  `interruptedAssistantMessage` spreads `...message`, so the id survives the
  settle and is present in state before the merge reads it.
- `hasPersistedAssistantForPending` now anchors on `serverUserMessageId` via
  `serverMessages.findIndex(m => m.id === anchorId)` instead of re-matching
  `pendingForUserContent`. A unique anchor cannot collide with an identical
  earlier turn. No anchor present → returns `false` (keep the bubble) as a safe
  fallback.
- Removed `findLastMessageIndex` — it was used only by the old content anchor.

### Deliberately not changed

- `hasPersistedMatchingUser` (optimistic USER-bubble dedup) has the same
  content-matching shape but is benign: the turn's user message is persisted
  (`routes.py:429`) before streaming/disconnect, so a content match reliably
  reflects this turn's presence; and a false positive only swaps the optimistic
  bubble for a server user message with identical text — no visible loss, no
  assistant-bubble impact. Left content-based per scope discipline.
- The `done` `message_id` is not threaded: the user-id anchor covers both the
  completed and disconnected cases, and the disconnect case has no `done` event.

### Also in this patch

- Reverted the temporary `build A1` / `chat-build-marker` span (staleness-check
  scaffolding; never intended to ship).

### Device acceptance (to verify on `:8000`)

- Mid-stream drop with a REPEATED message leaves the interrupted bubble in place
  (was vanishing).
- Unique-message drop still leaves the bubble.
- Normal completion still yields the local bubble to the server copy.
- HTTP rejection (422/403) still shows its specific error and does not refetch
  (rejected before `streamStarted`).

## Project Anam Alignment Check

- Did not assign the entity a name or visual identity.
- Did not add a personality, alter `soul.md`, guidance, prompts, model config,
  memory architecture, scheduler, research, or backend behavior.
- No schema change; no migration required.
- No new external dependencies or services.
- Preserved raw chat experience: optimistic/partial bubbles are reconciled
  against server-persisted history rather than replaced by inferred state, and
  debug/instrumentation paths are untouched.
- Reduced frontend complexity (net removal of recovery machinery), consistent
  with the ACTIVE_TASK directive to avoid adding recovery layers.
