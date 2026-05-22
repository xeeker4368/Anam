# ACTIVE_TASK.md

## Current Recommended Task

Go-Live Reset Runbook v1.

This is a design/runbook task for the future destructive go-live wipe/reset process. It must not implement reset behavior or delete current runtime state.

## Task Goal

Document a safe future go-live reset procedure:

- require fresh backup and backup-restore verification
- define what pre-live runtime state should be wiped
- define what project/config/governance/user/schema state must be preserved
- require explicit confirmation for any future destructive command
- keep current pre-live data available for testing until final launch preparation

## Current Checkpoint

Recent completed foundation and course-correction work:

- Behavioral guidance runtime loading is dormant before go-live.
- `BEHAVIORAL_GUIDANCE.md` is a dormant placeholder and contains no active `- Guidance:` lines.
- Reflection journals no longer receive active behavioral guidance as entity context.
- Retrieved context uses neutral source framing: `Retrieved context follows. Each item is labeled by source type.`
- `OPERATIONAL_GUIDANCE.md` has been compressed to source/tool/action safety.
- Journal and research prompts now allow quiet days, no useful findings, no open questions, no follow-ups, and no suggested review items where honest.
- `memory_search` and real-time tool freshness wording now use indexed prior-record/source framing instead of broad self-memory framing.
- `soul.md` was reviewed for minimality before go-live and was not changed.
- Reflection journals can be written, registered, indexed, and retrieved.
- Operational reflection review exists as a manual admin command.
- Runtime configuration foundation exists with TOML/env overrides and Ollama model options.
- Single-model global temperature calibration is complete.
- External Review Checkpoint v1 exists as documentation/review prep.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Runtime v1 is complete for the manual CLI path.
- Research Open-Loop Runtime v1 is complete for the first standalone manual path.
- Bounded / Scheduled Research Design v1 exists in `docs/BOUNDED_SCHEDULED_RESEARCH_DESIGN.md`.
- Manual Bounded Open-Loop Research Planner v1 is complete.
- Manual Bounded Open-Loop Research Run v1 is complete.
- Moltbook Source Collection Design v1 exists in `docs/MOLTBOOK_SOURCE_COLLECTION_DESIGN.md`.
- Moltbook Source Preview Runtime v1 is complete.
- Bounded Moltbook source trace support is complete.
- Research Open-Loop Run-Next v1 is complete.
- Web Source Collection Design v1 exists in `docs/WEB_SOURCE_COLLECTION_DESIGN.md`.
- Pre-Go-Live Roadmap Correction clarified the image/avatar split and bounded scheduler candidate status.
- Experiment Hypothesis / Observation Criteria v1 exists in `docs/EXPERIMENT_HYPOTHESIS_AND_OBSERVATION_CRITERIA.md`.
- Trusted Household User Mode v1 exists in `docs/TRUSTED_HOUSEHOLD_USER_MODE.md`.
- Backup / Restore Verification v1 is complete and committed.

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, review items, or working theories automatically.

## Current Documentation Scope

The current go-live reset runbook patch should:

- add `docs/GO_LIVE_RESET_RUNBOOK.md`
- update `ROADMAP.md` narrowly with the runbook checkpoint
- define wipe/preserve lists, guardrails, command shape, and verification checklist
- avoid implementing any reset behavior
- add a changelog entry

Pre-go-live candidates now include Image / Media Capability Foundation v1 and a tightly bounded scheduler/nightly tick v1, subject to separate approved implementation patches.

## Explicitly Deferred

- Avatar/self-representation creation before go-live.
- Expanded autonomy/background research.
- Broad autonomous web crawling.
- Working-theory/synthesis records.
- Review-item creation.
- Automatic open-loop creation without explicit operator action.
- Automatic review-item creation.
- DB schema changes unless a separate approved implementation proves existing metadata fields are insufficient.
- Chroma indexing changes.
- Promotion to truth, behavioral guidance, self-understanding, or project decisions.
- Value-density scoring.
- Retrieval ranking changes.
- Changes to `BEHAVIORAL_GUIDANCE.md`, `SELF_UNDERSTANDING.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
- Implementing household multi-user support.
- Real login/session authentication.
- Implementing image generation or scheduler runtime behavior.
- Moltbook behavior changes beyond separately approved read-only/source-trace work.
- Canary runtime harness.
- UI redesign.
- Go-live DB wipe/reset.
- Real restore into active runtime state outside the existing explicit `restore --force` path.
  Current pre-live runtime data remains useful test data until final launch preparation.

## Design Constraints

- Project Anam is the substrate/project, not the entity name.
- The AI entity currently has no name.
- The system must not assign a fixed personality.
- Drift is not inherently bad.
- Research conclusions are provisional working notes.
- Open loops are unresolved questions, not conclusions or instructions.
- Behavioral guidance runtime loading must remain dormant.
- Research artifacts need a clear purpose and consumption path.
- Live/external source material is context, not factual authority.
- Source text must be separated from the entity's interpretation.
- Absence of external results is not proof of absence.
- No durable research state should update silently without an artifact once execution exists.
- Future record creation must preserve source lineage.
- The design must preserve the Project Anam/entity distinction.

## Files/Subsystems To Inspect First

- `PROJECT_STATE.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `CODING_ASSISTANT_RULES.md`
- `changelog/`

## Success Criteria

This go-live reset runbook patch should:

- document the future reset operator procedure
- define what to wipe and what to preserve
- require backup and backup-restore verification before future destructive reset
- include future command shape and post-reset verification checklist
- avoid implementing reset command, DB mutation, Chroma deletion, or workspace deletion
- avoid runtime code, prompts, guidance, `soul.md`, model config, auth, UI, research, Moltbook, or web behavior changes
- preserve the Project Anam/entity distinction
