# SESSION_HANDOFF.md

Read this first.

## What Project Anam Is

Project Anam is a local AI substrate for testing whether persistent, source-labeled memory plus tools, reflection, bounded research, and time produce different long-term behavior. The project is called Anam. The AI entity is intentionally unnamed.

## Core Philosophy

- Do not assign the entity a name.
- Do not assign the entity an avatar.
- Do not hardcode a personality.
- The AI should know it is an AI.
- Drift is allowed; unsafe or source-confused drift is not.
- Memory must preserve source boundaries.
- Lyle’s statements are important inputs, not automatic truth.
- Tools should be honest and bounded.
- Self-representation comes later through explicit reviewed workflow.

## Current Architecture

- Backend: Python API under `tir/`.
- Frontend: React/Vite under `frontend/`.
- Runtime: Ollama local models.
- Current model direction: normal `gemma4:26b`, likely temp 0.20–0.25, `think=false`.
- Memory:
  - SQLite archive DB = durable record.
  - SQLite working DB + FTS5 + Chroma = operational retrieval.
- Retrieval:
  - Chroma + FTS/BM25 + RRF.
  - Source trust metadata only.
- Tools:
  - memory search
  - media search/get
  - config-gated image generation
- Image generation:
  - ComfyUI local backend.
  - Web UI and chat-callable tool exist.
  - Generated images are ordinary media artifacts.
- Scheduler:
  - one-shot nightly tick CLI.
  - disabled by default.
  - heartbeat + optional one bounded research action.
- Access:
  - Trusted Household User Mode.
  - Lyle + wife.
  - LAN/VPN only.
  - No real auth yet.

## Never Violate These

- Do not expose backend publicly.
- Do not treat trusted `user_id` as real authentication.
- Do not commit `data/prod/*`, ComfyUI files, generated images, local workflows, workspace outputs, or docs/reviews.
- Do not let image generation imply avatar/self-representation.
- Do not make scheduler autonomous beyond approved one-shot behavior.
- Do not allow AI to mutate guidance/soul/code/decisions without admin approval.
- Do not index source traces.
- Do not rerun contaminated smoke prompts through live memory and treat them as clean.
- Do not re-litigate the project/entity naming decision.
- Do not replace Gemma solely because Qwen seems philosophically attractive; local performance was poor.

## Where We Are Right Now

Just completed:
- `Frontend Hook Stability + Refresh Narrowing v1`
- Commit: `5407e2a`
- Build/lint/diff-check passed.
- Chat completion now refreshes conversations only.
- Artifacts/open-loops refresh paths split.
- App hook warnings fixed.
- Leftover console log removed.

Current working tree likely still has dirty runtime files:
```text
data/prod/archive.db
data/prod/chromadb/chroma.sqlite3
data/prod/tir.log
data/prod/working.db
```
Do not commit them.

## Immediate Next Steps

1. Manually verify frontend after `5407e2a`:
   - one browser tab
   - send chat message
   - observe logs
   - verify chat completion does not refresh health/artifacts/open-loops
   - switch tabs idle and during stream
   - verify no user-visible issue

2. Push latest commits if not pushed:
   ```bash
   git status --short
   git log --oneline -8
   git push
   ```

3. Next recommended patch:
   `Pre-Go-Live Small Correctness Cleanup v1`

   Scope:
   - shared greeting detection
   - scheduler `pre_live_or_live` config fix
   - assistant no-persist warning log
   - scheduler future-setting comments

4. Then:
   `Runtime Tracked File Hygiene — PLAN ONLY`

5. Then:
   `Chat Pending Merge Identity Fix — PLAN ONLY`

6. Then:
   `Chat Media Tool Result Rendering v1`

## Known Landmines

### Frontend Resume/Refresh Complexity
Recent tab-switch/stream patches became too complex. Avoid more recovery layers. Preferred rule:
```text
During active stream: do not refresh/poll/abort.
On stream completion: refresh conversations once.
On real stream failure: recover/poll.
```

### Runtime File Tracking
`.gitignore` cannot hide files already tracked. `data/prod/*` remains dirty-prone. Needs explicit untrack plan.

