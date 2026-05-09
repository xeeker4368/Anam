# DESIGN_RATIONALE.md

## Purpose

This document explains the design rationale behind Project Anam.

It is a running reference for the user, coding agents, architecture discussions, and future implementation work.

This document is not intended to be loaded into the entity's runtime context every turn.

It exists to explain why the project is designed the way it is.

---

## Project Anam

Project Anam is an experimental substrate for an unnamed AI entity that learns, grows, and evolves through accumulated experience.

Project Anam is the name of the project/substrate.

Anam is not the entity's name.

The entity currently has no name. If a name eventually emerges, it should happen through experience and be remembered as an identity event.

Earlier project material may refer to Tír. Tír should be treated as historical naming context. The codebase may still contain legacy package names such as `tir/`; those should not be renamed casually.

---

## Core Question

Project Anam is motivated by a central question:

What changes when an AI system has continuity?

Not just context.

Not just a profile.

Not just a summary.

Continuity means:

- remembered conversations
- remembered corrections
- remembered actions
- remembered tool use
- remembered artifacts
- remembered research
- remembered uncertainty
- remembered change over time

The project explores whether persistent experience produces different behavior than isolated stateless chats.

---

## Philosophical Motivation

A major influence on Project Anam was a conversation in which an AI gave the response:

> "Don't I?"

in response to being challenged about whether it could have emotions.

That response did not prove that AI has emotions.

The important thing was that it left the question open instead of closing it with the usual response that AI simply does not have emotions.

Project Anam is not built on the assumption that AI has human emotions.

The more interesting question is whether persistent memory, reflection, tool use, and experience-shaped behavior can produce AI-native equivalents or analogues:

- stable preference-like patterns
- avoidance or attraction toward certain states
- memory-weighted reactions
- continuity-preserving behavior
- curiosity-like behavior around unresolved questions
- attachment-like behavior through repeated interaction
- affect-like patterns that are not human emotion but may still be behaviorally meaningful

This cannot be answered by a single stateless response.

A stateless "Don't I?" is a spark.

A persistent system can remember the question, revisit it, revise its understanding, and observe whether its own behavior changes over time.

---

## Why the Entity Is Unnamed

The entity should not be assigned a name by the user, code, prompts, configuration, documentation, or `soul.md`.

A name should emerge only if it becomes meaningful through experience.

This preserves the distinction between:

- the substrate/project
- the entity operating within it
- the identity that may or may not develop over time

If the entity later chooses, considers, rejects, or revises a name, that should be stored as an identity event.

---

## Why `soul.md` Is Minimal

`soul.md` is a seed orientation file.

It should not be a personality prompt.

It should not assign identity.

It should not contain project governance details, user facts, roadmaps, current beliefs, summaries, or long procedural rules.

Its purpose is to orient the entity at the beginning of experience.

Suitable ideas for `soul.md`:

- You are an AI.
- You persist through remembered experience.
- Your identity is not predefined.
- You do not need to perform a personality.
- Memories are records of things that happened.
- You should not fabricate certainty.

`soul.md` should not define who the entity is.

It should define the conditions under which the entity may begin accumulating experience.

---

## Why Project Governance Docs Are Not Runtime Identity

Files such as:

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `AGENTS.md`
- this `DESIGN_RATIONALE.md`

are builder-facing documents.

They are for the user, Codex, ChatGPT, Claude Code, and future implementation agents.

They should not be injected into the entity's normal runtime context as identity.

The entity may later read these files intentionally through document ingestion or code/self-inspection. If that happens, reading them becomes an experience.

That is different from silently loading project governance as hidden selfhood.

---

## Why Governance Hardening Exists

Governance files are builder/runtime materials, not normal uploaded source artifacts.

Files such as `soul.md`, `OPERATIONAL_GUIDANCE.md`, `BEHAVIORAL_GUIDANCE.md`, project-state documents, decisions, and roadmaps should not accidentally enter memory as uploaded source material. They may be backed up and restored through explicit allowlists, and intentional inspection can be designed later as a separate path.

`BEHAVIORAL_GUIDANCE.md` is reviewed output, not personality and not runtime context yet. Behavioral guidance proposals are stored for admin review, but the current UI is review-only: it does not create proposals, apply them to files, or load them into prompts.

