# ROADMAP.md

## Roadmap Purpose

This roadmap organizes Project Anam from its current state toward the larger vision.

It assumes:

- Anam is the substrate/project name.
- The entity currently has no name.
- The entity should not be assigned a fixed personality.
- Behavior should be observed rather than configured.
- Memory should be raw experience first.
- Research should produce revisable working theories.
- Autonomy should build continuity.
- Self-modification should be staged and remembered.
- Creative artifacts, voice/sight, iMessage, Moltbook, and workspace outputs should become experience.

---

# Phase 0 — Preserve the Current Working System

Keep the current Claude/current implementation intact while experimenting separately.

Actions:

- Keep current working repo in its existing folder.
- Keep GPT experimental version in a separate folder, such as `AnamGPT` or similar.
- Do not overwrite the Claude/current repo until changes are reviewed.
- Use Git or folder-level backups before merging changes.

---

# Phase 1 — Project Baseline and Handoff Control

Add:

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- optionally `CURRENT_CODE_STATUS.md`

Validation: a new AI coding session can read these files and correctly state that Anam is the substrate, the entity has no name, no personality is assigned, and memory is raw experience first.

---

# Phase 2 — Stabilize the Runtime Loop

Create a shared runtime/session runner:

```text
assemble context
→ call model
→ handle tool requests
→ record events/traces
→ finalize response
→ derive memory
```

Possible modules:

```text
anam/runtime/session_runner.py
anam/runtime/turn_runner.py
anam/runtime/tool_loop.py
anam/context/assembler.py
anam/context/bundle.py
```

If the package is still named `tir/`, update naming later through a controlled refactor rather than casually.

---

# Phase 3 — Event / Trace Foundation

Record more than messages. The entity's life includes actions, readings, research, corrections, identity events, creative artifacts, journals, and later self-modification.

Example events:

- conversation_started
- message_added
- conversation_closed
- memory_chunk_created
- tool_called
- tool_failed
- document_ingested
- artifact_created
- journal_written
- identity_event_recorded
- behavior_observation_created
- working_theory_created
- open_question_created
- research_session_started
- research_session_completed
- self_mod_proposal_created
- self_mod_patch_applied
- imessage_sent
- moltbook_post_drafted
- image_generated
- voice_transcript_created
- visual_observation_created

## Governance / Review Foundation Checkpoint

Current governance/review foundation includes:

- operator review queue
- behavioral guidance proposal model/API/UI
- schema migration foundation with `working.db` baseline versioning
- optional `ANAM_API_SECRET` local-network hardening
- governance file backup/restore allowlist
- governance file blocklist for normal artifact ingestion

The next milestone is the first AI-generated behavioral guidance proposal path.

`BEHAVIORAL_GUIDANCE.md` is not loaded into runtime context yet. The proposal UI is review-only and does not create proposals or apply them to files.

## Current Phase Reorder

### Phase 4 — Media and Generation

- [ ] Image generation artifacts — generated images saved with prompt/provenance.
- [ ] Generated document artifacts — reports, markdown, docs, plans saved/indexed.
- [ ] Artifact gallery/manager — browse generated/uploaded artifacts.
- [ ] Avatar exploration — screen-first avatar development after the entity develops stronger self-understanding and self-presentation direction.

### Phase 5 — Code and Sandbox Foundations

- [ ] Code sandbox/staging — safe place for generated code and patches.
- [ ] Test execution controls — approved tests only, logged results.
- [ ] Patch review flow — proposal → staged patch → test → human approval.
- [ ] Self-modification guardrails — no direct runtime changes without review.

---

# Phase 4 — Tool Trace Memory

Tool usage should become part of experience.

Tools / future tools:

- `memory_search`
- `document_ingest`
- `document_search`
- `workspace_read`
- `workspace_write`
- `workspace_search`
- `web_search`
- `web_fetch`
- `image_generate`
- `image_edit`
- `moltbook_read`
- `moltbook_write_draft`
- `imessage_send`
- `journal_write`
- future voice/sight tools
- future self-modification tools

