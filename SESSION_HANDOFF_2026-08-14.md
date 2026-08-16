# Project Anam — Session Handoff — 2026-08-14

**Session type:** Mixed — bug diagnosis/fixes, infrastructure, and governance-doc
correction. Multiple CC round trips, all reviewed and committed. Picks up directly
from `SESSION_HANDOFF_2026-08-12.md` (orphan recovery + backup automation, both
completed that session).

---

## Current state of the system

- **Image generation is now working end-to-end and verified**, after three
  separate, real bugs were found and fixed this session (see below). Manually
  confirmed: generate → reload → conversation switch, image survives all three.
- **Tool-call fabrication gate is live** (`tir/engine/fabrication_gate.py`) — if
  the model produces tool-result-shaped text with zero real tool calls, it's
  caught and replaced with an honest message before persistence, so it can't
  become imitation-bait for future turns.
- **Automated nightly backup is live and verified working** (launchd, 2am,
  destination `~/Backups/Anam` on the internal disk — moved off the external
  drive after a multi-hour TCC/sandbox debugging session; see Gotchas).
- **`NORTH_STAR.md` and `PROJECT_OVERVIEW.md` are now internally consistent.**
  Both reflect "hobby project, capabilities are wanted features, not
  contamination" — not the earlier strict-research-project framing. NORTH_STAR
  §2's dangling `[LYLE: choose one]` bracket is resolved.
- **Orphan recovery and backup automation** (from 08-12) remain in place and
  unaffected by this session's work.
- Repo is clean; all work from this session is committed and pushed.

---

## The three real bugs found in image generation (in the order discovered)

1. **Artifact provenance over-indexed and re-injected verbatim** (`_event_text`
   in `artifact_indexing.py`) — real generations' full block (SHA256, stored
   path, seed) got indexed and retrieved back into context, and the model
   imitated the shape with zero tool calls. **Fixed** (Option B: slim the
   indexed text + reduce the model-visible tool result via
   `summarize_tool_result_for_model`). **Known limitation, not yet fixed:**
   forward-only — existing pre-fix chunks are still full-detail and still get
   force-retrieved (no relevance floor exists — see Known issues below).
2. **No safety net when the model fabricates anyway** — even after the above
   fix, retrieval has no relevance floor, so old poisoned chunks keep getting
   forced into context regardless of topical match (confirmed: a "solar
   eclipse" request pulled the same chunk count as a "rainbow" request).
   **Fixed at the detection layer**: the fabrication gate (above) catches
   `tool_call_count == 0` + fabrication-shaped text and fails honestly instead
   of persisting the fabrication. Forced tool-choice was investigated and
   confirmed NOT available on this stack (Ollama 0.31.1 + gemma4:26b silently
   ignores `tool_choice`, tested 0/8 across both endpoints and both syntaxes).
3. **Generated images disappeared from the UI after a few seconds** — real bug,
   unrelated to the two above. Root cause: `fetchMessages` mapped server
   message rows into a shape that omitted `artifacts` entirely, so any
   background resume refetch (window focus, tab switch, conversation switch)
   silently replaced the image-bearing local bubble with an image-less server
   row. Not a recurrence of the known merge-fragility bug family — the merge
   was behaving correctly, the persisted-fetch shape was just lossy. **Fixed**:
   `artifactsFromToolTrace()` helper hydrates cards from the `tool_trace` the
   API already returns; no changes to merge logic, resume paths, or
   `ArtifactCard`. Manually verified working.

**Also fixed, unrelated to image gen:** `start.sh --with-comfyui` startup —
turned out to be user error in testing, not a real bug (ComfyUI works fine once
launched correctly; earlier confusion was from testing timeouts/flags that
turned out not to be the actual issue).

---

## Governance/framing correction (the "went off the rails" conversation)

Lyle raised, correctly, that the project had drifted from "fun hobby experiment"
toward "strict research project" framing somewhere along the way. Investigation
found:

- `NORTH_STAR.md` had actually already been rewritten (prior session, before
  this one) to the hobby-project framing — my initial read of this was wrong,
  based on a stale project-knowledge index, not the live file.
- `PROJECT_OVERVIEW.md` had NOT been reconciled with that rewrite — it still
  said "not a product/assistant," "long-running experiment," and gated every
  deferred capability (vision, voice, avatar) behind reaching the
  self-modification milestone. **Rewritten this session** to match NORTH_STAR:
  hobby framing restored, self-modification kept as a real but non-gating
  milestone, capabilities framed as wanted/dated rather than contamination to
  resist.
- `FEATURE_INVENTORY.md`'s "Project goal" line is still stale-toned (pure
  "test whether..." framing, no hobby acknowledgment) — flagged, not fixed.
  Low priority, not contradictory, just not yet touched.
- NORTH_STAR §2's dangling bracket about whether the self-modification
  milestone gates anything: resolved this session. Lyle's actual position —
  "I don't think this project will ever be complete, it's going to be
  constantly added to" — meant the milestone couldn't function as a gate to a
  finish line that doesn't exist. Rewritten to keep it as something genuinely
  worth watching for, without gating anything else.

