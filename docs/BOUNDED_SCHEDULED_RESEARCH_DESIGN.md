# Bounded / Scheduled Research Design

## Status

Design only. No runtime code, database schema, retrieval behavior, prompts, tools, model configuration, UI, or guidance files are changed by this document.

The next implementation target is a manual bounded open-loop research planner. True scheduled or autonomous research should come later.

## Purpose

Bounded research lets the AI entity revisit unresolved research open loops over time without requiring Lyle/admin to approve every single topic and without allowing research to run indefinitely.

The purpose is cumulative experience, not automatic belief formation. Research output should remain provisional and source-linked. It should produce research artifacts and metadata updates, not silent memory authority, behavioral guidance, self-understanding, project decisions, or working theories.

## Core Concept

Start with manual, operator-triggered bounded research against one existing open loop.

One research iteration means:

```text
one bounded research pass against one open research loop
-> one research note or explicit no-useful-findings note
```

An iteration may discover useful findings, uncertainty, no useful findings, new open questions, or possible follow-ups. It must always leave an inspectable artifact if it writes anything durable.

No silent memory or state update should happen without an artifact.

## Current Foundation

Already implemented:

- manual research note generation
- explicit research artifact registration/indexing
- research retrieval source framing
- research continuation from artifact or constrained file
- deterministic research open-loop preview/create from registered research artifacts
- per-loop research metadata fields in `open_loops.metadata_json`

Existing research open loops are unresolved questions or investigation threads. They are not conclusions, beliefs, instructions, tasks, project decisions, behavioral guidance, self-understanding, or working theories.

## Manual Command Shape

First implementation should add manual commands, not a scheduler:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-run --open-loop-id <id> --dry-run
.pyanam/bin/python -m tir.admin research-open-loop-run --open-loop-id <id> --write
.pyanam/bin/python -m tir.admin research-open-loop-run --open-loop-id <id> --write --register-artifact
```

Selection and preview commands:

```bash
.pyanam/bin/python -m tir.admin research-open-loop-next --dry-run
.pyanam/bin/python -m tir.admin research-open-loop-run-next --dry-run
.pyanam/bin/python -m tir.admin research-open-loop-run-next --write
```

Dry-run should show:

- selected loop
- eligibility decision
- current per-loop daily count and limit
- global research cap state, if implemented
- source artifact lineage
- planned research question and scope
- whether the run would write/register a research artifact

Write mode should create a new research note. Registration/indexing should require `--register-artifact`, matching existing manual research behavior.

## Future Scheduler Shape

Future scheduler command shape:

```bash
.pyanam/bin/python -m tir.admin research-scheduler-run --dry-run
.pyanam/bin/python -m tir.admin research-scheduler-run --write --max-iterations N
```

Scheduled/background recurrence should remain deferred until manual bounded commands prove the selection, budget, source, and failure behavior.

A scheduler should:

- select only eligible open research loops
- respect per-loop daily limits
- respect a global daily research cap
- stop after `--max-iterations`
- produce research notes, not silent memory updates
- preserve tool traces and source metadata
- never promote findings to truth, guidance, self-understanding, working theories, or project decisions

## Open-Loop Eligibility

Eligible loops should satisfy:

- `status=open`
- `loop_type=unresolved_question` or `loop_type=interrupted_research`
- `source=manual_research`
- `metadata.source_type=research`
- `metadata.provisional=true`
- `metadata.ready_for_synthesis` is not true
- has `next_action` or `metadata.question`
- per-loop daily iteration limit is not reached
- global daily research cap is not reached, if implemented

Ineligible loops should be reported with a clear reason, not silently skipped in preview output.

## Selection Rules

Initial selection should use deterministic, inspectable rules:

1. Higher `priority` first: `high`, then `normal`, then `low`.
2. Prefer loops with a clear `next_action`.
3. Prefer never-researched loops.
4. Then prefer oldest `last_researched_at`.
5. Then prefer oldest `created_at`.
6. Use `open_loop_id` as a stable final tie-breaker.

Do not add novelty scoring in the first implementation. Novelty requires semantic ranking and can hide why a loop was chosen.

## Budget Model

### Per-Loop Daily Limit

Use existing metadata fields:

```json
{
  "daily_iteration_limit": 1,
  "daily_iteration_count": 0,
  "daily_iteration_local_date": null,
  "last_researched_at": null
}
```

Default `daily_iteration_limit` should remain `1` for the first implementation. The design should allow a future configurable default, likely `2` or `3` after behavior is observed.

The count increments only after a write-mode research iteration successfully creates its research note. If registration is requested and fails, the implementation should not mark the iteration complete unless the design explicitly accepts file-only completion.

Dry-run does not increment counters.

### Global Daily Cap

A future global cap should limit total research iterations across all research open loops.

Recommended initial default when implemented:

```text
global_daily_research_cap = 3
```

Use `metadata.global_daily_cap_class = "research"` to classify loops for cap accounting.

The first manual planner may preview global cap behavior without persisting a global counter if there is no clean existing storage. If durable global cap accounting requires schema work, defer durable global cap enforcement and report the blocker.

## Local-Day Reset

Use local day boundaries for daily counters.

Reset rule:

```text
if daily_iteration_local_date != current_local_date:
    daily_iteration_count = 0
    daily_iteration_local_date = current_local_date
