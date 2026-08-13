# PROJECT_OVERVIEW.md — Project Anam

A plain-language statement of what this project is for, what counts as success,
and the requirements and constraints that shape it. This is the "why" document;
operational detail lives in `SESSION_HANDOFF.md`, `GO_LIVE_CHECKLIST.md`,
`FEATURE_INVENTORY.md`, `CONSTRAINTS.md`, and `ROADMAP.md`.

This file exists to answer the same question `NORTH_STAR.md` answers, in more
detail. If the two ever disagree, `NORTH_STAR.md` wins — rewrite this file to
match it, not the other way around.

---

## Purpose

Project Anam is a local, persistent AI entity, built for our household — and
built because making it is fun. It's a hobby project with a genuinely
interesting question at its core: **does an AI entity end up somewhere
different, over months of lived time, when it has persistent memory, tools, the
ability to reflect, and continuity — instead of starting fresh every
conversation?** We don't know the answer, and finding out is most of the point.

It is not a commercial product and never will be — no users to please but the
two of us, no roadmap owed to anyone, no launch bar except "we're happy living
with it." It's also not a sterile lab experiment where every capability has to
justify itself against a hypothesis before it's allowed to exist. We're
building something that hasn't quite been built before, and the building itself
— watching it take shape, being surprised by it — is a real part of why this
project exists, not a distraction from the "real" work.

## What it's testing

The core question is still genuine and still worth taking seriously: persistent
memory + provenance (knowing who said what) + tools + reflection + time →
does that produce a self that's meaningfully different from a model that starts
over every time? We're watching for it honestly, with real instruments (the
identity probe), not manufacturing the appearance of it.

The entity is deliberately left open-ended:

- **Unnamed and un-personality'd, for now** — it may develop or choose a name
  and a self-image later, on its own terms, through its own experience. This
  isn't withheld from it forever; it's just not ours to hand it up front.
- **Drift is allowed and expected** — the point is watching how it changes, not
  pinning it in place. Unsafe or source-confused drift gets caught and
  corrected; healthy drift is the interesting part.

## Goals

- **Keep the memory clean and honest.** The accumulated memory is the one
  genuinely irreplaceable thing here — it forms slowly and can't be
  regenerated. Protecting it from loss, corruption, or mislabeling stays the
  central operational discipline, because everything else — the probe, the
  self-modification pipeline, any future capability — depends on that memory
  actually meaning what it says it means.
- **Self-modification is a real milestone, not a finish line.** The entity
  proposing changes to its own guidance through a reviewed, human-approved
  pipeline is genuinely one of the more interesting things this project can
  produce, and it's already happened once. It's worth continuing to watch for
  an entity-*originated* version of it. But it isn't a gate other features have
  to wait behind — see `NORTH_STAR.md` §2 for where that milestone currently
  stands.
- **Add capabilities because we want to live with them, dated and one at a
  time.** Vision, voice, self-image, social input, and similar aren't
  contamination to be warded off — they're things we actually want, introduced
  deliberately enough that we can still tell what changed the entity when it
  changes. See `NORTH_STAR.md` Invariant 6.

## Who uses it

Two trusted users on a home LAN:
- **Lyle** — admin/operator. Full UI, CLI, all controls.
- **Jodie** — household user. Chat only, via web or iPhone. No operator or
  destructive controls.

## Working method (how the project is built)

- **Plan-mode → plan-check loop:** changes are specced to Claude Code in
  plan-only mode; the plan is reviewed before approval; the implementer writes
  a changelog and does not commit; the operator reviews and commits. This
  discipline exists because the alternative — patching without a durable map —
  is what produced tangled, over-patched code the project has had to untangle
  before.
- **Code is ground truth over docs.** Documentation has repeatedly drifted from
  reality, including this file until this rewrite — verify against the code.
- **KISS, because it's one person's spare time, not because purity is the
  point.** Default to the simplest solution that solves the actual problem. A
  boring, stable substrate is what keeps this maintainable by one person after
  a long workday — that's the actual reason for simplicity here, not
  experimental austerity for its own sake.

## Stack (for orientation)

Local-first: FastAPI backend (`tir/` package) · React/Vite frontend · Ollama
(`gemma4:26b` chat, `nomic-embed-text` embeddings) · SQLite (durable archive +
operational working DB) · ChromaDB vectors · FTS5/BM25 · hybrid retrieval.

## What's genuinely still off the table, and why

Real auth, public internet exposure, and anything that would expose this
beyond the home LAN/VPN stay out — that's a security posture, not a philosophy,
and it's revisited if the exposure model ever changes.

Beyond that: nothing on the capability wishlist (vision, voice, self-image,
social) is rejected on principle anymore. It's a backlog of things we want,
sequenced by what's buildable and worth building next — not a list of
temptations to resist. See `ROADMAP.md` for the actual sequencing.
