# FEATURE_INVENTORY.md

Authoritative feature/capability view of Project Anam: what is built, what to do
before go-live, and what comes after.

**Relationship to other docs:**
- `GO_LIVE_CHECKLIST.md` = operational launch *steps and ritual* ("how").
- This file = *capability* view: what exists, what to build pre/post ("what").
- `ROADMAP.md` = long-term vision detail (pointed to, not duplicated).
- `FINDINGS.md` = open defects.

When this file and a roadmap disagree about what is *built*, trust code, then this
file. Several roadmap "[x]" marks were found wrong this session.

---

## Project goal (the lens for every decision)

Test whether persistent, source-labeled memory + tools + reflection + bounded
research + time produces meaningfully different long-term behavior in an AI entity.

Two consequences drive every pre/post decision below:
1. **The accumulated memory is the irreplaceable asset.** It forms slowly and
   cannot be regenerated. Protect it; keep it clean.
2. **Anything that writes bad/mislabeled/unsupervised data into live memory is
   permanent pollution.** Memory-*formation* mechanisms get scrutiny;
   memory-*reading* features mostly don't.

---

## Security posture (settled by threat model — not open work)

Home LAN only, two trusted users (Lyle + wife), wife on web/iPhone UI only.
Therefore, deliberate and requiring no further hardening:
- No real login/session auth (fine for two trusted household users).
- CORS proxy-only.
- `ANAM_API_SECRET` shared secret — optional, low priority.

ONE hard invariant (the real security blocker):
- **Never expose backend/frontend beyond LAN/VPN; never leak data sideways
  (public repo, readable offsite backup).** Every shortcut is safe only while this
  holds. (The public-repo-with-DBs issue caught this session was this invariant
  failing through a non-network channel.)

Verify once: the wife's web/iPhone UI exposes no destructive admin path
(reset/restore/config are CLI `tir.admin` only — confirm UI has nothing equivalent).

---

# Part 1 — Built & working now

`[verified]` = confirmed in code this session; otherwise from docs, spot-check
before trusting for launch.

## Core platform
- Local FastAPI backend (`tir/` package — legacy name, do NOT rename casually)
- React/Vite web UI
- Ollama runtime — `gemma4:26b` chat, `nomic-embed-text` embeddings
- Layered config: `defaults.toml` → `local.toml` → env `[verified]`
- `start.sh` local + `--lan` + optional `--with-comfyui`
- Ctrl+C process cleanup — works in normal single-press path; double-press-during-
  shutdown race can orphan a process (not yet hardened)
- `num_ctx` pinned to 32768 `[verified]` — live `ollama ps` confirmation owed

## Memory / continuity
- SQLite archive DB (durable) + working DB (operational/rebuildable)
- ChromaDB vectors; FTS5/BM25; hybrid retrieval via RRF
- **Conversation memory = RAW timestamped, speaker-labeled transcripts** `[verified]`
  — not model summaries. Faithful by design; pollution risk limited to wrong
  attribution or persisted garbage turns.
- Source-trust weighting; chunking + checkpointing; embedding-dimension guard (768)
- Full conversation history loaded per request (unbounded — see pre-go-live)

## Source / provenance
- Source-labeled memory; source-trace sidecars
- Source traces blocked from indexing; governance files blocked from ingestion `[verified]`

## Identity / governance
- `soul.md` seed + integrity floor (no fabrication, tool-failure honesty, no silent
  mutation, AI self-awareness)
- Behavioral-guidance proposal/review — advisory only, dormant pre-launch,
  operator-approval required `[verified dormant]`
- Entity unnamed, no avatar, no assigned personality

## Users / household
- Trusted Household User Mode (Lyle admin + wife); active-user display/switch
- Per-user source attribution
- NOTE: `admin.py` has `set-password`/`add-user`/`show-user` — more user-identity
  plumbing in the schema than docs implied; relevant to the attribution work below.

## Chat / agent loop
- Streaming chat; stable message IDs; agent loop with tool dispatch
- Tool-call/result + debug event stream; pending-bubble; mobile resume; localStorage
  persistence; recovery polling on real disruption
- No-persist warning log on empty agent result `[verified]`

