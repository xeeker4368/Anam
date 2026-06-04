# Resume Coordination v1 (Frontend Consolidation Phase B)

## Summary

Replaced Chat.jsx's own tab-return resume listener with a single signal driven by
App.jsx's existing resume listener. Previously a single tab-return fired two
uncoordinated systems — App's resume (visibility/focus/pageshow, ~15s throttle →
conversations + health + registries) and Chat's resume (same events, ~2.5s
throttle → messages) — producing a clustered burst with two different throttles.
Now App owns the only visibility/focus/pageshow listener and the only throttle;
Chat re-syncs its messages in response to a counter prop App bumps once per
coordinated resume. Net reduction in code, no new abstraction or module.

## Files Changed

- `frontend/src/App.jsx`
- `frontend/src/components/Chat.jsx`

## Behavior Changed

- `App` adds a `resumeSignal` counter (`useState(0)`), bumped in `runResumeRefresh`
  after the existing conversations/health/registries fetches — so the bump is
  gated by the same `chatStreamActiveRef` guard and ~15s throttle as the rest of
  App's resume. It is passed to `<Chat>` as `resumeSignal`.
- `Chat` reacts via one effect: when `resumeSignal` actually changes (ref-baseline
  guard), and not streaming, and a conversation is active, it calls
  `fetchMessages(conversationId)`. Mount is a no-op (baseline equals current); a
  conversation switch is ignored here (the conversationId-load effect already
  handles it) — only a genuine resume bump fetches.
- Chat's message-refresh-on-resume throttle changes from ~2.5s to App's ~15s
  (single unified throttle). See "Intentional behavior change".

## Code Removed (Chat.jsx)

- The entire resume `useEffect` (visibilitychange/focus/pageshow listeners,
  `scheduleResumeMessageRefresh`, `runResumeMessageRefresh`, handlers, listener
  add/remove and timer cleanup).
- `wasHiddenRef` — write-only after Phase A removed its only consumer; both the
  producer (this effect) and the declaration are now gone.
- `resumeMessageRefreshTimerRef`, `lastResumeMessageRefreshRef`.
- Constants `RESUME_MESSAGE_REFRESH_DELAY_MS`, `RESUME_MESSAGE_REFRESH_THROTTLE_MS`.
- The `resumeMessageRefreshTimerRef` clearing blocks in `setStreamingActive` and
  in the unmount cleanup effect.

Added in Chat.jsx: `resumeSignal` prop, `lastResumeSignalRef`, and the small
signal effect. Net: ~60 lines removed, ~10 added; production bundle shrank
~0.8 kB.

## Intentional Behavior Change

Resume message-refresh throttle goes ~2.5s → ~15s. Justification: Phase A's
one-shot refetch (in `sendMessage`'s `finally`, on an unclean stream end) already
covers the urgent missed-tail case — a reply that landed while the tab was briefly
backgrounded. The coordinated resume path is therefore reduced to a periodic
re-sync on return, for which the unified ~15s throttle is sufficient.

## Double-Fetch / Race (mid-stream return)

No double-fetch in the normal case. On a mid-stream background, JS is suspended;
on return the resume events fire before the suspended stream's read rejection is
processed, so `chatStreamActiveRef` is still `true` and App's resume is gated —
`resumeSignal` is not bumped. The stream rejection then runs Phase A's single
one-shot refetch. The signal effect additionally guards `isStreamingRef`. A rare
interleaving (a second resume event after teardown) yields at most one extra
idempotent `GET /messages` that the merge reconciles.

## Out of Scope (unchanged)

- The standing 30s `fetchHealth` interval (App.jsx) — independent polling, not a
  resume trigger.
- Keyboard/viewport code — untouched (Phase C).

## Tests/Checks Run

- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run build` — succeeds; bundle `index-CQHSfbjH.js`.

## Known Limitations

- On-device `:8000` verification pending (acceptance below), both admin and
  household.

## Device Acceptance (to verify on :8000)

- Idle tab away and return → a single coordinated refresh, not a burst of the old
  endpoints.
- Tab away mid-stream and return → no double-fetch, stream unaffected, Phase A
  recovery still behaves.
- Both admin and household layouts (App's resume effect runs above the role-based
  early returns, so both get the coordinated path).

## Follow-Up Work

- Phase C — Keyboard loop (Finding #4): stop hand-computing composer top from
  sampled viewport snapshots; covers both admin-mobile and household layouts.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, guidance, model config, memory, scheduler, research,
  image generation, or backend behavior.
- No schema change; no migration required.
- No new external dependencies or services.
- No package rename; `tir/` untouched.
- Reduced frontend complexity (net removal of a duplicate listener system),
  consistent with the ACTIVE_TASK directive to reduce refresh/state complexity.
  Preserved raw chat experience: optimistic/pending bubbles still reconcile
  against server-persisted history; debug/instrumentation untouched.