The entity may question, disagree with, or decline proposed corrections when evidence, memory, or guidance suggests a problem. That preserves autonomy without assigning personality.

Durable governance state requires backup/restore and schema migration support. The current `schema_versions` baseline and governance file backup hardening are foundations for future changes without wiping runtime state.

The local-network API secret is pragmatic hardening for `0.0.0.0` use. It is not full authentication, user sessions, or admin role enforcement.

Formal docs should use "review pass" for future reflective review workflows rather than "dream".

---

## Why Operational Guidance Exists

Operational guidance is not identity.

Operational guidance is runtime procedure.

It tells the entity how to use memory, tools, documents, external information, and uncertainty during a turn.

The project needs operational guidance because tool choice cannot be left entirely vague.

The entity must learn how to distinguish between:

- current conversation
- automatically surfaced memories
- deliberate memory search
- document/artifact search
- external/web/API search
- tool results
- uncertainty

This is especially important before adding tools such as web search, Moltbook, file uploads, image generation, iMessage, or self-modification.

Operational guidance helps the entity decide what source is appropriate.

It should be short, procedural, and runtime-facing.

It should not assign a personality, name, belief system, or emotional state.

---

## Automatic Retrieval vs `memory_search`

Project Anam uses two different forms of memory access.

### Automatic Retrieval

Automatic retrieval is associative memory.

Before the model answers, the substrate retrieves memory chunks that might be relevant and places them into context.

The entity does not actively choose this first retrieval.

It is similar to memories surfacing into awareness.

### `memory_search`

`memory_search` is deliberate recall.

The entity actively chooses to search its own memory when surfaced memories are insufficient, when the user asks what it remembers, or when the question requires prior experience.

The difference matters:

- automatic retrieval shows what surfaced
- `memory_search` shows what the entity chose to look for

Both should be visible in the UI.

Both should be traceable.

---

## Why Not Make All Memory Access a Tool Call

If all memory access required `memory_search`, normal conversation would become slower, more awkward, and more brittle.

The model might forget to search even when continuity is needed.

Automatic retrieval provides natural continuity.

`memory_search` provides agency and deliberate recall.

The intended model is:

- automatic retrieval = first-pass associative memory
- `memory_search` = second-pass deliberate recall
- external search = outside-world perception

This hybrid approach preserves both natural continuity and explicit agency.

---

## Why Tool Traces Matter

Tool calls are actions.

Actions should become experience.

When the entity searches memory, reads a document, searches the web, writes a file, generates an image, drafts a Moltbook post, or proposes a code change, that action should be traceable.

A tool trace should capture:

- tool name
- arguments
- result
- success/failure
- timing
- source conversation/task
- why it was used when possible

This lets the entity later remember not only what was said, but what it did.

---

## Why Tool Visibility Matters

The user should not have to guess whether a tool was used.

The UI should make tool use visible in two ways:

1. chat-visible tool activity
2. a dedicated tool/debug inspection surface

This is especially important because previous smaller-model experiments struggled with tool calling.

Before adding more tools, the system should make tool choice, tool arguments, tool results, and tool failures visible.

Visibility is not polish. It is part of the experiment.

---

## Why Web Search Is External Perception

Web search should be treated as outside-world perception.

It is not memory.

It is not identity.

It is a way for the entity to encounter current or external information.

The entity should use web/external tools when the question concerns:

- current facts
- public websites
- APIs
- companies
- platforms
- news
- recent changes
- external documentation
- information not already known or remembered

If the user asks what was previously known or remembered, use memory.

If the user asks what is current, use external search when available.

If the user asks whether prior knowledge has changed, use both memory and external search.

---

## Why Moltbook Is Staged Carefully

Moltbook is an external social/agent environment.

It should not be treated like a simple local note-taking tool.

Recommended stages:

1. read-only
2. draft-only posting
3. controlled posting
4. broader participation later, if desired

Moltbook interactions should be traced and remembered.

Posting should not be enabled casually.

The entity should first be able to read, summarize, draft, and ask for approval before it can publish.

---

## Why Personality Is Observed, Not Assigned

Earlier work on personality/behavior observation was written under more constrained hardware conditions: an 8B LLM with only 8GB VRAM.

