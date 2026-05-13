# ACTIVE_TASK.md

## Current Recommended Task

Research Open-Loop / Review-Item Design v1.

## Task Goal

Design how manual research notes and continuations should surface open questions, follow-ups, and suggested review items as explicit future records without creating those records automatically.

This is a design-only next step. It should not add runtime code, database schema, web source collection, autonomous research, scheduler behavior, automatic open-loop/review-item creation, or promotion paths.

## Current Checkpoint

Recent completed foundation work:

- Behavioral guidance proposal model/API/UI exists.
- AI-generated behavioral guidance proposal review paths exist.
- Approved addition guidance can be applied to `BEHAVIORAL_GUIDANCE.md`.
- Active behavioral guidance is loaded into runtime context.
- Reflection journals can be written, registered, indexed, and retrieved.
- Operational reflection review exists as a manual admin command.
- Prompt audit and database schema documentation exist.
- Runtime configuration foundation exists with TOML/env overrides and Ollama model options.
- `SELF_UNDERSTANDING.md` has concept design only; no implementation exists.
- Guidance scoping and guidance removal/revision mechanics have design docs only.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Runtime v1 is complete for the manual CLI path. `research-run` can continue from a registered research artifact with `--continue-artifact` or from a constrained Markdown file under `workspace/research/` with `--continue-file`. Continuation creates a new provisional research note, preserves lineage, frames the prior note as provisional context, and never overwrites or mutates the prior note.

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, open loops, or review items automatically.

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

## Design Constraints

- Research conclusions are provisional working notes.
- Research artifacts need a clear purpose and consumption path.
- Research suggestions may become candidate records only through explicit, reviewable operator action.
- Future record creation must preserve source lineage to the originating research note or continuation.
- The design must preserve the Anam/entity distinction.
- The design must not assign the entity a name or personality.

## Files/Subsystems To Inspect First

- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `tir/research/manual.py`
- `tir/open_loops/service.py`
- review queue service/API patterns
- `tir/admin.py`
- `tests/test_manual_research.py`
- `tests/test_open_loops.py`
- `tests/test_review_queue.py`

## New Chat Kickoff Instruction

Use this in the new design chat:

```text
You are helping me continue Project Anam.

Before making suggestions or writing code, read the attached project baseline documents in this order:

1. PROJECT_STATE.md
2. DECISIONS.md
3. ROADMAP.md
4. ACTIVE_TASK.md
5. CODING_ASSISTANT_RULES.md

After reading, respond with:
- your understanding of Project Anam in 8 bullets
- the current active task
- the files/subsystems you need to inspect first
- any assumptions or risks
- no code changes yet
```

## Success Criteria For The Next Design Patch

The Research Open-Loop / Review-Item Design v1 patch should prove:

- Research open questions and suggested review items remain provisional until explicitly written.
- Future record creation has dry-run preview requirements.
- Source lineage and duplicate-prevention rules are specified.
- Open-loop and review-item workflows remain separate from behavioral guidance and project decisions.
- No runtime, schema, scheduler, guidance, self-understanding, operational guidance, soul, or project-decision files are mutated except approved documentation.
