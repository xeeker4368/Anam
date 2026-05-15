# ACTIVE_TASK.md

## Current Recommended Task

Manual Bounded Open-Loop Research Planner v1.

## Task Goal

Design and implement the smallest safe planner for selecting one eligible research open loop for a bounded manual research pass.

The planner should make open-loop research selection inspectable before any scheduler or autonomous loop exists.

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

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, review items, or working theories automatically.

## Current Implementation Scope

Manual Bounded Open-Loop Research Planner v1 should likely implement:

- eligibility checks for existing research open loops
- deterministic selection of the next eligible loop
- dry-run preview output
- per-loop daily limit evaluation from `metadata_json`
- local-day reset planning or preview behavior
- clear ineligible-loop reasons
- no research execution yet unless explicitly approved in a later runtime patch
- no scheduler/background behavior

Likely command:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-next --dry-run
```

The next runtime patch may add:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-run --open-loop-id <id> --dry-run
.pyanam/bin/python -m tir.admin research-open-loop-run-next --dry-run
```

## Explicitly Deferred

- True scheduler/background research.
- Web source collection.
- Moltbook/live-source research collection.
- Working-theory/synthesis records.
- Review-item creation.
- Automatic open-loop creation without explicit operator action.
- Automatic review-item creation.
- DB schema changes unless implementation proves existing `metadata_json` is insufficient.
- Chroma indexing for open loops.
- Promotion to truth, behavioral guidance, self-understanding, or project decisions.
- Value-density scoring.
- Retrieval ranking changes.
- Title/search research continuation.
- Changes to `BEHAVIORAL_GUIDANCE.md`, `SELF_UNDERSTANDING.md`, `OPERATIONAL_GUIDANCE.md`, or `soul.md`.
- Implementing household multi-user support.
- Media/image artifact implementation.
- Moltbook behavior changes beyond separately approved read-only verification/source-capture work.
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
- No durable research state should update silently without an artifact once execution exists.
- Future record creation must preserve source lineage.
- The design must preserve the Anam/entity distinction.

## Files/Subsystems To Inspect First

- `docs/BOUNDED_SCHEDULED_RESEARCH_DESIGN.md`
- `docs/RESEARCH_OPEN_LOOP_DESIGN.md`
- `tir/research/open_loops.py`
- `tir/open_loops/service.py`
- `tir/research/manual.py`
- `tir/admin.py`
- `tests/test_research_open_loops.py`
- `tests/test_open_loops.py`
- `tests/test_admin.py`

## Success Criteria

Manual Bounded Open-Loop Research Planner v1 should:

- preview the next eligible research loop without writing
- expose why loops are eligible or ineligible
- respect per-loop daily metadata in planning
- keep selection deterministic and inspectable
- avoid running research unless separately approved
- avoid scheduler/background behavior
- avoid DB schema changes unless clearly necessary
- avoid Chroma indexing changes
- avoid review-item creation
- avoid promotion to truth, guidance, self-understanding, working theories, or project decisions
