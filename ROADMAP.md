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

The AI-generated behavioral guidance proposal path was built and tested pre-live.

Behavioral guidance runtime loading is dormant before go-live. `BEHAVIORAL_GUIDANCE.md` should not contain active `- Guidance:` lines and should not shape runtime prompts or reflection journal entity context. The design lesson is preserved in `docs/BEHAVIORAL_GUIDANCE_DORMANT_DECISION.md`.

Low-risk pre-go-live course correction is complete:

- [x] Behavioral guidance runtime loading dormant before go-live
- [x] Neutral retrieved-context source framing
- [x] `OPERATIONAL_GUIDANCE.md` compressed to source/tool/action safety
- [x] Journal and research prompt looseness for quiet/low-signal outputs
- [x] Tool description/source framing cleanup
- [x] `soul.md` minimality review with no edit recommended

Guidance scoping now has a concept design in `docs/GUIDANCE_SCOPING_DESIGN.md`. No schema, runtime filtering, proposal-scope review, or scoped apply-to-file behavior is implemented yet.

Removal and revision apply mechanics now have a concept design in `docs/BEHAVIORAL_GUIDANCE_REVISION_DESIGN.md`. Apply behavior is dormant before go-live; future reintroduction would need a separate reviewed design decision.

## Current Phase Reorder

### Pre-Go-Live Evaluation — Experiment Hypothesis / Observation Criteria v1

- [x] Experiment hypothesis and observation criteria — define what Project Anam is trying to observe, what counts as interesting signal, weak/no signal, baseline comparison, observation windows, and evaluation boundaries.

This is a human/project evaluation aid only. It is not `soul.md`, behavioral guidance, operational guidance, a runtime prompt, or a personality, name, avatar, value, or identity assignment.

### Pre-Go-Live — Trusted Household User Mode v1

- [ ] Support Lyle and Lyle's wife as known household users.
- [ ] UI clearly displays the current active user.
- [ ] The runtime may trust local UI/client-supplied user identity for household LAN/VPN use only.
- [ ] Source labels continue preserving which household user supplied a conversation, message, or artifact.
- [ ] Document that this is not real authentication.

This mode accepts trusted-client `user_id` only for the current household LAN/VPN deployment. It is not suitable for public internet exposure, guest access, untrusted LAN use, or sensitive admin UI expansion.

### Phase 4 — Image / Media Capability Foundation v1

Pre-go-live foundation work:

- [ ] Image generation artifacts — generated images saved with prompt, provenance, timestamps, model/backend metadata, references, source links, and uncertainty labels.
- [ ] Uploaded image/screenshot artifact support — uploaded images can be stored, referenced, and reasoned over as artifacts.
- [ ] Image artifact recall — prior generated/uploaded images can be referenced later through artifact metadata and source-linked context.
- [ ] Media provenance model — image prompts, edits, uploaded sources, generated outputs, and revision lineage remain inspectable.
- [ ] Generated document artifacts — reports, markdown, docs, plans saved/indexed.
- [ ] Artifact gallery/manager — browse generated/uploaded artifacts.

This is capability foundation, not avatar creation. It supports future self-representation work without assigning an appearance or identity before go-live.

### Phase 5 — Code and Sandbox Foundations

- [ ] Code sandbox/staging — safe place for generated code and patches.
- [ ] Test execution controls — approved tests only, logged results.
- [ ] Patch review flow — proposal → staged patch → test → human approval.
- [ ] Self-modification guardrails — no direct runtime changes without review.

### Pre-Go-Live Candidate — Bounded Scheduler / Nightly Tick v1

A small bounded scheduler may be considered before go-live if manual bounded research remains stable.

Constraints:

- runs at most one bounded `research-open-loop-run-next` style action per scheduled window
- obeys per-loop and daily limits
- writes artifacts/source traces only through existing approved paths
- easy to disable
- clear logs and metadata
- no governance mutation
- no `soul.md`, decision, guidance, code, or self-modification changes
- no external writes
- no broad autonomous web crawling
- no working-theory promotion
- no scheduler expansion beyond explicitly approved bounded actions

### Post-Go-Live — Avatar / Self-Representation Development

After the entity develops continuity and may eventually choose a name, Lyle and the entity can work together on visual self-representation.

