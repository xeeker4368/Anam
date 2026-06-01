# GO_LIVE_CHECKLIST.md

**This is the operational source of truth for launching Project Anam.**
The vision/feature arc lives in `ROADMAP.md`; open defects live in `FINDINGS.md`.
This file is *only* the conclusive list of what must happen to go live safely,
and what is deliberately deferred. When this file and a roadmap disagree about
go-live, this file wins.

Status legend: `[x]` done · `[~]` in progress · `[ ]` not started · **(BLOCKER)**
= must be true before launch · **(VERIFY)** = operator must check, not build.

---

## What "go-live" actually is

Go-live is a single milestone, not a vague state. At go-live:

1. The contaminated pre-live test memory is wiped (destructive reset).
2. From that point, accumulated memory is **real and irreplaceable** — the risk
   model flips from "disposable test data" to "the experiment itself."
3. `scheduler.go_live = true` is set so audit rows stop recording `pre_live`.
4. The launch config profile is locked and the launch commit is tagged as the
   30/60/90-day drift baseline.

Everything below is in service of reaching that milestone safely and being able
to recover if it goes wrong.

---

## Already shipped (this session)

- [x] Untrack `data/prod` + `workspace` runtime files from the (public) repo
- [x] Pin Ollama `num_ctx` to 32768 in config (commit: num_ctx pin)
- [x] `CLAUDE.md` importing `AGENTS.md` + `CODING_ASSISTANT_RULES.md` (rules now
      actually load for Claude Code — previously dormant)
- [x] Governance/session docs tracked in repo
- [x] Scheduler `go_live` pre_live/live audit flag added (default false)
- [x] Greeting helper deduplicated; no-persist warning log added; prompt
      inventory regenerated

---

## Remaining — Verifications (operator-run, cheap)

- [ ] **(VERIFY)** `num_ctx` honored live: start stack, send a chat, run
      `ollama ps`, confirm CONTEXT ≈ 32K and no CPU spill. *Config wiring is
      proven by tests; this proves Ollama actually honors it.*
- [ ] **(VERIFY)** Frontend manual check: single tab, send message, confirm chat
      completion does NOT trigger health/artifacts/open-loops refresh; tab-switch
      idle and mid-stream; image-gen UI still works.
- [ ] **(VERIFY)** Wife user exists and can use the UI, including iPhone over LAN.
- [ ] **(VERIFY)** Startup preflight: Ollama reachable and `gemma4:26b` +
      `nomic-embed-text` present before the app declares ready. *(If no preflight
      exists, see Build work — add one.)*
- [ ] **(VERIFY · BLOCKER)** Deferred/dormant features are actually OFF in the
      resolved launch config (not just in the docs):
  - agent image tool (`allow_agent_tool`) — off, or deliberately on by decision
  - scheduler automation (launchd/cron) — off
  - behavioral-guidance runtime loading — dormant
  - avatar/self-representation — absent
  - autonomous web research — off
  - *Motivation: image-gen was found defaulting ON in `defaults.toml` while docs
    said it required env flags. Verify the live config, not the documentation.*

---

## Remaining — Config & Decisions (Final Startup Profile)

- [ ] **(BLOCKER)** Pin chat temperature (0.20/0.25) in **tracked** config, not
      the gitignored `local.toml`. A clean checkout currently runs 0.35.
- [ ] **(BLOCKER)** Decide image-generation default: env-gated vs on-by-default,
      and set it deliberately in tracked config.
- [ ] **(BLOCKER)** `scheduler.go_live = true` set for launch (else the audit
      flag is a no-op forever).
- [ ] `ANAM_API_SECRET` set for launch.
- [ ] ComfyUI python path / Moltbook token / LAN mode captured in the launch
      profile.
- [ ] CORS stance decided (proxy-only documented, or configurable LAN origins).
- [ ] Soul.md go-live wording review. *NOTE: roadmaps disagree on whether this is
      done — one marks it complete, SESSION_HANDOFF lists it open. Decide and
      record the answer here; do not trust the conflicting `[x]`.*

---

## Remaining — Build Work

