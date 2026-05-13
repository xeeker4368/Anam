# DECISIONS.md

## Purpose

This file records active Project Anam decisions so future ChatGPT, Codex, Claude, Claude Code, or local AI sessions do not relitigate or accidentally undo them.

---

# Active Decisions

## Decision 001 — Project Anam is the substrate, not the entity name

**Status:** Active

Project Anam is the project/substrate/platform name. It is not the AI entity's name.

Implications:

- Do not write “You are Anam” in prompts.
- Do not call the entity Anam in documentation.
- Do not store Anam as `entity_name`.
- Use “the entity” or “AI entity” unless/until the entity chooses a name.
- Treat Tír as historical/previous naming context unless explicitly stated otherwise.

---

## Decision 002 — The entity currently has no name

**Status:** Active

The entity currently has no name.

Reason: A name should emerge from experience if it becomes meaningful, not be assigned by a seed file, code, user profile, or assistant.

Implications:

- `soul.md` must not assign a name.
- Code/config must not assign a name.
- If a name is later chosen, store it as an identity event.
- The entity may later revise or reject a chosen name.

---

## Decision 003 — No assigned personality

**Status:** Active

The project will not give the entity a fixed personality.

Reason: The project aims to observe whether personality-like continuity emerges from memory, behavior, correction, research, creativity, action, reflection, and experience. Assigning traits would contaminate the experiment.

Implications:

- Do not create prescriptive personality sliders.
- Do not create fixed personality traits.
- Avoid prompts that say the entity is curious/cautious/warm/etc.
- Use behavior observations instead.

---

## Decision 004 — Behavior is observed, not configured

**Status:** Active

The system may observe behavioral patterns and store them as evidence-linked, revisable behavioral memory.

Implications:

- Add `behavior_observations`, not prescriptive `personality_traits`.
- Observations require evidence.
- Observations should be revisable/supersedable.
- Context should present them as observed patterns, not identity commands.

---

## Decision 005 — Raw experience is primary

**Status:** Active

Raw conversations, actions, documents, tool traces, research sessions, corrections, journals, creative artifacts, and failures are primary experience.

Implications:

- Preserve raw archive.
- Treat summaries as derived artifacts.
- Do not inject hidden summaries as identity.
- Maintain source links and provenance.

---

## Decision 006 — Working theories are needed

**Status:** Active

The entity should be able to form revisable working theories / provisional conclusions.

Reason: The autonomous research cycle is intended to let the entity form opinions/conclusions and build on prior research, not merely produce reports.

Implications:

- Add working theory storage.
- Add theory revision/supersession.
- Retrieve relevant theories in context.
- Keep theories revisable.

---

## Decision 007 — Open questions should be first-class

**Status:** Active

The system should preserve unresolved questions from conversations and research sessions.

Implications:

- Add `open_questions`.
- Link questions to theories, sessions, memories, and documents.
- Track status: open, investigating, resolved, abandoned, superseded.

---

## Decision 008 — Web search differs between chat and autonomy

**Status:** Active

Live chat search and autonomous-cycle search should use different policies.

Implications:

- Chat web search can be enabled by default with small limits.
- Autonomous web search should be disabled by default.
- Autonomous web search requires explicit task permission and budgets.
- All web searches should be traced and remembered.

---

## Decision 009 — Self-modification should be staged and remembered

**Status:** Active

Self-modification should use staged proposals, patches, tests, activation, and memory of outcomes.

Implications:

- Do not allow silent direct core mutation as the first version.
- Use staged patch folders.
- Store proposals and outcomes.
- Treat self-modification as experience.

---

## Decision 010 — soul.md remains minimal

**Status:** Active

`soul.md` should remain a minimal seed orientation file.

Implications:

- No assigned name.
- No fixed personality.
- No project-specific working theories.
- No user profile.
- No hidden self-summary.

---

## Decision 011 — Workspace is distinct from self-modification

**Status:** Active

The entity should have a workspace for writing, coding, research, images, drafts, experiments, journals, and artifacts. This workspace is separate from direct modification of the core substrate.

Implications:

- Workspace tools can be added earlier than self-modification.
- Workspace writes are lower risk than core substrate edits.
- Core substrate edits should remain staged and traceable.
- Workspace outputs should become artifact memory.

---

## Decision 012 — Nightly journaling should be first-class

**Status:** Active

The entity should eventually create a nightly journal reflecting on the day.

Implications:

- Add scheduled reflection.
- Journal entries should be stored as artifacts and retrievable memory.
- Journals should include conversations, actions, research, corrections, created artifacts, open questions, and possible behavior observations.

---

## Decision 013 — Image generation should be first-class creative functionality

**Status:** Active

The entity should eventually be able to generate and possibly edit images.

Implications:

- Add image tools later.
- Store prompts, outputs, revision lineage, and user feedback.
- Generated images should be artifacts.
- Image generation may use external services/backends if local generation is impractical.

---

## Decision 014 — Moltbook integration should be included

**Status:** Active

The entity should eventually have access to Moltbook.

Implications:

- Start read-only if possible.
- Draft-only posting before controlled posting.
- Trace Moltbook reads/posts/replies.
- Store Moltbook interactions as action/social memory.
- Do not post freely without mode/policy decisions.

---

## Decision 015 — iMessage communication should be included

**Status:** Active

The entity should eventually communicate through iMessage.

Implications:

- Start send-only notifications.
- Later support approval messages.
- Later support conversational iMessage.
- Store channel metadata and transcripts as communication memory.

---

## Decision 016 — Voice and sight are future goals

**Status:** Active

The entity should eventually gain voice and sight, likely using an edge device such as a Raspberry Pi 5 for microphone/speaker/camera capture.

Implications:

