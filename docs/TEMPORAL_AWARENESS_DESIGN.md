# Temporal Awareness Design

## Status

Design only. No runtime code, prompts, tests, retrieval scoring, database schema, Chroma behavior, research generation, Moltbook or web behavior, guidance files, `soul.md`, model configuration, or UI behavior are changed by this document.

Temporal awareness is a proposed context-framing layer. It should help Project Anam represent memory as time-structured experience instead of flat retrieved text.

## Purpose

Project Anam already stores timestamps across conversations, messages, artifacts, research notes, journals, open loops, source traces, and operational records. Those timestamps are useful, but current retrieved context mostly answers "what past content is relevant?" rather than:

- when the content happened relative to now
- whether it belongs to pre-live test data or live continuity
- whether it is recent, old, stale, provisional, revised, or superseded
- whether the source was retrieved recently or a long time ago
- whether later evidence has changed the interpretation
- what project phase produced the record

Temporal awareness should make time visible as context without turning time into hidden authority or hidden ranking.

## Boundaries

- Temporal awareness is not a personality assignment.
- Temporal awareness is not proof of human-like experience.
- Temporal labels are metadata and context aids, not truth.
- Temporal labels should help interpretation, not force conclusions.
- Temporal framing must not delete, hide, or downrank old records in v1.
- Raw timestamps remain the source of record.
- Pre-live material should be clearly distinguishable from live continuity after go-live.
- Temporal labels should be inspectable and debug-visible.

## Current Temporal Metadata Inventory

### Conversations

- `started_at`
- `ended_at`

These are runtime-created timestamps and are reliable for conversation session timing.

### Messages

- `timestamp`

Message timestamps are runtime-created and reliable for the order and time of raw conversation experience.

### Chunks And FTS

- `created_at`

Chunk timestamps indicate when a memory chunk was written or rewritten, not necessarily when the underlying experience originally occurred. Conversation chunk text may include per-message timestamps.

### Artifacts

- `created_at`
- `updated_at`

Artifact timestamps are reliable for artifact record creation and status updates. They may not represent when the artifact content was first conceived or when an external source was originally published.

### Open Loops

- `created_at`
- `updated_at`
- `closed_at`

Open-loop timestamps are reliable for control-plane lifecycle. Bounded research also stores per-loop research timing in metadata.

### Bounded Research Metadata

- `last_researched_at`
- `daily_iteration_local_date`

These indicate when a loop was last successfully researched and which local date was used for per-loop iteration limits.

### Research Notes

- Markdown header `Created`
- artifact metadata `research_date`

These indicate when the research note was generated/written. They do not make the findings current or true.

### Reflection Journals

- `journal_date`
- artifact/indexing `created_at`

`journal_date` represents the day being reflected on. Artifact/indexing `created_at` represents when the journal artifact or memory chunks were written.

### Source Traces

- `retrieved_at`

This is the key timestamp for external source collection. It records when Project Anam collected or attempted to collect source material.

### External Source Timestamps

Examples:

- Moltbook post `created_at`
- future web page `published_at`
- future web page `last_modified`

These are less authoritative than runtime-created timestamps because they come from external systems or extraction heuristics. They should be preserved, but labeled as source-provided metadata.

### Backup And Reset Records

Backup manifests and future go-live reset audits contain timestamps that can help define project phase boundaries, especially the future go-live marker.

## Core Model

Temporal awareness should be computed from existing timestamps where possible.

Raw timestamps remain the source of record. Temporal labels are derived context, not separate truth.

V1 should compute labels at retrieval or prompt-assembly time rather than storing fixed labels at indexing time. This keeps labels accurate relative to "now" and avoids writing stale derived metadata into memory.

Recommended principles:

- compute from raw timestamps
- keep raw timestamp visible or debug-visible
- keep labels deterministic
- keep labels short
- do not affect ranking in v1
- do not hide old records
- do not delete old records
- expose labels in debug output

## Proposed Temporal Fields

Future temporal framing may expose a compact object like:

```json
{
  "event_time": "2026-05-22T14:00:00+00:00",
  "event_time_source": "artifact_created_at",
  "relative_age": "3 days ago",
  "age_band": "2_7_days",
  "project_phase": "pre_live_test",
  "freshness_label": "older_context",
  "revision_label": "provisional"
}
```

### event_time

The timestamp chosen as the best available time anchor for the record.

Examples:

- message `timestamp` for conversation chunks
- research note `Created` or artifact `created_at`
- journal `journal_date`
- source trace `retrieved_at`
- open loop `created_at` or `last_researched_at`, depending on context

### event_time_source

The field used to derive `event_time`.

Examples:

- `message_timestamp`
- `conversation_started_at`
- `artifact_created_at`
- `research_created_header`
- `journal_date`
- `source_retrieved_at`
- `external_source_created_at`
- `open_loop_last_researched_at`

### relative_age

Human-readable age relative to the current local time.

Examples:

- `today`
- `yesterday`
- `3 days ago`
- `5 weeks ago`
- `unknown age`

### age_band

A coarse deterministic grouping. Initial labels should be conservative and configurable later.

Possible bands:

- `current_conversation`
- `last_24h`
- `2_7_days`
- `1_6_weeks`
- `2_6_months`
- `older_than_6_months`
- `unknown`

Do not overfit these bands before observing retrieval behavior.

### project_phase

The project phase in which the record belongs.

Recommended values:

- `pre_live_test`
- `live_continuity`
- `preserved_historical_test_context`
- `unknown`

### freshness_label

A prompt-facing hint about how current the record may be.

Possible values:

- `current`
- `recent`
- `older_context`
- `stale_candidate`
- `historical`
- `unknown`

