# Research Continuation Design

## Status

Implemented for the first manual runtime path. `research-run` supports `--continue-artifact` and constrained `--continue-file`; dry-run remains default; `--write` creates a new continuation note; `--write --register-artifact` registers/indexes the new continuation note.

Still not implemented: title/search continuation, database schema changes, retrieval ranking changes, web search, scheduler, autonomous research, open-loop creation, review-item creation, or promotion paths.

## Purpose

Research continuation is a manual, explicit extension of a prior provisional research note.

It lets the operator continue a line of research without treating the earlier note as final truth, project decision, behavioral guidance, self-understanding, or runtime instruction. Continuation should preserve source framing, uncertainty, and lineage while producing a new provisional research artifact.

## Core Concept

Continuation must:

- use the prior note as source-framed context
- create a new provisional research note
- preserve lineage
- avoid overwriting or revising the old note
- distinguish prior findings from updated findings
- allow weakening or superseding prior claims only in the new note's text and metadata
- avoid mutating the previous artifact

Every continuation is a new note. The previous note remains intact.

## Current Command Shape

Primary command:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --continue-artifact <artifact_id> \
  --question "What changed or what should we examine next?" \
  --scope "Continue prior provisional research."
```

Fallback command:

```bash
.pyanam/bin/python -m tir.admin research-run \
  --continue-file workspace/research/YYYY-MM-DD-topic.md \
  --question "What changed or what should we examine next?"
```

Prefer extending `research-run` over adding a separate `research-continue` command so dry-run, write, register, model, and output conventions stay consistent.

## Source Selection

### Preferred: Artifact ID

Use `--continue-artifact <artifact_id>` as the primary v1 implementation path.

Reason:

- artifact IDs are stable
- registered artifacts already include metadata, path, title, status, and index state
- duplicate titles are possible
- registered artifacts support explicit lineage

The selected artifact should be validated as:

- `artifact_type=research_note`
- active unless an explicit future flag allows inactive artifacts
- metadata `source_type=research`
- metadata `source_role=research_reference`
- metadata `origin=manual_research`
- metadata `provisional=true`

### Fallback: File Path

Use `--continue-file <path>` only as a controlled fallback.

Rules:

- path must resolve under `workspace/research/`
- path must point to an existing Markdown file
- if a registered artifact exactly matches the path, use its metadata for lineage
- if no artifact matches, mark the prior source as file-only/unregistered
- do not infer artifact identity from similar paths or titles

### Deferred: Title

Defer `--continue-title`.

Reason: titles can collide and require disambiguation.

### Deferred: Search

Defer search-based continuation.

Reason: search requires ranking, candidate display, and explicit selection rules before it is safe enough for continuation.

## Continuation Artifact Format

Continuation should create a new Markdown note:

```markdown
# Research Note — <title>

- Question: ...
- Scope: ...
- Created: ...
- Research mode: manual_research_continuation_v1
- Continued from: <title/path/artifact_id/date>
- Sources used: Model-only draft plus prior provisional research note; no external sources collected.
- Provisional: true

## Purpose

## Prior Research Considered

## What Changed / What Is Being Extended

## Updated Findings

## Superseded Or Weakened Prior Claims

## Remaining Uncertainty

## Sources

## New Open Questions

## Possible Follow-Ups

## Suggested Review Items

## Working Notes
```

The Markdown must remain understandable without database access. Lineage should appear in the file, not only in metadata.

## Metadata

Recommended metadata:

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
  "research_version": "manual_research_continuation_v1",
  "provisional": true,
  "continuation_mode": "manual",
  "continuation_of_artifact_id": "...",
  "continuation_of_path": "...",
  "continuation_of_title": "...",
  "continuation_of_research_date": "YYYY-MM-DD"
}
```

For file-only continuation:

- omit `continuation_of_artifact_id`
- keep `continuation_of_path`
- include `continuation_source_registered=false`
- clearly mark the prior source as file-only/unregistered in the generated note

## Prompt Source Framing

Prior research should be supplied to the model as:

```text
[Prior provisional research note]

This prior research note is working research context, not truth, project decision, behavioral guidance, or self-understanding. Use it to continue the investigation, identify what still holds, what is uncertain, and what may need revision.
```

Authority rules:

- Prior findings are inputs, not authorities.
- The new note should distinguish "prior note said" from "updated finding."
- If the continuation disagrees with prior research, it should say so explicitly.
- Do not mutate the prior artifact.
- Do not mark prior claims superseded in DB/file automatically.

## Relationship To Open Loops And Review Items

V1 design keeps open loops and review items as Markdown text only.

Allowed:

- copy or summarize open questions from the prior note
- create a `New Open Questions` section
- list suggested follow-ups
- list suggested review items

Not allowed in v1:

- create open-loop records automatically
- create review-item records automatically
- promote suggested review items into the review queue
- treat open questions as first-class records without an explicit later patch

Future flags such as `--create-open-loops` and `--create-review-items` should be designed separately and should include dry-run previews.

## Difference From Fresh Research

Fresh `research-run` starts from a question and scope.

Continuation starts from:

- a question and scope
- one explicit prior provisional research note
- lineage metadata
- prior findings, uncertainties, open questions, and follow-ups as source-framed context

The output should focus on what changed, what is being extended, what remains uncertain, and which prior claims are weakened or superseded.

## Supersession And Revision

Continuation is not destructive revision.

The continuation note may say that a prior claim is weakened, superseded, or no longer supported. It must not:

- edit the previous file
- update previous artifact metadata
- change previous artifact status
- remove previous chunks
- alter retrieval ranking

Formal working-theory supersession and research-claim promotion should be a separate design.

## Implementation Phases

1. [x] Design doc only.
2. [x] Add continuation artifact lookup/planning helpers.
3. [x] Add `--continue-artifact` dry-run support.
4. [x] Add safe `--continue-file` fallback.
5. [x] Add continuation Markdown format and metadata.
6. [x] Add `--write` support creating a new note.
7. [x] Add `--write --register-artifact` support for continuation notes.
8. Later: disambiguated title/search continuation.
9. Later: explicit open-loop/review-item creation flags.
10. Later: working-theory promotion/supersession rules.

## Implemented Test Coverage

Current implementation tests cover:

- `--continue-artifact` loads the selected research artifact and source file.
- non-research artifacts are rejected.
- missing artifacts fail clearly.
- inactive artifacts are rejected unless explicitly allowed.
- `--continue-file` accepts only files under `workspace/research/`.
- `--continue-file` rejects path traversal and non-Markdown files.
- file-only continuation marks the source as unregistered.
- continuation creates a new note and does not overwrite the old note.
- continuation metadata includes lineage fields.
- `--write --register-artifact` indexes continuation notes as `source_type=research`.
- open-loop and review-item records are not created.
- prior research framing is present in the model prompt.
- prior research is framed as provisional context, not truth.

## Risks

- Prior provisional notes can become hidden authority if framing is weak.
- File-path continuation can bypass metadata unless carefully constrained.
- Title/search continuation can select the wrong artifact.
- Continuation can accumulate stale claims unless weakened/superseded sections are required.
- Lineage only in metadata is not enough; the Markdown should remain understandable outside the DB.
- Future auto-created open loops/review items could create noise without strict previews.

## Non-Goals

This design does not implement runtime code, CLI flags, database schema, artifact ingestion/indexing changes, retrieval ranking changes, web source collection, scheduler behavior, autonomous research, open-loop creation, review-item creation, working-theory promotion, or changes to governance/runtime files.
