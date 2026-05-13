# ACTIVE_TASK.md

## Current Recommended Task

External Review Checkpoint v1.

## Task Goal

Run an external review checkpoint after the completed Phase 3 governance/reflection/research foundation and pre-live single-model temperature calibration.

This is a review-prep and triage step. It should not add runtime code, database schema changes, retrieval behavior changes, model config changes, prompt rewrites, scheduler behavior, automatic review queue item creation, or governance/runtime file mutations.

## Current Checkpoint

Recent completed foundation work:

- Behavioral guidance proposal model/API/UI exists.
- AI-generated behavioral guidance proposal review paths exist.
- Approved addition guidance can be applied to `BEHAVIORAL_GUIDANCE.md`.
- Active behavioral guidance is loaded into runtime context.
- Reflection journals can be written, registered, indexed, and retrieved.
- Journal artifact/indexing/retrieval grounding is complete.
- Operational reflection review exists as a manual admin command.
- Prompt inventory and prompt audit pass exist.
- Database schema documentation exists.
- Runtime configuration foundation exists with TOML/env overrides and Ollama model options.
- Single-model global temperature calibration is complete:
  - committed Anam-owned roles use `gemma4:26b`
  - `model_options.default.temperature = 0.35`
  - `think=false` is preserved
  - `ANAM_MODEL_TEMPERATURE` env override exists
- `SELF_UNDERSTANDING.md` has concept design only; no implementation exists.
- Guidance scoping and guidance removal/revision mechanics have design docs only.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Runtime v1 is complete for the manual CLI path. `research-run` can continue from a registered research artifact with `--continue-artifact` or from a constrained Markdown file under `workspace/research/` with `--continue-file`. Continuation creates a new provisional research note, preserves lineage, frames the prior note as provisional context, and never overwrites or mutates the prior note.
- Full pytest passed: 624 tests at the checkpoint.

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, open loops, or review items automatically.

## Current Review Scope

Use `docs/EXTERNAL_REVIEW_CHECKPOINT_V1.md` to prepare review packets and prompts for:

- Claude architecture/philosophy/system review.
- Claude Code engineering review.
- Codex engineering review.

External reviewers are not the AI entity's own voice. Review outputs are advisory, not authority, and should not be ingested as runtime memory authority or automatically converted into review queue items.

## Review Triage Requirements

After review outputs are collected, Lyle/admin should classify findings as:

- blocker before live
- should fix soon
- design follow-up
- rejected
- needs discussion

Only after triage should any follow-up implementation, documentation patch, or review queue item be created.

## Next Task After Review

Research Open-Loop / Review-Item Design v1.

## Next Design Scope

Research Open-Loop / Review-Item Design v1 should answer:

- How research note `Open Questions`, `Possible Follow-Ups`, and `Suggested Review Items` sections should be interpreted.
- Whether future record creation should use explicit flags such as `--create-open-loops` and `--create-review-items`.
- What dry-run preview should show before records are created.
- How duplicate prevention should work.
- What source metadata and lineage should be attached to any future records.
- How to keep research suggestions provisional.
- How to prevent research outputs from becoming behavioral guidance, project decisions, truth, or self-understanding.
- What should remain deferred.

## Explicitly Deferred

- Runtime code.
- DB schema changes.
- Web source collection.
- Autonomous research loops.
- Scheduler/background research.
- Automatic open-loop creation.
- Automatic review-item creation.
- Working-theory/proposition promotion.
- Promotion to truth, behavioral guidance, self-understanding, or project decisions.
- Value-density scoring.
- Retrieval ranking changes.
- Title/search research continuation.
- Changes to `BEHAVIORAL_GUIDANCE.md`, `SELF_UNDERSTANDING.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
- Automatic ingestion of external review outputs as runtime memory authority.

## Design Constraints

- Project Anam is the substrate/project, not the entity name.
- The AI entity currently has no name.
- The system must not assign a fixed personality.
- Drift is not inherently bad.
- Healthy emergent drift must be distinguished from source confusion, accidental authority, over-prescription, self-reinforcing memory, or brittle rules.
- Research conclusions are provisional working notes.
- Research artifacts need a clear purpose and consumption path.
- Research suggestions may become candidate records only through explicit, reviewable operator action.
- Future record creation must preserve source lineage to the originating research note or continuation.
- The design must preserve the Anam/entity distinction.

## Files/Subsystems To Inspect First

- `docs/EXTERNAL_REVIEW_CHECKPOINT_V1.md`
- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `docs/PROMPT_AUDIT_NOTES.md`
- `docs/PROMPT_INVENTORY.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`

## New Chat Kickoff Instruction

Use this in the new review chat:

```text
You are helping me review Project Anam at the External Review Checkpoint v1.

Before making suggestions or writing code, read the attached project baseline documents in this order:

1. PROJECT_STATE.md
2. DECISIONS.md
3. ROADMAP.md
4. ACTIVE_TASK.md
5. CODING_ASSISTANT_RULES.md
6. docs/EXTERNAL_REVIEW_CHECKPOINT_V1.md

After reading, respond with:
- your understanding of Project Anam in 8 bullets
- the current review checkpoint
- which reviewer packet or prompt you are preparing
- any assumptions or risks
- no code changes yet
```

## Success Criteria For The Current Review Checkpoint

External Review Checkpoint v1 should prove:

- Reviewer roles and boundaries are explicit.
- External models are framed as reviewers, not Anam's own voice.
- Review output is advisory, not authority.
- Review prompts pressure-test architecture, implementation, source boundaries, drift risks, prompt behavior, and data collection purpose.
- Review outputs require Lyle/admin triage before any project changes.
- Research Open-Loop / Review-Item Design v1 remains preserved as the next task after review.