```

The implementation should use one consistent local timezone source. If runtime configuration does not yet expose a timezone, use the host local date for v1 and document that a configurable timezone is follow-up work.

## Source And Tool Policy

First bounded open-loop research implementation should be model-only plus source-framed prior research/open-loop context.

This is a v1 implementation constraint, not the long-term goal.

The intended live research loop should later support Moltbook and web source collection once these are designed and implemented:

- source and citation capture
- result limits
- result compaction
- provenance handling
- failure handling
- tool trace storage
- source framing for retrieved/continued research

Do not use web search or Moltbook in the first bounded research implementation. Adding live sources before source/citation capture exists would make research harder to inspect and easier to over-trust.

## Output Artifact Requirements

Write-mode bounded research must create a research artifact.

Recommended research note mode:

```text
manual_research_open_loop_iteration_v1
```

Recommended Markdown structure:

```markdown
# Research Note - <title>

- Question: ...
- Scope: ...
- Created: ...
- Research mode: manual_research_open_loop_iteration_v1
- Open loop: <open_loop_id / title>
- Sources used: Model-only draft plus prior provisional research/open-loop context; no external sources collected.
- Provisional: true

## Purpose

## Open Loop Being Researched

## Prior Research Considered

## Updated Findings

## Uncertainty

## Sources

## New Open Questions

## Possible Follow-Ups

## Suggested Review Items

