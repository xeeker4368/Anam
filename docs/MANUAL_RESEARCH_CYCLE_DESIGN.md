# Manual Research Cycle Design

Status: implemented through the first bounded CLI path. `research-run` can generate provisional research notes, write them to `workspace/research/`, explicitly register/index them with `--write --register-artifact`, and retrieve them with working-research source framing.

Research continuation now has a design document in `docs/RESEARCH_CONTINUATION_DESIGN.md` and a runtime implementation through `--continue-artifact` and constrained `--continue-file`.

Research open loops now have a design document in `docs/RESEARCH_OPEN_LOOP_DESIGN.md`. Runtime open-loop creation remains deferred.

Still deferred: title/search continuation, open-loop runtime creation, review-item creation, web source collection, working-theory promotion, autonomous research, scheduler behavior, value-density scoring, and any promotion to truth, behavioral guidance, self-understanding, or project decisions.

## Purpose

Manual research should be a user-triggered, bounded artifact-producing workflow.

It should let the operator ask for focused research that produces a durable Markdown artifact with provenance, uncertainty, and follow-up paths. It should not collect research data just to collect it, and it should not silently promote conclusions into truth, guidance, self-understanding, or project decisions.

## Core Principles

- Research artifacts need a purpose and a consumption path.
- Research conclusions are working notes, not truth.
- Research should produce artifacts, possible open loops, and possible review items.
- Research must not silently alter memory authority.
- Research must not mutate behavioral guidance, self-understanding, operational guidance, project decisions, or runtime prompts.
- v1 is manual and user-triggered, not autonomous or scheduled.

## Current Command Shape

Current CLI:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --title "Local LLM avatar box architecture" \
  --question "What architecture should Project Anam use for a Pi-based avatar box?"
```

Default mode is dry-run.

Write mode:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --title "Local LLM avatar box architecture" \
  --question "What architecture should Project Anam use for a Pi-based avatar box?" \
  --write
```

Registration/indexing requires an explicit flag:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --title "Local LLM avatar box architecture" \
  --question "What architecture should Project Anam use for a Pi-based avatar box?" \
  --write \
  --register-artifact
```

Current options include:

- `--scope TEXT`
- `--model MODEL`
- `--register-artifact`
- `--continue-artifact ARTIFACT_ID`
- `--continue-file PATH`

Likely future options:

- `--create-open-loops`
- `--create-review-items`
- later `--continue-title`
- later search-based continuation
- later `--use-web`
- later `--max-sources N`

## Storage Strategy

Write mode creates Markdown files under:

```text
workspace/research/YYYY-MM-DD-<slug>.md
```

The slug should derive from the title and be deterministic enough for review, while avoiding overwriting existing files unless a later explicit revision workflow exists.

## Research Artifact Format

Recommended Markdown structure:

```markdown
# Research Note — <title>

- Question: ...
- Scope: ...
- Created: ...
- Research mode: manual_research_v1
- Sources used: ...
- Provisional: true

## Purpose

## Summary

## Findings

## Uncertainty

## Sources

## Open Questions

## Possible Follow-Ups

## Suggested Review Items

## Working Notes
```

The artifact should state its purpose clearly. If there is no meaningful purpose or likely consumption path, the research should not be run.

## Artifact And Indexing Strategy

`--write` should create the Markdown file only.

`--write --register-artifact` creates the file, registers it as an artifact, and indexes it as research memory.

Recommended metadata:

```json
{
  "source_role": "research_reference",
  "origin": "manual_research",
  "source_type": "research",
  "research_question": "...",
  "research_title": "...",
  "research_date": "YYYY-MM-DD",
  "created_by": "admin_cli",
  "research_version": "manual_research_v1",
  "provisional": true
}
```

Use `artifact_type=research_note`.

Use `source_role=research_reference`.

Use `source_type=research` for indexed chunks.

Use `origin=manual_research` rather than misusing `autonomous_research`.

## Retrieval Source Framing

Retrieved research chunks are labeled:

```text
[Research you wrote on <date> — working research notes]
```

This framing preserves continuity while making clear that research artifacts are working notes, not project decisions, durable behavioral guidance, or permanent truth.

## Consumption Paths

Manual research artifacts currently support:

- retrievable memory as `source_type=research`

Manual research artifacts may later support:

- open loops for unresolved questions
- review items for conclusions needing admin attention
- a future working-theory proposal path
- future behavioral guidance proposals only through the separate behavioral guidance workflow

Research must not directly mutate:

- `BEHAVIORAL_GUIDANCE.md`
- `SELF_UNDERSTANDING.md`
- runtime prompt guidance
- project decisions
- `soul.md`
- `OPERATIONAL_GUIDANCE.md`

## Open Loops And Review Items

Research open-loop design lives in `docs/RESEARCH_OPEN_LOOP_DESIGN.md`.

Open-loop creation should be optional, explicit, and preview-first, likely through `--preview-open-loops` and `--create-open-loops`.

Durable open-loop creation should source-link to a written/registered research artifact.

Review-item creation should be optional and explicit, likely through `--create-review-items`.

Dry-run should print suggested open loops and review items without writing them.

Open loops should represent unresolved questions with concrete next actions. They are not conclusions, beliefs, instructions, project decisions, behavioral guidance, self-understanding, or working theories.

Review items should represent conclusions, contradictions, or decisions that need admin attention.

Neither open loops nor review items should become behavioral guidance automatically.

## Web Search

Web search should be deferred from the first implementation.

`--use-web` needs a separate source collection design, including:

- source limits
- fetch limits
- failure handling
- citation and source capture
- source trace storage
- how web results become artifact evidence

The current foundation avoids autonomous browsing and does not use web search. Web source collection should not be added unless a dedicated web research patch is approved.

## Difference From Normal Chat

Normal chat answers the user in the current conversation.

Manual research produces a durable, titled, scoped, reviewable artifact with provenance and explicit follow-up paths.

Manual research should be consumed later through artifact memory, review surfaces, open loops, or future working-theory proposal mechanisms.

## Risks

Research notes can become hidden authority if retrieved without framing.

Web research can collect sources without a clear purpose.

Unreviewed conclusions can be mistaken for project decisions.

Automatic open-loop or review-item creation can create noise.

Model-only research can hallucinate sources or overstate certainty.

Indexed research can reinforce outdated conclusions if supersession is not designed.

Research can become hidden guidance if findings are injected into runtime prompts as instructions.

## Implementation Phases

1. [x] Design doc only.
2. [x] Add CLI dry-run that generates structured Markdown.
3. [x] Add `--write` to create files under `workspace/research/`.
4. [x] Add `--register-artifact` to register and index with `source_type=research`.
5. [x] Add research retrieval source framing.
6. [x] Design research continuation from prior provisional research notes.
7. [x] Implement manual research continuation from prior provisional research notes.
8. [x] Design research open loops.
9. [ ] Add optional suggested open-loop creation.
10. [ ] Design review-item creation separately.
11. [ ] Add bounded web source collection with explicit `--use-web`.
12. [ ] Add future working-theory proposal path.

## Non-Goals For This Patch

The implemented foundation does not change database schema, web tools, schedulers, guidance files, `SELF_UNDERSTANDING.md`, `soul.md`, or `OPERATIONAL_GUIDANCE.md`.