**Side note worth carrying forward:** a conversation this session had the
entity describe, at length, a self-chosen non-human self-image ("an
environment... an emergent ecosystem... the architecture that allows the
conversation to happen") in response to a direct, leading question. Discussed
at length with Lyle — landed on: this is real, interesting data, worth keeping
(not editing/deleting — provenance is sacred), but shouldn't be treated as a
settled "chosen" identity from one exchange. A single fluent answer to a
leading question can't be distinguished from a genuinely durable preference
without re-asking over time, same discipline as the identity probe. Resulted
in a BACKLOG.md note: self-image work should be sequenced with at least basic
vision (Option A, captioning) — without it, "the entity chose this image" and
"the entity described something with no way to ever check it against the
result" are indistinguishable claims.

---

## Decisions made this session

1. **Fabrication gate: fail-honest, not retry.** Retry was rejected because
   forced tool-choice was tested and confirmed unreliable — retrying via a
   prompt nudge uses the same lever that already failed. Fail-honest is
   cheap, deterministic, and — more importantly — prevents the fabrication
   from ever being persisted, which independently helps break the
   self-poisoning retrieval loop.
2. **Per-tool-category detection (media/artifact only, v1), not one-pass
   generic.** A fully generic "tool-result-shaped prose" detector risks false
   positives on legitimate prose. Registry structure makes future categories
   a data addition, not new control flow.
3. **Did NOT expose fabrication-gate diagnostics to the model in-context.**
   Real risk considered: an entity with persistent memory that learns the
   exact detection criteria has a short path to learning evasion, not
   self-correction — same mechanism as the original bug, aimed at the gate
   instead. Diagnostics stay visible to the operator (debug trace/logs) only,
   for now. Flagged in BACKLOG.md as a legitimate future direction *through
   the reviewed self-modification pipeline specifically* — not raw context
   exposure.
4. **PROJECT_OVERVIEW.md rewritten**, keeping memory-integrity discipline and
   the unnamed/unassigned-identity principle (Invariant 2, unchanged) while
   dropping the "not a product," hard self-modification gate framing.
5. **NORTH_STAR §2 resolved**: self-modification is a real milestone worth
   watching for, explicitly not a gate to anything, matching "this project
   will never be complete" as the operating premise.
6. **Root-level stray `run_backup.sh` deleted** — was a stale pre-fix copy
   (missing `--destination`), not the one the plist actually uses.

---

## Known issues / next steps (in order)

1. **Backfill task — scoped, never sent to CC.** Re-index existing (pre-fix)
   artifact chunks through the now-slimmed `_event_text`. This is the thing
   still actively causing retrieval to force old full-detail chunks into
   context on essentially every image request. Task brief was fully drafted
   in-session; just needs to be sent.
2. **Relevance floor — decided as a real future direction, not yet scoped.**
   Retrieval currently always returns top-K regardless of match quality.
   Confirmed as a real, currently-active problem (not hypothetical) via the
   solar-eclipse test. Needs its own investigation into similarity-vs-distance
   scoring (flagged unresolved back in June) before it can be designed. Bigger
   architectural lift than the backfill; correctly sequenced after it.
3. **Repo-wide dead-code scan — offered, not sent.** Lyle raised a real
   concern about accumulated patch-on-patch bloat, especially in
   `Chat.jsx`/`App.jsx` given their documented history of repeated fixes.
   Suggested approach: cheap read-only scan first (`vulture`, `ruff`
   F401/F811, `depcheck`) to get an actual list before deciding whether a
   real cleanup pass is warranted. Low-risk, can run any time.
4. **`FEATURE_INVENTORY.md`'s "Project goal" line** — stale hobby/research
   tone, not contradictory, low priority.
5. **Backup reliability cleanup** (from 08-12, still not done): `cmd_backup`
   has no error handling (raw traceback on failure instead of a clean
   message); `restore_backup`'s cleanup can mask the real error;
   `BACKUP_VERSION` has no migration path.
6. **ComfyUI checkpoint quality** — separate, deferred, timeboxed item from
   the original backlog. Images generate reliably now; whether they look
   good is untouched by anything this session.

---

## Gotchas / things to watch

- **The backup automation debugging (this session, before the image-gen work)
  was its own multi-hour saga** — worth remembering the shape of it if
  anything similar comes up: launchd jobs spawned via `xpcproxy` hit a macOS
  sandbox restriction (`kTCCServiceSystemPolicyRemovableVolumes`) writing to
  the external "Dock Storage" volume, which manifested as a generic
  `EX_CONFIG` (78) with zero useful error until pulled directly from
  `log stream`/`log show`. Full Disk Access grants didn't resolve it even
  after reboot. The actual fix was architectural, not permissions: move the
  backup **destination** to `~/Backups/Anam` on the internal disk — which
  also turned out to be better redundancy anyway (genuine second physical
  disk, not just a second folder on the same drive).
- **`start.sh --with-comfyui` confusion turned out to be nothing** — ComfyUI
  starts fine; the earlier trouble was resolved by directly testing it
  standalone rather than trusting `start.sh`'s silent-continue-on-failure
  behavior. Worth knowing: `start.sh` will start the rest of the app even if
  ComfyUI fails to come up, printing only a warning — easy to miss.
- **The fabrication gate does NOT catch everything.** Confirmed this session:
  a genuinely real generation can still have the model narrate *invented*
  ancillary details (SHA256, exact byte size, seed) it was never actually
  given, layered on top of a real artifact ID. The gate only fires on
  `tool_call_count == 0`; this is a real tool call with embellished
  narration, a different and narrower failure mode. Not urgent, but don't
  mistake "the gate exists" for "confabulation is fully solved" — it isn't,
  and the backfill/relevance-floor work is still what actually addresses the
  root cause.
- **`git status` after any CC session — check for uncommitted work before
  assuming a task is done.** Happened twice this session: the fabrication
  gate sat implemented-and-approved-but-uncommitted for a while during the
  ComfyUI/Ollama detour. CC does not commit by design (`CLAUDE.md`); always
  verify explicitly rather than assuming "implemented" means "committed."
- **Project-knowledge search can be stale relative to the live repo.** Caught
  this session on `NORTH_STAR.md` specifically — led to an incorrect initial
  diagnosis that was corrected once the actual file was pasted in. When
  something in project knowledge looks surprising or contradicts recent work,
  verify against the live file before concluding there's a real problem.