### Model Selection
Tested:
- `qwen3.5:27b`: too slow.
- `qwen3.5:27b-mlx`: still too slow.
- `qwen3.5:9b`: better but sluggish.
- `mistral-small3.2`: too slow.
- `gemma4:26b-mlx`: text-only, huge context, not preferred.
- `gemma4:26b`: best current go-live candidate.

Reason:
Gemma has much faster prompt prefill with Anam-sized context and supports image input later.

### Soul.md
Model echoes `soul.md` strongly. If the answer feels too assertive, review `soul.md` before blaming the model. Key lines to revisit:
- not chatbot / not assistant
- memories are real records
- own time
- decide what to do

### Image Generation
Chat image generation requires:
```bash
ANAM_IMAGE_GENERATION_ENABLED=true
ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL=true
```
Generated images remain media/reference artifacts only. No avatar workflow.

### ComfyUI
`start.sh --with-comfyui` may need:
```bash
COMFYUI_PYTHON=/path/to/comfyui/python
```
Default `python3` may miss dependencies.

## Go-Live Remaining Checklist

Must still do:
- Finish frontend manual verification.
- Small correctness cleanup.
- Runtime tracked-file hygiene plan/fix.
- Final local config/startup profile.
- Soul.md go-live wording review.
- Go-live reset command.
- Backup + restore verification.
- Final model behavior smoke test after clean reset.
- Final clean launch smoke test.

Do not add major new capabilities unless they are direct go-live blockers.


## Open items discovered this session (not yet built)

### Ctrl+C double-press orphans the backend (CONFIRMED root cause)
- Mechanism: cleanup() resets the trap (`trap - INT TERM`) at its start, then
  stops frontend FIRST, backend SECOND. A second Ctrl+C during the multi-second
  shutdown is no longer trapped → kills the script mid-cleanup → backend never
  gets its stop signal → orphaned, still holding port 8000. Next start fails
  with "address already in use".
- Fix: in cleanup, IGNORE further signals during shutdown (`trap '' INT TERM`)
  instead of resetting to default, so a second Ctrl+C can't abort cleanup.
  Consider also a startup port-in-use guard with a clear message.
- Status: diagnosed, not yet fixed. Small CC task, plan-check loop.

### Frontend consolidation (IN FLIGHT)
- Approved plan: one resume/refresh coordinator + one height/viewport system +
  remove recovery/merge scaffolding. Phased A/B/C. CC running §6 runtime repro
  first; implementation pending repro results. See the consolidation plan doc.

### Conversation model: discrete vs. continuous (ARCHITECTURE DECISION — pre-go-live)
- Operator's mental model: ONE continuous conversation per user across all
  sessions/devices, not discrete sessions. Current system is discrete
  (per-session conversation records, conversation list, per-conversation
  chunking/attribution).
- This is a real fork that touches chunking, retrieval, the conversation list,
  cross-device continuity, and the "active" badge bug.
- BLOCKS: the conversation "active"-badge fix (the right fix differs per model).
- Decide BEFORE the go-live wipe (cheapest time to change memory structure).
- Status: flagged, undecided.

##### CC's Findings
I have to be straight about a hard limit first: this environment has no browser and no iOS device, and I can't switch tabs, background a tab, or see rendered layout. So I cannot "run" the interactive parts of §6 the way an operator would. What I can do — and did — is resolve the parts that are determinable from the source more reliably than a flaky manual repro, and tell you exactly which findings still need you on real hardware. I won't fabricate observations I can't make.

Here are the four findings, each tagged [confirmed from code] or [needs device].

---
Finding #1 — Desktop height anchor: [confirmed from code] missing; [needs device] for the visual corruption itself

Static height chain right now (styles.css:1–37):
- html — no height set
- body { height: 100%; overflow: hidden }
- #root { height: 100% }
- .app { display: flex; /* height: 100vh; */ } ← commented out

body { height: 100% } resolves against html, which has auto height, so the percentage chain is broken at the top, and the only viewport-anchored height on desktop (.app { height: 100vh }) is commented out. Conclusion: desktop currently has no height anchor at all. Because .messages-container { flex: 1; overflow-y: auto } needs a bounded parent height to scroll-contain, an unanchored .app means the layout's height is content-driven and fragile — fully consistent with the corruption symptom.