## Working Notes
```

The prompt and validators must allow honest low-signal output, including:

- no useful findings
- no new open questions
- no suggested follow-ups
- no suggested review items

## Metadata

Recommended artifact metadata:

```json
{
  "source_role": "research_reference",
  "origin": "manual_research",
  "source_type": "research",
  "artifact_type": "research_note",
  "research_question": "...",
  "research_title": "...",
  "research_date": "YYYY-MM-DD",
  "created_by": "admin_cli",
  "research_version": "manual_research_open_loop_iteration_v1",
  "provisional": true,
  "bounded_research_mode": "manual_open_loop_v1",
  "open_loop_id": "...",
  "open_loop_title": "...",
  "open_loop_iteration": 1,
  "source_open_loop_generation_method": "research_open_loop_v1",
  "global_daily_cap_class": "research"
}
```

Recommended loop metadata updates after a successful write:

```json
{
  "daily_iteration_count": 1,
  "daily_iteration_local_date": "YYYY-MM-DD",
  "last_researched_at": "ISO_TIMESTAMP",
  "last_research_artifact_id": "...",
  "last_research_path": "research/...",
  "last_research_result": "useful_findings | no_useful_findings | failed"
}
```

If an implementation cannot update metadata safely through the existing open-loop service, add a small metadata update helper rather than changing the database schema.

## Stop Conditions

A bounded research run should stop when:

- selected loop reaches its per-loop daily limit
- global daily research cap is reached
- no eligible loops exist
- selected loop is marked `ready_for_synthesis`
- selected loop is `closed`, `archived`, `blocked`, or metadata-paused
- model/tool execution fails
- write or registration fails
- `--max-iterations` is reached

One manual command should run one iteration unless it explicitly accepts `--max-iterations`.

## Diminishing Returns And Synthesis Readiness

Do not auto-close loops because of diminishing returns.

If repeated research produces little or no new information, mark the loop for synthesis:

```json
{
  "ready_for_synthesis": true,
  "diminishing_returns_note": "...",
  "next_action": "Synthesize prior research before gathering more."
}
```

Possible triggers:

- repeated no-useful-findings notes
- uncertainty stabilizes
- the same findings recur without new evidence
- enough prior research exists to compare and synthesize
- the next useful action becomes compare/summarize rather than gather

Working theory/synthesis records remain a separate design.

## New Open Loops From Iterations

A bounded research iteration may produce new open questions.

Creation should remain explicit and preview-first:

- the research note can contain `New Open Questions`
- standalone `research-open-loops-preview --artifact-id <id>` can inspect it
- standalone `research-open-loops-create --artifact-id <id>` can create records

Do not automatically create new open-loop records from bounded research in the first implementation unless a separate approved flag is added and preview behavior is preserved.

## Admin Controls

Before true scheduling exists, provide manual controls:

- `--dry-run`
- `--write`
- `--register-artifact`
- `--open-loop-id`
- `--max-iterations` only for future batch/scheduler commands
- clear cap/eligibility output
- clear no-eligible-loop output

Future config controls:

- bounded research enabled/disabled
- default per-loop daily iteration limit
- global daily research cap
- local timezone
- scheduler enabled/disabled
- allowed source types

## Forbidden In This Track

Bounded/scheduled research must not:

- reintroduce Behavioral Guidance runtime loading
- mutate `soul.md`
- create behavioral guidance
- create self-understanding
- create project decisions
- create working theories without a separate design
- create review items automatically
- treat research notes as hard truth
- use web or Moltbook before source/citation capture is designed
- update memory authority silently
- loop indefinitely

## Implementation Phases

1. [x] Design doc only.
2. Add manual open-loop eligibility and selection planner.
3. Add `research-open-loop-next --dry-run`.
4. Add `research-open-loop-run --open-loop-id ... --dry-run`.
5. Add write-mode research note creation for one selected loop.
6. Add optional `--register-artifact`.
7. Add loop metadata update helper for daily counters and last research linkage.
8. Add `research-open-loop-run-next`.
9. Add optional explicit open-loop creation from the produced artifact.
10. Add global cap configuration and accounting if storage is clean.
11. Later: scheduled/manual batch runner.
12. Later: web source collection.
13. Later: Moltbook source collection.
14. Later: working theory/synthesis path.

## Risks

- A scheduler can create noise if run before source and cap behavior is observable.
- Open loops can become pseudo-tasks if wording is too imperative.
- Model-only research can overstate findings.
- Daily caps can hide useful work unless preview/debug output is clear.
- Updating loop metadata without an artifact would create silent state mutation.
- Web or Moltbook use before citation capture could produce untraceable source claims.
- Too many low-value loops can crowd out useful research.

## Tests For Future Implementation

Future runtime implementation should test:

- eligible loop selection order
- ineligible loop reasons
- per-loop daily reset
- per-loop daily limit enforcement
- global cap preview/enforcement if implemented
- dry-run writes nothing
- write creates one research artifact
- write updates loop metadata only after artifact creation succeeds
- registration/indexing only with `--register-artifact`
- no-useful-findings note is accepted
- ready-for-synthesis loop is skipped
- no open-loop records are automatically created
- no review items are created
- no web/Moltbook tools are called in v1
