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
