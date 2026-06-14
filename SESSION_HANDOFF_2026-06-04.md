# Session Handoff — 2026-06-04 (Frontend Consolidation A/B done, C next)

This continues the frontend refresh/resume/viewport/keyboard consolidation. Paste
forward to resume. Read alongside `FRONTEND_CONSOLIDATION_FINDINGS.md` (the
device-verified findings) and the existing `SESSION_HANDOFF.md` open-items.

## Current state of the system

Three commits landed on `main` this session, in this order:

1. **`start.sh` LAN backend bind fix** (`changelog/2026-06-04-lan-backend-bind-v1.md`,
   plus a `docs/GO_LIVE_RESET_RUNBOOK.md` network-hardening checklist entry).
   `--lan` now binds the backend to `0.0.0.0:8000` (was loopback-only, so the
   backend was unreachable from phones). Default (no `--lan`) stays `127.0.0.1`.
2. **Phase A — recovery-poll replacement + id-anchored reconciliation**
   (`changelog/2026-06-04-recovery-poll-replacement-v1.md`, `Chat.jsx`).
3. **Phase B — resume coordination**
   (`changelog/2026-06-04-resume-coordination-v1.md`, `App.jsx`, `Chat.jsx`).

Consolidation status: **Finding #1 (desktop anchor) closed**, **#2 (resume
fan-out) = Phase B, done**, **#3 (recovery poll) = Phase A, done**, **#4
(keyboard) = Phase C, NOT started — next step.**

All three commits were device-tested on **`:8000`** (the production bundle) before
committing, both admin and household roles where relevant.

## Decisions made this session (and why)

- **Recovery poll deleted, replaced with a one-shot refetch** (Phase A). Confirmed
  both by code trace (sync streaming generator is torn down at the token yield on
  client disconnect; `GeneratorExit` is not caught by `except Exception`, so the
  assistant `save_message` never runs) and by device test (dropped reply absent
  after a clean reload → backend never persisted it). Time-based polling recovered
  nothing real. Kept a single refetch on unclean stream end because iOS sometimes
  keeps the socket alive and the server finishes — one refetch catches that edge.

- **Reconcile the pending assistant bubble by message ID, not content** (Phase A
  follow-on). The old `hasPersistedAssistantForPending` matched by exact content
  string; with repeated messages ("Testing" sent many times) it anchored on an
  earlier identical turn that *did* get a reply and wrongly dropped the current
  interrupted bubble. Fix: stamp `serverUserMessageId` (from the `debug` event's
  `user_message_id`) onto the bubble and anchor reconciliation on
  `serverMessages.findIndex(m => m.id === anchorId)`. The user-message id is a
  single identity threaded end-to-end (mint → debug event → GET /messages `id`).
  Did NOT thread the `done` `message_id` (the user-id anchor covers both cases;
  the disconnect case has no `done` event). Left `hasPersistedMatchingUser`
  content-based (assessed provably benign — a false positive only swaps an
  optimistic user bubble for an identical-text server one).

- **Resume coordination via a single signal** (Phase B). App owns the only
  visibility/focus/pageshow listener and the only throttle; Chat reacts to a
  monotonic `resumeSignal` counter prop via one ref-baseline-guarded effect.
  Removed Chat's duplicate resume listener, `wasHiddenRef` (write-only after Phase
  A retired its consumer), its timer/throttle refs and constants, and the related
  cleanup. Intentional behavior change: message-refresh-on-resume throttle
  2.5s → 15s, justified because Phase A's one-shot now owns the urgent missed-tail
  case, so resume refetch degrades to periodic re-sync where 15s is fine.

- **`--lan` binds the backend wide** (home-LAN-only, trusted-household model;
  operator accepted the unauthenticated-API + `0.0.0.0` exposure for a private
  LAN). CORS untouched — confirmed unnecessary because the frontend calls the
  backend same-origin on `:8000` (relative paths, backend serves the built
  frontend). Setting `ANAM_API_SECRET` was tracked as a go-live follow-up, NOT
  bundled into the bind fix.

## Known issues / next steps

