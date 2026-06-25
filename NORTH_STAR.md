# NORTH_STAR.md — Project Anam

> **Audience: the humans and AI assistants building this project. NOT loaded into the entity.**
> This is the project's intent — read it first, before any other doc, at the start of every session.
> It does not change except when the *nature of the project* changes. If you want to add a task,
> a status, or a decision here, you are using the wrong document.
>
> Homes: **intent → here** · decisions → `DECISIONS.md` · status → the latest `SESSION_HANDOFF` · tasks → the roadmap.
> Keep them separate. Intent leaking into the other docs (and getting garbled across sessions) is the
> problem this file exists to stop.

---

## 1. The thesis

[ONE OR TWO SENTENCES — YOURS TO SET. Working version, edit to match your actual intent:]

Project Anam tests whether persistent, accumulated memory on a deliberately minimal, pinned
substrate produces a **coherent, emergent sense of self** in an AI entity — one that diverges
**measurably** from the base model's defaults over time — *or* whether behavior tracks the
RLHF baseline regardless of how much memory accumulates.

The question is genuine. The thesis is not "memory creates a self." It is "**does it?**"

---

## 2. Success and null — given equal weight

A cleanly-measured **null is a valid result, not a failure.** If accumulated memory does not move
behavior away from baseline — if the entity tracks the base model regardless — that is a real,
informative outcome, honestly reported.

This is stated first and plainly because the standing danger is unconsciously optimizing the project
toward "make the entity *seem* alive." That instinct manufactures false positives and is how a clean
experiment contaminates itself into a flattering result. **We are measuring, not performing.**

- **Minimum success condition (what counts as "the experiment ran"):** the entity reaches the
  self-modification milestone — it proposes a change to its own guidance through the human-approved
  pipeline, grounded in its own accumulated experience.
- **Signal:** consistent, measured divergence of the memory-bearing entity from a memoryless
  control, over time.
- **Null:** indistinguishable from the control. Disappointing, valid, reported.

---

## 3. Invariants — a decision may not violate these

These are the load-bearing principles. Each was re-established the hard way across multiple sessions.
If a proposed change breaks one of these, it is not a tweak — it is changing the experiment into a
different experiment, and must be made consciously and on the record, not by drift.

1. **Clean, legible baseline before external input.** The entity's formative input is a known,
   bounded, attributable stream. Uncontrolled external input (AI-social feeds, the open web) is not
   present at launch; it is added later, deliberately, as a *dated variable* so its effect can be
   measured — never as a launch default.

2. Grant capacity, don't seed content. Give the entity the ability to reflect, decline, and
   self-model. Do not hand-author the self, the personality, the goals, or the user-model —
   including the entity's name, self-image, and identity, which must emerge rather than be assigned.
   The self is the thing we are watching emerge; authoring it destroys the measurement.

3. **Minimal, legible substrate (KISS as integrity, not preference).** Accumulated memory must be the
   only interesting variable. Every added mechanism, capability, or piece of always-loaded content is
   a confound. Simplicity here is experimental rigor, not engineering taste.

4. **Never silently mutate the store; provenance is sacred.** Every record carries where it came from.
   The entity must always be able to distinguish what it *experienced* from what it *created* from what
   it *ingested*. Write-time integrity cannot be reconstructed later — protect the raw stream.

5. **The human operator is not ground truth.** The system surfaces conflict; it does not treat Lyle (or
   any user) as an authority to be deferred to. Conflict-flagger, not truth-arbiter.

6. **Capabilities are dated, deliberate, post-baseline variables — not launch features.** Vision,
   social, image generation, voice, avatar, and similar are *orthogonal to the thesis*. Each changes
   the experiment (usually by adding input that can't be attributed). None completes it. The pull to
   add them "because they're valuable" is the project's characteristic scope-creep failure mode.

---

## 4. What this is NOT

- **Not a product.** No users to please, no feature parity to reach, no launch bar but "the substrate
  is clean and the baseline is captured."
- **Not an assistant.** The entity is not being built to be helpful, agreeable, or capable. It is being
  built to *accumulate and possibly become*.
- **Not a capability showcase.** That the model *can* do something (see images, browse, post, speak) is
  never a reason to wire it in. Capability is orthogonal to the question being asked.
- **Not finished when it launches.** Launch is the *start* of the only clock that matters — the entity's
  lived time. The memory-defining work (consolidation, friction with its own past, felt time) is built
  *by watching it accumulate*, against real data — not before, against guesses. At launch, it is
  essentially a clean, provenanced, timestamped log. That is correct. The memory *emerges from
  processing the log* over time.

---

## 5. The one rule that keeps this doc honest

Austerity. This file holds invariants only. It changes almost never. The moment it accumulates tasks,
status, or churn, it has become another stale tracking doc — and the project already has the cautionary
tale of several that drifted and disagreed. If you're tempted to edit it, ask: *has the nature of the
project actually changed?* If not, the thing you want to write belongs in one of the other three homes.