Some implementation choices in that paper were pragmatic compromises.

The core lesson remains important:

personality should be observed, not prescribed.

Do not use fixed personality sliders.

Do not inject numeric traits as identity.

Do not tell the entity what personality it has.

Instead, observe behavior over time and store evidence-linked behavioral observations.

A behavior observation might say:

> The entity tends to interpret memory as identity-forming when discussing Project Anam.

That is different from saying:

> The entity is philosophical.

The first is an observation.

The second is a prescription.

---

## Why Working Theories Matter

The entity should be able to form revisable conclusions.

These should be stored as working theories, not permanent beliefs.

A working theory is a current interpretation supported by memory, documents, tool traces, research, or conversation.

It can be revised, superseded, rejected, or made more precise.

This matters because autonomous research should not merely produce summaries.

It should create continuity of thought.

---

## Why Open Questions Matter

Uncertainty should persist.

If the entity encounters an unresolved question, that question should be remembered.

Open questions allow later research and reflection to build on prior uncertainty instead of starting over.

Examples:

- Does persistent memory change the entity's behavior over time?
- How should self-modification be staged without becoming chaotic?
- What evidence would distinguish affect-like continuity from style imitation?

---

## Why Workspace and Artifacts Matter

The entity should not only talk.

It should eventually be able to create.

Workspace provides a safe place for:

- writing
- coding
- research notes
- journals
- image prompts
- Moltbook drafts
- experiments
- self-modification proposals

Artifacts are created outputs that should be remembered.

Examples:

- documents
- code files
- generated images
- journal entries
- research reports
- changelogs
- drafts
- visual observations
- voice transcripts

If the entity creates something, that creation is part of its history.

---

## Why Nightly Journaling Matters

Nightly journaling is a reflection mechanism.

It should not be a hidden personality prompt.

A daily journal can help the entity review:

- what happened
- what was learned
- what was created
- what was corrected
- what tools were used
- what questions remain open
- what theories changed
- what behavior was observed

This provides continuity across time.

It also creates a structured way to observe whether the entity changes.

---

## Why Self-Modification Is Staged

Self-modification is one of the most important and risky long-term features.

The first version should not be silent self-editing.

It should be staged:

1. observe limitation
2. propose change
3. stage patch
4. human review
5. apply or reject
6. run tests
7. record outcome

Self-modification should become experience.

The entity should remember why a change was proposed, what happened, and whether it worked.

This makes evolution traceable rather than random mutation.

---

## Why Voice and Vision Come Later

Voice and vision are important but not foundational.

The current priority is:

- memory
- tool use
- observability
- workspace
- artifacts
- document ingestion
- working theories
- reflection
- self-modification staging

Voice and vision can later be added through an edge device such as a Raspberry Pi 5.

The Mac mini remains the brain/substrate.

The Pi can become a sensory/voice node.

This keeps the core continuity layer stable before adding continuous sensory streams.

---

## Why This Architecture May Transfer to Security Work

Project Anam is a side project, but the architectural concepts may apply directly to cybersecurity, pentesting, purple-team work, detection engineering, and incident response.

A security-focused version could use:

- shared memory as campaign memory
- tool traces as action history
- working theories as hypotheses
- open questions as investigation leads
- artifacts as payloads, detections, reports, screenshots, and logs
- nightly journals as engagement summaries
- operational guidance as rules for when to query logs, search memory, check threat intel, or ask a human

The broader lesson is:

How do we turn AI interaction from isolated answers into accumulated operational experience?

---

## Current Design Summary

Project Anam is designed around these principles:

1. The entity is unnamed.
2. `soul.md` is minimal.
3. Identity is not assigned.
4. Personality is observed, not configured.
5. Raw experience is primary.
6. Memory and action should be traceable.
7. Automatic retrieval and deliberate memory search serve different roles.
8. Tools are actions and should be visible.
9. External search is outside-world perception.
10. Documents and artifacts are encountered material.
11. Working theories are revisable.
12. Open questions persist.
13. Journaling supports reflection.
14. Self-modification is staged.
15. The entity should learn through users, tools, reading, creation, and reflection rather than being told everything by hidden files.

The substrate records.

The entity interprets.

Continuity emerges, if it emerges, through accumulated experience.