- **Phase C — keyboard loop (NEXT).** Re-plan against the CURRENT committed code,
  because Phase B may have changed the picture (see gotcha below). Approved
  *direction* (not yet a committed plan): stop hand-computing the composer top
  from sampled mid-animation viewport snapshots; either sticky-bottom composer in
  a visual-viewport-height container, or `interactive-widget=resizes-content`
  (evaluate this FIRST — if it works it could shrink C to a meta-tag + deleting
  the sync code). Remove the rAF + staggered 60/160/320ms `scrollIntoView` timers
  and the visualViewport `scroll` listener (the ongoing oscillation feeder); keep
  `resize` to update the height var. Before deleting `--vh` from App's
  `useViewportHeight`, confirm the hook writes only that var and nothing reads it.
  Verify on `:8000`, BOTH roles. Loop: CC findings-first → plan → review → PATCH
  APPROVED → implement + changelog → `:8000` device test → commit.

- **NEW device observation feeding Phase C:** after Phase B, the keyboard
  *flashing* appears to have stopped, and a cleaner symptom surfaced — **keyboard
  up hides the last message** (composer occlusion: the message-list bottom reserve
  doesn't account for the composer's footprint with the keyboard up). The
  occlusion is the more reproducible thing to fix against. See gotcha re: the
  flashing.

## Parked (deliberately — do not patch around)

- **Conversation model: segmented vs. continuous** (architecture decision,
  pre-go-live). Operator's mental model is one continuous thread per user; system
  is discrete per-session. Touches chunking, retrieval, the conversation list,
  cross-device continuity, attribution, and **blocks the conversation
  "active"-badge fix**. Decide before the go-live wipe (cheapest time to change
  memory structure). Three questions to answer: (1) minimal change for continuous
  *experience* without breaking chunking/retrieval — is it "always resume one
  thread + drop the list, storage stays segmented underneath," or deeper? (2) does
  continuous help or hurt retrieval quality? (3) confirm it simplifies rather than
  breaks the per-message attribution work. Note: continuous *experience* ≠
  continuous *storage* — don't conflate them.

- **Ctrl+C double-press orphans the backend.** Diagnosed, not fixed. `cleanup()`
  resets the trap (`trap - INT TERM`) then stops frontend first, backend second; a
  second Ctrl+C mid-shutdown kills the script before the backend is stopped,
  leaving port 8000 held. Fix: `trap '' INT TERM` during cleanup (ignore, don't
  reset). Small CC task, plan-check loop.

## Pre-go-live (not urgent)

- Automated off-drive backup (pending a USB drive).
- LAN reachability — backend is now reachable on `:8000` via the bind fix; do a
  full verify pass.
- Config-decision pass: temperature in tracked config; image-gen agent tool OFF;
  `scheduler.go_live=true`.
- **Set `ANAM_API_SECRET` before go-live** (new this session; in the runbook's
  network-hardening checklist). Enforcement exists end-to-end but is dormant while
  unset; with the backend now bound to `0.0.0.0`, set it before the wipe.

## Gotchas / things to watch

- **Test on `:8000`, NOT `:5173`.** This cost ~an hour this session. `:5173` is
  the Vite dev server; backgrounding Safari mid-stream (exactly the drop test)
  desyncs HMR, so the phone can run code that doesn't match the source. `:8000`
  serves the built `dist/` and is the go-live path. Hard-refresh after a rebuild
  (Safari may cache `index.html` pointing at the old hashed bundle).

- **The "flashing stopped after Phase B" result is unverified and suspicious.**
  Phase B did not touch keyboard/viewport code. Hypothesis: the old Chat resume
  listener's refetch-driven re-renders were one feeder of the
  scroll↔viewport-sync oscillation, and removing it damped the loop. If true, the
  Phase C keyboard diagnosis is less severe than the original repro. DO NOT bank
  it — when testing C, run focus/type/send several times (the oscillation was
  always variable) to confirm whether flashing is gone or just intermittent.

- **When code analysis repeatedly predicts X and the device shows not-X, suspect
  you're not running the analyzed code.** That pattern (this session) meant stale
  bundle / wrong server, not a subtle logic bug. Confirm build freshness before
  deep-diagnosing device behavior.

- **`start.sh`/repo doc drift:** PROJECT_STATE.md said the static-serving path was
  "deferred," but `:8000` actively serves `dist/`. Reality leads the docs in a few
  places — verify against running code, not docs. (Reconcile during the go-live
  config pass.)

- **Uncommitted work doesn't sync.** The repo sync only carries commits; in-flight
  plans/findings that live only in chat are invisible to the next session (this
  bit us — the "approved A/B/C plan" turned out never to have existed as a doc).
  That's why this handoff + the findings doc exist as committed files.
