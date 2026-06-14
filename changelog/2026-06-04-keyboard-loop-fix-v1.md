# Keyboard Loop + Composer Occlusion Fix v1 (Frontend Consolidation Phase C)

## Summary

Removed the iOS keyboard-active feedback loop and the composer-occlusion bug by
deleting the hand-computed `position: fixed` composer top and the rAF + staggered
`scrollIntoView` storm, and reverting the keyboard-active composer to the in-flow
sticky-bottom rule already used elsewhere. The keyboard-active chat container is
sized to a single visualViewport height var (updated on `resize` only), and the
in-flow composer rides above the keyboard with the message list naturally sized
above it. This is the final phase of the refresh/resume/viewport/keyboard
consolidation (Findings #1–#4).

## Root Cause (confirmed in code)

`updateVisualViewportVars` computed `--anam-composer-fixed-top` from
`visualViewport.offsetTop/height` mid-animation snapshots; `scheduleViewportSync`
fired a rAF plus `60/160/320ms` staggered `scrollIntoView` timers; the
visualViewport effect listened to both `resize` and `scroll`. Each composer
reposition + scroll provoked another visualViewport event (the `scroll` listener
was the re-entrant feeder), oscillating. The composer being `position: fixed`
(out of flow) is also why the last message was occluded — the message list
extended under it, relying on a mis-computed reserve.

## Files Changed

- `frontend/src/components/Chat.jsx`
- `frontend/src/styles.css`
- `frontend/src/App.jsx`

## Behavior Changed

- Keyboard-active composer is now in-flow sticky-bottom (the base
  `.m-body .input-area { position: sticky; bottom: 0 }` applies) inside the
  `.m-body > .chat.keyboard-active { height: min(100%, var(--anam-visual-viewport-height)) }`
  container. No JS-computed composer top.
- `updateVisualViewportVars` now writes only `--anam-visual-viewport-height`
  (`visualViewport.height ?? window.innerHeight`).
- The visualViewport effect listens to `resize` only (no `scroll`); on the
  debounced resize it updates the height var and does a single
  `scrollToLatestMessage('auto')`.
- Focus/blur update the height var and do a single scroll-to-bottom (no storm).

## Code Removed / Replaced

- Chat.jsx: `scheduleViewportSync` (rAF + `60/160/320ms` staggered scroll timers);
  the visualViewport `scroll` listener; `viewportRafRef` and
  `viewportDelayTimersRef` (+ their unmount cleanup). `updateVisualViewportVars`
  reduced from ~36 lines (10 `setProperty` calls, most dead) to a single var write.
- styles.css: deleted `.m-body .chat.keyboard-active .input-area` (the
  `position: fixed; top: var(--anam-composer-fixed-top)` override) and
  `.m-body .chat.keyboard-active .messages-container` (the occluded-space padding
  override). Pruned dead `:root` vars: `--anam-visual-viewport-bottom-gap`,
  `--anam-composer-height`, `--anam-composer-fixed-top`,
  `--anam-composer-occluded-bottom-space`, `--vv-height`, `--vv-offset-top`,
  `--composer-height`, `--composer-fixed-top`. Kept `--anam-visual-viewport-height`
  and `--anam-mobile-composer-reserve`.
- App.jsx: removed the dead `useViewportHeight` hook and its call (wrote `--vh`,
  read nowhere).

`inputAreaRef` is retained (still attached in JSX) but no longer read by JS.
Production CSS shrank ~0.77 kB and JS ~2 kB.

## interactive-widget Meta

Not added. `interactive-widget=resizes-content` is a Chromium feature and is a
no-op on iOS Safari (the iPhone target), so it cannot eliminate the visualViewport
JS there; the fix does not depend on it. (Optional Android-forward enhancement,
deferred by request.)

## Fallback (not applied)

If device testing shows occlusion persists on a given iOS version, the planned
fallback is to reintroduce a single computed composer bottom-offset, recomputed
ONLY on the debounced `resize` settle (never on `scroll`, never via rAF/staggered
timers), keeping the loop dead. Per instruction, this would be re-checked on
device and surfaced before any commit — not committed as a silent pivot.

## Tests/Checks Run

- `npm --prefix frontend run lint` — clean.
- `npm --prefix frontend run build` — succeeds; bundle `index-CeeOPEFi.js` /
  `index-ChqkqTeF.css`.

## Known Limitations

- On-device `:8000` verification pending (acceptance below). iOS visual-viewport
  /sticky behavior is the part most likely to need the fallback; this is the
  riskiest phase.

## Device Acceptance (to verify on :8000, BOTH roles)

- Focus / type / send several times: confirm the flashing is genuinely gone (not
  intermittent), keyboard up and down.
- Confirm the last message is no longer hidden behind the composer with the
  keyboard up.
- Admin mobile (`.m-body`) and household (`.app-chat-only`) — household already
  used the in-flow composer; this also removes the shared-JS storm from its path.

## Follow-Up Work

- None queued from the consolidation plan — this is the last of Findings #1–#4
  (desktop height was already closed). Resume/stream code (Phases A/B) untouched.

## Addendum — Focus-Time Viewport Re-Sample (device-test fix, folded into Phase C)

Device testing on `:8000` (admin mobile) confirmed the flashing/oscillation is
gone and the sticky composer lands correctly once the height var is right. But a
focus-time bug remained: on focus (keyboard animating up) BEFORE typing, the
composer was pushed off-screen below the keyboard; it jumped to the correct spot
only after the first keystroke.

### Root cause

Phase C replaced the focus path's staggered re-samples with a single synchronous
`updateVisualViewportVars()` on focus. On iOS the keyboard-reduced
`visualViewport.height` is NOT available synchronously at focus time (the resize
fires unreliably / late on keyboard-open), so the focus-time read captured the
pre-keyboard full height → `.m-body > .chat.keyboard-active` (and household
`.app-chat-only`) sized to full height → in-flow composer sat below the keyboard
until a later resize that effectively coincided with the first keystroke. The
deleted staggered timers had been doing this legitimate re-sample job in addition
to the harmful scroll storm; Phase C removed both.

### Fix (Variant B — three fixed settle re-samples)

In `handleInputFocus`, keep the immediate on-focus `updateVisualViewportVars()`
(covers already-up refocus), then re-sample the height at fixed ~200/500/800ms
delays to bracket a slow keyboard-open animation. Timers are tracked in
`focusSettleTimersRef` and cleared on blur and on unmount. The `resize` listener
remains as the ongoing backstop.

Loop stays dead by construction: the settle timers do height-only writes
(`--anam-visual-viewport-height`), which resize a CSS container but cannot resize
the visual viewport, so they cannot trigger a `resize` and cannot feed themselves.
No scroll, no rAF, no scroll listener. This is not the old 3-timer storm (that
storm computed `fixed-top` and fired `scrollIntoView`, which fed the deleted
`scroll` listener).

### Scope

`Chat.jsx` only — the focus/blur handlers, one ref, and unmount cleanup. No CSS or
App.jsx change. Both roles are covered (shared `Chat` component / shared height
var). `lint` + `build` clean; bundle `index-DA7Dd3mU.js`.

### Device acceptance (re-test on :8000, both roles)

- Tap the composer full-screen, BEFORE typing: composer animates to the correct
  position above the keyboard on focus, without needing a keystroke.
- Flashing still gone across repeated focus/blur; last message still clears the
  composer.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, guidance, model config, memory, scheduler, research,
  image generation, or backend behavior.
- No schema change; no migration required.
- No new external dependencies or services.
- No package rename; `tir/` untouched.
- Net reduction in frontend complexity (removed a feedback loop and ~8 dead CSS
  vars + a dead hook), consistent with the ACTIVE_TASK directive to reduce
  refresh/viewport complexity. Debug/instrumentation untouched.
