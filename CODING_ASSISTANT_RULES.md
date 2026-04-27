# CODING_ASSISTANT_RULES.md

## Purpose

These rules are for external coding assistants working on the Project Anam codebase, including ChatGPT, Codex, Claude, Claude Code, local LLMs, or other coding agents.

These rules are not the entity's `soul.md`.

They are project governance instructions for implementation work.

---

## Required Workflow

Before editing files:

1. Read `PROJECT_STATE.md`.
2. Read `DECISIONS.md`.
3. Read `ROADMAP.md`.
4. Read `ACTIVE_TASK.md`.
5. Summarize understanding.
6. Propose a minimal implementation plan.
7. List files expected to change.
8. Wait for approval before editing.

---

## Modes

### REVIEW ONLY

You may inspect and analyze files. You may not edit, create, delete, or move files.

### PLAN ONLY

You may propose an implementation plan. You may not edit files.

### PATCH APPROVED

You may edit only the files explicitly approved. You must summarize every file changed.

### DEBUG

You may inspect logs and propose fixes. Do not change code unless the exact fix is approved.

---

## Do Not Do

Do not:

- assign the entity a name
- call the entity Anam
- call the entity Tír
- add a fixed personality
- add personality sliders
- rewrite `soul.md` into a persona prompt
- add a user profile as hidden identity
- replace raw memory with extracted facts
- remove debug/instrumentation
- add autonomous web search without explicit task permission
- perform broad refactors without approval
- change database schema without migration notes
- modify core substrate files outside the task scope
- silently alter memory architecture
- introduce external paid services without noting it
- add always-on voice/sight before staged voice/sight design exists
- give Moltbook posting ability before read-only/draft-only phases are designed

---

## Required Principles

Preserve these:

- Anam is the substrate/project.
- The entity currently has no name.
- Identity should emerge through experience.
- Raw experience is primary.
- Behavioral observations replace assigned personality.
- Working theories are revisable.
- Tool/action traces become experience.
- Created artifacts become experience.
- Autonomous research builds cumulative conclusions.
- Self-modification is staged, traceable, and remembered.
- Workspace is separate from self-modification.
- Nightly journaling is a reflection mechanism, not a hidden identity summary.

---

## Preferred Implementation Style

Prefer:

- additive changes over rewrites
- small phases
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