- [ ] **(BLOCKER · LONG POLE)** Go-Live Reset Command v1: dry-run + destructive
      mode, typed confirmation, mandatory backup + backup-restore-verify first,
      wipe contaminated runtime memory, reset Chroma/FTS, clear workspace outputs,
      preserve users/schema/code/docs/governance, audit file, verify-clean mode,
      tests. *Most of the remaining engineering. Everything in the launch ritual
      depends on this existing.*
- [ ] **(BLOCKER)** Off-drive recurring backup of runtime memory
      (`archive.db`, `working.db`, ChromaDB, workspace). *Code/governance is
      already protected by git; memory is NOT. It lives on one external drive
      that already proved a single point of failure. Minimum: scheduled or
      documented-cadence backup to a second location.*
- [ ] Truncation detection: log a warning when the assembled prompt exceeds the
      context window. *`num_ctx` is pinned but history is still loaded unbounded;
      eventually a long conversation will exceed 32K and Ollama silently drops the
      oldest content (including `soul.md` at the front). Make it visible.*
- [ ] Log/debug-trace size cap (`tir.log`, `chat_debug.jsonl`) — disk-full
      protection for an unattended months-long run on the memory drive.

---

## Launch Ritual (strict order — do not reorder)

1. [ ] Lock the final config/startup profile (all Config & Decisions above set).
2. [ ] Final backup of runtime memory.
3. [ ] **Retain that backup as the labeled ROLLBACK artifact** — separate from
       rotating backups, not to be overwritten. This is the only way back if
       launch fails.
4. [ ] Backup-restore verification passes (real wipe-and-restore into an isolated
       dir; confirm DBs/Chroma/workspace/governance readable; manifest hashes
       where present). *Do not trust the existing "complete" mark without running
       it.*
5. [ ] Tag the launch commit (drift baseline reference).
6. [ ] Run the Go-Live Reset Command (destructive wipe of contaminated memory).
7. [ ] Set `scheduler.go_live = true`; confirm launch config is the locked profile.
8. [ ] Final clean-launch smoke test on **fresh** post-reset memory:
   - core single-user behavior
   - **two-user source attribution** — Lyle vs. wife interleaved, confirm no
     attribution bleed (this is the core project thesis; test it)
   - memory write/retrieve round-trip works after reset
   - re-confirm deferred features still off (item from Verifications)
9. [ ] Save smoke-test transcripts as dev artifacts OUTSIDE live memory.

---

## Decide Deliberately (likely "out" — but on purpose, not by oversight)

- [ ] Monitoring / auto-restart. *Probably unnecessary for a 2-person appliance
      ("notice it's down, rerun start.sh"). Building uptime infra would be scope
      creep. Decide it's out.*
- [ ] "Entity misbehaves / memory looks corrupted" freeze-and-inspect runbook.
      *Half-page: if X, then disable scheduler / restore from backup / inspect.
      Cheap insurance for the one scenario the constitution explicitly cares
      about (unsafe drift).*

---

## Post-Go-Live Backlog (NOT blockers — detail lives elsewhere)

Near-term polish (see `FINDINGS.md` for specifics):
- Chat Pending Merge Identity Fix (repeated identical-message merge)
- Chat Media Tool Result Rendering (inline image preview in chat)
- Frontend test harness (merge/resume/localStorage)
- FINDINGS mediums: media-search beyond recent slice, image preview magic-byte
  check, checkpoint embedding off the response hot path, full-history windowing

Vision arc (see `ROADMAP.md`):
- Event/trace foundation, identity events, behavioral observations, working
  theories, context-assembler upgrade, nightly journal
- iMessage (send-only → approval → conversational)
- Moltbook (read-only → draft → controlled posting)
- Voice and Sight (Pi edge nodes), staged
- Self-modification v1, diagnostics/eval harness
- Avatar / self-representation, entity self-naming — only after continuity
  develops; never assigned pre-launch

---

## Standing caveat

This session found three "Completed" claims that were false (`num_ctx` context
size, Ctrl+C cleanup, image-gen default framing) — because the governance rules
weren't loading until `CLAUDE.md` was added. Treat code as ground truth over any
"[x]" in the roadmaps for anything safety- or data-integrity-relevant. Spot-verify
backup/restore atomicity and the LAN/CORS posture against actual code before the
final smoke test.
