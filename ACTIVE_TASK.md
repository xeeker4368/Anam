# ACTIVE_TASK.md

## Current Recommended Task

Research Open-Loop / Review-Item Design v1.

## Task Goal

Design how manual research note `Open Questions`, `Possible Follow-Ups`, and `Suggested Review Items` sections may later create durable open-loop or review-item records through explicit operator action.

This is a design task. It should not add runtime code, database schema changes, web source collection, autonomous research, scheduler behavior, automatic record creation, retrieval ranking changes, or promotion of research into truth, behavioral guidance, self-understanding, or project decisions.

## Current Checkpoint

Recent completed foundation and course-correction work:

- Behavioral guidance proposal model/API/UI was built and tested pre-live.
- AI-generated behavioral guidance proposal review paths exist.
- Approved addition guidance apply-to-file workflow was tested pre-live; apply is now dormant before go-live.
- Behavioral guidance runtime loading is dormant before go-live.
- `BEHAVIORAL_GUIDANCE.md` is a dormant placeholder and contains no active `- Guidance:` lines.
- Reflection journals no longer receive active behavioral guidance as entity context.
- Retrieved context uses neutral source framing: `Retrieved context follows. Each item is labeled by source type.`
- `OPERATIONAL_GUIDANCE.md` has been compressed to source/tool/action safety.
- Journal and research prompts now allow quiet days, no useful findings, no open questions, no follow-ups, and no suggested review items where honest.
- `memory_search` and real-time tool freshness wording now use indexed prior-record/source framing instead of broad self-memory framing.
- `soul.md` was reviewed for minimality before go-live and was not changed.
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
- External Review Checkpoint v1 exists as documentation/review prep.
- `SELF_UNDERSTANDING.md` has concept design only; no implementation exists.
- Guidance scoping and guidance removal/revision mechanics have design docs only.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Runtime v1 is complete for the manual CLI path. `research-run` can continue from a registered research artifact with `--continue-artifact` or from a constrained Markdown file under `workspace/research/` with `--continue-file`. Continuation creates a new provisional research note, preserves lineage, frames the prior note as provisional context, and never overwrites or mutates the prior note.

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, open loops, or review items automatically.

## Current Design Scope

Research Open-Loop / Review-Item Design v1 should answer:

- How research note `Open Questions`, `Possible Follow-Ups`, and `Suggested Review Items` sections should be interpreted.
- Whether future record creation should use explicit flags such as `--create-open-loops` and `--create-review-items`.
- What dry-run preview should show before records are created.
- How duplicate prevention should work.
- What source metadata and lineage should be attached to any future records.
- How to keep research suggestions provisional.
- How to prevent research outputs from becoming behavioral guidance, project decisions, truth, or self-understanding.
- How created records should remain traceable to the originating research note or continuation.
- What should remain deferred.

## Explicitly Deferred

- Runtime implementation for open-loop/review-item creation.
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
- Reintroducing behavioral guidance runtime loading.
- Implementing household multi-user support.
- Media/image artifact implementation.
- Moltbook behavior changes.
- Canary runtime harness.
- UI redesign.
- Go-live DB wipe/reset.

## Design Constraints

- Project Anam is the substrate/project, not the entity name.
- The AI entity currently has no name.
- The system must not assign a fixed personality.
- Drift is not inherently bad.
- Healthy emergent drift must be distinguished from source confusion, accidental authority, over-prescription, self-reinforcing memory, or brittle rules.
- Research conclusions are provisional working notes.
- Behavioral guidance runtime loading is dormant before go-live because it was judged too prescriptive for the emergence goal.
- Pre-go-live household multi-user support is required but not implemented here: Lyle/admin user, wife/trusted household user, `source_user_id` preservation where applicable, and admin-only operations remaining admin-only.
- Research artifacts need a clear purpose and consumption path.
- Research suggestions may become candidate records only through explicit, reviewable operator action.
- Future record creation must preserve source lineage to the originating research note or continuation.
- The design must preserve the Anam/entity distinction.

## Files/Subsystems To Inspect First

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `tir/research/manual.py`
- existing open-loop and review queue services/tests

## Success Criteria

Research Open-Loop / Review-Item Design v1 should produce a concrete future implementation plan that:

- keeps research suggestions provisional
- requires explicit operator flags before creating records
- includes dry-run previews
- prevents obvious duplicates
- preserves source metadata and lineage
- avoids behavioral guidance, project decision, self-understanding, or truth promotion
- identifies what should remain deferred
