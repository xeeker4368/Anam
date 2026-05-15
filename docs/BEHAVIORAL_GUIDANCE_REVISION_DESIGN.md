# Behavioral Guidance Removal / Revision Design

Status: concept design only. Behavioral guidance runtime loading is dormant before go-live. No code, schema, runtime loader, proposal service, UI, or guidance-file behavior is implemented by this document.

## Purpose

The current behavioral guidance apply workflow supports addition proposals only. Future removal and revision proposals need explicit mechanics that preserve history, source traceability, and reviewability.

Behavioral guidance should not be silently deleted or rewritten. Approved removals and revisions should leave an auditable trail in both the proposal records and `BEHAVIORAL_GUIDANCE.md`.

## Core Principles

- AI proposes behavioral guidance changes.
- Admins approve, reject, archive, or reopen proposals.
- Applying approved guidance is explicit and admin-controlled.
- History should be preserved.
- If behavioral guidance is reintroduced later, runtime should load only active guidance.
- Retired or superseded guidance should remain reviewable but should not load as active runtime guidance.
- Raw source records, proposals, reasons, and application history should remain preserved.

## Removal Mechanics

Use retirement, not deletion.

Approved removal proposals should require a stable target identifier, preferably `target_existing_guidance_id` or the target proposal ID. `target_text` may be a fallback only when exact validation succeeds.

Dry-run should show:

- the target active entry
- planned retirement metadata
- the proposed Markdown diff or plan
- the proposal status changes that would occur

Write mode should mark or move the active entry as retired. It should preserve:

- original guidance text
- proposal ID
- source references
- applied timestamp
- scope metadata
- rationale

Retirement metadata should include:

```text
Status: retired
Retired by proposal: <removal proposal_id>
Retired at: <timestamp>
Reason: <removal rationale or apply_note>
```

The removal proposal should be marked `applied` only after the file write succeeds.

The guidance text should not be deleted from the file.

## Revision Mechanics

Use supersession, not in-place rewrite.

Approved revision proposals should require a target active guidance entry by proposal ID or guidance ID. Fuzzy matching should be avoided.

Applying a revision should:

1. retire the old active entry
2. append a new active entry with the revised guidance text
3. link both directions
4. preserve the old text in retired history

The retired old entry should include:

```text
Superseded by proposal: <revision proposal_id>
```

The new active entry should include:

```text
Supersedes: <old proposal_id or guidance_id>
```

Scope changes must be explicit and reviewable. A revision that changes wording and scope should make both changes visible in dry-run output.

## Markdown Representation

Future applied guidance should use deterministic active and retired sections.

```markdown
## Active Guidance

### Guidance <guidance_id-or-proposal_id>

Status: active
Proposal ID: ...
Type: addition
Applied: ...
Scope:
- Users: ...
- Channels: ...
- Contexts: ...
Supersedes: none

- Guidance: ...

## Retired Guidance

### Guidance <old_guidance_id-or-proposal_id>

Status: retired
Proposal ID: ...
Type: addition
Applied: ...
Retired by proposal: ...
Retired at: ...
Reason: ...

- Guidance: ...
```

The current addition-only format can remain valid during migration, but future removal/revision tooling should prefer a parser that understands entry boundaries and status metadata.

## Target Detection

Preferred target matching:

1. exact guidance/proposal ID
2. exact `target_existing_guidance_id`
3. exact `target_text` only as a fallback

Do not support fuzzy text matching without explicit admin confirmation.

If the target entry is missing, already retired, duplicated, or text has changed from the approved target, dry-run and write mode should fail clearly.

## Runtime Loader Implications

If behavioral guidance is reintroduced later, runtime must load only active guidance.

Future loader behavior can either:

- continue extracting only active `- Guidance:` lines under `## Active Guidance`, or
- parse entry-level `Status: active` and ignore `Status: retired`

`## Retired Guidance` must never be loaded into runtime active guidance.

Loader tests should verify:

- retired entries are ignored
- superseded entries are ignored
- revised active entries are loaded
- active scoped entries remain parseable
- metadata does not leak into guidance text unless intentionally loaded

## DB And Proposal Implications

Future proposal records should support stable target identifiers for removal and revision.

`target_existing_guidance_id` should become the preferred target field for removal and revision proposals. `target_text` should remain secondary and must match exactly if used.

Future metadata should support:

- `supersedes_guidance_ids`
- `superseded_by_proposal_id`
- scope metadata
- target validation data
- dry-run plan metadata, if useful

Proposal status should become `applied` only after explicit successful file application. File and database updates are not fully atomic, so implementation should preserve clear recovery paths and diagnostics.

## Scope Interaction

Removal and revision mechanics should preserve scope metadata.

A revision may:

- change guidance text
- narrow scope
- broaden scope
- supersede one or more earlier entries
- retire older guidance only for a specific context in a later scoped implementation

Broadening scope is higher risk and should be explicit in review.

## Dry-Run Diff Preview

Dry-run should be the default.

Dry-run output should include:

- target entry identifier
- target entry status
- operation type: removal or revision
- retirement metadata
- new active entry, for revisions
- scope changes, if any
- a Markdown diff or structured edit plan
- proposal status changes that would be applied

Dry-run must not mutate the file or proposal status.

## Risks

In-place Markdown editing is fragile.

File and database updates are not fully atomic.

Exact text matching can fail after manual formatting changes.

Revision can accidentally broaden scope.

Runtime loader bugs could re-load retired guidance.

Too much metadata in active context could become noisy if extraction is not strict.

Deleting guidance would destroy review history and should be avoided.

## Implementation Phases

1. Design doc only.
2. Add guidance-entry parser and planner for active and retired sections.
3. Add dry-run diff/plan for removal and revision.
4. Implement removal apply with retirement.
5. Implement revision apply with retire-and-append supersession.
6. Add runtime loader tests for active-only behavior.
7. Add scope-aware revision and supersession handling.

## Non-Goals For This Patch

This design does not change code, database schema, runtime loading, proposal services, UI, `BEHAVIORAL_GUIDANCE.md`, `soul.md`, or `OPERATIONAL_GUIDANCE.md`.
