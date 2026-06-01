# FEATURE_INVENTORY.md

Authoritative feature/capability view of Project Anam, split into what is built,
what should be done before go-live, and what comes after.

**How this relates to the other docs:**
- `GO_LIVE_CHECKLIST.md` = the operational *steps and ritual* to launch. ("How.")
- This file = the *capability* view: what exists, what to build pre/post launch. ("What.")
- `ROADMAP.md` = the long-term vision detail. This file points at it, doesn't duplicate it.
- `FINDINGS.md` = open defects. Referenced, not copied.

When this file and a roadmap disagree about what is *built*, trust code, then this
file. Several roadmap "[x]" marks were found wrong this session.

---

## Security posture (settled by threat model — not open work)

Threat model: home LAN only, two trusted users (Lyle + wife), wife on web/iPhone
UI only. Given that, these are deliberate and require no further hardening:

- No real login/session auth — fine for two trusted household users.
- CORS proxy-only (localhost origins; iPhone via Vite proxy) — fine.
- `ANAM_API_SECRET` shared secret — **optional**, low priority. Worth setting only
  as insurance against a compromised device already on the LAN; not required.

The model has ONE hard invariant, and it is the real security blocker:

- **Never expose the backend or frontend beyond LAN/VPN**, and never leak the data
  sideways (public repo, offsite backup left readable). Every shortcut above is
  safe *only* while this holds. (The public-repo-with-DBs issue caught earlier was
  this invariant failing through a non-network channel.)

Verify once before launch: the wife's web/iPhone UI exposes **no destructive admin
path** (reset/restore/config are CLI `tir.admin` only — confirm the UI has nothing
equivalent).

---

# Part 1 — Built & working now

Marked `[verified]` where confirmed in code this session; otherwise from project
docs and should be spot-checked before trusting for launch.

## Core platform
- Local FastAPI backend (`tir/` package)
- React/Vite web UI
- Ollama runtime — `gemma4:26b` chat, `nomic-embed-text` embeddings
- Layered config: `defaults.toml` → `local.toml` → env overrides `[verified]`
- `start.sh` local + `--lan` + optional `--with-comfyui`
- Process-tree cleanup on Ctrl+C — works in the normal single-Ctrl+C path;
  a double-Ctrl+C-during-shutdown race exists (can orphan a process). Not yet
  hardened.
- `num_ctx` pinned to 32768 `[verified, this session]` — live `ollama ps`
  confirmation still owed.

## Memory / continuity
- SQLite archive DB (durable) + working DB (operational)
- ChromaDB vector store; FTS5/BM25; hybrid retrieval via RRF
- Source-trust weighting (firsthand/secondhand/thirdhand)
- Conversation chunking + checkpointing
- Embedding-dimension guard (768)
- Full conversation history loaded per request (unbounded — see pre-go-live)

## Source / provenance
- Source-labeled memory (which user said what)
- Source-trace sidecars; unique paths
- Source traces blocked from indexing; governance files blocked from artifact
  ingestion `[verified]`

## Identity / governance
- `soul.md` identity seed + integrity floor (no fabrication, tool-failure honesty,
  no silent mutation, AI self-awareness)
- Operational guidance loaded; behavioral-guidance proposal/review path —
  advisory only, dormant pre-launch, operator-approval required `[verified dormant]`
- Entity unnamed, no avatar, no assigned personality; drift allowed

## Users / household
- Trusted Household User Mode (Lyle admin + wife); active-user display/switch
- Per-user source attribution
- LAN/VPN only; optional shared secret `[verified posture]`

## Chat / agent loop
- Streaming chat endpoint; stable message IDs; optimistic user messages
- Agent loop with tool dispatch; tool-call/result + debug event stream
- Pending assistant bubble; tab-switch stream preservation; mobile resume;
  localStorage persistence; recovery polling on real disruption
- No-persist warning log on empty agent result `[verified, this session]`

## Tools / skills
- Skill registry; `memory_search`; `media_search` / `media_get`;
  config-gated `image_generate`

## Artifacts / media
- Artifact ingestion + registry; provenance metadata; revision/source links
- Uploaded image + screenshot support; safe image-preview endpoint
- Raw image bytes excluded from Chroma/FTS (metadata-only) `[verified intent]`
- `intended_use` limited to general/reference; avatar rejected `[verified]`

## Image generation
- ComfyUI local backend; CLI + web UI + chat-callable paths
- Provenance metadata (prompt/seed/dimensions/model)
- **Currently enabled by default in tracked config** (`enabled=true`,
  `allow_agent_tool=true`). NOTE: this contradicts the docs' "disabled by
  default" claim — it is a pre-go-live decision, not a settled state.

## Research / open loops
- Manual bounded research planner + runtime; research notes; registration/indexing;
  orphan recovery; open-loop run-next; low-signal filtering
- Moltbook source preview/collection (read-only); bounded-research integration