This label is not a truth score and must not silently suppress records.

### revision_label

A lifecycle label when available.

Possible values:

- `active`
- `provisional`
- `superseded`
- `archived`
- `revised`
- `unknown`

For research notes, `provisional` is usually the right v1 label. Future working theories may use richer revision labels.

## Recommended First Runtime Target

The first runtime implementation should add temporal labels to:

1. retrieved-memory headers
2. context debug output

Do not change retrieval ranking in the first runtime patch.

Do not add database columns in the first runtime patch.

Do not rewrite indexing paths in the first runtime patch.

## Example Future Retrieved Context Headers

```text
[Research note - 2026-05-22 - 3 days ago - pre-live/test context - provisional working research]
```

```text
[Conversation - 2026-06-12 - yesterday - current live continuity - Lyle]
```

```text
[Moltbook source trace - retrieved 2 hours ago - external context, not truth]
```

These headers should remain concise. If a label is unknown, omit it rather than producing noisy placeholder text.

## Debug Output

Context debug output should include temporal metadata when available.

Recommended debug fields:

```json
{
  "event_time": "...",
  "event_time_source": "...",
  "relative_age": "...",
  "age_band": "...",
  "project_phase": "...",
  "freshness_label": "...",
  "revision_label": "..."
}
```

Debug output should make it easy to see how the visible header was derived.

## Retrieval Ranking

Temporal labels should not affect retrieval ranking in v1.

Do not add hidden temporal downranking.

Do not silently suppress old records.

Do not make `stale_candidate` a ranking penalty in v1.

Reason:

- old memories may be important continuity
- stale source material may still be historically useful
- hidden recency boosts or penalties reduce debuggability
- Project Anam recently moved source trust to metadata-only for similar reasons

Future salience, aging, or temporal decay should be a separate explicit design. If implemented later, it should be configurable, debug-visible, and tested.

## Pre-Live And Live Distinction

After go-live reset, post-reset records should be labeled `live_continuity`.

Pre-live data should be labeled `pre_live_test` unless intentionally imported or preserved.

If pre-live artifacts are intentionally preserved into launch, they should be labeled `preserved_historical_test_context`, not silently treated as live continuity.

The future go-live reset implementation should create a go-live marker or audit timestamp. Temporal framing can use that marker to compute project phase.

The reset process must not delete useful test data accidentally. Backup and restore verification remain prerequisites for destructive reset work.

## Research Notes

Research notes should be temporally framed as provisional records created at a specific time.

Recommended future header:

```text
[Research note - <research_date> - <relative_age> - <project_phase> - provisional working research]
```

Old research notes should not automatically become invalid. They may become `stale_candidate` when:

- they concern current-state claims
- they cite old external source traces
- later research supersedes them
- a future working theory marks them as weakened

Do not mark all old research stale by age alone in v1.

## Journals

Journals should distinguish:

- the day being reflected on: `journal_date`
- the artifact/indexing time: `created_at`

Recommended future header:

```text
[Reflection journal - <journal_date> - <relative_age> - personal reflection]
```

Journals are experience reflections, not timeless facts.

## Open Loops

Open loops should expose:

- created date
- last researched date
- daily iteration local date
- status
- ready-for-synthesis metadata when present

Temporal framing can help choose and inspect loops, but should not become hidden priority ranking without a separate design.

## Source Traces

Source traces should be framed by `retrieved_at`.

External source timestamps should be preserved separately.

Example:

```text
[Moltbook source trace - retrieved 2 hours ago - external context, not truth]
```

For future web source traces, also preserve source timestamps such as `published_at` or `last_modified` when available, but keep `retrieved_at` as the runtime collection timestamp.

## Interaction With Interpretation Traces

Interpretation traces should include temporal context when relevant.

They should note:

- whether prior research is old, recent, pre-live, or live
- when source traces were retrieved
- whether freshness limits interpretation
- whether later material revised an earlier view

Example:

```markdown
- Prior research from 2026-05-22 is pre-live provisional context and may not represent current live continuity.
- Moltbook source trace was retrieved at 2026-05-24T12:00:00+00:00; it is live external context, not truth.
```

Temporal context should support revision and comparison without turning time labels into certainty.

## Interaction With Future Working Theories

Future working theories should track:

- first formed at
- last revised at
- source traces considered
- research notes considered
- superseded or revised status
- stale-candidate status when not revisited after major new evidence
- revision history

Do not implement working theories in v1.

Interpretation traces and temporal labels should provide inputs to future theory revision, not become theories automatically.

## Risks

- Temporal labels may be mistaken for certainty.
- A `stale_candidate` label may undervalue old but important memory.
- Project phase labels may clutter prompts.
- Too much temporal language may encourage theatrical self-narration.
- Hidden temporal ranking would reduce debuggability.
- Pre-live/live distinction could accidentally delete useful test data if mixed with reset behavior.
- External source timestamps may be unreliable but appear authoritative.

## Mitigations

- Labels only, no ranking in v1.
- Concise prompt headers.
- Debug visibility for computed labels.
- Preserve raw timestamps.
- Use an explicit go-live marker after reset.
- Avoid dramatic language.
- Treat external source timestamps as source-provided metadata.
- Omit unknown labels rather than cluttering headers.

## Deferred

- Runtime implementation.
- Prompt changes.
- Retrieval scoring changes.
- Temporal ranking, aging, or decay.
- Database schema changes.
- Chroma or FTS schema changes.
- Working theory integration.
- UI surfaces.
- Go-live reset implementation.
- Automatic stale/superseded inference.
- Any deletion, hiding, or suppression of old records.

