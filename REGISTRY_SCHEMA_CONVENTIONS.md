# Registry Schema Conventions

This document defines default conventions for Project Anam internal registry
tables and services. Registries are metadata foundations for continuity,
diagnostics, review, and future workflows. They do not automatically create
runtime behavior, tool access, memory indexing, autonomy, or self-modification.

## When To Add A Registry

Add a registry/table only when the concept has a distinct lifecycle, required
fields, relationships, and likely future behavior.

Prefer linking existing registries when the concept is only:

- an object or output
- a continuation marker
- a user feedback signal
- an evidence-backed system issue
- a label that can fit cleanly in an existing type/category field

Do not create a new table only because a new word or label exists. A registry
should represent a durable class of record with clear boundaries.

## Standard Field Patterns

Use a primary key named after the concept:

- `artifact_id`
- `open_loop_id`
- `feedback_id`
- `diagnostic_id`
- `<future_registry>_id`

Use `title` when a human-readable label is useful or required. Use
`description` for optional detail.

Use controlled string fields for lifecycle and classification:

- `status`
- `type` or `<concept>_type`
- `category`
- `priority`
- `severity`

Use `metadata_json` for optional structured extensions. Do not place core
fields in metadata when they are important for filtering, lifecycle, or joins.

## Timestamp Conventions

Use ISO 8601 UTC strings consistently.

- `created_at`: when the record was created.
- `updated_at`: when registry metadata or status last changed.
- `closed_at`: when a continuation/lifecycle record is closed. This is
  appropriate for open loops or similar records.
- `resolved_at`: when an issue or feedback record is resolved or archived.
  This is appropriate for diagnostic issues and feedback records.
- `archived_at`: when archival is distinct from closure or resolution. This may
  be appropriate for idea or artifact registries where archival is not the same
  as solving a problem or closing a continuation.

Prefer one terminal timestamp per registry unless the lifecycle genuinely needs
more precision.

## Metadata JSON Rules

Services may accept a `metadata` dict and store it as sorted JSON in
`metadata_json`.

Services should return both:

- `metadata_json`: the stored string
- `metadata`: the decoded dict, or `None`

Reject metadata that is not JSON serializable.

Do not use `metadata_json` as a substitute for fields that need indexes,
validation, lifecycle behavior, or common filters.

## Source-Link Conventions

Use source fields to describe where a record came from:

- `source`
- `source_conversation_id`
- `source_message_id`
- `source_tool_name`

These fields identify origin. They do not imply ownership, current status,
truth, or lifecycle state.

Keep source conversation/message/tool references as loose metadata until stable
cross-registry IDs exist.

## Relationship Conventions

Use nullable foreign keys for links between internal registries when practical.
Examples:

- feedback records can link to artifacts and open loops
- diagnostic issues can link to feedback records, open loops, and artifacts
- future research ideas may link to artifacts, open loops, feedback records, or
  diagnostics

Use loose metadata for conversation IDs, message IDs, tool trace IDs, and target
IDs until those references have stable schema-level identities.

Foundation patches should not add cascading behavior, automatic record creation,
or cross-registry mutation unless explicitly approved.

## Registry Boundaries

### Artifacts

Artifacts are metadata records for created outputs. The artifact is the object
or result.

Examples:

- writing draft
- code output
- research note
- image prompt
- self-modification proposal

Artifact contents live in the workspace/filesystem or external systems, not in
the artifact metadata table.

### Open Loops

Open loops are continuation markers for unfinished, interrupted, unresolved, or
worth-revisiting threads.

Use open loops when something needs future attention, resumption, closure, or
review. Do not use open loops as a generic task manager.

### Feedback Records

Feedback records are structured user learning signals.

Use feedback records when the user corrects, disputes, clarifies, approves,
rejects, or evaluates a result, assumption, memory, tool behavior, or direction.

Feedback records are not model-weight updates and do not automatically alter
operational guidance.

### Diagnostic Issues

Diagnostic issues are evidence-backed records that something in the substrate,
tooling, retrieval, memory, workflow, UI, or behavior may be failing, degrading,
or needing improvement.

Use diagnostic issues for problems and suspected failures. Do not use them as
research queues or generic tasks.

### Research Ideas

Research ideas are possible future inquiries, hypotheses, leads, or questions.

Use research ideas when the core record is an idea worth exploring, not a
created output, unfinished obligation, user correction, or system defect.

### Decision Records

Decision records are records explaining why the entity/system chose a meaningful
action, especially during autonomous cycles, research selection, tool choice,
artifact closure, or self-modification proposal flow.

Project/design decisions remain documented in `DECISIONS.md`.

### Research Sessions

Research sessions are bounded records of research execution or investigation.

Use research sessions for what was attempted, what sources or artifacts were
used, what was found, and what remains unresolved after a research pass.

## Avoiding Schema Bloat

Before adding a registry, check whether the concept is better represented as:

- an artifact
- an open loop
- a feedback record
- a diagnostic issue
- a metadata field on an existing registry
- a link between existing registries

Add a table only when the concept has a separate lifecycle and likely future
operations. Avoid making registries for labels, temporary states, or speculative
categories.

## Legacy Tables

`documents`, `tasks`, and `overnight_runs` are older operational tables. They do
not currently follow every registry convention in this document.

Do not refactor legacy tables as part of documentation-only or new-registry
foundation patches. Do not use legacy `tasks` as a substitute for durable
registries such as research ideas, feedback records, or diagnostic issues.

## Testing And Changelog Expectations

Documentation-only patches should run:

- `git diff --check`

Manual Markdown review is sufficient unless the patch also changes runtime code,
schema, or tests.

Every approved implemented patch should add a changelog entry in `changelog/`.
