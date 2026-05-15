# Research Open-Loop Design

## Status

Design only. No runtime code, database schema, retrieval behavior, research behavior, journal behavior, prompts, UI, or model configuration is changed by this document.

## Purpose

Research open loops preserve unresolved research questions so Project Anam can build continuity across research without turning questions into beliefs, behavioral guidance, self-understanding, project decisions, or hard truth.

Research is an experience channel. It may produce background knowledge, sources, open questions, provisional conclusions, or no useful findings. Not every research note should create an open loop, and not every open loop should become a working theory.

## Core Concept

A research open loop is a source-linked unresolved question or investigation thread that may be revisited later.

It is not:

- a conclusion
- a belief
- an instruction
- a task assignment
- a project decision
- behavioral guidance
- self-understanding
- a working theory

Open loops should support curiosity and research continuity. They should not prescribe behavior or silently promote research findings into authority.

## Distinctions

### Research Note

A research note is one bounded research pass or continuation artifact. It records question, scope, findings, uncertainty, sources, open questions, follow-ups, suggested review items, and working notes.

It may suggest open loops, but it does not create durable records unless an explicit later workflow does so.

### Research Open Loop

A research open loop is an unresolved question or topic to revisit. It should point back to the research note, artifact, or other source that raised it.

It is a continuity marker, not a memory chunk or conclusion.

### Review Item

A review item is for operator/admin attention. It may represent a decision, contradiction, operational concern, or question that needs human judgment.

Research Open-Loop Design v1 keeps review-item creation deferred. Review items are admin/operator attention, not research curiosity.

### Working Theory / Synthesis

A working theory or synthesis is a provisional conclusion based on evidence, sources, reasoning, and prior research.

Open loops can feed future synthesis, but they do not directly become theories. Working theories need a separate design.

## Storage Approach

Use the existing `working.db` `open_loops` table for v1 implementation.

Use existing fields where possible:

- `title`
- `description`
- `status`
- `loop_type`
- `priority`
- `related_artifact_id`
- `source`
- `next_action`
- `metadata_json`

For research loops:

- `loop_type`: `unresolved_question` or `interrupted_research`
- `source`: `manual_research`
- `related_artifact_id`: source research note artifact
- `priority`: `low`, `normal`, or `high`

Use `metadata_json` for research-specific metadata first. Do not add first-class columns until scheduled/autonomous research proves which fields need indexed filtering.

Do not index open loops into ChromaDB by default in v1. Open loops are control-plane research continuity markers, not normal retrieved memory.

## Recommended Metadata

```json
{
  "generation_method": "research_open_loop_v1",
  "source_type": "research",
  "source_research_version": "manual_research_v1",
  "source_research_title": "...",
  "source_research_date": "YYYY-MM-DD",
  "source_research_path": "research/...",
  "question": "...",
  "reason_it_matters": "...",
  "provisional": true,
  "daily_iteration_limit": 1,
  "daily_iteration_count": 0,
  "daily_iteration_local_date": null,
  "global_daily_cap_class": "research",
  "last_researched_at": null,
  "ready_for_synthesis": false,
  "diminishing_returns_note": null
}
```

`daily_iteration_limit` may default to `1` in the first implementation and tests. It should become configurable later and may likely become `2` or `3` for deeper research once scheduled research behavior exists.

## Creation Flow

Research open-loop creation should be explicit and preview-first.

Recommended flow:

1. Generate/write research note.
2. Optionally register/index the research artifact.
3. Generate candidate open loops from `Open Questions` and `Possible Follow-Ups`.
4. Show dry-run preview.
5. Create records only with an explicit flag.

Durable creation should require a stable source artifact. Preview may be possible from a just-generated draft, but record creation should source-link to a written/registered artifact.

If a research note has no useful open loops, the preview should say so and create nothing.

## Future Command Shape

Create during research run:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --question "..." \
  --scope "..." \
  --write \
  --register-artifact \
  --create-open-loops
```

Preview during research run:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --question "..." \
  --scope "..." \
  --preview-open-loops
```

Standalone preview for existing registered research notes:

```bash
.pyanam/bin/python -m tir.admin research-open-loops-preview --artifact-id <id>
```

Standalone creation for existing registered research notes:

```bash
.pyanam/bin/python -m tir.admin research-open-loops-create --artifact-id <id>
```

The first runtime implementation should prefer standalone preview/create commands or a clearly separated helper so existing research artifacts can be processed without regenerating notes.

## Iteration Limits