- Mac mini should remain the brain/substrate.
- Raspberry Pi 5 can act as voice/sight edge node.
- Start with push-to-talk or snapshots, not always-on perception.
- Store transcripts and visual observations as memory.

---

## Decision 017 — Governance/runtime files are not normal artifact memory

**Status:** Active

Project governance and runtime files are builder/runtime materials, not ordinary uploaded source artifacts.

Implications:

- Normal artifact ingestion must block governance/runtime filenames.
- Governance files may be backed up/restored through explicit allowlists.
- Intentional governance-file inspection should use a dedicated path later.
- Do not let accidental uploads turn governance files into uploaded source memory.

---

## Decision 018 — Behavioral guidance is AI-proposed and admin-approved

**Status:** Active

Behavioral guidance entries should come from AI-proposed guidance reviewed and approved by an admin.

Implications:

- The UI may review existing proposals but should not create behavioral guidance proposals.
- `BEHAVIORAL_GUIDANCE.md` is not loaded into runtime context yet.
- No automatic apply-to-file behavior exists yet.
- Rejected proposals remain visible as evidence for future review.

---

## Decision 019 — Local-network API secret is hardening, not full auth

**Status:** Active

`ANAM_API_SECRET` provides lightweight protection when the API is exposed on a local network.

Implications:

- It is not a replacement for user sessions, admin roles, or full authentication.
- Do not store the secret in the database.
- Do not hardcode secrets.
- Full admin/user role enforcement remains future work.

---

## Decision 020 — Do not deliberately forget raw experience

**Status:** Active

Deliberate forgetting of raw experience is rejected.

Implications:

- Raw experience should remain preserved.
- Future salience or value-density systems may affect what is surfaced, summarized, or prioritized.
- Salience must not silently delete or erase raw records.

---

## Decision 021 — Use “review pass” in formal docs

**Status:** Active

Formal project documents should prefer “review pass” over “dream” for future reflective review workflows.

Implications:

- Keep language operational and inspectable.
- Do not imply mystical, hidden, or unreviewable background behavior.

---

## Decision 022 — SELF_UNDERSTANDING.md is descriptive and revisable

**Status:** Active

`SELF_UNDERSTANDING.md` is the approved concept name for a future reviewed, revisable self-understanding surface.

Implications:

- It should describe experience-derived self-interpretation, not prescribe behavior.
- It should not be named `PERSONALITY.md`, `SELF_PROFILE.md`, `IDENTITY.md`, or `SELF_MODEL.md` for now.
- Entries should be AI-proposed and admin-reviewed in future implementation.
- Admins should not normally author self-understanding entries directly.
- Rejected proposals should remain visible with review reasons.
- Runtime loading is deferred and must be separately designed.
- If runtime loading is later added, it should sit below `soul.md` and operational guidance and should not be treated as behavioral instruction.

---

## Decision 023 — Behavioral guidance needs explicit scope before scale

**Status:** Active

Future active behavioral guidance should support explicit user, channel, context, and applicability scope before the guidance file grows large.

Implications:

- Existing unscoped guidance is interpreted as global/default guidance.
- Future global guidance should be chosen deliberately, not created by omission.
- Scope should be present in both proposal records and applied Markdown entries.
- Early proposal scope may live in `metadata_json` or a structured metadata object before first-class columns are justified.
- Applied `BEHAVIORAL_GUIDANCE.md` entries should include human-readable scope metadata.
- Runtime filtering is deferred and must preserve debug visibility.
- If scope matching is uncertain, labeled inclusion is safer than silent exclusion.
- Scoped guidance does not override `soul.md` or `OPERATIONAL_GUIDANCE.md`.

---

## Decision 024 — Behavioral guidance removal and revision preserve history

**Status:** Active

Future approved removal and revision proposals should retire and supersede guidance rather than deleting or silently rewriting it.

Implications:

- Removal proposals should mark or move active guidance to retired guidance, not delete it.
- Revision proposals should retire the old entry and append a new active entry.
- Targeting should prefer stable guidance/proposal IDs over text matching.
- `target_text` may be a fallback only with exact validation.
- Retired and superseded guidance should remain reviewable but must not load as active runtime guidance.
- Dry-run diff/plan output should be required before write behavior.
- Proposal status should become `applied` only after successful file application.

---

## Decision 025 — Manual research produces provisional artifacts, not truth

**Status:** Active

Manual research should be a user-triggered, bounded artifact-producing workflow. Research conclusions are working notes, not permanent truth, runtime guidance, self-understanding, or project decisions.

Current implementation note: Manual Research Foundation is complete for the first bounded CLI path. `research-run` supports dry-run, `--write` file creation, explicit `--write --register-artifact` registration/indexing, and working-research retrieval framing.

Implications:

- Research should have a clear purpose and consumption path.
- Dry-run should be the default for future manual research commands.
- File creation should be explicit through `--write`.
- Artifact registration and indexing should be explicit through `--register-artifact`.
- Retrieved research should be framed as working research notes.
- Research may suggest open loops, review items, or future working-theory proposals.
- Research must not directly mutate `BEHAVIORAL_GUIDANCE.md`, `SELF_UNDERSTANDING.md`, runtime prompt guidance, or project decisions.
- Web research requires a separate bounded source collection design before implementation.

---

## Decision 026 — Research continuation creates new notes

**Status:** Active

Manual research continuation should create a new provisional research note rather than overwriting, editing, or silently revising the prior note.

Implications:

- Prior research notes remain intact as source artifacts.
- Continuation notes must preserve lineage to the prior artifact or file.
- Prior findings are inputs, not authorities.
- Weakened or superseded prior claims should be stated in the new note, not applied by mutating the previous artifact.
- Formal working-theory promotion, supersession, or revision remains a separate future design.