## Scheduler
- One-shot nightly-tick CLI (no daemon), disabled by default; dry-run + write
- Heartbeat + optional one bounded research action; audit in `overnight_runs`
- `go_live` pre_live/live audit flag (default false) `[verified, this session]`

## Ops / diagnostics
- Backup / restore / backup-restore-verify with atomic-restore hardening
- Status/capabilities endpoints; `tir.log`; structured `chat_debug.jsonl` trace

## Web UI
- Chat (primary), history, registry/media, status, debug panels
- Mobile nav; iPhone LAN access; keyboard/composer fixes; image-gen + upload UI

---

# Part 2 — Before go-live

Because there is no deadline, the bias is to fix silent-failure and data-integrity
modes *before* launch rather than patch them on top of irreplaceable memory.

## Hard blockers (cannot launch safely without)
- [ ] **Go-Live Reset Command v1** — dry-run + destructive mode, typed
      confirmation, mandatory backup + verify first, wipe contaminated memory,
      reset Chroma/FTS, clear workspace outputs, preserve users/schema/code/docs/
      governance, audit file, verify-clean mode, tests. *The defining act of
      go-live and the largest remaining build.*
- [ ] **Off-drive recurring backup of runtime memory** (DBs/Chroma/workspace).
      Code/governance is in git; memory is not, and lives on one external drive.
      Must be in place AT launch — first night of real memory is already
      irreplaceable.
- [ ] **Backup/restore verification by real wipe-and-restore** — before you trust
      the reset command's mandatory-backup step.
- [ ] **Config decisions locked in tracked config:**
  - [ ] Chat temperature (0.20/0.25) in tracked config, not `local.toml`
  - [ ] Image-generation default decided deliberately (currently on)
  - [ ] `scheduler.go_live = true` for launch

## Worth doing before launch (no deadline → prevent silent corruption now)
- [ ] Truncation detection — log when assembled prompt exceeds the context window
      (silent context loss otherwise; `soul.md` is at the front and gets dropped
      first).
- [ ] Conversation-history windowing/summarization — the actual fix for the
      unbounded-history cause behind truncation. Bigger build; at minimum land
      truncation *detection* before launch and windowing soon after.
- [ ] Log/debug-trace size cap (`tir.log`, `chat_debug.jsonl`) — disk-full
      protection for an unattended months-long run.
- [ ] Startup preflight — fail loud if Ollama is unreachable or required models
      aren't pulled, instead of erroring on first chat.
- [ ] `soul.md` go-live wording review — shapes day-zero behavior. (Roadmaps
      disagree on whether done; decide and record.)
- [ ] Chat Pending Merge Identity Fix — repeated identical messages can confuse
      optimistic-merge; cheap, prevents UI confusion.

## Verifications (operator-run, not build)
- [ ] `num_ctx` honored live (`ollama ps` ≈ 32K, no CPU spill)
- [ ] Frontend manual check (no broad refresh; tab-switch idle + mid-stream)
- [ ] Wife user works on web + iPhone; UI exposes no destructive admin path
- [ ] Deferred/dormant features actually off in resolved config (image agent tool
      decided, scheduler automation off, guidance dormant, avatar absent,
      autonomous web off)

## Launch ritual
See `GO_LIVE_CHECKLIST.md` for the strict-order ritual (lock config → final backup
→ retain as rollback → verify restore → tag baseline → reset → set go_live →
clean smoke test incl. two-user attribution).

---

# Part 3 — Post-go-live

## Near-term polish (see `FINDINGS.md`)
- Chat media tool result rendering (inline image preview)
- Frontend test harness (merge/resume/localStorage)
- Media search beyond recent slice; image preview magic-byte validation;
  checkpoint embedding off the response hot path; artifact orphan cleanup
- Scheduler launchd/cron automation; scheduler/admin/model-selector UIs

## Capability arc (see `ROADMAP.md` for detail)
- Event/trace foundation; identity events; behavioral observations; working
  theories + open questions; context-assembler upgrade
- Nightly journal / reflection cycle
- Interpretation-trace + temporal-awareness runtimes
- iMessage (send-only → approval → conversational)
- Moltbook (read-only → draft → controlled posting)
- Expanded autonomous research with budgets; web search/fetch in chat
- Voice (Pi edge node), then sight/vision
- Self-modification v1; diagnostics/eval harness
- Avatar / self-representation; entity self-naming — only after continuity
  develops, never assigned pre-launch
- Multi-model routing; long-context specialist model
- Real auth — only if exposure model ever changes (not needed for LAN-only)

---

## Standing caveat
This session found three false "Completed" claims (context size, Ctrl+C, image-gen
default) because governance rules weren't loading until `CLAUDE.md` was added.
Treat code as ground truth over any doc checkbox for anything safety- or
data-integrity-relevant. Keep this file updated as work ships; do not spawn another
roadmap to replace it.