Use per-loop daily iteration limits plus a later global daily research cap.

Per-loop model:

- each loop has `daily_iteration_limit`
- each loop tracks `daily_iteration_count`
- each loop tracks `daily_iteration_local_date`
- reset is based on local day

Daily limit reached should not close the loop.

Daily limit reached may trigger a synthesis check if repeated research stops producing new useful material.

Later autonomous/scheduled research should also respect a global daily research cap. The cap should apply across research loops so the system does not spend unbounded time chasing unresolved questions.

## Status Model

Existing `open_loops` statuses are enough for first implementation:

- `open`
- `in_progress`
- `blocked`
- `closed`
- `archived`

Research-specific states can live in `metadata_json` first:

- `researching`
- `daily_limit_reached`
- `ready_for_synthesis`
- `synthesized`
- `paused`

If these states become central to scheduler queries, a later migration can promote them to first-class status values or fields.

## Diminishing Returns And Synthesis Readiness

Do not auto-close loops for diminishing returns.

Mark a loop as ready for synthesis when:

- repeated research yields little new information
- uncertainty stabilizes
- enough source material exists to compare or synthesize
- next action becomes compare/synthesize rather than gather more
- the daily limit is reached repeatedly without meaningful progress

Use:

- `metadata.ready_for_synthesis=true`
- `metadata.diminishing_returns_note`
- `next_action` updated to a synthesis-oriented action

This is still not a working theory. It is only a signal that synthesis may be useful.

## Duplicate Prevention

Before creating a research open loop, compare against existing active/open loops using:

- same `related_artifact_id`
- same normalized title/question
- same `metadata.generation_method`
- optionally same `metadata.source_research_path`

Broader normalized question matching may be useful, but it should be conservative and previewed. Do not fuzzy-merge or suppress candidates without showing the operator what was skipped and why.

## Retrieval And Source Framing

Open loops should not be normal retrieved memories in v1.

When later included in research planning, frame them as:

```text
[Open research loop — provisional question to revisit]

This is an unresolved research question, not a conclusion, instruction, project decision, behavioral guidance, or self-understanding.
```

Open loops may inform what to investigate next. They should not be used as factual claims.

## Future Origins

Research-note-based loops should be implemented first.

The model should preserve future support for loops originating from:

- conversations
- Moltbook
- artifacts
- journals
- tool failures
- image/screenshot context
- prior open loops
- prior syntheses or working theories

Each future origin should preserve source metadata and use explicit creation rules.

## Relationship To Scheduled Or Autonomous Research

Open loops are the queue substrate for later bounded research.

A future scheduler should:

- select only eligible open research loops
- respect per-loop daily limits
- respect global daily caps
- check `last_researched_at`
- prefer loops with clear `next_action`
- stop when diminishing returns are detected
- produce research notes, not silent memory updates

Autonomous research should update or continue research artifacts and loop metadata. It should not silently convert unresolved questions into truth.

## Relationship To Working Theories

Open loops can feed synthesis, but they do not directly become working theories.

Future flow:

```text
research notes + open loops
→ synthesis candidate
→ working theory/conclusion record
→ later revision/supersession
```

Working theories need separate design for evidence, confidence, contradiction handling, retrieval framing, revision, and supersession.

## Deferred

- Runtime implementation.
- DB schema changes.
- Chroma indexing for open loops.
- Automatic open-loop creation.
- Review-item creation.
- Working-theory/synthesis records.
- Web source collection.
- Scheduled/autonomous research.
- Title/search continuation.
- UI.
- Retrieval ranking changes.
- Any promotion to truth, behavioral guidance, self-understanding, or project decisions.

## Risks

- Open loops can become task assignments instead of questions.
- Too many open loops can create noise.
- Automatic creation can preserve low-value questions.
- Open loops can be mistaken for beliefs if retrieved without framing.
- Duplicate prevention can suppress useful related questions if matching is too aggressive.
- Daily caps can hide important work if not visible in previews and debug output.

## Implementation Phases

1. Design doc only.
2. Add research open-loop candidate planner/parser with dry-run preview.
3. Add standalone preview command for registered research artifacts.
4. Add standalone create command for registered research artifacts.
5. Add `research-run --preview-open-loops`.
6. Add `research-run --write --register-artifact --create-open-loops`.
7. Add duplicate prevention and skipped-candidate reporting.
8. Add iteration metadata and local-day daily limit handling.
9. Later: scheduler uses open loops.
10. Later: synthesis/working theory path.