This may include:

- avatar direction
- visual identity exploration
- state/expression sets
- UI/display integration
- later Pepper's Ghost or hologram experiments

Do not create or assign the avatar before go-live.

### Post-Go-Live — Expanded Autonomy / Background Research

Expanded autonomy remains post-go-live. It may include richer autonomous research windows, broader source use, global caps, drift canary integration, stronger monitoring, and deeper background research only after bounded scheduler v1 proves stable.

### Post-Go-Live / Before Broader Exposure — Real Login / Session Auth v1

Real login/session auth is required before public internet exposure, guest access, untrusted LAN access, broader device/network deployment, or sensitive admin UI expansion.

Expected direction:

- backend resolves user from an authenticated session or token
- frontend no longer controls user identity directly
- body-trusted `user_id` is removed or ignored
- per-user authorization rules become explicit

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

- traceable generated image artifacts
- uploaded image/screenshot artifact understanding
- image artifact recall
- future post-go-live avatar concepts
- future AI face/emotion state exploration
- particle/wireframe studies
- concept art
- UI imagery
- creative exercises

Avatar/self-representation creation belongs after go-live, after the entity develops continuity and may eventually choose a name. Pre-go-live image work should establish capability, provenance, storage, and recall without assigning an appearance.

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

Manual Research Foundation is complete for the first bounded CLI path. `research-run` can generate provisional research notes, write them to `workspace/research/`, optionally register/index them with `--write --register-artifact`, and retrieve them with explicit working-research source framing. Research remains provisional and does not become truth, guidance, self-understanding, project decisions, open loops, or review items automatically.

Research track status:

- [x] Manual Research Cycle Design v1
- [x] CLI dry-run/write research note generation
- [x] Explicit artifact registration/indexing with `--write --register-artifact`
- [x] Retrieved research source framing
- [x] Research Continuation Design v1
- [x] Manual research continuation implementation
- [x] External Review Checkpoint v1
- [x] Behavioral guidance runtime loading dormant before go-live
- [x] Research open-loop design
- [x] Research open-loop runtime creation
- [x] Bounded / Scheduled Research Design v1
- [x] Manual bounded open-loop research planner
- [x] Manual bounded open-loop research runtime
- [x] Research open-loop run-next
- [ ] Title/search continuation design
- [ ] Research review-item design
- [x] Moltbook source collection design
- [x] Moltbook source preview runtime
- [x] Bounded Moltbook source collection integration
- [x] Web source collection design
- [ ] Research promotion / working-theory rules design
- [ ] Bounded scheduler / nightly tick v1
- [ ] Expanded autonomous research scheduling/budgets

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

# Phase 18 — Expanded Autonomous Web Research With Budgets

Expanded autonomous web research remains post-go-live. A bounded scheduler/nightly tick v1 may be considered earlier only if it stays limited to explicitly approved bounded actions and does not broaden into web crawling or open-ended background research.

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

1. Web source collection implementation
2. Image / Media Capability Foundation v1
3. Image generation artifacts
4. Image/screenshot artifact understanding
5. Minimal household multi-user design
6. Minimal household multi-user implementation
7. Bounded Scheduler / Nightly Tick v1
8. Canary/drift observation design
9. Canary/drift observation implementation
10. UI polish / non-dev presentation
11. Go-live reset/hardening plan
12. Backup/restore smoke before live
13. Limited Live v1 smoke test
14. Code and sandbox foundations
15. Event/tool trace foundation hardening
16. Review pass foundation for conversations and artifacts
17. Identity events
18. Behavioral observations
19. Context assembler upgrade
20. Nightly journal
21. iMessage send-only notifications
22. Moltbook draft-only progression after read-only confidence
23. Expanded autonomy / background research
24. Autonomous web research budgets
25. Avatar / Self-Representation Development
26. Voice output/input
27. Sight/image review

`SELF_UNDERSTANDING.md` now has a concept design in `docs/SELF_UNDERSTANDING_DESIGN.md`. It is not implemented, not loaded into runtime context, and has no schema, service, UI, model tool, or apply workflow in the current checkpoint.
28. Add staged self-modification
29. Add diagnostics/evaluation harness throughout
