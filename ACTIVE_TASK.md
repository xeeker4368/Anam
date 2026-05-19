# ACTIVE_TASK.md

## Current Recommended Task

Moltbook Source Preview Runtime v1.

## Task Goal

Implement the smallest safe preview command for bounded, read-only Moltbook source collection.

The preview should make Moltbook source collection inspectable before bounded research uses live Moltbook context.

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

Research remains provisional and does not become truth, guidance, self-understanding, project decisions, review items, or working theories automatically.

## Current Implementation Scope

Moltbook Source Preview Runtime v1 should likely implement:

- deterministic Moltbook source preview for an explicit query/feed/submolt/post selection
- compact source records with source ids, titles, authors, URLs, timestamps, excerpts, and provenance
- read-only enforcement through existing Moltbook tools
- source limits from `docs/MOLTBOOK_SOURCE_COLLECTION_DESIGN.md`
- clear no-result output that does not imply proof of absence
- no research note generation
- no source trace writes unless explicitly approved by the runtime patch scope
- no scheduler/background behavior

Likely command:

```bash
.pyanam/bin/python -m tir.admin moltbook-source-preview --query "agent autonomy before go-live" --limit 10
```

The next runtime patch may add:

```bash
.pyanam/bin/python -m tir.admin moltbook-source-preview --query "agent autonomy before go-live" --read-post-id <post_id> --comments-limit 5
```

## Explicitly Deferred

- True scheduler/background research.
- Web source collection.
- Moltbook use inside bounded research.
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
- Moltbook behavior changes beyond separately approved read-only source preview/capture work.
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
- Moltbook source material is live external context, not factual authority.
- Moltbook source text must be separated from Anam's interpretation.
- Absence of Moltbook results is not proof of absence.
- No durable research state should update silently without an artifact once execution exists.
- Future record creation must preserve source lineage.
- The design must preserve the Anam/entity distinction.

## Files/Subsystems To Inspect First

- `docs/MOLTBOOK_SOURCE_COLLECTION_DESIGN.md`
- `skills/active/moltbook/skill.yaml`
- `skills/active/moltbook/moltbook.py`
- `tir/tools/registry.py`
- `tir/tools/http_declarative.py`
- `tir/admin.py`
- `tests/test_moltbook_declarative_skill.py`
- `tests/test_moltbook_search_semantics.py`
- `tests/test_admin.py`

## Success Criteria

Moltbook Source Preview Runtime v1 should:

- preview compact Moltbook sources without writing research notes
- require an explicit query/feed/submolt/post selection
- enforce read-only Moltbook use
- preserve provenance for each compact source record
- keep source text separate from interpretation
- report no usable results without treating absence as proof
- avoid Chroma indexing changes
- avoid bounded research integration unless separately approved
- avoid scheduler/background behavior
- avoid review-item creation
- avoid promotion to truth, guidance, self-understanding, working theories, or project decisions
