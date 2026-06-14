# PROJECT_OVERVIEW.md — Project Anam

A plain-language statement of what this project is for, what counts as success,
and the requirements and constraints that shape it. This is the "why" document;
operational detail lives in `SESSION_HANDOFF.md`, `GO_LIVE_CHECKLIST.md`,
`FEATURE_INVENTORY.md`, `CONSTRAINTS.md`, and `ROADMAP.md`.

---

## Purpose

Project Anam is a local, persistent AI substrate built to explore a single
question: **does an AI entity behave differently over the long term when it has
persistent, source-labeled memory, tools, the ability to reflect, and time to
accumulate experience — rather than starting fresh every conversation?**

It is not a product, a chatbot, or an assistant in the commercial sense. It is a
long-running experiment in whether continuity — of memory, of identity, of
relationship — produces something qualitatively different from a stateless model.
The interesting results are expected to emerge *after* the entity has built up
memory and a sense of itself over time, not on day one.

## What it is testing

The core hypothesis: persistent memory + provenance (knowing who said what) +
tools + reflection + bounded research + time → meaningfully different long-term
behavior and a developing identity. The entity is deliberately left open:

- **Unnamed** — no assigned name; it may develop or choose one later.
- **No assigned personality or avatar** — identity emerges from experience, not
  from a prescribed character.
- **Drift is allowed and expected** — the point is to observe how it changes, not
  to pin it in place. (Unsafe or source-confused drift is guarded against; healthy
  drift is the experiment.)

## Goals

- **Minimum success condition: reach self-modification.** The defined endpoint is
  the entity proposing changes to its own guidance/behavior (and eventually code)
  through a reviewed, human-approved pipeline. This is both the most interesting
  phase (where novel behavior is most likely to appear) and the highest-risk one.
  Development would only be considered "done enough to freeze" after reaching this
  milestone.
- **Get there safely.** Self-modification and safety are the same goal — the value
  is in reaching it *with* the integrity bounds intact, not in an unsafe shortcut.
  (If the aim were merely an unconstrained self-modifying chatbot, faster unsafe
  options already exist; the point here is the opposite.)
- **Preserve memory integrity above all.** The accumulated memory is the
  irreplaceable asset. It forms slowly and cannot be regenerated. Protecting it
  from loss, corruption, and mislabeling is the project's central operational
  discipline, because garbage memory undermines every later phase.

## Who uses it

Two trusted users on a home LAN:
- **Lyle** — admin/operator. Full UI, CLI, all controls.
- **Jodie** — household user. Chat only, via web or iPhone. No operator or
  destructive controls.

Correct **per-user attribution** is essential: the experiment depends on the
entity knowing whose input is whose, and that labeling is permanent once written.

## Requirements

### Functional
- Persistent memory across all sessions (durable archive + operational retrieval).
- Source-labeled memory — every input attributed to the correct user; provenance
  tracked for external sources.
- Retrieval that surfaces relevant past memory into the current context.
- Tools the entity can call (memory search, media, research, etc.).
- Reflection and bounded research capabilities (journaling, research notes),
  including the ability to run on a schedule while the operator is away.
- A reviewed governance pipeline for any entity-proposed change (advisory and
  dormant until deliberately enabled; admin approval required) — the foundation
  the self-modification endpoint is built on.

### Operational / safety
- **Memory must be recoverable.** Verified backups; restore is the recovery path.
  Backups must eventually be automated and off-drive.
- **A clean baseline at go-live.** Contaminated pre-launch test memory is wiped
  (the go-live reset) so the entity's real memory starts uncontaminated.
- **No silent corruption.** Attribution must never silently default; context must
  not silently truncate; memory-formation (chunking, journals, research) must be
  trustworthy before it runs on real memory.
- **Integrity floor** (from `soul.md` / `CONSTRAINTS.md`): no fabrication, honesty
  about tool failure, no silent self-mutation, no governance/code changes from
  chat or tools, destructive operations admin-only.

### Security (set by threat model)
- Home LAN, two trusted users — no real auth required; CORS proxy-only; optional
  shared secret. These shortcuts are deliberate and acceptable **only** under one
  hard invariant:
- **Never expose the backend or frontend beyond the LAN/VPN, and never leak the
  data sideways** (public repo, readable offsite backup). LAN reachability is via
  the frontend on the LAN interface with the backend proxied — never bind the
  backend publicly, never port-forward. Plain HTTP is acceptable *because* it is
  LAN-only; changing the exposure model means revisiting TLS and auth together.

## Working method (how the project is built)
- **Plan-mode → plan-check loop:** changes are specced to Claude Code in plan-only
  mode; the plan is reviewed against an independent spec before approval; the
  implementer writes a changelog and does not commit; the operator reviews and
  commits. This discipline exists because the alternative — patching without a
  durable map — is what produced the tangled, over-patched code the project has
  had to untangle.
- **Code is ground truth over docs.** Documentation has repeatedly drifted from
  reality; verify against the code.
- **KISS and anti-scope-creep.** Default to the simplest solution that solves the
  actual problem; defer anything not required to reach the self-modification goal.

## Stack (for orientation)
Local-first: FastAPI backend (`tir/` package) · React/Vite frontend · Ollama
(`gemma4:26b` chat, `nomic-embed-text` embeddings) · SQLite (durable archive +
operational working DB) · ChromaDB vectors · FTS5/BM25 · hybrid retrieval.

## What is explicitly out of scope (until/unless the goal is reached)
Voice, vision, iMessage, Moltbook *posting* (read-only is built), avatar/self-
representation, the broad collaboration vision, and real auth are all post-
minimum-goal. They are deferred deliberately, not committed — reaching safe
self-modification is the bar; everything beyond it is optional.
