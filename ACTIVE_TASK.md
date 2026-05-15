# ACTIVE_TASK.md

## Current Recommended Task

Research Open-Loop Runtime v1.

## Task Goal

Implement explicit, preview-first research open-loop creation from registered manual research artifacts.

Open loops should preserve unresolved research questions and follow-up topics without turning research into truth, behavioral guidance, self-understanding, project decisions, review items, or working theories.

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
- Single-model global temperature calibration is complete.
- External Review Checkpoint v1 exists as documentation/review prep.
- `SELF_UNDERSTANDING.md` has concept design only; no implementation exists.
- Guidance scoping and guidance removal/revision mechanics have design docs only.
- Manual Research Foundation is complete for the first bounded CLI path.
- Research Continuation Runtime v1 is complete for the manual CLI path.
- Research Open-Loop Design v1 is complete in `docs/RESEARCH_OPEN_LOOP_DESIGN.md`.

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, open loops, review items, or working theories automatically.

## Current Implementation Scope

Research Open-Loop Runtime v1 should likely implement:

- candidate planning/parsing from registered research artifacts
- dry-run preview for candidates
- explicit creation command for approved candidates
- source linkage to the originating research artifact
- metadata from `docs/RESEARCH_OPEN_LOOP_DESIGN.md`
- duplicate prevention for obvious duplicates
- skipped-candidate reporting
- no Chroma indexing of open loops by default

Prefer standalone commands first so existing research artifacts can be processed without regenerating notes:

```bash
.pyanam/bin/python -m tir.admin research-open-loops-preview --artifact-id <id>
.pyanam/bin/python -m tir.admin research-open-loops-create --artifact-id <id>
```

`research-run --preview-open-loops` and `research-run --write --register-artifact --create-open-loops` may follow if they remain small and preserve existing research-run behavior.

## Explicitly Deferred

- Review-item creation.
- Working-theory/synthesis records.
- DB schema changes unless implementation proves existing `metadata_json` is insufficient.
- Chroma indexing for open loops.
- Web source collection.
- Autonomous research loops.
- Scheduler/background research.
- Automatic open-loop creation without explicit operator action.
- Automatic review-item creation.
- Promotion to truth, behavioral guidance, self-understanding, or project decisions.
- Value-density scoring.
- Retrieval ranking changes.
- Title/search research continuation.
- Changes to `BEHAVIORAL_GUIDANCE.md`, `SELF_UNDERSTANDING.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
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
- Research conclusions are provisional working notes.
- Open loops are unresolved questions, not conclusions or instructions.
- Behavioral guidance runtime loading must remain dormant.
- Research artifacts need a clear purpose and consumption path.
- Future record creation must preserve source lineage to the originating research note or continuation.
- The design must preserve the Anam/entity distinction.

## Files/Subsystems To Inspect First

- `docs/RESEARCH_OPEN_LOOP_DESIGN.md`
- `docs/MANUAL_RESEARCH_CYCLE_DESIGN.md`
- `docs/RESEARCH_CONTINUATION_DESIGN.md`
- `tir/research/manual.py`
- `tir/open_loops/service.py`
- `tir/admin.py`
- `tests/test_manual_research.py`
- `tests/test_open_loops.py`
- `tests/test_admin.py`

## Success Criteria

Research Open-Loop Runtime v1 should:

- preview candidates without writing
- create records only through explicit operator action
- require a stable source artifact for durable creation
- preserve research source lineage
- keep candidates provisional
- avoid review-item creation
- avoid Chroma indexing by default
- avoid DB schema changes unless clearly necessary
- keep research notes from becoming truth, guidance, self-understanding, or project decisions