## Tools / artifacts / media
- `memory_search`; `media_search`/`media_get`; config-gated `image_generate`
- Artifact ingestion + registry; provenance metadata
- Uploaded image + screenshot support; safe preview endpoint
- Raw image bytes excluded from Chroma/FTS (metadata-only)
- `intended_use` general/reference only; avatar rejected `[verified]`

## Image generation
- ComfyUI local backend (SD 1.5 test checkpoint — low quality); CLI + web UI +
  chat-callable paths
- **Currently enabled by default in tracked config** (`enabled=true`,
  `allow_agent_tool=true`) — a pre-go-live decision, see below

## Research / open loops / Moltbook
- Manual bounded research planner + runtime; notes; registration/indexing; orphan
  recovery; open-loop run-next; low-signal filtering
- **Moltbook source collection/preview = READ-ONLY, built.** Read already gives the
  entity AI-generated input. Posting is separate — see post-go-live.

## Scheduler
- One-shot nightly-tick CLI (no daemon), disabled by default; dry-run + write
- Heartbeat + optional one bounded research action; `overnight_runs` audit
- `go_live` pre_live/live audit flag (default false) `[verified]`

## Ops
- Backup / restore / backup-restore-verify with atomic-restore hardening
- `memory-audit` + `memory-repair` commands (repair scope unverified — see recoverability)
- Status/capabilities endpoints; `tir.log`; `chat_debug.jsonl` trace

---

# Part 2 — Before go-live

No deadline → bias toward fixing silent-failure and pollution modes *before* launch,
since they corrupt irreplaceable memory if discovered later.

## Hard blockers
- [ ] **Go-Live Reset Command v1** — dry-run + destructive mode, typed confirmation,
      mandatory backup + verify first, wipe contaminated memory, reset Chroma/FTS,
      clear workspace outputs, preserve users/schema/code/docs/governance, audit
      file, verify-clean, tests. *Largest remaining build; defines go-live.*
- [ ] **Automated off-drive backup of runtime memory** (DBs/Chroma/workspace). Code/
      governance is in git; memory is not, and sits on one external drive. Must be
      AUTOMATED (launchd) — a backup you must remember to run won't run the week
      you're away. First night of real memory is already irreplaceable.
- [ ] **Backup/restore verification by real wipe-and-restore** before trusting the
      reset command's mandatory backup.
- [ ] **Both users usable + attribution correct** — Lyle and wife on web/iPhone;
      per-device identity default; prominent always-visible "chatting as: X";
      VERIFY the selected user is actually written as the source label into
      `archive.db` (chunks are raw transcripts, so a wrong label is permanently
      wrong). Protects the core thesis.
- [ ] **Config decisions locked in tracked config:**
  - [ ] Chat temperature (0.20/0.25) in tracked config, not `local.toml`
  - [ ] Image generation: **agent tool OFF** at launch; manual/CLI path stays
        available (rationale below)
  - [ ] `scheduler.go_live = true` for launch

## Recoverability (verify; build only the gap)
- [ ] Confirm whether `memory-repair` can fully **rebuild Chroma + FTS from the
      durable archive**. If not, build that path. Architecture promises "rebuildable"
      operational memory; that must be real before launch (corruption or an
      embedding-model change otherwise = manual surgery / data loss).
- [ ] **Lock the embedding model** (`nomic-embed-text`) before the wipe — changing it
      later invalidates every vector and forces a full rebuild.

## Memory-formation quality (the real pollution surface)
- [ ] **Journal + research quality gate before enabling automation.** These are
      model-GENERATED and indexed permanently, and they're the unattended path. Before
      the nightly tick runs unwatched, confirm reflections aren't fabricated, research
      notes don't invent facts, and low-signal handling works ("nothing notable today"
      vs manufactured significance).
- [ ] **Pre-wipe inspection of existing memory** — before deleting the throwaway DB,
      read its journals/research notes/chunks and judge formation quality. Free QA of
      the whole pipeline against data you're deleting anyway.

## Worth doing before launch (no deadline → prevent silent corruption now)
- [ ] Truncation detection — log when assembled prompt exceeds the context window
      (silent loss otherwise; degraded turns also get persisted as permanent memory)
- [ ] Conversation-history windowing/summarization — the real fix for the unbounded-
      history cause; at minimum land detection pre-launch, windowing soon after
