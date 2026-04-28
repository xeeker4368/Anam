# AGENTS.md

## Purpose

This file gives coding agents, including Codex, Claude Code, ChatGPT, and local LLM coding tools, the required project instructions before working on Project Anam.

These instructions are for implementation work only.

This file is not the entity's `soul.md`.

---

## Required Reading Order

Before doing any work, read these files in order:

1. `PROJECT_STATE.md`
2. `DECISIONS.md`
3. `ROADMAP.md`
4. `ACTIVE_TASK.md`
5. `CODING_ASSISTANT_RULES.md`

After reading them, summarize your understanding before editing files.

---

## Default Mode

Default mode is:

```text
REVIEW ONLY
```

You may inspect files and report findings.

You may not edit, create, delete, rename, or move files until the user explicitly approves a patch.

---

## Approval Rule

Do not modify files unless the user explicitly says something like:

```text
PATCH APPROVED
```

or clearly approves a specific implementation plan.

Before editing, provide:

1. The implementation plan
2. The files you expect to modify
3. Risks or assumptions
4. Tests/checks you plan to run

---

## Core Project Facts

Preserve these facts:

- The project/substrate is called **Project Anam**.
- **Anam is not the AI entity's name.**
- The AI entity currently has no name.
- The entity should not be assigned a name by code, prompt, config, documentation, or `soul.md`.
- If the entity eventually chooses a name, it should be stored as an identity event because it happened through experience.
- The entity should not be assigned a fixed personality.
- Behavior should be observed over time, not configured as static traits.
- Raw experience is primary.
- Tool/action traces become experience.
- Created artifacts become experience.
- Working theories are revisable.
- Autonomous research should build cumulative conclusions.
- Self-modification should be staged, traceable, and remembered.
- Workspace is separate from self-modification.

---

## Legacy Naming

The repository may still contain legacy names such as:

```text
tir/
Tír
```

Do not rename packages, modules, database paths, imports, or folders from `tir` to `anam` unless the user explicitly approves a dedicated rename/refactor task.

Current meaning:

- Project Anam = current project/substrate name
- `tir/` = legacy implementation package/folder name
- Tír = historical/previous naming context
- the AI entity = unnamed

Do not treat `tir/` as evidence that the entity is named Tír.

---

## Do Not Do

Do not:

- call the entity Anam
- call the entity Tír
- assign the entity a name
- add a fixed personality
- add personality sliders
- rewrite `soul.md` into a persona prompt
- add hidden user-profile identity
- replace raw memory with extracted facts
- remove debug/instrumentation
- add autonomous web search without explicit task permission
- perform broad refactors without approval
- rename `tir/` to `anam/` without a dedicated approved task
- change database schema without migration notes
- silently alter memory architecture
- introduce external paid services without noting it
- add always-on voice/sight before staged design exists
- give Moltbook posting ability before read-only/draft-only phases are designed

---

## Preferred Implementation Style

Prefer:

- additive changes over rewrites
- small scoped patches
- explicit schemas
- migration notes
- source-linked derived artifacts
- inspectable context
- testable runtime boundaries
- rebuildable indexes
- clear tool traces
- CLI/API diagnostics before UI polish
- workspace/artifact support before advanced autonomy
- staged integrations for Moltbook, iMessage, voice, and sight

---

## Review Checklist

Before finalizing changes, answer:

1. Did this assign the entity a name?
2. Did this call the entity Anam or Tír?
3. Did this assign personality instead of observing behavior?
4. Did this preserve raw experience?
5. Are derived artifacts traceable?
6. Are tool calls recorded?
7. Are created artifacts remembered?
8. Is context construction inspectable?
9. Does this make autonomy more cumulative?
10. Does this preserve the Anam/entity distinction?
11. Does this require a migration?
12. What tests should be run?
13. Did this change core substrate behavior unnecessarily?
14. Did this add external dependencies/services that need configuration?
15. Does this preserve the difference between workspace and self-modification?
16. Did this avoid casual legacy package renaming?

---

## Recommended First Response to Any New Task

When given a task, respond first with:

```text
I will first inspect the relevant files and compare the task against PROJECT_STATE.md, DECISIONS.md, ROADMAP.md, ACTIVE_TASK.md, and CODING_ASSISTANT_RULES.md. I will not edit files until a specific patch is approved.
```

Then proceed in REVIEW ONLY mode unless the user has explicitly approved implementation.

## Changelog Requirement

For every approved patch, create a Markdown changelog entry in `changelog/`.

The entry must include:
- summary
- files changed
- behavior changed
- tests/checks run
- known limitations
- follow-up work
- Project Anam alignment check

Do not create a changelog during REVIEW ONLY or PLAN ONLY mode.
Only create a changelog when a patch has been approved and implemented.