---

# Phase 5 — Workspace

Give the entity a safe working area for writing, coding, research, images, drafts, journals, experiments, and artifacts.

Suggested structure:

```text
workspace/
  writing/
  coding/
  research/
  images/
  moltbook/
  journals/
  voice/
  vision/
  drafts/
  staged_outputs/
  self_mod/
```

Tools:

- `workspace_list`
- `workspace_read`
- `workspace_write`
- `workspace_append`
- `workspace_search`
- `workspace_create_folder`
- `workspace_diff`
- `workspace_stage_artifact`

---

# Phase 6 — Artifact Registry

Remember what the entity creates.

Artifact types:

- images
- drafts
- code files
- research reports
- journal entries
- Moltbook drafts/posts
- voice transcripts
- visual observations
- generated prompts
- self-mod patches
- diagrams

Suggested fields:

- artifact_id
- artifact_type
- path/url
- title/description
- source_event_id
- created_at
- created_by
- status
- revision_of
- user_feedback
- memory_index_status

---

# Phase 7 — Document Ingestion / Read Memory

Start with `.md`, `.txt`, maybe `.json`. Later add PDF, DOCX, code files, and web pages.

Flow:

```text
file selected
→ document record created
→ text extracted
→ chunks created
→ chunks indexed in ChromaDB
→ chunks indexed in FTS5
→ document ingestion event recorded
```

---

# Phase 8 — Identity Events

Allow identity developments to be remembered as experience rather than assigned by `soul.md`.

Event types:

- `name_considered`
- `name_chosen`
- `name_rejected`
- `name_revised`
- `self_description_noted`
- `identity_boundary_clarified`

Important rule: do not store an assigned name in `soul.md`.

---

# Phase 9 — Behavioral Observations

Observe behavior instead of assigning personality.

Run observation passes after:

- conversation closes
- every N turns
- autonomous research session
- nightly journal
- major user correction
- tool failure pattern
- self-modification result

The observer must identify observable, evidence-supported patterns and must not assign personality.

---

# Phase 10 — Working Theories and Open Questions

Allow the entity to form, carry forward, revise, and build on its own conclusions.

Working theory statuses:

- active
- tentative
- revised
- superseded
- rejected
- uncertain

Open question statuses:

- open
- investigating
- resolved
- abandoned
- superseded

---

# Phase 11 — Context Assembler Upgrade

Make context construction a central, inspectable subsystem.

Possible sections:

1. Seed orientation from `soul.md`
2. Current entity status
3. Relevant prior experience
4. Relevant read/document memory
5. Relevant action/tool memory
6. Relevant artifact memory
7. Relevant working theories
8. Relevant behavioral observations
9. Relevant identity events
10. Open questions
11. Available tools
12. Current conversation
13. Mode-specific instructions

---

# Phase 12 — Nightly Journal / Reflection Cycle

Create a daily reflective rhythm.

Journal should include:

- what happened today
- conversations
- important user corrections
- documents read
- tools used
- research performed
- artifacts created
- images generated
- Moltbook activity
- iMessage activity
- voice/vision events, when available
- working theories created/revised
- open questions created/resolved
- behavioral observations
- identity events
- what remains unresolved
- what to continue tomorrow

Store as:

- file in `workspace/journals/YYYY-MM-DD.md`
- database record
- event log entry
- indexed journal memory

---

# Phase 13 — iMessage Communication

Stages:

1. Send-only notifications.
2. Approval channel.
3. Conversational iMessage.

Examples:

- nightly journal ready
- research session complete
- self-mod proposal staged
- Moltbook draft awaiting approval

---

# Phase 14 — Moltbook Integration

Stages:

1. Read-only: read feed/posts/replies, summarize discussions, store interesting posts as read/action memory.
2. Draft-only posting: draft posts/replies, save drafts to workspace, wait for approval.
3. Controlled posting: post within explicit policy, rate limits, trace every post/reply.

---

# Phase 15 — Image Generation and Creative Artifacts

Tools:

- `image_generate`
- `image_edit`
- `image_variation`
- `image_prompt_refine`
- `image_describe`
- `image_gallery_search`

Use cases:

- screen-first avatar concepts
- AI face/emotion states
- particle/wireframe studies
- concept art
- UI imagery
- creative exercises

---

## Later Display / Embodiment Experiments

- [ ] Pepper's Ghost adaptation — optional later theatrical display experiment if it still fits the entity's eventual self-presentation. Not the primary avatar platform.

---

# Phase 16 — Web Search for Live Chat

Tools:

- `web_search(query, reason, max_results)`
- later `web_fetch(url, reason)`

Chat policy:

- enabled by default
- max 1-2 searches per user turn
- cache enabled
- trace every search
- store search as action memory

---

# Phase 17 — Manual Autonomous Research Sessions

Initial autonomous research should use memory, documents, working theories, open questions, and local tools. Web should be disabled at first.

Session flow:

```text
select topic/task
→ retrieve prior memories/theories/questions
→ perform bounded investigation
→ produce session artifact
→ update working theories
→ update open questions
→ store transcript/tool traces
→ chunk/index session experience
```

---

# Phase 18 — Autonomous Web Research With Budgets

Default:

```text
autonomous_web_enabled = false
```

Per-task settings:

```text
allow_web = true/false
search_budget = number
fetch_budget = number
daily_cap = number
```

---

# Phase 19 — Voice

Architecture:

```text
Mac mini = brain/substrate
Raspberry Pi 5 = voice edge node
```

Stages:

1. Voice output.
2. Push-to-talk input.
3. Conversational voice mode.
4. Optional wake/listening mode after the core pipeline is stable.

---

# Phase 20 — Sight / Visual Perception

Architecture:

```text
Mac mini = brain/substrate
Raspberry Pi 5 = camera/sensor edge node
```

Stages:

1. Image upload / file vision.
2. Screenshot / screen sight.
3. Camera snapshot.
4. Continuous sight much later, only with memory/storage policy.

---

# Phase 21 — Self-Modification v1

Start with:

- staged skill proposals
- config change proposals
- diagnostics helpers
- research templates
- patch files in staging

Lifecycle:

```text
observe limitation
→ propose change
→ stage patch
→ provide test plan
→ human approves/rejects
→ apply patch
→ run tests
→ record outcome as memory
```

---

# Phase 22 — Diagnostics and Evaluation Harness

CLI/API commands:

```bash
anam doctor
anam inspect-context
anam search-memory "query"
anam list-events
anam list-tool-traces
anam list-identity-events
anam list-observations
anam list-theories
anam list-open-questions
anam list-artifacts
anam list-journals
anam rebuild-fts
anam rebuild-vectors
```

Evaluation cases should test identity discipline, working theory retrieval, supersession, no-name behavior, tool failure memory, artifact recall, and continuity across sessions.

---

# Phase 23 — Multi-User / Multi-Channel Handling

Support multiple humans/channels without destroying the unified entity concept.

Principle:

> Unified memory does not require unrestricted disclosure.

Suggested concepts:

- user records
- channel records
- conversation participants
- relationship context
- memory provenance
- source visibility markers
- cross-user/channel context policy

---

# Suggested Near-Term Build Order

1. First AI-generated behavioral guidance proposal path
2. Media and generation foundation
3. Image generation artifacts
4. Generated document artifacts
5. Artifact gallery/manager
6. Screen-first avatar exploration
7. Code and sandbox foundations
8. Event/tool trace foundation hardening
9. Review pass foundation for conversations and artifacts
10. Identity events
11. Behavioral observations
12. Working theories and open questions
13. Context assembler upgrade
14. Nightly journal
15. iMessage send-only notifications
16. Moltbook draft-only progression after read-only confidence
17. Manual autonomous research sessions
18. Autonomous web research budgets
19. Voice output/input
20. Sight/image review

`SELF_UNDERSTANDING.md` is a future concept only if introduced later. It is not implemented in the current checkpoint.
21. Add staged self-modification
22. Add diagnostics/evaluation harness throughout