- [ ] Log/debug-trace size cap (disk-full protection for unattended months)
- [ ] Startup preflight — fail loud if Ollama unreachable or required models missing
- [ ] `soul.md` go-live wording review (shapes day-zero behavior; roadmaps disagree
      on whether done — decide and record)
- [ ] Chat Pending Merge Identity Fix (repeated-message merge confusion)

## Image generation — capability work, pre-wipe
- [ ] Improve checkpoint quality (SDXL fits ~tight on 32GB beside the LLM; Flux needs
      load-on-demand) and measure LLM+image coexistence — via the **manual/CLI path
      against the throwaway DB**, since experimentation generates junk artifacts.
- General non-avatar uses (concept art, wireframe/particle studies, UI imagery,
  variations) are legitimate and don't carry the avatar's constraints.
- **Agent-autonomous generation stays OFF at launch** regardless of quality —
  autonomous generation into live memory pollutes the dataset and is peripheral to
  the thesis. Manual capability yes; agent autonomy no.

## Verifications (operator-run)
- [ ] `num_ctx` honored live (`ollama ps` ≈ 32K, no CPU spill)
- [ ] Frontend manual check (no broad refresh; tab-switch idle + mid-stream)
- [ ] Wife user works web + iPhone; UI exposes no destructive admin path
- [ ] Deferred/dormant features off in resolved config (image agent tool off,
      scheduler automation as decided, guidance dormant, avatar absent, autonomous web off)

## Automation (required by the away-from-home goal)
- [ ] launchd scheduling for the **bounded nightly tick** (one bounded action/night;
      scope unchanged — automating the trigger, not expanding behavior; consistent
      with CONSTRAINTS if scope stays bounded). Gated on the journal/research quality
      gate above.
- [ ] launchd scheduling for **automated backup** (non-negotiable regardless of the
      research-automation decision).

---

# Part 3 — Post-go-live

## Early post-launch (deliberate, not day-one)
- **Moltbook interaction — user-initiated, draft-confirmed.** Read-only is already
  built. Posting is held OUT of go-live deliberately: introducing AI-social influence
  from day one destroys the human-only baseline needed to *observe* how that influence
  changes the entity. Introduce it as a dated, deliberate variable a few weeks in.
  Shape: entity drafts on user request, shows the draft, user confirms before send
  (gate on content, not just intent). On the staged path read → draft → controlled.
- Conversation-history windowing (if only detection landed pre-launch)

## Near-term polish (see `FINDINGS.md`)
- Chat media tool result rendering (inline image preview)
- Frontend test harness; media-search beyond recent slice; image magic-byte
  validation; checkpoint embedding off the hot path; artifact orphan cleanup
- Scheduler/admin/model-selector UIs

## Capability arc (see `ROADMAP.md`)
- Event/trace foundation; identity events; **behavioral observations; working
  theories** (NOTE: model-generated-into-memory writers — keep deferred; adding them
  pre-launch would *increase* pollution surface); context-assembler upgrade
- Interpretation-trace + temporal-awareness runtimes
- iMessage (send-only → approval → conversational)
- Voice (Pi edge node), then sight/vision; image understanding
- Self-modification v1; diagnostics/eval harness
- **Avatar / self-representation; entity self-naming** — only after continuity
  develops, via a reviewed entity-driven workflow; never assigned pre-launch; the
  current image tool deliberately rejects avatar use
- Multi-model routing; long-context specialist
- Real auth — only if the LAN-only exposure model ever changes

## Housekeeping (deliberately NOT doing)
- Renaming `tir/` → `anam/`: broad repo-wide import refactor, zero functional gain,
  flagged as a landmine in `AGENTS.md`. DB paths are under `data/prod/` (not under
  `tir/`), so it wouldn't endanger memory — but it's churn with breakage risk for a
  name neither user nor entity ever sees. If ever done: dedicated tested CC task,
  pre-wipe, never post-launch. Recommendation: leave it.

---

## Standing caveat
This session found three false "Completed" claims (context size, Ctrl+C, image-gen
default) because governance rules weren't loading until `CLAUDE.md` was added. Trust
code over any doc checkbox for safety/data-integrity-relevant items. Keep this file
current as work ships; do not spawn another roadmap to replace it.
