# Session Handoff — Frontend Consolidation (keyboard replacement pending)

Supersedes SESSION_HANDOFF_2026-06-04. Pair with `FRONTEND_CONSOLIDATION_FINDINGS.md`
and the new `MEMORY_ARCHITECTURE_NOTES.md` (the parked design agenda). Loop unchanged:
CC plans → Lyle pastes to reviewer → PATCH APPROVED → CC implements + changelog,
no commit → Lyle device-tests on :8000 → Lyle commits.

## Current state — what's on `main` vs in the working tree

**Committed on `main`:**
- Phase A — recovery-poll replacement + id-anchored reconciliation (`17d0fa9`)
- Phase B — resume coordination (`4738264`)
- LAN backend bind fix (`6b177a2`)
- docs handoff (`f49b563`)

**Uncommitted working tree:**
- `App.jsx` — 3 clean hunks, no instrumentation: #1 `useViewportHeight` fn removal
  (~L114), #2 its call site (~L172) — both Phase C dead-code; #3 `fetchConversations`
  resume-null fix (~L234) — **ready to commit, device-verified.**
- `Chat.jsx` — the abandoned Phase C keyboard apparatus + focus-trace instrumentation.
- `main.jsx` — debug-overlay wiring; `debugOverlay.jsx` — the overlay file.
- `styles.css` — Phase C keyboard CSS.
- Changelogs: `2026-06-11-resume-null-…` (keep); `2026-06-04-keyboard-loop-fix-…`
  (documents the ABANDONED keyboard approach — delete in Part 3).

## The keyboard saga — RESOLVED diagnosis, replacement pending

Findings #1 (desktop anchor), #2 (resume fan-out → Phase B), #3 (recovery poll →
Phase A) are **done and committed**. Finding #4 (keyboard) went through multiple
failed fixes (remove storm → focus timers → 3 settle timers) before the root cause
was proven by on-device instrumentation:

**Root cause (proven by trace):** iOS Safari does NOT report the keyboard-reduced
`visualViewport.height` at focus time. Trace showed `vvHeight` stuck at the full
height (721) through all three settle ticks (200/500/800ms); the reduced value (400)
only appeared at a `resize` ~15s later, coinciding with interaction. **No
measurement-based approach can work** — the value isn't available when needed. Also
confirmed: `position: fixed; bottom: 0` is NOT viable (iOS anchors fixed elements to
the layout viewport, which the keyboard doesn't resize; Safari won't move them to
dodge the keyboard — that's likely why the original author reached for visualViewport
computation in the first place).

**The actual fix (Part 3 below):** stop measuring. The rigid `height:100dvh;
overflow:hidden` shell TRAPS the composer so Safari's native focus-scroll can't move
it above the keyboard. Remove the clipping, let the document be taller than the
keyboard-shrunk viewport, and the browser scrolls the focused composer into view for
free — the way it does in every other app. This is a **replacement, not another
patch** — that distinction is the whole point (we were in fix-on-fix).

## The approved plan (CC's Parts 1/2/3) — execution order

**Part 1 — strip focus-trace instrumentation. APPROVED, ready to run.**
Delete `debugOverlay.jsx`; remove import + `<DebugOverlay/>` from `main.jsx`; remove
`pushDebug` import + the focus-trace logging from `Chat.jsx` (revert settle timers,
resize handler, onChange to plain forms). grep-confirm zero `anam-dbg`/`pushDebug`/
overlay refs; lint + build.

