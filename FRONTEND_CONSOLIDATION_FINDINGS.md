# Frontend Consolidation — Findings (device-verified)

Refresh/resume/viewport/keyboard consolidation. These findings are confirmed
against code AND on-device behavior (`:8000`, the production bundle), and they
supersede CC's original §6 runtime-repro analysis where they conflict. Phasing
was A → B → C; A and B are committed, C is next.

## Finding #1 — Desktop height anchor: CLOSED

The desktop layout corruption was a missing viewport height anchor: `.app
{ height: 100vh }` had been commented out, and with it commented the percentage
height chain had no top-level anchor. Operator uncommented it in a prior session;
`.app` now resolves to `100vh` (verified in-browser: `882px` from a live rule).
Desktop renders correctly. No further work. (CC's §6 said "commented out, no
anchor" — that was accurate when written, before the uncomment.)

## Finding #2 — Refresh/resume fan-out: ADDRESSED by Phase B (committed)

A single tab-return fired two uncoordinated resume systems plus a standing
interval: App's resume effect (visibilitychange/focus/pageshow, ~15s throttle →
conversations + health + registries) and Chat's resume effect (same events, ~2.5s
throttle → messages), plus the 30s health interval. Two listener sets, two
throttles, clustered burst on return.

Fix (Phase B): App owns the single resume listener and throttle; Chat reacts to a
monotonic `resumeSignal` counter prop via one ref-baseline-guarded effect (mount
= no-op, conversation-switch ignored, only a genuine bump fetches). Removed Chat's
duplicate listener, `wasHiddenRef`, its timer/throttle refs/constants, and the
related cleanup. ~60 lines out, ~10 in, no new abstraction. The 30s health
interval was left as-is (independent polling, not a resume trigger).

## Finding #3 — Recovery poll: ADDRESSED by Phase A (committed)

**Backend does not persist on mid-stream client disconnect.** Confirmed by code:
`/api/chat/stream` is a synchronous `def` returning `StreamingResponse` over a
sync generator; the assistant `save_message` sits AFTER the token-yield loop,
guarded by `should_persist_assistant`, with no `finally`. On client disconnect the
generator is parked at the token yield and torn down with `GeneratorExit` — which
is a `BaseException`, NOT caught by the loop's `except Exception` — so the code
after the loop (the save) never runs. Confirmed on device: after backgrounding
mid-response and returning, the dropped reply was absent on a clean reload.

The time-based recovery polling (1.5s interval / 30s timeout) therefore recovered
nothing real and was deleted, along with the `recovering` placeholder state. It
was replaced with a single message refetch on an unclean stream end — kept because
iOS sometimes keeps the socket alive and the server finishes, in which case one
refetch adopts the persisted reply.

### Sub-finding (surfaced during Phase A device testing): content-collision in reconciliation

The pending assistant bubble was reconciled to server history by matching the
pending user-message *content* (`hasPersistedAssistantForPending` → exact-string
match via `findLastMessageIndex`). With repeated content (e.g. "Testing" sent many
times), it anchored on an earlier identical user turn that DID get a reply and
wrongly dropped the current interrupted bubble — the bubble briefly showed
"interrupted" then vanished when the one-shot refetch landed. This was pre-existing
merge code that Phase A's refetch was the first to exercise on the disconnect path.

Fix: reconcile by message ID. The user-message id is one identity threaded
end-to-end — minted by `save_message`, surfaced in the `debug` event as
`user_message_id`, and present on every `GET /messages` row as `id`. Stamp
`serverUserMessageId` onto the pending bubble in the debug handler; anchor
reconciliation on `findIndex(m => m.id === anchorId)`; no anchor → keep the bubble.
Did not thread the `done` `message_id` (the user-id anchor covers both completed
and disconnected cases; disconnect has no `done` event). `hasPersistedMatchingUser`
(the optimistic *user* bubble dedup) has the same content-collision shape but was
left content-based — provably benign: a false positive only swaps an optimistic
user bubble for an identical-text server one (no visible change, no assistant
impact). Verified on device: repeated-message mid-stream drop now keeps the
interrupted bubble.

## Finding #4 — iOS keyboard oscillation + occlusion: PHASE C (not started)

Admin login, reproduced in a private window on a fresh chat (so it's the layout
path, not stale state): keyboard up → flashing; dismiss keyboard → stops. Root
cause is a feedback loop in the keyboard-active path — the `position: fixed`
composer driven by the JS-computed `--anam-composer-fixed-top`, plus rAF +
staggered 60/160/320ms `scrollIntoView` timers reacting to `visualViewport`
events, each adjustment provoking another event. The visualViewport `scroll`
listener is the ongoing oscillation feeder (keyboard-drag scroll events).

Two related symptoms, same root system: (a) the flashing/oscillation; (b)
**keyboard up hides the last message** — composer occlusion, the message-list
bottom reserve not accounting for the composer's footprint when the keyboard is
up. A screenshot earlier in the saga showed the composer caught mid-oscillation at
a wrong fixed-top occluding content — same cause, not separate.

**Unverified post-Phase-B observation:** after Phase B, the flashing appears to
have stopped while the occlusion remains. Phase B did not touch this code;
hypothesis is that the old Chat resume listener's refetch-driven re-renders were
one feeder of the oscillation. NOT confirmed — re-verify the flashing during Phase
C (run focus/type/send several times; it was always variable).

Approved direction (CC to re-plan against current committed code, findings-first):
stop hand-computing the composer top from sampled mid-animation viewport
snapshots. Evaluate `interactive-widget=resizes-content` FIRST (could reduce C to
a meta-tag + deleting the sync code); otherwise sticky-bottom composer in a
visual-viewport-height container. Remove the rAF + staggered timers and the
visualViewport `scroll` listener; keep `resize` for the height var. Fix the bottom
reserve so the last message clears the composer. Before deleting `--vh` from App's
`useViewportHeight`, confirm it's fully dead. Verify on `:8000`, BOTH roles.

## Cross-cutting notes

- **Test on `:8000` (built bundle), not `:5173` (Vite dev).** Backgrounding Safari
  mid-stream desyncs HMR; `:5173` gave false results. `:8000` is the go-live path.
- **Phases are more runtime-coupled than the static separation implied** — e.g.
  Phase A's one-shot refetch and Phase B's resume signal both touch the
  backgrounded-return path; the `chatStreamActiveRef` gate keeps them from
  double-fetching (resume signal is suppressed while a stream is active).
- **Backend stream handler** lives in `tir/api/routes.py` (`stream_chat` /
  `generate`); frontend chat lifecycle in `frontend/src/components/Chat.jsx`;
  resume/layout orchestration in `frontend/src/App.jsx`.
