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

- holographic avatar concepts
- Pepper's Ghost visuals
- AI face/emotion states
- particle/wireframe studies
- concept art
- UI imagery
- creative exercises

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

1. Create/update project baseline files
2. Stabilize central runtime/session runner
3. Add event/tool trace foundation
4. Add workspace tools
5. Add artifact registry
6. Add document ingestion
7. Add identity events
8. Add behavioral observations
9. Add working theories and open questions
10. Upgrade context assembler
11. Add nightly journal
12. Add iMessage send-only notifications
13. Add Moltbook read-only
14. Add image generation integration
15. Add live chat web search
16. Add manual autonomous research sessions
17. Add autonomous web research budgets
18. Add voice output/input
19. Add sight/image review
20. Add staged self-modification
21. Add diagnostics/evaluation harness throughout