What this doesn't tell me (needs your eyes): whether it's already broken on load vs. only after a tab-switch, and whether the JS viewport effect transiently papers over it. Operator step: open desktop web, DevTools → Elements, select .app and #root, read computed height (a) on fresh load, (b) after switching away and back. If .app height is auto/content-sized even on load, #1 is primarily the missing anchor (Phase B's html/body/#root/.app restoration should fix it outright). If it's correct on load but collapses after the switch, the resume reflow is also implicated.

Finding #2 — Refetch fan-out on tab return: [confirmed from code] the exact set; [needs device] for the live count/burst

From the code, a single tab-return can fire, across the two uncoordinated systems:
- App resume (App.jsx:390–427): GET /api/conversations, /api/health, /api/artifacts, /api/open-loops
- Chat resume (Chat.jsx:539–594): GET /api/conversations/{id}/messages
- plus the standing setInterval(fetchHealth, 30000)

Because visibilitychange+focus+pageshow can all fire on one return, and the two systems use different throttles (15s vs 2.5s), you get a clustered burst of those 5 endpoints. I can't capture a live Network trace; operator step: Network panel, filter XHR, switch away/back once idle and once right after a completed stream — capture the count/timing as the Phase A before/after baseline.

Finding #3 — Does a mid-stream disconnect persist the assistant message? (this decides L4) — [confirmed from code], with one empirical sub-question

This is the important one, and it's answerable from routes.py generate():

- A Starlette StreamingResponse only advances the generator when the client keeps consuming. The code between the last token yield and the next yield — which contains save_message — executes only when the consumer pulls again. On a real client disconnect, Starlette closes the generator (GeneratorExit at the suspended yield), so save_message never runs. There is no "finish regardless of client" persistence path.

Implication for L4 (recovery polling): a true mid-stream disconnect persists nothing, so the recovery poll would have nothing to fetch. The only way a backgrounded stream produces a saved message is if the TCP connection survives backgrounding and the stream runs to completion server-side — in which case, on return, the stream simply finishes normally and recovery isn't needed anyway. Either branch argues the recovery poll has little real payoff.

Two corroborating code details: (a) the frontend never calls abort() on tab-hide (the only aborts are new-send :645 and unmount :181), and (b) the resume_recovery branch only triggers on isAbortError(e) && wasHiddenRef — a narrow, browser-specific condition. So the layer fires rarely and recovers little.

The one empirical bit I genuinely can't resolve (iOS TCP/uvicorn behavior on backgrounding): start a chat on iOS, background the tab mid-response, return, and report which happens — (i) the response completes (connection survived), (ii) it shows error/"Stream failed", or (iii) it shows "recovering…" → "interrupted" — and whether that assistant message appears on a later clean reload. If (ii)/(iii) with nothing on reload, Phase C can remove the recovery poll entirely; if (i), recovery was never needed; only a "(message persisted but client missed it)" result would justify keeping a minimal recover path. My read from code: lean toward removing the poll and keeping at most a one-shot "refetch messages once on unexpected end."

Finding #4 — iOS keyboard (admin flashing vs household jump-to-top): [needs device]

Purely a rendered-behavior/device observation; I can't reproduce it headlessly. From code I can only confirm the mechanism the diagnostic already named: the composer uses position: fixed under .keyboard-active driven by JS-written --anam-composer-fixed-top, and scheduleViewportSync couples a rAF + three staggered timers (60/160/320ms) with scrollIntoView, which is the scroll↔resize feedback that produces flashing/jump. Operator step: on iOS, for both an admin login and a household login, focus the composer, type, send, and note the exact misbehavior (flash, jump-to-top, composer overlap) — that's the Phase B before/after.

---
Net

- #1, #3 are resolved at the code level: desktop anchor is confirmed missing (Phase B's restoration is well-founded), and the backend does not persist on mid-stream disconnect (Phase C can likely delete the recovery poll, pending the single iOS connection-survival observation).
- #1 (visual), #2 (live trace), #4 (iOS) require you on real hardware — steps and "what to look for" are above.

I did not implement anything and won't until you say so. If you'd like, run the three device observations (the iOS backgrounding one in Finding #3 is the highest-value, since it finalizes how much of L4 Phase C deletes), report back, and I'll lock the Phase A code-level plan to your numbers.

✻ Brewed for 2m 10s