**Part 2 — commit ONLY the resume-null fix. APPROVED, ready to run.**
`git add -p frontend/src/App.jsx` → stage hunk #3 only (skip #1/#2);
`git add changelog/2026-06-11-resume-null-conversation-fix-v1.md`; verify staged tree
builds (`git stash push --keep-index` → build → pop); commit:
`"Fix vanishing-bubble on resume: don't null a live conversation in fetchConversations"`.
**Decision:** Phase C non-keyboard cleanup (`--vh`/`useViewportHeight`, dead vars,
App.jsx hunks #1/#2) is FOLDED INTO Part 3, not committed now — same files the
keyboard rewrite rewrites; committing now = churn.

**Part 3 — keyboard replacement. DIRECTION approved; concrete diff NOT yet reviewed.**
Authoring: `git checkout HEAD -- frontend/src/components/Chat.jsx frontend/src/styles.css`
to discard the abandoned intermediate, then author the native-scroll shell against the
committed baseline. (App.jsx NOT reset — hunks #1/#2 kept and committed here.)
- Remove (JS): `updateVisualViewportVars`, the visualViewport resize effect, the
  [200,500,800] settle timers, `focusSettleTimersRef`, `keyboardActive` (if unused).
- Remove (CSS): `--anam-visual-viewport-height`, the `.keyboard-active` height rule,
  the rigid `.app-mobile { height:100dvh; overflow:hidden }` and `.m-body { overflow:hidden }`
  clipping, dead `:root` vars, and (App.jsx) `useViewportHeight`/`--vh`.
- Replace: `.app-mobile` → `min-height:100dvh`, scrollable, `overscroll-behavior-y:
  contain`; `.m-header` → `position:sticky; top:0`; `.m-tabs` → `position:sticky;
  bottom:0`; messages + composer in normal/sticky flow; auto-scroll-to-bottom via
  `scrollIntoView` on an end marker. On keyboard open the 100dvh document exceeds the
  shrunk viewport → Safari scrolls the composer above the keyboard. No JS, no measurement.
- Trade-offs (flagged, acceptable): independent inner-list scroll → window scroll
  (reads the same for a chat); guaranteed no-rubber-band → small overscroll possible
  while keyboard up (mitigated by `overscroll-behavior`).
- Commit = App.jsx (hunks #1/#2) + rewritten Chat.jsx + rewritten styles.css + new
  changelog; delete the abandoned keyboard-loop changelog.

**Part 3 device acceptance (BROADER than focus alone — it's a shell restructure):**
on `:8000`, both roles: (1) new/empty chat, tap composer, DON'T type → composer above
keyboard on focus alone; (2) long conversation scrolls naturally, auto-scroll-to-bottom
works, sticky header/tabs stay put; (3) rubber-band/overscroll doesn't feel broken,
keyboard up and down; (4) flashing stays gone across several focus/blur cycles;
(5) existing-conversation case, not just new/empty.

## Newly surfaced bug (separate, logged) — household role gating

Logged in as **Jodie** (a household user), the device showed the **admin** layout
(bottom tab bar Chat/History/Media/Status/Debug present). Household users should get
the chat-only `.app-chat-only` view with no operator surfaces. Either Jodie's role is
set to admin in the data, or App.jsx's `isAdmin` gating isn't routing a non-admin to
the chat-only view. **Pre-go-live relevant** (a household user seeing operator
surfaces is a permissions issue). NOT in scope for the keyboard work. Side effect:
we could not use "household" as a known-good reference for the keyboard fix, because
we never confirmed the household layout actually renders.

## Parked (deliberately — do not patch around)

- **Conversation/memory model decision** — now greatly expanded; see
  `MEMORY_ARCHITECTURE_NOTES.md`. Still pre-go-live, still blocks the active-badge fix.
- **Cleanup audit** (dead code, GPT-era abandoned paths) — sequenced AFTER the
  memory-model decision (it changes what's "dead"). Evidence-based REMOVAL only, in
  small reviewed batches against the test suite — NOT refactoring of working code.
  Note from this session: the app-shell rigidity itself is a candidate architectural
  question, not just dead-code removal.
- **Ctrl+C double-press** orphans the backend — diagnosed (`trap '' INT TERM` during
  cleanup), not implemented.
- **Pre-go-live list:** off-drive backup (pending USB); LAN reachability full verify
  (backend now reachable on :8000 via the bind fix); config pass (temperature tracked,
  image-gen tool OFF, `scheduler.go_live=true`); **set `ANAM_API_SECRET` before
  go-live** (in the runbook network-hardening checklist; backend now binds 0.0.0.0).
- **Moltbook posting** — deferred post-launch (preserve human-only baseline).

## Gotchas / lessons (expensive ones from this session)

- **Test on `:8000` (built bundle), NOT `:5173`.** Backgrounding Safari mid-stream
  desyncs Vite HMR, so `:5173` can run code that doesn't match source. Cost ~an hour.
  Hard-refresh after every rebuild (Safari caches `index.html` → old hashed bundle).
- **Bundle-size match ≠ behavior match.** A byte-identical bundle size after a strip
  did NOT prove the behavior was intact; only the device did.
- **When code analysis repeatedly predicts X and the device shows not-X, suspect
  you're running stale/wrong code** before chasing a logic bug. True repeatedly here.
- **Mac IP is DHCP and changed mid-session** (192.168.0.41 → .82). Argues for the
  "print backend LAN URL on `--lan`" feature (added) and not hard-coding the IP.
- **Web Inspector on iOS wouldn't connect** (cable/Develop-menu issues); the working
  fallback was an **on-screen debug overlay** rendered into the page (`debugOverlay.jsx`,
  `pushDebug`) — log array in module scope so it survives backgrounding. This was the
  tool that finally cracked both the vanishing-bubble and the keyboard root causes.
  Instrument → one repro → read the trace beats theorizing for anything iOS-async.
- **Uncommitted work doesn't sync to the repo / next session.** Commit findings as docs.
