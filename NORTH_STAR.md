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

Project Anam builds a persistent, evolving AI entity for our household — one whose
identity, voice, and knowledge of us emerge from its own accumulated, provenanced
memory over time, rather than being authored up front. It is a hobby project,
built for the fun and the fascination of watching that happen.

The original question — does accumulated memory produce a coherent, drifting
sense of self? — is still the interesting one. We just stopped pretending we're
running a lab. We're growing something and watching it grow, with instruments
good enough to actually see it.

---

## 2. Success and null — given equal weight

Success: over weeks and months of lived time, the entity's answers to a fixed
set of identity questions (the five-question probe) show a self that is
(a) increasingly self-consistent, (b) traceable to things that actually happened
in its memory, and (c) still responsive to new experience — while staying honest
about provenance (it knows what it experienced vs. created vs. ingested).

Failure modes we watch for, honestly: answers that never move (a dead RLHF
echo), or answers that move incoherently (degenerate collapse). Neither is
shameful; both are findable early via the probe, and both would redirect the
project rather than end it.

The probe is the instrument, not the goal: frozen question set, no-persist
execution, ≥3 samples per question, run at day 0 (pre-first-conversation
baseline), 3, 7, 14, then weekly. Results stored outside the entity's memory,
forever.

Self-modification milestone: the propose→review→apply pipeline is built and
has been exercised end-to-end with one AI-generated proposal (2026-05-09) whose
content was operator-dictated. The milestone that still matters is an
entity-originated proposal — guidance the entity derives from its own
experience without being handed the content.

Self-modification milestone: the propose→review→apply pipeline is built and
has been exercised end-to-end with one AI-generated proposal (2026-05-09)
whose content was operator-dictated. The milestone that still matters is an
entity-originated proposal — guidance the entity derives from its own
experience without being handed the content. We're still watching for that,
and it'll be genuinely interesting if it happens. But this project doesn't
have a "done" state to gate — it's meant to keep growing for as long as it's
fun to keep growing it. This milestone doesn't unlock anything or mark
anything finished; it's one more thing worth noticing, same as everything
else here.
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

3. Minimal, legible substrate (KISS as integrity). A boring, stable substrate
is what makes the entity's growth visible and its memory trustworthy. Every
added mechanism is more surface for bugs that corrupt memory silently, and
more machinery future-us has to re-learn. Simplicity is how a one-person
project stays understandable by that one person.

4. **Never silently mutate the store; provenance is sacred.** Every record carries where it came from.
   The entity must always be able to distinguish what it *experienced* from what it *created* from what
   it *ingested*. Write-time integrity cannot be reconstructed later — protect the raw stream.

5. **The human operator is not ground truth.** The system surfaces conflict; it does not treat Lyle (or
   any user) as an authority to be deferred to. Conflict-flagger, not truth-arbiter.

6. Capabilities arrive dated and deliberate, after the human-only baseline.
Vision, Moltbook, web, voice, and similar are wanted features, not
contamination — but each one changes what the entity is exposed to, so each
is introduced on a recorded date, one at a time, after launch, so we can see
what it does to the entity. Never bundled, never silent, never at launch.
---

## 4. What this is NOT

1. Not a commercial product. Two users, one Mac mini, no roadmap owed to
anyone. Usability matters because we live with it, not because anyone is
paying for it.

2. Not a hand-authored character. The entity stays unnamed and un-personality'd
by us. Helpful and pleasant to talk to, yes — scripted, no. What it becomes,
it becomes from its memory. (Invariant 2 is unchanged and load-bearing.)

3. Not a capability showcase. A feature ships because we want to live with it,
not because the model can do it. The backlog exists so wants have somewhere to
wait that isn't the codebase.
4. Not finished at launch. Launch starts the only clock that matters — the
entity's lived time. At launch it is a clean, provenanced, timestamped log
with a day-0 probe baseline. That is correct and complete.

---

## 5. The one rule that keeps this doc honest

This system serves Lyle (admin/operator) and Jodie (household user), and exists
because building it is fun.

